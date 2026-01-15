#!/usr/bin/env python3
"""
LogManager - Sistema de logging en memoria con autolimpieza

Mantiene los últimos 1000 registros de log en memoria y permite
acceder a ellos para mostrar en la UI o exportar.
"""

import threading
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from collections import deque


@dataclass
class LogEntry:
    """Representa una entrada de log"""
    timestamp: datetime
    level: str
    message: str
    module: str = ""
    function: str = ""
    line: int = 0
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "message": self.message,
            "module": self.module,
            "function": self.function,
            "line": self.line
        }
    
    def to_display(self) -> str:
        """Formato para mostrar en UI"""
        time_str = self.timestamp.strftime("%H:%M:%S")
        icons = {
            "DEBUG": "🔍",
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }
        icon = icons.get(self.level, "📝")
        return f"{time_str} | {icon} {self.level: <8} | {self.message}"


class LogManager:
    """
    Gestor de logs en memoria con las siguientes características:
    - Buffer circular de 1000 registros
    - Autolimpieza automática
    - Filtrado por nivel
    - Búsqueda por texto
    - Callbacks para actualizaciones en UI
    """
    
    MAX_ENTRIES = 1000
    
    def __init__(self, max_entries: int = MAX_ENTRIES):
        self._buffer: deque = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._callbacks: List[Callable] = []
        self._filter_level = "DEBUG"  # Nivel mínimo a guardar
        self._search_text = ""
        
        # Contadores
        self._counts = {
            "DEBUG": 0,
            "INFO": 0,
            "WARNING": 0,
            "ERROR": 0,
            "CRITICAL": 0
        }
    
    def add_entry(
        self, 
        level: str, 
        message: str, 
        module: str = "",
        function: str = "",
        line: int = 0
    ):
        """Añade una entrada al buffer de logs"""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            module=module,
            function=function,
            line=line
        )
        
        with self._lock:
            self._buffer.append(entry)
            self._counts[level] = self._counts.get(level, 0) + 1
        
        # Notificar callbacks
        self._notify_callbacks()
    
    def debug(self, message: str, module: str = "", function: str = "", line: int = 0):
        self.add_entry("DEBUG", message, module, function, line)
    
    def info(self, message: str, module: str = "", function: str = "", line: int = 0):
        self.add_entry("INFO", message, module, function, line)
    
    def warning(self, message: str, module: str = "", function: str = "", line: int = 0):
        self.add_entry("WARNING", message, module, function, line)
    
    def error(self, message: str, module: str = "", function: str = "", line: int = 0):
        self.add_entry("ERROR", message, module, function, line)
    
    def critical(self, message: str, module: str = "", function: str = "", line: int = 0):
        self.add_entry("CRITICAL", message, module, function, line)
    
    def get_entries(self, limit: int = 100, level_filter: Optional[str] = None) -> List[LogEntry]:
        """
        Obtiene las entradas del buffer.
        
        Args:
            limit: Máximo número de entradas a devolver
            level_filter: Filtrar por nivel (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
        Returns:
            Lista de entradas (más recientes primero)
        """
        with self._lock:
            entries = list(self._buffer)
        
        # Invertir para que los más recientes estén primero
        entries = entries[::-1]
        
        # Aplicar filtro de nivel
        if level_filter:
            levels_to_show = self._get_levels_up_to(level_filter)
            entries = [e for e in entries if e.level in levels_to_show]
        
        # Aplicar filtro de búsqueda
        if self._search_text:
            search_lower = self._search_text.lower()
            entries = [e for e in entries if search_lower in e.message.lower()]
        
        return entries[:limit]
    
    def get_recent(self, count: int = 100) -> List[LogEntry]:
        """Obtiene las entradas más recientes"""
        return self.get_entries(limit=count)
    
    def clear(self):
        """Limpia el buffer de logs"""
        with self._lock:
            self._buffer.clear()
            self._counts = {k: 0 for k in self._counts}
        self._notify_callbacks()
    
    def set_filter(self, level: str = "DEBUG", search_text: str = ""):
        """Configura los filtros"""
        self._filter_level = level
        self._search_text = search_text
        self._notify_callbacks()
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del log"""
        with self._lock:
            return {
                "total": len(self._buffer),
                "counts": dict(self._counts),
                "filter": self._filter_level,
                "search": self._search_text
            }
    
    def register_callback(self, callback: Callable):
        """Registra un callback para cuando hay nuevos logs"""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        """Elimina un callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def add_callback(self, callback: Callable):
        """Agrega un callback para notificar actualizaciones"""
        with self._lock:
            self._callbacks.append(callback)

    def _notify_callbacks(self):
        """Notifica a todos los callbacks registrados"""
        for callback in self._callbacks:
            try:
                callback()
            except Exception:
                pass  # Ignorar errores en callbacks
    
    def _get_levels_up_to(self, level: str) -> set:
        """Obtiene los niveles de log hasta el nivel dado"""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        valid_levels = set()
        for l in levels:
            valid_levels.add(l)
            if l == level:
                break
        return valid_levels
    
    def export_to_text(self, limit: int = 1000) -> str:
        """Exporta los logs a formato texto"""
        entries = self.get_entries(limit=limit)
        lines = []
        for entry in entries:
            lines.append(entry.to_display())
        return "\n".join(lines)
    
    def export_to_json(self, limit: int = 1000) -> str:
        """Exporta los logs a formato JSON"""
        import json
        entries = self.get_entries(limit=limit)
        return json.dumps([e.to_dict() for e in entries], indent=2)


# Instancia global
log_manager = LogManager()


def get_log_manager() -> LogManager:
    """Obtiene la instancia global del LogManager"""
    return log_manager


def setup_log_manager(max_entries: int = 1000) -> LogManager:
    """
    Configura e inicializa el LogManager global.
    
    Args:
        max_entries: Máximo número de registros a mantener
    
    Returns:
        Instancia del LogManager
    """
    global log_manager
    log_manager = LogManager(max_entries=max_entries)
    return log_manager
