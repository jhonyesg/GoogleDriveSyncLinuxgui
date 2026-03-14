from pathlib import Path
import shutil

from lxdrive.config import AUTOSTART_DIR, DATA_DIR


DESKTOP_ENTRY = """[Desktop Entry]
Version=1.0
Name=lX_Drive
Comment=Cloud synchronization with rclone
Exec={exec_path} --tray
Icon={icon_path}
Terminal=false
Type=Application
Categories=Network;FileTransfer;GTK;
StartupNotify=true
X-GNOME-Autostart-enabled=true
"""


def _find_executable() -> str:
    """Busca el ejecutable de lxdrive en el sistema."""
    # Primero intentar con shutil.which (busca en PATH)
    exec_path = shutil.which("lxdrive")
    if exec_path:
        return exec_path
    
    # Si no está en PATH, buscar en ubicaciones comunes
    common_paths = [
        "/usr/bin/lxdrive",
        "/usr/local/bin/lxdrive",
        str(Path.home() / ".local" / "bin" / "lxdrive"),
    ]
    
    for path in common_paths:
        if Path(path).exists():
            return path
    
    # Fallback por defecto (instalación desde .deb)
    return "/usr/bin/lxdrive"


def _find_icon() -> str:
    """Busca el icono de lxdrive en el sistema."""
    # Ubicaciones donde puede estar el icono (en orden de preferencia)
    icon_locations = [
        "/usr/share/icons/hicolor/128x128/apps/lxdrive.png",
        "/usr/share/pixmaps/lxdrive.png",
        str(DATA_DIR / "icons" / "lxdrive.png"),
        str(Path.home() / ".local" / "share" / "lxdrive" / "icons" / "lxdrive.png"),
    ]
    
    for icon_path in icon_locations:
        if Path(icon_path).exists():
            return icon_path
    
    # Fallback: usar el nombre del icono sin ruta (para temas de iconos)
    return "lxdrive"


def get_autostart_file() -> Path:
    return AUTOSTART_DIR / "lxdrive.desktop"


def enable_autostart() -> bool:
    autostart_file = get_autostart_file()
    autostart_file.parent.mkdir(parents=True, exist_ok=True)
    
    exec_path = _find_executable()
    icon_path = _find_icon()
    
    content = DESKTOP_ENTRY.format(
        exec_path=exec_path,
        icon_path=icon_path
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
