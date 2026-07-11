#!/usr/bin/env python3
"""
Separate system tray process for Wall-IT to avoid GTK3/GTK4 conflicts
On Wayland (like Niri), this may not show a traditional system tray icon
but will still enable IPC communication for tray functionality.
"""

import os
import sys
import math
import signal
import subprocess
import time
import fcntl
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
try:
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    print("⚠️ python-dbus not available — D-Bus IPC disabled")

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

_singleton_lock_fd = None

def acquire_singleton_lock() -> bool:
    """Ensure only one wall-it-tray.py process is running."""
    global _singleton_lock_fd
    try:
        lock_dir = Path.home() / ".cache" / "wall-it"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_file = lock_dir / "wall-it-tray.lock"
        _singleton_lock_fd = open(lock_file, "w")
        fcntl.flock(_singleton_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _singleton_lock_fd.write(f"{os.getpid()}\n")
        _singleton_lock_fd.flush()
        return True
    except BlockingIOError:
        print("ℹ️ Wall-IT tray is already running. Exiting duplicate instance.")
        return False
    except Exception as e:
        print(f"⚠️ Failed to acquire tray singleton lock: {e}")
        return False

class WallItTray:
    def __init__(self):
        self.indicator = None
        self.main_loop = None

        # Generate/install a real PNG tray icon up front. The tray host (e.g.
        # waybar on wlroots) rasterizes themed *SVG* icons itself and, via
        # AppIndicator3's IconPixmap path, that frequently renders as a mosaic of
        # coloured squares. A proper PNG handed over as an absolute file path is
        # loaded directly by the host and displays correctly.
        self.icon_name = "wall-it"
        self.icon_path = self._ensure_tray_icon()

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

        # AppIndicator3 is available and working — create the full indicator
        self.create_indicator_with_fallback()
    
    def _ensure_tray_icon(self):
        """Generate and install a real PNG tray icon, returning its path.

        With AppIndicator3 + a wlroots tray host (waybar), themed SVG icons get
        rasterized and shipped as IconPixmap bytes that render as coloured
        squares. Installing a PNG and giving the indicator an absolute file path
        (set_icon_full) makes the host load the PNG directly, which displays
        correctly. The PNG is cached and also installed into the hicolor icon
        theme so it resolves by name ('wall-it')."""
        try:
            import cairo
        except Exception as exc:
            print(f"⚠️ cairo not available for tray icon: {exc}")
            return None

        cache_icon = Path.home() / ".cache" / "wall-it" / "icons" / "wall-it.png"
        # Regenerate only when missing or when explicitly requested.
        if cache_icon.exists() and os.environ.get("WALLIT_REGEN_TRAY_ICON") != "1":
            return str(cache_icon)

        sizes = [16, 22, 24, 32, 48, 64, 128, 256]
        try:
            cache_icon.parent.mkdir(parents=True, exist_ok=True)
            # Master icon used directly by the tray via set_icon_full().
            self._draw_disco_ball(cairo, 64).write_to_png(str(cache_icon))
            # Install into the user's hicolor theme so it also resolves by name.
            hicolor = Path.home() / ".local" / "share" / "icons" / "hicolor"
            for s in sizes:
                d = hicolor / f"{s}x{s}" / "apps"
                d.mkdir(parents=True, exist_ok=True)
                self._draw_disco_ball(cairo, s).write_to_png(str(d / "wall-it.png"))
            # Refresh the icon cache (best-effort).
            try:
                subprocess.run(
                    ["gtk-update-icon-cache", "-f", "-t", str(hicolor)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                )
            except Exception:
                pass
            print(f"✅ Generated Wall-IT tray icon -> {cache_icon}")
            return str(cache_icon)
        except Exception as exc:
            print(f"⚠️ Failed to generate tray icon: {exc}")
            return None

    @staticmethod
    def _draw_disco_ball(cairo, size):
        """Draw a disco-ball icon onto a new transparent cairo ImageSurface."""
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        ctx = cairo.Context(surf)
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()

        cx = cy = size / 2.0
        R = size * 0.44

        # Sphere body with radial shading (lit from the upper-left).
        ctx.save()
        ctx.arc(cx, cy, R, 0, 2 * math.pi)
        ctx.clip()
        grad = cairo.RadialGradient(cx - R * 0.4, cy - R * 0.4, R * 0.1, cx, cy, R * 1.05)
        grad.add_color_stop_rgba(0.15, 0.92, 0.95, 1.00, 1.0)
        grad.add_color_stop_rgba(0.55, 0.40, 0.46, 0.92, 1.0)
        grad.add_color_stop_rgba(1.00, 0.08, 0.10, 0.28, 1.0)
        ctx.set_source(grad)
        ctx.rectangle(0, 0, size, size)
        ctx.fill()

        # Mirror tiles: a grid of small squares with a per-tile shimmer.
        n = 7  # tiles across the diameter
        step = (2 * R) / n
        tile = step * 0.82

        def hsh(i, j):
            x = math.sin((i + 1) * 12.9898 + (j + 1) * 78.233) * 43758.5453
            return x - math.floor(x)

        for j in range(n):
            for i in range(n):
                tx = cx - R + (i + 0.5) * step
                ty = cy - R + (j + 0.5) * step
                dx, dy = tx - cx, ty - cy
                if dx * dx + dy * dy > R * R:
                    continue
                lz = max(0.0, 1.0 - math.hypot(dx, dy) / R)
                light = 0.35 + 0.65 * max(0.0, (-dx - dy) / (R * 1.7))
                shimmer = 0.7 + 0.3 * hsh(i, j)
                b = max(0.0, min(1.0, light * shimmer + lz * 0.25))
                r = min(1.0, 0.55 * b + 0.30 * (b * b))
                g = min(1.0, 0.62 * b + 0.34 * (b * b))
                bl = min(1.0, 0.95 * b + 0.30 * (b * b))
                ctx.set_source_rgba(r, g, bl, 0.55 + 0.4 * b)
                ctx.rectangle(tx - tile / 2, ty - tile / 2, tile, tile)
                ctx.fill()
        ctx.restore()

        # Subtle outline so it reads on both light and dark bars.
        ctx.set_source_rgba(0.03, 0.04, 0.10, 0.85)
        ctx.set_line_width(max(1.0, size / 48.0))
        ctx.arc(cx, cy, R, 0, 2 * math.pi)
        ctx.stroke()

        # Specular highlight (upper-left).
        sp, sq, sr = cx - R * 0.38, cy - R * 0.38, R * 0.16
        sgrad = cairo.RadialGradient(sp, sq, 0, sp, sq, sr)
        sgrad.add_color_stop_rgba(0, 1, 1, 1, 0.95)
        sgrad.add_color_stop_rgba(1, 1, 1, 1, 0)
        ctx.set_source(sgrad)
        ctx.arc(sp, sq, sr, 0, 2 * math.pi)
        ctx.fill()

        return surf

    def _create_minimal_wayland_support(self):
        """Create minimal support for Wayland environments where tray icons don't work"""
        print("🔧 Setting up IPC communication for Wayland environment")
        
        # Create a minimal indicator that won't be visible but enables IPC
        try:
            self.indicator = AppIndicator3.Indicator.new(
                "wall-it",
                self.icon_name,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            if self.icon_path:
                self.indicator.set_icon_full(self.icon_path, "Wall-IT")
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
        if self.icon_path:
            self.status_icon.set_from_file(self.icon_path)
        else:
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
            self.icon_name,                   # Our generated PNG (resolves by name)
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
                if self.icon_path:
                    self.indicator.set_icon_full(self.icon_path, "Wall-IT")
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
        if self.icon_path:
            self.indicator.set_icon_full(self.icon_path, "Wall-IT")
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
    if not acquire_singleton_lock():
        return 0
    # Initialize D-Bus main loop if available
    if DBUS_AVAILABLE:
        DBusGMainLoop(set_as_default=True)

    tray = WallItTray()
    tray.run()


if __name__ == "__main__":
    main()