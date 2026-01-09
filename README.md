# 🚀 lX Drive

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

## 📦 Instalación (Desarrollo)

Actualmente en fase de desarrollo activo. Se recomienda ejecutar desde el código fuente.

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

# 🚀 lX Drive

**Advanced Synchronization Client for Google Drive on Linux**

An open-source, powerful, and modern alternative to proprietary solutions like Insync. Designed for users who need real performance, multi-account management, and full control over their files.

---

## ✨ Key Features

- 🔑 **True Multi-Account**: Manage unlimited Google Drive accounts simultaneously.
- 🔄 **Intelligent Hybrid Synchronization**: 
  - **VFS Mode (Streaming)**: Browse petabytes of data without taking up disk space.
  - **Sync Mode (Mirror)**: Keep your work files always available offline.
- ⚡ **Concurrent Engine**: Synchronize multiple folders at once without bottlenecks.
- 👁️ **Real-Time Detection**: Thanks to **Watchdog**, local changes (save, move, delete) are instantly replicated.
- 🧠 **Smart Rename**: Detects file renames and moves to avoid unnecessary re-uploads.
- 🛠️ **Robust Recovery**: Auto-repair system for `.lck` locks to ensure continuity.

---

## 🖼️ Feature Gallery

### Account Configuration
![New Account Configuration](img/Configuracion%20de%20nueva%20cuenta%20Gui.png)

### Activity View
![Activity Panel](img/vista%20de%20panel%20de%20registro%20de%20evento%20de%20carpetas%20y%20%20de%20dsco%20vfs.png)

### Simultaneous Synchronization
![Multiple Account Sync](img/vista%20de%20configuracion%20de%202%20cuentas%20simultaneas%20de%20google%20drive.png)

### Browser Confirmation
![Browser Confirmation](img/confirmacion%20de%20apertura%20de%20navegador%20para%20logueo%20usando%20rclone.png)

### Login Result
![Login Result](img/resultado%20de%20logueo%20de%20cuenta%20de%20google.png)

### Auto-Start Configuration
![Auto-Start](img/vista%20de%20activar%20inicio%20automatico%20de%20la%20aplicacion%20apenas%20se%20inicie%20el%20sistema.png)

### Full Interface View
![Full Interface](img/Interfaz%20completa,%20vista%20cuenta,%20%20y%20actividades.png)

### Unit and Simultaneous Sync Configuration
![Unit and Sync](img/seccion%20donde%20se%20ve%20que%20una%20cuenta%20se%20puede%20tener%20la%20unidad%20y%20tambien%20sincronizacion%20de%20carpeta%20de%20manera%20simultanea.png)

### Account Configuration Option
![Account Configuration Option](img/Vista%20de%20la%20opcion%20de%20configuracion%20de%20cuenta%20vinculada.png)

---

## 🛠️ Technologies

- **Backend**: `rclone` (v1.72+) - The most robust engine on the market.
- **Core**: Python 3 + `watchdog` (FS Monitoring).
- **GUI**: PyQt6 - Modern, dark, and responsive interface.
- **Persistence**: JSON - Portable configuration.

---

## 📦 Installation (Development)

Currently under active development. It is recommended to run from the source code.

### 1. Prerequisites

You need to have **rclone** installed on your system:

```bash
curl https://rclone.org/install.sh | sudo bash
```

### 2. Clone and Prepare

```bash
# Clone repository
git clone https://github.com/jhonyesg/GoogleDriveSyncLinuxgui.git
cd GoogleDriveSyncLinuxgui

# Create virtual environment (Recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install watchdog  # Critical for real-time detection
```

---

## 🚀 Usage Example

1. **Start the Application**:
   ```bash
   python3 -m lxdrive
   ```

2. **Configure an Account**:

   To configure an account, follow the steps shown in the image below:

   <div align="center">
      <img src="img/ejemplo%20de%20adicion%20de%20cuentas%20google%20drive.png" alt="Configuration Example" width="600"/>
   </div>

3. **Synchronize Files**:
   ![Active Synchronization](img/vista%20de%20unidad%20montada%20de%20cuenta%20pyme%20y%20gratuita%20de%20google%20drive%20en%20linux.png)

---

## 🤝 Contributions

Contributions are welcome! Please open an issue or submit a pull request to improve the project.

---

## 📄 License

This project is under an Open Source license. General use is allowed, but **resale is not authorized**. 

**Author:** Jhon Efraín Suárez Gómez  
**Position:** CEO & Lead Systems Engineer  
**Email:** [jsuarez@mediaclouding.com](mailto:jsuarez@mediaclouding.com)  
**Website:** [https://mediaserver.com.co](https://mediaserver.com.co)  
**LinkedIn:** [https://mediaclouding.com](https://mediaclouding.com)  
**Upwork:** [Upwork Profile](https://www.upwork.com)

---

**lX Drive** - *Your cloud, under your control.* 🐧☁️
