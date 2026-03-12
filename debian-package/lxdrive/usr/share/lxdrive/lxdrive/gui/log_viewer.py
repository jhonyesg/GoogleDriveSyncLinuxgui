import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib
from lxdrive.utils.translations import _


class LogViewer(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        self._setup_ui()
    
    def _setup_ui(self):
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_bottom(12)
        
        clear_button = Gtk.Button(label=_("clear"))
        clear_button.set_image(Gtk.Image.new_from_icon_name("edit-clear-symbolic", Gtk.IconSize.BUTTON))
        clear_button.set_always_show_image(True)
        clear_button.connect("clicked", self._on_clear)
        toolbar.pack_start(clear_button, False, False, 0)
        
        level_label = Gtk.Label(label=_("log_level_label"))
        toolbar.pack_start(level_label, False, False, 6)
        
        self.level_combo = Gtk.ComboBoxText()
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            self.level_combo.append_text(level)
        self.level_combo.set_active(1)
        self.level_combo.connect("changed", self._on_level_changed)
        toolbar.pack_start(self.level_combo, False, False, 0)
        
        toolbar.pack_start(Gtk.Box(), True, True, 0)
        
        refresh_button = Gtk.Button()
        refresh_button.set_image(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON))
        refresh_button.set_tooltip_text(_("refresh"))
        refresh_button.connect("clicked", lambda b: self._refresh_logs())
        toolbar.pack_start(refresh_button, False, False, 0)
        
        self.pack_start(toolbar, False, False, 0)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        
        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView()
        self.log_view.set_buffer(self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        
        scrolled.add(self.log_view)
        self.pack_start(scrolled, True, True, 0)
        
        self._refresh_logs()
    
    def _refresh_logs(self):
        from lxdrive.utils.logger import get_log_records
        records = get_log_records()
        self.log_buffer.set_text("\n".join(records))
        
        end_iter = self.log_buffer.get_end_iter()
        self.log_view.scroll_to_iter(end_iter, 0.0, True, 0.0, 1.0)
    
    def append_log(self, message: str, level: str):
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, message + "\n")
        
        end_iter = self.log_buffer.get_end_iter()
        self.log_view.scroll_to_iter(end_iter, 0.0, True, 0.0, 1.0)
    
    def _on_clear(self, button):
        from lxdrive.utils.logger import clear_log_records
        clear_log_records()
        self.log_buffer.set_text("")
    
    def _on_level_changed(self, combo):
        from lxdrive.utils.logger import set_log_level
        selected = combo.get_active()
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if selected >= 0 and selected < len(levels):
            set_log_level(levels[selected])
