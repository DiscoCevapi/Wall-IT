#!/usr/bin/env python3
"""
Separate system tray process for Wall-IT to avoid GTK3/GTK4 conflicts
On Wayland (like Niri), this may not show a traditional system tray icon
but will still enable IPC communication for tray functionality.
"""

import os
import sys
import signal
import subprocess
import time
from pathlib import Path

# Import for system tray (using GTK3 in separate process)
import gi
gi.require_version('Gtk', '3.0')

# Check for AppIndicator3 first
try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
    APP_INDICATOR_AVAILABLE = True
    print("✅ AppIndicator3 available")
except (ImportError, ValueError):
    APP_INDICATOR_AVAILABLE = False
    print("⚠️ AppIndicator3 not available")

from gi.repository import Gtk, GLib
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

# Check if we're on Wayland
IS_WAYLAND = os.environ.get('WAYLAND_DISPLAY') is not None
print(f"🌐 Running on {'Wayland' if IS_WAYLAND else 'X11'}")

# Check for specific desktop environments that may affect tray behavior
DESKTOP_ENV = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
WAYLAND_COMPOSITOR = os.environ.get('WAYLAND_COMPOSITOR', '').lower()

# Some Wayland compositors that support system trays or have alternatives
WAYLAND_TRAY_SUPPORTED = any([
    DESKTOP_ENV.startswith('kde'),
    DESKTOP_ENV.startswith('gnome'),
])

print(f"🖥️ Desktop Environment: {DESKTOP_ENV or 'Unknown'}")
print(f"🔧 Wayland Compositor: {WAYLAND_COMPOSITOR or 'None'}")

class WallItTray:
    def __init__(self):
        self.indicator = None
        self.main_loop = None
        
        if IS_WAYLAND and not WAYLAND_TRAY_SUPPORTED:
            # On Wayland with compositors that don't support system trays (like Niri)
            print("⚠️ On Wayland without tray support (Niri), system tray may not be visible")
            print("💡 Use the close button in the main application instead")
            # Still create the indicator for IPC functionality, but warn about visibility
            self._create_minimal_wayland_support()
            return
        elif IS_WAYLAND and WAYLAND_TRAY_SUPPORTED:
            # On Wayland with tray support (like KDE on Wayland)
            print("✅ On Wayland with tray support (KDE/GNOME)")
        elif not IS_WAYLAND:
            # On X11, traditional tray should work
            print("✅ On X11, traditional tray should work")
        
        # Try to use a disco ball icon from Documents/Terminal Logos folder
        icon_path = None
        docs_path = Path.home() / "Documents" / "Terminal Logos"
        if docs_path.exists():
            # Look for disco ball related icons first
            for pattern in ['*disco*', '*Discoball*', '*disco*.*', '*Discoball*.*']:
                for icon_file in docs_path.glob(pattern):
                    if icon_file.suffix.lower() in ['.png', '.svg', '.jpg', '.jpeg', '.ico']:
                        icon_path = str(icon_file)
                        break
                if icon_path:
                    break

            # If no disco-related icon found, use any image file
            if not icon_path:
                for ext in ['.png', '.svg', '.jpg', '.jpeg', '.ico']:
                    for icon_file in docs_path.glob(f'*{ext}'):
                        icon_path = str(icon_file)
                        break
                    if icon_path:
                        break

        # Check if AppIndicator3 is working properly by testing basic functionality
        if not self._test_app_indicator_support():
            print("⚠️ AppIndicator3 not working properly, falling back to StatusIcon")
            self._create_status_icon_fallback()
            return
    
    def _create_minimal_wayland_support(self):
        """Create minimal support for Wayland environments where tray icons don't work"""
        print("🔧 Setting up IPC communication for Wayland environment")
        
        # Create a minimal indicator that won't be visible but enables IPC
        try:
            self.indicator = AppIndicator3.Indicator.new(
                "wall-it",
                "image-x-generic",  # Minimal icon
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.indicator.set_title("🪩 Wall-IT")
            
            # Create menu for IPC functionality
            self.menu = Gtk.Menu()
            
            # Show Window item
            show_item = Gtk.MenuItem(label="Show Wall-IT")
            show_item.connect("activate", self._on_show_window)
            self.menu.append(show_item)
            
            # Separator
            sep1 = Gtk.SeparatorMenuItem()
            self.menu.append(sep1)
            
            # Random wallpaper item
            random_item = Gtk.MenuItem(label="🎲 Random Wallpaper")
            random_item.connect("activate", self._on_random_wallpaper)
            self.menu.append(random_item)
            
            # Next wallpaper item
            next_item = Gtk.MenuItem(label="➡️ Next Wallpaper")
            next_item.connect("activate", self._on_next_wallpaper)
            self.menu.append(next_item)
            
            # Separator
            sep2 = Gtk.SeparatorMenuItem()
            self.menu.append(sep2)
            
            # Auto-change toggle
            self.auto_toggle = Gtk.CheckMenuItem(label="⏰ Auto Change")
            self.auto_toggle.set_active(False)
            self.auto_toggle.connect("toggled", self._on_auto_toggle)
            self.menu.append(self.auto_toggle)
            
            # Separator
            sep3 = Gtk.SeparatorMenuItem()
            self.menu.append(sep3)
            
            # Quit item
            quit_item = Gtk.MenuItem(label="Quit")
            quit_item.connect("activate", self._on_quit)
            self.menu.append(quit_item)
            
            self.menu.show_all()
            self.indicator.set_menu(self.menu)
            
            print("✅ Wall-IT tray process running (IPC enabled for Wayland)")
        except Exception as e:
            print(f"⚠️ Could not create indicator even for Wayland: {e}")
            # Still try to run the main loop for IPC
            pass
    
    def _test_app_indicator_support(self):
        """Test if AppIndicator3 is working properly on this system"""
        try:
            # Try to create a minimal indicator to test support
            test_indicator = AppIndicator3.Indicator.new(
                "wall-it-test",
                "image-x-generic",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            test_indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
            # If we get here without error, AppIndicator is likely supported
            # Don't set to ACTIVE yet to avoid showing a test icon
            del test_indicator  # Clean up test indicator
            return True
        except Exception as e:
            print(f"⚠️ AppIndicator3 test failed: {e}")
            return False
    
    def _create_status_icon_fallback(self):
        """Create a StatusIcon fallback when AppIndicator3 is not working"""
        print("🔧 Creating StatusIcon fallback")
        
        # Create status icon as fallback
        self.status_icon = Gtk.StatusIcon()
        self.status_icon.set_from_icon_name("preferences-desktop-wallpaper")
        self.status_icon.set_tooltip_text("🪩 Wall-IT - Wallpaper Manager")
        self.status_icon.set_visible(True)
        
        # Create popup menu
        self.menu = Gtk.Menu()
        
        # Show Window item
        show_item = Gtk.MenuItem(label="Show Wall-IT")
        show_item.connect("activate", self._on_show_window)
        self.menu.append(show_item)
        
        # Separator
        sep1 = Gtk.SeparatorMenuItem()
        self.menu.append(sep1)
        
        # Random wallpaper item
        random_item = Gtk.MenuItem(label="🎲 Random Wallpaper")
        random_item.connect("activate", self._on_random_wallpaper)
        self.menu.append(random_item)
        
        # Next wallpaper item
        next_item = Gtk.MenuItem(label="➡️ Next Wallpaper")
        next_item.connect("activate", self._on_next_wallpaper)
        self.menu.append(next_item)
        
        # Separator
        sep2 = Gtk.SeparatorMenuItem()
        self.menu.append(sep2)
        
        # Auto-change toggle
        self.auto_toggle = Gtk.CheckMenuItem(label="⏰ Auto Change")
        self.auto_toggle.set_active(False)
        self.auto_toggle.connect("toggled", self._on_auto_toggle)
        self.menu.append(self.auto_toggle)
        
        # Separator
        sep3 = Gtk.SeparatorMenuItem()
        self.menu.append(sep3)
        
        # Quit item
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        self.menu.append(quit_item)
        
        self.menu.show_all()
        
        # Connect popup menu
        self.status_icon.connect('button-press-event', self._on_status_icon_press)
        
        print("✅ Wall-IT system tray created with StatusIcon fallback")
    
    def _on_status_icon_press(self, status_icon, event):
        """Handle status icon click"""
        if event.button == 3:  # Right-click
            self.menu.popup(None, None, None, None, event.button, event.time)
        elif event.button == 1:  # Left-click
            self._on_show_window(None)
    
    def create_indicator_with_fallback(self):
        """Create indicator with fallback icons to avoid purple/black squares"""
        # Try multiple fallback icons in order of preference
        fallback_icons = [
            "preferences-desktop-wallpaper",  # Standard wallpaper icon
            "applications-graphics",          # Graphics applications icon
            "image-x-generic",               # Generic image icon
            "folder-pictures",               # Pictures folder icon
            "emblem-photos",                 # Photos emblem
            "applications-other",            # Other applications
        ]
        
        for icon_name in fallback_icons:
            try:
                self.indicator = AppIndicator3.Indicator.new(
                    "wall-it",
                    icon_name,
                    AppIndicator3.IndicatorCategory.APPLICATION_STATUS
                )
                self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
                print(f"✅ Using fallback icon: {icon_name}")
                # If we reach here, icon creation was successful
                return
            except Exception as e:
                print(f"⚠️ Fallback icon {icon_name} failed: {e}")
                continue
        
        # If all named icons fail, try to create a simple fallback
        # This might not work in all cases, but we'll try the generic image icon
        try:
            self.indicator = AppIndicator3.Indicator.new(
                "wall-it",
                "image-x-generic",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            print("✅ Using generic fallback icon")
        except:
            # Last resort: create with empty string (may use default)
            self.indicator = AppIndicator3.Indicator.new(
                "wall-it",
                "",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            print("⚠️ Using default system indicator")
        
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("🪩 Wall-IT")  # Disco ball emoji in title
        
        # Create menu
        self.menu = Gtk.Menu()
        
        # Show Window item
        show_item = Gtk.MenuItem(label="Show Wall-IT")
        show_item.connect("activate", self._on_show_window)
        self.menu.append(show_item)
        
        # Separator
        sep1 = Gtk.SeparatorMenuItem()
        self.menu.append(sep1)
        
        # Random wallpaper item
        random_item = Gtk.MenuItem(label="🎲 Random Wallpaper")
        random_item.connect("activate", self._on_random_wallpaper)
        self.menu.append(random_item)
        
        # Next wallpaper item
        next_item = Gtk.MenuItem(label="➡️ Next Wallpaper")
        next_item.connect("activate", self._on_next_wallpaper)
        self.menu.append(next_item)
        
        # Separator
        sep2 = Gtk.SeparatorMenuItem()
        self.menu.append(sep2)
        
        # Auto-change toggle
        self.auto_toggle = Gtk.CheckMenuItem(label="⏰ Auto Change")
        # Initially unchecked - state will be updated by communication
        self.auto_toggle.set_active(False)
        self.auto_toggle.connect("toggled", self._on_auto_toggle)
        self.menu.append(self.auto_toggle)
        
        # Separator
        sep3 = Gtk.SeparatorMenuItem()
        self.menu.append(sep3)
        
        # Quit item
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        self.menu.append(quit_item)
        
        self.menu.show_all()
        self.indicator.set_menu(self.menu)
        
        print("✅ Wall-IT system tray created in separate process")
    
    def _on_show_window(self, item):
        """Show main Wall-IT window"""
        # Send command to show the window
        self._send_ipc_command("show_window")
    
    def _on_random_wallpaper(self, item):
        """Trigger random wallpaper via IPC"""
        self._send_ipc_command("random_wallpaper")
    
    def _on_next_wallpaper(self, item):
        """Trigger next wallpaper via IPC"""
        self._send_ipc_command("next_wallpaper")
    
    def _on_auto_toggle(self, item):
        """Toggle auto-change via IPC"""
        self._send_ipc_command("toggle_auto_change")
    
    def _on_quit(self, item):
        """Send quit command to main application"""
        self._send_ipc_command("quit_app")
        # Give the main app time to quit gracefully, then exit tray
        GLib.timeout_add(1000, self._quit_tray)
    
    def _send_ipc_command(self, command):
        """Send command to main Wall-IT application via a simple file-based IPC"""
        try:
            # Create a temporary file to communicate with the main app
            ipc_dir = Path.home() / ".cache" / "wall-it" / "ipc"
            ipc_dir.mkdir(parents=True, exist_ok=True)
            
            # Write command to a file
            cmd_file = ipc_dir / f"command_{int(time.time())}_{os.getpid()}"
            cmd_file.write_text(command)
            
            print(f"_ipc_command sent: {command}")
        except Exception as e:
            print(f"Error sending IPC command: {e}")
    
    def _quit_tray(self):
        """Quit the tray process"""
        if self.main_loop:
            self.main_loop.quit()
        else:
            # If no main loop running, just exit
            Gtk.main_quit()
    
    def run(self):
        """Run the tray application"""
        self.main_loop = GLib.MainLoop()
        
        # Handle SIGTERM gracefully
        def signal_handler(signum, frame):
            print("Received termination signal, exiting...")
            self._quit_tray()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            print("Interrupted, exiting...")
        finally:
            print("Tray process exited")


def main():
    # Initialize D-Bus main loop
    DBusGMainLoop(set_as_default=True)
    
    tray = WallItTray()
    tray.run()


if __name__ == "__main__":
    main()