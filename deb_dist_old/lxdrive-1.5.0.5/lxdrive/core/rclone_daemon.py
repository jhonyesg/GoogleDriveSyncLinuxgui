#!/usr/bin/env python3
"""
RcloneDaemon - Gestor del daemon rclone rcd

Maneja el inicio, detención y monitoreo del servidor
rclone Remote Control.
"""

import subprocess
import time
import signal
import os
from pathlib import Path
from typing import Optional
from loguru import logger


class RcloneDaemon:
    """
    Gestor del daemon rclone rcd.
    
    Inicia y gestiona el servidor RC de rclone en segundo plano
    para permitir acceso a la API de control remoto.
    """
    
    def __init__(
        self,
        port: int = 5572,
        user: str = "lxdrive",
        password: str = "lxdrive_rc_2026",
        config_path: Optional[Path] = None
    ):
        """
        Inicializa el gestor del daemon.
        
        Args:
            port: Puerto para el servidor RC
            user: Usuario para autenticación
            password: Password para autenticación
            config_path: Ruta al archivo de configuración de rclone
        """
        self.port = port
        self.user = user
        self.password = password
        self.config_path = config_path or Path.home() / ".config" / "rclone" / "rclone.conf"
        self.process: Optional[subprocess.Popen] = None
        self.pid_file = Path.home() / ".cache" / "lxdrive" / "rclone_rcd.pid"
        
    def is_running(self) -> bool:
        """
        Verifica si el daemon está corriendo.
        
        Returns:
            True si el proceso está activo
        """
        # Verificar por proceso
        if self.process and self.process.poll() is None:
            return True
        
        # Verificar por PID file
        if self.pid_file.exists():
            try:
                with open(self.pid_file) as f:
                    pid = int(f.read().strip())
                
                # Verificar si el proceso existe
                try:
                    os.kill(pid, 0)  # Signal 0 solo verifica existencia
                    return True
                except OSError:
                    # Proceso no existe, limpiar PID file
                    self.pid_file.unlink()
                    return False
                    
            except (ValueError, FileNotFoundError):
                return False
        
        return False
    
    def start(self) -> bool:
        """
        Inicia el daemon rclone rcd.
        
        Returns:
            True si se inició correctamente
        """
        if self.is_running():
            logger.info("rclone rcd ya está corriendo")
            return True
        
        try:
            # Crear directorio para PID file
            self.pid_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Construir comando
            cmd = [
                "rclone", "rcd",
                "--rc-addr", f"localhost:{self.port}",
                "--rc-no-auth",  # Sin autenticación para localhost
                "--rc-allow-origin", "*",  # Permitir CORS
                "--log-level", "INFO"
            ]
            
            if self.config_path.exists():
                cmd.extend(["--config", str(self.config_path)])
            
            # Log file
            log_file = self.pid_file.parent / "rclone_rcd.log"
            
            logger.info(f"Iniciando rclone rcd en puerto {self.port}...")
            
            # Iniciar proceso en background
            with open(log_file, "w") as log:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True  # Desacoplar del proceso padre
                )
            
            # Guardar PID
            with open(self.pid_file, "w") as f:
                f.write(str(self.process.pid))
            
            # Esperar a que inicie
            max_wait = 5
            for i in range(max_wait):
                time.sleep(1)
                if self.is_running():
                    logger.info(f"✅ rclone rcd iniciado (PID: {self.process.pid})")
                    return True
            
            logger.error("rclone rcd no respondió después de 5 segundos")
            return False
            
        except FileNotFoundError:
            logger.error("rclone no está instalado en el sistema")
            return False
        except Exception as e:
            logger.error(f"Error iniciando rclone rcd: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Detiene el daemon rclone rcd.
        
        Returns:
            True si se detuvo correctamente
        """
        if not self.is_running():
            logger.info("rclone rcd no está corriendo")
            return True
        
        try:
            pid = None
            
            # Obtener PID
            if self.process:
                pid = self.process.pid
            elif self.pid_file.exists():
                with open(self.pid_file) as f:
                    pid = int(f.read().strip())
            
            if pid:
                logger.info(f"Deteniendo rclone rcd (PID: {pid})...")
                
                # Intentar detención graceful
                try:
                    os.kill(pid, signal.SIGTERM)
                    
                    # Esperar hasta 5 segundos
                    for _ in range(5):
                        time.sleep(1)
                        try:
                            os.kill(pid, 0)
                        except OSError:
                            # Proceso terminó
                            break
                    else:
                        # Si no terminó, forzar
                        logger.warning("Forzando detención de rclone rcd...")
                        os.kill(pid, signal.SIGKILL)
                        time.sleep(1)
                    
                except ProcessLookupError:
                    # Ya estaba muerto
                    pass
            
            # Limpiar PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
            
            self.process = None
            logger.info("✅ rclone rcd detenido")
            return True
            
        except Exception as e:
            logger.error(f"Error deteniendo rclone rcd: {e}")
            return False
    
    def restart(self) -> bool:
        """
        Reinicia el daemon.
        
        Returns:
            True si se reinició correctamente
        """
        logger.info("Reiniciando rclone rcd...")
        self.stop()
        time.sleep(2)
        return self.start()
    
    def get_log_path(self) -> Path:
        """
        Obtiene la ruta del archivo de log.
        
        Returns:
            Path al archivo de log
        """
        return self.pid_file.parent / "rclone_rcd.log"
    
    def get_logs(self, lines: int = 50) -> str:
        """
        Obtiene las últimas líneas del log.
        
        Args:
            lines: Número de líneas a obtener
            
        Returns:
            String con el contenido del log
        """
        log_file = self.get_log_path()
        
        if not log_file.exists():
            return "No hay logs disponibles"
        
        try:
            with open(log_file) as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as e:
            return f"Error leyendo logs: {e}"
