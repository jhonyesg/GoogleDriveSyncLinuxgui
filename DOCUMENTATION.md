# lX_Drive - Documentación Técnica Completa

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Documentación por Módulo](#documentación-por-módulo)
4. [Configuración del Sistema](#configuración-del-sistema)
5. [Manuales de Usuario](#manuales-de-usuario)
6. [Solución de Problemas](#solución-de-problemas)
7. [Guía de Desarrollador](#guía-de-desarrollador)

---

## Introducción

lX_Drive es una aplicación de escritorio para Linux Mint que gestiona la sincronización bidireccional entre carpetas locales y proveedores de almacenamiento en la nube. Utiliza **rclone** como motor backend, lo que permite soportar múltiples proveedores simultáneamente.

### Características Principales

- **Multi-proveedor**: Google Drive, OneDrive, Dropbox y más (a través de rclone)
- **VFS Mount**: Montaje de almacenamiento cloud como sistema de archivos local
- **Sincronización Bidireccional**: Usando rclone bisync
- **Interfaz GTK3 Nativa**: Integración perfecta con Linux Mint (Cinnamon, MATE, XFCE)
- **Temas**: Claro, Oscuro o sistema
- **Autoarranque**: Servicios systemd para inicio automático
- **Tray Icon**: Operación en segundo plano con notificaciones
- **Logs Integrados**: Visor de registros en tiempo real

### Dependencias del Sistema

```bash
# Requisitos mínimos
- Linux Mint 20+ (Ubuntu 20.04+ compatible)
- Python 3.10+
- rclone (motor de sincronización)
- GTK3 (gir1.2-gtk-3.0)
- FUSE3 (sistema de archivos virtual)
- systemd (para servicios de usuario)
```

---

## Arquitectura del Sistema

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                      Interfaz GTK3                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Main Window  │  │ Accounts     │  │ Tasks Panel  │      │
│  │  + Tray Icon │  │   Panel      │  │              │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      Lógica de Negocio                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ TaskManager  │  │ RcloneMgr    │  │ MountMgr     │      │
│  │              │  │              │  │              │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         ▼                 ▼                 ▼               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Systemd Manager                         │   │
│  │            (Servicios de usuario)                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │                 │                 │
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      Motor rclone                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Rclone Mount │  │ Rclone Bisync │  │ Rclone Config│      │
│  │   VFS        │  │   (sync)      │  │   Wizard     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      Almacenamiento                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Cloud Mounts │  │ Local FS     │  │ Config Files │      │
│  │ (FUSE)       │  │              │  │  (JSON)      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Estructura de Directorios

```
lX_Drive/
├── lxdrive/                    # Código fuente principal
│   ├── __init__.py            # Versionado y metadatos
│   ├── config.py              # Configuración y constantes
│   ├── main.py                # Punto de entrada
│   │
│   ├── backend/               # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── models.py          # Modelos de datos (Task, Remote, etc.)
│   │   ├── rclone_manager.py  # Gestión de rclone
│   │   ├── mount_manager.py   # Gestión de montajes VFS
│   │   ├── sync_manager.py    # Gestión de sincronización bisync
│   │   └── systemd_manager.py # Creación de servicios systemd
│   │
│   ├── gui/                   # Interfaz gráfica
│   │   ├── __init__.py
│   │   ├── main_window.py     # Ventana principal
│   │   ├── accounts_panel.py  # Panel de cuentas
│   │   ├── tasks_panel.py     # Panel de tareas
│   │   ├── settings_dialog.py # Configuración
│   │   ├── log_viewer.py      # Visor de logs
│   │   ├── add_account_dialog.py  # Wizard de cuentas
│   │   ├── add_task_dialog.py    # Wizard de tareas
│   │   ├── task_dialog.py        # Diálogo de tarea
│   │   ├── remote_folder_dialog.py # Selección de carpetas
│   │   ├── styles.py          # CSS de temas
│   │   └── translations.py    # Traducciones
│   │
│   └── utils/                 # Utilidades
│       ├── __init__.py
│       ├── logger.py          # Sistema de logging
│       ├── autostart.py       # Gestión de autoarranque
│       └── desktop_entry.py   # Creación de .desktop files
│
├── data/                       # Datos del proyecto
│   └── icons/                 # Iconos SVG
│       ├── lxdrive.svg
│       ├── google-drive.svg
│       ├── onedrive.svg
│       └── dropbox.svg
│
├── services/                   # Templates systemd
│   ├── lxdrive-mount@.service # Servicio de montaje
│   └── lxdrive-sync@.service  # Servicio de sincronización
│
├── build-deb.sh               # Script para crear .deb
├── install.sh                  # Script de instalación
├── uninstall.sh                # Script de desinstalación
├── setup.py                    # Configuración de Python packaging
├── requirements.txt            # Dependencias Python
└── README.md                   # Documentación usuario
```

---

## Documentación por Módulo

### 1. Configuración (`lxdrive/config.py`)

Define toda la configuración global, constantes y rutas del sistema.

**Clases Principales:**

```python
class TaskType(Enum):
    MOUNT = "mount"      # Montaje VFS
    BISYNC = "bisync"    # Sincronización bidireccional

class TaskStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    SYNCING = "syncing"

class Theme(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"
```

**Configuración del Sistema:**

```python
APP_NAME = "lX_Drive"
APP_ID = "com.lxdrive.app"
VERSION = "1.0.0"

# Directorios
HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "lxdrive"
DATA_DIR = HOME / ".local" / "share" / "lxdrive"
LOG_DIR = CONFIG_DIR / "logs"
CACHE_DIR = HOME / ".cache" / "lxdrive"
SYSTEMD_USER_DIR = HOME / ".config" / "systemd" / "user"
AUTOSTART_DIR = HOME / ".config" / "autostart"
APPLICATIONS_DIR = HOME / ".local" / "share" / "applications"
LOCAL_BIN_DIR = HOME / ".local" / "bin"
```

**Proveedores Soportados:**

```python
SUPPORTED_PROVIDERS = {
    "gdrive": {
        "name": "Google Drive",
        "rclone_type": "drive",
        "icon": "google-drive",
    },
    "onedrive": {
        "name": "OneDrive",
        "rclone_type": "onedrive",
        "icon": "onedrive",
    },
    "dropbox": {
        "name": "Dropbox",
        "rclone_type": "dropbox",
        "icon": "dropbox",
    },
}
```

**Función de Utilidad:**

```python
def ensure_directories():
    """Crea todos los directorios necesarios si no existen"""
```

---

### 2. Backend - Modelos (`lxdrive/backend/models.py`)

Define las estructuras de datos usadas en toda la aplicación.

**RemoteInfo**

```python
@dataclass
class RemoteInfo:
    name: str              # Nombre del remote (ej: "gdrive")
    provider: str          # Proveedor (ej: "gdrive", "onedrive")
    type: str              # Tipo de rclone (ej: "drive")
    is_configured: bool    # Si está configurado en rclone
```

**QuotaInfo**

```python
@dataclass
class QuotaInfo:
    used: int              # Espacio usado en bytes
    total: int             # Espacio total en bytes
    available: int         # Espacio disponible en bytes

    # Propiedades human-readable
    used_human: str        # "12.5 GB"
    total_human: str       # "100 GB"
    available_human: str   # "87.5 GB"
    percentage: float      # 12.5% (0-100)
```

**TaskManager**

```python
@dataclass
class Task:
    id: str                        # UUID único
    name: str                      # Nombre descriptivo
    remote_name: str               # Nombre del remote
    remote_path: str               # Ruta remota (opcional)
    local_path: Path               # Ruta local (Path object)
    task_type: TaskType            # MOUNT o BISYNC
    enabled: bool                  # Si está activa
    autostart: bool                # Si inicia con el sistema
    last_sync: datetime            # Última sincronización (None si no sync)
    status: TaskStatus              # Estado actual
    created_at: datetime            # Fecha de creación
    updated_at: datetime            # Última actualización

@dataclass
class TaskManager:
    tasks: list[Task]              # Lista de tareas cargadas

    def load() -> TaskManager
    def save() -> None
    def add_task(task: Task) -> None
    def update_task(task: Task) -> None
    def remove_task(task_id: str) -> None
    def get_task(task_id: str) -> Optional[Task]
    def find_tasks(remote_name: str) -> list[Task]
```

**MountInfo**

```python
@dataclass
class MountInfo:
    remote_name: str          # Nombre del remote
    mount_point: Path          # Punto de montaje
    pid: Optional[int]        # PID del proceso rclone (si es daemon)
    is_active: bool           # Si está montado actualmente
```

---

### 3. Backend - Rclone Manager (`lxdrive/backend/rclone_manager.py`)

Gestiona la interacción con rclone para configuración y consultas.

**Clase Principal:**

```python
class RcloneManager:
    def __init__(self)
        self.rclone_path: Optional[str]  # Ruta a rclone

    # Verificación
    def is_available() -> bool
    def get_version() -> Optional[str]

    # Gestión de Remotes
    def list_remotes() -> list[str]
    def get_remote_info(name: str) -> Optional[RemoteInfo]
    def create_remote_interactive(name: str, provider: str) -> bool
    def delete_remote(name: str) -> bool
    def check_connection(name: str) -> tuple[bool, str]
    def get_quota(name: str) -> Optional[QuotaInfo]

    # Configuración
    def _read_config() -> dict
    def _write_config(config: dict) -> None
    def _find_rclone() -> Optional[str]
```

**Flujo de Configuración:**

1. Verificar que rclone esté instalado
2. Crear remote interactivo usando `rclone config create`
3. Especificar tipo (drive, onedrive, dropbox, etc.)
4. Probar conexión
5. Guardar configuración en `~/.config/rclone/rclone.conf`

**Ejemplo de Configuración:**

```ini
[gdrive]
type = drive
client_id = <id>
client_secret = <secret>
root_folder_id = <id>
token = <token>
```

---

### 4. Backend - Mount Manager (`lxdrive/backend/mount_manager.py`)

Gestiona montajes VFS de rclone.

**Clase Principal:**

```python
class MountManager:
    def __init__(self)
        self.rclone_path: Optional[str]
        self.active_mounts: dict[str, MountInfo]
        self._verify_fuse_available()

    # Verificación
    def check_mount_requirements() -> tuple[bool, str]
    def is_available() -> bool

    # Gestión de Montajes
    def mount(
        remote_name: str,
        local_path: Path,
        options: dict = None,
        daemon: bool = True
    ) -> tuple[bool, str]

    def unmount(mount_point: Path) -> tuple[bool, str]
    def list_mounts() -> list[MountInfo]
    def is_mounted(mount_point: Path) -> bool

    # Procesos
    def get_process_info(mount_point: Path) -> Optional[MountInfo]
```

**Opciones por Defecto:**

```python
{
    "vfs-cache-mode": "full",          # Caché completo (recomendado)
    "vfs-cache-max-age": "24h",        # Max antigüedad 24h
    "vfs-cache-max-size": "10G",       # Max tamaño 10GB
    "buffer-size": "64M",              # Buffer 64MB
    "dir-cache-time": "72h",           # Cache directorios 72h
    "poll-interval": "15s",            # Poll cada 15s
}
```

**Proceso de Montaje:**

1. Verificar rclone y FUSE
2. Verificar permisos en directorio local
3. Verificar que no esté montado
4. Ejecutar `rclone mount` con opciones
5. Usar `--daemon` para ejecutar en background
6. Guardar PID para gestión posterior

**Ejemplo de Comando:**

```bash
rclone mount gdrive: /home/user/Cloud/gdrive \
    --vfs-cache-mode full \
    --vfs-cache-max-age 24h \
    --vfs-cache-max-size 10G \
    --buffer-size 64M \
    --dir-cache-time 72h \
    --poll-interval 15s \
    --log-file ~/.config/lxdrive/logs/mount-gdrive.log \
    --daemon
```

---

### 5. Backend - Sync Manager (`lxdrive/backend/sync_manager.py`)

Gestiona sincronización bidireccional usando rclone bisync.

**Clase Principal:**

```python
class SyncManager:
    def __init__(self)
        self.rclone_path: Optional[str]
        self.active_syncs: dict

    # Verificación
    def check_sync_requirements() -> tuple[bool, str]
    def validate_local_path(local_path: Path) -> tuple[bool, str]

    # Ejecución
    def run_sync(
        task: SyncTask,
        watch: bool = False,
        dry_run: bool = False,
        force_resync: bool = False,
        _retrying: bool = False
    ) -> tuple[bool, str]

    def pause_sync(task_id: str) -> bool
    def resume_sync(task_id: str) -> bool
    def stop_sync(task_id: str) -> bool

    # Consulta
    def get_sync_status(task_id: str) -> tuple[TaskStatus, str]

    def _validate_remote(remote_name: str) -> tuple[bool, str]
    def _create_bisync_command(
        local_path: Path,
        remote_name: str,
        remote_path: str,
        options: dict
    ) -> list[str]
```

**Flujo de Sincronización:**

1. Verificar rclone y FUSE
2. Validar ruta local
3. Validar remote configurado
4. Crear comando bisync con opciones
5. Ejecutar en background (puede usar watch=True)
6. Actualizar estado del task

**Opciones de Bisync:**

```python
{
    "--resync": True,                 # Forzar resync inicial
    "--watch": True,                  # Monitorear cambios
    "--track-renames": True,          # Seguir renombres
    "--drive-import-formats": [
        "docx,xlsx,pptx,doc,xls,ppt",
        "odt,ods,odp"
    ],                                # Formatos a importar
    "--resync-period": "3m",          # Período de resync
}
```

**Resync Explícito:**

Si `force_resync=True`, ejecuta un resync completo:
```bash
rclone bisync /local /remote \
    --resync \
    --watch
```

---

### 6. Backend - Systemd Manager (`lxdrive/backend/systemd_manager.py`)

Gestiona servicios systemd de usuario para automatización.

**Clase Principal:**

```python
class SystemdManager:
    SERVICE_MOUNT_TEMPLATE = """..."""  # Template servicio montaje
    SERVICE_SYNC_TEMPLATE = """..."""   # Template servicio sync

    def __init__(self)
        self.systemctl_path: Optional[str]
        self.rclone_path: Optional[str]
        self.user_dir: Path

    # Verificación
    def is_available() -> bool

    # Gestión de Servicios
    def create_mount_service(
        remote_name: str,
        mount_path: Path
    ) -> tuple[bool, str]

    def create_sync_service(
        task_id: str,
        remote_name: str,
        remote_path: str,
        local_path: Path
    ) -> tuple[bool, str]

    def remove_service(service_name: str) -> bool
    def enable_service(service_name: str) -> bool
    def disable_service(service_name: str) -> bool
    def get_service_status(service_name: str) -> tuple[bool, str]

    # Utilidades
    def _get_service_name(name: str, service_type: str) -> str
    def _create_service_content(template: str, params: dict) -> str
```

**Template Servicio de Montaje:**

```ini
[Unit]
Description=lX_Drive Mount for {remote_name}
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart={rclone_path} mount {remote_name}: {mount_path} \
    --vfs-cache-mode full \
    --vfs-cache-max-age 24h \
    --vfs-cache-max-size 10G \
    --buffer-size 64M \
    --dir-cache-time 72h \
    --poll-interval 15s \
    --log-level INFO \
    --log-file {log_path}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

**Template Servicio de Sync:**

```ini
[Unit]
Description=lX_Drive Bisync for {task_id}
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart={rclone_path} bisync {local_path} {remote_name}:{remote_path} \
    --resync \
    --watch \
    --log-level INFO \
    --log-file {log_path}
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
```

**Flujo de Creación:**

1. Generar nombre seguro del servicio
2. Construir contenido del servicio
3. Crear archivo `.service` en `~/.config/systemd/user/`
4. Recargar systemd user
5. Habilitar servicio

---

### 7. GUI - Main Window (`lxdrive/gui/main_window.py`)

Ventana principal de la aplicación con gestión de tray icon.

**Clase LXDriveApp (Gtk.Application):**

```python
class LXDriveApp(Gtk.Application):
    def __init__(self)
        self.main_window: Optional[MainWindow] = None

    def do_activate()
        start_hidden = "--tray" in sys.argv
        # Crear o mostrar ventana principal

    def do_startup()
        # Crear actions de la app
```

**Clase MainWindow (Gtk.ApplicationWindow):**

```python
class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app, start_hidden=False)
        self.app = app
        self.config = AppConfig.load()
        self.task_manager = TaskManager()
        self.rclone_manager = RcloneManager()
        self.mount_manager = MountManager()
        self.sync_manager = SyncManager()
        self.systemd_manager = SystemdManager()

    # Setup
    def _setup_window()
    def _setup_header_bar()
    def _setup_content()
    def _setup_tray_icon()
    def _apply_settings()
    def _setup_logger()

    # Gestión de Tray Icon
    def _setup_tray_icon()
    def _on_show_window()
    def _on_minimize_to_tray()
    def _on_tray_settings()
    def _on_tray_quit()

    # Eventos
    def _on_close_request()
    def _on_refresh()
    def _on_account_added()
    def _on_account_removed()
    def _on_task_changed()

    # Diálogos
    def show_settings()
    def show_about()
```

**Tray Icon Integration:**

```python
def _setup_tray_icon(self):
    if AppIndicator3 is None:
        print("AppIndicator3 no disponible")
        return

    icon_path = "/usr/share/icons/hicolor/128x128/apps/lxdrive.png"

    self.indicator = AppIndicator3.Indicator.new(
        APP_NAME.lower(),
        icon_path,
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS
    )
    self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()
    # ... opciones show, hide, settings, quit
```

**Contenido de la Ventana:**

- **HeaderBar**: Título + botones (refresh, settings, about)
- **StackSwitcher**: Navegación entre pestañas
- **Stack**: Contenido principal (3 paneles)
- **StatusBar**: Estado actual

**Pestañas:**

1. **Accounts Panel**: Lista de remotes configurados
2. **Tasks Panel**: Lista de tareas de montaje/sync
3. **Logs Panel**: Visor de logs en tiempo real

---

### 8. GUI - Accounts Panel (`lxdrive/gui/accounts_panel.py`)

Panel de gestión de cuentas (remotes) de rclone.

**Funcionalidades:**

- Listar todos los remotes configurados
- Verificar conexión con cada remote
- Ver cuota de espacio usado
- Crear nuevo remote (Wizard)
- Eliminar remote existente
- Abrir punto de montaje en archivo
- Traducir nombres de proveedores

**Widget Principal:**

```python
class AccountsPanel(Gtk.Box):
    def __init__(
        self,
        rclone_manager: RcloneManager,
        on_account_added: Callable,
        on_account_removed: Callable,
        config: AppConfig
    )

    def refresh() -> None
    def add_account(self) -> None
    def remove_account(self, remote_name: str) -> None
    def verify_connection(self, remote_name: str) -> None
    def show_quota(self, remote_name: str) -> None
    def open_mount_point(self, remote_name: str) -> None
    def update_config(self, config: AppConfig) -> None
```

**Elementos de UI:**

- ListBox con filas de remotes
- Botón "Add Account" (ícono +)
- Botón "Verify" (comprobar conexión)
- Botón "Open" (abrir carpeta)
- Botón "Remove" (eliminar)
- Barra de estado con cuota

---

### 9. GUI - Tasks Panel (`lxdrive/gui/tasks_panel.py`)

Panel de gestión de tareas (montajes y sincronización).

**Funcionalidades:**

- Listar todas las tareas
- Crear nuevas tareas (Wizard)
- Activar/desactivar tareas
- Configurar autoarranque
- Ejecutar sync manual
- Verificar estado
- Eliminar tareas

**Widget Principal:**

```python
class TasksPanel(Gtk.Box):
    def __init__(
        self,
        task_manager: TaskManager,
        rclone_manager: RcloneManager,
        mount_manager: MountManager,
        sync_manager: SyncManager,
        systemd_manager: SystemdManager,
        on_task_changed: Callable
    )

    def refresh() -> None
    def add_task(self) -> None
    def toggle_task(self, task_id: str) -> None
    def enable_autostart(self, task_id: str) -> None
    def disable_autostart(self, task_id: str) -> None
    def start_sync(self, task_id: str) -> None
    def remove_task(self, task_id: str) -> None
```

**Elementos de UI:**

- ListBox con filas de tareas
- Botón "Add Task" (ícono +)
- Toggle switches para enabled/autostart
- Botón "Sync" (ejecutar sync manual)
- Botón "Remove" (eliminar)
- Columna de estado

**Tipos de Tareas:**

1. **Mount (VFS)**: Montaje de almacenamiento cloud
2. **Bidirectional Sync**: Sincronización bidireccional

---

### 10. GUI - Add Account Dialog (`lxdrive/gui/add_account_dialog.py`)

Wizard para crear nuevas cuentas de nube.

**Flujo:**

1. **Step 1**: Seleccionar proveedor (grid de iconos)
2. **Step 2**: Configurar rclone interactivo
3. **Verify**: Probar conexión
4. **Complete**: Guardar

**Widgets:**

- Box de selección de proveedores (gdrive, onedrive, dropbox, etc.)
- Entry para nombre custom
- Progreso bar
- Terminal embebido para output de rclone
- Botón Next/Previous/Cancel

---

### 11. GUI - Add Task Dialog (`lxdrive/gui/add_task_dialog.py`)

Wizard para crear nuevas tareas.

**Flujo:**

1. **Type Selection**: Mount vs Sync
2. **Remote Selection**: Seleccionar remote configurado
3. **Path Selection**:
   - Para Mount: Seleccionar carpeta local
   - Para Sync: Seleccionar ruta remota y local
4. **Options**:
   - Enable task
   - Auto-start
5. **Complete**: Crear tarea

**Widgets:**

- Radio buttons para tipo
- ComboBox para remotes
- FileChooserButton para carpetas
- CheckButtons para opciones
- Formulario de entrada

---

### 12. GUI - Log Viewer (`lxdrive/gui/log_viewer.py`)

Visor de logs en tiempo real.

**Funcionalidades:**

- Mostrar logs por niveles (INFO, WARNING, ERROR)
- Auto-scroll
- Filtrar por nivel
- Copiar logs
- Limpiar

**Widget:**

```python
class LogViewer(Gtk.Box):
    def __init__(self)

    def append_log(message: str, level: str) -> None
    def clear() -> None
    def set_filter(self, level: Optional[str]) -> None
```

**Handler Logging:**

```python
class GUILogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        for callback in self.callbacks:
            callback(log_entry, record.levelno)
```

---

### 13. GUI - Settings Dialog (`lxdrive/gui/settings_dialog.py`)

Diálogo de configuración de la aplicación.

**Secciones:**

1. **Appearance**:
   - Theme selector (Light/Dark/System)
   - Preview

2. **General**:
   - Auto-start app
   - Mount base path

3. **Advanced**:
   - Log level (DEBUG/INFO/WARNING/ERROR)
   - Timeout

**Widget:**

```python
class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, config: AppConfig)

    def show()
    def apply_settings() -> None
```

---

### 14. GUI - Styles (`lxdrive/gui/styles.py`)

Sistema de temas CSS.

**Temas:**

1. **LIGHT_THEME**:
   - Fondo por defecto
   - Listas con fondo claro
   - Selección con color de sistema

2. **DARK_THEME**:
   - Fondo #1e1e1e
   - Listas #2d2d2d
   - Botones #3d3d3d

3. **SYSTEM_THEME**:
   - Usa gtk-settings para determinar dark/light

**Funciones:**

```python
def get_css_provider(theme: str = "system") -> Gtk.CssProvider
def apply_theme(theme: str = "system") -> None
```

---

### 15. Utils - Logger (`lxdrive/utils/logger.py`)

Sistema de logging completo.

**Logger:**

- RotatingFileHandler (5MB max, 5 backups)
- ConsoleHandler (INFO)
- GUILogHandler (DEBUG para GUI)

**Funciones:**

```python
def setup_logger(name, log_level, log_dir) -> logging.Logger
def get_logger() -> logging.Logger
def add_gui_log_callback(callback)
def set_log_level(level: str)
```

**Output de Logs:**

```
2026-03-12 14:30:15 - lxdrive - INFO - lX_Drive v1.0.0 started
2026-03-12 14:30:16 - lxdrive - INFO - Indicador creado
2026-03-12 14:30:20 - lxdrive - INFO - Montando gdrive...
2026-03-12 14:30:22 - lxdrive - INFO - Montado: gdrive
```

---

### 16. Utils - Autostart (`lxdrive/utils/autostart.py`)

Gestión de autoarranque en Linux.

**Funciones:**

```python
def enable_autostart() -> bool
def disable_autostart() -> bool
def is_autostart_enabled() -> bool
```

**Implementación:**

- Crea archivo `~/.config/autostart/lxdrive.desktop`
- Usa `@reboot` con systemd

---

### 17. Utils - Desktop Entry (`lxdrive/utils/desktop_entry.py`)

Crea .desktop files para el menú.

**Funciones:**

```python
def create_desktop_entry(
    name: str,
    exec: str,
    icon: str,
    category: str
) -> None
```

**Contenido:**

```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=lX_Drive
Comment=Cloud sync manager
Exec=lxdrive
Icon=lxdrive
Terminal=false
Categories=Network;FileTransfer;GTK;
StartupNotify=true
```

---

## Configuración del Sistema

### Archivos de Configuración

**1. Configuración de la Aplicación**

```json
{
    "theme": "system",
    "autostart_app": false,
    "log_level": "INFO",
    "mount_base_path": "/home/user/Cloud",
    "window_width": 900,
    "window_height": 600
}
```

**Ubicación**: `~/.config/lxdrive/config.json`

**2. Tareas Definidas**

```json
[
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Google Drive Mount",
        "remote_name": "gdrive",
        "remote_path": "",
        "local_path": "/home/user/Cloud/gdrive",
        "task_type": "mount",
        "enabled": true,
        "autostart": true,
        "last_sync": null,
        "status": "idle",
        "created_at": "2026-03-12T14:30:00Z",
        "updated_at": "2026-03-12T14:30:00Z"
    }
]
```

**Ubicación**: `~/.config/lxdrive/tasks.json`

**3. Configuración de rclone**

```ini
[gdrive]
type = drive
client_id = <id>
client_secret = <secret>
root_folder_id = <id>
token = <token>
```

**Ubicación**: `~/.config/rclone/rclone.conf`

---

### Servicios Systemd de Usuario

**Ubicación**: `~/.config/systemd/user/`

**Servicios:**

1. `lxdrive-mount@{remote}.service`
2. `lxdrive-sync@{task_id}.service`

**Para gestionar:**

```bash
# Listar servicios
systemctl --user list-units lxdrive-*

# Ver estado
systemctl --user status lxdrive-mount@gdrive.service

# Iniciar
systemctl --user start lxdrive-mount@gdrive.service

# Detener
systemctl --user stop lxdrive-mount@gdrive.service

# Habilitar (autoarranque)
systemctl --user enable lxdrive-mount@gdrive.service

# Deshabilitar
systemctl --user disable lxdrive-mount@gdrive.service

# Recargar daemon
systemctl --user daemon-reload

# Ver logs
journalctl --user -u lxdrive-mount@gdrive.service
```

---

### Variables de Entorno

**Opciones recomendadas:**

```bash
# Para debugging
export RCLONE_VERBOSITY=vvv

# Para probar
cd /usr/share/lxdrive && python3 -m lxdrive.main --debug
```

---

## Manuales de Usuario

### Primeros Pasos - Instalación

#### Opción 1: Paquete Debian

```bash
# Instalar .deb
sudo dpkg -i lxdrive_1.0.0_all.deb

# Actualizar cache de iconos
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor/

# Ejecutar
lxdrive
```

#### Opción 2: Desde Script

```bash
# Descargar código fuente
git clone https://github.com/lxdrive/lxdrive.git
cd lX_Drive

# Instalar dependencias
sudo apt install rclone python3 python3-gi gir1.2-gtk-3.0 fuse3

# Ejecutar script de instalación
chmod +x install.sh
./install.sh
```

### Primeros Pasos - Configuración

**1. Crear Cuenta de Nube**

1. Abre lX_Drive
2. Ve a la pestaña **Accounts**
3. Haz clic en el botón **+** (Add Account)
4. Selecciona tu proveedor (Google Drive, OneDrive, etc.)
5. Dale un nombre al remote (ej: "gdrive")
6. Sigue el asistente de rclone
   - Elige el tipo de proveedor
   - Configura las credenciales
   - Prueba la conexión
7. Selecciona la carpeta en tu nube para usar como raíz (opcional)
8. Guarda la configuración

**2. Crear Montaje VFS**

1. Ve a la pestaña **Tasks**
2. Haz clic en el botón **+** (Add Task)
3. Selecciona **Mount (VFS)**
4. Elige la cuenta creada
5. Selecciona la carpeta local donde montar (ej: `~/Cloud/gdrive`)
6. Activa el toggle "Enabled"
7. (Opcional) Activa "Auto-start" para iniciar al boot
8. Haz clic en **Create**

**3. Crear Sincronización**

1. Ve a la pestaña **Tasks**
2. Haz clic en el botón **+** (Add Task)
3. Selecciona **Bidirectional Sync**
4. Elige la cuenta y la ruta remota
5. Selecciona la carpeta local
6. Activa el toggle "Enabled"
7. (Opcional) Activa "Auto-start"
8. Haz clic en **Create**

### Uso Diario

**1. Ver Estado de Montajes**

Ve a la pestaña **Tasks**:
- Verás las tareas de montaje activas
- Columna "Status" muestra si está montado
- Botón "Sync" para ejecutar manualmente

**2. Verificar Conexión**

En la pestaña **Accounts**:
- Botón "Verify" para probar conexión con la nube
- Se muestra la cuota de espacio usado

**3. Ver Logs**

Ve a la pestaña **Logs**:
- Verás todos los mensajes del sistema
- Puedes filtrar por nivel (INFO, WARNING, ERROR)
- Botón "Copy" para copiar

**4. Minimizar a Tray Icon**

- Haz clic en la "X" de la ventana
- Se minimiza a la bandeja del sistema
- Haz clic derecho en el icono para opciones:
  - Show Window (mostrar ventana)
  - Minimize to Tray (minimizar)
  - Settings (configuración)
  - Quit (salir)

### Autoarranque

**Para que una tarea inicie al boot:**

1. En la pestaña **Tasks**
2. Encuentra la tarea
3. Activa el toggle "Auto-start"
4. Los servicios systemd se crean automáticamente

**Verificar servicios:**

```bash
systemctl --user list-units | grep lxdrive
```

**Reiniciar y probar:**

```bash
systemctl --user restart lxdrive-mount@gdrive.service
systemctl --user status lxdrive-mount@gdrive.service
```

---

## Solución de Problemas

### Problema: "rclone no encontrado"

**Solución:**

```bash
# Instalar rclone
sudo apt install rclone

# O desde script oficial
curl https://rclone.org/install.sh | sudo bash
```

**Verificar instalación:**

```bash
rclone version
rclone config
```

---

### Problema: "FUSE no está disponible"

**Solución:**

```bash
# Instalar fuse3
sudo apt install fuse3

# Agregar usuario al grupo fuse
sudo usermod -a -G fuse $USER

# Reiniciar sesión para aplicar cambios
```

**Verificar:**

```bash
groups $USER
ls -l /dev/fuse
```

---

### Problema: "Error de permisos FUSE"

**Solución:**

```bash
# Verificar que /dev/fuse existe
ls -l /dev/fuse

# Verificar que el usuario está en grupo fuse
groups $USER

# Verificar montajes existentes
fusermount -l
```

---

### Problema: "El montaje no funciona"

**Solución:**

1. **Verificar que está desmontado:**

```bash
fusermount -u ~/Cloud/gdrive
```

2. **Verificar directorio local:**

```bash
ls -la ~/Cloud/
mkdir -p ~/Cloud/gdrive
```

3. **Verificar permisos:**

```bash
ls -ld ~/Cloud/
chmod 755 ~/Cloud/
```

4. **Probar rclone manual:**

```bash
rclone mount gdrive: ~/Cloud/gdrive-test
# Si funciona, el problema es en lX_Drive
```

5. **Verificar logs:**

```bash
tail -f ~/.config/lxdrive/logs/mount-gdrive.log
```

---

### Problema: "El tray icon no aparece en KDE"

**Solución:**

KDE Plasma maneja los tray icons diferente a Gnome/MATE:

1. **Verificar AppIndicator está instalado:**

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

2. **Actualizar cache de iconos:**

```bash
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor/
```

3. **Reiniciar lxdrive:**

```bash
lxdrive
```

4. **Verificar si el icono se crea:**

```bash
ps aux | grep lxdrive
```

5. **Ver logs en terminal:**

```bash
lxdrive 2>&1
```

---

### Problema: "La ventana se minimiza al abrir"

**Solución:**

Este es un comportamiento normal. Para prevenirlo:

1. No cierres la ventana con la "X"
2. Usa el botón "Minimize" en el header bar
3. O minimiza manualmente usando el tray icon

**Opcional: Deshabilitar minimizado automático**

Modifica `lxdrive/gui/main_window.py:358-366`:

```python
def do_activate(self):
    start_hidden = "--tray" in sys.argv or "-t" in sys.argv
    if not self.main_window:
        self.main_window = MainWindow(self, start_hidden=start_hidden)
    
    # Elimina estas líneas para que siempre se muestre
    if not start_hidden:
        self.main_window.show_all()
        self.main_window.present()
        self.main_window.get_window().raise_()
```

---

### Problema: "Sincronización se detiene"

**Solución:**

1. **Verificar estado de la tarea:**

En la pestaña **Tasks**, busca el estado "idle" o "error"

2. **Reiniciar sync manual:**

Botón "Sync" en la tarea

3. **Verificar logs:**

```bash
tail -f ~/.config/lxdrive/logs/sync-gdrive.log
```

4. **Verificar systemd service:**

```bash
systemctl --user status lxdrive-sync-gdrive.service
journalctl --user -u lxdrive-sync-gdrive.service
```

---

### Problema: "El icono del tray icon no se ve"

**Solución:**

1. **Verificar que el PNG existe:**

```bash
ls -la /usr/share/icons/hicolor/128x128/apps/lxdrive.png
```

2. **Verificar icono en código:**

En `lxdrive/gui/main_window.py:229-235`:

```python
icon_path = "/usr/share/icons/hicolor/128x128/apps/lxdrive.png"

if not Path(icon_path).exists():
    icon_path = str(Path.home() / ".local/share/lxdrive/icons/lxdrive.png")
```

3. **Actualizar icon theme:**

```bash
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor/
```

4. **Verificar AppIndicator:**

```bash
python3 -c "from gi.repository import AppIndicator3; print(AppIndicator3.__version__)"
```

---

### Problema: "Error de conexión con Google Drive"

**Solución:**

1. **Verificar rclone config:**

```bash
rclone config
```

2. **Probar conexión manual:**

```bash
rclone lsd gdrive:
```

3. **Verificar tokens:**

```bash
rclone config show gdrive
```

4. **Reconfigurar si es necesario:**

```bash
rclone config reconnect gdrive
```

5. **Verificar cuota:**

En lX_Drive: Accounts -> Botón "Verify"

---

### Problema: "Conflictos en sincronización"

**Solución:**

1. **Analizar conflicto:**

Los archivos con conflictos tendrán sufijos como `~CONFLICT~`, `~DELETED~`, etc.

2. **Verificar logs:**

```bash
grep -i conflict ~/.config/lxdrive/logs/sync-gdrive.log
```

3. **Resolver manualmente:**

```bash
# Ver conflictos
rclone conflict-list gdrive:/ruta

# Resolver conflicto
rclone conflict-goto gdrive:/ruta <conflict-id> new
```

4. **Reiniciar sync:**

En lX_Drive: Botón "Sync" en la tarea

---

### Problema: "Servicios systemd no se crean"

**Solución:**

1. **Verificar systemd user:**

```bash
systemctl --user status
```

2. **Reiniciar daemon:**

```bash
systemctl --user daemon-reload
```

3. **Verificar permisos:**

```bash
ls -la ~/.config/systemd/user/
```

4. **Crear servicio manual:**

Copia el template desde `services/lxdrive-mount@.service` a `~/.config/systemd/user/`

---

### Problema: "Navegador de archivos no muestra montaje"

**Solución:**

1. **Verificar que está montado:**

```bash
mount | grep gdrive
fusermount -l
```

2. **Verificar permisos:**

```bash
ls -la ~/Cloud/gdrive
```

3. **Verificar capacidad:**

El mount debe ser legible por tu usuario actual

4. **Probar acceso manual:**

```bash
cd ~/Cloud/gdrive
ls
```

---

## Guía de Desarrollador

### Ambiente de Desarrollo

**Requisitos:**

```bash
# Python 3.10+
sudo apt install python3.10 python3-pip

# GTK3
sudo apt install gir1.2-gtk-3.0

# Dependencies
pip3 install PyGObject pyxdg
```

**Estructura:**

```
lX_Drive/
├── lxdrive/                    # Código fuente
├── data/icons/                 # Iconos
├── services/                   # Templates systemd
├── debian-package/            # Para construir .deb
├── install.sh                  # Script de instalación
├── build-deb.sh                # Script de build .deb
└── requirements.txt           # Dependencias
```

---

### Desarrollo - Flujo Normal

**1. Modificar código:**

```bash
cd /usr/share/lxdrive
nano lxdrive/gui/main_window.py
```

**2. Probar directamente:**

```bash
cd /usr/share/lxdrive
python3 -m lxdrive.main
```

**3. Verificar cambios:**

- Reinstalar: `sudo dpkg -i lxdrive_1.0.0_all.deb`
- Ejecutar: `lxdrive`

---

### Desarrollo - Build Nuevo .deb

**1. Modificar código y scripts**

**2. Ejecutar build script:**

```bash
./build-deb.sh
```

**3. Verificar contenido:**

```bash
dpkg-deb -c lxdrive_1.0.0_all.deb
```

**4. Instalar:**

```bash
sudo dpkg -i lxdrive_1.0.0_all.deb
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor/
```

---

### Test - Modo Unitario

```python
# test_rclone_manager.py
from lxdrive.backend.rclone_manager import RcloneManager

def test_list_remotes():
    manager = RcloneManager()
    remotes = manager.list_remotes()
    print("Remotes:", remotes)

if __name__ == "__main__":
    test_list_remotes()
```

```bash
python3 test_rclone_manager.py
```

---

### Test - Integración GUI

```bash
# Modo debug
lxdrive --debug

# Verificar que AppIndicator se crea
# Verificar que se cargan los archivos
```

---

### Debug - Logs

**Ver logs de la app:**

```bash
tail -f ~/.config/lxdrive/logs/lxdrive.log
```

**Ver logs de rclone:**

```bash
tail -f ~/.config/lxdrive/logs/mount-gdrive.log
tail -f ~/.config/lxdrive/logs/sync-gdrive.log
```

**Ver logs de systemd:**

```bash
journalctl --user -u lxdrive-mount@gdrive.service
journalctl --user -u lxdrive-sync-gdrive.service
```

---

### Debug - Problemas comunes

**Rclone no se encuentra:**

```python
from lxdrive.backend.rclone_manager import RcloneManager

manager = RcloneManager()
print("Rclone:", manager.rclone_path)
print("Disponible:", manager.is_available())
```

**Mount no funciona:**

```python
from lxdrive.backend.mount_manager import MountManager

manager = MountManager()
check_ok, check_msg = manager.check_mount_requirements()
print("Check:", check_ok, check_msg)

is_ok, msg = manager.mount("gdrive", Path("~/Cloud/gdrive"))
print("Mount:", is_ok, msg)
```

**Sync no funciona:**

```python
from lxdrive.backend.sync_manager import SyncManager

manager = SyncManager()

valid, msg = manager.validate_local_path(Path("~/Cloud/gdrive/sync"))
print("Valid:", valid, msg)
```

---

### Contribuciones

**Reportar Bugs:**

1. Capturar logs de terminal
2. Verificar estado de servicios
3. Documentar reproduce steps

**Feature Request:**

1. Mencionar caso de uso
2. Preferencias de implementación
3. Posibles alternativas

---

## Referencias Adicionales

### rclone

**Documentación oficial:** https://rclone.org/

**Comandos útiles:**

```bash
# Ver version
rclone version

# Listar remotes
rclone listremotes

# Configurar remote
rclone config

# Probar conexión
rclone lsd gdrive:

# Ver cuota
rclone about gdrive:

# Montar manual
rclone mount gdrive: ~/Cloud/gdrive

# Bisync manual
rclone bisync ~/Cloud/gdrive gdrive: --resync --watch

# Ver conflictos
rclone conflict-list gdrive:/ruta
```

---

### Systemd de Usuario

**Documentación:** https://www.freedesktop.org/software/systemd/man/systemd.user.html

**Comandos:**

```bash
# Listar unidades
systemctl --user list-units

# Ver unidad específica
systemctl --user show lxdrive-mount@gdrive.service

# Habilitar
systemctl --user enable lxdrive-mount@gdrive.service

# Iniciar
systemctl --user start lxdrive-mount@gdrive.service

# Detener
systemctl --user stop lxdrive-mount@gdrive.service

# Recargar
systemctl --user daemon-reload

# Logs
journalctl --user -u lxdrive-mount@gdrive.service
journalctl --user -f  # Follow
```

---

### GTK3 Python

**Documentación:** https://lazka.github.io/PyGObject-docs/

**Ejemplo básico:**

```python
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

def on_button_clicked(button):
    print("¡Hola desde GTK!")

win = Gtk.Window(title="Test")
win.connect("destroy", Gtk.main_quit)

btn = Gtk.Button(label="Click me")
btn.connect("clicked", on_button_clicked)
win.add(btn)

win.show_all()
Gtk.main()
```

---

## Versión y Changelog

### v1.0.0 (2026-03-12)

**Features:**
- Montaje VFS de múltiples proveedores
- Sincronización bidireccional con rclone bisync
- Interfaz GTK3 nativa para Linux Mint
- Soporte para Google Drive, OneDrive, Dropbox
- Tray icon con menú contextual
- Temas Light/Dark/System
- Autoarranque con systemd
- Sistema de logs integrado
- Archivo .deb de instalación

**Bug Fixes:**
- Tray icon visible en KDE Plasma
- Ventana no se minimiza al abrir
- Icono PNG aplicado correctamente
- Installation .deb incluye archivos Python
- Servicios systemd creados correctamente

**Technical:**
- Python 3.10+
- GTK3 (gir1.2-gtk-3.0)
- rclone como motor backend
- Systemd user services
- FUSE3 para montajes

---

## Licencia

GPL-3.0

---

## Contacto

**Proyecto:** lX_Drive Team
**Repositorio:** https://github.com/lxdrive/lxdrive
**Issues:** https://github.com/lxdrive/lxdrive/issues
**Email:** info@lxdrive.org

---

**Documentación Actualizada:** 2026-03-12
**Versión:** 1.0.0
