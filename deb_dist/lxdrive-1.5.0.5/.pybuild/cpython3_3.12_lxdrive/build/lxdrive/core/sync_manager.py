import threading
import time
from pathlib import Path
from typing import Optional, Dict, Callable, Any, Tuple, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from loguru import logger

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileMovedEvent, FileCreatedEvent, FileDeletedEvent, FileModifiedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("Watchdog no instalado. La detección de cambios instantánea no funcionará. (pip install watchdog)")

from .account_manager import Account, AccountManager, SyncStatus, SyncDirection
from .rclone_wrapper import RcloneWrapper


class ChangeHandler(FileSystemEventHandler):
    """
    Manejador de eventos del sistema de archivos con soporte para renombres.
    
    Detecta:
    - FileMovedEvent: Renombre directo (Linux inotify lo captura bien)
    - Delete + Create: Patrón alternativo de renombre (algunos editores/apps)
    
    Ignora:
    - Archivos temporales de rclone (.partial, .tmp)
    - Cambios durante sincronización activa
    """
    
    # Patrones de archivos temporales a ignorar (generados por rclone durante sync)
    IGNORE_PATTERNS = ['.partial', '.tmp', '.rclone', '~', '.swp', '.swo']
    
    def __init__(self, callback, debounce=2.0, base_path: str = ""):
        self.callback = callback
        self.debounce = debounce
        self.base_path = base_path  # Ruta base que estamos monitoreando
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        
        # Flag para pausar detección durante sincronización
        self._sync_in_progress = False
        
        # Tracking para detectar renombres como Delete+Create
        self._pending_deletes: Dict[str, dict] = {}  # {path: {size, mtime, time}}
        self._rename_window = 2.0  # Segundos para considerar delete+create como rename
        
        # Cola de renombres detectados para procesar antes del bisync
        self._pending_renames: list = []  # [(old_path, new_path), ...]

        # Tracking de directorios movidos para evitar duplicación de eventos hijos
        self._moved_directories: Dict[str, dict] = {}  # {old_path: {new_path, time}}
        self._directory_move_window = 5.0  # Segundos para ignorar cambios dentro de directorios movidos
    
    def set_sync_in_progress(self, in_progress: bool):
        """Marca si hay una sincronización en progreso para ignorar cambios de rclone"""
        with self._lock:
            self._sync_in_progress = in_progress
            if in_progress:
                logger.debug(f"Watchdog pausado para {self.base_path}")
            else:
                logger.debug(f"Watchdog reanudado para {self.base_path}")
    
    def _should_ignore(self, path: str) -> bool:
        """Determina si un archivo debe ignorarse (temporal de rclone, etc.)"""
        # Ignorar si hay sync en progreso
        if self._sync_in_progress:
            return True
        
        # Ignorar archivos temporales
        path_lower = path.lower()
        for pattern in self.IGNORE_PATTERNS:
            if pattern in path_lower:
                logger.debug(f"Ignorando archivo temporal: {path}")
                return True
        
        # Ignorar si el archivo está dentro de un directorio que se acaba de mover
        # (Para evitar ráfagas de eventos Delete/Create que confunden a bisync)
        if self._is_within_moved_directory(path):
            logger.debug(f"Ignorando cambio dentro de directorio movido recientemente: {path}")
            return True
        
        return False
        
    def _is_within_moved_directory(self, path: str) -> bool:
        """Verifica si una ruta está dentro de un directorio movido recientemente."""
        with self._lock:
            path_obj = Path(path)
            now = time.time()
            
            # Buscar si este path está dentro de algún directorio movido
            for old_dir_path, move_info in list(self._moved_directories.items()):
                # Limpiar si ya expiró la ventana de tiempo
                if now - move_info["time"] > self._directory_move_window:
                    del self._moved_directories[old_dir_path]
                    continue
                
                # Verificar si el path es descendiente del directorio movido (origen o destino)
                try:
                    # Si el archivo pertenecía al path viejo
                    path_obj.relative_to(Path(old_dir_path))
                    return True
                except ValueError:
                    pass
                
                try:
                    # Si el archivo pertenece al path nuevo
                    path_obj.relative_to(Path(move_info["new_path"]))
                    return True
                except ValueError:
                    pass
            
            return False

    def get_and_clear_renames(self) -> list:
        """Obtiene y limpia la lista de renombres pendientes"""
        with self._lock:
            renames = self._pending_renames.copy()
            self._pending_renames.clear()
            self._moved_directories.clear() # Limpiar tracking de directorios al procesar
            return renames
        
    def _schedule_callback(self):
        """Programa el callback con debounce"""
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce, self.callback)
            self._timer.start()
    
    def on_moved(self, event):
        """Maneja eventos de movimiento/renombre (FileMovedEvent)"""
        if event.is_directory:
            # Soporte para renombres de directorios (evita duplicación de archivos dentro)
            logger.info(f"Directorio movido detectado: {event.src_path} -> {event.dest_path}")
            with self._lock:
                self._moved_directories[event.src_path] = {
                    "new_path": event.dest_path,
                    "time": time.time()
                }
                self._pending_renames.append((event.src_path, event.dest_path))
            self._schedule_callback()
            return
        
        # Ignorar archivos temporales de rclone (.partial -> final)
        if self._should_ignore(event.src_path) or self._should_ignore(event.dest_path):
            return
        
        # Ignorar si el origen es un archivo .partial (rclone finalizando descarga)
        if '.partial' in event.src_path:
            logger.debug(f"Ignorando finalización de descarga rclone: {event.src_path}")
            return
        
        logger.info(f"Renombre detectado (FileMovedEvent): {event.src_path} -> {event.dest_path}")
        
        # Guardar el renombre para procesarlo antes del bisync
        with self._lock:
            self._pending_renames.append((event.src_path, event.dest_path))
        
        self._schedule_callback()
    
    def on_deleted(self, event):
        """Maneja eventos de eliminación - guarda info para detectar rename como delete+create"""
        if event.is_directory:
            # Los directorios eliminados se ignoran si fueron parte de un on_moved
            # Si no, rclone sync se encargará de eliminarlos en el remoto
            return
        
        if self._should_ignore(event.src_path):
            return
        
        logger.debug(f"Archivo eliminado detectado: {event.src_path}")
        
        # Guardar información del archivo eliminado para posible emparejamiento
        with self._lock:
            self._pending_deletes[event.src_path] = {
                "time": time.time(),
                "ext": Path(event.src_path).suffix,
                "parent": str(Path(event.src_path).parent),
                "name": Path(event.src_path).name,
                "full_path": event.src_path
            }
        
        self._schedule_callback()
        
        # Limpiar deletes antiguos después de la ventana de tiempo
        threading.Timer(self._rename_window + 0.5, self._cleanup_pending_deletes).start()
    
    def on_created(self, event):
        """Maneja eventos de creación - verifica si es parte de un rename (delete+create)"""
        if event.is_directory:
            return
        
        if self._should_ignore(event.src_path):
            return
        
        logger.debug(f"Archivo creado detectado: {event.src_path}")
        
        # Verificar si este "create" coincide con un "delete" reciente (posible rename)
        created_path = Path(event.src_path)
        now = time.time()
        
        with self._lock:
            matched_delete = None
            old_path = None
            for del_path, del_info in list(self._pending_deletes.items()):
                # Verificar ventana de tiempo
                if now - del_info["time"] > self._rename_window:
                    continue
                
                # Verificar mismo directorio padre y misma extensión
                if del_info["parent"] == str(created_path.parent) and \
                   del_info["ext"] == created_path.suffix:
                    
                    # Verificar que no sea el mismo archivo (redundante)
                    if del_path != event.src_path:
                        matched_delete = del_path
                        old_path = del_info["full_path"]
                        logger.info(f"Renombre detectado (delete+create): {del_info['name']} -> {created_path.name}")
                        
                        # Guardar el renombre detectado
                        self._pending_renames.append((old_path, event.src_path))
                        break
            
            # Consumir el delete emparejado
            if matched_delete:
                del self._pending_deletes[matched_delete]
        
        self._schedule_callback()
    
    def on_modified(self, event):
        """Maneja eventos de modificación"""
        if event.is_directory:
            return
        
        if self._should_ignore(event.src_path):
            return
        
        logger.debug(f"Archivo modificado detectado: {event.src_path}")
        self._schedule_callback()
    
    def _cleanup_pending_deletes(self):
        """Limpia deletes antiguos que no se emparejaron"""
        now = time.time()
        with self._lock:
            expired = [p for p, info in self._pending_deletes.items() 
                      if now - info["time"] > self._rename_window]
            for p in expired:
                del self._pending_deletes[p]


@dataclass
class SyncTask:
    """Representa una tarea de sincronización"""
    account_id: str
    source: str
    dest: str
    direction: SyncDirection
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    success: bool = False
    message: str = ""
    files_transferred: int = 0
    bytes_transferred: int = 0


class SyncManager:
    """
    Gestiona la sincronización automática de cuentas.
    
    Características:
    - Sincronización periódica en segundo plano
    - Cola de tareas de sincronización
    - Callbacks para reportar progreso
    - Manejo de errores y reintentos
    """
    
    def __init__(
        self, 
        rclone: RcloneWrapper, 
        account_manager: AccountManager
    ):
        """
        Inicializa el gestor de sincronización.
        
        Args:
            rclone: Wrapper de rclone
            account_manager: Gestor de cuentas
        """
        self.rclone = rclone
        self.account_manager = account_manager
        
        # Estado interno
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._active_syncs: set = set()  # Conjunto de IDs activos para concurrencia
        self._pending_syncs: set = set() # Cola de IDs que necesitan sync al terminar la actual
        
        # Historial de listados para detectar renombres manualmente si rclone falla
        self._last_listings: Dict[str, Dict[str, Any]] = {}  # {pair_id: {file_name: {size, time}}}
        
        
        # Callbacks
        self._on_sync_start: Optional[Callable[[str], None]] = None
        self._on_sync_complete: Optional[Callable[[SyncTask], None]] = None
        self._on_sync_error: Optional[Callable[[str, str], None]] = None
        self._on_progress: Optional[Callable[[str, float], None]] = None
        self._on_file_activity: Optional[Callable[[str, str, str, str], None]] = None  # (acc_id, name, action, path)
        
        
        # Callbacks
        self._last_sync_times: Dict[str, datetime] = {}
        
        # Watchdog
        self._observer = Observer() if WATCHDOG_AVAILABLE else None
        self._watchers: Dict[str, Any] = {} # Map de path -> watcher

    def set_callbacks(
        self,
        on_start=None,
        on_complete=None,
        on_error=None,
        on_progress=None,
        on_activity=None
    ):
        """Configura los callbacks para eventos de sincronización"""
        self._on_sync_start = on_start
        self._on_sync_complete = on_complete
        self._on_sync_error = on_error
        self._on_progress = on_progress
        self._on_file_activity = on_activity
    
    def start(self):
        """Inicia el servicio de sincronización en segundo plano"""
        if self._running:
            logger.warning("El servicio de sincronización ya está corriendo")
            return
        
        self._running = True
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        
        # Iniciar Watchdog
        if self._observer:
            try:
                self._observer.start()
                # Registrar carpetas
                for account in self.account_manager.get_enabled_accounts():
                    self._start_watching(account)
                logger.info("Monitor de cambios en tiempo real (Watchdog) iniciado")
            except Exception as e:
                logger.error(f"Error iniciando Watchdog: {e}")

        logger.info("Servicio de sincronización iniciado")
    
    def stop(self):
        """Detiene el servicio de sincronización"""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
            
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join()
            except: pass
            
        logger.info("Servicio de sincronización detenido")
    
    def _start_watching(self, account: Account):
        """Inicia la vigilancia de carpetas locales"""
        if not self._observer: return
        
        for pair in account.sync_pairs:
            if not pair.enabled: continue
            path = str(Path(pair.local_path).resolve())
            
            if path in self._watchers: continue
            
            try:
                # Pasamos la cuenta y la ruta base al handler para poder procesar renombres
                handler = ChangeHandler(
                    callback=lambda acc_id=account.id: self.sync_now(acc_id),
                    base_path=path
                )
                self._observer.schedule(handler, path, recursive=True)
                self._watchers[path] = {
                    "handler": handler,
                    "account_id": account.id,
                    "remote_name": account.remote_name,
                    "remote_path": pair.remote_path
                }
                logger.info(f"Vigilando cambios en: {path}")
            except Exception as e:
                logger.warning(f"No se pudo vigilar {path}: {e}")

    def is_running(self) -> bool:
        """Verifica si el servicio está corriendo"""
        return self._running
    
    def is_sync_active(self, sync_id: str) -> bool:
        """Verifica si una sincronización específica está activa"""
        with self._lock:
            return sync_id in self._active_syncs

    def get_active_syncs(self) -> list:
        """Obtiene lista de IDs activos"""
        with self._lock:
            return list(self._active_syncs)
    
    def _sync_loop(self):
        """Bucle principal de sincronización"""
        while self._running:
            try:
                self._check_and_sync()
            except Exception as e:
                logger.error(f"Error en bucle de sincronización: {e}")
            
            # Esperar antes de la siguiente verificación
            time.sleep(5)  # Verificar cada 5 segundos
    
    def _check_and_sync(self):
        """Verifica qué cuentas necesitan sincronización"""
        accounts = self.account_manager.get_enabled_accounts()
        now = datetime.now()
        
        for account in accounts:
            if account.status == SyncStatus.PAUSED:
                continue
            
            # Verificar si es momento de sincronizar
            last_sync = self._last_sync_times.get(account.id)
            
            if last_sync is None:
                # Primera sincronización
                self._sync_account(account)
            else:
                elapsed = (now - last_sync).total_seconds()
                if elapsed >= account.sync_interval:
                    self._sync_account(account)
    
    def _process_pending_renames(self, local_path: str, remote_name: str, remote_base_path: str):
        """
        Procesa renombres pendientes detectados por Watchdog haciendo rename server-side.
        Esto evita que bisync vea el rename como delete+create y duplique archivos.
        
        Args:
            local_path: Ruta local del par de sincronización
            remote_name: Nombre del remote rclone (ej: "gdrive")
            remote_base_path: Ruta base en el remote (ej: "My Drive/Sync")
        """
        # Buscar el handler asociado a esta ruta local
        local_path_resolved = str(Path(local_path).resolve())
        watcher_info = self._watchers.get(local_path_resolved)
        
        if not watcher_info or not isinstance(watcher_info, dict):
            return
        
        handler = watcher_info.get("handler")
        if not handler or not isinstance(handler, ChangeHandler):
            return
        
        # Obtener renombres pendientes
        pending_renames = handler.get_and_clear_renames()
        
        if not pending_renames:
            return
        
        logger.info(f"Procesando {len(pending_renames)} renombre(s) detectado(s) para {local_path}")
        
        for old_local_path, new_local_path in pending_renames:
            try:
                # Calcular rutas relativas
                old_path = Path(old_local_path)
                new_path = Path(new_local_path)
                base_path = Path(local_path_resolved)
                
                # Obtener ruta relativa al directorio base
                try:
                    old_relative = old_path.relative_to(base_path)
                    new_relative = new_path.relative_to(base_path)
                except ValueError:
                    logger.warning(f"Rutas fuera del directorio vigilado: {old_local_path} -> {new_local_path}")
                    continue
                
                # Construir rutas remotas
                old_remote = f"{remote_name}:{remote_base_path}/{old_relative}" if remote_base_path else f"{remote_name}:{old_relative}"
                new_remote = f"{remote_name}:{remote_base_path}/{new_relative}" if remote_base_path else f"{remote_name}:{new_relative}"
                
                # Limpiar posibles dobles barras
                old_remote = old_remote.replace("//", "/")
                new_remote = new_remote.replace("//", "/")
                
                logger.info(f"Renombrando en servidor: {old_remote} -> {new_remote}")
                
                # Ejecutar rename server-side
                success, msg = self.rclone.moveto(old_remote, new_remote)
                
                if success:
                    logger.info(f"Renombre server-side exitoso: {old_path.name} -> {new_path.name}")
                    # Emitir evento de actividad
                    if self._on_file_activity:
                        self._on_file_activity(
                            watcher_info.get("account_id", ""),
                            new_path.name,
                            "moved",
                            str(new_relative)
                        )
                else:
                    # Si falla (ej: archivo no existe en servidor), dejamos que bisync lo maneje
                    logger.warning(f"Renombre server-side falló (bisync lo manejará): {msg}")
                    
            except Exception as e:
                logger.error(f"Error procesando renombre {old_local_path} -> {new_local_path}: {e}")

    def _sync_account(self, account: Account):
        """
        Sincroniza una cuenta específica.
        
        Args:
            account: Cuenta a sincronizar
        """
        with self._lock:
            if account.id in self._active_syncs:
                return  # Ya está sincronizando esta cuenta
            self._active_syncs.add(account.id)
        
        task = SyncTask(
            account_id=account.id,
            source="",
            dest="",
            direction=account.sync_direction,
            started_at=datetime.now()
        )
        
        try:
            logger.info(f"Iniciando sincronización: {account.name}")
            
            if self._on_sync_start:
                self._on_sync_start(account.id)
            
            all_success = True
            error_messages = []
            now = datetime.now()

            for pair in account.sync_pairs:
                if not pair.enabled: continue

                pair_success, pair_message, pair_file_count = self._sync_single_pair(account, pair)
                task.files_transferred += pair_file_count

                if not pair_success:
                    all_success = False
                    error_messages.append(f"{Path(pair.local_path).name}: {pair_message}")

            # Finalizar tarea global
            task.success = all_success
            task.completed_at = datetime.now()
            task.message = "\n".join(error_messages) if error_messages else "Sincronización completada"
            
            self._last_sync_times[account.id] = datetime.now()
            self.account_manager.set_status(account.id, SyncStatus.IDLE if all_success else SyncStatus.ERROR)

            if not all_success and self._on_sync_error:
                self._on_sync_error(account.id, task.message)

            if self._on_sync_complete:
                self._on_sync_complete(task)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Excepción en sincronización: {error_msg}")
            self.account_manager.set_status(account.id, SyncStatus.ERROR, error_msg)
            
            task.success = False
            task.message = error_msg
            
            if self._on_sync_error:
                self._on_sync_error(account.id, error_msg)
                
        finally:
            with self._lock:
                self._active_syncs.discard(account.id)
    
    def sync_now(self, account_id: str) -> bool:
        """Sincroniza toda la cuenta (todos sus pares) inmediatamente"""
        if self.is_sync_active(account_id): return False
        
        account = self.account_manager.get_by_id(account_id)
        if not account: return False
        thread = threading.Thread(target=self._sync_account, args=(account,))
        thread.start()
        return True

    def sync_pair_now(self, account_id: str, pair_id: str) -> bool:
        """Sincroniza un par específico inmediatamente"""
        lock_id = f"{account_id}:{pair_id}"
        if self.is_sync_active(lock_id):
            logger.warning(f"Sincronización ya activa para {lock_id}")
            return False
            
        account = self.account_manager.get_by_id(account_id)
        if not account: return False
        
        pair = next((p for p in account.sync_pairs if p.id == pair_id), None)
        if not pair: return False

        thread = threading.Thread(target=self._sync_single_pair_thread, args=(account, pair, lock_id))
        thread.start()
        return True

    def _sync_single_pair_thread(self, account, pair, lock_id=None):
        """Hilo para sincronizar un solo par"""
        # Si no nos pasan lock_id, lo generamos (caso de uso interno raro pero posible)
        if not lock_id: lock_id = f"{account.id}:{pair.id}"

        with self._lock:
            if lock_id in self._active_syncs: return
            self._active_syncs.add(lock_id)

        try:
            if self._on_sync_start: self._on_sync_start(account.id)
            success, msg, file_count = self._sync_single_pair(account, pair)

            task = SyncTask(
                account_id=account.id,
                source=pair.local_path,
                dest=pair.remote_path,
                direction=pair.direction,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=success,
                message=msg,
                files_transferred=file_count
            )
            if self._on_sync_complete: self._on_sync_complete(task)
            self.account_manager.set_status(account.id, SyncStatus.IDLE if success else SyncStatus.ERROR)
        except Exception as e:
            logger.error(f"Error en sync manual de par: {e}")
        finally:
            with self._lock:
                self._active_syncs.discard(lock_id)

    def _sync_single_pair(self, account, pair) -> Tuple[bool, str, int]:
        """Lógica central para sincronizar un par (SyncPair)"""
        logger.info(f"Sincronizando par: {pair.local_path} -> {pair.remote_path}")

        # Buffer heurístico para renombres
        recent_events = []

        # Determinar estado
        pair_status = SyncStatus.SYNCING
        if not pair.last_sync: pair_status = SyncStatus.RESYNCING
        self.account_manager.set_status(account.id, pair_status)

        remote_path = f"{account.remote_name}:{pair.remote_path}"
        local_path = pair.local_path
        local_path_resolved = str(Path(local_path).resolve())
        
        # --- PROCESAR RENOMBRES SERVER-SIDE ANTES DEL BISYNC ---
        # Esto evita duplicación de archivos al renombrar localmente
        self._process_pending_renames(local_path, account.remote_name, pair.remote_path)
        
        # --- PAUSAR WATCHDOG DURANTE BISYNC ---
        # Esto evita que detecte los cambios de rclone (descargas, .partial, etc.)
        watcher_info = self._watchers.get(local_path_resolved)
        handler = None
        if watcher_info and isinstance(watcher_info, dict):
            handler = watcher_info.get("handler")
            if handler and isinstance(handler, ChangeHandler):
                handler.set_sync_in_progress(True)

        def run_bisync(resync_mode):
            nonlocal recent_events
            inner_success = True
            inner_message = "Sincronización completada"
            file_operations_count = 0

            # No enviar sync_start como actividad de archivo
            logger.debug(f"Iniciando sincronización para {account.name} - {Path(local_path).name}")

            # --- PRE-LIMPIEZA PROACTIVA ---
            # Si hay un lock file huérfano de una sesión anterior fallida, rclone fallará inmediatamente.
            # Intentamos detectarlo antes de empezar.
            try:
                bisync_cache = Path.home() / ".cache" / "rclone" / "bisync"
                if bisync_cache.exists():
                    # Buscamos archivos .lck que parezcan de este par
                    # Rclone nombra: path1..path2.lck donde pathX tiene / y : reemplazados
                    # Hacemos una búsqueda laxa para limpiar basura obvia
                    for f in bisync_cache.glob("*.lck"):
                        # Si el archivo tiene más de 5 minutos, asumimos que es zombie (rclone bisync no suele tardar tanto en lock sin actividad)
                        try:
                            mtime = f.stat().st_mtime
                            if time.time() - mtime > 300: # 5 minutos
                                logger.warning(f"Limpiando lock file antiguo/zombie: {f.name}")
                                f.unlink()
                        except: pass
            except: pass

            logger.info(f"Lanzando bisync (resync={resync_mode}) para {account.name} - {Path(local_path).name}")

            for line in self.rclone.bisync_stream(local_path, remote_path, resync=resync_mode):
                line = line.strip()
                if not line: continue
                
                line_lower = line.lower()
                
                # Señal de reintento desde rclone_wrapper (lock limpiado)
                if "RETRY_NEEDED" in line:
                    logger.info("Lock file limpiado, se reintentará automáticamente")
                    continue
                
                if any(x in line_lower for x in ["error", "fatal", "failed", "critical"]):
                    # Ignorar avisos que no son errores fatales de ejecución
                    if "ignoring" in line_lower:
                        continue

                    # No tratar como error fatal si es terminación normal por señal (SIGTERM = 143, SIGINT = 130)
                    if "código 143" in line or "código 130" in line or "signal" in line_lower or "terminated" in line_lower:
                        logger.info(f"rclone terminado por señal del sistema: {line}")
                        continue
                    
                    # Ignorar error de "cannot remove lockfile" - es benigno (ya lo eliminamos nosotros)
                    if "cannot remove lockfile" in line_lower or "no such file or directory" in line_lower:
                        logger.debug(f"Ignorando error benigno de lock file: {line}")
                        continue

                    # No enviar errores de lock file al panel de actividad (se manejan internamente con reintentos)
                    is_lock_error = "lock file found" in line_lower or "prior lock" in line_lower

                    # Todos estos errores se manejan internamente con lógica de reintentos, no enviar al panel de actividad
                    if is_lock_error:
                        logger.warning(f"rclone lock file error (handled internally): {line}")
                    else:
                        logger.error(f"rclone error fatal: {line}")

                    inner_success = False
                    inner_message = line

                    # No enviar errores internos de rclone al panel de actividad (se manejan con reintentos)
                elif "INFO" in line:
                    # Descartar líneas de resumen estadístico para no ensuciar la actividad
                    if "changes:" in line_lower or "delta" in line_lower or "synchronizing" in line_lower:
                        continue

                    if any(x in line_lower for x in ["copied", "updated", "deleted", "moved", "skipped", "removed"]):
                        try:
                            content = line.split("INFO")[-1].strip()
                            if content.startswith(":"): content = content[1:].strip()
                            
                            parts = [p.strip() for p in content.split(":")]
                            file_path = None
                            action = "uploading"

                            # Formato 1: "PathX: ruta/al/archivo: Acción" (3 o más partes)
                            if len(parts) >= 3 and ("Path1" in parts[0] or "Path2" in parts[0]):
                                file_path = parts[1]
                                action_text = parts[2].lower()
                                if "Path2" in parts[0] or "download" in action_text:
                                    action = "downloading"
                            
                            # Formato 2: "ruta/al/archivo: Acción" (2 partes, común en borrados o resync)
                            elif len(parts) >= 2:
                                # Asegurarse de que parts[0] no sea un nivel de log o PathX
                                if not any(x in parts[0] for x in ["Path1", "Path2", "INFO", "NOTICE"]):
                                    file_path = parts[0]
                                    action_text = parts[1].lower()
                                    if "download" in action_text: action = "downloading"
                            
                            if file_path:
                                # Limpiar el nombre del archivo
                                file_name = file_path.split("/")[-1]
                                
                                # Refinar acción por palabras clave en toda la línea
                                if any(x in line_lower for x in ["deleted", "removing", "removed", "unlink"]):
                                    action = "deleted"
                                elif any(x in line_lower for x in ["moved", "renamed", "renaming"]):
                                    action = "moved"
                                
                                # Validar que no estemos capturando una palabra clave de rclone como archivo
                                if file_name.lower() not in ["deleted", "copied", "updated", "moved", "skipped", "changes", "renamed"]:
                                    # Heurística de Renombres: Buffer temporal
                                    # Si vemos Deleted A y Uploading B (misma ext, misma carpeta) -> MOVED
                                    
                                    # Guardamos evento actual
                                    current_event = {
                                        "name": file_name,
                                        "path": file_path,
                                        "action": action,
                                        "time": time.time(),
                                        "ext": Path(file_path).suffix,
                                        "parent": str(Path(file_path).parent)
                                    }
                                    
                                    # Buscar coincidencia en eventos recientes (últimos 3 segs)
                                    matched_rename = False
                                    for prev in recent_events[:]:
                                        # Limpiar eventos viejos (> 5s)
                                        if current_event["time"] - prev["time"] > 5:
                                            recent_events.remove(prev)
                                            continue
                                            
                                        # Lógica de emparejamiento:
                                        # 1. Uno Deleted y otro Uploading
                                        # 2. Misma extensión (ej .zip)
                                        # 3. Misma carpeta padre
                                        if (prev["action"] == "deleted" and action == "uploading") or \
                                           (prev["action"] == "uploading" and action == "deleted"):
                                            
                                            if prev["ext"] == current_event["ext"] and \
                                               prev["parent"] == current_event["parent"]:
                                                
                                                # ¡Es un renombre! Emitimos MOVED con el nombre nuevo
                                                final_name = file_name if action == "uploading" else prev["name"]
                                                final_path = file_path if action == "uploading" else prev["path"]
                                                
                                                if self._on_file_activity:
                                                    # Avisar que fue renombrado (sobrescribimos la acción anterior visualmente si se pudo, 
                                                    # pero como es asíncrono, mejor emitimos el evento limpio)
                                                    self._on_file_activity(account.id, final_name, "moved", final_path)
                                                
                                                matched_rename = True
                                                recent_events.remove(prev) # Consumir evento
                                                break
                                    
                                    if not matched_rename:
                                        recent_events.append(current_event)
                                        # Emitir evento normal si no se emparejó (aún)
                                        # Nota: Esto puede mostrar "Deleted" brevemente antes del "Moved",
                                        # pero es mejor que perder el evento si no se empareja.
                                        if self._on_file_activity:
                                            self._on_file_activity(account.id, file_name, action, file_path)
                                            file_operations_count += 1
                                        
                        except Exception as e:
                            logger.debug(f"Error parseando línea INFO: {e}")

           # No emitir sync_complete como actividad de archivo, solo devolver el conteo
            return inner_success, inner_message, file_operations_count

        # Ejecución con try/finally para garantizar que Watchdog se reactive
        try:
            with self._lock:
                # Actualizar estado
                pair.status = SyncStatus.SYNCING
                self.account_manager.update(account)
            
            # 1. Intentar Sincronización Normal (Primero confiamos en rclone)
            success, message, file_count = run_bisync(not pair.last_sync)

            # Reintento si falla (Protocolo de REPARACIÓN GRADUAL)
            if not success:
                # Solo si el error es de LOCK FILE prior, intervenimos
                if "lock file found" in message or "prior lock" in message:
                    logger.warning(f"Bloqueo detectado para {account.name}. Intentando desbloqueo...")

                    try:
                        # Estrategia 1: Usar la ruta exacta si el mensaje de error nos la dio
                        lock_path_extracted = None
                        if "prior lock file found: " in message:
                            lock_path_extracted = message.split("prior lock file found: ")[-1].strip()

                        if lock_path_extracted and Path(lock_path_extracted).exists():
                             logger.info(f"Eliminando LOCK específico reportado: {lock_path_extracted}")
                             Path(lock_path_extracted).unlink()
                        else:
                            # Estrategia 2: Búsqueda heurística (Fallback)
                            cache_path = Path.home() / ".cache" / "rclone" / "bisync"
                            if cache_path.exists():
                                safe_local = "".join(c if c.isalnum() else "_" for c in local_path)
                                for f in cache_path.glob("*.lck"):
                                    if safe_local in f.name or "lxdrive" in f.name:
                                        logger.info(f"Desbloqueando sesión (heurística): {f.name}")
                                        f.unlink()
                    except FileNotFoundError:
                        pass # Ya se borró, mejor
                    except Exception as e:
                        logger.warning(f"No se pudo limpiar lock: {e}")

                # Intento 2: Reintentar NORMAL tras desbloqueo
                logger.info("Reintentando sincronización tras desbloqueo...")
                time.sleep(1) # Dar un respiro al filesystem
                success, message, retry_count = run_bisync(False)
                file_count += retry_count

            # Si sigue fallando (o no era lock), vamos a resync
            if not success:
                logger.warning("Iniciando LIMPIEZA PROFUNDA (Resync)...")
                try:
                    # Limpiar todo lo relacionado para forzar resync
                    cache_path = Path.home() / ".cache" / "rclone" / "bisync"
                    if cache_path.exists():
                        safe_local = "".join(c if c.isalnum() else "_" for c in local_path)
                        for f in cache_path.glob("*"):
                            if safe_local in f.name:
                                f.unlink()
                except: pass

                # Intento 3 con resync forzado
                success, message, resync_count = run_bisync(True)
                file_count += resync_count

            if success:
                pair.last_sync = datetime.now().isoformat()
                self.account_manager.update(account)

            return success, message, file_count
        
        finally:
            # --- REANUDAR WATCHDOG DESPUÉS DE BISYNC (siempre, incluso si hay excepción) ---
            if handler and isinstance(handler, ChangeHandler):
                handler.set_sync_in_progress(False)

    def pause_account(self, account_id: str):
        """Pausa la sincronización de una cuenta"""
        self.account_manager.set_status(account_id, SyncStatus.PAUSED)
        logger.info(f"Cuenta pausada: {account_id}")
    
    def resume_account(self, account_id: str):
        """Reanuda la sincronización de una cuenta"""
        self.account_manager.set_status(account_id, SyncStatus.IDLE)
        logger.info(f"Cuenta reanudada: {account_id}")
    
    def pause_all(self):
        """Pausa todas las sincronizaciones"""
        for account in self.account_manager.get_all():
            self.pause_account(account.id)
    
    def resume_all(self):
        """Reanuda todas las sincronizaciones"""
        for account in self.account_manager.get_all():
            if account.sync_enabled:
                self.resume_account(account.id)
