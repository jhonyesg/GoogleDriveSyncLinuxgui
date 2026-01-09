#!/usr/bin/env python3
"""
TrayIcon - Icono de bandeja del sistema

Permite controlar lX Drive desde la bandeja del sistema.
"""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PyQt6.QtCore import pyqtSignal, QObject
from typing import Optional, Callable
from loguru import logger

from ..core import AccountManager, SyncManager, MountManager
from ..core.account_manager import Account, SyncStatus


class TrayIcon(QSystemTrayIcon):
    """
    Icono de bandeja del sistema para lX Drive.
    
    Proporciona acceso rápido a:
    - Estado de sincronización
    - Sincronizar todo
    - Pausar/Reanudar
    - Abrir ventana principal
    - Salir
    """
    
    # Señales
    show_main_window = pyqtSignal()
    quit_app = pyqtSignal()
    
    def __init__(
        self,
        account_manager: AccountManager,
        sync_manager: SyncManager,
        mount_manager: MountManager,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        
        self.account_manager = account_manager
        self.sync_manager = sync_manager
        self.mount_manager = mount_manager
        
        self._setup_icon()
        self._setup_menu()
        self._connect_signals()
        
        self.show()
    
    def _setup_icon(self):
        """Configura el icono de la bandeja"""
        # Crear un icono simple programáticamente
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparente
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fondo circular
        painter.setBrush(QColor(66, 133, 244))  # Azul Google
        painter.setPen(QColor(52, 168, 83))  # Verde Google
        painter.drawEllipse(4, 4, 56, 56)
        
        # Texto "lX"
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 20, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), 0x0084, "lX")  # AlignCenter
        
        painter.end()
        
        icon = QIcon(pixmap)
        self.setIcon(icon)
        self.setToolTip("lX Drive - Cloud Sync")
    
    def _setup_menu(self):
        """Configura el menú contextual"""
        menu = QMenu()
        
        # Estilo del menú
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                color: #ffffff;
                padding: 8px 30px 8px 15px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4285f4;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3d3d3d;
                margin: 5px 10px;
            }
        """)
        
        # Título/Estado
        self.status_action = QAction("lX Drive - Sincronizado", self)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        
        menu.addSeparator()
        
        # Sincronizar todo
        sync_action = QAction("🔄 Sincronizar todo", self)
        sync_action.triggered.connect(self._sync_all)
        menu.addAction(sync_action)
        
        # Pausar/Reanudar
        self.pause_action = QAction("⏸ Pausar sincronización", self)
        self.pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self.pause_action)
        
        menu.addSeparator()
        
        # Submenú de cuentas
        self.accounts_menu = menu.addMenu("📂 Cuentas")
        self._update_accounts_menu()
        
        menu.addSeparator()
        
        # Abrir ventana principal
        open_action = QAction("🖥️ Abrir lX Drive", self)
        open_action.triggered.connect(self._open_main)
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        # Salir
        exit_action = QAction("❌ Salir", self)
        exit_action.triggered.connect(self._quit)
        menu.addAction(exit_action)
        
        self.setContextMenu(menu)
    
    def _connect_signals(self):
        """Conecta señales"""
        self.activated.connect(self._on_activated)
    
    def _on_activated(self, reason):
        """Maneja activación del icono"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_main()
    
    def _open_main(self):
        """Emite señal para abrir ventana principal"""
        self.show_main_window.emit()
    
    def _quit(self):
        """Emite señal para salir"""
        self.quit_app.emit()
    
    def _sync_all(self):
        """Sincroniza todas las cuentas"""
        for account in self.account_manager.get_enabled_accounts():
            self.sync_manager.sync_now(account.id)
        
        self.showMessage(
            "lX Drive",
            "Sincronizando todas las cuentas...",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )
    
    def _toggle_pause(self):
        """Alterna pausa de sincronización"""
        if self.pause_action.text().startswith("⏸"):
            self.sync_manager.pause_all()
            self.pause_action.setText("▶️ Reanudar sincronización")
            self.update_status("Pausado")
        else:
            self.sync_manager.resume_all()
            self.pause_action.setText("⏸ Pausar sincronización")
            self.update_status("Sincronizado")
    
    def _update_accounts_menu(self):
        """Actualiza el submenú de cuentas"""
        self.accounts_menu.clear()
        
        accounts = self.account_manager.get_all()
        
        if not accounts:
            no_accounts = QAction("No hay cuentas", self)
            no_accounts.setEnabled(False)
            self.accounts_menu.addAction(no_accounts)
            return
        
        for account in accounts:
            # Icono de estado
            status_icon = account.get_status_icon()
            
            # Crear submenú para la cuenta
            account_menu = self.accounts_menu.addMenu(
                f"{status_icon} {account.name}"
            )
            
            # Opciones de la cuenta
            sync_action = QAction("🔄 Sincronizar", self)
            sync_action.triggered.connect(
                lambda checked, aid=account.id: self.sync_manager.sync_now(aid)
            )
            account_menu.addAction(sync_action)
            
            if account.mount_enabled:
                mount_action = QAction("⏏ Desmontar", self)
                mount_action.triggered.connect(
                    lambda checked, aid=account.id: self.mount_manager.unmount(aid)
                )
            else:
                mount_action = QAction("💾 Montar", self)
                mount_action.triggered.connect(
                    lambda checked, aid=account.id: self.mount_manager.mount(aid)
                )
            account_menu.addAction(mount_action)
            
            # Abrir carpeta local
            open_folder = QAction("📁 Abrir carpeta", self)
            open_folder.triggered.connect(
                lambda checked, path=account.local_path: self._open_folder(path)
            )
            account_menu.addAction(open_folder)
    
    def _open_folder(self, path: str):
        """Abre una carpeta en el explorador de archivos"""
        import subprocess
        try:
            subprocess.Popen(["xdg-open", path])
        except Exception as e:
            logger.error(f"Error abriendo carpeta: {e}")
    
    def update_status(self, status: str):
        """Actualiza el estado mostrado"""
        self.status_action.setText(f"lX Drive - {status}")
        self.setToolTip(f"lX Drive - {status}")
    
    def show_notification(self, title: str, message: str, icon_type: str = "info"):
        """Muestra una notificación"""
        icons = {
            "info": QSystemTrayIcon.MessageIcon.Information,
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "error": QSystemTrayIcon.MessageIcon.Critical,
        }
        
        self.showMessage(
            title,
            message,
            icons.get(icon_type, QSystemTrayIcon.MessageIcon.Information),
            5000
        )
    
    def refresh_menu(self):
        """Refresca el menú con datos actualizados"""
        self._update_accounts_menu()
