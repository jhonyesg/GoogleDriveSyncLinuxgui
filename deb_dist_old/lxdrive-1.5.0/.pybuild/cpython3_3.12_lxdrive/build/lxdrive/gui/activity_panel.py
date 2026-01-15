"""
ActivityPanel - Panel de actividad mejorado con soporte por cuenta

Muestra la actividad de sincronización y VFS filtrada por la cuenta seleccionada.
Usa el nuevo ActivityLogManager para registros persistentes.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QPushButton, QFrame, QProgressBar,
    QTabWidget, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
from pathlib import Path

# Mantener compatibilidad con código existente
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
    """Clase de compatibilidad con código existente"""
    def __init__(self, path: str, name: str, action: FileAction, 
                 progress: float = 0.0, timestamp: Optional[datetime] = None,
                 account_name: str = "", error_message: str = "",
                 account_id: str = "", sync_pair_id: str = ""):
        self.path = path
        self.name = name
        self.action = action
        self.progress = progress
        self.timestamp = timestamp or datetime.now()
        self.account_name = account_name
        self.account_id = account_id
        self.error_message = error_message
        self.sync_pair_id = sync_pair_id


class FileActivityWidget(QFrame):
    """Widget para mostrar una actividad individual"""
    
    def __init__(self, activity, parent=None):
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
        
        # Determinar icono según tipo de activity
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Soportar tanto FileActivity como ActivityEntry
        if hasattr(self.activity, 'get_icon'):
            icon_label.setText(self.activity.get_icon())
        else:
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
            icon_label.setText(icon_map.get(self.activity.action, "��"))
        
        icon_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(icon_label)
        
        # Textos
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        name_label = QLabel(self.activity.name)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #efefef;")
        text_layout.addWidget(name_label)
        
        # Obtener texto de acción
        if hasattr(self.activity, 'get_action_text'):
            action_text = self.activity.get_action_text()
        else:
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
        
        # Error message
        error_msg = getattr(self.activity, 'error_message', '')
        if error_msg:
            action_text = f"Error: {error_msg}"
        
        # Timestamp
        if hasattr(self.activity, 'timestamp'):
            ts = self.activity.timestamp
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except:
                    ts = datetime.now()
            time_str = ts.strftime('%H:%M:%S')
        else:
            time_str = datetime.now().strftime('%H:%M:%S')
        
        # Determinar si es error
        is_error = False
        if hasattr(self.activity, 'action'):
            if isinstance(self.activity.action, str):
                is_error = self.activity.action == 'error'
            else:
                is_error = self.activity.action == FileAction.ERROR
        
        detail_label = QLabel(f"{action_text} • {time_str}")
        detail_label.setStyleSheet(f"color: {'#ff6b6b' if is_error else '#888'}; font-size: 10px;")
        text_layout.addWidget(detail_label)
        
        layout.addLayout(text_layout, 1)
        
        # Barra de progreso para subidas/descargas
        action_val = self.activity.action
        if isinstance(action_val, str):
            show_progress = action_val in ['uploading', 'downloading']
        else:
            show_progress = action_val in [FileAction.UPLOADING, FileAction.DOWNLOADING]
        
        if show_progress:
            progress = getattr(self.activity, 'progress', 0.0)
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(progress))
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
        
        # Obtener valores
        name = self.activity.name
        path = getattr(self.activity, 'path', '')
        action = self.activity.action
        if isinstance(action, str):
            status_text = action.upper()
        else:
            status_text = action.value.upper()
        
        if 'error' in status_text.lower():
            status_text = "❌ ERROR"
        
        timestamp = getattr(self.activity, 'timestamp', datetime.now())
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except:
                timestamp = datetime.now()
        
        detail = f"""
        <b>Archivo:</b> {name}<br>
        <b>Ruta:</b> {path}<br>
        <b>Estado:</b> {status_text}<br>
        <b>Hora:</b> {timestamp.strftime('%Y-%m-%d %H:%M:%S')}<br>
        """
        
        error_message = getattr(self.activity, 'error_message', '')
        if error_message:
            detail += f"<br><b style='color:red;'>Mensaje de error:</b><br>{error_message}"
            
        msg.setText(detail)
        msg.setStyleSheet("""
            QMessageBox { background-color: #1e1e1e; }
            QLabel { color: #ccc; font-size: 13px; }
            QPushButton { background-color: #3d3d3d; color: white; border: none; padding: 6px 15px; border-radius: 4px; }
            QPushButton:hover { background-color: #4a4a4a; }
        """)
        msg.exec()
        super().mousePressEvent(event)


class ActivityPanel(QWidget):
    """
    Panel de actividad mejorado que muestra registros por cuenta.
    Soporta persistencia y filtrado por cuenta seleccionada.
    """
    
    pause_requested = pyqtSignal()
    account_changed = pyqtSignal(str)  # Emite account_id cuando cambia la cuenta

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_account_id: Optional[str] = None
        self._account_names: Dict[str, str] = {}  # account_id -> nombre
        self._activity_manager = None
        self._setup_ui()
        
        # Timer para refrescar (solo si hay cambios pendientes)
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_activities)
        self._refresh_timer.start(5000)  # Refrescar cada 5 segundos (menos frecuente)

    def _setup_ui(self):
        self.setMinimumWidth(320)
        self.setStyleSheet("background-color: #1e1e1e; border-left: 1px solid #333;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header con selector de cuenta
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("background-color: #252525; border-bottom: 1px solid #333;")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(10, 8, 10, 8)
        
        title = QLabel("ACTIVIDAD RECIENTE")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #aaa; letter-spacing: 1px;")
        h_layout.addWidget(title)
        
        # Selector de cuenta
        self.account_selector = QComboBox()
        self.account_selector.setStyleSheet("""
            QComboBox {
                background-color: #333;
                color: #fff;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #888;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #333;
                color: #fff;
                selection-background-color: #4285f4;
            }
        """)
        self.account_selector.currentIndexChanged.connect(self._on_account_changed)
        h_layout.addWidget(self.account_selector)
        
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
        self.tabs.addTab(self.sync_scroll, "📁 CARPETAS")
        
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
        self.tabs.addTab(self.mount_scroll, "💿 UNIDAD VFS")
        
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
        
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #666; font-size: 10px;")
        s_layout.addWidget(self.stats_label)
        
        s_layout.addStretch()
        
        clear_btn = QPushButton("Limpiar")
        clear_btn.setStyleSheet("color: #666; font-size: 10px; background: transparent;")
        clear_btn.clicked.connect(self._clear_current_account)
        s_layout.addWidget(clear_btn)
        
        main_layout.addWidget(stats)

    def set_activity_manager(self, manager):
        """Configura el ActivityLogManager a usar"""
        self._activity_manager = manager
        if manager:
            manager.register_global_callback(self._on_activity_update)
    
    def set_accounts(self, accounts: List):
        """Configura las cuentas disponibles"""
        self.account_selector.blockSignals(True)
        self.account_selector.clear()
        self._account_names.clear()
        
        for account in accounts:
            self._account_names[account.id] = account.name
            self.account_selector.addItem(account.name, account.id)
        
        self.account_selector.blockSignals(False)
        
        # Seleccionar primera cuenta si hay
        if accounts and not self._current_account_id:
            self.set_current_account(accounts[0].id)
    
    def set_current_account(self, account_id: str, emit_signal: bool = False):
        """
        Establece la cuenta actual a mostrar.
        
        Args:
            account_id: ID de la cuenta
            emit_signal: Si emitir señal account_changed (False por defecto para evitar recursión)
        """
        if self._current_account_id == account_id:
            return  # Sin cambio
        
        self._current_account_id = account_id
        
        # Actualizar selector
        for i in range(self.account_selector.count()):
            if self.account_selector.itemData(i) == account_id:
                self.account_selector.blockSignals(True)
                self.account_selector.setCurrentIndex(i)
                self.account_selector.blockSignals(False)
                break
        
        self._refresh_activities()
        
        # Solo emitir señal si se solicita explícitamente
        if emit_signal:
            self.account_changed.emit(account_id)
    
    def _on_account_changed(self, index: int):
        """Handler cuando cambia la selección de cuenta por el usuario"""
        account_id = self.account_selector.itemData(index)
        if account_id and account_id != self._current_account_id:
            self._current_account_id = account_id
            self._refresh_activities()
            # El usuario cambió la cuenta, emitir señal
            self.account_changed.emit(account_id)
    
    def _on_activity_update(self, account_id: str):
        """Callback cuando hay nueva actividad"""
        if account_id == self._current_account_id:
            # Usar QTimer.singleShot para no bloquear el hilo que llama
            QTimer.singleShot(0, self._refresh_activities)
    
    def _refresh_activities(self):
        """Refresca las actividades mostradas de forma incremental"""
        if not self._current_account_id or not self._activity_manager:
            return
        
        try:
            # Obtener actividades de la cuenta actual
            sync_activities = self._activity_manager.get_sync_activities(
                self._current_account_id, limit=50  # Reducir límite para mejor rendimiento
            )
            vfs_activities = self._activity_manager.get_vfs_activities(
                self._current_account_id, limit=50
            )
            
            # Actualizar sync tab de forma incremental
            self._update_activity_list(
                self.sync_layout, 
                self.sync_empty, 
                sync_activities,
                "sync"
            )
            
            # Actualizar vfs tab de forma incremental
            self._update_activity_list(
                self.mount_layout, 
                self.mount_empty, 
                vfs_activities,
                "vfs"
            )
            
            # Actualizar estadísticas
            self.stats_label.setText(f"Sync: {len(sync_activities)} | VFS: {len(vfs_activities)}")
            
        except Exception as e:
            # No bloquear la UI si hay un error
            pass
    
    def _update_activity_list(self, layout, empty_label, activities, tab_type: str):
        """
        Actualiza una lista de actividades de forma incremental.
        Solo recrea widgets si cambiaron los datos.
        """
        # Obtener widgets actuales (excluyendo el label vacío)
        current_widgets = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget and isinstance(widget, FileActivityWidget):
                    current_widgets.append(widget)
        
        # Crear identificadores únicos para las actividades actuales
        current_ids = set()
        for w in current_widgets:
            activity = w.activity
            ts = getattr(activity, 'timestamp', '')
            if isinstance(ts, str):
                current_ids.add(f"{activity.name}_{ts}")
            else:
                current_ids.add(f"{activity.name}_{ts.isoformat() if ts else ''}")
        
        # Crear identificadores para las nuevas actividades
        new_ids = set()
        for activity in activities:
            ts = activity.timestamp if hasattr(activity, 'timestamp') else ''
            if isinstance(ts, str):
                new_ids.add(f"{activity.name}_{ts}")
            else:
                new_ids.add(f"{activity.name}_{ts.isoformat() if ts else ''}")
        
        # Solo actualizar si hay cambios
        if current_ids == new_ids and len(current_widgets) == len(activities):
            return
        
        # Limpiar y reconstruir solo si cambió
        self._clear_layout(layout, keep_empty=True)
        
        if activities:
            empty_label.hide()
            # Limitar la cantidad de widgets creados de una vez
            for activity in activities[:50]:
                widget = FileActivityWidget(activity)
                layout.insertWidget(layout.count() - 1, widget)
        else:
            empty_label.show()
    
    def _clear_layout(self, layout, keep_empty: bool = False):
        """Limpia un layout manteniendo opcionalmente el label empty"""
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    if keep_empty and isinstance(widget, QLabel) and "Sin actividad" in widget.text():
                        continue
                    widget.deleteLater()
    
    def _clear_current_account(self):
        """Limpia las actividades de la cuenta actual"""
        if self._current_account_id and self._activity_manager:
            self._activity_manager.clear_account(self._current_account_id)
            self._refresh_activities()

    # --- Métodos de compatibilidad con código existente ---
    
    def add_activity(self, activity: FileActivity, is_mount: bool = False):
        """
        Método de compatibilidad para añadir actividad.
        Convierte FileActivity al nuevo sistema.
        """
        if not self._activity_manager:
            return
        
        from ..utils.activity_log import ActivityType, ActivityAction
        
        # Mapear FileAction a ActivityAction
        action_map = {
            FileAction.UPLOADING: ActivityAction.UPLOADING,
            FileAction.DOWNLOADING: ActivityAction.DOWNLOADING,
            FileAction.SYNCED: ActivityAction.SYNCED,
            FileAction.CONFLICT: ActivityAction.CONFLICT,
            FileAction.ERROR: ActivityAction.ERROR,
            FileAction.MOUNTED: ActivityAction.MOUNTED,
            FileAction.DELETED: ActivityAction.DELETED,
            FileAction.MOVED: ActivityAction.MOVED,
        }
        
        activity_type = ActivityType.VFS if is_mount else ActivityType.SYNC
        action = action_map.get(activity.action, ActivityAction.SYNCED)
        
        # Determinar account_id
        account_id = activity.account_id or self._current_account_id
        if not account_id:
            return
        
        self._activity_manager.add_activity(
            account_id=account_id,
            activity_type=activity_type,
            action=action,
            name=activity.name,
            path=activity.path,
            progress=activity.progress,
            error_message=activity.error_message,
            sync_pair_id=getattr(activity, 'sync_pair_id', '')
        )

    def clear_all(self):
        """Limpia todas las actividades de la cuenta actual"""
        self._clear_current_account()
