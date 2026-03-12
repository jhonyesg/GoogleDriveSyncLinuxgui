#!/bin/bash

set -e

APP_NAME="lX_Drive"
HOME_DIR="$HOME"

echo "=========================================="
echo "  $APP_NAME - Uninstallation Script"
echo "=========================================="
echo ""

read -p "Are you sure you want to uninstall $APP_NAME? (y/N): " choice
case "$choice" in 
    y|Y ) echo "Proceeding with uninstallation...";;
    * ) echo "Aborting."; exit 0;;
esac

echo ""
echo "Stopping any running services..."

for service in $(systemctl --user list-units --all "lxdrive-*" 2>/dev/null | grep -o "lxdrive-[^\ ]*\.service" || true); do
    echo "  Stopping $service..."
    systemctl --user stop "$service" 2>/dev/null || true
    systemctl --user disable "$service" 2>/dev/null || true
done

echo ""
echo "Removing files..."

rm -f "$HOME_DIR/.local/bin/lxdrive"
rm -f "$HOME_DIR/.local/share/applications/lxdrive.desktop"
rm -f "$HOME_DIR/.config/autostart/lxdrive.desktop"
rm -rf "$HOME_DIR/.local/share/lxdrive"
rm -f "$HOME_DIR/.config/systemd/user/lxdrive-"*.service

update-desktop-database "$HOME_DIR/.local/share/applications" 2>/dev/null || true
systemctl --user daemon-reload 2>/dev/null || true

echo ""
read -p "Remove configuration files (~/.config/lxdrive)? (y/N): " choice
case "$choice" in 
    y|Y ) 
        rm -rf "$HOME_DIR/.config/lxdrive"
        echo "Configuration removed."
        ;;
    * ) 
        echo "Configuration files preserved."
        ;;
esac

echo ""
read -p "Remove Cloud mount directory (~/Cloud)? (y/N): " choice
case "$choice" in 
    y|Y ) 
        rm -rf "$HOME_DIR/Cloud"
        echo "Cloud directory removed."
        ;;
    * ) 
        echo "Cloud directory preserved."
        ;;
esac

echo ""
echo "=========================================="
echo "  Uninstallation Complete!"
echo "=========================================="
echo ""
