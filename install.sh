#!/bin/bash

set -e

APP_NAME="lX_Drive"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="$HOME"

echo "=========================================="
echo "  $APP_NAME - Installation Script"
echo "=========================================="
echo ""

check_dependencies() {
    echo "Checking dependencies..."
    
    local missing=()
    
    if ! command -v rclone &> /dev/null; then
        missing+=("rclone")
    fi
    
    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    fi
    
    if ! python3 -c "import gi" 2>/dev/null; then
        missing+=("gir1.2-gtk-4.0 (PyGObject)")
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        echo "Missing dependencies:"
        for dep in "${missing[@]}"; do
            echo "  - $dep"
        done
        echo ""
        echo "Install them with:"
        echo "  sudo apt install rclone python3 python3-gi gir1.2-gtk-4.0"
        echo ""
        read -p "Continue anyway? (y/N): " choice
        case "$choice" in 
            y|Y ) echo "Continuing...";;
            * ) echo "Aborting."; exit 1;;
        esac
    else
        echo "All dependencies satisfied."
    fi
}

create_directories() {
    echo "Creating directories..."
    
    mkdir -p "$HOME_DIR/.config/lxdrive/logs"
    mkdir -p "$HOME_DIR/.config/lxdrive"
    mkdir -p "$HOME_DIR/.local/share/lxdrive/icons"
    mkdir -p "$HOME_DIR/.local/share/applications"
    mkdir -p "$HOME_DIR/.local/bin"
    mkdir -p "$HOME_DIR/.config/systemd/user"
    mkdir -p "$HOME_DIR/Cloud"
}

install_python_deps() {
    echo "Installing Python dependencies..."
    
    pip3 install --user -q PyGObject pyxdg 2>/dev/null || {
        echo "Warning: Could not install Python dependencies via pip."
        echo "Make sure PyGObject and pyxdg are available."
    }
}

install_app() {
    echo "Installing application files..."
    
    cp -r "$SCRIPT_DIR/lxdrive" "$HOME_DIR/.local/share/lxdrive/"
    
    cp -r "$SCRIPT_DIR/data/icons/"* "$HOME_DIR/.local/share/lxdrive/icons/" 2>/dev/null || true
    
    cat > "$HOME_DIR/.local/bin/lxdrive" << 'EOF'
#!/bin/bash
cd /usr/share/lxdrive 2>/dev/null || cd ~/.local/share/lxdrive 2>/dev/null
python3 -m lxdrive.main "$@"
EOF
    chmod +x "$HOME_DIR/.local/bin/lxdrive"
    
    if [[ ":$PATH:" != *":$HOME_DIR/.local/bin:"* ]]; then
        echo ""
        echo "Note: ~/.local/bin is not in your PATH."
        echo "Add this to your ~/.bashrc:"
        echo '  export PATH="$HOME/.local/bin:$PATH"'
    fi
}

create_desktop_entry() {
    echo "Creating desktop entry..."
    
    cat > "$HOME_DIR/.local/share/applications/lxdrive.desktop" << EOF
[Desktop Entry]
Version=1.0
Name=$APP_NAME
Comment=Cloud sync manager for Linux Mint
Exec=$HOME_DIR/.local/bin/lxdrive
Icon=$HOME_DIR/.local/share/lxdrive/icons/lxdrive.svg
Terminal=false
Type=Application
Categories=Network;FileTransfer;GTK;
StartupNotify=true
Keywords=cloud;sync;drive;rclone;
EOF
    
    chmod +x "$HOME_DIR/.local/share/applications/lxdrive.desktop"
    
    update-desktop-database "$HOME_DIR/.local/share/applications" 2>/dev/null || true
}

install_systemd_services() {
    echo "Installing systemd service templates..."
    
    cp "$SCRIPT_DIR/services/"*.service "$HOME_DIR/.config/systemd/user/" 2>/dev/null || true
    
    systemctl --user daemon-reload 2>/dev/null || true
}

create_config() {
    echo "Creating default configuration..."
    
    if [ ! -f "$HOME_DIR/.config/lxdrive/config.json" ]; then
        cat > "$HOME_DIR/.config/lxdrive/config.json" << EOF
{
    "theme": "system",
    "autostart_app": false,
    "log_level": "INFO",
    "mount_base_path": "$HOME_DIR/Cloud",
    "window_width": 900,
    "window_height": 600
}
EOF
    fi
}

print_success() {
    echo ""
    echo "=========================================="
    echo "  Installation Complete!"
    echo "=========================================="
    echo ""
    echo "To launch $APP_NAME:"
    echo "  - From terminal: lxdrive"
    echo "  - From menu: Search for 'lX_Drive'"
    echo ""
    echo "Configuration files are in:"
    echo "  ~/.config/lxdrive/"
    echo ""
    echo "Logs are stored in:"
    echo "  ~/.config/lxdrive/logs/"
    echo ""
    echo "Cloud mounts will be in:"
    echo "  ~/Cloud/"
    echo ""
    echo "First run guide:"
    echo "  1. Open lX_Drive"
    echo "  2. Go to 'Accounts' tab"
    echo "  3. Click 'Add Account' and select your provider"
    echo "  4. Follow the rclone configuration wizard"
    echo "  5. Go to 'Tasks' tab and create a mount or sync task"
    echo ""
}

main() {
    check_dependencies
    create_directories
    install_python_deps
    install_app
    create_desktop_entry
    install_systemd_services
    create_config
    print_success
}

main "$@"
