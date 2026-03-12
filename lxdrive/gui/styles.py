import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gdk


LIGHT_THEME = """
window {
    background-color: @theme_bg_color;
}

.list-row:selected {
    background-color: @theme_selected_bg_color;
}

.status-active {
    color: #2ecc71;
}

.status-inactive {
    color: #e74c3c;
}

.status-syncing {
    color: #3498db;
}
"""

DARK_THEME = """
window {
    background-color: #1e1e1e;
    color: #ffffff;
}

.list-row {
    background-color: #2d2d2d;
    color: #ffffff;
}

.list-row:selected {
    background-color: #3498db;
}

.header-bar {
    background-color: #252525;
}

.status-active {
    color: #2ecc71;
}

.status-inactive {
    color: #e74c3c;
}

.status-syncing {
    color: #3498db;
}

button {
    background-color: #3d3d3d;
    color: #ffffff;
}

entry {
    background-color: #3d3d3d;
    color: #ffffff;
}

treeview {
    background-color: #2d2d2d;
    color: #ffffff;
}

treeview:selected {
    background-color: #3498db;
}
"""


def get_css_provider(theme: str = "system") -> Gtk.CssProvider:
    provider = Gtk.CssProvider()
    
    if theme == "dark":
        css_data = DARK_THEME
    elif theme == "light":
        css_data = LIGHT_THEME
    else:
        gtk_settings = Gtk.Settings.get_default()
        if gtk_settings:
            prefer_dark = gtk_settings.get_property("gtk-application-prefer-dark-theme")
            css_data = DARK_THEME if prefer_dark else LIGHT_THEME
        else:
            css_data = LIGHT_THEME
    
    provider.load_from_data(css_data.encode())
    return provider


def apply_theme(theme: str = "system"):
    provider = get_css_provider(theme)
    
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    gtk_settings = Gtk.Settings.get_default()
    if gtk_settings:
        if theme == "dark":
            gtk_settings.set_property("gtk-application-prefer-dark-theme", True)
        elif theme == "light":
            gtk_settings.set_property("gtk-application-prefer-dark-theme", False)
