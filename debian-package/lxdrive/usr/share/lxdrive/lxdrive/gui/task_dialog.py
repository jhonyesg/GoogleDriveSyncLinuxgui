import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GObject
from typing import Optional
from pathlib import Path
import os
import uuid

from lxdrive.config import TaskType, DEFAULT_MOUNT_BASE
from lxdrive.backend.models import SyncTask, TaskManager
from lxdrive.backend.rclone_manager import RcloneManager
from lxdrive.gui.remote_folder_dialog import RemoteFolderDialog
from lxdrive.utils.translations import _


class TaskDialog(Gtk.Dialog):
    __gsignals__ = {
        "task-saved": (GObject.SignalFlags.RUN_FIRST, None, (str,))
    }
    
    def __init__(self, parent: Gtk.Window, remotes: list, task_manager: TaskManager, 
                 rclone_manager: RcloneManager, task: SyncTask = None):
        super().__init__(
            title=_("edit_task") if task else _("add_task"),
            transient_for=parent,
            modal=True,
            use_header_bar=True
        )
        
        self.remotes = remotes
        self.task_manager = task_manager
        self.rclone_manager = rclone_manager
        self.editing_task = task
        
        self._setup_ui()
        self.set_default_size(500, 500)
        
        if task:
            self._load_task_data()
        
        self.show_all()
    
    def _setup_ui(self):
        self.add_button(_("cancel"), Gtk.ResponseType.CANCEL)
        self.add_button(_("save"), Gtk.ResponseType.OK)
        
        content = self.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_spacing(12)
        
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        name_label = Gtk.Label(label=_("task_name"))
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        name_box.pack_start(name_label, False, False, 0)
        
        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text(_("task_name_placeholder"))
        name_box.pack_start(self.name_entry, True, True, 0)
        
        content.pack_start(name_box, False, False, 0)
        
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        
        type_label = Gtk.Label()
        type_label.set_markup(_("task_type"))
        type_label.set_halign(Gtk.Align.START)
        content.pack_start(type_label, False, False, 0)
        
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        self.mount_radio = Gtk.RadioButton(label=_("mount_vfs"))
        self.mount_radio.set_active(True)
        type_box.pack_start(self.mount_radio, False, False, 0)
        
        self.sync_radio = Gtk.RadioButton(label=_("bidirectional_sync"), group=self.mount_radio)
        type_box.pack_start(self.sync_radio, False, False, 0)
        
        content.pack_start(type_box, False, False, 0)
        
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        
        remote_label = Gtk.Label()
        remote_label.set_markup(_("cloud_account"))
        remote_label.set_halign(Gtk.Align.START)
        content.pack_start(remote_label, False, False, 0)
        
        remote_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        remote_combo_label = Gtk.Label(label=_("remote"))
        remote_combo_label.set_halign(Gtk.Align.START)
        remote_combo_label.set_hexpand(True)
        remote_box.pack_start(remote_combo_label, False, False, 0)
        
        self.remote_combo = Gtk.ComboBoxText()
        for remote in self.remotes:
            self.remote_combo.append_text(remote)
        if self.remotes:
            self.remote_combo.set_active(0)
        remote_box.pack_start(self.remote_combo, True, True, 0)
        
        content.pack_start(remote_box, False, False, 0)
        
        remote_path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        remote_path_label = Gtk.Label(label=_("remote_path"))
        remote_path_label.set_halign(Gtk.Align.START)
        remote_path_label.set_hexpand(True)
        remote_path_box.pack_start(remote_path_label, False, False, 0)
        
        self.remote_path_entry = Gtk.Entry()
        self.remote_path_entry.set_placeholder_text(_("remote_path_placeholder"))
        self.remote_path_entry.set_text("/")
        remote_path_box.pack_start(self.remote_path_entry, True, True, 0)
        
        browse_remote_btn = Gtk.Button()
        browse_remote_btn.set_image(Gtk.Image.new_from_icon_name("folder-remote-symbolic", Gtk.IconSize.BUTTON))
        browse_remote_btn.set_tooltip_text(_("select_remote_folder"))
        browse_remote_btn.connect("clicked", self._on_browse_remote_path)
        remote_path_box.pack_start(browse_remote_btn, False, False, 0)
        
        content.pack_start(remote_path_box, False, False, 0)
        
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        
        local_label = Gtk.Label()
        local_label.set_markup(_("local_path"))
        local_label.set_halign(Gtk.Align.START)
        content.pack_start(local_label, False, False, 0)
        
        local_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        local_path_label = Gtk.Label(label=_("local_folder"))
        local_path_label.set_halign(Gtk.Align.START)
        local_path_label.set_hexpand(True)
        local_box.pack_start(local_path_label, False, False, 0)
        
        self.local_path_entry = Gtk.Entry()
        self.local_path_entry.set_placeholder_text(_("local_folder_placeholder"))
        local_box.pack_start(self.local_path_entry, True, True, 0)
        
        browse_button = Gtk.Button()
        browse_button.set_image(Gtk.Image.new_from_icon_name("folder-open-symbolic", Gtk.IconSize.BUTTON))
        browse_button.set_tooltip_text(_("select_local_folder"))
        browse_button.connect("clicked", self._on_browse_local_path)
        local_box.pack_start(browse_button, False, False, 0)
        
        content.pack_start(local_box, False, False, 0)
        
        self._update_default_path()
        self.remote_combo.connect("changed", lambda *args: self._update_default_path())
    
    def _load_task_data(self):
        self.name_entry.set_text(self.editing_task.name or "")
        
        if self.editing_task.task_type == TaskType.MOUNT:
            self.mount_radio.set_active(True)
        else:
            self.sync_radio.set_active(True)
        
        for i, remote in enumerate(self.remotes):
            if remote == self.editing_task.remote_name:
                self.remote_combo.set_active(i)
                break
        
        self.remote_path_entry.set_text(self.editing_task.remote_path)
        self.local_path_entry.set_text(self.editing_task.local_path)
    
    def _update_default_path(self):
        selected = self.remote_combo.get_active()
        if selected >= 0 and selected < len(self.remotes):
            remote_name = self.remotes[selected]
            default_path = DEFAULT_MOUNT_BASE / remote_name
            if not self.editing_task and not self.local_path_entry.get_text():
                self.local_path_entry.set_text(str(default_path))
    
    def _on_browse_remote_path(self, button):
        selected = self.remote_combo.get_active()
        if selected < 0 or selected >= len(self.remotes):
            return
        
        remote_name = self.remotes[selected]
        
        dialog = RemoteFolderDialog(self, self.rclone_manager, remote_name)
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            selected_path = dialog.get_selected_path()
            if selected_path:
                display_path = f"/{selected_path}" if selected_path else "/"
                self.remote_path_entry.set_text(display_path)
        
        dialog.destroy()
    
    def _on_browse_local_path(self, button):
        dialog = Gtk.FileChooserDialog(
            title=_("select_local_folder"),
            transient_for=self,
            modal=True,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.OK
            )
        )
        
        current = self.local_path_entry.get_text()
        if current:
            expanded = str(Path(current).expanduser())
            dialog.set_current_folder(expanded)
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.local_path_entry.set_text(dialog.get_filename())
        dialog.destroy()
    
    def _get_task_type(self) -> TaskType:
        if self.mount_radio.get_active():
            return TaskType.MOUNT
        return TaskType.BISYNC
    
    def do_response(self, response_id):
        if response_id == Gtk.ResponseType.OK:
            self._save_task()
        else:
            self.destroy()
    
    def _validate_task(self) -> tuple[bool, str]:
        selected = self.remote_combo.get_active()
        if selected < 0 or selected >= len(self.remotes):
            return False, _("select_remote_account")
        
        remote_name = self.remotes[selected]
        local_path_str = self.local_path_entry.get_text().strip()
        
        if not local_path_str:
            return False, _("local_path_required")
        
        local_path = Path(local_path_str).expanduser()
        
        if not local_path.is_absolute():
            local_path = Path.home() / local_path
        
        if not local_path.parent.exists():
            return False, f"El directorio padre no existe: {local_path.parent}"
        
        if not os.access(str(local_path.parent), os.W_OK):
            return False, f"No tienes permisos de escritura en: {local_path.parent}"
        
        if local_path.exists():
            if not local_path.is_dir():
                return False, f"La ruta existe pero no es un directorio: {local_path}"
            if not os.access(str(local_path), os.R_OK | os.W_OK):
                return False, f"No tienes permisos de lectura/escritura en: {local_path}"
        
        return True, ""
    
    def _save_task(self):
        valid, error_msg = self._validate_task()
        if not valid:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=_("validation_error")
            )
            dialog.format_secondary_text(error_msg)
            dialog.run()
            dialog.destroy()
            return
        
        selected = self.remote_combo.get_active()
        remote_name = self.remotes[selected]
        remote_path = self.remote_path_entry.get_text().strip() or "/"
        local_path = Path(self.local_path_entry.get_text().strip()).expanduser()
        task_name = self.name_entry.get_text().strip()
        
        if not task_name:
            task_name = f"{remote_name} - {remote_path}"
        
        if not local_path.is_absolute():
            local_path = Path.home() / local_path
        
        local_path.mkdir(parents=True, exist_ok=True)
        
        task_type = self._get_task_type()
        
        if self.editing_task:
            self.editing_task.name = task_name
            self.editing_task.remote_name = remote_name
            self.editing_task.remote_path = remote_path
            self.editing_task.local_path = str(local_path)
            self.editing_task.task_type = task_type
            self.task_manager.save()
            self.emit("task-saved", self.editing_task.id)
        else:
            task_id = str(uuid.uuid4())[:8]
            
            task = SyncTask(
                id=task_id,
                name=task_name,
                remote_name=remote_name,
                remote_path=remote_path,
                local_path=str(local_path),
                task_type=task_type,
                enabled=True,
                autostart=False
            )
            
            self.task_manager.add_task(task)
            self.emit("task-saved", task_id)
        
        self.destroy()
