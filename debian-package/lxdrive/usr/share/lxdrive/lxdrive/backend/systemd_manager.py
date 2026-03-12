import subprocess
from pathlib import Path
from typing import Optional
import shutil
import re

from lxdrive.config import SYSTEMD_USER_DIR, DATA_DIR


class SystemdManager:
    SERVICE_MOUNT_TEMPLATE = """[Unit]
Description=lX_Drive Mount for {remote_name}
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart={rclone_path} mount {remote_name}: {mount_path} \
    --vfs-cache-mode full \
    --vfs-cache-max-age 24h \
    --vfs-cache-max-size 10G \
    --buffer-size 64M \
    --dir-cache-time 72h \
    --poll-interval 15s \
    --log-level INFO \
    --log-file {log_path}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""

    SERVICE_SYNC_TEMPLATE = """[Unit]
Description=lX_Drive Bisync for {task_id}
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart={rclone_path} bisync {local_path} {remote_name}:{remote_path} \
    --resync-period 3m \
    --track-renames \
    --drive-import-formats docx,xlsx,pptx,doc,xls,ppt,odt,ods,odp \
    --log-level INFO \
    --log-file {log_path}
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
"""

    def __init__(self):
        self.systemctl_path = shutil.which("systemctl")
        self.rclone_path = shutil.which("rclone")
        self.user_dir = SYSTEMD_USER_DIR
        self.user_dir.mkdir(parents=True, exist_ok=True)
    
    def is_available(self) -> bool:
        return self.systemctl_path is not None
    
    def _get_service_name(self, name: str, service_type: str) -> str:
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        return f"lxdrive-{service_type}@{safe_name}.service"
    
    def create_mount_service(
        self,
        remote_name: str,
        mount_path: Path
    ) -> tuple[bool, str]:
        if not self.is_available():
            return False, "systemctl not available"
        
        service_name = self._get_service_name(remote_name, "mount")
        log_path = DATA_DIR / "logs" / f"mount-{remote_name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        service_content = self.SERVICE_MOUNT_TEMPLATE.format(
            remote_name=remote_name,
            mount_path=str(mount_path),
            rclone_path=self.rclone_path or "/usr/bin/rclone",
            log_path=str(log_path)
        )
        
        service_file = self.user_dir / service_name
        service_file.write_text(service_content)
        
        return self._daemon_reload()
    
    def create_sync_service(
        self,
        task_id: str,
        remote_name: str,
        remote_path: str,
        local_path: Path
    ) -> tuple[bool, str]:
        if not self.is_available():
            return False, "systemctl not available"
        
        service_name = self._get_service_name(task_id, "sync")
        log_path = DATA_DIR / "logs" / f"sync-{task_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        service_content = self.SERVICE_SYNC_TEMPLATE.format(
            task_id=task_id,
            remote_name=remote_name,
            remote_path=remote_path,
            local_path=str(local_path),
            rclone_path=self.rclone_path or "/usr/bin/rclone",
            log_path=str(log_path)
        )
        
        service_file = self.user_dir / service_name
        service_file.write_text(service_content)
        
        return self._daemon_reload()
    
    def _daemon_reload(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                [self.systemctl_path, "--user", "daemon-reload"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, "Daemon reloaded"
            return False, result.stderr or "Failed to reload daemon"
        except Exception as e:
            return False, str(e)
    
    def enable_service(self, name: str, service_type: str) -> tuple[bool, str]:
        if not self.is_available():
            return False, "systemctl not available"
        
        service_name = self._get_service_name(name, service_type)
        
        try:
            result = subprocess.run(
                [self.systemctl_path, "--user", "enable", service_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, f"Service {service_name} enabled"
            return False, result.stderr or f"Failed to enable {service_name}"
        except Exception as e:
            return False, str(e)
    
    def disable_service(self, name: str, service_type: str) -> tuple[bool, str]:
        if not self.is_available():
            return False, "systemctl not available"
        
        service_name = self._get_service_name(name, service_type)
        
        try:
            result = subprocess.run(
                [self.systemctl_path, "--user", "disable", service_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, f"Service {service_name} disabled"
            return False, result.stderr or f"Failed to disable {service_name}"
        except Exception as e:
            return False, str(e)
    
    def start_service(self, name: str, service_type: str) -> tuple[bool, str]:
        if not self.is_available():
            return False, "systemctl not available"
        
        service_name = self._get_service_name(name, service_type)
        
        try:
            result = subprocess.run(
                [self.systemctl_path, "--user", "start", service_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, f"Service {service_name} started"
            return False, result.stderr or f"Failed to start {service_name}"
        except Exception as e:
            return False, str(e)
    
    def stop_service(self, name: str, service_type: str) -> tuple[bool, str]:
        if not self.is_available():
            return False, "systemctl not available"
        
        service_name = self._get_service_name(name, service_type)
        
        try:
            result = subprocess.run(
                [self.systemctl_path, "--user", "stop", service_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, f"Service {service_name} stopped"
            return False, result.stderr or f"Failed to stop {service_name}"
        except Exception as e:
            return False, str(e)
    
    def get_service_status(self, name: str, service_type: str) -> Optional[str]:
        if not self.is_available():
            return None
        
        service_name = self._get_service_name(name, service_type)
        
        try:
            result = subprocess.run(
                [self.systemctl_path, "--user", "is-active", service_name],
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except Exception:
            return None
    
    def remove_service(self, name: str, service_type: str) -> tuple[bool, str]:
        if not self.is_available():
            return False, "systemctl not available"
        
        service_name = self._get_service_name(name, service_type)
        service_file = self.user_dir / service_name
        
        self.stop_service(name, service_type)
        self.disable_service(name, service_type)
        
        if service_file.exists():
            service_file.unlink()
        
        self._daemon_reload()
        return True, f"Service {service_name} removed"
    
    def list_lxdrive_services(self) -> list[dict]:
        services = []
        
        for service_file in self.user_dir.glob("lxdrive-*.service"):
            name = service_file.stem
            service_type = "mount" if "mount" in name else "sync"
            status = self.get_service_status(
                name.split("@")[1].replace(".service", ""),
                service_type
            )
            services.append({
                "name": name,
                "file": str(service_file),
                "type": service_type,
                "status": status or "unknown"
            })
        
        return services
