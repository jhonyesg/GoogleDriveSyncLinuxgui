import os
import shutil
import subprocess
import threading
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import signal

from lxdrive.config import LOG_DIR, TaskStatus
from lxdrive.backend.models import SyncTask, TaskManager
from lxdrive.utils.logger import get_logger


class FileWatcher:
    def __init__(self, path: Path, poll_interval: int = 30):
        self.path = Path(path).expanduser()
        self.poll_interval = poll_interval
        self._file_hashes: Dict[str, str] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: list = []
    
    def _compute_file_hash(self, file_path: Path) -> str:
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _scan_directory(self) -> Dict[str, str]:
        hashes = {}
        if self.path.exists():
            for item in self.path.rglob('*'):
                if item.is_file():
                    try:
                        rel_path = item.relative_to(self.path)
                        hashes[str(rel_path)] = self._compute_file_hash(item)
                    except Exception:
                        pass
        return hashes
    
    def _check_for_changes(self) -> bool:
        current_hashes = self._scan_directory()
        
        if current_hashes != self._file_hashes:
            self._file_hashes = current_hashes
            return True
        return False
    
    def _watch_loop(self):
        self._file_hashes = self._scan_directory()
        
        while self._running:
            time.sleep(self.poll_interval)
            if not self._running:
                break
            
            if self._check_for_changes():
                for callback in self._callbacks:
                    try:
                        callback(self.path)
                    except Exception as e:
                        pass
    
    def add_callback(self, callback):
        self._callbacks.append(callback)
    
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)


class SyncManager:
    def __init__(self):
        self.rclone_path = shutil.which("rclone")
        self.active_syncs: dict = {}
        self.watchers: Dict[str, FileWatcher] = {}
        self.logger = get_logger()
    
    def is_available(self) -> bool:
        return self.rclone_path is not None
    
    def check_sync_requirements(self) -> tuple[bool, str]:
        if not self.is_available():
            return False, "rclone no está instalado"
        
        if not os.path.exists("/dev/fuse"):
            return False, "FUSE no está disponible"
        
        return True, ""
    
    def validate_local_path(self, local_path: Path) -> tuple[bool, str]:
        local_path = Path(local_path).expanduser()
        
        if not local_path.is_absolute():
            return False, "La ruta local debe ser una ruta absoluta"
        
        parent = local_path.parent
        if not parent.exists():
            return False, f"El directorio padre no existe: {parent}"
        
        if not os.access(str(parent), os.W_OK):
            return False, f"No tienes permisos de escritura en: {parent}"
        
        if local_path.exists():
            if not local_path.is_dir():
                return False, f"La ruta existe pero no es un directorio: {local_path}"
            if not os.access(str(local_path), os.R_OK | os.W_OK):
                return False, f"No tienes permisos de lectura/escritura en: {local_path}"
        
        return True, ""
    
    def _normalize_remote_path(self, path: str) -> str:
        path = path.strip()
        if path.startswith("/"):
            path = path[1:]
        return path
    
    def _validate_remote(self, remote_name: str) -> tuple:
        if not self.is_available():
            return False, "rclone no esta instalado"
        
        remote_name = remote_name.strip().rstrip(":")
        
        try:
            result = subprocess.run(
                [self.rclone_path, "listremotes"],
                capture_output=True,
                text=True,
                timeout=10
            )
            remotes = [r.strip().rstrip(":") for r in result.stdout.strip().split("\n") if r.strip()]
            
            if remote_name not in remotes:
                return False, f"El remote '{remote_name}' no existe. Remotos disponibles: {', '.join(remotes)}"
            
            return True, "OK"
        except Exception as e:
            return False, str(e)
    
    def run_sync(
        self,
        task: SyncTask,
        watch: bool = False,
        dry_run: bool = False,
        force_resync: bool = False,
        _retrying: bool = False
    ) -> tuple:
        if not self.is_available():
            return False, "rclone no está instalado"
        
        check_ok, check_msg = self.check_sync_requirements()
        if not check_ok:
            return False, check_msg
        
        if task.id in self.active_syncs:
            return False, "Ya hay una sincronización en curso"
        
        valid, msg = self._validate_remote(task.remote_name)
        if not valid:
            return False, msg
        
        local_path = Path(task.local_path.strip()).expanduser()
        
        valid_path, path_msg = self.validate_local_path(local_path)
        if not valid_path:
            return False, path_msg
        
        if not local_path.exists():
            try:
                local_path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return False, f"Permiso denegado al crear: {local_path}"
            except Exception as e:
                return False, f"No se puede crear la carpeta local: {e}"
        
        remote_path = self._normalize_remote_path(task.remote_path)
        remote_full = f"{task.remote_name}:{remote_path}"
        
        bisync_dir = local_path / ".bisync"
        needs_resync = force_resync or not bisync_dir.exists()
        
        cmd = [
            self.rclone_path,
            "bisync",
            str(local_path),
            remote_full,
            "--track-renames",
            "--drive-import-formats", "docx,xlsx,pptx,doc,xls,ppt,odt,ods,odp",
            "--log-level", "INFO",
        ]
        
        if needs_resync:
            cmd.append("--resync")
        
        if dry_run:
            cmd.append("--dry-run")
        
        for f in task.filters:
            cmd.extend(["--filter", f])
        
        log_file = LOG_DIR / f"sync-{task.id}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--log-file", str(log_file)])
        
        task.status = TaskStatus.RUNNING
        task_manager = TaskManager()
        task_manager.update_task(task)
        self.active_syncs[task.id] = True
        
        try:
            self.logger.debug(f"Iniciando sincronización: {' '.join(cmd)}")
            
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
                try:
                    stdout, stderr = proc.communicate(timeout=120)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                    return False, "Timeout: sincronización tardó más de 2 minutos"
            
            result = proc.returncode
            
            if result == 0:
                task.last_sync = datetime.now()
                task.last_sync_result = "Éxito"
                task.status = TaskStatus.IDLE
                task.sync_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "result": "Éxito",
                    "message": "Sincronización completada"
                })
                if len(task.sync_history) > 10:
                    task.sync_history = task.sync_history[-10:]
                
                task_manager.update_task(task)
                self.logger.info(f"Sincronización exitosa para {task.name}")
                
                return True, "Sincronización completada exitosamente"
            
            task.status = TaskStatus.ERROR
            self.logger.error(f"Sincronización fallida para {task.name}: {result}")
            
            error_msg = stderr.strip() if stderr else stdout.strip()
            
            if not error_msg and log_file.exists():
                try:
                    with open(log_file, "r") as f:
                        content = f.read()
                        if "Failed to bisync:" in content:
                            lines = content.split("\n")
                            for line in reversed(lines):
                                if "Failed to bisync:" in line:
                                    error_msg = line.split("Failed to bisync:")[1].strip()
                                    break
                except:
                    pass
            
            if not error_msg:
                error_msg = "Error desconocido"
            
            error_lower = error_msg.lower()
            
            if "quota" in error_lower or "rate limit" in error_lower or "429" in error_msg:
                error_msg = "Límite de Google Drive alcanzado. Espera unos minutos e intenta de nuevo."
            elif "must run --resync" in error_lower:
                if not _retrying:
                    return self.run_sync(task, watch, dry_run, force_resync=True, _retrying=True)
                else:
                    error_msg = "Error de sincronización. Intenta de nuevo."
            elif "directory not found" in error_lower:
                error_msg = "Directorio no encontrado"
            elif "not found" in error_lower:
                error_msg = "Carpeta no encontrada"
            elif ".lck" in error_lower and "no such file" in error_lower:
                error_msg = "Lock de sincronización anterior. Reintentando..."
                if not _retrying:
                    return self.run_sync(task, watch, dry_run, force_resync=True, _retrying=True)
            elif "prior lock" in error_lower:
                cache_dir = Path.home() / ".cache" / "rclone" / "bisync"
                if cache_dir.exists():
                    for lock_file in cache_dir.glob("*.lck"):
                        try:
                            lock_file.unlink()
                        except:
                            pass
                error_msg = "Había un lock de sincronización anterior. Reintentando..."
                if not _retrying:
                    return self.run_sync(task, watch, dry_run, force_resync=True, _retrying=True)
            elif "critical error" in error_lower:
                if not _retrying:
                    return self.run_sync(task, watch, dry_run, force_resync=True, _retrying=True)
                else:
                    error_msg = "Error en la sincronización inicial. Verifica la conexión y los permisos."
            elif "google document type" in error_lower:
                if not _retrying:
                    return self.run_sync(task, watch, dry_run, force_resync=True, _retrying=True)
                else:
                    error_msg = "Error con documentos de Google Drive. Intenta de nuevo."
            elif "failed to bisync" in error_lower:
                error_msg = f"Error de sincronización: {error_msg}"
            
            task.last_sync_result = f"Error: {error_msg}"
            task.sync_history.append({
                "timestamp": datetime.now().isoformat(),
                "result": "Error",
                "message": error_msg
            })
            if len(task.sync_history) > 10:
                task.sync_history = task.sync_history[-10:]
            
            task_manager = TaskManager()
            task_manager.update_task(task)
            
            return False, error_msg
            
        except subprocess.TimeoutExpired:
            task.status = TaskStatus.ERROR
            return False, "Timeout - la operacion tardo demasiado"
        except FileNotFoundError as e:
            task.status = TaskStatus.ERROR
            return False, f"Archivo no encontrado: {e}"
        except PermissionError as e:
            task.status = TaskStatus.ERROR
            return False, f"Error de permisos: {e}"
        except Exception as e:
            task.status = TaskStatus.ERROR
            return False, f"Error: {str(e)}"
    
    def stop_sync(self, task_id: str) -> tuple:
        if task_id not in self.active_syncs:
            return False, "No hay sincronizacion activa"
        
        process = self.active_syncs[task_id]
        try:
            process.terminate()
            process.wait(timeout=10)
            del self.active_syncs[task_id]
            return True, "Sincronizacion detenida"
        except subprocess.TimeoutExpired:
            process.kill()
            del self.active_syncs[task_id]
            return True, "Sincronizacion detenida"
        except Exception as e:
            return False, str(e)
    
    def get_sync_status(self, task_id: str) -> Optional[TaskStatus]:
        if task_id not in self.active_syncs:
            return None
        
        process = self.active_syncs[task_id]
        poll = process.poll()
        
        if poll is None:
            return TaskStatus.RUNNING
        elif poll == 0:
            return TaskStatus.IDLE
        else:
            return TaskStatus.ERROR
    
    def cleanup(self):
        for task_id in list(self.active_syncs.keys()):
            try:
                self.active_syncs[task_id].terminate()
                self.active_syncs[task_id].wait(timeout=5)
            except:
                try:
                    self.active_syncs[task_id].kill()
                except:
                    pass
        self.active_syncs.clear()
        self.stop_all_watchers()
    
    def start_watcher(self, task: SyncTask, poll_interval: int = 30) -> bool:
        if task.id in self.watchers:
            return False
        
        local_path = Path(task.local_path.strip()).expanduser()
        watcher = FileWatcher(local_path, poll_interval=poll_interval)
        
        def on_change(path):
            self._trigger_sync(task)
        
        watcher.add_callback(on_change)
        watcher.start()
        self.watchers[task.id] = watcher
        return True
    
    def stop_watcher(self, task_id: str) -> bool:
        if task_id not in self.watchers:
            return False
        
        self.watchers[task_id].stop()
        del self.watchers[task_id]
        return True
    
    def stop_all_watchers(self):
        for task_id in list(self.watchers.keys()):
            self.watchers[task_id].stop()
        self.watchers.clear()
    
    def _trigger_sync(self, task: SyncTask):
        if task.id in self.active_syncs:
            return
        
        task.status = TaskStatus.SYNCING
        threading.Thread(target=self._run_sync_background, args=(task,), daemon=True).start()
    
    def _run_sync_background(self, task: SyncTask):
        task_manager = TaskManager()
        self.active_syncs[task.id] = True
        try:
            success, msg = self.run_sync(task, watch=False)
        finally:
            if task.id in self.active_syncs:
                del self.active_syncs[task.id]
