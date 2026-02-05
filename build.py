#!/usr/bin/env python3
"""
Build script for lX Drive v2.0

Creates a self-contained .deb package using dh-virtualenv.

Usage:
    python3 build.py              # Build .deb
    python3 build.py --clean      # Clean build artifacts
"""

import os
import sys
import shutil
import subprocess
import argparse
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

# Build paths
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_DIR = SCRIPT_DIR
BUILD_DIR = REPO_DIR / "build"
DEB_DIST_DIR = REPO_DIR / "deb_dist" / f"{APP_NAME}-{APP_VERSION}"


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
    print(f"{Colors.GREEN}[lX Drive Build]{Colors.END} {msg}")


def run_command(cmd, cwd=None, check=True):
    """Run a shell command"""
    log(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, check=check, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Command failed: {result.stderr}", Colors.RED)
        if check:
            sys.exit(1)
    return result


def clean():
    """Clean build artifacts"""
    log("Cleaning build artifacts...", Colors.YELLOW)
    
    dirs_to_remove = [
        BUILD_DIR,
        DEB_DIST_DIR,
        REPO_DIR / "dist",
        REPO_DIR / f"{APP_NAME}.egg-info",
        REPO_DIR / f"{APP_NAME}_{APP_VERSION}_amd64.deb",
    ]
    
    for d in dirs_to_remove:
        if d.exists():
            shutil.rmtree(d)
            log(f"  Removed: {d}")
    
    for pycache in REPO_DIR.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    
    log("Clean complete!", Colors.GREEN)


def download_rclone():
    """Download rclone binary"""
    log(f"Downloading rclone {RCLONE_VERSION}...", Colors.BLUE)
    
    zip_path = BUILD_DIR / "rclone.zip"
    
    if not zip_path.exists():
        log(f"  Downloading from {RCLONE_URL}...")
        urllib.request.urlretrieve(RCLONE_URL, zip_path)
        log(f"  Downloaded: {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        log("  Using cached download")
    
    # Extract
    extract_dir = BUILD_DIR / "rclone-extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    
    log("  Extracting...")
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_dir)
    
    # Find rclone binary (it's inside a subfolder)
    rclone_binary = None
    for root, dirs, files in os.walk(extract_dir):
        if "rclone" in files and not any(x in root for x in ['.zip', '.txt', '.html', '.1']):
            rclone_binary = os.path.join(root, "rclone")
            break
    
    if not rclone_binary or not os.path.exists(rclone_binary):
        raise FileNotFoundError(f"rclone binary not found in {extract_dir}")
    
    log(f"  rclone binary ready", Colors.GREEN)
    return rclone_binary


def prepare_build():
    """Prepare build directory structure"""
    log("Preparing build structure...", Colors.BLUE)
    
    if DEB_DIST_DIR.exists():
        shutil.rmtree(DEB_DIST_DIR)
    
    DEB_DIST_DIR.mkdir(parents=True)
    
    dirs = [
        DEB_DIST_DIR / "usr/share/applications",
        DEB_DIST_DIR / "usr/share/icons",
        DEB_DIST_DIR / "usr/lib" / APP_NAME / "rclone",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    log("  Structure ready", Colors.GREEN)
    return DEB_DIST_DIR


def copy_application_files(deb_dir):
    """Copy application files to build directory"""
    log("Copying application files...", Colors.BLUE)
    
    # Python package directory
    pkg_dir = deb_dir / "usr/lib/python3/dist-packages" / APP_NAME
    pkg_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy entire lxdrive package
    src_pkg = REPO_DIR / APP_NAME
    dst_pkg = pkg_dir
    
    for item in src_pkg.iterdir():
        if item.is_file() and item.suffix == '.py':
            shutil.copy2(item, dst_pkg / item.name)
            log(f"  {item.name}")
        elif item.is_dir():
            dst_subdir = dst_pkg / item.name
            dst_subdir.mkdir(parents=True, exist_ok=True)
            for subitem in item.rglob("*.py"):
                rel_path = subitem.relative_to(item)
                dst_file = dst_subdir / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(subitem, dst_file)
            log(f"  {item.name}/")
    
    log("  Files copied", Colors.GREEN)


def copy_assets(deb_dir):
    """Copy desktop file and icon"""
    log("Copying assets...", Colors.BLUE)
    
    # Desktop file
    desktop_src = REPO_DIR / f"{APP_NAME}.desktop"
    if desktop_src.exists():
        shutil.copy2(desktop_src, deb_dir / "usr/share/applications" / f"{APP_NAME}.desktop")
        log("  desktop file")
    
    # Icon
    icon_src = REPO_DIR / "img" / "logo.png"
    if icon_src.exists():
        shutil.copy2(icon_src, deb_dir / "usr/share/icons" / f"{APP_NAME}.png")
        log("  icon")
    
    log("  Assets ready", Colors.GREEN)


def install_rclone(deb_dir, rclone_binary):
    """Install rclone binary"""
    log("Installing rclone binary...", Colors.BLUE)
    
    dst = deb_dir / "usr/lib" / APP_NAME / "rclone" / "rclone"
    shutil.copy2(rclone_binary, dst)
    os.chmod(dst, 0o755)
    
    log(f"  rclone installed", Colors.GREEN)


def create_wrapper_scripts(deb_dir):
    """Create wrapper scripts"""
    log("Creating wrapper scripts...", Colors.BLUE)
    
    bin_dir = deb_dir / "usr/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    
    # Main script
    main_script = f'''#!/bin/bash
# Main launcher for {APP_NAME}

# Find embedded rclone
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
EMBEDDED_RCLONE="$SCRIPT_DIR/../lib/{APP_NAME}/rclone/rclone"

export RCLONE_CONFIG_DIR="$HOME/.config/rclone"

# Use embedded rclone if available
if [ -x "$EMBEDDED_RCLONE" ]; then
    export RCLONE="{APP_NAME}"
fi

python3 -m {APP_NAME} "$@"
'''
    
    main_dst = bin_dir / APP_NAME
    with open(main_dst, 'w') as f:
        f.write(main_script)
    os.chmod(main_dst, 0o755)
    log(f"  Created: {APP_NAME}")
    
    # GUI script
    gui_script = f'''#!/bin/bash
# GUI launcher for {APP_NAME}

# Find embedded rclone
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
EMBEDDED_RCLONE="$SCRIPT_DIR/../lib/{APP_NAME}/rclone/rclone"

export RCLONE_CONFIG_DIR="$HOME/.config/rclone"

# Use embedded rclone if available
if [ -x "$EMBEDDED_RCLONE" ]; then
    export RCLONE="{APP_NAME}"
fi

python3 -m {APP_NAME} --gui "$@"
'''
    
    gui_dst = bin_dir / f"{APP_NAME}-gui"
    with open(gui_dst, 'w') as f:
        f.write(gui_script)
    os.chmod(gui_dst, 0o755)
    log(f"  Created: {APP_NAME}-gui")
    
    log("  Scripts ready", Colors.GREEN)


def create_debian_files(deb_dir):
    """Create Debian control files"""
    log("Creating Debian files...", Colors.BLUE)
    
    # NOTE: debian directory must be named DEBIAN (uppercase) for dpkg-deb
    debian_dir = deb_dir / "DEBIAN"
    debian_dir.mkdir(parents=True, exist_ok=True)
    
    # control file - MUST be ASCII, no special characters
    control = f"""Source: lxdrive
Maintainer: {MAINTAINER}
Section: python
Priority: optional
Build-Depends: dh-python, python3-all, debhelper (>= 9)
Standards-Version: 3.9.6
Homepage: {HOMEPAGE}
Package: python3-{APP_NAME}
Version: {APP_VERSION}
Architecture: all
Depends: python3, rclone
Description: {APP_DESCRIPTION}
 {APP_NAME} es un cliente de sincronizacion avanzado para Google Drive.
 .
 Features:
  - Multi-account support
  - VFS mode and sync mode
  - Real-time change detection
  - Intelligent conflict resolution
  - Modern PyQt6 UI
  - Embedded rclone binary
"""
    
    with open(debian_dir / "control", 'w') as f:
        f.write(control)
    log("  DEBIAN/control")
    
    # rules (optional for dpkg-deb direct build)
    rules = "#!/usr/bin/make -f\n%\n\tdh $@\n"
    with open(debian_dir / "rules", 'w') as f:
        f.write(rules)
    os.chmod(debian_dir / "rules", 0o755)
    log("  DEBIAN/rules")
    
    # changelog
    changelog = f"""Source: {APP_NAME}
Binary: python3-{APP_NAME}
Maintainer: {MAINTAINER}
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}
Version: {APP_VERSION}
Distribution: unstable
Urgency: low

  * v2.0.0 - Nueva arquitectura de sincronizacion
    - Motor basado en file_id (detecta moves/renames correctamente)
    - Soporte para 10+ cuentas
    - Cache hibrido (<=10GB local, >10GB on-demand)
    - Resolucion de conflictos mejorada
    - UI moderna con Qt Material
    - rclone embebido en el paquete

 -- {MAINTAINER}  {datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}
"""
    
    with open(debian_dir / "changelog", 'w') as f:
        f.write(changelog)
    log("  DEBIAN/changelog")
    
    # compat
    with open(debian_dir / "compat", 'w') as f:
        f.write("9")
    log("  DEBIAN/compat")
    
    log("  Debian files ready", Colors.GREEN)


def build_deb():
    """Build the .deb package using dh-virtualenv"""
    log("Building .deb package...", Colors.YELLOW)
    
    # Download rclone
    rclone_binary = download_rclone()
    
    # Prepare structure
    deb_dir = prepare_build()
    
    # Copy files
    copy_application_files(deb_dir)
    copy_assets(deb_dir)
    install_rclone(deb_dir, rclone_binary)
    create_wrapper_scripts(deb_dir)
    create_debian_files(deb_dir)
    
    log("\n========================================", Colors.BLUE)
    log("Estructura preparada en:", Colors.BLUE)
    log(f"  {deb_dir}", Colors.YELLOW)
    log("\nPara construir el .deb, necesitas dh-virtualenv:", Colors.BLUE)
    log("  sudo apt install dh-virtualenv", Colors.YELLOW)
    log("  cd deb_dist/lxdrive-2.0.0 && debuild -us -uc", Colors.YELLOW)
    log("\nO usa el metodo alternativo sin dh-virtualenv:", Colors.BLUE)
    log(f"  cd {deb_dir}", Colors.YELLOW)
    log("  dpkg-deb --build . ../lxdrive_2.0.0_amd64.deb", Colors.YELLOW)
    log("========================================\n", Colors.BLUE)
    
    return deb_dir


def build_deb_simple():
    """Build .deb without dh-virtualenv (using dpkg-deb directly)"""
    log("Building .deb package (simple method)...", Colors.YELLOW)
    
    # Download rclone
    rclone_binary = download_rclone()
    
    # Prepare structure
    deb_dir = prepare_build()
    
    # Copy files
    copy_application_files(deb_dir)
    copy_assets(deb_dir)
    install_rclone(deb_dir, rclone_binary)
    create_wrapper_scripts(deb_dir)
    create_debian_files(deb_dir)
    
    # Build .deb
    deb_path = REPO_DIR / f"{APP_NAME}_{APP_VERSION}_amd64.deb"
    if deb_path.exists():
        deb_path.unlink()
    
    log(f"Building .deb with dpkg-deb...", Colors.BLUE)
    run_command(f"dpkg-deb --build {deb_dir} {deb_path}")
    
    log(f"\n✅ .deb creado: {deb_path}", Colors.GREEN)
    log(f"   Size: {deb_path.stat().st_size / 1024 / 1024:.1f} MB", Colors.GREEN)
    
    return deb_path


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description=f"Build script for {APP_NAME}")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    parser.add_argument("--simple", action="store_true", help="Build .deb without dh-virtualenv (recommended)")
    
    args = parser.parse_args()
    
    print()
    log(f"{Colors.BOLD}lX Drive v{APP_VERSION} Build Script{Colors.END}", Colors.BLUE)
    print()
    
    if args.clean:
        clean()
        return
    
    try:
        deb_path = build_deb_simple()
        
        print()
        log("Para instalar:", Colors.YELLOW)
        log(f"  sudo dpkg -i {deb_path}", Colors.BLUE)
        log(f"  {APP_NAME}-gui", Colors.YELLOW)
        
    except Exception as e:
        log(f"Build failed: {e}", Colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    main()
