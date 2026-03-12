import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gio
from typing import Optional

from lxdrive.backend.models import AppConfig
from lxdrive.config import Theme, IconSize
from lxdrive.gui.styles import apply_theme
from lxdrive.utils.autostart import enable_autostart, disable_autostart, is_autostart_enabled
from lxdrive.utils.translations import _, set_language, get_language


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, config: AppConfig):
        super().__init__(
            title=_("settings"),
            transient_for=parent,
            modal=True,
            use_header_bar=True
        )
        
        self.config = config
        self.parent_window = parent
        
        self._setup_ui()
        self.set_default_size(400, 400)
        self.show_all()
    
    def _setup_ui(self):
        self.add_button(_("cancel"), Gtk.ResponseType.CANCEL)
        self.add_button(_("apply"), Gtk.ResponseType.APPLY)
        
        content = self.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_spacing(12)
        
        appearance_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        appearance_label = Gtk.Label()
        appearance_label.set_markup(f"<b>{_('appearance')}</b>")
        appearance_label.set_halign(Gtk.Align.START)
        appearance_group.pack_start(appearance_label, False, False, 0)
        
        theme_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        theme_label = Gtk.Label(label=_("theme"))
        theme_label.set_halign(Gtk.Align.START)
        theme_label.set_hexpand(True)
        theme_box.pack_start(theme_label, False, False, 0)
        
        self.theme_combo = Gtk.ComboBoxText()
        for t in [_("system"), _("light"), _("dark")]:
            self.theme_combo.append_text(t)
        
        current_theme = self.config.theme.value
        theme_index = {"system": 0, "light": 1, "dark": 2}.get(current_theme, 0)
        self.theme_combo.set_active(theme_index)
        theme_box.pack_start(self.theme_combo, True, True, 0)
        
        appearance_group.pack_start(theme_box, False, False, 0)
        
        icon_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon_label = Gtk.Label(label=_("icon_size"))
        icon_label.set_halign(Gtk.Align.START)
        icon_label.set_hexpand(True)
        icon_box.pack_start(icon_label, False, False, 0)
        
        self.icon_combo = Gtk.ComboBoxText()
        self.icon_combo.append_text(_("small"))
        self.icon_combo.append_text(_("medium"))
        self.icon_combo.append_text(_("large"))
        
        current_icon = self.config.icon_size.value
        icon_index = {"small": 0, "medium": 1, "large": 2}.get(current_icon, 1)
        self.icon_combo.set_active(icon_index)
        icon_box.pack_start(self.icon_combo, True, True, 0)
        
        appearance_group.pack_start(icon_box, False, False, 0)
        content.pack_start(appearance_group, False, False, 0)
        
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        
        general_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        general_label = Gtk.Label()
        general_label.set_markup(f"<b>{_('general')}</b>")
        general_label.set_halign(Gtk.Align.START)
        general_group.pack_start(general_label, False, False, 0)
        
        lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lang_label = Gtk.Label(label=_("language"))
        lang_label.set_halign(Gtk.Align.START)
        lang_label.set_hexpand(True)
        lang_box.pack_start(lang_label, False, False, 0)
        
        self.lang_combo = Gtk.ComboBoxText()
        self.lang_combo.append_text(_("spanish"))
        self.lang_combo.append_text(_("english"))
        current_lang = get_language()
        lang_index = 0 if current_lang == "es" else 1
        self.lang_combo.set_active(lang_index)
        lang_box.pack_start(self.lang_combo, True, True, 0)
        
        general_group.pack_start(lang_box, False, False, 0)
        
        autostart_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        autostart_label = Gtk.Label(label=_("start_with_system"))
        autostart_label.set_halign(Gtk.Align.START)
        autostart_label.set_hexpand(True)
        autostart_box.pack_start(autostart_label, False, False, 0)
        
        self.autostart_switch = Gtk.Switch()
        self.autostart_switch.set_active(is_autostart_enabled())
        autostart_box.pack_start(self.autostart_switch, False, False, 0)
        
        general_group.pack_start(autostart_box, False, False, 0)
        
        mount_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        mount_label = Gtk.Label(label=_("mount_base_path"))
        mount_label.set_halign(Gtk.Align.START)
        mount_label.set_hexpand(True)
        mount_box.pack_start(mount_label, False, False, 0)
        
        self.mount_entry = Gtk.Entry()
        self.mount_entry.set_text(getattr(self.config, 'mount_base_path', str(self.config.mount_base_path) if hasattr(self.config, 'mount_base_path') else ''))
        self.mount_entry.set_hexpand(True)
        mount_box.pack_start(self.mount_entry, True, True, 0)
        
        browse_button = Gtk.Button()
        browse_button.set_image(Gtk.Image.new_from_icon_name("folder-open-symbolic", Gtk.IconSize.BUTTON))
        browse_button.connect("clicked", self._on_browse_mount_path)
        mount_box.pack_start(browse_button, False, False, 0)
        
        general_group.pack_start(mount_box, False, False, 0)
        content.pack_start(general_group, False, False, 0)
        
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        
        advanced_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        advanced_label = Gtk.Label()
        advanced_label.set_markup(f"<b>{_('advanced')}</b>")
        advanced_label.set_halign(Gtk.Align.START)
        advanced_group.pack_start(advanced_label, False, False, 0)
        
        log_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        log_label = Gtk.Label(label=_("log_level"))
        log_label.set_halign(Gtk.Align.START)
        log_label.set_hexpand(True)
        log_box.pack_start(log_label, False, False, 0)
        
        self.log_combo = Gtk.ComboBoxText()
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            self.log_combo.append_text(level)
        
        log_index = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}.get(self.config.log_level, 1)
        self.log_combo.set_active(log_index)
        log_box.pack_start(self.log_combo, True, True, 0)
        
        advanced_group.pack_start(log_box, False, False, 0)
        content.pack_start(advanced_group, False, False, 0)
    
    def _on_browse_mount_path(self, button):
        dialog = Gtk.FileChooserDialog(
            title=_("select_mount_base"),
            transient_for=self,
            modal=True,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.OK
            )
        )
        
        current = self.mount_entry.get_text()
        if current:
            dialog.set_current_folder(current)
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.mount_entry.set_text(dialog.get_filename())
        dialog.destroy()
    
    def apply_settings(self):
        theme_index = self.theme_combo.get_active()
        themes = [Theme.SYSTEM, Theme.LIGHT, Theme.DARK]
        self.config.theme = themes[theme_index]
        
        lang_index = self.lang_combo.get_active()
        languages = ["es", "en"]
        set_language(languages[lang_index])
        
        autostart_enabled = self.autostart_switch.get_active()
        if autostart_enabled:
            enable_autostart()
        else:
            disable_autostart()
        self.config.autostart_app = autostart_enabled
        
        self.config.mount_base_path = self.mount_entry.get_text()
        
        log_index = self.log_combo.get_active()
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        self.config.log_level = levels[log_index]
        
        icon_index = self.icon_combo.get_active()
        icon_sizes = [IconSize.SMALL, IconSize.MEDIUM, IconSize.LARGE]
        self.config.icon_size = icon_sizes[icon_index]
        
        apply_theme(self.config.theme.value)
        
        from lxdrive.config import CONFIG_FILE
        self.config.save(CONFIG_FILE)
