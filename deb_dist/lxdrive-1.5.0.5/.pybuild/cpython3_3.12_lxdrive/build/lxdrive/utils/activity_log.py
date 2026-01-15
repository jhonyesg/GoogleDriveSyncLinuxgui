#!/usr/bin/env python3
"""
ActivityLogManager - Sistema de registros de actividad por cuenta

Mantiene registros separados por cuenta con persistencia en disco.
Cada cuenta tiene su propio buffer de 500 registros que se persisten en JSON.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Callable
from collections import deque
from enum import Enum


class ActivityType(Enum):
    """Tipo de actividad"""
    SYNC = "sync"           # Actividad de sincronización de carpetas
    VFS = "vfs"             # Actividad de unidad virtual montada
    SYSTEM = "system"       # Eventos del sistema


class ActivityAction(Enum):
    """Acción realizada"""
    UPLOADING = "uploading"
    DOWNLOADING = "downloading"
    SYNCED = "synced"
    CONFLICT = "conflict"
    ERROR = "error"
    MOUNTED = "mounted"
    UNMOUNTED = "unmounted"
    DELETED = "deleted"
    MOVED = "moved"
    CREATED = "created"
    MODIFIED = "modified"
    STARTED = "started"
    STOPPED = "stopped"


@dataclass
class ActivityEntry:
    """Representa una entrada de actividad"""
    timestamp: str
    account_id: str
    activity_type: str  # sync, vfs, system
    action: str
    name: str
    path: str = ""
    progress: float = 0.0
    error_message: str = ""
    sync_pair_id: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ActivityEntry":
        return cls(**data)
    
    def get_icon(self) -> str:
        """Retorna el icono según la acción"""
        icons = {
            "uploading": "📤",
            "downloading": "📥",
            "synced": "✅",
            "conflict": "⚠️",
            "error": "❌",
            "mounted": "📦",
            "unmounted": "📴",
            "deleted": "🗑️",
            "moved": "🔄",
            "created": "➕",
            "modified": "📝",
            "started": "▶️",
            "stopped": "⏹️"
        }
        return icons.get(self.action, "📄")
    
    def get_action_text(self) -> str:
        """Retorna texto descriptivo de la acción"""
        texts = {
            "uploading": "Subiendo...",
            "downloading": "Descargando...",
            "synced": "Sincronizado",
            "conflict": "Conflicto",
            "error": "Error",
            "mounted": "Unidad conectada",
            "unmounted": "Unidad desconectada",
            "deleted": "Eliminado",
            "moved": "Renombrado/Movido",
            "created": "Creado",
            "modified": "Modificado",
            "started": "Iniciado",
            "stopped": "Detenido"
        }
        return texts.get(self.action, self.action)


class AccountActivityLog:
    """
    Gestor de actividad para una cuenta específica.
    Mantiene un buffer circular de 500 registros con persistencia.
    """
    
    MAX_ENTRIES = 500
    
    def __init__(self, account_id: str, storage_dir: Path):
        self.account_id = account_id
        self.storage_dir = storage_dir
        self._lock = threading.Lock()
        
        # Buffers separados para sync y vfs
        self._sync_buffer: deque = deque(maxlen=self.MAX_ENTRIES)
        self._vfs_buffer: deque = deque(maxlen=self.MAX_ENTRIES)
        
        # Callbacks para notificar cambios
        self._callbacks: List[Callable] = []
        
        # Cargar datos persistidos
        self._load()
    
    @property
    def _sync_file(self) -> Path:
        return self.storage_dir / f"activity_sync_{self.account_id}.json"
    
    @property
    def _vfs_file(self) -> Path:
        return self.storage_dir / f"activity_vfs_{self.account_id}.json"
    
    def _load(self):
        """Carga las actividades desde disco"""
        # Cargar sync
        if self._sync_file.exists():
            try:
                with open(self._sync_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for entry_data in data:
                        self._sync_buffer.append(ActivityEntry.from_dict(entry_data))
            except Exception:
                pass  # Si hay error, empezamos vacío
        
        # Cargar vfs
        if self._vfs_file.exists():
            try:
                with open(self._vfs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for entry_data in data:
                        self._vfs_buffer.append(ActivityEntry.from_dict(entry_data))
            except Exception:
                pass
    
    def _save(self):
        """Guarda las actividades a disco"""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with self._lock:
                # Guardar sync
                with open(self._sync_file, "w", encoding="utf-8") as f:
                    json.dump([e.to_dict() for e in self._sync_buffer], f, ensure_ascii=False)
                
                # Guardar vfs
                with open(self._vfs_file, "w", encoding="utf-8") as f:
                    json.dump([e.to_dict() for e in self._vfs_buffer], f, ensure_ascii=False)
        except Exception:
            pass  # Ignorar errores de escritura
    
    def add_activity(
        self,
        activity_type: ActivityType,
        action: ActivityAction,
        name: str,
        path: str = "",
        progress: float = 0.0,
        error_message: str = "",
        sync_pair_id: str = ""
    ):
        """Añade una entrada de actividad"""
        entry = ActivityEntry(
            timestamp=datetime.now().isoformat(),
            account_id=self.account_id,
            activity_type=activity_type.value,
            action=action.value,
            name=name,
            path=path,
            progress=progress,
            error_message=error_message,
            sync_pair_id=sync_pair_id
        )
        
        with self._lock:
            if activity_type == ActivityType.VFS:
                # Deduplicación: buscar si ya existe este path
                for existing in self._vfs_buffer:
                    if existing.path == path and existing.name == name:
                        # Actualizar en lugar de añadir nuevo
                        existing.timestamp = entry.timestamp
                        existing.action = entry.action
                        existing.progress = entry.progress
                        self._notify_callbacks()
                        return
                self._vfs_buffer.append(entry)
            else:
                # Para sync también deduplicamos
                for existing in self._sync_buffer:
                    if existing.path == path and existing.name == name and existing.sync_pair_id == sync_pair_id:
                        existing.timestamp = entry.timestamp
                        existing.action = entry.action
                        existing.progress = entry.progress
                        self._notify_callbacks()
                        return
                self._sync_buffer.append(entry)
        
        # Persistir cambios (async para no bloquear)
        threading.Thread(target=self._save, daemon=True).start()
        self._notify_callbacks()
    
    def get_sync_activities(self, limit: int = 100) -> List[ActivityEntry]:
        """Obtiene las actividades de sincronización más recientes"""
        with self._lock:
            entries = list(self._sync_buffer)
        return entries[::-1][:limit]  # Más recientes primero
    
    def get_vfs_activities(self, limit: int = 100) -> List[ActivityEntry]:
        """Obtiene las actividades de VFS más recientes"""
        with self._lock:
            entries = list(self._vfs_buffer)
        return entries[::-1][:limit]
    
    def get_all_activities(self, limit: int = 100) -> List[ActivityEntry]:
        """Obtiene todas las actividades ordenadas por tiempo"""
        with self._lock:
            all_entries = list(self._sync_buffer) + list(self._vfs_buffer)
        all_entries.sort(key=lambda x: x.timestamp, reverse=True)
        return all_entries[:limit]
    
    def clear(self, activity_type: Optional[ActivityType] = None):
        """Limpia las actividades"""
        with self._lock:
            if activity_type == ActivityType.SYNC or activity_type is None:
                self._sync_buffer.clear()
            if activity_type == ActivityType.VFS or activity_type is None:
                self._vfs_buffer.clear()
        self._save()
        self._notify_callbacks()
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas de la cuenta"""
        with self._lock:
            return {
                "sync_count": len(self._sync_buffer),
                "vfs_count": len(self._vfs_buffer),
                "total": len(self._sync_buffer) + len(self._vfs_buffer)
            }
    
    def register_callback(self, callback: Callable):
        """Registra un callback para notificar cambios"""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        """Elimina un callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self):
        """Notifica a los callbacks registrados"""
        for callback in self._callbacks:
            try:
                callback(self.account_id)
            except Exception:
                pass


class ActivityLogManager:
    """
    Gestor global de logs de actividad.
    Mantiene un ActivityLog por cada cuenta.
    Thread-safe para uso desde múltiples hilos.
    """
    
    _instance: Optional["ActivityLogManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, storage_dir: Optional[Path] = None):
        if self._initialized:
            return
        
        self.storage_dir = storage_dir or Path.home() / ".config" / "lxdrive" / "activity"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self._account_logs: Dict[str, AccountActivityLog] = {}
        self._global_callbacks: List[Callable] = []
        
        self._initialized = True
    
    def get_account_log(self, account_id: str) -> AccountActivityLog:
        """Obtiene o crea el log de actividad para una cuenta"""
        if account_id not in self._account_logs:
            self._account_logs[account_id] = AccountActivityLog(
                account_id=account_id,
                storage_dir=self.storage_dir
            )
            # Conectar callbacks globales
            self._account_logs[account_id].register_callback(self._on_account_activity)
        return self._account_logs[account_id]
    
    def add_activity(
        self,
        account_id: str,
        activity_type: ActivityType,
        action: ActivityAction,
        name: str,
        path: str = "",
        progress: float = 0.0,
        error_message: str = "",
        sync_pair_id: str = ""
    ):
        """Añade actividad para una cuenta específica"""
        log = self.get_account_log(account_id)
        log.add_activity(
            activity_type=activity_type,
            action=action,
            name=name,
            path=path,
            progress=progress,
            error_message=error_message,
            sync_pair_id=sync_pair_id
        )
    
    def get_sync_activities(self, account_id: str, limit: int = 100) -> List[ActivityEntry]:
        """Obtiene actividades de sync para una cuenta"""
        return self.get_account_log(account_id).get_sync_activities(limit)
    
    def get_vfs_activities(self, account_id: str, limit: int = 100) -> List[ActivityEntry]:
        """Obtiene actividades de VFS para una cuenta"""
        return self.get_account_log(account_id).get_vfs_activities(limit)
    
    def clear_account(self, account_id: str, activity_type: Optional[ActivityType] = None):
        """Limpia las actividades de una cuenta"""
        if account_id in self._account_logs:
            self._account_logs[account_id].clear(activity_type)
    
    def delete_account_logs(self, account_id: str):
        """Elimina todos los logs de una cuenta (para cuando se elimina la cuenta)"""
        if account_id in self._account_logs:
            del self._account_logs[account_id]
        
        # Eliminar archivos
        sync_file = self.storage_dir / f"activity_sync_{account_id}.json"
        vfs_file = self.storage_dir / f"activity_vfs_{account_id}.json"
        
        if sync_file.exists():
            sync_file.unlink()
        if vfs_file.exists():
            vfs_file.unlink()
    
    def register_global_callback(self, callback: Callable):
        """Registra un callback global para cualquier cambio"""
        self._global_callbacks.append(callback)
    
    def unregister_global_callback(self, callback: Callable):
        """Elimina un callback global"""
        if callback in self._global_callbacks:
            self._global_callbacks.remove(callback)
    
    def _on_account_activity(self, account_id: str):
        """Callback interno cuando hay actividad en cualquier cuenta"""
        for callback in self._global_callbacks:
            try:
                callback(account_id)
            except Exception:
                pass
    
    def get_all_stats(self) -> Dict[str, dict]:
        """Obtiene estadísticas de todas las cuentas"""
        stats = {}
        for account_id, log in self._account_logs.items():
            stats[account_id] = log.get_stats()
        return stats


# Instancia global
_activity_log_manager: Optional[ActivityLogManager] = None


def get_activity_log_manager() -> ActivityLogManager:
    """Obtiene la instancia global del ActivityLogManager"""
    global _activity_log_manager
    if _activity_log_manager is None:
        _activity_log_manager = ActivityLogManager()
    return _activity_log_manager


def setup_activity_log_manager(storage_dir: Optional[Path] = None) -> ActivityLogManager:
    """Inicializa el ActivityLogManager global"""
    global _activity_log_manager
    _activity_log_manager = ActivityLogManager(storage_dir=storage_dir)
    return _activity_log_manager
