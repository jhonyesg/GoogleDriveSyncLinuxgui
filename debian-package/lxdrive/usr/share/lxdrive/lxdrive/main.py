import sys
import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gio

from lxdrive.config import APP_NAME, APP_ID, VERSION, ensure_directories
from lxdrive.gui.main_window import LXDriveApp


def main():
    ensure_directories()
    
    app = LXDriveApp()
    
    try:
        exit_status = app.run(sys.argv)
        sys.exit(exit_status)
    except KeyboardInterrupt:
        app.quit()
        sys.exit(0)


if __name__ == "__main__":
    main()
