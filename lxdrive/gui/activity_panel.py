from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QPushButton, QFrame, QProgressBar,
    QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
from pathlib import Path

class FileAction(Enum):
    UPLOADING = "uploading"
    DOWNLOADING = "downloading"
    SYNCED = "synced"
    CONFLICT = "conflict"
    ERROR = "error"
    MOUNTED = "mounted"
    DELETED = "deleted"
    MOVED = "moved"

class FileActivity:
    def __init__(self, path: str, name: str, action: FileAction, 
                 progress: float = 0.0, timestamp: Optional[datetime] = None,
                 account_name: str = "", error_message: str = ""):
        self.path = path
        self.name = name
        self.action = action
        self.progress = progress
        self.timestamp = timestamp or datetime.now()
        self.account_name = account_name
        self.error_message = error_message

class FileActivityWidget(QFrame):
    def __init__(self, activity: FileActivity, parent=None):
        super().__init__(parent)
        self.activity = activity
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(65)
        self.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-radius: 8px;
                margin-bottom: 2px;
            }
            QFrame:hover {
                background-color: #323232;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Icono según acción
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_map = {
            FileAction.UPLOADING: "📤",
            FileAction.DOWNLOADING: "📥",
            FileAction.SYNCED: "✅",
            FileAction.CONFLICT: "⚠️",
            FileAction.ERROR: "❌",
            FileAction.MOUNTED: "📦",
            FileAction.DELETED: "🗑️",
            FileAction.MOVED: "🔄"
        }
        icon_label.setText(icon_map.get(self.activity.action, "📄"))
        icon_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(icon_label)
        
        # Textos
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        name_label = QLabel(self.activity.name)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #efefef;")
        text_layout.addWidget(name_label)
        
        action_text = {
            FileAction.UPLOADING: "Subiendo...",
            FileAction.DOWNLOADING: "Descargando...",
            FileAction.SYNCED: "Sincronizado",
            FileAction.CONFLICT: "Conflicto",
            FileAction.ERROR: "Error",
            FileAction.MOUNTED: "Unidad conectada",
            FileAction.DELETED: "Eliminado",
            FileAction.MOVED: "Renombrado/Movido"
        }.get(self.activity.action, "")
        
        if self.activity.action == FileAction.ERROR and self.activity.error_message:
            action_text = f"Error: {self.activity.error_message}"
        
        detail_label = QLabel(f"{action_text} • {self.activity.timestamp.strftime('%H:%M:%S')}")
        detail_label.setStyleSheet(f"color: {'#ff6b6b' if self.activity.action == FileAction.ERROR else '#888'}; font-size: 10px;")
        text_layout.addWidget(detail_label)
        
        layout.addLayout(text_layout, 1)
        
        # Barra de progreso para subidas/descargas
        if self.activity.action in [FileAction.UPLOADING, FileAction.DOWNLOADING]:
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(self.activity.progress))
            self.progress_bar.setFixedHeight(4)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setStyleSheet("""
                QProgressBar { background-color: #1a1a1a; border: none; border-radius: 2px; }
                QProgressBar::chunk { background-color: #4285f4; border-radius: 2px; }
            """)
            text_layout.insertWidget(1, self.progress_bar)

    def mousePressEvent(self, event):
        """Muestra un modal con los detalles de la actividad"""
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Detalle de Actividad")
        
        status_text = self.activity.action.value.upper()
        if self.activity.action == FileAction.ERROR:
            status_text = "❌ ERROR"
        
        detail = f"""
        <b>Archivo:</b> {self.activity.name}<br>
        <b>Ruta:</b> {self.activity.path}<br>
        <b>Estado:</b> {status_text}<br>
        <b>Hora:</b> {self.activity.timestamp.strftime('%Y-%m-%d %H:%M:%S')}<br>
        """
        
        if self.activity.error_message:
            detail += f"<br><b style='color:red;'>Mensaje de error:</b><br>{self.activity.error_message}"
            
        msg.setText(detail)
        # Aplicar estilo oscuro al modal de detalle
        msg.setStyleSheet("""
            QMessageBox { background-color: #1e1e1e; }
            QLabel { color: #ccc; font-size: 13px; }
            QPushButton { background-color: #3d3d3d; color: white; border: none; padding: 6px 15px; border-radius: 4px; }
            QPushButton:hover { background-color: #4a4a4a; }
        """)
        msg.exec()
        super().mousePressEvent(event)

class ActivityPanel(QWidget):
    pause_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(320)
        self.setStyleSheet("background-color: #1e1e1e; border-left: 1px solid #333;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet("background-color: #252525; border-bottom: 1px solid #333;")
        h_layout = QHBoxLayout(header)
        
        title = QLabel("ACTIVIDAD RECIENTE")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #aaa; letter-spacing: 1px;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        
        main_layout.addWidget(header)
        
        # Sistema de pestañas
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #1e1e1e; }
            QTabBar::tab {
                background: #252525;
                color: #888;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 11px;
                border: none;
            }
            QTabBar::tab:selected {
                background: #1e1e1e;
                color: #4285f4;
                border-bottom: 2px solid #4285f4;
            }
        """)
        
        # Pestaña 1: Sincronización (Carpetas)
        self.sync_scroll = QScrollArea()
        self.sync_scroll.setWidgetResizable(True)
        self.sync_scroll.setStyleSheet("border: none; background: transparent;")
        self.sync_container = QWidget()
        self.sync_layout = QVBoxLayout(self.sync_container)
        self.sync_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.sync_layout.setContentsMargins(10, 10, 10, 10)
        self.sync_layout.setSpacing(8)
        
        self.sync_empty = QLabel("Sin actividad de sincronización")
        self.sync_empty.setStyleSheet("color: #555; padding-top: 40px;")
        self.sync_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sync_layout.addWidget(self.sync_empty)
        
        self.sync_scroll.setWidget(self.sync_container)
        self.tabs.addTab(self.sync_scroll, "� CARPETAS")
        
        # Pestaña 2: Unidad Virtual (VFS)
        self.mount_scroll = QScrollArea()
        self.mount_scroll.setWidgetResizable(True)
        self.mount_scroll.setStyleSheet("border: none; background: transparent;")
        self.mount_container = QWidget()
        self.mount_layout = QVBoxLayout(self.mount_container)
        self.mount_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.mount_layout.setContentsMargins(10, 10, 10, 10)
        self.mount_layout.setSpacing(8)
        
        self.mount_empty = QLabel("Sin actividad en la unidad virtual")
        self.mount_empty.setStyleSheet("color: #555; padding-top: 40px;")
        self.mount_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mount_layout.addWidget(self.mount_empty)
        
        self.mount_scroll.setWidget(self.mount_container)
        self.tabs.addTab(self.mount_scroll, "� UNIDAD VFS")
        
        main_layout.addWidget(self.tabs)
        
        # Footer / Stats
        stats = QFrame()
        stats.setFixedHeight(40)
        stats.setStyleSheet("background-color: #1a1a1a; border-top: 1px solid #333;")
        s_layout = QHBoxLayout(stats)
        s_layout.setContentsMargins(15, 0, 15, 0)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #34a853; font-size: 18px;")
        s_layout.addWidget(self.status_dot)
        
        self.status_text = QLabel("Sistema en línea")
        self.status_text.setStyleSheet("color: #888; font-size: 11px;")
        s_layout.addWidget(self.status_text)
        s_layout.addStretch()
        
        clear_btn = QPushButton("Limpiar Todo")
        clear_btn.setStyleSheet("color: #666; font-size: 10px; background: transparent;")
        clear_btn.clicked.connect(self.clear_all)
        s_layout.addWidget(clear_btn)
        
        main_layout.addWidget(stats)

    def add_activity(self, activity: FileActivity, is_mount: bool = False):
        """Añade actividad con deduplicación y límite de 100"""
        from PyQt6 import sip
        target_layout = self.mount_layout if is_mount else self.sync_layout
        target_empty = self.mount_empty if is_mount else self.sync_empty
        
        if sip.isdeleted(target_empty): return

        if target_empty.isVisible():
            target_empty.hide()
        
        # 1. DEDUPLICACIÓN: Buscar si ya existe este archivo (por path)
        for i in range(target_layout.count()):
            item = target_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                try:
                    if hasattr(w, 'activity') and w.activity.path == activity.path:
                        # Si es el mismo archivo, lo movemos arriba y actualizamos
                        target_layout.removeWidget(w)
                        target_layout.insertWidget(0, w)
                        w.activity.timestamp = activity.timestamp
                        return
                except: continue

        # 2. Crear widget nuevo
        widget = FileActivityWidget(activity)
        target_layout.insertWidget(0, widget)
        
        # 3. Límite de 100
        while target_layout.count() > 100:
            item = target_layout.takeAt(target_layout.count() - 1)
            if item and item.widget():
                item.widget().deleteLater()

    def clear_all(self):
        """Limpia ambas pestañas"""
        for layout in [self.sync_layout, self.mount_layout]:
            for i in reversed(range(layout.count())):
                widget = layout.itemAt(i).widget()
                if widget and not isinstance(widget, QLabel):
                    widget.deleteLater()
        
        self.sync_empty.show()
        self.mount_empty.show()
