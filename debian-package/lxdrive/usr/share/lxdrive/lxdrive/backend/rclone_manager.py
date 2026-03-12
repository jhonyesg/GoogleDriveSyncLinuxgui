import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from lxdrive.config import RCLONE_CONFIG_FILE, SUPPORTED_PROVIDERS


@dataclass
class RemoteInfo:
    name: str
    provider: str
    type: str
    is_configured: bool = True


@dataclass  
class QuotaInfo:
    used: int
    total: int
    available: int
    
    @property
    def used_human(self) -> str:
        return self._human_size(self.used)
    
    @property
    def total_human(self) -> str:
        return self._human_size(self.total)
    
    @property
    def available_human(self) -> str:
        return self._human_size(self.available)
    
    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.used / self.total) * 100
    
    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


class RcloneManager:
    def __init__(self):
        self.rclone_path = self._find_rclone()
    
    def _find_rclone(self) -> Optional[str]:
        return shutil.which("rclone")
    
    def is_available(self) -> bool:
        return self.rclone_path is not None
    
    def get_version(self) -> Optional[str]:
        if not self.is_available():
            return None
        try:
            result = subprocess.run(
                [self.rclone_path, "version"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.split("\n")[0]
        except subprocess.CalledProcessError:
            return None
    
    def list_remotes(self) -> list[str]:
        if not self.is_available():
            return []
        try:
            result = subprocess.run(
                [self.rclone_path, "listremotes"],
                capture_output=True,
                text=True,
                check=True
            )
            remotes = []
            for line in result.stdout.strip().split("\n"):
                if line.endswith(":"):
                    remotes.append(line[:-1])
            return remotes
        except subprocess.CalledProcessError:
            return []
    
    def get_remote_info(self, name: str) -> Optional[RemoteInfo]:
        if not self.is_available():
            return None
        
        config = self._read_config()
        if name not in config:
            return None
        
        remote_config = config[name]
        provider = remote_config.get("type", "unknown")
        
        provider_name = "Unknown"
        for key, info in SUPPORTED_PROVIDERS.items():
            if info["rclone_type"] == provider:
                provider_name = info["name"]
                break
        
        return RemoteInfo(
            name=name,
            provider=provider_name,
            type=provider,
            is_configured=True
        )
    
    def _read_config(self) -> dict:
        if not RCLONE_CONFIG_FILE.exists():
            return {}
        
        config = {}
        current_section = None
        
        with open(RCLONE_CONFIG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                    config[current_section] = {}
                elif "=" in line and current_section:
                    key, value = line.split("=", 1)
                    config[current_section][key.strip()] = value.strip()
        
        return config
    
    def check_connection(self, name: str) -> tuple[bool, str]:
        if not self.is_available():
            return False, "rclone not installed"
        
        try:
            result = subprocess.run(
                [self.rclone_path, "lsd", f"{name}:", "--max-depth", "1"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return True, "Connection successful"
            return False, result.stderr.strip() or "Connection failed"
        except subprocess.TimeoutExpired:
            return False, "Connection timeout"
        except Exception as e:
            return False, str(e)
    
    def get_quota(self, name: str) -> Optional[QuotaInfo]:
        if not self.is_available():
            return None
        
        try:
            result = subprocess.run(
                [self.rclone_path, "about", f"{name}:", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return None
            
            data = json.loads(result.stdout)
            return QuotaInfo(
                used=data.get("used", 0),
                total=data.get("total", 0),
                available=data.get("free", 0)
            )
        except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired):
            return None
    
    def create_remote_interactive(self, name: str, provider: str) -> tuple[bool, str]:
        if not self.is_available():
            return False, "rclone not installed. Please install rclone first."
        
        provider_info = SUPPORTED_PROVIDERS.get(provider)
        if not provider_info:
            return False, f"Unknown provider: {provider}"
        
        rclone_type = provider_info["rclone_type"]
        
        try:
            subprocess.run(
                [self.rclone_path, "config", "create", name, rclone_type],
                check=True
            )
            return True, f"Remote '{name}' configured successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to configure remote: {e}"
    
    def delete_remote(self, name: str) -> tuple[bool, str]:
        if not self.is_available():
            return False, "rclone not installed"
        
        try:
            result = subprocess.run(
                [self.rclone_path, "config", "delete", name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, f"Remote '{name}' deleted"
            return False, result.stderr or "Failed to delete remote"
        except subprocess.CalledProcessError as e:
            return False, str(e)
    
    def list_remote_files(self, name: str, path: str = "") -> list[dict]:
        if not self.is_available():
            return []
        
        remote_path = f"{name}:{path}" if path else f"{name}:"
        
        try:
            result = subprocess.run(
                [self.rclone_path, "lsjson", remote_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                return []
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired):
            return []
