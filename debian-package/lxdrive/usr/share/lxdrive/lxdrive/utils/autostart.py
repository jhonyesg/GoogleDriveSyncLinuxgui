from pathlib import Path

from lxdrive.config import AUTOSTART_DIR, DATA_DIR


DESKTOP_ENTRY = """[Desktop Entry]
Version=1.0
Name=lX_Drive
Comment=Cloud synchronization with rclone
Exec={bin_path}/lxdrive --tray
Icon={icon_path}
Terminal=false
Type=Application
Categories=Network;FileTransfer;GTK;
StartupNotify=true
X-GNOME-Autostart-enabled=true
"""


def get_autostart_file() -> Path:
    return AUTOSTART_DIR / "lxdrive.desktop"


def enable_autostart() -> bool:
    autostart_file = get_autostart_file()
    autostart_file.parent.mkdir(parents=True, exist_ok=True)
    
    import shutil
    bin_path = shutil.which("lxdrive")
    if bin_path is None:
        bin_path = "/usr/bin/lxdrive"
    
    icon_path = Path.home() / ".local" / "share" / "lxdrive" / "icons" / "lxdrive.png"
    
    content = DESKTOP_ENTRY.format(
        bin_path=str(Path(bin_path).parent),
        icon_path=str(icon_path)
    )
    
    try:
        autostart_file.write_text(content)
        return True
    except Exception:
        return False


def disable_autostart() -> bool:
    autostart_file = get_autostart_file()
    
    if autostart_file.exists():
        try:
            autostart_file.unlink()
            return True
        except Exception:
            return False
    
    return True


def is_autostart_enabled() -> bool:
    autostart_file = get_autostart_file()
    return autostart_file.exists()
