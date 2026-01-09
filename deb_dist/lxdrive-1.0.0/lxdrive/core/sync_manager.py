import threading
import time
from pathlib import Path
from typing import Optional, Dict, Callable, Any, Tuple, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from loguru import logger

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("Watchdog no instalado. La detección de cambios instantánea no funcionará. (pip install watchdog)")

from .account_manager import Account, AccountManager, SyncStatus, SyncDirection
from .rclone_wrapper import RcloneWrapper


class ChangeHandler(FileSystemEventHandler):
    """Manejador de eventos del sistema de archivos"""
    def __init__(self, callback, debounce=2.0):
        self.callback = callback
        self.debounce = debounce
        self._timer: Optional[threading.Timer] = None
        
    def on_any_event(self, event):
        if event.is_directory: return
        # Log de debug para confirmar detección
        logger.debug(f"Detectado cambio local en: {event.src_path}")
        
        # Debounce para evitar múltiples llamadas por un solo cambio
        if self._timer: self._timer.cancel()
        self._timer = threading.Timer(self.debounce, self.callback)
        self._timer.start()


@dataclass
class SyncTask:
    """Representa una tarea de sincronización"""
    account_id: str
    source: str
    dest: str
    direction: SyncDirection
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    success: bool = False
    message: str = ""
    files_transferred: int = 0
    bytes_transferred: int = 0


class SyncManager:
    """
    Gestiona la sincronización automática de cuentas.
    
    Características:
    - Sincronización periódica en segundo plano
    - Cola de tareas de sincronización
    - Callbacks para reportar progreso
    - Manejo de errores y reintentos
    """
    
    def __init__(
        self, 
        rclone: RcloneWrapper, 
        account_manager: AccountManager
    ):
        """
        Inicializa el gestor de sincronización.
        
        Args:
            rclone: Wrapper de rclone
            account_manager: Gestor de cuentas
        """
        self.rclone = rclone
        self.account_manager = account_manager
        
        # Estado interno
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._active_syncs: set = set()  # Conjunto de IDs activos para concurrencia
        self._pending_syncs: set = set() # Cola de IDs que necesitan sync al terminar la actual
        
        # Historial de listados para detectar renombres manualmente si rclone falla
        self._last_listings: Dict[str, Dict[str, Any]] = {}  # {pair_id: {file_name: {size, time}}}
        
        
        # Callbacks
        self._on_sync_start: Optional[Callable[[str], None]] = None
        self._on_sync_complete: Optional[Callable[[SyncTask], None]] = None
        self._on_sync_error: Optional[Callable[[str, str], None]] = None
        self._on_progress: Optional[Callable[[str, float], None]] = None
        self._on_file_activity: Optional[Callable[[str, str, str, str], None]] = None  # (acc_id, name, action, path)
        
        
        # Callbacks
        self._last_sync_times: Dict[str, datetime] = {}
        
        # Watchdog
        self._observer = Observer() if WATCHDOG_AVAILABLE else None
        self._watchers: Dict[str, Any] = {} # Map de path -> watcher

    def set_callbacks(
        self,
        on_start=None,
        on_complete=None,
        on_error=None,
        on_progress=None,
        on_activity=None
    ):
        """Configura los callbacks para eventos de sincronización"""
        self._on_sync_start = on_start
        self._on_sync_complete = on_complete
        self._on_sync_error = on_error
        self._on_progress = on_progress
        self._on_file_activity = on_activity
    
    def start(self):
        """Inicia el servicio de sincronización en segundo plano"""
        if self._running:
            logger.warning("El servicio de sincronización ya está corriendo")
            return
        
        self._running = True
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        
        # Iniciar Watchdog
        if self._observer:
            try:
                self._observer.start()
                # Registrar carpetas
                for account in self.account_manager.get_enabled_accounts():
                    self._start_watching(account)
                logger.info("Monitor de cambios en tiempo real (Watchdog) iniciado")
            except Exception as e:
                logger.error(f"Error iniciando Watchdog: {e}")

        logger.info("Servicio de sincronización iniciado")
    
    def stop(self):
        """Detiene el servicio de sincronización"""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
            
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join()
            except: pass
            
        logger.info("Servicio de sincronización detenido")
    
    def _start_watching(self, account: Account):
        """Inicia la vigilancia de carpetas locales"""
        if not self._observer: return
        
        for pair in account.sync_pairs:
            if not pair.enabled: continue
            path = str(Path(pair.local_path).resolve())
            
            if path in self._watchers: continue
            
            try:
                # Usamos un lambda que captura el ID de la cuenta para sincronizar
                handler = ChangeHandler(lambda acc_id=account.id: self.sync_now(acc_id))
                self._observer.schedule(handler, path, recursive=True)
                self._watchers[path] = handler
                logger.info(f"Vigilando cambios en: {path}")
            except Exception as e:
                logger.warning(f"No se pudo vigilar {path}: {e}")

    def is_running(self) -> bool:
        """Verifica si el servicio está corriendo"""
        return self._running
    
    def is_sync_active(self, sync_id: str) -> bool:
        """Verifica si una sincronización específica está activa"""
        with self._lock:
            return sync_id in self._active_syncs

    def get_active_syncs(self) -> list:
        """Obtiene lista de IDs activos"""
        with self._lock:
            return list(self._active_syncs)
    
    def _sync_loop(self):
        """Bucle principal de sincronización"""
        while self._running:
            try:
                self._check_and_sync()
            except Exception as e:
                logger.error(f"Error en bucle de sincronización: {e}")
            
            # Esperar antes de la siguiente verificación
            time.sleep(5)  # Verificar cada 5 segundos
    
    def _check_and_sync(self):
        """Verifica qué cuentas necesitan sincronización"""
        accounts = self.account_manager.get_enabled_accounts()
        now = datetime.now()
        
        for account in accounts:
            if account.status == SyncStatus.PAUSED:
                continue
            
            # Verificar si es momento de sincronizar
            last_sync = self._last_sync_times.get(account.id)
            
            if last_sync is None:
                # Primera sincronización
                self._sync_account(account)
            else:
                elapsed = (now - last_sync).total_seconds()
                if elapsed >= account.sync_interval:
                    self._sync_account(account)
    
    def _sync_account(self, account: Account):
        """
        Sincroniza una cuenta específica.
        
        Args:
            account: Cuenta a sincronizar
        """
        with self._lock:
            if account.id in self._active_syncs:
                return  # Ya está sincronizando esta cuenta
            self._active_syncs.add(account.id)
        
        task = SyncTask(
            account_id=account.id,
            source="",
            dest="",
            direction=account.sync_direction,
            started_at=datetime.now()
        )
        
        try:
            logger.info(f"Iniciando sincronización: {account.name}")
            
            if self._on_sync_start:
                self._on_sync_start(account.id)
            
            all_success = True
            error_messages = []
            now = datetime.now()

            for pair in account.sync_pairs:
                if not pair.enabled: continue
                
                pair_success, pair_message = self._sync_single_pair(account, pair)
                
                if not pair_success:
                    all_success = False
                    error_messages.append(f"{Path(pair.local_path).name}: {pair_message}")

            # Finalizar tarea global
            task.success = all_success
            task.completed_at = datetime.now()
            task.message = "\n".join(error_messages) if error_messages else "Sincronización completada"
            
            self._last_sync_times[account.id] = datetime.now()
            self.account_manager.set_status(account.id, SyncStatus.IDLE if all_success else SyncStatus.ERROR)

            if not all_success and self._on_sync_error:
                self._on_sync_error(account.id, task.message)

            if self._on_sync_complete:
                self._on_sync_complete(task)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Excepción en sincronización: {error_msg}")
            self.account_manager.set_status(account.id, SyncStatus.ERROR, error_msg)
            
            task.success = False
            task.message = error_msg
            
            if self._on_sync_error:
                self._on_sync_error(account.id, error_msg)
                
        finally:
            with self._lock:
                self._active_syncs.discard(account.id)
    
    def sync_now(self, account_id: str) -> bool:
        """Sincroniza toda la cuenta (todos sus pares) inmediatamente"""
        if self.is_sync_active(account_id): return False
        
        account = self.account_manager.get_by_id(account_id)
        if not account: return False
        thread = threading.Thread(target=self._sync_account, args=(account,))
        thread.start()
        return True

    def sync_pair_now(self, account_id: str, pair_id: str) -> bool:
        """Sincroniza un par específico inmediatamente"""
        lock_id = f"{account_id}:{pair_id}"
        if self.is_sync_active(lock_id):
            logger.warning(f"Sincronización ya activa para {lock_id}")
            return False
            
        account = self.account_manager.get_by_id(account_id)
        if not account: return False
        
        pair = next((p for p in account.sync_pairs if p.id == pair_id), None)
        if not pair: return False

        thread = threading.Thread(target=self._sync_single_pair_thread, args=(account, pair, lock_id))
        thread.start()
        return True

    def _sync_single_pair_thread(self, account, pair, lock_id=None):
        """Hilo para sincronizar un solo par"""
        # Si no nos pasan lock_id, lo generamos (caso de uso interno raro pero posible)
        if not lock_id: lock_id = f"{account.id}:{pair.id}"

        with self._lock:
            if lock_id in self._active_syncs: return
            self._active_syncs.add(lock_id)
            
        try:
            if self._on_sync_start: self._on_sync_start(account.id)
            success, msg = self._sync_single_pair(account, pair)
            
            task = SyncTask(
                account_id=account.id,
                source=pair.local_path,
                dest=pair.remote_path,
                direction=pair.direction,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=success,
                message=msg
            )
            if self._on_sync_complete: self._on_sync_complete(task)
            self.account_manager.set_status(account.id, SyncStatus.IDLE if success else SyncStatus.ERROR)
        except Exception as e:
            logger.error(f"Error en sync manual de par: {e}")
        finally:
            with self._lock:
                self._active_syncs.discard(lock_id)

    def _sync_single_pair(self, account, pair) -> Tuple[bool, str]:
        """Lógica central para sincronizar un par (SyncPair)"""
        logger.info(f"Sincronizando par: {pair.local_path} -> {pair.remote_path}")
        
        # Buffer heurístico para renombres
        recent_events = []
        
        # Determinar estado
        pair_status = SyncStatus.SYNCING
        if not pair.last_sync: pair_status = SyncStatus.RESYNCING
        self.account_manager.set_status(account.id, pair_status)
        
        remote_path = f"{account.remote_name}:{pair.remote_path}"
        local_path = pair.local_path
        
        def run_bisync(resync_mode):
            inner_success = True
            inner_message = "Sincronización completada"
            
            if self._on_file_activity:
                self._on_file_activity(account.id, Path(local_path).name, "sync_start", "Sincronización iniciada")
            
            # --- PRE-LIMPIEZA PROACTIVA ---
            # Si hay un lock file huérfano de una sesión anterior fallida, rclone fallará inmediatamente.
            # Intentamos detectarlo antes de empezar.
            try:
                bisync_cache = Path.home() / ".cache" / "rclone" / "bisync"
                if bisync_cache.exists():
                    # Buscamos archivos .lck que parezcan de este par
                    # Rclone nombra: path1..path2.lck donde pathX tiene / y : reemplazados
                    # Hacemos una búsqueda laxa para limpiar basura obvia
                    for f in bisync_cache.glob("*.lck"):
                        # Si el archivo tiene más de 5 minutos, asumimos que es zombie (rclone bisync no suele tardar tanto en lock sin actividad)
                        try:
                            mtime = f.stat().st_mtime
                            if time.time() - mtime > 300: # 5 minutos
                                logger.warning(f"Limpiando lock file antiguo/zombie: {f.name}")
                                f.unlink()
                        except: pass
            except: pass

            logger.info(f"Lanzando bisync (resync={resync_mode}) para {account.name} - {Path(local_path).name}")
            
            for line in self.rclone.bisync_stream(local_path, remote_path, resync=resync_mode):
                line = line.strip()
                if not line: continue
                logger.debug(f"RCLONE_RAW: {line}")
                line_lower = line.lower()
                
                logger.debug(f"RCLONE_RAW: {line}")
                line_lower = line.lower()
                
                if any(x in line_lower for x in ["error", "fatal", "failed", "critical"]):
                    # Ignorar avisos que no son errores fatales de ejecución
                    if "ignoring" in line_lower:
                        continue
                        
                    logger.error(f"rclone error fatal: {line}")
                    inner_success = False
                    inner_message = line
                    try:
                        if ":" in line:
                            msg = line.split(":")[-1].strip()
                            if self._on_file_activity:
                                self._on_file_activity(account.id, "Error Grave", "error", msg)
                    except: pass
                elif "INFO" in line:
                    # Descartar líneas de resumen estadístico para no ensuciar la actividad
                    if "changes:" in line_lower or "delta" in line_lower or "synchronizing" in line_lower:
                        continue

                    if any(x in line_lower for x in ["copied", "updated", "deleted", "moved", "skipped", "removed"]):
                        try:
                            content = line.split("INFO")[-1].strip()
                            if content.startswith(":"): content = content[1:].strip()
                            
                            parts = [p.strip() for p in content.split(":")]
                            file_path = None
                            action = "uploading"

                            # Formato 1: "PathX: ruta/al/archivo: Acción" (3 o más partes)
                            if len(parts) >= 3 and ("Path1" in parts[0] or "Path2" in parts[0]):
                                file_path = parts[1]
                                action_text = parts[2].lower()
                                if "Path2" in parts[0] or "download" in action_text:
                                    action = "downloading"
                            
                            # Formato 2: "ruta/al/archivo: Acción" (2 partes, común en borrados o resync)
                            elif len(parts) >= 2:
                                # Asegurarse de que parts[0] no sea un nivel de log o PathX
                                if not any(x in parts[0] for x in ["Path1", "Path2", "INFO", "NOTICE"]):
                                    file_path = parts[0]
                                    action_text = parts[1].lower()
                                    if "download" in action_text: action = "downloading"
                            
                            if file_path:
                                # Limpiar el nombre del archivo
                                file_name = file_path.split("/")[-1]
                                
                                # Refinar acción por palabras clave en toda la línea
                                if any(x in line_lower for x in ["deleted", "removing", "removed", "unlink"]):
                                    action = "deleted"
                                elif any(x in line_lower for x in ["moved", "renamed", "renaming"]):
                                    action = "moved"
                                
                                # Validar que no estemos capturando una palabra clave de rclone como archivo
                                if file_name.lower() not in ["deleted", "copied", "updated", "moved", "skipped", "changes", "renamed"]:
                                    # Heurística de Renombres: Buffer temporal
                                    # Si vemos Deleted A y Uploading B (misma ext, misma carpeta) -> MOVED
                                    
                                    # Guardamos evento actual
                                    current_event = {
                                        "name": file_name,
                                        "path": file_path,
                                        "action": action,
                                        "time": time.time(),
                                        "ext": Path(file_path).suffix,
                                        "parent": str(Path(file_path).parent)
                                    }
                                    
                                    # Buscar coincidencia en eventos recientes (últimos 3 segs)
                                    matched_rename = False
                                    for prev in recent_events[:]:
                                        # Limpiar eventos viejos (> 5s)
                                        if current_event["time"] - prev["time"] > 5:
                                            recent_events.remove(prev)
                                            continue
                                            
                                        # Lógica de emparejamiento:
                                        # 1. Uno Deleted y otro Uploading
                                        # 2. Misma extensión (ej .zip)
                                        # 3. Misma carpeta padre
                                        if (prev["action"] == "deleted" and action == "uploading") or \
                                           (prev["action"] == "uploading" and action == "deleted"):
                                            
                                            if prev["ext"] == current_event["ext"] and \
                                               prev["parent"] == current_event["parent"]:
                                                
                                                # ¡Es un renombre! Emitimos MOVED con el nombre nuevo
                                                final_name = file_name if action == "uploading" else prev["name"]
                                                final_path = file_path if action == "uploading" else prev["path"]
                                                
                                                if self._on_file_activity:
                                                    # Avisar que fue renombrado (sobrescribimos la acción anterior visualmente si se pudo, 
                                                    # pero como es asíncrono, mejor emitimos el evento limpio)
                                                    self._on_file_activity(account.id, final_name, "moved", final_path)
                                                
                                                matched_rename = True
                                                recent_events.remove(prev) # Consumir evento
                                                break
                                    
                                    if not matched_rename:
                                        recent_events.append(current_event)
                                        # Emitir evento normal si no se emparejó (aún)
                                        # Nota: Esto puede mostrar "Deleted" brevemente antes del "Moved", 
                                        # pero es mejor que perder el evento si no se empareja.
                                        if self._on_file_activity:
                                            self._on_file_activity(account.id, file_name, action, file_path)
                                        
                        except Exception as e:
                            logger.debug(f"Error parseando línea INFO: {e}")
            
            return inner_success, inner_message

        # Ejecución
        with self._lock:
            # Actualizar estado
            pair.status = SyncStatus.SYNCING
            self.account_manager.update(account)
        
        # 1. Intentar Sincronización Normal (Primero confiamos en rclone)
        success, message = run_bisync(not pair.last_sync)
        
        # Reintento si falla (Protocolo de REPARACIÓN GRADUAL)
        if not success:
            # Solo si el error es de LOCK FILE prior, intervenimos
            if "lock file found" in message or "prior lock" in message:
                logger.warning(f"Bloqueo detectado para {account.name}. Intentando desbloqueo...")
                
                try:
                    # Estrategia 1: Usar la ruta exacta si el mensaje de error nos la dio
                    lock_path_extracted = None
                    if "prior lock file found: " in message:
                        lock_path_extracted = message.split("prior lock file found: ")[-1].strip()
                        
                    if lock_path_extracted and Path(lock_path_extracted).exists():
                         logger.info(f"Eliminando LOCK específico reportado: {lock_path_extracted}")
                         Path(lock_path_extracted).unlink()
                    else:
                        # Estrategia 2: Búsqueda heurística (Fallback)
                        cache_path = Path.home() / ".cache" / "rclone" / "bisync"
                        if cache_path.exists():
                            safe_local = "".join(c if c.isalnum() else "_" for c in local_path)
                            for f in cache_path.glob("*.lck"):
                                if safe_local in f.name or "lxdrive" in f.name:
                                    logger.info(f"Desbloqueando sesión (heurística): {f.name}")
                                    f.unlink()
                except FileNotFoundError:
                    pass # Ya se borró, mejor
                except Exception as e:
                    logger.warning(f"No se pudo limpiar lock: {e}")

                # Intento 2: Reintentar NORMAL tras desbloqueo
                logger.info("Reintentando sincronización tras desbloqueo...")
                time.sleep(1) # Dar un respiro al filesystem
                success, message = run_bisync(False)

            # Si sigue fallando (o no era lock), vamos a resync
            if not success:
                logger.error("Iniciando LIMPIEZA PROFUNDA (Resync)...")
                try:
                    # Limpiar todo lo relacionado para forzar resync
                    cache_path = Path.home() / ".cache" / "rclone" / "bisync"
                    if cache_path.exists():
                        safe_local = "".join(c if c.isalnum() else "_" for c in local_path)
                        for f in cache_path.glob("*"):
                            if safe_local in f.name:
                                f.unlink()
                except: pass
                
                # Intento 3 con resync forzado
                success, message = run_bisync(True)

        if success:
            pair.last_sync = datetime.now().isoformat()
            self.account_manager.update(account)
            
        return success, message

    def pause_account(self, account_id: str):
        """Pausa la sincronización de una cuenta"""
        self.account_manager.set_status(account_id, SyncStatus.PAUSED)
        logger.info(f"Cuenta pausada: {account_id}")
    
    def resume_account(self, account_id: str):
        """Reanuda la sincronización de una cuenta"""
        self.account_manager.set_status(account_id, SyncStatus.IDLE)
        logger.info(f"Cuenta reanudada: {account_id}")
    
    def pause_all(self):
        """Pausa todas las sincronizaciones"""
        for account in self.account_manager.get_all():
            self.pause_account(account.id)
    
    def resume_all(self):
        """Reanuda todas las sincronizaciones"""
        for account in self.account_manager.get_all():
            if account.sync_enabled:
                self.resume_account(account.id)
