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
git clone <url-repo>
cd lX_Drive

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
   ![Ejemplo de configuración](img/ejemplo%20de%20adicion%20de%20cuentas%20google%20drive.png)

3. **Sincronizar Archivos**:
   ![Sincronización activa](img/vista%20de%20unidad%20montada%20de%20cuenta%20pyme%20y%20gratuita%20de%20google%20drive%20en%20linux.png)

---

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Por favor, abre un issue o envía un pull request para mejorar el proyecto.

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo LICENSE para más detalles.

---

**lX Drive** - *Tu nube, bajo tu control.* 🐧☁️
