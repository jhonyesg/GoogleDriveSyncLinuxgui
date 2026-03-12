# lX_Drive

Aplicación de escritorio para Linux Mint que gestiona la sincronización bidireccional entre carpetas locales y múltiples proveedores de almacenamiento en la nube usando **rclone** como motor backend.

## Características

- **Gestión Multi-Proveedor**: Soporte para Google Drive, OneDrive, Dropbox y más
- **Montaje VFS**: Monta unidades virtuales con caché optimizado
- **Sincronización Bidireccional**: Usa rclone bisync para mantener carpetas sincronizadas
- **Interfaz GTK Nativa**: Integración perfecta con Linux Mint (Cinnamon/MATE/XFCE)
- **Temas Visuales**: Claro, Oscuro o sincronizado con el sistema
- **Autoarranque**: Configura el inicio automático de tareas
- **Systemd**: Servicios de usuario para montajes y sincronización en segundo plano
- **Logs**: Visor de registros integrado

## Requisitos del Sistema

- Linux Mint 20+ (o cualquier distribución con GTK 4.0)
- Python 3.10+
- rclone (instalado y configurado)
- fuse3

### Dependencias

```bash
sudo apt install rclone python3 python3-gi gir1.2-gtk-4.0 fuse3
pip3 install --user PyGObject pyxdg
```

## Instalación

### Desde el código fuente

```bash
cd lX_Drive
chmod +x install.sh
./install.sh
```

El script de instalación:
1. Verifica las dependencias
2. Instala los archivos de la aplicación
3. Crea el acceso directo en el menú
4. Configura los servicios systemd
5. Crea la configuración inicial

## Uso

### Primera ejecución

1. Abre **lX_Drive** desde el menú de aplicaciones
2. Ve a la pestaña **Accounts**
3. Haz clic en **Add Account**
4. Selecciona tu proveedor de nube
5. Sigue el asistente de configuración de rclone
6. Ve a la pestaña **Tasks** para crear tareas de montaje o sincronización

### Crear una tarea de montaje

1. En la pestaña **Tasks**, haz clic en **Add Task**
2. Selecciona **Mount (VFS)**
3. Elige la cuenta configurada
4. Selecciona la carpeta local donde montar
5. Haz clic en **Create**

### Crear una tarea de sincronización

1. En la pestaña **Tasks**, haz clic en **Add Task**
2. Selecciona **Bidirectional Sync**
3. Elige la cuenta y la ruta remota
4. Selecciona la carpeta local
5. Haz clic en **Create**

### Autoarranque

Para que una tarea se inicie automáticamente al iniciar sesión:
1. Selecciona la tarea en la lista
2. Activa el interruptor de autoarranque

## Estructura del Proyecto

```
lX_Drive/
├── lxdrive/                 # Código principal
│   ├── backend/             # Lógica de rclone, montajes, sync
│   ├── gui/                 # Interfaz gráfica GTK
│   ├── utils/               # Utilidades (logger, autostart)
│   ├── config.py            # Configuración global
│   └── main.py              # Punto de entrada
├── data/
│   └── icons/               # Iconos SVG
├── services/                # Templates systemd
├── install.sh               # Script de instalación
├── uninstall.sh             # Script de desinstalación
└── README.md
```

## Configuración

Los archivos de configuración se encuentran en:

- `~/.config/lxdrive/config.json` - Configuración de la aplicación
- `~/.config/lxdrive/tasks.json` - Tareas definidas
- `~/.config/lxdrive/logs/` - Archivos de registro
- `~/.config/rclone/rclone.conf` - Configuración de remotos (gestionado por rclone)

## Modo Headless (Servidor)

Para usar los scripts sin interfaz gráfica:

```bash
# Listar remotos
python3 -c "from lxdrive.backend import RcloneManager; print(RcloneManager().list_remotes())"

# Montar un remote
python3 -c "from lxdrive.backend import MountManager; MountManager().mount('gdrive', '/home/user/Cloud/gdrive')"

# Crear servicio systemd para montaje
python3 -c "from lxdrive.backend import SystemdManager; SystemdManager().create_mount_service('gdrive', '/home/user/Cloud/gdrive')"
```

## Solución de Problemas

### rclone no encontrado

```bash
sudo apt install rclone
# o
curl https://rclone.org/install.sh | sudo bash
```

### Error de permisos FUSE

Asegúrate de que tu usuario esté en el grupo `fuse`:

```bash
sudo usermod -a -G fuse $USER
# Cierra sesión y vuelve a entrar
```

### El montaje no funciona

Verifica que el punto de montaje esté vacío y que tengas permisos:

```bash
mkdir -p ~/Cloud/gdrive
fusermount -u ~/Cloud/gdrive  # Desmontar si estaba montado
```

## Desinstalación

```bash
chmod +x uninstall.sh
./uninstall.sh
```

## Licencia

GPL-3.0

## Créditos

- Desarrollado con Python y GTK 4.0
- Motor de sincronización: [rclone](https://rclone.org/)
- Inspirado en las necesidades de gestión de nube en Linux Mint
