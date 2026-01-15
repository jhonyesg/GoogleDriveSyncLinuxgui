#!/usr/bin/env python3
"""
FilterManager - Sistema de filtros y exclusiones

Gestiona patrones de exclusión/inclusión para la sincronización,
similar a .gitignore pero para archivos de sincronización.
"""

import json
from pathlib import Path
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class FilterPreset:
    """Preset de filtros predefinidos"""
    name: str
    description: str
    patterns: List[str]


# Presets predefinidos
FILTER_PRESETS = {
    "development": FilterPreset(
        name="Desarrollo",
        description="Excluye archivos de desarrollo (node_modules, __pycache__, etc.)",
        patterns=[
            "node_modules/",
            "__pycache__/",
            ".venv/",
            "venv/",
            "*.pyc",
            ".git/",
            ".idea/",
            ".vscode/",
            "*.log",
            ".env",
            ".DS_Store"
        ]
    ),
    "office": FilterPreset(
        name="Office",
        description="Excluye archivos temporales de Office",
        patterns=[
            "~$*",  # Archivos temporales de Office
            "*.tmp",
            ".~lock.*",
            "~*.tmp"
        ]
    ),
    "media": FilterPreset(
        name="Media",
        description="Excluye archivos temporales de media",
        patterns=[
            ".thumbnails/",
            "*.part",
            "*.crdownload",
            "*.download"
        ]
    ),
    "system": FilterPreset(
        name="Sistema",
        description="Excluye archivos del sistema",
        patterns=[
            ".DS_Store",
            "Thumbs.db",
            "desktop.ini",
            ".Trash-*/",
            "$RECYCLE.BIN/",
            "*.lnk"
        ]
    ),
    "backup": FilterPreset(
        name="Backups",
        description="Excluye archivos de backup",
        patterns=[
            "*.bak",
            "*.backup",
            "*~",
            "*.swp",
            "*.swo"
        ]
    ),
    "large_files": FilterPreset(
        name="Archivos Grandes",
        description="Excluye archivos muy grandes (videos, ISOs, etc.)",
        patterns=[
            "*.iso",
            "*.dmg",
            "*.vdi",
            "*.vmdk",
            "*.ova"
        ]
    )
}


class FilterManager:
    """
    Gestor de filtros y exclusiones de sincronización.
    
    Permite definir patrones de archivos/carpetas a excluir o incluir
    en la sincronización, similar a .gitignore.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Inicializa el gestor de filtros.
        
        Args:
            config_path: Ruta al archivo de configuración
        """
        self.config_path = config_path or Path.home() / ".config" / "lxdrive" / "filters.json"
        self.filters = self._load_filters()
    
    def _load_filters(self) -> Dict:
        """Carga los filtros desde el archivo de configuración"""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando filtros: {e}")
        
        # Configuración por defecto
        return {
            "global_exclude": [
                ".DS_Store",
                "Thumbs.db",
                "desktop.ini"
            ],
            "global_include": [],
            "account_filters": {},  # {account_id: {exclude: [], include: []}}
            "enabled_presets": ["system"]  # Presets activos por defecto
        }
    
    def _save_filters(self):
        """Guarda los filtros en el archivo de configuración"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.filters, f, indent=2)
            logger.info("Filtros guardados correctamente")
        except Exception as e:
            logger.error(f"Error guardando filtros: {e}")
    
    def add_global_exclude(self, pattern: str):
        """
        Añade un patrón de exclusión global.
        
        Args:
            pattern: Patrón a excluir (formato glob)
        """
        if pattern not in self.filters["global_exclude"]:
            self.filters["global_exclude"].append(pattern)
            self._save_filters()
            logger.info(f"Patrón de exclusión añadido: {pattern}")
    
    def remove_global_exclude(self, pattern: str):
        """Elimina un patrón de exclusión global"""
        if pattern in self.filters["global_exclude"]:
            self.filters["global_exclude"].remove(pattern)
            self._save_filters()
            logger.info(f"Patrón de exclusión eliminado: {pattern}")
    
    def add_global_include(self, pattern: str):
        """
        Añade un patrón de inclusión global.
        
        Los patrones de inclusión tienen prioridad sobre exclusiones.
        
        Args:
            pattern: Patrón a incluir (formato glob)
        """
        if pattern not in self.filters["global_include"]:
            self.filters["global_include"].append(pattern)
            self._save_filters()
            logger.info(f"Patrón de inclusión añadido: {pattern}")
    
    def remove_global_include(self, pattern: str):
        """Elimina un patrón de inclusión global"""
        if pattern in self.filters["global_include"]:
            self.filters["global_include"].remove(pattern)
            self._save_filters()
            logger.info(f"Patrón de inclusión eliminado: {pattern}")
    
    def set_account_filters(
        self,
        account_id: str,
        exclude: List[str],
        include: List[str]
    ):
        """
        Establece filtros específicos para una cuenta.
        
        Args:
            account_id: ID de la cuenta
            exclude: Lista de patrones a excluir
            include: Lista de patrones a incluir
        """
        self.filters["account_filters"][account_id] = {
            "exclude": exclude,
            "include": include
        }
        self._save_filters()
        logger.info(f"Filtros actualizados para cuenta: {account_id}")
    
    def get_account_filters(self, account_id: str) -> Dict[str, List[str]]:
        """
        Obtiene los filtros de una cuenta específica.
        
        Args:
            account_id: ID de la cuenta
            
        Returns:
            Diccionario con listas de exclude e include
        """
        return self.filters["account_filters"].get(
            account_id,
            {"exclude": [], "include": []}
        )
    
    def enable_preset(self, preset_name: str):
        """
        Habilita un preset de filtros.
        
        Args:
            preset_name: Nombre del preset
        """
        if preset_name not in FILTER_PRESETS:
            logger.warning(f"Preset no encontrado: {preset_name}")
            return
        
        if preset_name not in self.filters["enabled_presets"]:
            self.filters["enabled_presets"].append(preset_name)
            self._save_filters()
            logger.info(f"Preset habilitado: {preset_name}")
    
    def disable_preset(self, preset_name: str):
        """Deshabilita un preset de filtros"""
        if preset_name in self.filters["enabled_presets"]:
            self.filters["enabled_presets"].remove(preset_name)
            self._save_filters()
            logger.info(f"Preset deshabilitado: {preset_name}")
    
    def get_enabled_presets(self) -> List[FilterPreset]:
        """Obtiene los presets habilitados"""
        return [
            FILTER_PRESETS[name]
            for name in self.filters["enabled_presets"]
            if name in FILTER_PRESETS
        ]
    
    def get_all_exclude_patterns(self, account_id: Optional[str] = None) -> List[str]:
        """
        Obtiene todos los patrones de exclusión aplicables.
        
        Args:
            account_id: ID de cuenta (opcional, para incluir filtros específicos)
            
        Returns:
            Lista de patrones de exclusión
        """
        patterns = set(self.filters["global_exclude"])
        
        # Añadir patrones de presets habilitados
        for preset in self.get_enabled_presets():
            patterns.update(preset.patterns)
        
        # Añadir patrones específicos de cuenta
        if account_id:
            account_filters = self.get_account_filters(account_id)
            patterns.update(account_filters["exclude"])
        
        return list(patterns)
    
    def get_all_include_patterns(self, account_id: Optional[str] = None) -> List[str]:
        """
        Obtiene todos los patrones de inclusión aplicables.
        
        Args:
            account_id: ID de cuenta (opcional)
            
        Returns:
            Lista de patrones de inclusión
        """
        patterns = set(self.filters["global_include"])
        
        # Añadir patrones específicos de cuenta
        if account_id:
            account_filters = self.get_account_filters(account_id)
            patterns.update(account_filters["include"])
        
        return list(patterns)
    
    def to_rclone_args(self, account_id: Optional[str] = None) -> List[str]:
        """
        Convierte los filtros a argumentos de rclone.
        
        Args:
            account_id: ID de cuenta (opcional)
            
        Returns:
            Lista de argumentos para rclone
        """
        args = []
        
        # Patrones de exclusión
        for pattern in self.get_all_exclude_patterns(account_id):
            args.extend(["--exclude", pattern])
        
        # Patrones de inclusión (tienen prioridad)
        for pattern in self.get_all_include_patterns(account_id):
            args.extend(["--include", pattern])
        
        return args
    
    def import_from_gitignore(self, gitignore_path: Path) -> int:
        """
        Importa patrones desde un archivo .gitignore.
        
        Args:
            gitignore_path: Ruta al archivo .gitignore
            
        Returns:
            Número de patrones importados
        """
        if not gitignore_path.exists():
            logger.warning(f"Archivo no encontrado: {gitignore_path}")
            return 0
        
        imported = 0
        try:
            with open(gitignore_path) as f:
                for line in f:
                    line = line.strip()
                    
                    # Ignorar comentarios y líneas vacías
                    if not line or line.startswith('#'):
                        continue
                    
                    # Manejar negaciones (!)
                    if line.startswith('!'):
                        pattern = line[1:]
                        self.add_global_include(pattern)
                    else:
                        self.add_global_exclude(line)
                    
                    imported += 1
            
            logger.info(f"Importados {imported} patrones desde {gitignore_path}")
            return imported
            
        except Exception as e:
            logger.error(f"Error importando .gitignore: {e}")
            return 0
    
    def export_to_file(self, output_path: Path):
        """
        Exporta los filtros a un archivo de texto.
        
        Args:
            output_path: Ruta del archivo de salida
        """
        try:
            with open(output_path, 'w') as f:
                f.write("# lX Drive Filters\n\n")
                
                f.write("# Global Exclusions\n")
                for pattern in self.filters["global_exclude"]:
                    f.write(f"{pattern}\n")
                
                if self.filters["global_include"]:
                    f.write("\n# Global Inclusions\n")
                    for pattern in self.filters["global_include"]:
                        f.write(f"!{pattern}\n")
                
                f.write("\n# Enabled Presets\n")
                for preset_name in self.filters["enabled_presets"]:
                    f.write(f"# - {preset_name}\n")
            
            logger.info(f"Filtros exportados a: {output_path}")
            
        except Exception as e:
            logger.error(f"Error exportando filtros: {e}")
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas de filtros"""
        return {
            "global_exclude_count": len(self.filters["global_exclude"]),
            "global_include_count": len(self.filters["global_include"]),
            "accounts_with_filters": len(self.filters["account_filters"]),
            "enabled_presets": len(self.filters["enabled_presets"]),
            "total_patterns": (
                len(self.filters["global_exclude"]) +
                len(self.filters["global_include"]) +
                sum(len(FILTER_PRESETS[p].patterns) for p in self.filters["enabled_presets"] if p in FILTER_PRESETS)
            )
        }
