#!/usr/bin/env python3
"""
RcloneWrapper - Interfaz Python para comandos rclone

Este módulo proporciona una API limpia para interactuar con rclone,
manejando la configuración, autenticación y operaciones de sincronización.
"""

import subprocess
import json
import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class RcloneError(Exception):
    """Excepción personalizada para errores de rclone"""
    pass


class RemoteType(Enum):
    """Tipos de remotes soportados"""
    GOOGLE_DRIVE = "drive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"
    NEXTCLOUD = "webdav"
    PCLOUD = "pcloud"
    
    @classmethod
    def get_display_name(cls, remote_type: "RemoteType") -> str:
        names = {
            cls.GOOGLE_DRIVE: "Google Drive",
            cls.DROPBOX: "Dropbox",
            cls.ONEDRIVE: "OneDrive",
            cls.NEXTCLOUD: "Nextcloud/WebDAV",
            cls.PCLOUD: "pCloud"
        }
        return names.get(remote_type, remote_type.value)


@dataclass
class RemoteInfo:
    """Información de un remote configurado"""
    name: str
    type: str
    root_folder_id: Optional[str] = None
    token: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "root_folder_id": self.root_folder_id,
        }


@dataclass 
class FileInfo:
    """Información de un archivo/carpeta remoto"""
    path: str
    name: str
    size: int
    mod_time: str
    is_dir: bool
    mime_type: Optional[str] = None


class RcloneWrapper:
    """
    Wrapper para interactuar con rclone CLI.
    
    Proporciona métodos para:
    - Verificar instalación de rclone
    - Crear y gestionar remotes (cuentas)
    - Listar archivos y carpetas
    - Sincronizar archivos
    - Montar unidades
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Inicializa el wrapper de rclone.
        
        Args:
            config_path: Ruta al archivo de configuración de rclone.
                        Si no se especifica, usa la ubicación por defecto.
        """
        self.config_path = config_path or Path.home() / ".config" / "rclone" / "rclone.conf"
        self.rclone_path = self._find_rclone()
        
        if not self.rclone_path:
            logger.warning("rclone no está instalado en el sistema")
    
    def _find_rclone(self) -> Optional[str]:
        """Busca el ejecutable de rclone en el sistema"""
        rclone = shutil.which("rclone")
        if rclone:
            logger.debug(f"rclone encontrado en: {rclone}")
            return rclone
        
        # Buscar en ubicaciones comunes
        common_paths = [
            "/usr/bin/rclone",
            "/usr/local/bin/rclone",
            Path.home() / ".local" / "bin" / "rclone"
        ]
        
        for path in common_paths:
            if Path(path).exists():
                logger.debug(f"rclone encontrado en: {path}")
                return str(path)
        
        return None
    
    def is_installed(self) -> bool:
        """Verifica si rclone está instalado"""
        return self.rclone_path is not None
    
    def get_version(self) -> Optional[str]:
        """Obtiene la versión de rclone instalada"""
        if not self.is_installed():
            return None
        
        try:
            result = self._run_command(["version"])
            # La primera línea contiene "rclone vX.X.X"
            first_line = result.stdout.split("\n")[0]
            return first_line.replace("rclone ", "").strip()
        except RcloneError:
            return None
    

    def _run_command_stream(
        self, 
        args: List[str]
    ):
        """
        Ejecuta un comando rclone y devuelve un generador para su salida.
        
        Args:
            args: Lista de argumentos para rclone
            
        Yields:
            Cada línea de la salida (stdout y stderr combinados)
        """
        if not self.is_installed():
            raise RcloneError("rclone no está instalado")
            
        cmd = [self.rclone_path] + args
        if self.config_path and self.config_path.exists():
            cmd.extend(["--config", str(self.config_path)])
            
        logger.debug(f"Streaming: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        for line in process.stdout:
            yield line
            
        process.stdout.close()
        return_code = process.wait()
        if return_code != 0:
            logger.warning(f"Comando stream terminó con código: {return_code}")
            yield f"ERROR: El proceso terminó con código {return_code}"

    def _run_command(
        self, 
        args: List[str], 
        capture_output: bool = True,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """
        Ejecuta un comando rclone.
        
        Args:
            args: Lista de argumentos para rclone
            capture_output: Si capturar stdout/stderr
            timeout: Timeout en segundos
            
        Returns:
            CompletedProcess con el resultado
            
        Raises:
            RcloneError: Si el comando falla
        """
        if not self.is_installed():
            raise RcloneError("rclone no está instalado")
        
        cmd = [self.rclone_path] + args
        
        # Añadir configuración personalizada si existe
        if self.config_path and self.config_path.exists():
            cmd.extend(["--config", str(self.config_path)])
        
        logger.debug(f"Ejecutando: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Error desconocido"
                # Si es un error de bisync que ya manejamos, no logger como error crítico aquí
                if "bisync" not in str(args):
                    logger.error(f"Error en rclone: {error_msg}")
                raise RcloneError(error_msg)
            
            return result

            
        except subprocess.TimeoutExpired:
            raise RcloneError(f"Timeout ejecutando: {' '.join(args)}")
        except FileNotFoundError:
            raise RcloneError("Ejecutable de rclone no encontrado")
    
    def run_command(self, args: List[str]) -> str:
        """
        Ejecuta un comando rclone y devuelve la salida como string.
        Utilizado por herramientas externas como el explorador de archivos.
        """
        result = self._run_command(args)
        return result.stdout

    def list_remotes(self) -> List[RemoteInfo]:
        """
        Lista todos los remotes configurados.
        
        Returns:
            Lista de RemoteInfo con la información de cada remote
        """
        try:
            result = self._run_command(["listremotes", "--long"])
            remotes = []
            
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                    
                # Formato: "nombre: tipo"
                parts = line.split(":")
                if len(parts) >= 2:
                    name = parts[0].strip()
                    remote_type = parts[1].strip()
                    remotes.append(RemoteInfo(name=name, type=remote_type))
            
            logger.info(f"Encontrados {len(remotes)} remotes configurados")
            return remotes
            
        except RcloneError as e:
            logger.error(f"Error listando remotes: {e}")
            return []
    
    def get_remote_config(self, remote_name: str) -> Dict[str, Any]:
        """
        Obtiene la configuración de un remote específico.
        
        Args:
            remote_name: Nombre del remote
            
        Returns:
            Diccionario con la configuración
        """
        try:
            result = self._run_command(["config", "dump"])
            config = json.loads(result.stdout)
            return config.get(remote_name, {})
        except (RcloneError, json.JSONDecodeError) as e:
            logger.error(f"Error obteniendo config de {remote_name}: {e}")
            return {}
    
    def create_remote_interactive(self, remote_name: str, remote_type: RemoteType) -> bool:
        """
        Crea un nuevo remote de forma interactiva.
        
        Esto abrirá el navegador para autenticar con el servicio.
        
        Args:
            remote_name: Nombre para el nuevo remote
            remote_type: Tipo de servicio cloud
            
        Returns:
            True si se creó correctamente
        """
        try:
            # Usar rclone config create con auto-config
            args = [
                "config", "create",
                remote_name,
                remote_type.value,
                "--drive-acknowledge-abuse=true"  # Para Google Drive
            ]
            
            # Este comando abrirá el navegador para OAuth
            subprocess.run(
                [self.rclone_path] + args,
                check=True
            )
            
            logger.info(f"Remote '{remote_name}' creado correctamente")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error creando remote: {e}")
            return False
    
    def delete_remote(self, remote_name: str) -> bool:
        """
        Elimina un remote configurado.
        
        Args:
            remote_name: Nombre del remote a eliminar
            
        Returns:
            True si se eliminó correctamente
        """
        try:
            self._run_command(["config", "delete", remote_name])
            logger.info(f"Remote '{remote_name}' eliminado")
            return True
        except RcloneError as e:
            logger.error(f"Error eliminando remote: {e}")
            return False
    
    def list_files(
        self, 
        remote_name: str, 
        path: str = "",
        recursive: bool = False
    ) -> List[FileInfo]:
        """
        Lista archivos en un remote.
        
        Args:
            remote_name: Nombre del remote
            path: Ruta dentro del remote (vacío = raíz)
            recursive: Si listar recursivamente
            
        Returns:
            Lista de FileInfo
        """
        try:
            remote_path = f"{remote_name}:{path}"
            args = ["lsjson", remote_path]
            
            if recursive:
                args.append("--recursive")
            
            result = self._run_command(args, timeout=60)
            files_data = json.loads(result.stdout)
            
            files = []
            for item in files_data:
                files.append(FileInfo(
                    path=item.get("Path", ""),
                    name=item.get("Name", ""),
                    size=item.get("Size", 0),
                    mod_time=item.get("ModTime", ""),
                    is_dir=item.get("IsDir", False),
                    mime_type=item.get("MimeType")
                ))
            
            return files
            
        except (RcloneError, json.JSONDecodeError) as e:
            logger.error(f"Error listando archivos: {e}")
            return []
    
    def sync(
        self,
        source: str,
        dest: str,
        dry_run: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Tuple[bool, str]:
        """
        Sincroniza archivos entre origen y destino.
        
        Args:
            source: Ruta origen (local o remote:path)
            dest: Ruta destino (local o remote:path)
            dry_run: Si solo simular sin hacer cambios
            progress_callback: Función para reportar progreso
            
        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            args = ["sync", source, dest, "--progress", "--stats-one-line"]
            
            if dry_run:
                args.append("--dry-run")
            
            result = self._run_command(args, timeout=3600)  # 1 hora timeout
            
            return True, "Sincronización completada"
            
        except RcloneError as e:
            return False, str(e)
    
    def bisync(
        self,
        path1: str,
        path2: str,
        dry_run: bool = False,
        resync: bool = False,
        force_resync: bool = False
    ) -> Tuple[bool, str]:
        """
        Sincronización bidireccional entre dos rutas.
        
        Args:
            path1: Primera ruta (local o remote:path)
            path2: Segunda ruta (local o remote:path)
            dry_run: Si solo simular sin hacer cambios
            resync: Si forzar resincronización completa
            force_resync: Si forzar resync incluso si ya existe tracking
            
        Returns:
            Tupla (éxito, mensaje)
        """
        # Verificar si es la primera sincronización
        # bisync guarda archivos de tracking en ~/.cache/rclone/bisync/
        bisync_cache = Path.home() / ".cache" / "rclone" / "bisync"
        
        # Generar nombre de tracking esperado
        import hashlib
        track_name = f"{path1}..{path2}".replace("/", "_").replace(":", "_")
        tracking_exists = False
        
        if bisync_cache.exists():
            # Buscar si hay archivos de tracking para esta combinación
            for f in bisync_cache.glob("*.lst*"):
                if track_name[:20] in f.name or any(
                    p in f.name for p in [path1.replace(":", "_")[:15], path2.replace("/", "_")[:15]]
                ):
                    tracking_exists = True
                    break
        
        try:
            args = ["bisync", path1, path2]
            
            if dry_run:
                args.append("--dry-run")
            
            # Usar resync si es primera vez o si se solicita
            if resync or force_resync or not tracking_exists:
                args.extend(["--resync", "--ignore-listing-checksum"])
                logger.info(f"🔄 Forzando resincronización completa para: {path1}")
            
            # Flags de rclone para evitar bloqueos y dar más info
            args.extend([
                "--verbose", 
                "--stats", "1s", 
                "--stats-one-line",
                "--conflict-resolve", "newer"  # El archivo más reciente siempre gana
            ])
            
            result = self._run_command(args, timeout=3600)
            
            # Algunos errores de bisync salen con return code 0 pero son fallos
            if "ERROR" in result.stderr and ("Bisync aborted" in result.stderr or "critical error" in result.stderr):
                raise RcloneError(result.stderr)
                
            return True, "Sincronización completada"
            
        except RcloneError as e:
            error_str = str(e)
            
            # 1. Detectar errores de autenticación/permisos
            auth_errors = ["expired", "token", "authorize", "401 Unauthorized", "login"]
            if any(err in error_str.lower() for err in auth_errors):
                return False, "Error de autenticación: Por favor, elimina y vuelve a añadir la cuenta."

            # 2. Detectar fallos de listings/cache
            resync_triggers = ["resync", "prior sync", "cannot find prior", "listings", "aborted", "recovery"]
            
            if any(trigger in error_str.lower() for trigger in resync_triggers):
                if not resync and not force_resync:
                    logger.warning("Fallo en archivos de control de rclone. Limpiando caché...")
                    
                    # LIMPIEZA PROFUNDA: Borrar listings y locks
                    try:
                        bisync_cache = Path.home() / ".cache" / "rclone" / "bisync"
                        if bisync_cache.exists():
                            # Borrar archivos relacionados con estas rutas
                            # (rclone usa hashes o rutas planas en los nombres de archivo)
                            for f in bisync_cache.glob("*"):
                                # Si el nombre del archivo contiene partes de la ruta, lo borramos
                                # o simplemente borramos todo lo de bisync para mayor seguridad
                                if ".lst" in f.name or ".lck" in f.name:
                                    f.unlink()
                            logger.info("Caché de bisync limpiada satisfactoriamente")
                    except Exception as ce:
                        logger.error(f"No se pudo limpiar la caché: {ce}")
                    
                    # Reintentar con resync absoluto
                    return self.bisync(path1, path2, dry_run=dry_run, resync=True, force_resync=True)
            
            return False, error_str.strip()


    def bisync_stream(
        self,
        path1: str,
        path2: str,
        resync: bool = False
    ):
        """
        Versión stream de bisync para capturar actividad.
        """
        args = [
            "bisync", path1, path2, 
            "--verbose", 
            "--stats", "1s",
            "--conflict-resolve", "newer",
            "--resilient",
            "--force",
            "--remove-empty-dirs",
            "--fix-case",
            "--recover",
            "--no-cleanup"
        ]
        
        # Flag para permitir descarga de archivos con 'abuse' (malware detectado por google)
        args.append("--drive-acknowledge-abuse")
        
        if resync:
            args.extend(["--resync", "--ignore-listing-checksum"])
            
        # Custom wrapper to catch and clean lock files
        for line in self._run_command_stream(args):
            # Check for lock file error in the stream
            if "prior lock file found" in line:
                logger.warning(f"Lock file detected in stream: {line.strip()}")
                try:
                    # Extract path from error (usually ends with .lck)
                    # Format: NOTICE: Failed to bisync: prior lock file found: /path/to/file.lck
                    if ": " in line:
                        lock_path = line.split(": ")[-1].strip()
                        if lock_path.endswith(".lck") and Path(lock_path).exists():
                            logger.info(f"Removing stale lock file: {lock_path}")
                            Path(lock_path).unlink()
                except Exception as e:
                    logger.error(f"Failed to remove lock file: {e}")
            
            yield line




    
    def get_disk_usage(self, remote_name: str) -> Dict[str, Any]:
        """
        Obtiene información de uso de disco de un remote.
        
        Args:
            remote_name: Nombre del remote
            
        Returns:
            Diccionario con total, used, free, trashed
        """
        try:
            result = self._run_command(["about", f"{remote_name}:", "--json"])
            return json.loads(result.stdout)
        except (RcloneError, json.JSONDecodeError) as e:
            logger.error(f"Error obteniendo uso de disco: {e}")
            return {}
    
    def check_connection(self, remote_name: str) -> bool:
        """
        Verifica la conexión a un remote.
        
        Args:
            remote_name: Nombre del remote
            
        Returns:
            True si la conexión es exitosa
        """
        try:
            self._run_command(["about", f"{remote_name}:"], timeout=30)
            return True
        except RcloneError:
            return False


# Funciones de utilidad
def install_rclone() -> Tuple[bool, str]:
    """
    Instala rclone en el sistema.
    
    Returns:
        Tupla (éxito, mensaje)
    """
    try:
        # Descargar e instalar usando el script oficial
        result = subprocess.run(
            ["curl", "-sL", "https://rclone.org/install.sh"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # El script necesita sudo, informar al usuario
            return False, "Por favor, ejecuta: curl https://rclone.org/install.sh | sudo bash"
        
        return False, "Error descargando el instalador"
        
    except Exception as e:
        return False, str(e)
