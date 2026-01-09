#!/usr/bin/env python3
"""
Config - Gestión de configuración de la aplicación
"""

import json
import yaml
from pathlib import Path
from typing import Any, Optional, Dict
from dataclasses import dataclass, field, asdict
from loguru import logger


@dataclass
class AppConfig:
    """Configuración general de la aplicación"""
    
    # Comportamiento
    start_minimized: bool = False
    start_on_login: bool = False
    check_updates: bool = True
    
    # Sincronización
    sync_on_startup: bool = True
    default_sync_interval: int = 300  # 5 minutos
    
    # Montaje
    mount_base_dir: str = ""
    auto_mount_on_startup: bool = False
    
    # Notificaciones
    notify_sync_complete: bool = True
    notify_sync_error: bool = True
    notify_conflict: bool = True
    
    # Interfaz
    theme: str = "dark"
    language: str = "es"
    
    # Avanzado
    rclone_path: str = ""
    log_level: str = "INFO"
    max_concurrent_syncs: int = 2
    
    def __post_init__(self):
        if not self.mount_base_dir:
            self.mount_base_dir = str(Path.home() / "CloudDrives")


class Config:
    """
    Gestor de configuración de lX Drive.
    
    Maneja la persistencia de configuración en archivos YAML.
    """
    
    _instance: Optional["Config"] = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_dir: Optional[Path] = None):
        if self._initialized:
            return
        
        self.config_dir = config_dir or Path.home() / ".config" / "lxdrive"
        self.config_file = self.config_dir / "config.yaml"
        
        self._config = AppConfig()
        
        self._ensure_config_dir()
        self._load()
        
        self._initialized = True
    
    def _ensure_config_dir(self):
        """Crea el directorio de configuración si no existe"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def _load(self):
        """Carga la configuración desde el archivo"""
        if not self.config_file.exists():
            self._save()  # Crear archivo con valores por defecto
            return
        
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            # Actualizar config con valores cargados
            for key, value in data.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
            
            logger.debug("Configuración cargada")
            
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
    
    def _save(self):
        """Guarda la configuración al archivo"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    asdict(self._config), 
                    f, 
                    default_flow_style=False,
                    allow_unicode=True
                )
            logger.debug("Configuración guardada")
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración.
        
        Args:
            key: Nombre de la configuración
            default: Valor por defecto si no existe
            
        Returns:
            El valor de la configuración
        """
        return getattr(self._config, key, default)
    
    def set(self, key: str, value: Any):
        """
        Establece un valor de configuración.
        
        Args:
            key: Nombre de la configuración
            value: Nuevo valor
        """
        if hasattr(self._config, key):
            setattr(self._config, key, value)
            self._save()
        else:
            logger.warning(f"Configuración desconocida: {key}")
    
    def get_all(self) -> Dict[str, Any]:
        """Obtiene toda la configuración como diccionario"""
        return asdict(self._config)
    
    def reset(self):
        """Restablece la configuración a valores por defecto"""
        self._config = AppConfig()
        self._save()
    
    @property
    def app(self) -> AppConfig:
        """Acceso directo al objeto de configuración"""
        return self._config
