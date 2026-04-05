import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import signal

from lxdrive.config import LOG_DIR


@dataclass
class MountInfo:
    remote_name: str
    mount_point: Path
    pid: Optional[int]
    is_active: bool


class MountManager:
    def __init__(self):
        self.rclone_path = shutil.which("rclone")
        self.active_mounts: dict[str, MountInfo] = {}
        self._verify_fuse_available()
    
    def _verify_fuse_available(self) -> tuple[bool, str]:
        fusermount = shutil.which("fusermount3") or shutil.which("fusermount")
        if not fusermount:
            return False, "FUSE no está disponible. Instala fuse3 o fuse"
        
        if not os.path.exists("/dev/fuse"):
            return False, "El dispositivo /dev/fuse no existe. Habilita FUSE en tu sistema"
        
        return True, ""
    
    def check_mount_requirements(self) -> tuple[bool, str]:
        if not self.is_available():
            return False, "rclone no está instalado"
        
        return self._verify_fuse_available()
    
    def is_available(self) -> bool:
        return self.rclone_path is not None
    
    def mount(
        self,
        remote_name: str,
        local_path: Path,
        options: dict = None,
        daemon: bool = True
    ) -> tuple[bool, str]:
        check_ok, check_msg = self.check_mount_requirements()
        if not check_ok:
            return False, check_msg
        
        local_path = Path(local_path)
        
        if not os.access(str(local_path.parent), os.W_OK):
            return False, f"No tienes permisos de escritura en: {local_path.parent}"
        
        if self.is_mounted(local_path):
            return False, f"Ya está montado: {local_path}"
        
        fuse_check, fuse_msg = self._verify_fuse_available()
        if not fuse_check:
            return False, fuse_msg
        
        default_options = {
            "vfs-cache-mode": "full",
            "vfs-cache-max-age": "24h",
            "vfs-cache-max-size": "10G",
            "buffer-size": "64M",
            "dir-cache-time": "72h",
            "poll-interval": "15s",
            "allow-non-empty": "",
        }
        
        if options:
            default_options.update(options)
        
        cmd = [self.rclone_path, "mount", f"{remote_name}:", str(local_path)]
        
        for key, value in default_options.items():
            if value == "":
                cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])
        
        if daemon:
            cmd.append("--daemon")
        
        log_file = LOG_DIR / f"mount-{remote_name}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, "w") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Comando: {' '.join(cmd)}\n")
        
        cmd.extend(["--log-file", str(log_file), "-vv"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                time.sleep(1)
                if self.is_mounted(local_path):
                    self.active_mounts[str(local_path)] = MountInfo(
                        remote_name=remote_name,
                        mount_point=local_path,
                        pid=None,
                        is_active=True
                    )
                    return True, f"Montado {remote_name} en {local_path}"
                else:
                    return False, "El comando rclone retornó éxito pero el montaje no se completó. Revisa el log para más detalles."
            
            error_msg = result.stderr.strip() if result.stderr.strip() else result.stdout.strip()
            if not error_msg:
                error_msg = "Error desconocido al montar"
            
            detailed_msg = self._get_mount_error_details(log_file)
            if detailed_msg:
                error_msg = f"{error_msg}\n\nDetalles del log:\n{detailed_msg}"
            
            return False, error_msg
        except subprocess.TimeoutExpired:
            return False, "Timeout al montar (el comando tardó más de 30 segundos)"
        except PermissionError:
            return False, "Permiso denegado. ¿Tienes FUSE configurado correctamente?"
        except FileNotFoundError:
            return False, "No se encontró rclone. ¿Está instalado?"
        except Exception as e:
            return False, f"Error al montar: {str(e)}"
    
    def _get_mount_error_details(self, log_file: Path, max_lines: int = 20) -> str:
        try:
            if log_file.exists():
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    error_lines = [l.strip() for l in lines if "ERROR" in l.upper() or "FAILED" in l.upper() or "panic" in l.lower()]
                    if error_lines:
                        return "\n".join(error_lines[-max_lines:])
        except Exception:
            pass
        return ""
    
    def unmount(self, mount_point: Path) -> tuple[bool, str]:
        mount_point = Path(mount_point)
        
        if not self.is_mounted(mount_point):
            return False, f"No esta montado: {mount_point}"
        
        fusermount = shutil.which("fusermount3") or shutil.which("fusermount")
        
        if fusermount:
            try:
                result = subprocess.run(
                    [fusermount, "-u", str(mount_point)],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if result.returncode == 0:
                    str_path = str(mount_point)
                    if str_path in self.active_mounts:
                        del self.active_mounts[str_path]
                    return True, f"Desmontado {mount_point}"
            except Exception as e:
                pass
        
        try:
            result = subprocess.run(
                ["umount", str(mount_point)],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                str_path = str(mount_point)
                if str_path in self.active_mounts:
                    del self.active_mounts[str_path]
                return True, f"Desmontado {mount_point}"
        except Exception as e:
            pass
        
        try:
            result = subprocess.run(
                ["umount", "-l", str(mount_point)],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                str_path = str(mount_point)
                if str_path in self.active_mounts:
                    del self.active_mounts[str_path]
                return True, f"Desmontado (lazy) {mount_point}"
        except Exception as e:
            return False, f"Error al desmontar: {e}"
        
        return False, "No se pudo desmontar"
    
    def is_mounted(self, path: Path) -> bool:
        path = Path(path)
        try:
            return os.path.ismount(str(path))
        except Exception:
            return False
    
    def list_mounts(self) -> list[MountInfo]:
        mounts = []
        
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        mount_point = parts[1]
                        if "rclone" in line or "fuse" in line:
                            mount_info = MountInfo(
                                remote_name="unknown",
                                mount_point=Path(mount_point),
                                pid=None,
                                is_active=True
                            )
                            mounts.append(mount_info)
        except Exception:
            pass
        
        return mounts
    
    def get_mount_info(self, mount_point: Path) -> Optional[MountInfo]:
        str_path = str(mount_point)
        if str_path in self.active_mounts:
            return self.active_mounts[str_path]
        return None
