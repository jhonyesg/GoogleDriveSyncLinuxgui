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