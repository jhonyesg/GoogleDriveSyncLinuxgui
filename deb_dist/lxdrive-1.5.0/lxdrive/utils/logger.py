#!/usr/bin/env python3
"""
Logger - Configuración del sistema de logging
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logger(
    log_level: str = "INFO",
    log_dir: Path = None,
    console: bool = True
):
    """
    Configura el sistema de logging para lX Drive.
    
    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directorio para archivos de log
        console: Si mostrar logs en consola
    """
    # Eliminar handler por defecto
    logger.remove()
    
    # Formato personalizado
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    simple_format = (
        "{time:HH:mm:ss} | <level>{level: <8}</level> | {message}"
    )
    
    # Handler de consola
    if console:
        logger.add(
            sys.stderr,
            format=simple_format,
            level=log_level,
            colorize=True
        )
    
    # Handler de archivo
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / "lxdrive.log"
        
        logger.add(
            log_file,
            format=log_format,
            level=log_level,
            rotation="10 MB",     # Rotar cuando llegue a 10MB
            retention="1 week",   # Mantener logs por 1 semana
            compression="zip",    # Comprimir logs antiguos
            encoding="utf-8"
        )
    
    logger.info("Sistema de logging inicializado")
    
    return logger
