# 🚀 lX Drive

**Advanced Synchronization Client for Google Drive on Linux**

A powerful and modern *opensource* alternative to proprietary solutions like Insync. Designed for users who need real performance, multi-account management, and full control over their files.

---

## ✨ Main Features

- 🔑 **True Multi-Account**: Manage unlimited Google Drive accounts simultaneously.
- 🔄 **Intelligent Hybrid Synchronization**: 
  - **VFS Mode (Streaming)**: Browse petabytes of data without taking up disk space.
  - **Sync Mode (Mirror)**: Keep your work files always available offline.
- ⚡ **Concurrent Engine**: Synchronize multiple folders at once without blocking.
- 👁️ **Real-Time Detection**: Thanks to **Watchdog**, local changes (save, move, delete) are instantly replicated.
- 🧠 **Smart Rename**: Detects file renames and moves to avoid unnecessary re-uploads.
- 🛠️ **Robust Recovery**: Auto-repair system for `.lck` locks to ensure continuity.

---

## 🖼️ Feature Gallery

### Account Setup
![New account setup](img/Configuracion%20de%20nueva%20cuenta%20Gui.png)

### Activity View
![Activity panel](img/vista%20de%20panel%20de%20registro%20de%20evento%20de%20carpetas%20y%20%20de%20dsco%20vfs.png)

### Simultaneous Synchronization
![Multiple account synchronization](img/vista%20de%20configuracion%20de%202%20cuentas%20simultaneas%20de%20google%20drive.png)

### Browser Confirmation
![Browser confirmation](img/confirmacion%20de%20apertura%20de%20navegador%20para%20logueo%20usando%20rclone.png)

### Login Result
![Login result](img/resultado%20de%20logueo%20de%20cuenta%20de%20google.png)

### Auto-Start Configuration
![Auto-start](img/vista%20de%20activar%20inicio%20automatico%20de%20la%20aplicacion%20apenas%20se%20inicie%20el%20sistema.png)

### Full Interface View
![Full interface](img/Interfaz%20completa,%20vista%20cuenta,%20%20y%20actividades.png)

### Drive and Simultaneous Sync Configuration
![Drive and simultaneous sync](img/seccion%20donde%20se%20ve%20que%20una%20cuenta%20se%20puede%20tener%20la%20unidad%20y%20tambien%20sincronizacion%20de%20carpeta%20de%20manera%20simultanea.png)

### Account Configuration Option
![Configuration option](img/Vista%20de%20la%20opcion%20de%20configuracion%20de%20cuenta%20vinculada.png)

---

## 🛠️ Technologies

- **Backend**: `rclone` (v1.72+) - The most robust engine on the market.
- **Core**: Python 3 + `watchdog` (FS Monitoring).
- **GUI**: PyQt6 - Modern, dark, and responsive interface.
- **Persistence**: JSON - Portable configuration.

---

## 📦 Installation (Development)

Currently in active development. It is recommended to run from the source code.

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

2. **Set Up an Account**:

   To set up an account, follow the steps shown in the image below:

   <div align="center">
      <img src="img/ejemplo%20de%20adicion%20de%20cuentas%20google%20drive.png" alt="Setup example" width="600"/>
   </div>

3. **Synchronize Files**:
   ![Active synchronization](img/vista%20de%20unidad%20montada%20de%20cuenta%20pyme%20y%20gratuita%20de%20google%20drive%20en%20linux.png)

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