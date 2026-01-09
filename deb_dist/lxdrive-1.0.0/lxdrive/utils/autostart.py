#!/usr/bin/env python3
"""
Utilidades para gestión del inicio automático con el sistema (XDG Autostart)
"""

import os
import sys
from pathlib import Path
from loguru import logger

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
DESKTOP_FILE = AUTOSTART_DIR / "lxdrive.desktop"

def is_autostart_enabled() -> bool:
    """Verifica si el inicio automático está habilitado"""
    return DESKTOP_FILE.exists()

def set_autostart(enable: bool):
    """
    Habilita o deshabilita el inicio automático.
    
    Args:
        enable: True para habilitar, False para deshabilitar
    """
    if enable:
        _create_desktop_file()
    else:
        _remove_desktop_file()

def _create_desktop_file():
    """Crea el archivo .desktop en autostart"""
    # Obtener ruta al ejecutable actual
    # Si corre como script python: python3 -m lxdrive
    # Si corre como ejecutable compilado: sys.argv[0]
    
    # Asumimos ejecución via python módulo por ahora en desarrollo
    # En producción dist, sys.executable apuntaría al binario
    
    exec_cmd = f"{sys.executable} -m lxdrive"
    
    content = f"""[Desktop Entry]
Type=Application
Name=lX Drive
Comment=Cliente de Google Drive para Linux
Exec={exec_cmd}
Icon=drive-multimedia
Terminal=false
Categories=Network;FileTools;
X-GNOME-Autostart-enabled=true
StartupNotify=false
"""
    
    try:
        AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        with open(DESKTOP_FILE, "w") as f:
            f.write(content)
        
        # Dar permisos de ejecución
        os.chmod(DESKTOP_FILE, 0o755)
        logger.info(f"Autostart habilitado: {DESKTOP_FILE}")
        
    except Exception as e:
        logger.error(f"Error creando autostart: {e}")

def _remove_desktop_file():
    """Elimina el archivo .desktop"""
    try:
        if DESKTOP_FILE.exists():
            DESKTOP_FILE.unlink()
            logger.info("Autostart deshabilitado")
    except Exception as e:
        logger.error(f"Error eliminando autostart: {e}")
