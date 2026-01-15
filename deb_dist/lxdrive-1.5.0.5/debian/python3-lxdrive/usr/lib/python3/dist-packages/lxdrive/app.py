#!/usr/bin/env python3
"""
lX Drive - Aplicación principal

Cliente de sincronización multi-cuenta para Google Drive en Linux.
Alternativa opensource a Insync.
"""

import sys
import signal
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from loguru import logger

from .core import RcloneWrapper, AccountManager, SyncManager, MountManager
from .gui import MainWindow, TrayIcon
from .utils import Config, setup_logger
from .utils.activity_log import ActivityLogManager, get_activity_log_manager, ActivityType, ActivityAction


class LXDriveApp:
    """
    Aplicación principal de lX Drive.
    
    Coordina todos los componentes:
    - RcloneWrapper: Interfaz con rclone
    - AccountManager: Gestión de cuentas
    - SyncManager: Sincronización automática
    - MountManager: Montaje de unidades
    - ActivityLogManager: Registros de actividad por cuenta
    - MainWindow: Interfaz gráfica
    - TrayIcon: Icono de bandeja
    """
    
    def __init__(self):
        self.app = None
        self.config = None
        self.rclone = None
        self.account_manager = None
        self.sync_manager = None
        self.mount_manager = None
        self.activity_manager = None  # Nuevo: gestor de actividad por cuenta
        self.main_window = None
        self.tray_icon = None
    
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
        
        # Inicializar gestor de actividad por cuenta
        activity_dir = Path.home() / ".config" / "lxdrive" / "activity"
        self.activity_manager = ActivityLogManager(storage_dir=activity_dir)
        
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

        # Asegurar que los componentes están inicializados
        assert self.rclone is not None
        assert self.account_manager is not None
        assert self.sync_manager is not None
        assert self.mount_manager is not None
        assert self.config is not None

        # Crear ventana principal con ActivityLogManager y Config
        self.main_window = MainWindow(
            self.rclone,
            self.account_manager,
            self.sync_manager,
            self.mount_manager,
            activity_manager=self.activity_manager,
            config=self.config
        )

        # Crear icono de bandeja
        self.tray_icon = TrayIcon(
            self.account_manager,
            self.sync_manager,
            self.mount_manager
        )

        # Asegurar que la GUI está inicializada
        assert self.main_window is not None
        assert self.tray_icon is not None
        
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
        assert self.main_window is not None
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
    
    def _quit_app(self):
        """Cierra la aplicación y limpia recursos"""
        assert self.sync_manager is not None
        assert self.mount_manager is not None
        assert self.tray_icon is not None
        assert self.app is not None

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
        assert self.account_manager is not None
        assert self.tray_icon is not None

        account = self.account_manager.get_by_id(account_id)
        if account:
            logger.info(f"Sincronizando: {account.name}")
            self.tray_icon.update_status(f"Sincronizando {account.name}...")
            
            # Registrar en ActivityLogManager
            if self.activity_manager:
                self.activity_manager.add_activity(
                    account_id=account_id,
                    activity_type=ActivityType.SYNC,
                    action=ActivityAction.STARTED,
                    name=f"Sincronización de {account.name}",
                    path=""
                )
    
    def _on_sync_complete(self, task):
        """Callback cuando termina sincronización"""
        assert self.account_manager is not None
        assert self.config is not None
        assert self.tray_icon is not None

        account = self.account_manager.get_by_id(task.account_id)
        if account:
            if task.success:
                logger.info(f"Sincronización completada: {account.name}")
                
                # Registrar en ActivityLogManager
                if self.activity_manager:
                    self.activity_manager.add_activity(
                        account_id=task.account_id,
                        activity_type=ActivityType.SYNC,
                        action=ActivityAction.SYNCED,
                        name=f"Sincronización completada",
                        path=f"{task.files_transferred} archivos"
                    )

                if self.config.get("notify_sync_complete", True):
                    # Incluir detalles de cambios si los hay
                    message = f"{account.name} sincronizado correctamente"
                    if task.files_transferred > 0:
                        message += f" ({task.files_transferred} archivo{'s' if task.files_transferred != 1 else ''} actualizado{'s' if task.files_transferred != 1 else ''})"
                    elif "completada" in task.message and "0" in task.message:
                        message += " (sin cambios)"
                    else:
                        # Si el mensaje contiene información detallada, usarla
                        if task.message and task.message != "Sincronización completada":
                            message += f" - {task.message}"

                    self.tray_icon.show_notification(
                        "Sincronización completada",
                        message,
                        "info"
                    )

            self.tray_icon.update_status("Sincronizado")
    
    def _on_file_activity(self, account_id: str, name: str, action: str, path: str):
        """Callback cuando hay actividad de archivos (Sync)"""
        # Registrar en ActivityLogManager
        if self.activity_manager:
            # Mapear string action a ActivityAction
            action_map = {
                "uploading": ActivityAction.UPLOADING,
                "downloading": ActivityAction.DOWNLOADING,
                "synced": ActivityAction.SYNCED,
                "deleted": ActivityAction.DELETED,
                "moved": ActivityAction.MOVED,
                "created": ActivityAction.CREATED,
                "modified": ActivityAction.MODIFIED,
                "error": ActivityAction.ERROR
            }
            activity_action = action_map.get(action.lower(), ActivityAction.SYNCED)
            
            self.activity_manager.add_activity(
                account_id=account_id,
                activity_type=ActivityType.SYNC,
                action=activity_action,
                name=name,
                path=path
            )
        
        # Emitir señal para la UI
        if self.main_window and hasattr(self.main_window, 'bridge'):
            self.main_window.bridge.activity_signal.emit(account_id, name, action, path)

    def _on_mount_activity(self, account_id: str, name: str, action: str, path: str):
        """Callback cuando hay actividad en la unidad virtual (Mount)"""
        # Registrar en ActivityLogManager como VFS
        if self.activity_manager:
            action_map = {
                "mounted": ActivityAction.MOUNTED,
                "unmounted": ActivityAction.UNMOUNTED,
                "uploading": ActivityAction.UPLOADING,
                "downloading": ActivityAction.DOWNLOADING,
                "created": ActivityAction.CREATED,
                "deleted": ActivityAction.DELETED,
                "modified": ActivityAction.MODIFIED,
                "error": ActivityAction.ERROR
            }
            activity_action = action_map.get(action.lower(), ActivityAction.SYNCED)
            
            self.activity_manager.add_activity(
                account_id=account_id,
                activity_type=ActivityType.VFS,
                action=activity_action,
                name=name,
                path=path
            )
        
        # Emitir señal para la UI
        if self.main_window and hasattr(self.main_window, 'bridge'):
            self.main_window.bridge.activity_signal.emit(account_id, name, action, path)
    
    def _on_sync_error(self, account_id: str, message: str):
        """Callback cuando hay error en sincronización"""
        assert self.account_manager is not None
        assert self.config is not None
        assert self.tray_icon is not None

        account = self.account_manager.get_by_id(account_id)
        if account:
            logger.error(f"Error en {account.name}: {message}")
            
            # Registrar error en ActivityLogManager
            if self.activity_manager:
                self.activity_manager.add_activity(
                    account_id=account_id,
                    activity_type=ActivityType.SYNC,
                    action=ActivityAction.ERROR,
                    name="Error de sincronización",
                    path="",
                    error_message=message
                )

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
