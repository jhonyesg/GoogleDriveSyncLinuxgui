#!/usr/bin/env python3
"""
MainWindow - Ventana principal de lX Drive

Interfaz de usuario moderna para gestionar las cuentas de cloud storage.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QStackedWidget, QFrame, QProgressBar, QMenu,
    QMessageBox, QFileDialog, QSplitter, QStatusBar,
    QToolBar, QSizePolicy, QSpacerItem, QGroupBox,
    QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QDialog, QFormLayout, QDialogButtonBox,
    QAbstractItemView, QScrollArea, QSystemTrayIcon # Added QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QIcon, QFont, QAction, QColor, QPalette, QPixmap
from pathlib import Path
from typing import Optional
from datetime import datetime
from loguru import logger

from ..core import RcloneWrapper, AccountManager, SyncManager, MountManager
from ..core.account_manager import Account, SyncStatus, SyncDirection
from ..core.rclone_wrapper import RemoteType


class AccountWidget(QFrame):
    """Widget para mostrar una cuenta en la lista"""
    
    clicked = pyqtSignal(str)  # Emite account_id
    sync_requested = pyqtSignal(str)
    mount_requested = pyqtSignal(str)
    settings_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    
    def __init__(self, account: Account, parent=None):
        super().__init__(parent)
        self.account = account
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        """Configura la interfaz del widget"""
        self.setFixedHeight(90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(15)
        
        # Icono del servicio
        icon_label = QLabel()
        icon_label.setFixedSize(50, 50)
        icon_text = self._get_service_icon()
        icon_label.setText(icon_text)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4285f4, stop:1 #34a853);
                border-radius: 12px;
                font-size: 24px;
                color: white;
            }
        """)
        layout.addWidget(icon_label)
        
        # Información de la cuenta
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # Nombre
        self.name_label = QLabel(self.account.name)
        self.name_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info_layout.addWidget(self.name_label)
        
        # Ruta local
        path_label = QLabel(f"📁 {self.account.local_path}")
        path_label.setStyleSheet("color: #888; font-size: 11px;")
        info_layout.addWidget(path_label)
        
        # Estado
        self.status_label = QLabel(self._get_status_text())
        self.status_label.setStyleSheet(f"color: {self._get_status_color()}; font-size: 11px;")
        info_layout.addWidget(self.status_label)
        
        layout.addLayout(info_layout, 1)
        
        # Botones de acción
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        # Botón sincronizar
        self.sync_btn = QPushButton("⟳")
        self.sync_btn.setFixedSize(36, 36)
        self.sync_btn.setToolTip("Sincronizar ahora")
        self.sync_btn.clicked.connect(lambda: self.sync_requested.emit(self.account.id))
        btn_layout.addWidget(self.sync_btn)
        
        # Botón montar
        mount_icon = "💾" if not self.account.mount_enabled else "⏏"
        self.mount_btn = QPushButton(mount_icon)
        self.mount_btn.setFixedSize(36, 36)
        self.mount_btn.setToolTip("Montar/Desmontar unidad")
        self.mount_btn.clicked.connect(lambda: self.mount_requested.emit(self.account.id))
        btn_layout.addWidget(self.mount_btn)
        
        # Botón configurar
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setToolTip("Configuración")
        self.settings_btn.clicked.connect(lambda: self.settings_requested.emit(self.account.id))
        btn_layout.addWidget(self.settings_btn)
        
        layout.addLayout(btn_layout)
    
    def _apply_styles(self):
        """Aplica estilos al widget"""
        self.setStyleSheet("""
            AccountWidget {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 12px;
            }
            AccountWidget:hover {
                background-color: #363636;
                border-color: #4285f4;
            }
            QPushButton {
                background-color: #3d3d3d;
                border: none;
                border-radius: 18px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #4285f4;
            }
        """)
    
    def _get_service_icon(self) -> str:
        """Obtiene el icono según el tipo de servicio"""
        icons = {
            "drive": "G",
            "dropbox": "D",
            "onedrive": "O",
            "pcloud": "P",
        }
        return icons.get(self.account.remote_type, "☁")
    
    def _get_status_text(self) -> str:
        """Obtiene el texto de estado"""
        # Si solo tiene mount habilitado (sin sync), mostrar estado de montaje
        if self.account.mount_enabled and not self.account.sync_enabled:
            if self.account.status == SyncStatus.IDLE:
                return "💾 Montado como unidad"
            elif self.account.status == SyncStatus.ERROR:
                error = self.account.error_message or "Error desconocido"
                if len(error) > 50:
                    error = error[:50] + "..."
                return f"⚠ {error}"
            return "💾 Listo para montar"
        
        # Estados para sync
        if self.account.status == SyncStatus.IDLE:
            return "✓ Sincronizado"
        elif self.account.status == SyncStatus.SYNCING:
            return "⟳ Sincronizando..."
        elif self.account.status == SyncStatus.RESYNCING:
            return "⟳ Indexando (primera vez)..."
        elif self.account.status == SyncStatus.PAUSED:
            return "⏸ Pausado"
        elif self.account.status == SyncStatus.ERROR:
            error = self.account.error_message or "Error desconocido"
            # Truncar mensajes de error largos
            if len(error) > 50:
                error = error[:50] + "..."
            return f"⚠ {error}"
        elif self.account.status == SyncStatus.OFFLINE:
            return "○ Sin conexión"
        
        return "Desconocido"
    
    def _get_status_color(self) -> str:
        """Obtiene el color según el estado"""
        colors = {
            SyncStatus.IDLE: "#34a853",
            SyncStatus.SYNCING: "#4285f4",
            SyncStatus.RESYNCING: "#fbbc04",  # Amarillo para indicar proceso especial
            SyncStatus.PAUSED: "#fbbc04",
            SyncStatus.ERROR: "#ea4335",
            SyncStatus.OFFLINE: "#888"
        }
        return colors.get(self.account.status, "#888")

    
    def update_account(self, account: Account):
        """Actualiza la información mostrada"""
        self.account = account
        self.name_label.setText(account.name)
        self.status_label.setText(self._get_status_text())
        self.status_label.setStyleSheet(f"color: {self._get_status_color()}; font-size: 11px;")
        
        mount_icon = "⏏" if account.mount_enabled else "💾"
        self.mount_btn.setText(mount_icon)
    
    def mousePressEvent(self, event):
        """Emite señal al hacer clic"""
        self.clicked.emit(self.account.id)
        super().mousePressEvent(event)


class RemoteBrowserDialog(QDialog):
    """Diálogo para navegar por las carpetas remotas de Google Drive"""
    def __init__(self, rclone, remote_name, parent=None):
        super().__init__(parent)
        self.rclone = rclone
        self.remote_name = remote_name
        self.current_path = ""
        self.selected_path = ""
        self._setup_ui()
        self._load_folders()

    def _setup_ui(self):
        self.setWindowTitle(f"Explorador Cloud - {self.remote_name}")
        self.setMinimumSize(400, 500)
        self.setStyleSheet("background-color: #1a1a1a; color: white;")
        layout = QVBoxLayout(self)
        
        self.path_label = QLabel("Ruta: /")
        self.path_label.setStyleSheet("color: #4285f4; font-weight: bold; padding: 5px;")
        layout.addWidget(self.path_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: #252525; border: 1px solid #333; border-radius: 5px; color: #ccc; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #2d2d2d; }
            QListWidget::item:selected { background-color: #4285f4; color: white; }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)
        
        btns = QHBoxLayout()
        self.select_btn = QPushButton("Seleccionar esta carpeta")
        self.select_btn.setStyleSheet("background-color: #4285f4; color: white; padding: 8px; border-radius: 5px;")
        self.select_btn.clicked.connect(self._on_select_clicked)
        btns.addWidget(self.select_btn)
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setStyleSheet("background-color: #333; color: white; padding: 8px; border-radius: 5px;")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def _load_folders(self, subpath=""):
        self.list_widget.clear()
        if subpath:
            self.list_widget.addItem(".. (Volver)")
        
        try:
            # Usar rclone lsf para listar solo directorios
            cmd = ["lsf", f"{self.remote_name}:{subpath}", "--dirs-only"]
            output = self.rclone.run_command(cmd)
            folders = output.splitlines()
            
            for f in folders:
                if f.strip():
                    self.list_widget.addItem(f.strip("/"))
            
            self.current_path = subpath
            self.path_label.setText(f"Ruta: /{subpath}")
            self.selected_path = subpath
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron cargar las carpetas: {e}")

    def _on_item_double_clicked(self, item):
        text = item.text()
        if text == ".. (Volver)":
            if "/" in self.current_path:
                new_path = "/".join(self.current_path.split("/")[:-1])
            else:
                new_path = ""
            self._load_folders(new_path)
        else:
            new_path = f"{self.current_path}/{text}".strip("/")
            self._load_folders(new_path)

    def _on_item_clicked(self, item):
        """Un solo clic: preparamos la ruta para ser seleccionada"""
        text = item.text()
        if text == ".. (Volver)":
            self.selected_path = self.current_path
        else:
            self.selected_path = f"{self.current_path}/{text}".strip("/")
        
        self.path_label.setText(f"Ruta: /{self.selected_path}")

    def _on_select_clicked(self):
        """Al darle al botón, confirmamos la selección actual"""
        # Si hay algo seleccionado en la lista que no sea "..", eso es lo que queremos
        current_item = self.list_widget.currentItem()
        if current_item:
            text = current_item.text()
            if text != ".. (Volver)":
                self.selected_path = f"{self.current_path}/{text}".strip("/")
            else:
                self.selected_path = self.current_path
        else:
            self.selected_path = self.current_path
            
        self.accept()

class AddSyncPairDialog(QDialog):
    """Diálogo para crear un nuevo vínculo de carpeta (Local ↔ Remote)"""
    def __init__(self, rclone, account, parent=None):
        super().__init__(parent)
        self.rclone = rclone
        self.account = account
        self.setWindowTitle(f"Añadir Carpeta - {account.name}")
        self.setMinimumWidth(450)
        self.setStyleSheet("background-color: #1e1e1e; color: white;")
        
        layout = QVBoxLayout(self)
        
        # 1. Ruta Local
        layout.addWidget(QLabel("Carpeta Local:"))
        local_layout = QHBoxLayout()
        self.local_edit = QLineEdit()
        self.local_edit.setPlaceholderText("/home/usuario/Carpeta")
        local_layout.addWidget(self.local_edit)
        
        browse_local_btn = QPushButton("Examinar...")
        browse_local_btn.clicked.connect(self._browse_local)
        local_layout.addWidget(browse_local_btn)
        layout.addLayout(local_layout)
        
        layout.addSpacing(10)
        
        # 2. Ruta Cloud
        layout.addWidget(QLabel("Carpeta en Google Drive:"))
        remote_layout = QHBoxLayout()
        self.remote_edit = QLineEdit()
        self.remote_edit.setPlaceholderText("Carpeta_en_la_Nube")
        remote_layout.addWidget(self.remote_edit)
        
        browse_remote_btn = QPushButton("Explorar Cloud...")
        browse_remote_btn.clicked.connect(self._browse_remote)
        browse_remote_btn.setStyleSheet("background-color: #4285f4; color: white;")
        remote_layout.addWidget(browse_remote_btn)
        layout.addLayout(remote_layout)
        
        layout.addSpacing(20)
        
        # Botones Finales
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        
        save_btn = QPushButton("Añadir Vínculo")
        save_btn.setStyleSheet("background-color: #34a853; color: white; padding: 10px 20px; font-weight: bold;")
        save_btn.clicked.connect(self._validate_and_accept)
        btns.addWidget(save_btn)
        
        layout.addLayout(btns)

    def _validate_and_accept(self):
        local = self.local_edit.text()
        remote = self.remote_edit.text()
        if not local or not Path(local).exists():
            QMessageBox.warning(self, "Error Local", "Debes seleccionar una carpeta local válida.")
            return
        if not remote:
            QMessageBox.warning(self, "Error Cloud", "Debes seleccionar una carpeta en la nube.\n(Para evitar sincronizar todo tu Drive por error)")
            return
        self.accept()

    def _browse_local(self):
        path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta Local")
        if path:
            self.local_edit.setText(path)

    def _browse_remote(self):
        browser = RemoteBrowserDialog(self.rclone, self.account.remote_name, self)
        if browser.exec():
            self.remote_edit.setText(browser.selected_path)

    def get_data(self):
        return self.local_edit.text(), self.remote_edit.text()


class AddAccountDialog(QDialog):
    """Diálogo para añadir una nueva cuenta"""
    
    def __init__(self, rclone: RcloneWrapper, parent=None):
        super().__init__(parent)
        self.rclone = rclone
        self.new_account: Optional[Account] = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura la interfaz del diálogo"""
        self.setWindowTitle("Añadir Cuenta")
        self.setMinimumSize(500, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit, QComboBox {
                padding: 10px 15px;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                background-color: #2d2d2d;
                color: white;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: white;
                selection-background-color: #4285f4;
                border: 1px solid #3d3d3d;
                outline: none;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #4285f4;
            }
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid #3d3d3d;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #4285f4;
                border-color: #4285f4;
            }
            QGroupBox {
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #3d3d3d;
                border-radius: 10px;
                margin-top: 15px;
                padding: 15px;
                padding-top: 25px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }
            QPushButton {
                padding: 12px 30px;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
                color: white;
            }
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4285f4, stop:1 #34a853);
            }
            QPushButton#primaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5a9cf5, stop:1 #4ab860);
            }
            QPushButton#secondaryBtn {
                background-color: #3d3d3d;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #4d4d4d;
            }
            QPushButton#browseBtn {
                background-color: #3d3d3d;
                padding: 10px;
                min-width: 40px;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(10)
        
        # Título
        title = QLabel("🌐 Nueva Cuenta Cloud")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # --- Grupo 1: Información básica ---
        basic_group = QGroupBox("Información de la cuenta")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(15)
        
        # Nombre de la cuenta
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: Google Drive Personal")
        basic_layout.addRow("Nombre de la cuenta:", self.name_input)
        
        # Tipo de servicio
        self.service_combo = QComboBox()
        self.service_combo.setToolTip("Elige el tipo de servicio cloud")
        # Primero, buscar remotes existentes para permitir re-utilizarlos
        existing_remotes = self.rclone.list_remotes()
        if existing_remotes:
            self.service_combo.addItem("--- Usar cuenta existente ---", "existing_header")
            for remote in existing_remotes:
                self.service_combo.addItem(f"🏠 Remote: {remote.name} ({remote.type})", f"remote:{remote.name}")
            self.service_combo.addItem("--- Crear nueva cuenta ---", "new_header")
        
        for r_type in RemoteType:
            self.service_combo.addItem(RemoteType.get_display_name(r_type), r_type)
            
        basic_layout.addRow("Servicio / Cuenta:", self.service_combo)
        
        main_layout.addWidget(basic_group)
        
        # === Modo de acceso ===
        mode_group = QGroupBox("Modo de acceso")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(12)
        
        # Opción: Montar como unidad
        self.mount_check = QCheckBox("💾 Montar como unidad de disco")
        self.mount_check.setChecked(True)
        self.mount_check.setToolTip("Accede a tus archivos como si fueran una unidad local")
        mode_layout.addWidget(self.mount_check)
        
        # Punto de montaje
        mount_path_layout = QHBoxLayout()
        mount_path_label = QLabel("    Punto de montaje:")
        mount_path_label.setStyleSheet("color: #aaa;")
        self.mount_path_input = QLineEdit()
        self.mount_path_input.setPlaceholderText("~/CloudDrives/MiCuenta")
        mount_path_layout.addWidget(mount_path_label)
        mount_path_layout.addWidget(self.mount_path_input)
        mode_layout.addLayout(mount_path_layout)
        
        # Separador visual
        separator = QLabel("─" * 50)
        separator.setStyleSheet("color: #3d3d3d;")
        separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_layout.addWidget(separator)
        
        # Opción: Sincronizar carpeta
        self.sync_check = QCheckBox("🔄 Sincronizar carpeta local (bidireccional)")
        self.sync_check.setChecked(False)
        self.sync_check.setToolTip("Sincroniza una carpeta local con una carpeta en la nube")
        self.sync_check.stateChanged.connect(self._on_sync_toggled)
        mode_layout.addWidget(self.sync_check)
        
        # Carpeta local para sincronización
        sync_folder_layout = QHBoxLayout()
        self.sync_folder_label = QLabel("    Carpeta local:")
        self.sync_folder_label.setStyleSheet("color: #aaa;")
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Selecciona una carpeta...")
        self.folder_input.setEnabled(False)
        
        self.browse_btn = QPushButton("📂")
        self.browse_btn.setObjectName("browseBtn")
        self.browse_btn.setFixedWidth(45)
        self.browse_btn.setEnabled(False)
        self.browse_btn.clicked.connect(self._browse_folder)
        
        sync_folder_layout.addWidget(self.sync_folder_label)
        sync_folder_layout.addWidget(self.folder_input)
        sync_folder_layout.addWidget(self.browse_btn)
        mode_layout.addLayout(sync_folder_layout)
        
        # Carpeta remota
        remote_folder_layout = QHBoxLayout()
        self.remote_folder_label = QLabel("    Carpeta remota:")
        self.remote_folder_label.setStyleSheet("color: #aaa;")
        self.remote_folder_input = QLineEdit()
        self.remote_folder_input.setPlaceholderText("/ (raíz) o /MiCarpeta")
        self.remote_folder_input.setEnabled(False)
        remote_folder_layout.addWidget(self.remote_folder_label)
        remote_folder_layout.addWidget(self.remote_folder_input)
        mode_layout.addLayout(remote_folder_layout)
        
        layout.addWidget(mode_group)
        
        # Espaciador
        layout.addStretch()
        
        # Nota informativa
        note = QLabel("ℹ️ Se abrirá el navegador para autorizar el acceso a tu cuenta")
        note.setStyleSheet("color: #888; font-size: 11px;")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)
        
        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        add_btn = QPushButton("✓ Añadir Cuenta")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_account)
        btn_layout.addWidget(add_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_sync_toggled(self, state):
        """Activa/desactiva los campos de sincronización"""
        enabled = state == 2  # Qt.CheckState.Checked
        self.folder_input.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self.remote_folder_input.setEnabled(enabled)
    
    def _browse_folder(self):
        """Abre diálogo para seleccionar carpeta"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de sincronización",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if folder:
            self.folder_input.setText(folder)
    
    def _show_styled_message(self, msg_type: str, title: str, text: str):
        """Muestra un mensaje con estilos oscuros"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        
        if msg_type == "info":
            msg.setIcon(QMessageBox.Icon.Information)
        elif msg_type == "warning":
            msg.setIcon(QMessageBox.Icon.Warning)
        elif msg_type == "error":
            msg.setIcon(QMessageBox.Icon.Critical)
        
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e1e;
            }
            QMessageBox QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QPushButton {
                background-color: #4285f4;
                color: white;
                padding: 8px 25px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a9cf5;
            }
        """)
        msg.exec()
    
    def _add_account(self):
        """Procesa la adición de la cuenta"""
        name = self.name_input.text().strip()
        selected_data = self.service_combo.currentData()
        
        # Validar selección de header
        if selected_data in ["existing_header", "new_header"]:
            self._show_styled_message("warning", "Error", "Por favor, elige una cuenta válida o un tipo de servicio de la lista.")
            return

        is_existing_remote = False
        remote_name = ""
        remote_type_str = ""
        
        if isinstance(selected_data, str) and selected_data.startswith("remote:"):
            is_existing_remote = True
            remote_name = selected_data.replace("remote:", "")
            # Buscar el tipo de remote
            remotes = self.rclone.list_remotes()
            for r in remotes:
                if r.name == remote_name:
                    remote_type_str = r.type
                    break
        else:
            remote_type = selected_data
            remote_type_str = remote_type.value
        
        mount_enabled = self.mount_check.isChecked()
        sync_enabled = self.sync_check.isChecked()
        
        mount_point = self.mount_path_input.text().strip()
        local_folder = self.folder_input.text().strip()
        remote_folder = self.remote_folder_input.text().strip() or ""
        
        # Validaciones
        if not name:
            self._show_styled_message("warning", "Error", "Por favor, ingresa un nombre para la cuenta")
            return
        
        if not mount_enabled and not sync_enabled:
            self._show_styled_message("warning", "Error", "Debes seleccionar al menos un modo de acceso:\n• Montar como unidad\n• Sincronizar carpeta")
            return
        
        if sync_enabled and not local_folder:
            self._show_styled_message("warning", "Error", "Por favor, selecciona una carpeta local")
            return
            
        # Generar remote_name si es nuevo
        if not is_existing_remote:
            remote_name = f"lxdrive_{name.lower().replace(' ', '_')}"
            
            # Autenticación con rclone
            self._show_styled_message("info", "Autorización", 
                                    f"Se abrirá el navegador para autorizar el acceso a {RemoteType.get_display_name(remote_type)}.\n\n"
                                    "Por favor, completa el proceso en el navegador y vuelve aquí.")
            
            if not self.rclone.create_remote_interactive(remote_name, remote_type):
                self._show_styled_message("error", "Error", "No se pudo crear la cuenta remoto")
                return

        # Crear objeto Account
        import uuid
        account_id = str(uuid.uuid4())[:8]
        
        self.new_account = Account(
            id=account_id,
            name=name,
            remote_name=remote_name,
            remote_type=remote_type_str,
            local_path=local_folder or str(Path.home() / name.replace(" ", "_")),
            remote_path=remote_folder,
            sync_enabled=sync_enabled,
            mount_enabled=mount_enabled,
            mount_point=mount_point,
            sync_direction=SyncDirection.BIDIRECTIONAL
        )
        
        self.accept()


class AccountSettingsDialog(QDialog):
    """Diálogo para configurar una cuenta existente"""
    
    def __init__(self, account: Account, parent=None):
        super().__init__(parent)
        self.account = account
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura la interfaz del diálogo"""
        self.setWindowTitle(f"Configuración - {self.account.name}")
        self.setMinimumSize(450, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit, QComboBox, QSpinBox {
                padding: 8px 12px;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                background-color: #2d2d2d;
                color: white;
            }
            QCheckBox {
                color: white;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        # Título
        title = QLabel(f"⚙️ {self.account.name}")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Configuración de sincronización
        sync_group = QGroupBox("Sincronización")
        sync_layout = QFormLayout(sync_group)
        
        # Habilitar sincronización
        self.sync_enabled = QCheckBox("Sincronización automática activa")
        self.sync_enabled.setChecked(self.account.sync_enabled)
        sync_layout.addRow(self.sync_enabled)
        
        # Dirección
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("↔️ Bidireccional", SyncDirection.BIDIRECTIONAL)
        self.direction_combo.addItem("⬆️ Solo subir", SyncDirection.UPLOAD_ONLY)
        self.direction_combo.addItem("⬇️ Solo descargar", SyncDirection.DOWNLOAD_ONLY)
        
        # Seleccionar el actual
        for i in range(self.direction_combo.count()):
            if self.direction_combo.itemData(i) == self.account.sync_direction:
                self.direction_combo.setCurrentIndex(i)
                break
        
        sync_layout.addRow("Dirección:", self.direction_combo)
        
        # Intervalo
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(60, 3600)
        self.interval_spin.setSuffix(" segundos")
        self.interval_spin.setValue(self.account.sync_interval)
        sync_layout.addRow("Intervalo:", self.interval_spin)
        
        layout.addWidget(sync_group)
        
        # Configuración de montaje
        mount_group = QGroupBox("Montaje como unidad")
        mount_layout = QFormLayout(mount_group)
        
        self.mount_enabled = QCheckBox("Montar como unidad de disco")
        self.mount_enabled.setChecked(self.account.mount_enabled)
        mount_layout.addRow(self.mount_enabled)
        
        self.mount_path = QLineEdit()
        self.mount_path.setText(self.account.mount_point or "")
        self.mount_path.setPlaceholderText("~/CloudDrives/MiCuenta")
        mount_layout.addRow("Punto de montaje:", self.mount_path)
        
        layout.addWidget(mount_group)
        
        layout.addStretch()
        
        # Botones
        btn_layout = QHBoxLayout()
        
        delete_btn = QPushButton("🗑️ Eliminar cuenta")
        delete_btn.setStyleSheet("background-color: #ea4335; color: white; padding: 10px 20px; border-radius: 6px;")
        delete_btn.clicked.connect(self._delete_account)
        btn_layout.addWidget(delete_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setStyleSheet("background-color: #3d3d3d; color: white; padding: 10px 20px; border-radius: 6px;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("💾 Guardar")
        save_btn.setStyleSheet("background-color: #4285f4; color: white; padding: 10px 20px; border-radius: 6px;")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _save_settings(self):
        """Guarda la configuración"""
        self.account.sync_enabled = self.sync_enabled.isChecked()
        self.account.sync_direction = self.direction_combo.currentData()
        self.account.sync_interval = self.interval_spin.value()
        self.account.mount_enabled = self.mount_enabled.isChecked()
        self.account.mount_point = self.mount_path.text().strip() or None
        
        self.accept()
    
    def _delete_account(self):
        """Solicita confirmación para eliminar"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar eliminación")
        msg.setText(f"¿Estás seguro de eliminar la cuenta '{self.account.name}'?\n\n"
                   "Los archivos locales NO serán eliminados.")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e1e;
            }
            QMessageBox QLabel {
                color: #ffffff;
                font-size: 13px;
                min-width: 300px;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                padding: 8px 25px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        
        reply = msg.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            self.done(2)  # Código especial para indicar eliminación


class SyncBridge(QObject):
    """Puente para comunicar el hilo de sync con la UI de forma segura"""
    start_signal = pyqtSignal(str)
    complete_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str, str)
    activity_signal = pyqtSignal(str, str, str, str)

class MainWindow(QMainWindow):
    """Ventana principal de lX Drive"""
    
    def __init__(
        self, 
        rclone: RcloneWrapper,
        account_manager: AccountManager,
        sync_manager: SyncManager,
        mount_manager: MountManager
    ):
        super().__init__()
        
        self.rclone = rclone
        self.account_manager = account_manager
        self.sync_manager = sync_manager
        self.mount_manager = mount_manager
        
        # Puente de señales
        self.bridge = SyncBridge()
        self.bridge.start_signal.connect(self._on_sync_start_ui)
        self.bridge.complete_signal.connect(self._on_sync_complete_ui)
        self.bridge.error_signal.connect(self._on_sync_error_ui)
        self.bridge.activity_signal.connect(self._on_file_activity_ui, Qt.ConnectionType.QueuedConnection)
        
        self._account_widgets: dict = {}  # account_id -> AccountWidget
        
        self._setup_ui()
        self._setup_callbacks()
        self._load_accounts()

        
        # Timer para actualizar estados
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_status)
        self.update_timer.start(5000)  # Cada 5 segundos
    
    def _setup_ui(self):
        """Configura la interfaz de usuario"""
        self.setWindowTitle("lX Drive - Cloud Sync Manager")
        self.setMinimumSize(900, 600)
        
        # Estilo global
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QWidget {
                color: #ffffff;
                font-family: 'Segoe UI', 'Ubuntu', sans-serif;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #4d4d4d;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5d5d5d;
            }
            QStatusBar {
                background-color: #2d2d2d;
                color: #888;
            }
            QComboBox {
                padding: 5px 10px;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                background-color: #2d2d2d;
                color: white;
                min-width: 150px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 25px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #888;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: white;
                selection-background-color: #4285f4;
                selection-color: white;
                border: 1px solid #444;
                outline: none;
                padding: 5px;
            }
            QMessageBox {
                background-color: #1e1e1e;
            }
            QMessageBox QLabel {
                color: white;
            }
            QMessageBox QPushButton {
                background-color: #3d3d3d;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                background-color: #2d2d2d;
                color: white;
            }
            QToolTip {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 4px;
            }
        """)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_v_layout = QVBoxLayout(central_widget)
        main_v_layout.setContentsMargins(0, 0, 0, 0)
        main_v_layout.setSpacing(0)
        
        # Header (fuera del splitter para que siempre esté arriba)
        header = self._create_header()
        main_v_layout.addWidget(header)
        
        # Splitter principal: Lado Izquierdo (Sidebar) | Lado Derecho (Detalle + Actividad)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(1)
        self.main_splitter.setStyleSheet("QSplitter::handle { background-color: #333; }")
        
        # --- 1. SIDEBAR IZQUIERDO: Lista de Cuentas ---
        self.sidebar = QWidget()
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setMaximumWidth(300)
        self.sidebar.setStyleSheet("background-color: #1a1a1a; border-right: 1px solid #333;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)
        
        sidebar_title = QLabel("Nubes")
        sidebar_title.setStyleSheet("color: #888; font-weight: bold; margin-bottom: 10px; font-size: 11px; text-transform: uppercase;")
        sidebar_layout.addWidget(sidebar_title)
        
        # Lista de cuentas (Sidebar)
        self.account_list_widget = QWidget()
        self.account_list_layout = QVBoxLayout(self.account_list_widget)
        self.account_list_layout.setContentsMargins(0, 0, 0, 0)
        self.account_list_layout.setSpacing(5)
        self.account_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setWidget(self.account_list_widget)
        sidebar_scroll.setStyleSheet("border: none; background: transparent;")
        sidebar_layout.addWidget(sidebar_scroll, 1)
        
        # Botón añadir en sidebar
        self.add_account_btn = QPushButton("➕ Añadir Cuenta")
        self.add_account_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                padding: 10px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #4d4d4d; }
        """)
        self.add_account_btn.clicked.connect(self._add_account)
        sidebar_layout.addWidget(self.add_account_btn)
        
        self.main_splitter.addWidget(self.sidebar)
        
        # --- 2. ÁREA CENTRAL: Detalle de Cuenta ---
        self.content_area = QStackedWidget() # Para cambiar entre cuenta y mensaje vacío
        
        # Vista de Cuenta Seleccionada
        self.account_detail_view = QWidget()
        self.detail_layout = QVBoxLayout(self.account_detail_view)
        self.detail_layout.setContentsMargins(30, 30, 30, 30)
        self.detail_layout.setSpacing(20)
        
        # Header de Detalle (Nombre y Tipo)
        self.detail_header = QWidget()
        header_layout = QHBoxLayout(self.detail_header)
        header_layout.setContentsMargins(0,0,0,0)
        
        self.account_name_label = QLabel("Selecciona una cuenta")
        self.account_name_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header_layout.addWidget(self.account_name_label)
        header_layout.addStretch()
        
        # Botón Configuración global de la cuenta
        self.acc_config_btn = QPushButton("⚙ Configuración")
        self.acc_config_btn.setStyleSheet("background-color: #333; color: white; padding: 8px 15px; border-radius: 6px;")
        header_layout.addWidget(self.acc_config_btn)
        
        self.detail_layout.addWidget(self.detail_header)
        
        # Sección de Montaje (Unidad Virtual)
        self.mount_card = QFrame()
        self.mount_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mount_card.setStyleSheet("""
            QFrame { background-color: #252525; border-radius: 10px; border: 1px solid #333; }
            QFrame:hover { background-color: #2a2a2a; border-color: #4285f4; }
        """)
        self.mount_card.mousePressEvent = lambda e: self._show_mount_details()
        
        mount_layout = QHBoxLayout(self.mount_card)
        mount_layout.setContentsMargins(20, 15, 20, 15)
        
        mount_info = QVBoxLayout()
        mount_title = QLabel("📦 Unidad Virtual (VFS)")
        mount_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        mount_info.addWidget(mount_title)
        self.mount_status_label = QLabel("Estado: Desconectado")
        self.mount_status_label.setStyleSheet("color: #888; font-size: 11px;")
        mount_info.addWidget(self.mount_status_label)
        mount_layout.addLayout(mount_info)
        
        mount_layout.addStretch()
        self.mount_toggle_btn = QPushButton("Montar Unidad")
        self.mount_toggle_btn.setFixedSize(140, 35)
        self.mount_toggle_btn.setStyleSheet("""
            QPushButton { background-color: #4285f4; color: white; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #5a9cf5; }
        """)
        mount_layout.addWidget(self.mount_toggle_btn)
        self.detail_layout.addWidget(self.mount_card)
        
        # Sección de Directorios Sincronizados (SyncPairs)
        sync_section_header = QHBoxLayout()
        sync_title = QLabel("📁 Carpetas Sincronizadas")
        sync_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        sync_section_header.addWidget(sync_title)
        sync_section_header.addStretch()
        
        self.add_sync_pair_btn = QPushButton("➕ Añadir Carpeta")
        self.add_sync_pair_btn.setStyleSheet("color: #4285f4; background: transparent; font-weight: bold;")
        sync_section_header.addWidget(self.add_sync_pair_btn)
        self.detail_layout.addLayout(sync_section_header)
        
        # Lista de SyncPairs (Como en tu captura)
        self.sync_pairs_scroll = QScrollArea()
        self.sync_pairs_scroll.setWidgetResizable(True)
        self.sync_pairs_scroll.setStyleSheet("border: none; background: transparent;")
        self.sync_pairs_container = QWidget()
        self.sync_pairs_layout = QVBoxLayout(self.sync_pairs_container)
        self.sync_pairs_layout.setContentsMargins(0, 0, 0, 0)
        self.sync_pairs_layout.setSpacing(10)
        self.sync_pairs_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.sync_pairs_scroll.setWidget(self.sync_pairs_container)
        self.detail_layout.addWidget(self.sync_pairs_scroll, 1)
        
        self.content_area.addWidget(self.account_detail_view)
        
        # Vista vacía (mensaje inicial)
        self.empty_view = QWidget()
        empty_layout = QVBoxLayout(self.empty_view)
        empty_label = QLabel("Bienvenido a lX Drive\n\nSelecciona una cuenta en el sidebar para gestionar tus archivos\no añade una nueva conexión cloud para empezar.")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("color: #555; font-size: 16px;")
        empty_layout.addWidget(empty_label)
        self.content_area.addWidget(self.empty_view)
        self.content_area.setCurrentWidget(self.empty_view)
        
        # --- SPLITTER SECUNDARIO: Detalle | Actividad ---
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setHandleWidth(1)
        self.content_splitter.setStyleSheet("QSplitter::handle { background-color: #333; }")
        self.content_splitter.addWidget(self.content_area)
        
        # Siempre crear el panel de actividad
        from .activity_panel import ActivityPanel
        self.activity_panel = ActivityPanel()
        self.content_splitter.addWidget(self.activity_panel)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 0) # El panel de actividad empieza colapsado o pequeño
        
        # CONEXIONES DE BOTONES DE DETALLE
        self.mount_toggle_btn.clicked.connect(self._mount_account_clicked)
        self.acc_config_btn.clicked.connect(self._edit_account_clicked)
        self.add_sync_pair_btn.clicked.connect(self._add_sync_pair_clicked)

        self.main_splitter.addWidget(self.content_splitter)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        
        main_v_layout.addWidget(self.main_splitter, 1)

        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()
    
    def _create_header(self) -> QWidget:
        """Crea el header de la aplicación"""
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a1a2e, stop:1 #16213e);
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(30, 0, 30, 0)
        
        # Logo y título
        title_layout = QHBoxLayout()
        
        logo_label = QLabel("☁️")
        logo_label.setFont(QFont("Segoe UI", 28))
        title_layout.addWidget(logo_label)
        
        title = QLabel("lX Drive")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        title_layout.addWidget(title)
        
        layout.addLayout(title_layout)
        layout.addStretch()
        
        # Botones de acción
        add_btn = QPushButton("➕ Añadir cuenta")
        add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4285f4, stop:1 #34a853);
                color: white;
                padding: 12px 25px;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5a9cf5, stop:1 #4ab860);
            }
        """)
        add_btn.clicked.connect(self._add_account)
        layout.addWidget(add_btn)
        
        sync_all_btn = QPushButton("🔄 Sincronizar todo")
        sync_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                padding: 12px 25px;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        sync_all_btn.clicked.connect(self._sync_all)
        layout.addWidget(sync_all_btn)
        
        return header
    
    def _setup_callbacks(self):
        """Configura los callbacks del sync manager"""
        self.sync_manager.set_callbacks(
            on_start=self._on_sync_start,
            on_complete=self._on_sync_complete,
            on_error=self._on_sync_error,
            on_file_activity=self._on_file_activity
        )

        
        # Conectar señales del panel de actividad
        if hasattr(self, 'activity_panel'):
            self.activity_panel.pause_requested.connect(self._toggle_all_sync)
    
    def _toggle_all_sync(self):
        """Pausa o reanuda todas las sincronizaciones"""
        # Lógica simple para el botón del panel
        current_running = self.sync_manager.is_running()
        if current_running:
            self.sync_manager.stop()
            self._show_styled_message("info", "Sync", "Sincronización global pausada.")
        else:
            self.sync_manager.start()
            self._show_styled_message("info", "Sync", "Sincronización global reanudada.")

    
    def _load_accounts(self):
        """Carga y muestra las cuentas en el sidebar"""
        # Limpiar widgets existentes del sidebar
        for i in reversed(range(self.account_list_layout.count())):
            widget = self.account_list_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        
        accounts = self.account_manager.get_all()
        
        if not accounts:
            self.content_area.setCurrentWidget(self.empty_view)
            return

        for account in accounts:
            btn = QPushButton(f"  {account.name}")
            # Icono según tipo
            icon = "📁"
            if "google" in account.remote_type.lower(): icon = "🤖"
            elif "dropbox" in account.remote_type.lower(): icon = "📦"
            elif "onedrive" in account.remote_type.lower(): icon = "☁"
            btn.setText(f"{icon}  {account.name}")
            
            btn.setFixedHeight(45)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding-left: 15px;
                    border: none;
                    border-radius: 6px;
                    color: #ccc;
                    font-size: 13px;
                }
                QPushButton:hover { background-color: #2d2d2d; color: white; }
                QPushButton:checked { background-color: #4285f4; color: white; font-weight: bold; }
            """)
            btn.setCheckable(True)
            btn.setProperty("account_id", account.id)
            # Manejar exclusividad manual de botones
            btn.clicked.connect(lambda checked, a=account, b=btn: self._select_account(a, b))
            self.account_list_layout.addWidget(btn)

    def _select_account(self, account, button):
        """Muestra los detalles de la cuenta seleccionada"""
        # Desmarcar otros botones
        for i in range(self.account_list_layout.count()):
            widget = self.account_list_layout.itemAt(i).widget()
            if widget != button and isinstance(widget, QPushButton):
                widget.setChecked(False)
        button.setChecked(True)
        
        self.selected_account = account
        self.content_area.setCurrentWidget(self.account_detail_view)
        
        # Actualizar UI de detalle
        self.account_name_label.setText(account.name)
        self.mount_status_label.setText(f"Estado: {'Montado' if account.mount_enabled else 'Desconectado'}")
        self.mount_toggle_btn.setText("Desmontar" if account.mount_enabled else "Montar Unidad")
        
        # Cargar carpetas sincronizadas
        self._load_sync_pairs(account)
        
    def _select_account_by_id(self, account_id: str):
        """Selecciona una cuenta en el sidebar por su ID"""
        for i in range(self.account_list_layout.count()):
            widget = self.account_list_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton) and widget.property("account_id") == account_id:
                account = self.account_manager.get_by_id(account_id)
                if account:
                    self._select_account(account, widget)
                    break

    def _load_sync_pairs(self, account):
        """Carga la lista de carpetas sincronizadas de la cuenta"""
        # Limpiar lista actual
        for i in reversed(range(self.sync_pairs_layout.count())):
            widget = self.sync_pairs_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            
        if not account.sync_pairs:
            empty = QLabel("No hay carpetas vinculadas. Haz clic en 'Añadir Carpeta' para empezar.")
            empty.setStyleSheet("color: #555; padding: 20px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sync_pairs_layout.addWidget(empty)
            return
            
        for pair in account.sync_pairs:
            pair_widget = QFrame()
            pair_widget.setFixedHeight(75) # Misma altura que la mount_card suele tener con padding
            pair_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            pair_widget.setStyleSheet("""
                QFrame { background-color: #252525; border-radius: 10px; border: 1px solid #333; }
                QFrame:hover { background-color: #2a2a2a; border-color: #34a853; }
            """)
            pair_widget.mousePressEvent = lambda e, p=pair: self._show_sync_pair_details(p)
            
            p_layout = QHBoxLayout(pair_widget)
            p_layout.setContentsMargins(20, 15, 20, 15)
            
            # Info de la carpeta (Izquierda)
            info = QVBoxLayout()
            info.setSpacing(2)
            local_name = Path(pair.local_path).name
            title = QLabel(f"📁 {local_name}")
            title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            title.setStyleSheet("color: #fff;")
            info.addWidget(title)
            
            # Última sincronización o Estado
            last_sync_str = "Nunca"
            if pair.last_sync:
                try:
                    dt = datetime.fromisoformat(pair.last_sync)
                    last_sync_str = dt.strftime("%d/%m/%y %H:%M:%S")
                except: pass
            
            status_text = f"Última: {last_sync_str}"
            status_label = QLabel(status_text)
            status_label.setStyleSheet("color: #888; font-size: 11px;")
            info.addWidget(status_label)
            
            p_layout.addLayout(info, 1)
            p_layout.addStretch()
            
            # Contenedor de acciones (Derecha)
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(10)

            # Botón Sincronizar Manual
            sync_pair_btn = QPushButton("⟳")
            sync_pair_btn.setFixedSize(35, 35)
            sync_pair_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            sync_pair_btn.setToolTip("Sincronizar esta carpeta ahora")
            sync_pair_btn.setStyleSheet("""
                QPushButton { background: #333; color: white; border-radius: 6px; border: none; font-size: 18px; font-weight: bold; }
                QPushButton:hover { background: #444; color: #34a853; }
            """)
            sync_pair_btn.clicked.connect(lambda _, a=account.id, p=pair.id: self.sync_manager.sync_pair_now(a, p))
            actions_layout.addWidget(sync_pair_btn)

            # Botón eliminar par
            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(35, 35)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip("Eliminar vínculo")
            del_btn.setStyleSheet("""
                QPushButton { background: #333; color: #cc6666; border-radius: 6px; border: none; font-size: 16px; }
                QPushButton:hover { background: #444; color: #ff6666; }
            """)
            del_btn.clicked.connect(lambda _, a=account, p=pair: self._remove_sync_pair(a, p))
            actions_layout.addWidget(del_btn)
            
            p_layout.addLayout(actions_layout)
            self.sync_pairs_layout.addWidget(pair_widget)

    def _add_sync_pair_clicked(self):
        """Abre el diálogo para añadir una nueva carpeta de sincronización"""
        if not hasattr(self, 'selected_account'): return
        
        dialog = AddSyncPairDialog(self.rclone, self.selected_account, self)
        if dialog.exec():
            local, remote = dialog.get_data()
            if local and remote:
                from ..core.account_manager import SyncPair
                import uuid
                new_pair = SyncPair(
                    id=str(uuid.uuid4())[:8],
                    local_path=local,
                    remote_path=remote
                )
                self.selected_account.sync_pairs.append(new_pair)
                self.account_manager.update(self.selected_account)
                
                # Cargar en la UI inmediatamente
                self._load_sync_pairs(self.selected_account)
                
                # Notificar al motor de sync para que empiece a trabajar con la nueva carpeta
                self.sync_manager.sync_now(self.selected_account.id)
                
                self.statusBar().showMessage(f"Carpeta añadida y sincronización iniciada", 3000)

    def _remove_sync_pair(self, account, pair):
        """Elimina un vínculo de carpeta"""
        reply = QMessageBox.question(
            self, "Eliminar Carpeta", 
            f"¿Estás seguro de que quieres dejar de sincronizar '{Path(pair.local_path).name}'?\n\nLos archivos no se borrarán de tu PC ni de la nube.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            account.sync_pairs.remove(pair)
            self.account_manager.update(account)
            self._load_sync_pairs(account)
            self.statusBar().showMessage("Carpeta desvinculada", 3000)
    
    def _mount_account_clicked(self):
        """Maneja el clic en el botón de montar/desmontar"""
        if not hasattr(self, 'selected_account'): return
        
        account = self.selected_account
        # Usar is_mounted real en lugar de solo la propiedad del objeto
        is_active = self.mount_manager.is_mounted(account.id)
        
        if is_active:
            # Desmontar
            success, msg = self.mount_manager.unmount(account.id)
            if success:
                self.mount_status_label.setText("Estado: Desconectado")
                self.mount_toggle_btn.setText("Montar Unidad")
                self.statusBar().showMessage(f"Unidad {account.name} desmontada", 3000)
            else:
                QMessageBox.warning(self, "Aviso al desmontar", msg)
        else:
            # Montar
            self.statusBar().showMessage(f"Montando {account.name}...", 0)
            success, msg = self.mount_manager.mount(account.id)
            if success:
                self.mount_status_label.setText(f"Estado: Montado en {account.mount_point or 'N/A'}")
                self.mount_toggle_btn.setText("Desmontar")
                self.statusBar().showMessage(f"Unidad {account.name} montada correctamente", 3000)
            else:
                QMessageBox.critical(self, "Error al montar", msg)
                self.statusBar().showMessage("Error al montar unidad", 3000)

    def _edit_account_clicked(self):
        """Abre el diálogo de configuración de la cuenta seleccionada"""
        if hasattr(self, 'selected_account'):
            self._show_account_settings(self.selected_account.id)
    
    def _add_account_widget(self, account: Account):
        """Añade un widget de cuenta a la lista"""
        widget = AccountWidget(account)
        widget.sync_requested.connect(self._sync_account)
        widget.mount_requested.connect(self._toggle_mount)
        widget.settings_requested.connect(self._show_account_settings)
        
        # Insertar antes del stretch
        self.accounts_layout.insertWidget(
            self.accounts_layout.count() - 1, 
            widget
        )
        
        self._account_widgets[account.id] = widget
    
    def _show_styled_message(self, msg_type: str, title: str, text: str):
        """Muestra un mensaje con estilos oscuros"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        
        if msg_type == "info":
            msg.setIcon(QMessageBox.Icon.Information)
        elif msg_type == "warning":
            msg.setIcon(QMessageBox.Icon.Warning)
        elif msg_type == "error":
            msg.setIcon(QMessageBox.Icon.Critical)
        elif msg_type == "question":
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e1e;
            }
            QMessageBox QLabel {
                color: #ffffff;
                font-size: 13px;
                min-width: 300px;
            }
            QPushButton {
                background-color: #4285f4;
                color: white;
                padding: 8px 25px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a9cf5;
            }
        """)
        
        return msg.exec()
    
    def _add_account(self):
        """Abre el diálogo para añadir cuenta"""
        if not self.rclone.is_installed():
            self._show_styled_message(
                "error",
                "rclone no instalado",
                "rclone no está instalado en el sistema.\n\n"
                "Por favor, instálalo con:\n"
                "curl https://rclone.org/install.sh | sudo bash"
            )
            return
        
        dialog = AddAccountDialog(self.rclone, self)
        
        if dialog.exec() and dialog.new_account:
            # Añadir al manager
            if self.account_manager.add(dialog.new_account):
                self._load_accounts()
                self._select_account_by_id(dialog.new_account.id)
                self._update_status_bar()
                
                self.statusBar().showMessage(f"Cuenta '{dialog.new_account.name}' añadida", 3000)
    
    def _sync_account(self, account_id: str):
        """Sincroniza una cuenta específica"""
        self.sync_manager.sync_now(account_id)
    
    def _sync_all(self):
        """Sincroniza todas las cuentas"""
        for account in self.account_manager.get_enabled_accounts():
            # Solo notificar si no está ya trabajando
            if account.status != SyncStatus.SYNCING:
                self._on_file_activity(account.id, "Sincronización Total", "sync_start", "Iniciando proceso para todos los pares")
                self.sync_manager.sync_now(account.id)
    
    def _toggle_mount(self, account_id: str):
        """Alterna el montaje de una cuenta"""
        if self.mount_manager.is_mounted(account_id):
            self.mount_manager.unmount(account_id)
        else:
            self.mount_manager.mount(account_id)
        
        # Actualizar widget
        account = self.account_manager.get_by_id(account_id)
        if account and account_id in self._account_widgets:
            self._account_widgets[account_id].update_account(account)
    
    def _show_account_settings(self, account_id: str):
        """Muestra el diálogo de configuración de cuenta"""
        account = self.account_manager.get_by_id(account_id)
        if not account:
            return
        
        dialog = AccountSettingsDialog(account, self)
        result = dialog.exec()
        
        if result == 1:  # Aceptado - guardar cambios
            self.account_manager.update(dialog.account)
            # Refrescar UI completa para reflejar posibles cambios de nombre
            self._load_accounts()
            self._select_account_by_id(account_id)
            self.statusBar().showMessage("Configuración guardada", 3000)
        elif result == 2:  # Eliminar
            self._delete_account(account_id)
    
    def _delete_account(self, account_id: str):
        """Elimina una cuenta"""
        # Desmontar si está montada
        if self.mount_manager.is_mounted(account_id):
            self.mount_manager.unmount(account_id)
        
        # Obtener info antes de eliminar
        account = self.account_manager.get_by_id(account_id)
        
        # Eliminar de rclone
        if account:
            self.rclone.delete_remote(account.remote_name)
        
        # Eliminar del manager
        self.account_manager.delete(account_id)
        
        # Recargar sidebar y mostrar vista vacía
        self._load_accounts()
        self.content_area.setCurrentWidget(self.empty_view)
        
        self._update_status_bar()
        self.statusBar().showMessage("Cuenta eliminada correctamente", 3000)
    
    def _setup_callbacks(self):
        """Configura los callbacks (gestionados centralmente por LXDriveApp)"""
        # Conectar señales del panel de actividad
        if hasattr(self, 'activity_panel'):
            self.activity_panel.pause_requested.connect(self._toggle_all_sync)
    
    def _toggle_all_sync(self):
        """Pausa o reanuda todas las sincronizaciones"""
        current_running = self.sync_manager.is_running()
        if current_running:
            self.sync_manager.stop()
            self._show_styled_message("info", "Sync", "Sincronización global pausada.")
        else:
            self.sync_manager.start()
            self._show_styled_message("info", "Sync", "Sincronización global reanudada.")

    # --- Métodos que se ejecutan en el HILO DE UI (Slots) ---

    def _on_sync_start_ui(self, account_id: str):
        """Manejador de señal para inicio de sync"""
        # Actualizar widget si existe
        if account_id in self._account_widgets:
            account = self.account_manager.get_by_id(account_id)
            if account:
                self._account_widgets[account_id].update_account(account)

    def _on_sync_complete_ui(self, task):
        """Manejador de señal para sync completada"""
        if task.account_id in self._account_widgets:
            account = self.account_manager.get_by_id(task.account_id)
            if account:
                self._account_widgets[task.account_id].update_account(account)

    def _on_sync_error_ui(self, account_id: str, message: str):
        """Manejador de señal para error de sync"""
        if hasattr(self, 'activity_panel'):
            from .activity_panel import FileActivity, FileAction
            self.activity_panel.add_activity(FileActivity(
                path="Error", name="Sincronización Interrumpida", action=FileAction.ERROR,
                error_message=message, account_name="Sistema"
            ), is_mount=False)

    def _on_file_activity_ui(self, account_id: str, name: str, action_str: str, path: str):
        """Manejador de señal para actividad de archivos (HILO SEGURO)"""
        # AQUÍ ESTABA EL ERROR: Llamar al proceso visual, NO volver a emitir la señal
        self._on_file_activity(account_id, name, action_str, path)

    def _show_mount_details(self):
        """Muestra detalles del montaje en un modal"""
        from PyQt6.QtWidgets import QMessageBox

        if not self.selected_account: return
        acc = self.selected_account
        
        status = "Montado" if acc.mount_enabled else "Desconectado"
        mount_point = acc.mount_point or "No asignado"
        remote = f"{acc.remote_name}:"
        
        msg = f"<b>Estado:</b> {status}<br><br>"
        msg += f"<b>Punto de Montaje:</b><br><code style='color: #4285f4;'>{mount_point}</code><br><br>"
        msg += f"<b>Origen Remoto:</b><br><code style='color: #34a853;'>{remote}</code><br><br>"
        msg += "<i>La unidad virtual te permite navegar por tus archivos de Google Drive como si estuvieran en tu PC sin ocupar espacio.</i>"
        
        box = QMessageBox(self)
        box.setWindowTitle(f"Detalles: Unidad Virtual - {acc.name}")
        box.setText(msg)
        box.setStyleSheet(self.styleSheet()) # Reusar el estilo global
        box.exec()

    def _show_sync_pair_details(self, pair):
        """Muestra detalles de una carpeta sincronizada en un modal"""
        from PyQt6.QtWidgets import QMessageBox

        if not self.selected_account: return
        acc = self.selected_account
        
        last_sync = pair.last_sync or "Nunca"
        if last_sync != "Nunca":
            try:
                dt = datetime.fromisoformat(last_sync)
                last_sync = dt.strftime("%A, %d de %B %Y - %H:%M:%S")
            except: pass

        msg = f"<b>Nombre:</b> {Path(pair.local_path).name}<br><br>"
        msg += f"<b>Ruta Local:</b><br><code style='color: #4285f4;'>{pair.local_path}</code><br><br>"
        msg += f"<b>Ruta Remota:</b><br><code style='color: #34a853;'>{acc.remote_name}:{pair.remote_path}</code><br><br>"
        msg += f"<b>Última Sincronización:</b><br>{last_sync}<br><br>"
        msg += "<i>Esta carpeta se mantiene sincronizada bidireccionalmente. Cualquier cambio en un lado se reflejará en el otro.</i>"
        
        box = QMessageBox(self)
        box.setWindowTitle(f"Detalles: Carpeta Sincronizada")
        box.setText(msg)
        box.setStyleSheet(self.styleSheet())
        box.exec()

    def _on_file_activity(self, account_id: str, name: str, action_str: str, path: str):
        """Implementación de actividad de archivos clasificada por pestañas"""
        print(f"DEBUG: Actividad recibida -> {name} | {action_str} | {path}")
        if hasattr(self, 'activity_panel'):
            from .activity_panel import FileActivity, FileAction
            
            action = FileAction.SYNCED
            error_msg = None
            is_mount_activity = False
            
            # 1. Determinar si es actividad de Mount (VFS) o de Sync (Carpetas)
            is_mount_activity = False
            if action_str in ["vfs_open", "vfs_read", "vfs_write"]:
                is_mount_activity = True
            elif action_str == "mounted" and name == "Unidad Virtual":
                is_mount_activity = True

            error_msg = ""
            # 2. Mapear acción a Enum
            if action_str in ["uploading", "uploaded", "vfs_write"]: 
                action = FileAction.UPLOADING
            elif action_str in ["downloading", "downloaded", "vfs_read"]: 
                action = FileAction.DOWNLOADING
            elif action_str == "mounted":
                action = FileAction.MOUNTED
                name = "Unidad Virtual"
                path = "Montaje exitoso"
            elif action_str == "sync_start":
                action = FileAction.SYNCED
                path = "Revisando cambios..."
            elif action_str == "sync_progress":
                action = FileAction.SYNCED
            elif action_str == "deleted":
                action = FileAction.DELETED
            elif action_str == "moved":
                action = FileAction.MOVED
            elif action_str == "error": 
                action = FileAction.ERROR
                error_msg = path 
            else:
                action = FileAction.SYNCED # Por defecto
            
            account = self.account_manager.get_by_id(account_id)
            acc_name = account.name if account else "Sistema"
            
            # 3. Añadir a la pestaña correcta
            self.activity_panel.add_activity(FileActivity(
                path=path, 
                name=name, 
                action=action, 
                account_name=acc_name,
                error_message=error_msg
            ), is_mount=is_mount_activity)


    def _update_status(self):
        """Actualiza el estado de las cuentas periódicamente"""
        for account_id, widget in self._account_widgets.items():
            account = self.account_manager.get_by_id(account_id)
            if account:
                widget.update_account(account)
    
    def _update_status_bar(self):
        """Actualiza la barra de estado"""
        accounts = self.account_manager.get_all()
        rclone_status = "✓ rclone instalado" if self.rclone.is_installed() else "✗ rclone no instalado"
        
        self.status_bar.showMessage(
            f"{len(accounts)} cuenta(s) configurada(s) | {rclone_status}"
        )
    
    def closeEvent(self, event):
        """Maneja el cierre de la ventana"""
        # Crear diálogo de cierre personalizado con estilos
        msg = QMessageBox(self)
        msg.setWindowTitle("Cerrar lX Drive")
        msg.setText("¿Qué deseas hacer?")
        msg.setIcon(QMessageBox.Icon.Question)
        
        # Botones personalizados
        minimize_btn = msg.addButton("Minimizar a bandeja", QMessageBox.ButtonRole.RejectRole)
        close_btn = msg.addButton("Cerrar aplicación", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e1e;
            }
            QMessageBox QLabel {
                color: #ffffff;
                font-size: 13px;
                min-width: 350px;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        
        # Estilizar el botón de cerrar de forma diferente
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ea4335;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f55a4e;
            }
        """)
        
        msg.exec()
        
        clicked = msg.clickedButton()
        
        if clicked == close_btn:
            # Desmontar todas las unidades
            self.mount_manager.unmount_all()
            # Detener sincronización
            self.sync_manager.stop()
            event.accept()
        elif clicked == minimize_btn:
            # Solo ocultar la ventana
            self.hide()
            event.ignore()
        else:
            event.ignore()

