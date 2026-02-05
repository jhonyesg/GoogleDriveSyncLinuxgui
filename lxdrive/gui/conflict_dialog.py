#!/usr/bin/env python3
"""
ConflictDialog - Diálogo para resolver conflictos de sincronización

Permite al usuario revisar y resolver conflictos cuando un archivo
ha sido modificado en ambos lados.

v2.0 Mejoras:
- Diálogo simplificado para conflictos individuales
- Comparación lado a lado
- Resolución por timestamp (default)
- Opciones: mantener local, remoto, ambos

Author: lX Drive Team
Version: 2.0.0
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QCheckBox, QFrame, QMessageBox,
    QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QPixmap
from pathlib import Path
from datetime import datetime
from loguru import logger


class ConflictDialog(QDialog):
    """
    Diálogo para resolver conflictos de sincronización.
    
    Muestra una lista de archivos en conflicto y permite al usuario
    decidir qué versión mantener o si mantener ambas.
    """
    
    conflicts_resolved = pyqtSignal(dict)  # {file_path: action}
    
    def __init__(self, conflicts: List[ConflictFile], parent=None):
        super().__init__(parent)
        self.conflicts = conflicts
        self.resolutions = {}  # {file_path: action}
        
        self.setWindowTitle(f"⚠️ Conflictos de Sincronización ({len(conflicts)} archivos)")
        self.setMinimumSize(900, 600)
        
        self._init_ui()
        self._populate_table()
    
    def _init_ui(self):
        """Inicializa la interfaz"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(
            "Se detectaron archivos modificados en ambos lados.\n"
            "Por favor, selecciona qué versión mantener para cada archivo."
        )
        header.setWordWrap(True)
        header.setStyleSheet("font-size: 13px; padding: 10px; background: #2d2d2d; border-radius: 5px;")
        layout.addWidget(header)
        
        # Tabla de conflictos
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Archivo",
            "Tamaño Local",
            "Tamaño Remoto",
            "Fecha Local",
            "Fecha Remota",
            "Acción",
            "Estado"
        ])
        
        # Configurar tabla
        header = self.table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        
        layout.addWidget(self.table)
        
        # Panel de detalles
        details_group = QGroupBox("Detalles del Conflicto")
        details_layout = QVBoxLayout(details_group)
        
        self.details_label = QLabel("Selecciona un archivo para ver detalles")
        self.details_label.setWordWrap(True)
        details_layout.addWidget(self.details_label)
        
        layout.addWidget(details_group)
        
        # Panel de acciones
        actions_group = QGroupBox("Resolver Conflicto")
        actions_layout = QVBoxLayout(actions_group)
        
        # Botones de acción individual
        action_buttons_layout = QHBoxLayout()
        
        self.btn_keep_local = QPushButton("📁 Mantener Local")
        self.btn_keep_local.clicked.connect(lambda: self._resolve_selected("keep_local"))
        action_buttons_layout.addWidget(self.btn_keep_local)
        
        self.btn_keep_remote = QPushButton("☁️ Mantener Remoto")
        self.btn_keep_remote.clicked.connect(lambda: self._resolve_selected("keep_remote"))
        action_buttons_layout.addWidget(self.btn_keep_remote)
        
        self.btn_keep_both = QPushButton("📋 Mantener Ambos")
        self.btn_keep_both.clicked.connect(lambda: self._resolve_selected("keep_both"))
        action_buttons_layout.addWidget(self.btn_keep_both)
        
        actions_layout.addLayout(action_buttons_layout)
        
        # Acciones masivas
        mass_actions_layout = QHBoxLayout()
        
        mass_label = QLabel("Aplicar a todos:")
        mass_actions_layout.addWidget(mass_label)
        
        self.btn_all_newer = QPushButton("⏰ Más Reciente")
        self.btn_all_newer.clicked.connect(lambda: self._resolve_all("newer"))
        mass_actions_layout.addWidget(self.btn_all_newer)
        
        self.btn_all_larger = QPushButton("📊 Más Grande")
        self.btn_all_larger.clicked.connect(lambda: self._resolve_all("larger"))
        mass_actions_layout.addWidget(self.btn_all_larger)
        
        self.btn_all_local = QPushButton("📁 Todos Local")
        self.btn_all_local.clicked.connect(lambda: self._resolve_all("local"))
        mass_actions_layout.addWidget(self.btn_all_local)
        
        self.btn_all_remote = QPushButton("☁️ Todos Remoto")
        self.btn_all_remote.clicked.connect(lambda: self._resolve_all("remote"))
        mass_actions_layout.addWidget(self.btn_all_remote)
        
        mass_actions_layout.addStretch()
        actions_layout.addLayout(mass_actions_layout)
        
        layout.addWidget(actions_group)
        
        # Botones finales
        buttons_layout = QHBoxLayout()
        
        self.btn_cancel = QPushButton("❌ Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        buttons_layout.addWidget(self.btn_cancel)
        
        buttons_layout.addStretch()
        
        self.progress_label = QLabel("0 de 0 resueltos")
        buttons_layout.addWidget(self.progress_label)
        
        self.btn_apply = QPushButton("✅ Aplicar Resoluciones")
        self.btn_apply.clicked.connect(self._apply_resolutions)
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet("background: #2d7d2d; font-weight: bold;")
        buttons_layout.addWidget(self.btn_apply)
        
        layout.addLayout(buttons_layout)
        
        # Deshabilitar botones de acción individual inicialmente
        self._enable_action_buttons(False)
    
    def _populate_table(self):
        """Llena la tabla con los conflictos"""
        self.table.setRowCount(len(self.conflicts))
        
        for i, conflict in enumerate(self.conflicts):
            # Nombre del archivo
            name_item = QTableWidgetItem(conflict.name)
            name_item.setToolTip(conflict.path)
            self.table.setItem(i, 0, name_item)
            
            # Tamaño local
            local_size = self._format_size(conflict.local_size)
            local_item = QTableWidgetItem(local_size)
            if conflict.is_larger_local:
                local_item.setForeground(QColor("#4CAF50"))
            self.table.setItem(i, 1, local_item)
            
            # Tamaño remoto
            remote_size = self._format_size(conflict.remote_size)
            remote_item = QTableWidgetItem(remote_size)
            if not conflict.is_larger_local:
                remote_item.setForeground(QColor("#4CAF50"))
            self.table.setItem(i, 2, remote_item)
            
            # Fecha local
            local_date = conflict.local_mtime.strftime("%Y-%m-%d %H:%M:%S")
            local_date_item = QTableWidgetItem(local_date)
            if conflict.is_newer_local:
                local_date_item.setForeground(QColor("#2196F3"))
            self.table.setItem(i, 3, local_date_item)
            
            # Fecha remota
            remote_date = conflict.remote_mtime.strftime("%Y-%m-%d %H:%M:%S")
            remote_date_item = QTableWidgetItem(remote_date)
            if not conflict.is_newer_local:
                remote_date_item.setForeground(QColor("#2196F3"))
            self.table.setItem(i, 4, remote_date_item)
            
            # Acción (vacío inicialmente)
            action_item = QTableWidgetItem("")
            action_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 5, action_item)
            
            # Estado
            status_item = QTableWidgetItem("⏳ Pendiente")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(QColor("#FFA726"))
            self.table.setItem(i, 6, status_item)
    
    def _format_size(self, size: float) -> str:
        """Formatea tamaño en bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def _on_selection_changed(self):
        """Maneja cambio de selección en la tabla"""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            conflict = self.conflicts[row]
            
            # Actualizar detalles
            details = f"<b>Archivo:</b> {conflict.path}<br><br>"
            details += f"<b>Local:</b><br>"
            details += f"  • Tamaño: {self._format_size(conflict.local_size)}<br>"
            details += f"  • Modificado: {conflict.local_mtime.strftime('%Y-%m-%d %H:%M:%S')}<br><br>"
            details += f"<b>Remoto:</b><br>"
            details += f"  • Tamaño: {self._format_size(conflict.remote_size)}<br>"
            details += f"  • Modificado: {conflict.remote_mtime.strftime('%Y-%m-%d %H:%M:%S')}<br><br>"
            details += f"<b>Diferencias:</b><br>"
            details += f"  • Tamaño: {self._format_size(conflict.size_diff)}<br>"
            details += f"  • Tiempo: {conflict.time_diff:.0f} segundos<br>"
            
            self.details_label.setText(details)
            self._enable_action_buttons(True)
        else:
            self.details_label.setText("Selecciona un archivo para ver detalles")
            self._enable_action_buttons(False)
    
    def _enable_action_buttons(self, enabled: bool):
        """Habilita/deshabilita botones de acción"""
        self.btn_keep_local.setEnabled(enabled)
        self.btn_keep_remote.setEnabled(enabled)
        self.btn_keep_both.setEnabled(enabled)
    
    def _resolve_selected(self, action: str):
        """Resuelve el conflicto seleccionado"""
        selected = self.table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        conflict = self.conflicts[row]
        
        self.resolutions[conflict.path] = action

        # Actualizar tabla
        action_text = {
            "keep_local": "📁 Local",
            "keep_remote": "☁️ Remoto",
            "keep_both": "📋 Ambos"
        }.get(action, action)

        item5 = self.table.item(row, 5)
        assert item5 is not None
        item5.setText(action_text)
        item6 = self.table.item(row, 6)
        assert item6 is not None
        item6.setText("✅ Resuelto")
        item6.setForeground(QColor("#4CAF50"))

        self._update_progress()
    
    def _resolve_all(self, strategy: str):
        """Resuelve todos los conflictos con una estrategia"""
        for i, conflict in enumerate(self.conflicts):
            if strategy == "newer":
                action = "keep_local" if conflict.is_newer_local else "keep_remote"
            elif strategy == "larger":
                action = "keep_local" if conflict.is_larger_local else "keep_remote"
            elif strategy == "local":
                action = "keep_local"
            elif strategy == "remote":
                action = "keep_remote"
            else:
                continue
            
            self.resolutions[conflict.path] = action
            
            # Actualizar tabla
            action_text = {
                "keep_local": "📁 Local",
                "keep_remote": "☁️ Remoto"
            }.get(action, action)

            item5 = self.table.item(i, 5)
            assert item5 is not None
            item5.setText(action_text)
            item6 = self.table.item(i, 6)
            assert item6 is not None
            item6.setText("✅ Resuelto")
            item6.setForeground(QColor("#4CAF50"))
        
        self._update_progress()
    
    def _update_progress(self):
        """Actualiza el progreso de resoluciones"""
        resolved = len(self.resolutions)
        total = len(self.conflicts)
        
        self.progress_label.setText(f"{resolved} de {total} resueltos")
        self.btn_apply.setEnabled(resolved == total)
    
    def _apply_resolutions(self):
        """Aplica las resoluciones y cierra el diálogo"""
        if len(self.resolutions) != len(self.conflicts):
            return
        
        self.conflicts_resolved.emit(self.resolutions)
        self.accept()
    
    def get_resolutions(self) -> dict:
        """Obtiene las resoluciones"""
        return self.resolutions
