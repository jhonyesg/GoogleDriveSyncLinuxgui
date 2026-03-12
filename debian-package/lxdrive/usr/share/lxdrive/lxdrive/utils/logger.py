import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
from datetime import datetime

from lxdrive.config import LOG_DIR, APP_NAME


class GUILogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.callbacks = []
    
    def emit(self, record):
        log_entry = self.format(record)
        for callback in self.callbacks:
            try:
                callback(log_entry, record.levelno)
            except Exception:
                pass
    
    def add_callback(self, callback):
        self.callbacks.append(callback)
    
    def remove_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)


_logger: Optional[logging.Logger] = None
_gui_handler: Optional[GUILogHandler] = None


def setup_logger(
    name: str = APP_NAME,
    log_level: str = "INFO",
    log_dir: Path = None
) -> logging.Logger:
    global _logger, _gui_handler
    
    if _logger is not None:
        return _logger
    
    _logger = logging.getLogger(name)
    _logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    log_path = log_dir or LOG_DIR
    log_path.mkdir(parents=True, exist_ok=True)
    
    log_file = log_path / f"{name.lower()}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    _logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    _logger.addHandler(console_handler)
    
    _gui_handler = GUILogHandler()
    _gui_handler.setLevel(logging.DEBUG)
    gui_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    _gui_handler.setFormatter(gui_formatter)
    _logger.addHandler(_gui_handler)
    
    return _logger


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger


def get_gui_handler() -> Optional[GUILogHandler]:
    return _gui_handler


def add_gui_log_callback(callback):
    handler = get_gui_handler()
    if handler:
        handler.add_callback(callback)


def remove_gui_log_callback(callback):
    handler = get_gui_handler()
    if handler:
        handler.remove_callback(callback)


_log_records: list = []
_max_records = 1000


def get_log_records() -> list:
    return _log_records.copy()


def clear_log_records():
    global _log_records
    _log_records = []


def add_log_record(record: str):
    global _log_records
    _log_records.append(record)
    if len(_log_records) > _max_records:
        _log_records = _log_records[-_max_records:]


def set_log_level(level: str):
    global _logger
    if _logger:
        _logger.setLevel(getattr(logging, level.upper(), logging.INFO))
