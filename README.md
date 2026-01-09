<div align="center">
  <h1>🚀 lX Drive</h1>
  <p><strong>Cliente de Sincronización Avanzado para Google Drive en Linux</strong></p>
  <p><strong>Advanced Synchronization Client for Google Drive on Linux</strong></p>
</div>

<div align="center">
  <button onclick="showContent('es')">🇪🇸 Español</button>
  <button onclick="showContent('en')">🇬🇧 English</button>
</div>

<div id="es" style="display: block;">

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

---

</div>

<div id="en" style="display: none;">

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

</div>

<script>
function showContent(lang) {
  document.getElementById('es').style.display = lang === 'es' ? 'block' : 'none';
  document.getElementById('en').style.display = lang === 'en' ? 'block' : 'none';
}
</script>
