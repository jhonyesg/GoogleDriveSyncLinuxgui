import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GObject
from typing import Optional
from pathlib import Path
import uuid

from lxdrive.config import TaskType, DEFAULT_MOUNT_BASE
from lxdrive.backend.models import SyncTask, TaskManager
from lxdrive.backend.rclone_manager import RcloneManager
from lxdrive.gui.remote_folder_dialog import RemoteFolderDialog
from lxdrive.utils.translations import _


class AddTaskDialog(Gtk.Dialog):
    __gsignals__ = {
        "task-added": (GObject.SignalFlags.RUN_FIRST, None, (str,))
    }
    
    def __init__(self, parent: Gtk.Window, remotes: list, task_manager: TaskManager, rclone_manager: RcloneManager):
        super().__init__(
            title=_("add_task"),
            transient_for=parent,
            modal=True,
            use_header_bar=True
        )
        
        self.remotes = remotes
        self.task_manager = task_manager
        self.rclone_manager = rclone_manager
        
        self._setup_ui()
        self.set_default_size(500, 450)
        self.show_all()
    
    def _setup_ui(self):
        self.add_button(_("cancel"), Gtk.ResponseType.CANCEL)
        self.add_button(_("create"), Gtk.ResponseType.OK)
        
        content = self.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_spacing(12)
        
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
    
    def _update_default_path(self):
        selected = self.remote_combo.get_active()
        if selected >= 0 and selected < len(self.remotes):
            remote_name = self.remotes[selected]
            default_path = DEFAULT_MOUNT_BASE / remote_name
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
            self._create_task()
        else:
            self.destroy()
    
    def _create_task(self):
        selected = self.remote_combo.get_active()
        if selected < 0 or selected >= len(self.remotes):
            return
        
        remote_name = self.remotes[selected]
        remote_path = self.remote_path_entry.get_text().strip() or "/"
        local_path = Path(self.local_path_entry.get_text().strip()).expanduser()
        
        if not local_path.is_absolute():
            local_path = Path.home() / local_path
        
        task_type = self._get_task_type()
        
        task_id = str(uuid.uuid4())[:8]
        
        task = SyncTask(
            id=task_id,
            remote_name=remote_name,
            remote_path=remote_path,
            local_path=str(local_path),
            task_type=task_type,
            enabled=True,
            autostart=False
        )
        
        self.task_manager.add_task(task)
        
        self.emit("task-added", task_id)
        self.destroy()
