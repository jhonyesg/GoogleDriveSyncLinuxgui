# 🚀 lX Drive v1.5.0.5

**Cliente de Sincronización Avanzado para Google Drive en Linux**

Una alternativa *opensource* potente y moderna a soluciones privativas como Insync. Diseñada para usuarios que necesitan rendimiento real, gestión de múltiples cuentas y control total sobre sus archivos.

---

## ✨ Características Principales

- 🔑 **Multi-Cuenta Real**: Gestiona ilimitadas cuentas de Google Drive simultáneamente.
- 🔄 **Sincronización Híbrida Inteligente**: 
  - **Modo VFS (Streaming)**: Navega por petabytes de datos sin ocupar espacio en disco.
  - **Modo Sync (Espejo)**: Ten tus archivos de trabajo siempre disponibles offline.
- ⚡ **Motor Concurrente**: Sincroniza múltiples carpetas a la vez sin bloqueos.
- 👁️ **Detección en Tiempo Real**: Gracias a **Watchdog**, los cambios locales (guardar, mover, borrar) se replican al instante.
- 🧠 **Smart Rename**: Detecta renombres y movimientos de archivos para evitar re-subidas innecesarias.
- 🛠️ **Recuperación Robusta**: Sistema de auto-reparación de bloqueos (`.lck`) para garantizar la continuidad.

---

## 🆕 Novedades en v1.5

### 📊 Sistema de Actividad por Cuenta
- **Registro persistente**: Hasta 500 eventos por cuenta almacenados en JSON.
- **Selector de cuenta**: Filtra actividad por cuenta específica o ve todas a la vez.
- **Separación Sync/VFS**: Logs independientes para sincronización de carpetas y unidades virtuales.
- **Cuenta por defecto**: Selección automática de la última cuenta activa al iniciar.

### 🔄 Detección Inteligente de Renombres
- **FileMovedEvent nativo**: Captura renombres directos del sistema de archivos (inotify).
- **Patrón Delete+Create**: Detecta renombres hechos por editores que no generan eventos de movimiento.
- **Rename Server-Side**: Usa `rclone moveto` para renombrar en el servidor sin re-subir el archivo completo.
- **Sin duplicación**: Evita la creación de copias al renombrar archivos localmente.

### ⏸️ Pausa Inteligente de Watchdog
- **Filtro de archivos temporales**: Ignora `.partial`, `.tmp`, `.rclone` y otros archivos de trabajo.
- **Pausa durante sync**: Watchdog se desactiva automáticamente durante bisync para evitar falsos positivos.
- **Reactivación garantizada**: Usa `try/finally` para asegurar que siempre se reactive.

### 🔧 Mejoras en Estabilidad
- **Limpieza proactiva de locks**: Elimina archivos `.lck` huérfanos antes de iniciar bisync.
- **Manejo de errores mejorado**: Mejor recuperación ante fallos de red o conflictos.
- **UI no bloqueante**: Panel de actividad optimizado con actualizaciones incrementales.

---

## 🖼️ Galería de Características

### Configuración de Cuentas
![Configuración de nueva cuenta](img/Configuracion%20de%20nueva%20cuenta%20Gui.png)

### Vista de Actividades
![Panel de actividades](img/vista%20de%20panel%20de%20registro%20de%20evento%20de%20carpetas%20y%20%20de%20dsco%20vfs.png)

### Sincronización Simultánea
![Sincronización de múltiples cuentas](img/vista%20de%20configuracion%20de%202%20cuentas%20simultaneas%20de%20google%20drive.png)

### Confirmación de Navegador
![Confirmación de apertura de navegador](img/confirmacion%20de%20apertura%20de%20navegador%20para%20logueo%20usando%20rclone.png)

### Resultado del Logueo
![Resultado del logueo](img/resultado%20de%20logueo%20de%20cuenta%20de%20google.png)

### Configuración de Inicio Automático
![Inicio automático](img/vista%20de%20activar%20inicio%20automatico%20de%20la%20aplicacion%20apenas%20se%20inicie%20el%20sistema.png)

### Vista Completa de la Interfaz
![Vista completa](img/Interfaz%20completa,%20vista%20cuenta,%20%20y%20actividades.png)

### Configuración de Unidad y Sincronización Simultánea
![Unidad y sincronización simultánea](img/seccion%20donde%20se%20ve%20que%20una%20cuenta%20se%20puede%20tener%20la%20unidad%20y%20tambien%20sincronizacion%20de%20carpeta%20de%20manera%20simultanea.png)

### Opción de Configuración de Cuenta
![Opción de configuración](img/Vista%20de%20la%20opcion%20de%20configuracion%20de%20cuenta%20vinculada.png)

---

## 🛠️ Tecnologías

- **Backend**: `rclone` (v1.72+) - El motor más robusto del mercado.
- **Core**: Python 3 + `watchdog` (Monitorización de FS).
- **GUI**: PyQt6 - Interfaz moderna, oscura y responsiva.
- **Persistencia**: JSON - Configuración portátil.

---

## 📦 Instalación (Paquete .deb) - Recomendado

Para una instalación rápida y sencilla, usa el paquete .deb que incluye todas las dependencias.

### Instalación del Paquete .deb

1. **Descargar el paquete**:
   ```bash
   # El paquete .deb está disponible en el directorio deb_dist/
   ls deb_dist/
   ```

2. **Instalar el paquete**:
   ```bash
   sudo dpkg -i deb_dist/python3-lxdrive_1.5.0-1_all.deb
   sudo apt --fix-broken install  # Si hay dependencias faltantes
   ```

3. **Verificar la instalación**:
   ```bash
   lxdrive --help
   ```

### Ventajas del Paquete .deb

- ✅ Instalación global del sistema
- ✅ Comandos disponibles: `lxdrive`, `lx-drive`, `lxdrive-gui`
- ✅ Aparece en el menú de aplicaciones con icono
- ✅ Actualizaciones automáticas vía apt (futuro)
- ✅ Todas las dependencias incluidas

---

## 📦 Instalación (Desarrollo)

Para contribuir o ejecutar desde código fuente.

### 1. Requisitos Previos

Necesitas tener **rclone** instalado en tu sistema:

```bash
curl https://rclone.org/install.sh | sudo bash
```

### 2. Clonar y Preparar

```bash
# Clonar repositorio
git clone https://github.com/jhonyesg/GoogleDriveSyncLinuxgui.git
cd GoogleDriveSyncLinuxgui

# Crear entorno virtual (Recomendado)
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
pip install watchdog  # Crítico para la detección en tiempo real
```

---

## 🚀 Ejemplo de Uso

1. **Iniciar la Aplicación**:
   ```bash
   # Si instalaste el paquete .deb:
   lxdrive

   # O desde el código fuente:
   python3 -m lxdrive
   ```

2. **Configurar una Cuenta**:

   Para configurar una cuenta, sigue los pasos indicados en la imagen a continuación:

   <div align="center">
      <img src="img/ejemplo%20de%20adicion%20de%20cuentas%20google%20drive.png" alt="Ejemplo de configuración" width="600"/>
   </div>

3. **Sincronizar Archivos**:
   ![Sincronización activa](img/vista%20de%20unidad%20montada%20de%20cuenta%20pyme%20y%20gratuita%20de%20google%20drive%20en%20linux.png)

---

## 📝 Changelog

### v1.5.0.5 (2026-01-15)
- 🚀 **Fix Crítico de Duplicación**: Nueva lógica jerárquica para movimientos de carpetas.
- 📂 **Soporte de Movimiento de Directorios**: Los movimientos de carpetas se detectan y procesan server-side con `moveto`.
- 🧠 **Filtrado Inteligente de Hijos**: Evita ráfagas de eventos duplicados al organizar subcarpetas.

### v1.5.0 (2026-01-11)
- ✨ Sistema de actividad por cuenta con persistencia (500 eventos/cuenta)
- 🔄 Detección inteligente de renombres (FileMovedEvent + Delete+Create)
- 🚀 Rename server-side con `rclone moveto` (sin duplicación)
- ⏸️ Pausa automática de Watchdog durante sincronización
- 🧹 Filtro de archivos temporales (.partial, .tmp, etc.)
- 🔧 Limpieza proactiva de lock files
- 🎨 Panel de actividad con selector de cuenta

### v1.0.0 (2025-12-01)
- 🎉 Versión inicial
- 🔑 Soporte multi-cuenta
- 🔄 Sincronización bidireccional (bisync)
- 📁 Montaje VFS
- 👁️ Detección en tiempo real con Watchdog

---

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Por favor, abre un issue o envía un pull request para mejorar el proyecto.

---

## 📄 Licencia

Este proyecto está bajo una licencia Open Source. Está permitido su uso general, pero **no está autorizado para reventa**. 

**Autor:** Jhon Efraín Suárez Gómez  
**Cargo:** CEO & Lead Systems Engineer  
**Correo:** [jsuarez@mediaclouding.com](mailto:jsuarez@mediaclouding.com)  
**Sitio Web:** [https://mediaserver.com.co](https://mediaserver.com.co)  
**LinkedIn:** [https://mediaclouding.com](https://mediaclouding.com)  
**Upwork:** [Perfil en Upwork](https://www.upwork.com)

---

**lX Drive** - *Tu nube, bajo tu control.* 🐧☁️
