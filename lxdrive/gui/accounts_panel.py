import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gio, GLib
from typing import Callable, Optional
from pathlib import Path

from lxdrive.config import SUPPORTED_PROVIDERS
from lxdrive.backend.rclone_manager import RcloneManager, QuotaInfo
from lxdrive.gui.add_account_dialog import AddAccountDialog
from lxdrive.utils.translations import _


class AccountRow(Gtk.ListBoxRow):
    def __init__(self, remote_name: str, provider: str, rclone_manager: RcloneManager, icon_size: Gtk.IconSize = Gtk.IconSize.LARGE_TOOLBAR):
        super().__init__()
        
        self.remote_name = remote_name
        self.provider = provider
        self.rclone_manager = rclone_manager
        self.icon_size = icon_size
        
        self._setup_ui()
        self._load_quota()
    
    def _setup_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        icon_name = self._get_icon_name()
        icon = Gtk.Image.new_from_icon_name(icon_name, self.icon_size)
        box.pack_start(icon, False, False, 0)
        
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        
        name_label = Gtk.Label(label=self.remote_name)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_markup(f"<b>{self.remote_name}</b>")
        info_box.pack_start(name_label, False, False, 0)
        
        provider_label = Gtk.Label(label=self.provider)
        provider_label.set_halign(Gtk.Align.START)
        provider_label.get_style_context().add_class("dim-label")
        info_box.pack_start(provider_label, False, False, 0)
        
        self.quota_label = Gtk.Label(label=_("loading_quota"))
        self.quota_label.set_halign(Gtk.Align.START)
        self.quota_label.get_style_context().add_class("dim-label")
        info_box.pack_start(self.quota_label, False, False, 0)
        
        box.pack_start(info_box, True, True, 0)
        
        self.status_icon = Gtk.Image()
        self.status_icon.set_from_icon_name("emblem-synchronizing-symbolic", Gtk.IconSize.BUTTON)
        box.pack_start(self.status_icon, False, False, 0)
        
        self.add(box)
    
    def _get_icon_name(self) -> str:
        for key, info in SUPPORTED_PROVIDERS.items():
            if info["name"] == self.provider or key == self.provider.lower():
                return info["icon"]
        return "folder-remote-symbolic"
    
    def _load_quota(self):
        def load_async():
            quota = self.rclone_manager.get_quota(self.remote_name)
            GLib.idle_add(self._update_quota, quota)
        
        import threading
        thread = threading.Thread(target=load_async, daemon=True)
        thread.start()
    
    def _update_quota(self, quota: Optional[QuotaInfo]):
        if quota:
            text = f"{quota.used_human} / {quota.total_human} ({quota.percentage:.1f}%)"
            self.quota_label.set_text(text)
            self.status_icon.set_from_icon_name("emblem-default-symbolic", Gtk.IconSize.BUTTON)
        else:
            self.quota_label.set_text(_("quota_not_available"))
            self.status_icon.set_from_icon_name("dialog-warning-symbolic", Gtk.IconSize.BUTTON)
        return False


class AccountsPanel(Gtk.Box):
    def __init__(
        self,
        rclone_manager: RcloneManager,
        on_account_added: Callable[[str], None],
        on_account_removed: Callable[[str], None],
        config = None
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        self.rclone_manager = rclone_manager
        self.on_account_added = on_account_added
        self.on_account_removed = on_account_removed
        self.config = config
        
        self._setup_ui()
        self.refresh()
    
    def _setup_ui(self):
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_bottom(12)
        
        add_button = Gtk.Button(label=_("add_account"))
        add_button.set_image(Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON))
        add_button.set_always_show_image(True)
        add_button.connect("clicked", self._on_add_account)
        toolbar.pack_start(add_button, False, False, 0)
        
        self.remove_button = Gtk.Button(label=_("remove"))
        self.remove_button.set_image(Gtk.Image.new_from_icon_name("list-remove-symbolic", Gtk.IconSize.BUTTON))
        self.remove_button.set_always_show_image(True)
        self.remove_button.set_sensitive(False)
        self.remove_button.connect("clicked", self._on_remove_account)
        toolbar.pack_start(self.remove_button, False, False, 0)
        
        verify_button = Gtk.Button(label=_("verify"))
        verify_button.set_image(Gtk.Image.new_from_icon_name("network-transmit-receive-symbolic", Gtk.IconSize.BUTTON))
        verify_button.set_always_show_image(True)
        verify_button.connect("clicked", self._on_verify_connection)
        toolbar.pack_start(verify_button, False, False, 0)
        
        toolbar.pack_start(Gtk.Box(), True, True, 0)
        
        refresh_button = Gtk.Button()
        refresh_button.set_image(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON))
        refresh_button.set_tooltip_text(_("refresh"))
        refresh_button.connect("clicked", lambda b: self.refresh())
        toolbar.pack_start(refresh_button, False, False, 0)
        
        self.pack_start(toolbar, False, False, 0)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.connect("row-selected", self._on_row_selected)
        
        scrolled.add(self.list_box)
        self.pack_start(scrolled, True, True, 0)
        
        self.placeholder = Gtk.Label(label=_("no_accounts"))
        self.placeholder.set_vexpand(True)
        self.placeholder.get_style_context().add_class("dim-label")
        self.list_box.set_placeholder(self.placeholder)
    
    def refresh(self):
        for child in self.list_box.get_children():
            self.list_box.remove(child)
        
        if not self.rclone_manager.is_available():
            self.placeholder.set_text(_("rclone_not_installed"))
            return
        
        remotes = self.rclone_manager.list_remotes()
        
        for remote_name in remotes:
            info = self.rclone_manager.get_remote_info(remote_name)
            if info:
                icon_size = self._get_icon_size()
                row = AccountRow(remote_name, info.provider, self.rclone_manager, icon_size)
                self.list_box.add(row)
        
        self.show_all()
    
    def _on_row_selected(self, list_box, row):
        self.remove_button.set_sensitive(row is not None)
    
    def _on_add_account(self, button):
        parent = self.get_toplevel()
        dialog = AddAccountDialog(parent, self.rclone_manager)
        dialog.connect("account-added", self._on_account_added_cb)
        dialog.show_all()
    
    def _on_account_added_cb(self, dialog, remote_name: str):
        self.refresh()
        if self.on_account_added:
            self.on_account_added(remote_name)
    
    def _on_remove_account(self, button):
        row = self.list_box.get_selected_row()
        if not row:
            return
        
        remote_name = row.remote_name
        
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("remove_account", name=remote_name)
        )
        dialog.format_secondary_text(_("remove_account_desc"))
        
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            success, msg = self.rclone_manager.delete_remote(remote_name)
            if success:
                self.refresh()
                if self.on_account_removed:
                    self.on_account_removed(remote_name)
            else:
                error_dialog = Gtk.MessageDialog(
                    transient_for=self.get_toplevel(),
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=_("failed_remove_account")
                )
                error_dialog.format_secondary_text(msg)
                error_dialog.run()
                error_dialog.destroy()
    
    def _on_verify_connection(self, button):
        row = self.list_box.get_selected_row()
        if not row:
            return
        
        remote_name = row.remote_name
        
        def verify_async():
            success, msg = self.rclone_manager.check_connection(remote_name)
            GLib.idle_add(self._show_verify_result, remote_name, success, msg)
        
        import threading
        thread = threading.Thread(target=verify_async, daemon=True)
        thread.start()
    
    def _show_verify_result(self, remote_name: str, success: bool, msg: str):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.INFO if success else Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=_("connection_to", name=remote_name)
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()
        return False
    
    def get_selected_remote(self) -> Optional[str]:
        row = self.list_box.get_selected_row()
        return row.remote_name if row else None
    
    def _get_icon_size(self) -> Gtk.IconSize:
        if self.config and hasattr(self.config, 'icon_size'):
            from lxdrive.config import IconSize
            size_map = {
                IconSize.SMALL: Gtk.IconSize.MENU,
                IconSize.MEDIUM: Gtk.IconSize.LARGE_TOOLBAR,
                IconSize.LARGE: Gtk.IconSize.DIALOG,
            }
            return size_map.get(self.config.icon_size, Gtk.IconSize.LARGE_TOOLBAR)
        return Gtk.IconSize.LARGE_TOOLBAR
    
    def update_config(self, config):
        self.config = config
        self.refresh()
