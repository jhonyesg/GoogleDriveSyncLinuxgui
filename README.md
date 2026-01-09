# 🚀 lX Drive

**Cliente de Sincronización Avanzado para Google Drive en Linux**

Una alternativa *opensource* potente y moderna a soluciones privativas como Insync. Diseñada para usuarios que necesitan rendimiento real, gestión de múltiples cuentas y control total sobre sus archivos.

## ✨ Características Principales

*   🔑 **Multi-Cuenta Real**: Gestiona ilimitadas cuentas de Google Drive simultáneamente.
*   🔄 **Sincronización Híbrida Inteligente**: 
    *   **Modo VFS (Streaming)**: Navega por petabytes de datos sin ocupar espacio en disco.
    *   **Modo Sync (Espejo)**: Ten tus archivos de trabajo siempre disponibles offline.
*   ⚡ **Motor Concurrente**: Sincroniza múltiples carpetas a la vez sin bloqueos.
*   👁️ **Detección en Tiempo Real**: Gracias a **Watchdog**, los cambios locales (guardar, mover, borrar) se replican al instante.
*   🧠 **Smart Rename**: Detecta renombres y movimientos de archivos para evitar re-subidas innecesarias.
*   🛡️ **Recuperación Robusta**: Sistema de auto-reparación de bloqueos (`.lck`) para garantizar la continuidad.

## 🛠️ Tecnologías

*   **Backend**: `rclone` (v1.72+) - El motor más robusto del mercado.
*   **Core**: Python 3 + `watchdog` (Monitorización de FS).
*   **GUI**: PyQt6 - Interfaz moderna, oscura y responsiva.
*   **Persistencia**: JSON - Configuración portátil.

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

### 3. Ejecutar

```bash
# Ejecutar módulo
python3 -m lxdrive
```

## 🚀 Guía de Uso Rápido

1.  **Añadir Cuenta**:
    *   Pulsa en "Añadir Cuenta" y sigue el flujo de OAuth de Google.
    *   **Importante**: Se abrirá tu navegador para autorizar el acceso.
2.  **Configurar Pares**:
    *   Elige una **Carpeta Local** vacía y una **Ruta Remota** en Drive.
    *   Activa "Sincronización Automática".
3.  **Monitorización**:
    *   El **Panel de Actividad** te mostrará en tiempo real qué está pasando.
    *   Iconos visuales para: 📤 Subidas, 📥 Bajadas, 🗑️ Borrados, 🔄 Renombres.

## 📁 Estructura del Proyecto

```
lX_Drive/
├── lxdrive/
│   ├── app.py               # Orquestador principal
│   ├── core/
│   │   ├── sync_manager.py  # Cerebro de sincronización (Watchdog + Threads)
│   │   ├── rclone_wrapper.py# Driver de bajo nivel
│   │   └── ...
│   └── gui/                 # Componentes PyQt6
├── requirements.txt
└── README.md
```

## 🤝 Contribuir

Si encuentras un bug o tienes una idea:
1.  Haz un Fork.
2.  Crea una rama (`git checkout -b feature/AmazingFeature`).
3.  Commit (`git commit -m 'Add some AmazingFeature'`).
4.  Push (`git push origin feature/AmazingFeature`).
5.  Abre un Pull Request.

---

**lX Drive** - *Tu nube, bajo tu control.* 🐧☁️
