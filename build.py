#!/usr/bin/env python3
"""
Build script for lX Drive v2.0

Creates a self-contained .deb package with:
- Python dependencies bundled
- rclone binary embedded
- All application files

Usage:
    python3 build.py                    # Build .deb
    python3 build.py --appimage         # Build AppImage instead
    python3 build.py --install          # Install after build
    python3 build.py --clean            # Clean build artifacts
"""

import os
import sys
import shutil
import subprocess
import argparse
import zipfile
import urllib.request
from pathlib import Path
from datetime import datetime

# Configuration
APP_NAME = "lxdrive"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Cliente de sincronización avanzado para Google Drive en Linux"
MAINTAINER = "J. Suarez"
HOMEPAGE = "https://github.com/jhonyesg/GoogleDriveSyncLinuxgui"

# Rclone configuration
RCLONE_VERSION = "v1.65.0"
RCLONE_URL = f"https://github.com/rclone/rclone/releases/download/{RCLONE_VERSION}/rclone-{RCLONE_VERSION}-linux-amd64.zip"
RCLONE_SHA256_URL = f"https://github.com/rclone/rclone/releases/download/{RCLONE_VERSION}/rclone-{RCLONE_VERSION}-linux-amd64.zip.sha256"

# Build paths
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_DIR = SCRIPT_DIR
BUILD_DIR = REPO_DIR / "build"
DEB_DIR = BUILD_DIR / "lxdrive_2.0.0_amd64"
STAGING_DIR = BUILD_DIR / "staging"

# Python paths
PYTHON_VERSION = f"python3.{sys.version_info.minor}"
SITE_PACKAGES = f"usr/lib/{PYTHON_VERSION}/dist-packages"
BIN_DIR = "usr/bin"


class Colors:
    """ANSI color codes"""
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    END = "\033[0m"
    BOLD = "\033[1m"


def log(msg, color=Colors.GREEN):
    """Print colored log message"""
    print(f"{color}[lX Drive Build]{Colors.END} {msg}")


def run_command(cmd, cwd=None, check=True, capture=False):
    """Run a shell command"""
    log(f"Running: {cmd}")
    result = subprocess.run(
        cmd, shell=True, cwd=cwd, check=check, 
        capture_output=capture, text=True
    )
    if capture:
        return result.stdout, result.stderr
    return None


def clean():
    """Clean build artifacts"""
    log("Cleaning build artifacts...", Colors.YELLOW)
    
    dirs_to_remove = [
        BUILD_DIR,
        REPO_DIR / "deb_dist",
        REPO_DIR / "dist",
        REPO_DIR / f"{APP_NAME}.egg-info",
    ]
    
    for d in dirs_to_remove:
        if d.exists():
            shutil.rmtree(d)
            log(f"  Removed: {d}")
    
    # Clean pycache
    for pycache in REPO_DIR.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    
    log("Clean complete!", Colors.GREEN)


def download_rclone():
    """Download and extract rclone binary"""
    log(f"Downloading rclone {RCLONE_VERSION}...", Colors.BLUE)
    
    zip_path = BUILD_DIR / "rclone.zip"
    extract_dir = BUILD_DIR / "rclone-extract"
    
    # Download
    if not zip_path.exists():
        log(f"  Downloading from {RCLONE_URL}...")
        urllib.request.urlretrieve(RCLONE_URL, zip_path)
        log(f"  Downloaded: {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        log("  Using cached download")
    
    # Extract
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    
    log("  Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_dir)
    
    rclone_binary = extract_dir / "rclone"
    if not rclone_binary.exists():
        raise FileNotFoundError(f"rclone binary not found in {extract_dir}")
    
    log(f"  rclone binary ready: {rclone_binary}", Colors.GREEN)
    return rclone_binary


def prepare_deb_structure():
    """Prepare Debian package structure"""
    log("Preparing DEB structure...", Colors.BLUE)
    
    # Clear and create directories
    if DEB_DIR.exists():
        shutil.rmtree(DEB_DIR)
    DEB_DIR.mkdir(parents=True)
    
    dirs = [
        DEB_DIR / SITE_PACKAGES / APP_NAME,
        DEB_DIR / SITE_PACKAGES / APP_NAME / "core",
        DEB_DIR / SITE_PACKAGES / APP_NAME / "gui",
        DEB_DIR / SITE_PACKAGES / APP_NAME / "utils",
        DEB_DIR / SITE_PACKAGES / APP_NAME / "img",
        DEB_DIR / BIN_DIR,
        DEB_DIR / "usr/share/applications",
        DEB_DIR / "usr/share/icons",
        DEB_DIR / "usr/lib" / APP_NAME / "rclone",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    log("  Directory structure created")
    return DEB_DIR


def copy_python_files():
    """Copy Python application files"""
    log("Copying Python files...", Colors.BLUE)
    
    # Core files
    core_files = [
        "__init__.py",
        "app.py",
        "core/__init__.py",
        "core/account_manager.py",
        "core/rclone_wrapper.py",
        "core/rclone_daemon.py",
        "core/rclone_rc.py",
        "core/mount_manager.py",
        "core/filter_manager.py",
        "core/conflict_resolver.py",
        # v2.0 files
        "core/metadata_store.py",
        "core/drive_api_client.py",
        "core/sync_engine.py",
    ]
    
    for f in core_files:
        src = REPO_DIR / APP_NAME / f
        dst = DEB_DIR / SITE_PACKAGES / APP_NAME / f
        if src.exists():
            shutil.copy2(src, dst)
            log(f"  {f}")
    
    # GUI files
    gui_files = [
        "gui/__init__.py",
        "gui/main_window.py",
        "gui/tray_icon.py",
        "gui/activity_panel.py",
        "gui/log_viewer.py",
        "gui/conflict_dialog.py",
    ]
    
    for f in gui_files:
        src = REPO_DIR / APP_NAME / f
        dst = DEB_DIR / SITE_PACKAGES / APP_NAME / f
        if src.exists():
            shutil.copy2(src, dst)
            log(f"  {f}")
    
    # Utils files
    utils_files = [
        "utils/__init__.py",
        "utils/config.py",
        "utils/logger.py",
        "utils/autostart.py",
        "utils/activity_log.py",
    ]
    
    for f in utils_files:
        src = REPO_DIR / APP_NAME / f
        dst = DEB_DIR / SITE_PACKAGES / APP_NAME / f
        if src.exists():
            shutil.copy2(src, dst)
            log(f"  {f}")
    
    # Main entry point
    main_src = REPO_DIR / APP_NAME / "__main__.py"
    main_dst = DEB_DIR / SITE_PACKAGES / APP_NAME / "__main__.py"
    if main_src.exists():
        shutil.copy2(main_src, main_dst)
        log("  __main__.py")
    
    log("  Python files copied", Colors.GREEN)


def copy_assets():
    """Copy application assets"""
    log("Copying assets...", Colors.BLUE)
    
    # Desktop file
    desktop_src = REPO_DIR / f"{APP_NAME}.desktop"
    desktop_dst = DEB_DIR / "usr/share/applications" / f"{APP_NAME}.desktop"
    if desktop_src.exists():
        shutil.copy2(desktop_src, desktop_dst)
        log("  desktop file")
    
    # Icon
    icon_src = REPO_DIR / "img" / "logo.png"
    icon_dst = DEB_DIR / "usr/share/icons" / f"{APP_NAME}.png"
    if icon_src.exists():
        shutil.copy2(icon_src, icon_dst)
        log("  icon")
    
    log("  Assets copied", Colors.GREEN)


def install_rclone(rclone_binary):
    """Install rclone binary into package"""
    log("Installing rclone binary...", Colors.BLUE)
    
    dst = DEB_DIR / "usr/lib" / APP_NAME / "rclone" / "rclone"
    shutil.copy2(rclone_binary, dst)
    os.chmod(dst, 0o755)
    
    log(f"  rclone installed: {dst}", Colors.GREEN)


def create_bin_scripts():
    """Create bin scripts"""
    log("Creating bin scripts...", Colors.BLUE)
    
    # Wrapper script that finds embedded rclone
    wrapper = f'''#!/bin/bash
# Wrapper script for {APP_NAME}
# Finds embedded rclone or uses system rclone

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
EMBEDDED_RCLONE="$SCRIPT_DIR/../lib/{APP_NAME}/rclone/rclone"

# Check for embedded rclone first
if [ -x "$EMBEDDED_RCLONE" ]; then
    export RCLONE_CONFIG_DIR="$HOME/.config/rclone"
    exec "$EMBEDDED_RCLONE" "$@"
else
    # Fall back to system rclone
    exec rclone "$@"
fi
'''
    
    wrapper_dst = DEB_DIR / BIN_DIR / APP_NAME
    with open(wrapper_dst, 'w') as f:
        f.write(wrapper)
    os.chmod(wrapper_dst, 0o755)
    
    # GUI launcher
    gui_launcher = f'''#!/bin/bash
# GUI launcher for {APP_NAME}

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PYTHON_PATH=$(which python3)

# Find embedded rclone
export RCLONE_CONFIG_DIR="$HOME/.config/rclone"

exec "$PYTHON_PATH" -m {APP_NAME} "$@"
'''
    
    gui_dst = DEB_DIR / BIN_DIR / f"{APP_NAME}-gui"
    with open(gui_dst, 'w') as f:
        f.write(gui_launcher)
    os.chmod(gui_dst, 0o755)
    
    log(f"  Created: {APP_NAME}", Colors.GREEN)
    log(f"  Created: {APP_NAME}-gui", Colors.GREEN)


def create_debian_files():
    """Create Debian control files"""
    log("Creating Debian files...", Colors.BLUE)
    
    # debian/control
    control_content = f"""Source: {APP_NAME}
Maintainer: {MAINTAINER} <{MAINTAINER}@example.com>
Section: python
Priority: optional
Build-Depends: dh-python, python3-setuptools, python3-all, debhelper (>= 9)
Standards-Version: 3.9.6
Homepage: {HOMEPAGE}

Package: python3-{APP_NAME}
Architecture: all
Depends: ${{misc:Depends}}, ${{python3:Depends}}, rclone
Description: {APP_DESCRIPTION}
 lX Drive es un cliente de sincronización avanzado para Google Drive en Linux.
 .
 Características:
  • Soporte multi-cuenta
  • Modo VFS (streaming) y sync (espejo)
  • Detección de cambios en tiempo real
  • Resolución de conflictos inteligente
  • Interfaz moderna con PyQt6
  • rclone embebido para funcionamiento autónomo

Package: {APP_NAME}
Architecture: amd64
Depends: ${{misc:Depends}}, python3-{APP_NAME}, rclone
Description: {APP_NAME} (metapackage)
 Metapaquete para instalar {APP_NAME} y todas sus dependencias.
"""
    
    control_dst = DEB_DIR / "debian" / "control"
    with open(control_dst, 'w') as f:
        f.write(control_content)
    
    # debian/rules
    rules_content = """#!/usr/bin/make -f

%:
\tdh $@ --with python3

override_dh_auto_install:
\t# Don't install Python files via dh_auto_install
"""
    
    rules_dst = DEB_DIR / "debian" / "rules"
    with open(rules_dst, 'w') as f:
        f.write(rules_content)
    os.chmod(rules_dst, 0o755)
    
    # debian/postinst
    postinst = """#!/bin/bash
set -e

# Create config directory
mkdir -p ~/.config/lxdrive
mkdir -p ~/.config/autostart

echo "lX Drive installed successfully!"

# Create default config if not exists
if [ ! -f ~/.config/lxdrive/config.yaml ]; then
    cat > ~/.config/lxdrive/config.yaml << 'EOF'
# lX Drive Configuration
start_minimized: true
notify_sync_complete: true
theme: dark
language: es
EOF
fi

exit 0
"""
    
    postinst_dst = DEB_DIR / "debian" / "postinst"
    with open(postinst_dst, 'w') as f:
        f.write(postinst)
    os.chmod(postinst_dst, 0o755)
    
    # debian/prerm
    prerm = """#!/bin/bash
set -e

# Don't remove user data on uninstall
echo "To completely remove lX Drive, delete ~/.config/lxdrive manually"

exit 0
"""
    
    prerm_dst = DEB_DIR / "debian" / "prerm"
    with open(prerm_dst, 'w') as f:
        f.write(prerm)
    os.chmod(prerm_dst, 0o755)
    
    log("  debian/control", Colors.GREEN)
    log("  debian/rules", Colors.GREEN)
    log("  debian/postinst", Colors.GREEN)
    log("  debian/prerm", Colors.GREEN)


def create_changelog():
    """Create debian changelog"""
    log("Creating changelog...", Colors.BLUE)
    
    changelog = f"""{APP_NAME} ({APP_VERSION}) unstable; urgency=low

  * v2.0.0 - Nueva arquitectura de sincronización
    - Motor basado en file_id (detecta moves/renames correctamente)
    - Soporte para 10+ cuentas
    - Caché híbrido (≤10GB local, >10GB on-demand)
    - Resolución de conflictos mejorada
    - UI moderna con Qt Material
    - rclone embebido en el paquete
    - Inicio minimizado a bandeja por defecto

 -- {MAINTAINER}  {datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}
"""
    
    changelog_dst = DEB_DIR / "debian" / "changelog"
    with open(changelog_dst, 'w') as f:
        f.write(changelog)
    
    log("  changelog created", Colors.GREEN)


def build_deb():
    """Build the .deb package"""
    log("Building .deb package...", Colors.YELLOW)
    
    # Download rclone
    rclone_binary = download_rclone()
    
    # Prepare structure
    prepare_deb_structure()
    
    # Copy files
    copy_python_files()
    copy_assets()
    
    # Install rclone
    install_rclone(rclone_binary)
    
    # Create scripts
    create_bin_scripts()
    
    # Create debian files
    create_debian_files()
    create_changelog()
    
    # Build .deb
    deb_path = REPO_DIR / f"{APP_NAME}_{APP_VERSION}_amd64.deb"
    if deb_path.exists():
        deb_path.unlink()
    
    log("Running dpkg-deb...", Colors.BLUE)
    run_command(f"dpkg-deb --build {DEB_DIR} {deb_path}")
    
    log(f"✅ .deb created: {deb_path}", Colors.GREEN)
    log(f"   Size: {deb_path.stat().st_size / 1024 / 1024:.1f} MB", Colors.GREEN)
    
    return deb_path


def install_deb(deb_path):
    """Install the .deb package"""
    log(f"Installing {deb_path}...", Colors.YELLOW)
    
    if not deb_path.exists():
        log(f"Error: {deb_path} not found. Run build first.", Colors.RED)
        sys.exit(1)
    
    # Install with dpkg
    run_command(f"sudo dpkg -i {deb_path}")
    
    log("✅ Installation complete!", Colors.GREEN)
    log("Run: lxdrive-gui", Colors.BLUE)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description=f"Build script for {APP_NAME}")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    parser.add_argument("--deb", action="store_true", help="Build .deb package (default)")
    parser.add_argument("--install", action="store_true", help="Install after building")
    parser.add_argument("--appimage", action="store_true", help="Build AppImage (not implemented)")
    
    args = parser.parse_args()
    
    print()
    log(f"{Colors.BOLD}lX Drive v{APP_VERSION} Build Script{Colors.END}", Colors.BLUE)
    print()
    
    if args.clean:
        clean()
        return
    
    try:
        deb_path = build_deb()
        
        if args.install:
            install_deb(deb_path)
    
    except Exception as e:
        log(f"Build failed: {e}", Colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    main()
