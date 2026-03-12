from .logger import setup_logger, get_logger
from .autostart import enable_autostart, disable_autostart, is_autostart_enabled
from .desktop_entry import create_desktop_entry

__all__ = [
    "setup_logger",
    "get_logger",
    "enable_autostart",
    "disable_autostart",
    "is_autostart_enabled",
    "create_desktop_entry",
]
