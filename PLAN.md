# Plan de Desarrollo: lX_Drive

## Resumen
Aplicación de escritorio para Linux Mint que gestiona sincronización bidireccional entre carpetas locales y múltiples proveedores de nube usando rclone como motor backend.

## Estructura de Archivos del Proyecto

```
lX_Drive/
├── lxdrive/
│   ├── __init__.py
│   ├── main.py                    # Punto de entrada principal
│   ├── config.py                  # Configuración global y constantes
│   │
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── rclone_manager.py      # Interfaz con rclone CLI
│   │   ├── mount_manager.py       # Gestión de montajes VFS
│   │   ├── sync_manager.py        # Gestión de bisync
│   │   ├── systemd_manager.py     # Creación/gestión de servicios systemd
│   │   └── models.py              # Modelos de datos (Remote, Task, etc.)
│   │
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py         # Ventana principal
│   │   ├── accounts_panel.py      # Panel de cuentas/proveedores
│   │   ├── tasks_panel.py         # Panel de tareas (montajes/sync)
│   │   ├── settings_dialog.py     # Diálogo de configuración/temas
│   │   ├── log_viewer.py          # Visor de logs
│   │   ├── add_account_dialog.py  # Wizard para agregar cuentas
│   │   ├── add_task_dialog.py     # Diálogo para crear tareas
│   │   └── styles.py              # CSS para temas
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py              # Sistema de logging
│       ├── autostart.py           # Gestión de autoarranque
│       └── desktop_entry.py       # Creación de .desktop files
│
├── data/
│   ├── icons/
│   │   ├── lxdrive.svg            # Icono de la app
│   │   ├── google-drive.svg
│   │   ├── onedrive.svg
│   │   └── dropbox.svg
│   └── ui/
│       └── (archivos .ui opcional para Glade)
│
├── services/
│   ├── lxdrive-mount@.service.in  # Template para montajes
│   └── lxdrive-sync@.service.in   # Template para bisync
│
├── install.sh                     # Script de instalación
├── uninstall.sh                   # Script de desinstalación
├── requirements.txt               # Dependencias Python
├── README.md                      # Documentación
└── setup.py                       # Instalación como paquete
```

## Módulos Detallados

### 1. Backend (`lxdrive/backend/`)

#### `rclone_manager.py`
- `list_remotes()` - Lista todos los remotes configurados
- `get_remote_info(name)` - Obtiene información de un remote
- `create_remote_interactive(name, provider)` - Lanza wizard de rclone config
- `delete_remote(name)` - Elimina un remote
- `check_connection(name)` - Verifica conexión con el remote
- `get_quota(name)` - Obtiene espacio usado/disponible

#### `mount_manager.py`
- `mount(remote, local_path, options)` - Monta un remote con VFS
- `unmount(mount_point)` - Desmonta
- `list_mounts()` - Lista montajes activos
- `is_mounted(path)` - Verifica si está montado

#### `sync_manager.py`
- `setup_bisync(remote, local_path, filters)` - Configura bisync
- `run_sync(task_id)` - Ejecuta sincronización
- `get_sync_status(task_id)` - Estado de sincronización
- `pause_sync(task_id)` / `resume_sync(task_id)`
- `resolve_conflict(task_id, strategy)` - Resolución de conflictos

#### `systemd_manager.py`
- `create_mount_service(remote, mount_point)` - Crea servicio de montaje
- `create_sync_service(remote, local_path)` - Crea servicio de sync
- `enable_service(name)` / `disable_service(name)`
- `get_service_status(name)`
- `remove_service(name)`

#### `models.py`
```python
@dataclass
class Remote:
    name: str
    provider: str  # gdrive, onedrive, dropbox, etc.
    root_folder: str
    is_configured: bool

@dataclass  
class SyncTask:
    id: str
    remote_name: str
    remote_path: str
    local_path: str
    task_type: str  # 'mount' o 'bisync'
    enabled: bool
    autostart: bool
    last_sync: datetime
    status: str

@dataclass
class AppConfig:
    theme: str  # 'light', 'dark', 'system'
    autostart_app: bool
    log_level: str
    mount_base_path: str
```

### 2. GUI (`lxdrive/gui/`)

#### `main_window.py`
- HeaderBar con menú principal
- Stack con 3 páginas: Cuentas, Tareas, Logs
- Barra de estado con indicadores
- Tray icon para minimizar a bandeja

#### `accounts_panel.py`
- ListBox de cuentas configuradas
- Cada fila muestra: icono proveedor, nombre, estado, quota
- Botones: Agregar cuenta, Eliminar, Verificar conexión, Abrir en archivo

#### `tasks_panel.py`
- TreeView o ListBox de tareas
- Columnas: Nombre, Tipo, Estado, Última sync, Acciones
- Toggles para activar/desactivar tareas
- Botón de sync manual

#### `settings_dialog.py`
- Sección Apariencia: Theme selector (Light/Dark/System)
- Sección General: Autoarranque, ruta base de montajes
- Sección Avanzado: Nivel de log, filtros por defecto

#### `add_account_dialog.py`
- Wizard de 2 pasos:
  1. Seleccionar proveedor (grid de iconos)
  2. Asistente de rclone config (terminal embebida o instrucciones)

### 3. Utilidades (`lxdrive/utils/`)

#### `autostart.py`
- `enable_autostart()` - Crea ~/.config/autostart/lxdrive.desktop
- `disable_autostart()` - Elimina el archivo
- `is_autostart_enabled()` - Verifica

#### `logger.py`
- Logger con rotación de archivos
- Handler para mostrar en GUI en tiempo real
- Niveles: DEBUG, INFO, WARNING, ERROR

## Servicios Systemd

### `lxdrive-mount@.service.in`
```ini
[Unit]
Description=lX_Drive Mount for %i
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/bin/rclone mount %i: %(mount_path) \
    --vfs-cache-mode full \
    --vfs-cache-max-age 24h \
    --vfs-cache-max-size 10G \
    --buffer-size 64M \
    --dir-cache-time 72h \
    --poll-interval 15s \
    --log-level INFO \
    --log-file %(log_path)
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

### `lxdrive-sync@.service.in`
```ini
[Unit]
Description=lX_Drive Bisync for %i
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart=/usr/bin/rclone bisync %(local_path) %i:%(remote_path) \
    --resync \
    --watch \
    --log-level INFO \
    --log-file %(log_path)
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
```

## Script de Instalación (`install.sh`)

El script debe:
1. Verificar dependencias (rclone, python3, gir1.2-gtk-4.0, etc.)
2. Instalar dependencias Python via pip
3. Copiar archivos a ~/.local/share/lxdrive/
4. Crear enlace simbólico al ejecutable en ~/.local/bin/
5. Crear archivo .desktop en ~/.local/share/applications/
6. Crear directorios de configuración (~/.config/lxdrive/)
7. Ofrecer crear icono en escritorio

## Archivo .desktop
```ini
[Desktop Entry]
Version=1.0
Name=lX_Drive
Comment=Sincronización de nube con rclone
Exec=lxdrive
Icon=lxdrive
Terminal=false
Type=Application
Categories=Network;FileTransfer;GTK;
StartupNotify=true
```

## Flujo de Trabajo de Implementación

### Fase 1: Estructura Base
1. Crear estructura de directorios
2. Crear archivos __init__.py
3. Crear config.py con constantes
4. Crear requirements.txt

### Fase 2: Backend Core
1. Implementar models.py
2. Implementar rclone_manager.py
3. Implementar mount_manager.py
4. Implementar sync_manager.py
5. Implementar systemd_manager.py

### Fase 3: Utilidades
1. Implementar logger.py
2. Implementar autostart.py
3. Implementar desktop_entry.py

### Fase 4: GUI
1. Implementar main_window.py (esqueleto)
2. Implementar accounts_panel.py
3. Implementar tasks_panel.py
4. Implementar add_account_dialog.py
5. Implementar add_task_dialog.py
6. Implementar settings_dialog.py
7. Implementar log_viewer.py
8. Implementar styles.py (temas CSS)

### Fase 5: Integración
1. Conectar GUI con Backend
2. Implementar main.py
3. Pruebas de integración

### Fase 6: Despliegue
1. Crear install.sh
2. Crear uninstall.sh
3. Crear servicios systemd templates
4. Documentar README.md

### Fase 7: Assets
1. Crear/obtener iconos SVG
2. Crear archivo .desktop

## Dependencias (requirements.txt)
```
PyGObject>=3.48.0
pyxdg>=0.28
```

## Dependencias del Sistema (verificar en install.sh)
- rclone
- python3 (>=3.10)
- gir1.2-gtk-4.0 (o gir1.2-gtk-3.0)
- fuse3
- libfuse3-3

## Configuración de Usuario
- `~/.config/lxdrive/config.json` - Configuración de la app
- `~/.config/lxdrive/tasks.json` - Tareas definidas
- `~/.config/lxdrive/logs/` - Archivos de log
- `~/.local/share/lxdrive/` - Datos de la aplicación
- `~/.config/systemd/user/` - Servicios de usuario
- `~/Cloud/` o `~/mnt/cloud/` - Ruta base sugerida para montajes

## Modo Headless (Opcional)
Los scripts backend pueden usarse sin GUI:
```bash
# Listar remotes
python3 -m lxdrive.backend.rclone_manager list

# Montar un remote
python3 -m lxdrive.backend.mount_manager mount gdrive ~/Cloud/gdrive

# Crear servicio systemd
python3 -m lxdrive.backend.systemd_manager create-mount gdrive ~/Cloud/gdrive
```

## Estimación de Archivos a Crear
- ~25 archivos Python
- 4-5 archivos de iconos SVG
- 2 templates systemd
- 2 scripts shell (install/uninstall)
- 1 requirements.txt
- 1 setup.py
- 1 README.md
- 1 lxdrive.desktop

**Total: ~38 archivos**
