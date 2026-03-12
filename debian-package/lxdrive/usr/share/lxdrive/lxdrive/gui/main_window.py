import sys
import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gio, Gdk, GLib, GObject
from typing import Optional

try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3
except (ImportError, ValueError):
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator3
    except (ImportError, ValueError):
        AppIndicator3 = None

from lxdrive.config import APP_NAME, APP_ID, VERSION, ensure_directories
from lxdrive.backend.models import AppConfig, TaskManager
from lxdrive.backend import RcloneManager, MountManager, SyncManager, SystemdManager
from lxdrive.gui.accounts_panel import AccountsPanel
from lxdrive.gui.tasks_panel import TasksPanel
from lxdrive.gui.log_viewer import LogViewer
from lxdrive.gui.settings_dialog import SettingsDialog
from lxdrive.gui.styles import apply_theme
from lxdrive.utils.logger import setup_logger, get_logger
from lxdrive.utils.autostart import is_autostart_enabled
from lxdrive.utils.translations import _


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, start_hidden=False):
        super().__init__(application=app)
        
        self.app = app
        self.config = AppConfig.load()
        self.task_manager = TaskManager()
        self.start_hidden = start_hidden
        
        self.rclone_manager = RcloneManager()
        self.mount_manager = MountManager()
        self.sync_manager = SyncManager()
        self.systemd_manager = SystemdManager()
        
        self._setup_logger()
        self._setup_window()
        self._setup_header_bar()
        self._setup_content()
        self._setup_tray_icon()
        self._apply_settings()
        
        self.logger = get_logger()
        self.logger.info(f"{APP_NAME} v{VERSION} started")
        
        GLib.idle_add(self._start_autostart_tasks)
    
    def _setup_logger(self):
        def log_callback(message: str, level: int):
            GLib.idle_add(self._update_log_viewer, message, level)
        
        setup_logger(log_level=self.config.log_level)
        from lxdrive.utils.logger import add_gui_log_callback
        add_gui_log_callback(log_callback)
    
    def _update_log_viewer(self, message: str, level: str):
        if hasattr(self, "log_viewer") and self.log_viewer:
            self.log_viewer.append_log(message, level)
        return False
    
    def _setup_window(self):
        from pathlib import Path
        self.set_title(APP_NAME)
        self.set_default_size(self.config.window_width, self.config.window_height)
        
        icon_path = Path.home() / ".local" / "share" / "lxdrive" / "icons" / "lxdrive.png"
        if icon_path.exists():
            self.set_icon_from_file(str(icon_path))
        else:
            self.set_icon_name("lxdrive")
        
        self.connect("delete-event", self._on_close_request)
        self.connect("window-state-event", self._on_window_state_changed)
        
        if self.start_hidden:
            self.hide()
    
    def _setup_header_bar(self):
        self.header_bar = Gtk.HeaderBar()
        self.header_bar.set_title(APP_NAME)
        self.header_bar.set_show_close_button(True)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        title_label = Gtk.Label()
        title_label.set_markup(f"<b>{APP_NAME}</b>")
        title_box.pack_start(title_label, False, False, 0)
        
        self.header_bar.set_custom_title(title_box)
        
        menu = Gio.Menu()
        menu.append(_("settings"), "app.settings")
        menu.append(_("about"), "app.about")
        
        menu_button = Gtk.MenuButton()
        menu_button.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        menu_button.set_menu_model(menu)
        self.header_bar.pack_end(menu_button)
        
        refresh_button = Gtk.Button()
        refresh_button.set_image(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON))
        refresh_button.set_tooltip_text(_("refresh"))
        refresh_button.connect("clicked", self._on_refresh)
        self.header_bar.pack_start(refresh_button)
        
        self.set_titlebar(self.header_bar)
    
    def _setup_content(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        
        self.accounts_panel = AccountsPanel(
            self.rclone_manager,
            self._on_account_added,
            self._on_account_removed,
            self.config
        )
        self.stack.add_titled(self.accounts_panel, "accounts", _("accounts"))
        
        self.tasks_panel = TasksPanel(
            self.task_manager,
            self.rclone_manager,
            self.mount_manager,
            self.sync_manager,
            self.systemd_manager,
            self._on_task_changed
        )
        self.stack.add_titled(self.tasks_panel, "tasks", _("tasks"))
        
        self.log_viewer = LogViewer()
        self.stack.add_titled(self.log_viewer, "logs", _("logs"))
        
        self.stack_switcher = Gtk.StackSwitcher()
        self.stack_switcher.set_stack(self.stack)
        self.stack_switcher.set_halign(Gtk.Align.CENTER)
        self.stack_switcher.set_hexpand(True)
        
        self.main_box.pack_start(self.stack_switcher, False, False, 0)
        self.main_box.pack_start(self.stack, True, True, 0)
        
        self.status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.status_bar.set_margin_top(6)
        self.status_bar.set_margin_bottom(6)
        self.status_bar.set_margin_start(12)
        self.status_bar.set_margin_end(12)
        
        self.status_label = Gtk.Label(label=_("ready"))
        self.status_label.set_halign(Gtk.Align.START)
        self.status_bar.pack_start(self.status_label, True, True, 0)
        
        self.main_box.pack_start(self.status_bar, False, False, 0)
        
        self.add(self.main_box)
    
    def _apply_settings(self):
        apply_theme(self.config.theme.value)
    
    def _start_autostart_tasks(self):
        self.logger.info("Iniciando tareas automático...")
        
        self.task_manager.load()
        
        for task in self.task_manager.tasks:
            if not task.enabled:
                continue
            
            if task.autostart:
                if task.task_type.value == "mount":
                    self.logger.info(f"Montando {task.name or task.remote_name}...")
                    success, msg = self.mount_manager.mount(
                        task.remote_name,
                        task.local_path
                    )
                    if success:
                        self.logger.info(f"Montado: {task.name or task.remote_name}")
                    else:
                        self.logger.error(f"Error al montar {task.name or task.remote_name}: {msg}")
                else:
                    self.logger.info(f"Sincronizando {task.name or task.remote_name}...")
                    import threading
                    thread = threading.Thread(target=self._run_sync_task, args=(task,), daemon=True)
                    thread.start()
        
        self.tasks_panel.refresh()
        return False
    
    def _run_sync_task(self, task):
        from lxdrive.config import TaskType
        success, msg = self.sync_manager.run_sync(task)
        
        def update_ui():
            if success:
                self.logger.info(f"Sincronización completada: {task.name or task.remote_name}")
            else:
                self.logger.error(f"Error en sincronización {task.name or task.remote_name}: {msg}")
            self.tasks_panel.refresh()
        
        GLib.idle_add(update_ui)
    
    def _on_close_request(self, widget, event):
        self.config.save()
        self.sync_manager.cleanup()
        self.hide()
        return True
    
    def _on_window_state_changed(self, widget, event):
        self.is_minimized = bool(event.new_window_state & Gdk.WindowState.ICONIFIED)
    
    def _setup_tray_icon(self):
        if AppIndicator3 is None:
            print("AppIndicator3 no disponible")
            return
        
        print("Configurando tray icon...")
        from pathlib import Path
        
        icon_path = "/usr/share/icons/hicolor/128x128/apps/lxdrive.png"
        
        if not Path(icon_path).exists():
            icon_path = str(Path.home() / ".local/share/lxdrive/icons/lxdrive.png")
        
        if not Path(icon_path).exists():
            icon_path = "lxdrive"
        
        print(f"Usando icono: {icon_path}")
        
        try:
            self.indicator = AppIndicator3.Indicator.new(
                APP_NAME.lower(),
                icon_path,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            print("Indicator creado")
        except Exception as e:
            print(f"Error creando indicator: {e}")
            return
        
        menu = Gtk.Menu()
        
        show_item = Gtk.MenuItem(label=_("show_window"))
        show_item.connect("activate", self._on_show_window)
        menu.append(show_item)
        
        hide_item = Gtk.MenuItem(label=_("minimize_to_tray"))
        hide_item.connect("activate", self._on_minimize_to_tray)
        menu.append(hide_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        settings_item = Gtk.MenuItem(label=_("settings"))
        settings_item.connect("activate", self._on_tray_settings)
        menu.append(settings_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        quit_item = Gtk.MenuItem(label=_("quit"))
        quit_item.connect("activate", self._on_tray_quit)
        menu.append(quit_item)
        
        menu.show_all()
        self.indicator.set_menu(menu)
        
        print("Menu configurado")
        
        self.indicator.connect("scroll-event", self._on_tray_scroll)
    
    def _on_show_window(self, menu_item):
        self.show()
        self.present()
    
    def _on_minimize_to_tray(self, menu_item):
        self.hide()
    
    def _on_tray_settings(self, menu_item):
        self.show()
        self.present()
        self.show_settings()
    
    def _on_tray_quit(self, menu_item):
        self.config.save()
        self.sync_manager.cleanup()
        self.app.quit()
    
    def _on_tray_scroll(self, indicator, steps, direction):
        pass
    
    def _on_refresh(self, button):
        self.accounts_panel.refresh()
        self.tasks_panel.refresh()
        self.set_status(_("refreshed"))
    
    def _on_account_added(self, remote_name: str):
        self.tasks_panel.refresh()
        self.set_status(_("account_added", name=remote_name))
    
    def _on_account_removed(self, remote_name: str):
        for task in self.task_manager.tasks:
            if task.remote_name == remote_name:
                self.task_manager.remove_task(task.id)
        self.tasks_panel.refresh()
        self.set_status(_("account_removed", name=remote_name))
    
    def _on_task_changed(self):
        self.set_status(_("task_updated"))
    
    def set_status(self, message: str):
        self.status_label.set_text(message)
    
    def show_settings(self):
        dialog = SettingsDialog(self, self.config)
        response = dialog.run()
        if response == Gtk.ResponseType.APPLY:
            dialog.apply_settings()
            self.accounts_panel.update_config(self.config)
        dialog.destroy()
    
    def show_about(self):
        about = Gtk.AboutDialog()
        about.set_transient_for(self)
        about.set_modal(True)
        about.set_program_name(APP_NAME)
        about.set_version(VERSION)
        about.set_comments(_("cloud_sync_manager"))
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_website("https://github.com/lxdrive/lxdrive")
        about.set_authors(["lX_Drive Team"])
        about.run()
        about.destroy()
    
    def refresh_all(self):
        self.accounts_panel.refresh()
        self.tasks_panel.refresh()


class LXDriveApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.main_window: Optional[MainWindow] = None
    
    def do_activate(self):
        start_hidden = "--tray" in sys.argv or "-t" in sys.argv
        if not self.main_window:
            self.main_window = MainWindow(self, start_hidden=start_hidden)
        
        if not start_hidden:
            self.main_window.show_all()
            self.main_window.present()
            self.main_window.get_window().raise_() if self.main_window.get_window() else None
    
    def do_startup(self):
        Gtk.Application.do_startup(self)
        
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self._on_settings)
        self.add_action(settings_action)
        
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)
        
        show_action = Gio.SimpleAction.new("show", None)
        show_action.connect("activate", self._on_show)
        self.add_action(show_action)
    
    def _on_settings(self, action, param):
        if self.main_window:
            self.main_window.show_settings()
    
    def _on_about(self, action, param):
        if self.main_window:
            self.main_window.show_about()
    
    def _on_show(self, action, param):
        if self.main_window:
            self.main_window.show()
            self.main_window.present()
    
    def quit_app(self):
        self.quit()
