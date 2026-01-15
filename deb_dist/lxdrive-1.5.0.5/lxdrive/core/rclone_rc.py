#!/usr/bin/env python3
"""
RcloneRC - Cliente para rclone Remote Control API

Proporciona acceso a la API JSON-RPC de rclone para obtener
información estructurada y precisa sobre transferencias y operaciones.
"""

import requests
import threading
import time
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from loguru import logger


@dataclass
class TransferInfo:
    """Información de una transferencia en curso"""
    name: str
    size: int
    bytes_transferred: int
    percentage: int
    speed: float  # bytes/sec
    eta: int  # segundos
    group: str
    
    @property
    def speed_mbps(self) -> float:
        """Velocidad en MB/s"""
        return self.speed / (1024 * 1024)
    
    @property
    def eta_formatted(self) -> str:
        """ETA formateado como HH:MM:SS"""
        hours = self.eta // 3600
        minutes = (self.eta % 3600) // 60
        seconds = self.eta % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@dataclass
class TransferStats:
    """Estadísticas globales de transferencias"""
    bytes_transferred: int
    checks: int
    deletes: int
    elapsed_time: float
    errors: int
    eta: Optional[int]
    fatalError: bool
    renames: int
    retryError: bool
    speed: float
    totalBytes: int
    totalChecks: int
    totalTransfers: int
    transferring: List[TransferInfo]
    transfers: int


class RcloneRC:
    """
    Cliente para rclone Remote Control API.
    
    Permite obtener información estructurada en tiempo real sobre:
    - Transferencias activas
    - Estadísticas de sincronización
    - Estado de operaciones
    - Eventos de archivos
    """
    
    def __init__(
        self, 
        host: str = "localhost",
        port: int = 5572,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Inicializa el cliente RC.
        
        Args:
            host: Host donde corre rclone rcd
            port: Puerto del servidor RC
            user: Usuario para autenticación (opcional)
            password: Password para autenticación (opcional)
        """
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        
        if user and password:
            self.session.auth = (user, password)
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: Dict[str, Callable] = {}
        
        logger.info(f"RcloneRC inicializado en {self.base_url}")
    
    def is_available(self) -> bool:
        """
        Verifica si el servidor RC está disponible.
        
        Returns:
            True si el servidor responde
        """
        try:
            response = self.session.post(
                f"{self.base_url}/rc/noop",
                timeout=2
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"RC no disponible: {e}")
            return False
    
    def get_stats(self, group: str = "") -> Optional[TransferStats]:
        """
        Obtiene estadísticas de transferencias.
        
        Args:
            group: Grupo de operaciones (vacío = todas)
            
        Returns:
            TransferStats con la información o None si falla
        """
        try:
            response = self.session.post(
                f"{self.base_url}/core/stats",
                json={"group": group},
                timeout=5
            )
            
            if response.status_code != 200:
                logger.warning(f"RC stats error: {response.status_code}")
                return None
            
            data = response.json()
            
            # Parsear transferencias activas
            transferring = []
            for t in data.get("transferring", []):
                transferring.append(TransferInfo(
                    name=t.get("name", ""),
                    size=t.get("size", 0),
                    bytes_transferred=t.get("bytes", 0),
                    percentage=t.get("percentage", 0),
                    speed=t.get("speed", 0.0),
                    eta=t.get("eta", 0),
                    group=t.get("group", "")
                ))
            
            return TransferStats(
                bytes_transferred=data.get("bytes", 0),
                checks=data.get("checks", 0),
                deletes=data.get("deletes", 0),
                elapsed_time=data.get("elapsedTime", 0.0),
                errors=data.get("errors", 0),
                eta=data.get("eta"),
                fatalError=data.get("fatalError", False),
                renames=data.get("renames", 0),
                retryError=data.get("retryError", False),
                speed=data.get("speed", 0.0),
                totalBytes=data.get("totalBytes", 0),
                totalChecks=data.get("totalChecks", 0),
                totalTransfers=data.get("totalTransfers", 0),
                transferring=transferring,
                transfers=data.get("transfers", 0)
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo stats de RC: {e}")
            return None
    
    def list_active_jobs(self) -> List[Dict[str, Any]]:
        """
        Lista todos los trabajos activos.
        
        Returns:
            Lista de diccionarios con información de jobs
        """
        try:
            response = self.session.post(
                f"{self.base_url}/job/list",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("jobids", [])
            
            return []
            
        except Exception as e:
            logger.error(f"Error listando jobs: {e}")
            return []
    
    def get_job_status(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado de un job específico.
        
        Args:
            job_id: ID del job
            
        Returns:
            Diccionario con el estado del job
        """
        try:
            response = self.session.post(
                f"{self.base_url}/job/status",
                json={"jobid": job_id},
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo status de job {job_id}: {e}")
            return None
    
    def set_callbacks(
        self,
        on_transfer: Optional[Callable[[TransferInfo], None]] = None,
        on_complete: Optional[Callable[[TransferStats], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        """
        Configura callbacks para eventos de transferencia.
        
        Args:
            on_transfer: Llamado por cada archivo en transferencia
            on_complete: Llamado cuando completa una operación
            on_error: Llamado cuando hay un error
        """
        if on_transfer:
            self._callbacks["transfer"] = on_transfer
        if on_complete:
            self._callbacks["complete"] = on_complete
        if on_error:
            self._callbacks["error"] = on_error
    
    def start_monitoring(self, interval: float = 1.0):
        """
        Inicia monitoreo continuo de transferencias.
        
        Args:
            interval: Intervalo de polling en segundos
        """
        if self._monitoring:
            logger.warning("Monitoreo ya está activo")
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("Monitoreo de RC iniciado")
    
    def stop_monitoring(self):
        """Detiene el monitoreo continuo"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Monitoreo de RC detenido")
    
    def _monitor_loop(self, interval: float):
        """
        Bucle de monitoreo en segundo plano.
        
        Args:
            interval: Intervalo entre checks
        """
        last_transfers = set()
        
        while self._monitoring:
            try:
                stats = self.get_stats()
                
                if stats:
                    # Detectar nuevas transferencias
                    current_transfers = {t.name for t in stats.transferring}
                    
                    # Notificar transferencias activas
                    if "transfer" in self._callbacks:
                        for transfer in stats.transferring:
                            self._callbacks["transfer"](transfer)
                    
                    # Detectar completadas (estaban antes, ya no están)
                    completed = last_transfers - current_transfers
                    if completed and "complete" in self._callbacks:
                        self._callbacks["complete"](stats)
                    
                    # Detectar errores
                    if stats.errors > 0 and "error" in self._callbacks:
                        self._callbacks["error"](f"{stats.errors} errores detectados")
                    
                    last_transfers = current_transfers
                
            except Exception as e:
                logger.error(f"Error en monitor loop: {e}")
            
            time.sleep(interval)
    
    def get_bandwidth_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de ancho de banda.

        Returns:
            Diccionario con bytes/s de subida y bajada
        """
        try:
            response = self.session.post(
                f"{self.base_url}/core/bwlimit",
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "rate": data.get("rate", ""),
                    "bandwidth": float(data.get("bytesPerSecond", 0))
                }

            return {"rate": "", "bandwidth": 0.0}

        except Exception as e:
            logger.error(f"Error obteniendo bandwidth: {e}")
            return {"rate": "", "bandwidth": 0.0}
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de memoria de rclone.
        
        Returns:
            Diccionario con uso de memoria
        """
        try:
            response = self.session.post(
                f"{self.base_url}/core/memstats",
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            
            return {}
            
        except Exception as e:
            logger.error(f"Error obteniendo memstats: {e}")
            return {}


# Funciones de utilidad

def format_bytes(bytes_val: float) -> str:
    """
    Formatea bytes a formato legible.

    Args:
        bytes_val: Cantidad de bytes

    Returns:
        String formateado (ej: "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


def format_speed(bytes_per_sec: float) -> str:
    """
    Formatea velocidad a formato legible.
    
    Args:
        bytes_per_sec: Bytes por segundo
        
    Returns:
        String formateado (ej: "5.2 MB/s")
    """
    return f"{format_bytes(bytes_per_sec)}/s"
