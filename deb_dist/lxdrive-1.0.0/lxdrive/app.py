#!/usr/bin/env python3
"""
lX Drive - Aplicación principal

Cliente de sincronización multi-cuenta para Google Drive en Linux.
Alternativa opensource a Insync.
"""

import sys
import signal
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from loguru import logger

from .core import RcloneWrapper, AccountManager, SyncManager, MountManager
from .gui import MainWindow, TrayIcon
from .utils import Config, setup_logger


class LXDriveApp:
    """
    Aplicación principal de lX Drive.
    
    Coordina todos los componentes:
    - RcloneWrapper: Interfaz con rclone
    - AccountManager: Gestión de cuentas
    - SyncManager: Sincronización automática
    - MountManager: Montaje de unidades
    - MainWindow: Interfaz gráfica
    - TrayIcon: Icono de bandeja
    """
    
    def __init__(self):
        self.app: QApplication = None
        self.config: Config = None
        self.rclone: RcloneWrapper = None
        self.account_manager: AccountManager = None
        self.sync_manager: SyncManager = None
        self.mount_manager: MountManager = None
        self.main_window: MainWindow = None
        self.tray_icon: TrayIcon = None
    
    def initialize(self):
        """Inicializa todos los componentes de la aplicación"""
        
        # Inicializar configuración
        self.config = Config()
        
        # Configurar logging
        log_dir = Path.home() / ".config" / "lxdrive" / "logs"
        setup_logger(
            log_level=self.config.get("log_level", "INFO"),
            log_dir=log_dir,
            console=True
        )
        
        logger.info("=" * 50)
        logger.info("Iniciando lX Drive")
        logger.info("=" * 50)
        
        # Inicializar core
        self.rclone = RcloneWrapper()
        
        if not self.rclone.is_installed():
            logger.warning("rclone no está instalado")
        else:
            version = self.rclone.get_version()
            logger.info(f"rclone versión: {version}")
        
        self.account_manager = AccountManager()
        self.sync_manager = SyncManager(self.rclone, self.account_manager)
        self.mount_manager = MountManager(self.rclone, self.account_manager)
        
        # Configurar callbacks de sincronización
        self.sync_manager.set_callbacks(
            on_start=self._on_sync_start,
            on_complete=self._on_sync_complete,
            on_error=self._on_sync_error,
            on_activity=self._on_file_activity
        )
        
        # Configurar callback de actividad de montaje
        self.mount_manager.set_activity_callback(self._on_mount_activity)
        
        logger.info(f"Cargadas {len(self.account_manager.get_all())} cuentas")
    
    def run(self) -> int:
        """
        Ejecuta la aplicación.
        
        Returns:
            Código de salida
        """
        # Crear aplicación Qt
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("lX Drive")
        self.app.setApplicationDisplayName("lX Drive")
        self.app.setOrganizationName("lX Drive")
        self.app.setQuitOnLastWindowClosed(False)  # Mantener en bandeja
        
        # Estilo oscuro global
        self.app.setStyle("Fusion")
        
        # Inicializar componentes
        self.initialize()
        
        # Crear ventana principal
        self.main_window = MainWindow(
            self.rclone,
            self.account_manager,
            self.sync_manager,
            self.mount_manager
        )
        
        # Crear icono de bandeja
        self.tray_icon = TrayIcon(
            self.account_manager,
            self.sync_manager,
            self.mount_manager
        )
        
        # Conectar señales
        self.tray_icon.show_main_window.connect(self._show_main_window)
        self.tray_icon.quit_app.connect(self._quit_app)
        
        # Manejar señales del sistema
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Iniciar servicios
        if self.config.get("sync_on_startup", True):
            self.sync_manager.start()
            logger.info("Servicio de sincronización iniciado")
        
        # Auto-montar cuentas que se dejaron montadas (persistencia de estado)
        for account in self.account_manager.get_all():
            if account.mount_enabled:
                logger.info(f"Remontando automáticamente unidad: {account.name}")
                self.mount_manager.mount(account.id)
        
        # Mostrar ventana según configuración
        if not self.config.get("start_minimized", False):
            self.main_window.show()
        else:
            self.tray_icon.show_notification(
                "lX Drive",
                "Ejecutándose en segundo plano",
                "info"
            )
        
        logger.info("lX Drive iniciado correctamente")
        
        # Ejecutar loop de eventos
        return self.app.exec()
    
    def _show_main_window(self):
        """Muestra la ventana principal"""
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
    
    def _quit_app(self):
        """Cierra la aplicación y limpia recursos"""
        logger.info("Cerrando lX Drive...")
        
        # 1. Detener sincronización
        self.sync_manager.stop()
        logger.info("Servicio de sincronización detenido")
        
        # 2. Desmontar unidades activamente
        unmounted = self.mount_manager.unmount_all()
        if unmounted > 0:
            logger.info(f"Limpieza completada: {unmounted} unidades desmontadas")
        else:
            logger.info("No había unidades montadas para limpiar")
        
        # Ocultar icono de bandeja
        self.tray_icon.hide()
        
        # Cerrar aplicación
        self.app.quit()
    
    def _signal_handler(self, signum, frame):
        """Maneja señales del sistema"""
        logger.info(f"Señal recibida: {signum}")
        self._quit_app()
    
    def _on_sync_start(self, account_id: str):
        """Callback cuando inicia sincronización"""
        account = self.account_manager.get_by_id(account_id)
        if account:
            logger.info(f"Sincronizando: {account.name}")
            self.tray_icon.update_status(f"Sincronizando {account.name}...")
    
    def _on_sync_complete(self, task):
        """Callback cuando termina sincronización"""
        account = self.account_manager.get_by_id(task.account_id)
        if account:
            if task.success:
                logger.info(f"Sincronización completada: {account.name}")
                
                if self.config.get("notify_sync_complete", True):
                    self.tray_icon.show_notification(
                        "Sincronización completada",
                        f"{account.name} sincronizado correctamente",
                        "info"
                    )
            
            self.tray_icon.update_status("Sincronizado")
    
    def _on_file_activity(self, account_id: str, name: str, action: str, path: str):
        """Callback cuando hay actividad de archivos (Sync)"""
        if self.main_window and hasattr(self.main_window, 'bridge'):
            self.main_window.bridge.activity_signal.emit(account_id, name, action, path)

    def _on_mount_activity(self, account_id: str, name: str, action: str, path: str):
        """Callback cuando hay actividad en la unidad virtual (Mount)"""
        if self.main_window and hasattr(self.main_window, 'bridge'):
            self.main_window.bridge.activity_signal.emit(account_id, name, action, path)
    
    def _on_sync_error(self, account_id: str, message: str):
        """Callback cuando hay error en sincronización"""
        account = self.account_manager.get_by_id(account_id)
        if account:
            logger.error(f"Error en {account.name}: {message}")
            
            if self.config.get("notify_sync_error", True):
                self.tray_icon.show_notification(
                    "Error de sincronización",
                    f"{account.name}: {message}",
                    "error"
                )
            
            self.tray_icon.update_status("Error")


def main() -> int:
    """
    Punto de entrada principal.
    
    Returns:
        Código de salida
    """
    try:
        app = LXDriveApp()
        return app.run()
    except Exception as e:
        logger.exception(f"Error fatal: {e}")
        
        # Mostrar error en GUI si es posible
        try:
            if QApplication.instance() is None:
                temp_app = QApplication(sys.argv)
            
            QMessageBox.critical(
                None,
                "Error Fatal",
                f"lX Drive ha encontrado un error:\n\n{e}"
            )
        except:
            pass
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
