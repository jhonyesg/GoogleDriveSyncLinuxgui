#!/usr/bin/env python3
"""
ConflictResolver - Sistema de detección y resolución de conflictos

Detecta cuando un archivo ha sido modificado en ambos lados (local y remoto)
desde la última sincronización y proporciona estrategias para resolverlos.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from loguru import logger


class ConflictStrategy(Enum):
    """Estrategias para resolver conflictos"""
    ASK = "ask"  # Preguntar al usuario
    NEWER = "newer"  # Mantener el más reciente
    LARGER = "larger"  # Mantener el más grande
    LOCAL = "local"  # Siempre mantener local
    REMOTE = "remote"  # Siempre mantener remoto
    KEEP_BOTH = "keep_both"  # Mantener ambos (renombrar)


@dataclass
class ConflictFile:
    """Representa un archivo en conflicto"""
    path: str
    name: str
    local_size: int
    remote_size: int
    local_mtime: datetime
    remote_mtime: datetime
    local_hash: Optional[str] = None
    remote_hash: Optional[str] = None
    
    @property
    def size_diff(self) -> int:
        """Diferencia de tamaño en bytes"""
        return abs(self.local_size - self.remote_size)
    
    @property
    def time_diff(self) -> float:
        """Diferencia de tiempo en segundos"""
        return abs((self.local_mtime - self.remote_mtime).total_seconds())
    
    @property
    def is_newer_local(self) -> bool:
        """True si el archivo local es más reciente"""
        return self.local_mtime > self.remote_mtime
    
    @property
    def is_larger_local(self) -> bool:
        """True si el archivo local es más grande"""
        return self.local_size > self.remote_size


class ConflictResolver:
    """
    Gestor de conflictos de sincronización.
    
    Detecta y resuelve conflictos cuando un archivo ha sido modificado
    en ambos lados desde la última sincronización.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Inicializa el resolver de conflictos.
        
        Args:
            config_path: Ruta al archivo de configuración
        """
        self.config_path = config_path or Path.home() / ".config" / "lxdrive" / "conflicts.json"
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Carga la configuración de conflictos"""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando config de conflictos: {e}")
        
        # Configuración por defecto
        return {
            "default_strategy": ConflictStrategy.ASK.value,
            "auto_resolve_extensions": [".tmp", ".cache", ".lock"],
            "always_ask_extensions": [".docx", ".xlsx", ".pdf", ".txt"],
            "keep_both_suffix": "_conflict_{timestamp}",
            "conflict_history": []
        }
    
    def _save_config(self):
        """Guarda la configuración"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando config de conflictos: {e}")
    
    def detect_conflicts(
        self,
        local_path: str,
        remote_path: str,
        rclone_wrapper
    ) -> List[ConflictFile]:
        """
        Detecta conflictos entre local y remoto.
        
        Args:
            local_path: Ruta local
            remote_path: Ruta remota (formato remote:path)
            rclone_wrapper: Wrapper de rclone para listar archivos
            
        Returns:
            Lista de archivos en conflicto
        """
        conflicts = []
        
        try:
            # Usar rclone check para encontrar diferencias
            # Formato: rclone check local remote --combined output.txt
            
            # Por ahora, usamos una aproximación con lsjson
            # En producción, usar rclone check es más eficiente
            
            logger.info(f"Detectando conflictos entre {local_path} y {remote_path}")
            
            # Listar archivos locales
            local_files = self._list_local_files(Path(local_path))
            
            # Listar archivos remotos
            remote_name = remote_path.split(":")[0]
            remote_subpath = remote_path.split(":", 1)[1] if ":" in remote_path else ""
            remote_files = rclone_wrapper.list_files(remote_name, remote_subpath, recursive=True)
            
            # Crear mapas por nombre de archivo
            local_map = {f["path"]: f for f in local_files}
            remote_map = {f.path: f for f in remote_files}
            
            # Buscar archivos que existen en ambos lados
            common_files = set(local_map.keys()) & set(remote_map.keys())
            
            for file_path in common_files:
                local_file = local_map[file_path]
                remote_file = remote_map[file_path]
                
                # Verificar si hay diferencias
                size_diff = abs(local_file["size"] - remote_file.size)
                
                # Si hay diferencia de tamaño o tiempo, es potencial conflicto
                if size_diff > 0:
                    # Parsear tiempos
                    try:
                        local_mtime = datetime.fromtimestamp(local_file["mtime"])
                        remote_mtime = datetime.fromisoformat(remote_file.mod_time.replace('Z', '+00:00'))
                        
                        # Si ambos fueron modificados recientemente (últimas 24h), es conflicto
                        time_diff = abs((local_mtime - remote_mtime).total_seconds())
                        
                        if time_diff < 86400:  # 24 horas
                            conflicts.append(ConflictFile(
                                path=file_path,
                                name=Path(file_path).name,
                                local_size=local_file["size"],
                                remote_size=remote_file.size,
                                local_mtime=local_mtime,
                                remote_mtime=remote_mtime.replace(tzinfo=None)
                            ))
                    except Exception as e:
                        logger.debug(f"Error parseando tiempos para {file_path}: {e}")
            
            logger.info(f"Detectados {len(conflicts)} conflictos potenciales")
            return conflicts
            
        except Exception as e:
            logger.error(f"Error detectando conflictos: {e}")
            return []
    
    def _list_local_files(self, path: Path) -> List[Dict]:
        """Lista archivos locales con metadata"""
        files = []
        
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    stat = item.stat()
                    rel_path = str(item.relative_to(path))
                    files.append({
                        "path": rel_path,
                        "name": item.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime
                    })
        except Exception as e:
            logger.error(f"Error listando archivos locales: {e}")
        
        return files
    
    def get_strategy_for_file(self, conflict: ConflictFile) -> ConflictStrategy:
        """
        Determina la estrategia a usar para un archivo en conflicto.
        
        Args:
            conflict: Archivo en conflicto
            
        Returns:
            Estrategia a aplicar
        """
        ext = Path(conflict.name).suffix.lower()
        
        # Extensiones que se resuelven automáticamente
        if ext in self.config.get("auto_resolve_extensions", []):
            return ConflictStrategy.NEWER
        
        # Extensiones que siempre preguntan
        if ext in self.config.get("always_ask_extensions", []):
            return ConflictStrategy.ASK
        
        # Estrategia por defecto
        default = self.config.get("default_strategy", "ask")
        return ConflictStrategy(default)
    
    def resolve_conflict(
        self,
        conflict: ConflictFile,
        strategy: ConflictStrategy
    ) -> Tuple[str, str]:
        """
        Resuelve un conflicto según la estrategia.
        
        Args:
            conflict: Archivo en conflicto
            strategy: Estrategia a aplicar
            
        Returns:
            Tupla (acción, mensaje)
            Acciones: "keep_local", "keep_remote", "keep_both", "ask_user"
        """
        if strategy == ConflictStrategy.ASK:
            return ("ask_user", "Se requiere intervención del usuario")
        
        elif strategy == ConflictStrategy.NEWER:
            if conflict.is_newer_local:
                return ("keep_local", f"Local más reciente ({conflict.local_mtime})")
            else:
                return ("keep_remote", f"Remoto más reciente ({conflict.remote_mtime})")
        
        elif strategy == ConflictStrategy.LARGER:
            if conflict.is_larger_local:
                return ("keep_local", f"Local más grande ({conflict.local_size} bytes)")
            else:
                return ("keep_remote", f"Remoto más grande ({conflict.remote_size} bytes)")
        
        elif strategy == ConflictStrategy.LOCAL:
            return ("keep_local", "Preferencia: mantener local")
        
        elif strategy == ConflictStrategy.REMOTE:
            return ("keep_remote", "Preferencia: mantener remoto")
        
        elif strategy == ConflictStrategy.KEEP_BOTH:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = self.config.get("keep_both_suffix", "_conflict_{timestamp}")
            suffix = suffix.replace("{timestamp}", timestamp)
            return ("keep_both", f"Mantener ambos con sufijo: {suffix}")
        
        return ("ask_user", "Estrategia no reconocida")
    
    def set_default_strategy(self, strategy: ConflictStrategy):
        """Establece la estrategia por defecto"""
        self.config["default_strategy"] = strategy.value
        self._save_config()
        logger.info(f"Estrategia por defecto cambiada a: {strategy.value}")
    
    def add_auto_resolve_extension(self, extension: str):
        """Añade una extensión para resolver automáticamente"""
        if extension not in self.config["auto_resolve_extensions"]:
            self.config["auto_resolve_extensions"].append(extension)
            self._save_config()
    
    def add_always_ask_extension(self, extension: str):
        """Añade una extensión que siempre pregunta"""
        if extension not in self.config["always_ask_extensions"]:
            self.config["always_ask_extensions"].append(extension)
            self._save_config()
    
    def log_resolution(self, conflict: ConflictFile, action: str, strategy: str):
        """Registra una resolución de conflicto en el historial"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "file": conflict.path,
            "action": action,
            "strategy": strategy,
            "local_size": conflict.local_size,
            "remote_size": conflict.remote_size
        }
        
        history = self.config.get("conflict_history", [])
        history.append(entry)
        
        # Mantener solo últimos 100 registros
        self.config["conflict_history"] = history[-100:]
        self._save_config()
    
    def get_conflict_stats(self) -> Dict:
        """Obtiene estadísticas de conflictos resueltos"""
        history = self.config.get("conflict_history", [])
        
        if not history:
            return {
                "total": 0,
                "by_action": {},
                "by_strategy": {}
            }
        
        stats = {
            "total": len(history),
            "by_action": {},
            "by_strategy": {}
        }
        
        for entry in history:
            action = entry.get("action", "unknown")
            strategy = entry.get("strategy", "unknown")
            
            stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
            stats["by_strategy"][strategy] = stats["by_strategy"].get(strategy, 0) + 1
        
        return stats
