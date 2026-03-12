#!/bin/bash
set -e

VERSION="1.0.0"
PACKAGE_NAME="lxdrive"
BUILD_DIR="debian-package/${PACKAGE_NAME}"
PYTHON_VERSION="3.12"

rm -rf debian-package/${PACKAGE_NAME}

mkdir -p ${BUILD_DIR}/DEBIAN
mkdir -p ${BUILD_DIR}/usr/share/${PACKAGE_NAME}
mkdir -p ${BUILD_DIR}/usr/bin
mkdir -p ${BUILD_DIR}/usr/share/applications
mkdir -p ${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps
mkdir -p ${BUILD_DIR}/usr/share/icons/hicolor/128x128/apps
mkdir -p ${BUILD_DIR}/usr/share/doc/${PACKAGE_NAME}

cp -r lxdrive ${BUILD_DIR}/usr/share/${PACKAGE_NAME}/
find ${BUILD_DIR}/usr/share/${PACKAGE_NAME} -name "*.pyc" -delete
find ${BUILD_DIR}/usr/share/${PACKAGE_NAME} -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

cat > ${BUILD_DIR}/usr/bin/${PACKAGE_NAME} << 'EOF'
#!/bin/bash
cd /usr/share/lxdrive
exec python3 -m lxdrive.main "$@"
EOF
chmod 755 ${BUILD_DIR}/usr/bin/${PACKAGE_NAME}

cp data/icons/lxdrive.svg ${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/
cp data/icons/google-drive.svg ${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/
cp data/icons/onedrive.svg ${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/
cp data/icons/dropbox.svg ${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/

if [ -f lxdrive.png ]; then
    cp lxdrive.png ${BUILD_DIR}/usr/share/icons/hicolor/128x128/apps/
fi

cat > ${BUILD_DIR}/usr/share/applications/${PACKAGE_NAME}.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=lX_Drive
Comment=Cloud sync manager for Linux Mint
Exec=${PACKAGE_NAME}
Icon=${PACKAGE_NAME}
Terminal=false
Categories=Network;FileTransfer;GTK;
StartupNotify=true
Keywords=cloud;sync;drive;rclone;
EOF

cat > ${BUILD_DIR}/DEBIAN/control << EOF
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, rclone, python3-xdg, gir1.2-ayatanaappindicator3-0.1 | gir1.2-appindicator3-0.1
Maintainer: lX_Drive Team <info@lxdrive.org>
Description: Cloud sync manager for Linux Mint
 lX_Drive is a desktop application for Linux Mint that manages
 bidirectional synchronization between local folders and multiple
 cloud providers using rclone as backend.
 .
 Features:
  - Support for Google Drive, OneDrive, Dropbox and more
  - Mount cloud storage as local filesystem using VFS
  - Bidirectional synchronization with conflict resolution
  - Automatic startup on system boot
  - Easy to use GTK3 interface
  - Tray icon for background operation
EOF

cat > ${BUILD_DIR}/DEBIAN/postinst << 'EOF'
#!/bin/bash
set -e
gtk-update-icon-cache /usr/share/icons/hicolor/ 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
EOF
chmod 755 ${BUILD_DIR}/DEBIAN/postinst

cat > ${BUILD_DIR}/DEBIAN/prerm << 'EOF'
#!/bin/bash
set -e
EOF
chmod 755 ${BUILD_DIR}/DEBIAN/prerm

INSTALLED_SIZE=$(du -sk ${BUILD_DIR} | cut -f1)
echo "$INSTALLED_SIZE" > ${BUILD_DIR}/DEBIAN/installed-size 2>/dev/null || true

dpkg-deb --build --root-owner-group ${BUILD_DIR}

mv debian-package/${PACKAGE_NAME}_${VERSION}_all.deb . 2>/dev/null || true

echo ""
echo "Paquete creado: ${PACKAGE_NAME}_${VERSION}_all.deb"
echo ""
