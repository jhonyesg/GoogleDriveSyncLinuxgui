import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, Pango
from typing import Optional
import threading

from lxdrive.backend.rclone_manager import RcloneManager
from lxdrive.utils.translations import _


class RemoteFolderDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, rclone_manager: RcloneManager, remote_name: str):
        super().__init__(
            title=_("select_remote_folder"),
            transient_for=parent,
            modal=True,
            use_header_bar=True
        )
        
        self.rclone_manager = rclone_manager
        self.remote_name = remote_name
        self.current_path = ""
        self.selected_path = ""
        
        self._setup_ui()
        self.set_default_size(500, 400)
        self._load_directory("")
        self.show_all()
    
    def _setup_ui(self):
        self.add_button(_("cancel"), Gtk.ResponseType.CANCEL)
        self.select_button = self.add_button(_("select_btn"), Gtk.ResponseType.OK)
        self.select_button.set_sensitive(False)
        
        content = self.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_spacing(6)
        
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        self.back_button = Gtk.Button()
        self.back_button.set_image(Gtk.Image.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON))
        self.back_button.set_sensitive(False)
        self.back_button.connect("clicked", self._on_go_back)
        nav_box.pack_start(self.back_button, False, False, 0)
        
        self.home_button = Gtk.Button()
        self.home_button.set_image(Gtk.Image.new_from_icon_name("go-home-symbolic", Gtk.IconSize.BUTTON))
        self.home_button.connect("clicked", self._on_go_home)
        nav_box.pack_start(self.home_button, False, False, 0)
        
        self.path_entry = Gtk.Entry()
        self.path_entry.set_hexpand(True)
        self.path_entry.set_editable(False)
        self.path_entry.set_text("/")
        nav_box.pack_start(self.path_entry, True, True, 0)
        
        self.refresh_button = Gtk.Button()
        self.refresh_button.set_image(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON))
        self.refresh_button.connect("clicked", self._on_refresh)
        nav_box.pack_start(self.refresh_button, False, False, 0)
        
        content.pack_start(nav_box, False, False, 0)
        
        self.loading_spinner = Gtk.Spinner()
        self.loading_spinner.set_halign(Gtk.Align.CENTER)
        self.loading_spinner.set_margin_top(50)
        content.pack_start(self.loading_spinner, False, False, 0)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.folder_list = Gtk.ListBox()
        self.folder_list.set_activate_on_single_click(False)
        self.folder_list.connect("row-activated", self._on_row_activated)
        self.folder_list.connect("row-selected", self._on_row_selected)
        
        scrolled.add(self.folder_list)
        content.pack_start(scrolled, True, True, 0)
        
        self.path_history = []
    
    def _load_directory(self, path: str):
        self.loading_spinner.start()
        self.loading_spinner.show()
        self.folder_list.hide()
        self.select_button.set_sensitive(False)
        
        def load_async():
            files = self.rclone_manager.list_remote_files(self.remote_name, path)
            folders = [f for f in files if f.get("IsDir", False)]
            GLib.idle_add(self._update_folder_list, path, folders)
        
        thread = threading.Thread(target=load_async, daemon=True)
        thread.start()
    
    def _update_folder_list(self, path: str, folders: list):
        self.loading_spinner.stop()
        self.loading_spinner.hide()
        
        for child in self.folder_list.get_children():
            self.folder_list.remove(child)
        
        self.current_path = path
        display_path = f"/{path}" if path else "/"
        self.path_entry.set_text(display_path)
        
        self.back_button.set_sensitive(len(self.path_history) > 0)
        
        root_row = self._create_folder_row("", "/", True)
        self.folder_list.add(root_row)
        
        for folder in sorted(folders, key=lambda x: x.get("Name", "").lower()):
            folder_path = folder.get("Path", "")
            name = folder.get("Name", "")
            if folder_path:
                row = self._create_folder_row(folder_path, name, False)
                self.folder_list.add(row)
        
        self.folder_list.show_all()
    
    def _create_folder_row(self, path: str, name: str, is_root: bool) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.folder_path = path
        row.is_root = is_root
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        if is_root:
            icon = Gtk.Image.new_from_icon_name("go-home-symbolic", Gtk.IconSize.MENU)
            label_text = "<b>/</b> (raíz)"
        else:
            icon = Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.MENU)
            label_text = name
        
        box.pack_start(icon, False, False, 0)
        
        label = Gtk.Label()
        label.set_markup(label_text)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        box.pack_start(label, True, True, 0)
        
        row.add(box)
        return row
    
    def _on_row_activated(self, list_box, row):
        if hasattr(row, 'folder_path'):
            self.path_history.append(self.current_path)
            self._load_directory(row.folder_path)
    
    def _on_row_selected(self, list_box, row):
        if row and hasattr(row, 'folder_path'):
            self.selected_path = row.folder_path
            self.select_button.set_sensitive(True)
        else:
            self.select_button.set_sensitive(False)
    
    def _on_go_back(self, button):
        if self.path_history:
            prev_path = self.path_history.pop()
            self._load_directory(prev_path)
    
    def _on_go_home(self, button):
        self.path_history.append(self.current_path)
        self._load_directory("")
    
    def _on_refresh(self, button):
        self._load_directory(self.current_path)
    
    def get_selected_path(self) -> str:
        return self.selected_path
