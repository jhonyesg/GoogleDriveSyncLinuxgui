import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, Pango, GObject
from typing import Callable, Optional
from pathlib import Path
from datetime import datetime

from lxdrive.config import TaskType, TaskStatus
from lxdrive.backend.models import SyncTask, TaskManager
from lxdrive.backend.rclone_manager import RcloneManager
from lxdrive.backend.mount_manager import MountManager
from lxdrive.backend.sync_manager import SyncManager
from lxdrive.backend.systemd_manager import SystemdManager
from lxdrive.gui.task_dialog import TaskDialog
from lxdrive.utils.translations import _


class TaskRow(Gtk.ListBoxRow):
    __gsignals__ = {
        "selected": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "edit-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "remove-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }
    
    def __init__(
        self,
        task: SyncTask,
        mount_manager: MountManager,
        sync_manager: SyncManager,
        systemd_manager: SystemdManager
    ):
        super().__init__()
        
        self.task = task
        self.mount_manager = mount_manager
        self.sync_manager = sync_manager
        self.systemd_manager = systemd_manager
        
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.content_box.get_style_context().add_class("task-row")
        
        self._setup_ui()
        self._update_status()
        
        self.add(self.content_box)
        
        self.connect("button-press-event", self._on_button_press)
        self.connect("activate", self._on_activate)
        
        self._setup_context_menu()
    
    def _setup_context_menu(self):
        self.context_menu = Gtk.Menu()
        
        edit_item = Gtk.MenuItem(label=_("edit"))
        edit_item.connect("activate", self._on_edit_menu)
        self.context_menu.append(edit_item)
        
        remove_item = Gtk.MenuItem(label=_("remove"))
        remove_item.connect("activate", self._on_remove_menu)
        self.context_menu.append(remove_item)
        
        self.context_menu.append(Gtk.SeparatorMenuItem())
        
        if self.task.task_type == TaskType.MOUNT:
            mount_item = Gtk.MenuItem(label=_("mount"))
            mount_item.connect("activate", lambda w: self._on_mount(None))
            self.context_menu.append(mount_item)
            
            unmount_item = Gtk.MenuItem(label=_("unmount"))
            unmount_item.connect("activate", lambda w: self._on_unmount(None))
            self.context_menu.append(unmount_item)
        else:
            sync_item = Gtk.MenuItem(label=_("sync_now"))
            sync_item.connect("activate", lambda w: self._on_sync(None))
            self.context_menu.append(sync_item)
        
        self.context_menu.show_all()
    
    def _on_edit_menu(self, item):
        self.emit("edit-requested")
    
    def _on_remove_menu(self, item):
        self.emit("remove-requested")
    
    def _on_button_press(self, widget, event):
        if event.button == 1:
            self.emit("selected")
        elif event.button == 3:
            self.emit("selected")
            self.context_menu.popup_at_pointer(event)
            return True
        return False
    
    def _on_activate(self, row):
        self.emit("selected")
    
    def _setup_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        
        type_icon = Gtk.Image()
        if self.task.task_type == TaskType.MOUNT:
            type_icon.set_from_icon_name("folder-remote-symbolic", Gtk.IconSize.DIALOG)
        else:
            type_icon.set_from_icon_name("emblem-synchronizing-symbolic", Gtk.IconSize.DIALOG)
        main_box.pack_start(type_icon, False, False, 0)
        
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        
        task_display_name = self.task.name if self.task.name else self.task.remote_name
        name_label = Gtk.Label()
        name_label.set_markup(f"<b>{task_display_name}</b>")
        name_label.set_halign(Gtk.Align.START)
        info_box.pack_start(name_label, False, False, 0)
        
        path_label = Gtk.Label()
        path_label.set_text(f"{self.task.remote_name}:{self.task.remote_path} → {self.task.local_path}")
        path_label.set_halign(Gtk.Align.START)
        path_label.get_style_context().add_class("dim-label")
        path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        info_box.pack_start(path_label, False, False, 0)
        
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        self.status_icon = Gtk.Image()
        self.status_icon.set_from_icon_name("dialog-question-symbolic", Gtk.IconSize.MENU)
        status_box.pack_start(self.status_icon, False, False, 0)
        
        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.START)
        status_box.pack_start(self.status_label, False, False, 0)
        
        info_box.pack_start(status_box, False, False, 0)
        main_box.pack_start(info_box, True, True, 0)
        
        switches_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        enabled_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        if self.task.task_type == TaskType.MOUNT:
            enabled_label = Gtk.Label(label="Auto-montar (VFS)")
        else:
            enabled_label = Gtk.Label(label=_("auto_start_login"))
        enabled_label.set_halign(Gtk.Align.END)
        enabled_box.pack_start(enabled_label, True, True, 0)
        
        self.autostart_switch = Gtk.Switch()
        self.autostart_switch.set_active(self.task.autostart)
        self.autostart_switch.connect("notify::active", self._on_autostart_toggled)
        enabled_box.pack_start(self.autostart_switch, False, False, 0)
        
        switches_box.pack_start(enabled_box, False, False, 0)
        main_box.pack_start(switches_box, False, False, 0)
        
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        if self.task.task_type == TaskType.MOUNT:
            self.mount_btn = Gtk.Button()
            self.mount_btn.set_label(_("mount"))
            self.mount_btn.set_image(Gtk.Image.new_from_icon_name("folder-remote-symbolic", Gtk.IconSize.BUTTON))
            self.mount_btn.set_always_show_image(True)
            self.mount_btn.connect("clicked", self._on_mount)
            buttons_box.pack_start(self.mount_btn, False, False, 0)
            
            self.unmount_btn = Gtk.Button()
            self.unmount_btn.set_label(_("unmount"))
            self.unmount_btn.set_image(Gtk.Image.new_from_icon_name("media-eject-symbolic", Gtk.IconSize.BUTTON))
            self.unmount_btn.set_always_show_image(True)
            self.unmount_btn.connect("clicked", self._on_unmount)
            buttons_box.pack_start(self.unmount_btn, False, False, 0)
            
            self.open_btn = Gtk.Button()
            self.open_btn.set_image(Gtk.Image.new_from_icon_name("folder-open-symbolic", Gtk.IconSize.BUTTON))
            self.open_btn.set_tooltip_text(_("open_folder"))
            self.open_btn.connect("clicked", self._on_open_folder)
            buttons_box.pack_start(self.open_btn, False, False, 0)
        else:
            self.sync_btn = Gtk.Button()
            self.sync_btn.set_label(_("sync_now"))
            self.sync_btn.set_image(Gtk.Image.new_from_icon_name("emblem-synchronizing-symbolic", Gtk.IconSize.BUTTON))
            self.sync_btn.set_always_show_image(True)
            self.sync_btn.connect("clicked", self._on_sync)
            buttons_box.pack_start(self.sync_btn, False, False, 0)
            
            self.history_btn = Gtk.Button()
            self.history_btn.set_image(Gtk.Image.new_from_icon_name("view-list-symbolic", Gtk.IconSize.BUTTON))
            self.history_btn.set_tooltip_text(_("sync_history"))
            self.history_btn.connect("clicked", self._on_show_history)
            buttons_box.pack_start(self.history_btn, False, False, 0)
        
        buttons_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 6)
        
        self.edit_btn = Gtk.Button()
        self.edit_btn.set_image(Gtk.Image.new_from_icon_name("document-edit-symbolic", Gtk.IconSize.BUTTON))
        self.edit_btn.set_tooltip_text(_("edit"))
        self.edit_btn.connect("clicked", self._on_edit_clicked)
        buttons_box.pack_start(self.edit_btn, False, False, 0)
        
        self.delete_btn = Gtk.Button()
        self.delete_btn.set_image(Gtk.Image.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON))
        self.delete_btn.set_tooltip_text(_("remove"))
        self.delete_btn.connect("clicked", self._on_delete_clicked)
        buttons_box.pack_start(self.delete_btn, False, False, 0)
        
        main_box.pack_start(buttons_box, False, False, 0)
        
        self.content_box.pack_start(main_box, False, False, 0)
        
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.content_box.pack_start(separator, False, False, 0)
    
    def _update_status(self):
        if self.task.task_type == TaskType.MOUNT:
            is_mounted = self.mount_manager.is_mounted(str(self.task.local_path))
            if is_mounted:
                self.status_label.set_markup("<span color='#2ec27e'>✓ Montado</span>")
                self.status_icon.set_from_icon_name("emblem-default-symbolic", Gtk.IconSize.MENU)
                if hasattr(self, 'mount_btn'):
                    self.mount_btn.set_sensitive(False)
                    self.unmount_btn.set_sensitive(True)
                    self.open_btn.set_sensitive(True)
            else:
                self.status_label.set_markup("<span color='#e01b24'>○ No montado</span>")
                self.status_icon.set_from_icon_name("emblem-important-symbolic", Gtk.IconSize.MENU)
                if hasattr(self, 'mount_btn'):
                    self.mount_btn.set_sensitive(True)
                    self.unmount_btn.set_sensitive(False)
                    self.open_btn.set_sensitive(False)
        else:
            status_map = {
                TaskStatus.IDLE: ("Inactivo", "dialog-information-symbolic"),
                TaskStatus.RUNNING: ("Sincronizando...", "emblem-synchronizing-symbolic"),
                TaskStatus.PAUSED: ("Pausado", "media-playback-pause-symbolic"),
                TaskStatus.ERROR: ("Error", "dialog-error-symbolic"),
                TaskStatus.SYNCING: ("Sincronizando", "emblem-synchronizing-symbolic"),
            }
            status_text, icon_name = status_map.get(self.task.status, ("Desconocido", "dialog-question-symbolic"))
            self.status_label.set_text(status_text)
            self.status_icon.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
        
        if self.task.last_sync:
            time_str = self.task.last_sync.strftime('%d/%m/%Y %H:%M')
            current_text = self.status_label.get_text()
            if self.task.last_sync_result:
                result_emoji = "✓" if "Éxito" in self.task.last_sync_result else "✗"
                self.status_label.set_markup(f"{current_text}  •  {result_emoji} {time_str}")
            else:
                self.status_label.set_text(f"{current_text}  •  Último: {time_str}")
    
    def _on_enabled_toggled(self, switch, pspec):
        self.task.enabled = switch.get_active()
    
    def _on_autostart_toggled(self, switch, pspec):
        self.task.autostart = switch.get_active()
        
        from lxdrive.backend.models import TaskManager
        task_manager = TaskManager()
        
        try:
            if switch.get_active():
                if self.task.task_type == TaskType.MOUNT:
                    self.systemd_manager.create_mount_service(
                        self.task.remote_name,
                        Path(self.task.local_path)
                    )
                    self.systemd_manager.enable_service(self.task.remote_name, "mount")
                else:
                    self.systemd_manager.create_sync_service(
                        self.task.id,
                        self.task.remote_name,
                        self.task.remote_path,
                        Path(self.task.local_path)
                    )
                    self.systemd_manager.enable_service(self.task.id, "sync")
            else:
                if self.task.task_type == TaskType.MOUNT:
                    self.systemd_manager.disable_service(self.task.remote_name, "mount")
                else:
                    self.systemd_manager.disable_service(self.task.id, "sync")
            
            task_manager.update_task(self.task)
        except Exception as e:
            print(f"Error toggling autostart: {e}")
    
    def _on_mount(self, button):
        if button:
            button.set_sensitive(False)
        
        def mount_async():
            try:
                success, msg = self.mount_manager.mount(
                    self.task.remote_name,
                    Path(self.task.local_path)
                )
                GLib.idle_add(self._on_mount_complete, success, msg, button)
            except Exception as e:
                GLib.idle_add(self._on_mount_complete, False, str(e), button)
        
        import threading
        thread = threading.Thread(target=mount_async, daemon=True)
        thread.start()
    
    def _on_mount_complete(self, success, msg, button):
        self._update_status()
        if button:
            button.set_sensitive(True)
        
        if not success:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Error al montar"
            )
            dialog.format_secondary_text(msg)
            dialog.run()
            dialog.destroy()
    
    def _on_unmount(self, button):
        if button:
            button.set_sensitive(False)
        
        def unmount_async():
            try:
                success, msg = self.mount_manager.unmount(Path(self.task.local_path))
                GLib.idle_add(self._on_unmount_complete, success, msg, button)
            except Exception as e:
                GLib.idle_add(self._on_unmount_complete, False, str(e), button)
        
        import threading
        thread = threading.Thread(target=unmount_async, daemon=True)
        thread.start()
    
    def _on_unmount_complete(self, success, msg, button):
        self._update_status()
        if button:
            button.set_sensitive(True)
        
        if not success:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Error al desmontar"
            )
            dialog.format_secondary_text(msg)
            dialog.run()
            dialog.destroy()
    
    def _on_open_folder(self, button):
        try:
            import subprocess
            subprocess.Popen(["xdg-open", str(self.task.local_path)])
        except Exception as e:
            print(f"Error opening folder: {e}")
    
    def _on_sync(self, button):
        button.set_sensitive(False)
        
        def sync_async():
            try:
                success, msg = self.sync_manager.run_sync(self.task)
                GLib.idle_add(self._on_sync_complete, success, msg, button)
            except Exception as e:
                GLib.idle_add(self._on_sync_complete, False, str(e), button)
        
        import threading
        thread = threading.Thread(target=sync_async, daemon=True)
        thread.start()
    
    def _on_sync_complete(self, success: bool, msg: str, button):
        from lxdrive.backend.models import TaskManager
        task_manager = TaskManager()
        updated_task = task_manager.get_task(self.task.id)
        if updated_task:
            self.task = updated_task
        
        self._update_status()
        button.set_sensitive(True)
        
        if not success:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=_("sync_error")
            )
            dialog.format_secondary_text(msg)
            dialog.run()
            dialog.destroy()
    
    def _on_edit_clicked(self, button):
        self.emit("edit-requested")
    
    def _on_delete_clicked(self, button):
        self.emit("remove-requested")
    
    def _on_show_history(self, button):
        if not self.task.sync_history:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=_("no_sync_history")
            )
            dialog.run()
            dialog.destroy()
            return
        
        history_text = f"<b>Historial de Sincronizaciones</b>\n\n"
        for i, entry in enumerate(reversed(self.task.sync_history)):
            timestamp = entry.get("timestamp", "")
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime('%d/%m/%Y %H:%M')
            except:
                time_str = timestamp
            
            result = entry.get("result", "")
            message = entry.get("message", "")
            emoji = "✓" if result == "Éxito" else "✗"
            
            history_text += f"{emoji} <b>{time_str}</b>\n"
            history_text += f"   {message}\n\n"
        
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=_("sync_history")
        )
        dialog.format_secondary_text(history_text)
        dialog.run()
        dialog.destroy()


class TasksPanel(Gtk.Box):
    def __init__(
        self,
        task_manager: TaskManager,
        rclone_manager: RcloneManager,
        mount_manager: MountManager,
        sync_manager: SyncManager,
        systemd_manager: SystemdManager,
        on_task_changed: Callable[[], None]
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.task_manager = task_manager
        self.rclone_manager = rclone_manager
        self.mount_manager = mount_manager
        self.sync_manager = sync_manager
        self.systemd_manager = systemd_manager
        self.on_task_changed = on_task_changed
        self.selected_task: Optional[SyncTask] = None
        self.task_rows: dict = {}
        
        self._setup_ui()
        self.refresh()
    
    def _setup_ui(self):
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(12)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        
        add_btn = Gtk.Button()
        add_btn.set_label(_("add_task"))
        add_btn.set_image(Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON))
        add_btn.set_always_show_image(True)
        add_btn.get_style_context().add_class("suggested-action")
        add_btn.connect("clicked", self._on_add_task)
        toolbar.pack_start(add_btn, False, False, 0)
        
        self.edit_btn = Gtk.Button()
        self.edit_btn.set_label(_("edit"))
        self.edit_btn.set_image(Gtk.Image.new_from_icon_name("document-edit-symbolic", Gtk.IconSize.BUTTON))
        self.edit_btn.set_always_show_image(True)
        self.edit_btn.set_sensitive(False)
        self.edit_btn.connect("clicked", self._on_edit_task)
        toolbar.pack_start(self.edit_btn, False, False, 0)
        
        self.remove_btn = Gtk.Button()
        self.remove_btn.set_label(_("remove"))
        self.remove_btn.set_image(Gtk.Image.new_from_icon_name("list-remove-symbolic", Gtk.IconSize.BUTTON))
        self.remove_btn.set_always_show_image(True)
        self.remove_btn.set_sensitive(False)
        self.remove_btn.connect("clicked", self._on_remove_task)
        toolbar.pack_start(self.remove_btn, False, False, 0)
        
        toolbar.pack_start(Gtk.Box(), True, True, 0)
        
        refresh_btn = Gtk.Button()
        refresh_btn.set_image(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON))
        refresh_btn.set_tooltip_text(_("refresh"))
        refresh_btn.connect("clicked", lambda b: self.refresh())
        toolbar.pack_start(refresh_btn, False, False, 0)
        
        self.pack_start(toolbar, False, False, 0)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.tasks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.tasks_box.set_margin_start(12)
        self.tasks_box.set_margin_end(12)
        self.tasks_box.set_margin_bottom(12)
        
        self.placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.placeholder.set_valign(Gtk.Align.CENTER)
        self.placeholder.set_halign(Gtk.Align.CENTER)
        self.placeholder.set_vexpand(True)
        
        placeholder_icon = Gtk.Image.new_from_icon_name("folder-remote-symbolic", Gtk.IconSize.DIALOG)
        placeholder_icon.set_pixel_size(64)
        placeholder_icon.get_style_context().add_class("dim-label")
        self.placeholder.pack_start(placeholder_icon, False, False, 0)
        
        placeholder_text = Gtk.Label()
        placeholder_text.set_markup("<span size='large' weight='bold'>No hay tareas configuradas</span>\n\nHaz clic en <b>Agregar Tarea</b> para crear\nuna tarea de montaje o sincronización.")
        placeholder_text.set_justify(Gtk.Justification.CENTER)
        placeholder_text.get_style_context().add_class("dim-label")
        self.placeholder.pack_start(placeholder_text, False, False, 0)
        
        self.tasks_box.pack_start(self.placeholder, True, True, 0)
        
        scrolled.add(self.tasks_box)
        self.pack_start(scrolled, True, True, 0)
    
    def refresh(self):
        for child in self.tasks_box.get_children():
            if child != self.placeholder:
                self.tasks_box.remove(child)
        
        self.task_rows.clear()
        self.selected_task = None
        self.remove_btn.set_sensitive(False)
        self.edit_btn.set_sensitive(False)
        
        self.task_manager.load()
        
        if self.task_manager.tasks:
            self.placeholder.hide()
            for task in self.task_manager.tasks:
                row = TaskRow(
                    task,
                    self.mount_manager,
                    self.sync_manager,
                    self.systemd_manager
                )
                row.connect("selected", self._on_task_selected)
                row.connect("edit-requested", self._on_edit_requested)
                row.connect("remove-requested", self._on_remove_requested)
                self.tasks_box.pack_start(row, False, False, 0)
                row.show_all()
                self.task_rows[task.id] = row
        else:
            self.placeholder.show_all()
        
        self.show_all()
    
    def _on_task_selected(self, row):
        self.selected_task = row.task
        self.remove_btn.set_sensitive(True)
        self.edit_btn.set_sensitive(True)
    
    def _on_edit_requested(self, row):
        self.selected_task = row.task
        self._on_edit_task(None)
    
    def _on_remove_requested(self, row):
        self.selected_task = row.task
        self._on_remove_task(None)
    
    def _on_add_task(self, button):
        remotes = self.rclone_manager.list_remotes()
        if not remotes:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=_("no_accounts_configured")
            )
            dialog.format_secondary_text(_("add_cloud_first"))
            dialog.run()
            dialog.destroy()
            return
        
        parent = self.get_toplevel()
        dialog = TaskDialog(parent, remotes, self.task_manager, self.rclone_manager)
        dialog.connect("task-saved", self._on_task_saved_cb)
        dialog.show_all()
    
    def _on_edit_task(self, button):
        if not self.selected_task:
            return
        
        remotes = self.rclone_manager.list_remotes()
        if not remotes:
            return
        
        parent = self.get_toplevel()
        dialog = TaskDialog(parent, remotes, self.task_manager, self.rclone_manager, self.selected_task)
        dialog.connect("task-saved", self._on_task_saved_cb)
        dialog.show_all()
    
    def _on_task_saved_cb(self, dialog, task_id: str):
        self.selected_task = None
        self.remove_btn.set_sensitive(False)
        self.edit_btn.set_sensitive(False)
        self.refresh()
        if self.on_task_changed:
            self.on_task_changed()
    
    def _on_remove_task(self, button):
        if not self.selected_task:
            return
        
        task_display = self.selected_task.name if self.selected_task.name else f"{self.selected_task.remote_name}:{self.selected_task.remote_path}"
        
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("remove_task")
        )
        dialog.format_secondary_text(_("remove_task_desc", name=task_display))
        
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            self.task_manager.remove_task(self.selected_task.id)
            self.selected_task = None
            self.remove_btn.set_sensitive(False)
            self.edit_btn.set_sensitive(False)
            self.refresh()
            if self.on_task_changed:
                self.on_task_changed()
    
    def get_selected_task(self) -> Optional[SyncTask]:
        return self.selected_task
