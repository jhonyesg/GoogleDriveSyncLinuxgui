import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, GObject
from typing import Optional
import threading

from lxdrive.config import SUPPORTED_PROVIDERS
from lxdrive.backend.rclone_manager import RcloneManager
from lxdrive.utils.translations import _


class AddAccountDialog(Gtk.Dialog):
    __gsignals__ = {
        "account-added": (GObject.SignalFlags.RUN_FIRST, None, (str,))
    }
    
    def __init__(self, parent: Gtk.Window, rclone_manager: RcloneManager):
        super().__init__(
            title=_("add_cloud_account"),
            transient_for=parent,
            modal=True,
            use_header_bar=True
        )
        
        self.rclone_manager = rclone_manager
        self.selected_provider: Optional[str] = None
        
        self._setup_ui()
        self.set_default_size(500, 400)
        self.show_all()
    
    def _setup_ui(self):
        self.add_button(_("cancel"), Gtk.ResponseType.CANCEL)
        self.next_button = self.add_button(_("create"), Gtk.ResponseType.OK)
        self.next_button.set_sensitive(False)
        
        content = self.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_spacing(12)
        
        intro_label = Gtk.Label()
        intro_label.set_markup(_("select_provider"))
        intro_label.set_halign(Gtk.Align.START)
        content.pack_start(intro_label, False, False, 0)
        
        self.provider_grid = Gtk.Grid()
        self.provider_grid.set_row_spacing(12)
        self.provider_grid.set_column_spacing(12)
        self.provider_grid.set_row_homogeneous(True)
        self.provider_grid.set_column_homogeneous(True)
        
        providers = [
            ("gdrive", _("google_drive"), "goa-account-google"),
            ("onedrive", _("onedrive"), "goa-account-msn"),
            ("dropbox", _("dropbox"), "dropbox"),
        ]
        
        self.provider_buttons = {}
        
        for i, (key, name, icon) in enumerate(providers):
            button = Gtk.Button()
            button.set_size_request(140, 100)
            
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            
            icon_widget = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.DIALOG)
            box.pack_start(icon_widget, False, False, 0)
            
            label = Gtk.Label(label=name)
            box.pack_start(label, False, False, 0)
            
            button.add(box)
            button.connect("clicked", self._on_provider_selected, key)
            
            row = i // 3
            col = i % 3
            self.provider_grid.attach(button, col, row, 1, 1)
            self.provider_buttons[key] = button
        
        content.pack_start(self.provider_grid, False, False, 0)
        
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        
        self.name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        name_label = Gtk.Label(label=_("account_name"))
        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text(_("account_name_placeholder"))
        self.name_entry.connect("changed", self._on_name_changed)
        self.name_box.pack_start(name_label, False, False, 0)
        self.name_box.pack_start(self.name_entry, True, True, 0)
        content.pack_start(self.name_box, False, False, 0)
        
        self.status_label = Gtk.Label(label="")
        self.status_label.get_style_context().add_class("dim-label")
        content.pack_start(self.status_label, False, False, 0)
    
    def _on_provider_selected(self, button, provider_key: str):
        for key, btn in self.provider_buttons.items():
            ctx = btn.get_style_context()
            ctx.remove_class("suggested-action")
        
        ctx = button.get_style_context()
        ctx.add_class("suggested-action")
        self.selected_provider = provider_key
        
        default_name = f"my-{provider_key}"
        self.name_entry.set_text(default_name)
        
        self._validate()
    
    def _on_name_changed(self, entry):
        self._validate()
    
    def _validate(self):
        name = self.name_entry.get_text().strip()
        valid = bool(self.selected_provider and name and not name.isspace())
        self.next_button.set_sensitive(valid)
    
    def do_response(self, response_id):
        if response_id == Gtk.ResponseType.OK:
            self._configure_remote()
        else:
            self.destroy()
    
    def _configure_remote(self):
        name = self.name_entry.get_text().strip()
        
        self.next_button.set_sensitive(False)
        self.status_label.set_text(_("opening_rclone"))
        
        def configure_async():
            success, msg = self.rclone_manager.create_remote_interactive(
                name,
                self.selected_provider
            )
            GLib.idle_add(self._on_configured, success, msg, name)
        
        thread = threading.Thread(target=configure_async, daemon=True)
        thread.start()
    
    def _on_configured(self, success: bool, msg: str, name: str):
        if success:
            self.status_label.set_text(_("account_configured"))
            self.emit("account-added", name)
            self.destroy()
        else:
            self.status_label.set_text(f"Error: {msg}")
            self.next_button.set_sensitive(True)
            
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=_("failed_configure")
            )
            dialog.format_secondary_text(msg)
            dialog.run()
            dialog.destroy()
        
        return False
