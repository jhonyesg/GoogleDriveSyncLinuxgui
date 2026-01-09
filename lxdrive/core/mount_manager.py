#!/usr/bin/env python3
"""
MountManager - Gestión de montajes de unidades

Este módulo permite montar las cuentas de cloud storage
como unidades de disco usando rclone mount.
"""

import subprocess
import os
import signal
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from loguru import logger

from .rclone_wrapper import RcloneWrapper
from .account_manager import Account, AccountManager


@dataclass
class MountInfo:
    """Información de un punto de montaje activo"""
    account_id: str
    remote_name: str
    mount_point: str
    process_id: Optional[int] = None
    is_mounted: bool = False


class MountManager:
    """
    Gestiona el montaje de remotes como unidades de disco.
    
    Usa rclone mount para crear sistemas de archivos FUSE
    que permiten acceder a los archivos remotos como si fueran locales.
    """
    
    def __init__(
        self, 
        rclone: RcloneWrapper, 
        account_manager: AccountManager
    ):
        """
        Inicializa el gestor de montajes.
        
        Args:
            rclone: Wrapper de rclone
            account_manager: Gestor de cuentas
        """
        self.rclone = rclone
        self.account_manager = account_manager
        
        # Procesos de montaje activos: account_id -> proceso
        self._mount_processes: Dict[str, subprocess.Popen] = {}
        
        # Directorio base para puntos de montaje
        self.mount_base_dir = Path.home() / "CloudDrives"
        self._ensure_mount_dir()
    
    def _ensure_mount_dir(self):
        """Crea el directorio base para montajes si no existe"""
        self.mount_base_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directorio de montajes: {self.mount_base_dir}")
    
    def _get_mount_point(self, account: Account) -> Path:
        """
        Obtiene el punto de montaje para una cuenta.
        
        Args:
            account: Cuenta a montar
            
        Returns:
            Path del punto de montaje
        """
        if account.mount_point:
            return Path(account.mount_point)
        
        # Generar nombre basado en el nombre de la cuenta
        safe_name = "".join(c for c in account.name if c.isalnum() or c in " _-")
        return self.mount_base_dir / safe_name
    
    def mount(self, account_id: str) -> Tuple[bool, str]:
        """
        Monta una cuenta y activa el monitoreo de actividad.
        """
        if not self.rclone.is_installed():
            return False, "rclone no está instalado"
        
        account = self.account_manager.get_by_id(account_id)
        if not account:
            return False, "Cuenta no encontrada"
        
        if self.is_mounted(account_id):
            return True, "Ya está montada"
        
        mount_point = self._get_mount_point(account)
        mount_point.mkdir(parents=True, exist_ok=True)
        
        # 1. Notificar inicio de montaje en la UI
        self._emit_activity(account_id, "Unidad Virtual", "mounted", "Montando raíz del Drive...")

        # Comando con nivel DEBUG para ver APERTURA de archivos (Open)
        cmd = [
            self.rclone.rclone_path, "mount",
            f"{account.remote_name}:", # Montar la raíz, SIEMPRE
            str(mount_point),
            "--vfs-cache-mode", "full",
            "--vfs-cache-max-age", "24h",
            "--vfs-cache-max-size", "10G",
            "--log-level", "DEBUG",  # Cambiado de INFO a DEBUG para ver 'Open'
            "--stats", "1s",
            "--attr-timeout", "10s",
            "--dir-cache-time", "1m",
            "--vfs-read-chunk-size", "128M",
            "--use-json-log=false"
        ]
        
        try:
            # Lanzamos rclone
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                start_new_session=True
            )
            self._mount_processes[account_id] = process
            
            # Hilo monitor
            import threading
            threading.Thread(target=self._monitor_mount_activity, args=(account_id, process), daemon=True).start()
            
            # Esperar un momento a que FUSE se estabilice
            import time
            time.sleep(1.5)
            
            if self.is_mounted(account_id):
                account.mount_enabled = True
                self.account_manager.update(account)
                # Notificación retardada para asegurar que la UI esté lista
                # QTimer.singleShot(500, lambda: self._emit_activity(account_id, "Sistema", "mounted", "Unidad VFS Lista"))
                self._emit_activity(account_id, "Sistema", "mounted", "Unidad VFS Lista")
                return True, ""
            
            # Si no está montado después de la espera, el proceso puede haber fallado o no se ha registrado
            # Leer el posible error de rclone si el proceso ya terminó
            error_output = "El proceso rclone se inició pero la unidad no aparece montada."
            if process.poll() is not None: # Check if process has terminated
                # Try to read any remaining output from the process
                try:
                    remaining_output = process.stdout.read().strip()
                    if remaining_output:
                        error_output = remaining_output
                except Exception as read_err:
                    logger.warning(f"Error reading rclone output after mount failure: {read_err}")
            
            return False, error_output[:200] # Limit error message length
            
        except Exception as e:
            logger.error(f"Excepción al montar: {e}")
            return False, str(e)

    def _monitor_mount_activity(self, account_id, process):
        """Monitor de logs con detección inteligente de patrones"""
        try:
            logger.info(f"Monitor de actividad activo para: {account_id}")
            last_line = ""
            while True:
                line = process.stdout.readline()
                if not line: break
                
                line = line.strip()
                if not line or line == last_line: continue
                last_line = line
                
                lower_line = line.lower()
                filename = None
                action = None
                
                # 1. Detectar acción por palabras clave (Modo DEBUG de rclone mount)
                if any(x in lower_line for x in ["downloaded", "opening for read", "open:", "get"]):
                    action = "vfs_read"
                elif any(x in lower_line for x in ["flushed", "opening for write", "put", "upload", "write", "create", "mkdir"]):
                    action = "vfs_write"

                if action:
                    # 2. Intentar extraer nombre de archivo
                    if "'" in line:
                        parts = line.split("'")
                        if len(parts) >= 2: filename = parts[1]
                    elif " : " in line:
                        parts = line.split(" : ")
                        if len(parts) >= 2:
                            msg_part = parts[1]
                            # En modo DEBUG el path suele ir antes de ": Open:" o similar
                            if ":" in msg_part:
                                filename = msg_part.split(":")[0].strip()

                    # 3. Validar y notificar
                    if filename and len(filename) > 1 and "vfs cache" not in filename.lower():
                        filename = filename.lstrip("/")
                        
                        # FILTRO DE RUIDO: Ignorar archivos temporales de sistema/apps
                        # Si quieres ver TODO, puedes comentar estas líneas
                        noise = [".lock", ".tmp", "desktop.ini", "thumbs.db", ".part"]
                        if any(n in filename.lower() for n in noise):
                            continue
                            
                        self._emit_activity(account_id, filename, action, filename)
                        
        except Exception as e:
            logger.error(f"Error en hilo de monitorización: {e}")
        finally:
            logger.info(f"Monitor finalizado para {account_id}")

    def _emit_activity(self, account_id, name, action, path):
        """Notifica la actividad a la UI"""
        if hasattr(self, 'on_activity_callback') and self.on_activity_callback:
            # Enviamos account_id, name, action, path
            self.on_activity_callback(account_id, name, action, path)

    def set_activity_callback(self, callback):
        """Configura el callback para recibir eventos de actividad"""
        self.on_activity_callback = callback

    def unmount(self, account_id: str) -> Tuple[bool, str]:
        """
        Desmonta una cuenta.
        """
        account = self.account_manager.get_by_id(account_id)
        if not account: return False, "Cuenta no encontrada"
        
        mount_point = self._get_mount_point(account)
        
        try:
            # Intentar fusermount -u
            subprocess.run(["fusermount", "-uz", str(mount_point)], 
                         check=True, capture_output=True)
            
            account.mount_enabled = False
            self.account_manager.update(account)
            return True, ""
        except Exception as e:
            # Si falla, intentar umount normal
            try:
                subprocess.run(["umount", str(mount_point)], 
                             check=True, capture_output=True)
                account.mount_enabled = False
                self.account_manager.update(account)
                return True, ""
            except Exception as e2:
                # Si rclone ya no está o el punto no está, forzamos el estado a desconectado
                if not self.is_mounted(account_id):
                    account.mount_enabled = False
                    self.account_manager.update(account)
                    return True, "Ya estaba desmontado"
                return False, f"Error al desmontar: {e2}"
    
    def is_mounted(self, account_id: str) -> bool:
        """
        Verifica si una cuenta está montada.
        
        Args:
            account_id: ID de la cuenta
            
        Returns:
            True si está montada
        """
        account = self.account_manager.get_by_id(account_id)
        if not account:
            return False
        
        mount_point = self._get_mount_point(account)
        
        # Verificar si el punto de montaje está en /proc/mounts
        try:
            with open("/proc/mounts", "r") as f:
                mounts = f.read()
                return str(mount_point) in mounts
        except IOError:
            return account_id in self._mount_processes
    
    def get_mounted_accounts(self) -> List[MountInfo]:
        """
        Obtiene información de todas las cuentas montadas.
        
        Returns:
            Lista de MountInfo
        """
        mounted = []
        
        for account in self.account_manager.get_mount_accounts():
            mount_point = self._get_mount_point(account)
            process = self._mount_processes.get(account.id)
            
            mounted.append(MountInfo(
                account_id=account.id,
                remote_name=account.remote_name,
                mount_point=str(mount_point),
                process_id=process.pid if process else None,
                is_mounted=self.is_mounted(account.id)
            ))
        
        return mounted
    
    def mount_all(self) -> int:
        """
        Monta todas las cuentas configuradas para montaje.
        
        Returns:
            Número de cuentas montadas exitosamente
        """
        mounted_count = 0
        
        for account in self.account_manager.get_mount_accounts():
            if self.mount(account.id):
                mounted_count += 1
        
        logger.info(f"Montadas {mounted_count} cuentas")
        return mounted_count
    
    def unmount_all(self) -> int:
        """
        Desmonta todas las cuentas que estén realmente montadas en el sistema.
        
        Returns:
            Número de cuentas desmontadas exitosamente
        """
        unmounted_count = 0
        
        # Iterar sobre todas las cuentas para asegurar limpieza total
        for account in self.account_manager.get_all():
            if self.is_mounted(account.id):
                success, _ = self.unmount(account.id)
                if success:
                    unmounted_count += 1
        
        # Limpiar diccionario de procesos por si acaso
        self._mount_processes.clear()
        
        logger.info(f"Desmontadas {unmounted_count} cuentas")
        return unmounted_count
    
    def open_mount_point(self, account_id: str) -> bool:
        """
        Abre el punto de montaje en el explorador de archivos.
        
        Args:
            account_id: ID de la cuenta
            
        Returns:
            True si se abrió correctamente
        """
        account = self.account_manager.get_by_id(account_id)
        if not account:
            return False
        
        mount_point = self._get_mount_point(account)
        
        if not mount_point.exists():
            logger.error(f"Punto de montaje no existe: {mount_point}")
            return False
        
        try:
            # Intentar con xdg-open (estándar en Linux)
            subprocess.Popen(
                ["xdg-open", str(mount_point)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except FileNotFoundError:
            # Si no está xdg-open, intentar con otros
            for cmd in ["nautilus", "dolphin", "thunar", "pcmanfm", "nemo"]:
                try:
                    subprocess.Popen(
                        [cmd, str(mount_point)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return True
                except FileNotFoundError:
                    continue
        
        logger.error("No se encontró explorador de archivos")
        return False
