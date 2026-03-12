from pathlib import Path
import shutil

from lxdrive.config import APPLICATIONS_DIR, DATA_DIR


DESKTOP_ENTRY_TEMPLATE = """[Desktop Entry]
Version=1.0
Name=lX_Drive
Comment=Cloud synchronization with rclone
Exec={exec_path}
Icon={icon_path}
Terminal=false
Type=Application
Categories=Network;FileTransfer;GTK;
StartupNotify=true
"""


def create_desktop_entry(
    exec_path: str = None,
    icon_path: str = None,
    install: bool = True
) -> Path:
    if exec_path is None:
        bin_path = Path.home() / ".local" / "bin" / "lxdrive"
        exec_path = str(bin_path)
    
    if icon_path is None:
        icon_path = str(Path.home() / ".local" / "share" / "lxdrive" / "icons" / "lxdrive.png")
    
    content = DESKTOP_ENTRY_TEMPLATE.format(
        exec_path=exec_path,
        icon_path=icon_path
    )
    
    desktop_file = Path("lxdrive.desktop")
    
    if install:
        applications_dir = APPLICATIONS_DIR
        applications_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = applications_dir / "lxdrive.desktop"
    
    desktop_file.write_text(content)
    
    if install:
        desktop_file.chmod(0o755)
    
    return desktop_file


def create_desktop_shortcut(desktop_dir: Path = None) -> bool:
    if desktop_dir is None:
        desktop_dir = Path.home() / "Desktop"
    
    if not desktop_dir.exists():
        return False
    
    try:
        desktop_file = desktop_dir / "lxdrive.desktop"
        bin_path = Path.home() / ".local" / "bin" / "lxdrive"
        icon_path = DATA_DIR / "icons" / "lxdrive.png"
        
        content = DESKTOP_ENTRY_TEMPLATE.format(
            exec_path=str(bin_path),
            icon_path=str(icon_path)
        )
        
        desktop_file.write_text(content)
        desktop_file.chmod(0o755)
        return True
    except Exception:
        return False


def remove_desktop_entry() -> bool:
    desktop_file = APPLICATIONS_DIR / "lxdrive.desktop"
    
    if desktop_file.exists():
        try:
            desktop_file.unlink()
            return True
        except Exception:
            return False
    
    return True
