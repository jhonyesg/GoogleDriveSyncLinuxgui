#!/usr/bin/env python3
"""
LogViewer - Widget para visualizar logs en memoria

Muestra los últimos 1000 registros de log con filtros
por nivel y búsqueda por texto.
"""

import sys
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QLineEdit, QFrame, QScrollArea,
    QProgressBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject
from PyQt6.QtGui import QFont, QColor, QTextCursor

from ..utils.log_manager import get_log_manager, LogEntry
from ..utils.logger import setup_logger


class LogViewer(QWidget):
    """
    Widget para visualizar logs en tiempo real.
    
    Características:
    - Muestra últimos 1000 registros (buffer circular)
    - Filtrado por nivel (DEBUG, INFO, WARNING, ERROR)
    - Búsqueda por texto
    - Auto-scroll cuando hay nuevos logs
    - Colores según el nivel de log
    - Actualización thread-safe usando señales
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_manager = get_log_manager()
        self._auto_scroll = True
        self._pending_update = False
        self._init_ui()
        
        # Conectar callback del LogManager
        # Registrar callback en la instancia actual; en cada refresh usaremos
        # el LogManager global para evitar referencias obsoletas si se recrea.
        self._log_manager.add_callback(self._schedule_update)
        
        # Programar actualización inicial
        QTimer.singleShot(100, self._refresh_display)
    
    def _init_ui(self):
        """Inicializa la interfaz"""
        self.setStyleSheet("background-color: #1a1a1a;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header con filtros
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet("background-color: #252525; border-bottom: 1px solid #333;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 5, 10, 5)
        
        # Título
        title = QLabel("📋 REGISTRO DE LOGS")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #aaa; letter-spacing: 1px;")
        h_layout.addWidget(title)
        
        # Contador de logs
        self.count_label = QLabel("0 logs")
        self.count_label.setStyleSheet("color: #666; font-size: 11px;")
        h_layout.addWidget(self.count_label)
        
        h_layout.addStretch()
        
        # Filtro por nivel
        level_label = QLabel("Nivel:")
        level_label.setStyleSheet("color: #888; font-size: 11px;")
        h_layout.addWidget(level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["TODOS", "DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_combo.setStyleSheet("""
            QComboBox {
                background-color: #333;
                color: white;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 80px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: white;
                selection-background-color: #4285f4;
            }
        """)
        self.level_combo.currentTextChanged.connect(self._on_filter_changed)
        h_layout.addWidget(self.level_combo)
        
        # Búsqueda
        search_label = QLabel("Buscar:")
        search_label.setStyleSheet("color: #888; font-size: 11px;")
        h_layout.addWidget(search_label)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filtrar logs...")
        self.search_edit.setFixedWidth(150)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333;
                color: white;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #4285f4;
            }
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        h_layout.addWidget(self.search_edit)
        
        # Botón limpiar
        clear_btn = QPushButton("🗑️")
        clear_btn.setFixedSize(30, 30)
        clear_btn.setToolTip("Limpiar logs")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ea4335;
            }
        """)
        clear_btn.clicked.connect(self._on_clear)
        h_layout.addWidget(clear_btn)
        
        # Botón exportar
        export_btn = QPushButton("💾")
        export_btn.setFixedSize(30, 30)
        export_btn.setToolTip("Exportar logs")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #34a853;
            }
        """)
        export_btn.clicked.connect(self._on_export)
        h_layout.addWidget(export_btn)

        # Botón reconstruir logging
        reset_btn = QPushButton("🔁")
        reset_btn.setFixedSize(30, 30)
        reset_btn.setToolTip("Reiniciar sistema de logs (recrear buffer)")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #fbbc04;
            }
        """)
        reset_btn.clicked.connect(self._on_recreate_logging)
        h_layout.addWidget(reset_btn)
        
        layout.addWidget(header)
        
        # Área de texto con scroll
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #cccccc;
                border: none;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 10px;
            }
            QTextEdit QScrollBar:vertical {
                background-color: #2a2a2a;
                width: 10px;
            }
            QTextEdit QScrollBar::handle:vertical {
                background-color: #444;
                border-radius: 5px;
                min-height: 20px;
            }
            QTextBar::handle:vertical:hover {
                background-color: #555;
            }
        """)
        
        layout.addWidget(self.text_edit, 1)
        
        # Footer con estado
        footer = QFrame()
        footer.setFixedHeight(30)
        footer.setStyleSheet("background-color: #1a1a1a; border-top: 1px solid #333;")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(10, 0, 10, 0)
        
        # Auto-scroll toggle
        self.auto_scroll_cb = QPushButton("📜 Auto-scroll: ON")
        self.auto_scroll_cb.setCheckable(True)
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #34a853;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 10px;
            }
            QPushButton:checked {
                color: #888;
            }
        """)
        self.auto_scroll_cb.clicked.connect(self._toggle_auto_scroll)
        f_layout.addWidget(self.auto_scroll_cb)
        
        f_layout.addStretch()
        
        # Nivel de estadísticas
        self.stats_label = QLabel("D:0 | I:0 | W:0 | E:0")
        self.stats_label.setStyleSheet("color: #666; font-size: 10px; font-family: monospace;")
        f_layout.addWidget(self.stats_label)
        
        layout.addWidget(footer)
    
    def _schedule_update(self):
        """Programa una actualización de forma thread-safe"""
        if not self._pending_update:
            self._pending_update = True
            QTimer.singleShot(50, self._refresh_display)
    
    def _refresh_display(self):
        """Actualiza la visualización de logs"""
        self._pending_update = False
        
        # Verificar que el widget aún existe
        if not self or self.objectName() == "":
            return
        
        try:
            # Obtener nivel de filtro
            level = self.level_combo.currentText()
            level_filter = None if level == "TODOS" else level
            
            # Obtener búsqueda
            search = self.search_edit.text()
            
            # Obtener el LogManager global en tiempo de uso (evita referencias obsoletas)
            lm = get_log_manager()

            # Aplicar filtros
            lm.set_filter(level=level_filter or "DEBUG", search_text=search)

            # Obtener entradas
            entries = lm.get_entries(limit=500, level_filter=level_filter)
            
            # Construir texto de forma eficiente
            lines = []
            for entry in entries:
                lines.append(self._format_entry(entry))
            
            text = "<br>".join(lines)
            
            # Bloquear señales temporalmente durante la actualización
            self.text_edit.blockSignals(True)
            
            # Usar HTML para mejor rendimiento
            self.text_edit.setHtml(f'<html><body style="background-color:#1a1a1a;color:#cccccc;font-family:monospace;font-size:11px;">{text}</body></html>')
            
            # Auto-scroll al final
            if self._auto_scroll:
                cursor = QTextCursor(self.text_edit.document())
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.text_edit.setTextCursor(cursor)
            
            self.text_edit.blockSignals(False)
            
            # Actualizar contador
            stats = lm.get_stats()
            self.count_label.setText(f"{stats['total']} logs")
            
            counts = stats['counts']
            self.stats_label.setText(
                f"D:{counts.get('DEBUG', 0)} | "
                f"I:{counts.get('INFO', 0)} | "
                f"W:{counts.get('WARNING', 0)} | "
                f"E:{counts.get('ERROR', 0)}"
            )
        except RuntimeError:
            # El objeto fue destruido
            pass
    
    def _format_entry(self, entry: LogEntry) -> str:
        """Formatea una entrada para mostrar"""
        time_str = entry.timestamp.strftime("%H:%M:%S")
        
        # Colores según nivel
        colors = {
            "DEBUG": "#888888",    # Gris
            "INFO": "#34a853",     # Verde
            "WARNING": "#fbbc04",  # Amarillo
            "ERROR": "#ea4335",    # Rojo
            "CRITICAL": "#ff0000"  # Rojo intenso
        }
        
        icons = {
            "DEBUG": "&#128269;",   # 🔍
            "INFO": "&#8505;",      # ℹ️
            "WARNING": "&#9888;",   # ⚠️
            "ERROR": "&#10060;",    # ❌
            "CRITICAL": "&#128680;" # 🚨
        }
        
        color = colors.get(entry.level, "#cccccc")
        icon = icons.get(entry.level, "&#128221;")  # 📝
        
        # Escapar HTML correctamente
        import html
        message = html.escape(entry.message)
        
        return f'<span style="color: #666;">{time_str}</span> | <span style="color: {color};">{icon} {entry.level: <8}</span> | {message}'
    
    def _on_filter_changed(self, text):
        """Maneja cambio de filtro de nivel"""
        self._schedule_update()
    
    def _on_search_changed(self, text):
        """Maneja cambio de texto de búsqueda"""
        self._schedule_update()
    
    def _on_clear(self):
        """Limpia los logs"""
        self._log_manager.clear()
        self.text_edit.clear()
    
    def _on_export(self):
        """Exporta los logs a un archivo"""
        text = self._log_manager.export_to_text(limit=1000)
        
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Logs",
            f"lxdrive_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Archivos de texto (*.txt);;Todos los archivos (*.*)"
        )
        
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
                
                QMessageBox.information(self, "Exportar Logs", f"Logs exportados a:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{e}")

    def _on_recreate_logging(self):
        """Recrea el sistema de logging: reinicializa LogManager y handlers y reconecta el visor."""
        try:
            # Desregistrar callback del LogManager actual
            try:
                self._log_manager.unregister_callback(self._schedule_update)
            except Exception:
                pass

            # Recrear logging global (usa valores por defecto razonables)
            setup_logger(log_level='DEBUG', console=False)

            # Volver a obtener la nueva instancia y registrar callback
            self._log_manager = get_log_manager()
            self._log_manager.add_callback(self._schedule_update)

            # Forzar actualización inmediata
            self._schedule_update()
            QMessageBox.information(self, "Logs", "Sistema de logs reiniciado correctamente")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo reiniciar logs:\n{e}")
    
    def _toggle_auto_scroll(self):
        """Alterna auto-scroll"""
        self._auto_scroll = not self._auto_scroll
        
        if self._auto_scroll:
            self.auto_scroll_cb.setText("📜 Auto-scroll: ON")
            self.auto_scroll_cb.setStyleSheet("""
                QPushButton {
                    background-color: #333;
                    color: #34a853;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 10px;
                }
            """)
        else:
            self.auto_scroll_cb.setText("📜 Auto-scroll: OFF")
            self.auto_scroll_cb.setStyleSheet("""
                QPushButton {
                    background-color: #333;
                    color: #888;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 10px;
                }
            """)
    
    def refresh(self):
        """Actualiza manualmente la visualización"""
        self._schedule_update()
    
    def shutdown(self):
        """Limpia recursos al cerrar"""
        pass
