from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from pathlib import Path
import json

from lxdrive.config import TaskType, TaskStatus, Theme, IconSize


@dataclass
class Remote:
    name: str
    provider: str
    root_folder: str = "/"
    is_configured: bool = True
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "provider": self.provider,
            "root_folder": self.root_folder,
            "is_configured": self.is_configured,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Remote":
        return cls(
            name=data["name"],
            provider=data["provider"],
            root_folder=data.get("root_folder", "/"),
            is_configured=data.get("is_configured", True),
        )


@dataclass
class SyncTask:
    id: str
    remote_name: str
    remote_path: str
    local_path: str
    task_type: TaskType
    name: str = ""
    enabled: bool = True
    autostart: bool = False
    last_sync: Optional[datetime] = None
    last_sync_result: str = ""
    status: TaskStatus = TaskStatus.IDLE
    filters: list = field(default_factory=list)
    sync_history: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "remote_name": self.remote_name,
            "remote_path": self.remote_path,
            "local_path": str(self.local_path),
            "task_type": self.task_type.value,
            "enabled": self.enabled,
            "autostart": self.autostart,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_sync_result": self.last_sync_result,
            "status": self.status.value,
            "filters": self.filters,
            "sync_history": self.sync_history[-10:] if self.sync_history else [],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SyncTask":
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            remote_name=data["remote_name"],
            remote_path=data["remote_path"],
            local_path=data["local_path"],
            task_type=TaskType(data["task_type"]),
            enabled=data.get("enabled", True),
            autostart=data.get("autostart", False),
            last_sync=datetime.fromisoformat(data["last_sync"]) if data.get("last_sync") else None,
            last_sync_result=data.get("last_sync_result", ""),
            status=TaskStatus(data.get("status", "idle")),
            filters=data.get("filters", []),
            sync_history=data.get("sync_history", []),
        )


@dataclass
class AppConfig:
    theme: Theme = Theme.SYSTEM
    autostart_app: bool = False
    log_level: str = "INFO"
    mount_base_path: str = ""
    window_width: int = 900
    window_height: int = 600
    icon_size: IconSize = IconSize.MEDIUM
    
    def __post_init__(self):
        if not self.mount_base_path:
            from lxdrive.config import DEFAULT_MOUNT_BASE
            self.mount_base_path = str(DEFAULT_MOUNT_BASE)
    
    def to_dict(self) -> dict:
        return {
            "theme": self.theme.value,
            "autostart_app": self.autostart_app,
            "log_level": self.log_level,
            "mount_base_path": self.mount_base_path,
            "window_width": self.window_width,
            "window_height": self.window_height,
            "icon_size": self.icon_size.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        return cls(
            theme=Theme(data.get("theme", "system")),
            autostart_app=data.get("autostart_app", False),
            log_level=data.get("log_level", "INFO"),
            mount_base_path=data.get("mount_base_path", ""),
            window_width=data.get("window_width", 900),
            window_height=data.get("window_height", 600),
            icon_size=IconSize(data.get("icon_size", "medium")),
        )
    
    def save(self, config_file: Path = None):
        from lxdrive.config import CONFIG_FILE
        file_path = config_file or CONFIG_FILE
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, config_file: Path = None) -> "AppConfig":
        from lxdrive.config import CONFIG_FILE
        file_path = config_file or CONFIG_FILE
        if file_path.exists():
            with open(file_path, "r") as f:
                data = json.load(f)
            return cls.from_dict(data)
        return cls()


class TaskManager:
    def __init__(self, tasks_file: Path = None):
        from lxdrive.config import TASKS_FILE
        self.tasks_file = tasks_file or TASKS_FILE
        self.tasks: list[SyncTask] = []
        self.load()
    
    def load(self):
        self.tasks = []
        if self.tasks_file.exists():
            with open(self.tasks_file, "r") as f:
                data = json.load(f)
            self.tasks = [SyncTask.from_dict(t) for t in data.get("tasks", [])]
    
    def save(self):
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.tasks_file, "w") as f:
            json.dump({"tasks": [t.to_dict() for t in self.tasks]}, f, indent=2)
    
    def add_task(self, task: SyncTask):
        self.tasks.append(task)
        self.save()
    
    def remove_task(self, task_id: str):
        self.tasks = [t for t in self.tasks if t.id != task_id]
        self.save()
    
    def get_task(self, task_id: str) -> Optional[SyncTask]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def update_task(self, task: SyncTask):
        for i, t in enumerate(self.tasks):
            if t.id == task.id:
                self.tasks[i] = task
                break
        self.save()
