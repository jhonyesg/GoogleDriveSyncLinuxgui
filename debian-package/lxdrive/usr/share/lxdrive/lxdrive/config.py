import os
from pathlib import Path
from enum import Enum

APP_NAME = "lX_Drive"
APP_ID = "com.lxdrive.app"
VERSION = "1.0.0"
AUTHOR = "lX_Drive Team"

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "lxdrive"
DATA_DIR = HOME / ".local" / "share" / "lxdrive"
LOG_DIR = CONFIG_DIR / "logs"
CACHE_DIR = HOME / ".cache" / "lxdrive"

CONFIG_FILE = CONFIG_DIR / "config.json"
TASKS_FILE = CONFIG_DIR / "tasks.json"

DEFAULT_MOUNT_BASE = HOME / "Cloud"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_THEME = "system"

SYSTEMD_USER_DIR = HOME / ".config" / "systemd" / "user"
AUTOSTART_DIR = HOME / ".config" / "autostart"
APPLICATIONS_DIR = HOME / ".local" / "share" / "applications"
LOCAL_BIN_DIR = HOME / ".local" / "bin"

RCLONE_CONFIG_FILE = HOME / ".config" / "rclone" / "rclone.conf"


class TaskType(Enum):
    MOUNT = "mount"
    BISYNC = "bisync"


class TaskStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    SYNCING = "syncing"


class Theme(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class IconSize(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


SUPPORTED_PROVIDERS = {
    "gdrive": {
        "name": "Google Drive",
        "rclone_type": "drive",
        "icon": "google-drive",
    },
    "onedrive": {
        "name": "OneDrive",
        "rclone_type": "onedrive",
        "icon": "onedrive",
    },
    "dropbox": {
        "name": "Dropbox",
        "rclone_type": "dropbox",
        "icon": "dropbox",
    },
}


def ensure_directories():
    for directory in [CONFIG_DIR, DATA_DIR, LOG_DIR, CACHE_DIR, SYSTEMD_USER_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
