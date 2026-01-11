#!/usr/bin/env python3
"""
AccountManager - Gestión de cuentas de cloud storage

Este módulo maneja la persistencia y gestión de las cuentas
configuradas en lX Drive.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from loguru import logger


class SyncDirection(Enum):
    """Dirección de sincronización"""
    BIDIRECTIONAL = "bidirectional"  # Ambas direcciones
    UPLOAD_ONLY = "upload"           # Solo subir a la nube
    DOWNLOAD_ONLY = "download"       # Solo descargar de la nube


class SyncStatus(Enum):
    """Estado de sincronización de una cuenta"""
    IDLE = "idle"               # Sin actividad
    SYNCING = "syncing"         # Sincronizando
    RESYNCING = "resyncing"     # Resincronización inicial (lento)
    PAUSED = "paused"           # Pausado
    ERROR = "error"             # Error
    OFFLINE = "offline"         # Sin conexión



@dataclass
class SyncPair:
    """Representa un par de carpetas sincronizadas (Local <-> Remoto)"""
    id: str
    local_path: str
    remote_path: str = ""
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    enabled: bool = True
    last_sync: Optional[str] = None
    status: SyncStatus = SyncStatus.IDLE

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["direction"] = self.direction.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncPair":
        if "direction" in data and isinstance(data["direction"], str):
            data["direction"] = SyncDirection(data["direction"])
        if "status" in data and isinstance(data["status"], str):
            data["status"] = SyncStatus(data["status"])
        return cls(**data)


@dataclass
class Account:
    """
    Representa una conexión a cloud storage configuroda con múltiples carpetas.
    """
    id: str                              # ID único de la cuenta
    name: str                            # Nombre descriptivo (ej: "Google Drive Principal")
    remote_name: str                     # Nombre del remote en rclone
    remote_type: str                     # Tipo de servicio (drive, dropbox, etc)
    
    # Sincronización de carpetas (Múltiples)
    sync_pairs: List[SyncPair] = field(default_factory=list)
    sync_interval: int = 300             # Global para la cuenta
    
    # Montura Virtual (VFS)
    mount_enabled: bool = False          # Si montar como unidad
    mount_point: Optional[str] = None    # Punto de montaje
    
    created_at: str = ""                 # Fecha de creación
    status: SyncStatus = SyncStatus.IDLE
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        
        if isinstance(self.status, str):
            self.status = SyncStatus(self.status)
            
        # Convertir diccionarios a objetos SyncPair si vienen de JSON
        if self.sync_pairs and isinstance(self.sync_pairs[0], dict):
            converted_pairs = []
            for p in self.sync_pairs:
                if isinstance(p, dict):
                    converted_pairs.append(SyncPair.from_dict(p))
                else:
                    converted_pairs.append(p)
            self.sync_pairs = converted_pairs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la cuenta a diccionario para serialización"""
        data = asdict(self)
        data["sync_pairs"] = [p.to_dict() for p in self.sync_pairs]
        data["status"] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Account":
        """Crea una cuenta desde un diccionario con soporte para migración"""
        # Migración de formato antiguo a nuevo
        if "local_path" in data and "sync_pairs" not in data:
            logger.info(f"Migrando cuenta {data.get('name')} al nuevo formato multi-carpeta")
            pair = SyncPair(
                id="main",
                local_path=data.pop("local_path"),
                remote_path=data.pop("remote_path", ""),
                direction=SyncDirection(data.pop("sync_direction", "bidirectional")),
                enabled=data.pop("sync_enabled", True),
                last_sync=data.pop("last_sync", None)
            )
            # Limpiar otros campos antiguos
            data.pop("sync_interval", None) # El intervalo ahora es por cuenta
            data.pop("exclude_patterns", None)
            
            data["sync_pairs"] = [pair]
            
        return cls(**data)

    # Compatibilidad para código que aún usa local_path/remote_path
    @property
    def local_path(self):
        return self.sync_pairs[0].local_path if self.sync_pairs else ""
    @property
    def remote_path(self):
        return self.sync_pairs[0].remote_path if self.sync_pairs else ""
    @property
    def sync_direction(self):
        return self.sync_pairs[0].direction if self.sync_pairs else SyncDirection.BIDIRECTIONAL
    
    @sync_direction.setter
    def sync_direction(self, value):
        if isinstance(value, str): value = SyncDirection(value)
        for p in self.sync_pairs:
            p.direction = value

    @property
    def sync_enabled(self):
        return any(p.enabled for p in self.sync_pairs) if self.sync_pairs else True
    
    @sync_enabled.setter
    def sync_enabled(self, value):
        for p in self.sync_pairs:
            p.enabled = value

    @property
    def last_sync(self):
        return self.sync_pairs[0].last_sync if self.sync_pairs else None
    
    @last_sync.setter
    def last_sync(self, value):
        if self.sync_pairs:
            self.sync_pairs[0].last_sync = value
    
    def get_display_name(self) -> str:
        """Nombre para mostrar en la UI"""
        return f"{self.name} ({self.remote_type})"
    
    def get_status_icon(self) -> str:
        """Icono de estado para la UI"""
        icons = {
            SyncStatus.IDLE: "✓",
            SyncStatus.SYNCING: "⟳",
            SyncStatus.PAUSED: "⏸",
            SyncStatus.ERROR: "⚠",
            SyncStatus.OFFLINE: "○"
        }
        return icons.get(self.status, "?")


class AccountManager:
    """
    Gestiona las cuentas configuradas en lX Drive.
    
    Proporciona:
    - CRUD de cuentas
    - Persistencia en archivo JSON
    - Validación de configuración
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Inicializa el gestor de cuentas.
        
        Args:
            config_dir: Directorio de configuración. Si no se especifica,
                       usa ~/.config/lxdrive/
        """
        self.config_dir = config_dir or Path.home() / ".config" / "lxdrive"
        self.accounts_file = self.config_dir / "accounts.json"
        self._accounts: Dict[str, Account] = {}
        
        self._ensure_config_dir()
        self._load_accounts()
    
    def _ensure_config_dir(self):
        """Crea el directorio de configuración si no existe"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directorio de config: {self.config_dir}")
    
    def _load_accounts(self):
        """Carga las cuentas desde el archivo JSON"""
        if not self.accounts_file.exists():
            logger.info("No existe archivo de cuentas, iniciando vacío")
            return
        
        try:
            with open(self.accounts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for account_data in data.get("accounts", []):
                account = Account.from_dict(account_data)
                self._accounts[account.id] = account
            
            logger.info(f"Cargadas {len(self._accounts)} cuentas")
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error cargando cuentas: {e}")
    
    def _save_accounts(self):
        """Guarda las cuentas al archivo JSON"""
        try:
            data = {
                "version": "1.0",
                "accounts": [acc.to_dict() for acc in self._accounts.values()]
            }
            
            with open(self.accounts_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug("Cuentas guardadas correctamente")
            
        except IOError as e:
            logger.error(f"Error guardando cuentas: {e}")
    
    def _generate_id(self) -> str:
        """Genera un ID único para una cuenta"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def get_all(self) -> List[Account]:
        """
        Obtiene todas las cuentas configuradas.
        
        Returns:
            Lista de cuentas
        """
        return list(self._accounts.values())
    
    def get_by_id(self, account_id: str) -> Optional[Account]:
        """
        Obtiene una cuenta por su ID.
        
        Args:
            account_id: ID de la cuenta
            
        Returns:
            Account o None si no existe
        """
        return self._accounts.get(account_id)
    
    def get_by_remote_name(self, remote_name: str) -> Optional[Account]:
        """
        Obtiene una cuenta por su nombre de remote en rclone.
        
        Args:
            remote_name: Nombre del remote
            
        Returns:
            Account o None si no existe
        """
        for account in self._accounts.values():
            if account.remote_name == remote_name:
                return account
        return None
    
    def add(self, account: Account) -> bool:
        """
        Añade una nueva cuenta.
        
        Args:
            account: Cuenta a añadir
            
        Returns:
            True si se añadió correctamente
        """
        if not account.id:
            account.id = self._generate_id()
        
        if account.id in self._accounts:
            logger.warning(f"La cuenta {account.id} ya existe")
            return False
        
        # Validar que la carpeta local existe o crearla
        local_path = Path(account.local_path)
        if not local_path.exists():
            try:
                local_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Creada carpeta: {local_path}")
            except OSError as e:
                logger.error(f"No se pudo crear carpeta: {e}")
                return False
        
        self._accounts[account.id] = account
        self._save_accounts()
        
        logger.info(f"Cuenta añadida: {account.name} ({account.id})")
        return True
    
    def update(self, account: Account) -> bool:
        """
        Actualiza una cuenta existente.
        
        Args:
            account: Cuenta con datos actualizados
            
        Returns:
            True si se actualizó correctamente
        """
        if account.id not in self._accounts:
            logger.warning(f"La cuenta {account.id} no existe")
            return False
        
        self._accounts[account.id] = account
        self._save_accounts()
        
        logger.info(f"Cuenta actualizada: {account.name}")
        return True
    
    def delete(self, account_id: str) -> bool:
        """
        Elimina una cuenta.
        
        Args:
            account_id: ID de la cuenta a eliminar
            
        Returns:
            True si se eliminó correctamente
        """
        if account_id not in self._accounts:
            logger.warning(f"La cuenta {account_id} no existe")
            return False
        
        account = self._accounts.pop(account_id)
        self._save_accounts()
        
        logger.info(f"Cuenta eliminada: {account.name}")
        return True
    
    def set_status(self, account_id: str, status: SyncStatus, error: Optional[str] = None):
        """
        Actualiza el estado de una cuenta.
        
        Args:
            account_id: ID de la cuenta
            status: Nuevo estado
            error: Mensaje de error (opcional)
        """
        if account_id in self._accounts:
            self._accounts[account_id].status = status
            self._accounts[account_id].error_message = error
            
            if status == SyncStatus.IDLE and error is None:
                self._accounts[account_id].last_sync = datetime.now().isoformat()
            
            self._save_accounts()
    
    def get_enabled_accounts(self) -> List[Account]:
        """
        Obtiene las cuentas con sincronización habilitada.
        
        Returns:
            Lista de cuentas activas
        """
        return [acc for acc in self._accounts.values() if acc.sync_enabled]
    
    def get_mount_accounts(self) -> List[Account]:
        """
        Obtiene las cuentas configuradas para montaje.
        
        Returns:
            Lista de cuentas con montaje habilitado
        """
        return [acc for acc in self._accounts.values() if acc.mount_enabled]
    
    def validate_local_paths(self) -> List[str]:
        """
        Valida que las carpetas locales existan.
        
        Returns:
            Lista de errores encontrados
        """
        errors = []
        for account in self._accounts.values():
            if not Path(account.local_path).exists():
                errors.append(f"Carpeta no existe: {account.local_path} ({account.name})")
        return errors
