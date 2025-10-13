#!/usr/bin/env python3
"""
Test Wall-IT action methods directly
"""

import sys
import os

# Add the local bin to path so we can import from wallpaper-gui.py
sys.path.insert(0, os.path.dirname(__file__))

try:
    # Import GTK requirements
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('GdkPixbuf', '2.0')
    gi.require_version('Gdk', '4.0')
    gi.require_version('Gio', '2.0')
    from gi.repository import Gtk, GdkPixbuf, Gdk, Gio, GLib, Pango
    
    # Import our classes
    exec(open('/home/DiscoNiri/.local/bin/wallpaper-gui.py').read())
    
    print("Testing Wall-IT action methods...")
    
    # Create minimal app instance
    app = WallpaperApp()
    app.config = WallpaperConfig()
    app.wallpaper_setter = EnhancedWallpaperSetter(app.config)
    
    # Test if wallpapers directory exists and has wallpapers
    if app.config.wallpaper_dir.exists():
        wallpapers = []
        for file_path in app.config.wallpaper_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in app.config.image_extensions:
                wallpapers.append(file_path)
        print(f"Found {len(wallpapers)} wallpapers in {app.config.wallpaper_dir}")
        
        if wallpapers:
            # Create a minimal grid_view-like object
            class MockGridView:
                def __init__(self, wallpapers):
                    self.wallpapers = wallpapers
            
            app.grid_view = MockGridView(wallpapers)
            
            print("\nTesting action methods:")
            
            try:
                print("1. Testing next_wallpaper()...")
                app.next_wallpaper()
                print("   ✓ next_wallpaper() executed without error")
            except Exception as e:
                print(f"   ✗ next_wallpaper() failed: {e}")
            
            try:
                print("2. Testing previous_wallpaper()...")
                app.previous_wallpaper()
                print("   ✓ previous_wallpaper() executed without error")
            except Exception as e:
                print(f"   ✗ previous_wallpaper() failed: {e}")
            
            try:
                print("3. Testing random_wallpaper()...")
                app.random_wallpaper()
                print("   ✓ random_wallpaper() executed without error")
            except Exception as e:
                print(f"   ✗ random_wallpaper() failed: {e}")
            
            try:
                print("4. Testing present_window() (will fail - no window)...")
                app.present_window()
                print("   ✓ present_window() executed without error")
            except Exception as e:
                print(f"   ✗ present_window() failed (expected): {e}")
        else:
            print("No wallpapers found to test with")
    else:
        print(f"Wallpaper directory doesn't exist: {app.config.wallpaper_dir}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
