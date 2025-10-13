#!/usr/bin/env python3
"""
Simple test to check GTK image scaling
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, GdkPixbuf
from pathlib import Path
import sys

class TestImageWindow(Gtk.ApplicationWindow):
    def __init__(self, app, image_path):
        super().__init__(application=app)
        self.set_title("GTK Image Test")
        self.set_default_size(800, 600)
        
        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        self.set_child(main_box)
        
        # Test different sizes
        sizes = [150, 200, 250, 300]
        
        for size in sizes:
            try:
                # Create pixbuf at specific size
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(image_path), size, size, True)
                
                # Create image widget
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                image.set_size_request(size, size)
                
                # Create frame with label
                frame = Gtk.Frame()
                frame.set_label(f"{size}x{size}px")
                frame.set_child(image)
                
                main_box.append(frame)
                print(f"✅ Created {size}x{size} image - Pixbuf: {pixbuf.get_width()}x{pixbuf.get_height()}")
                
            except Exception as e:
                print(f"❌ Error creating {size}x{size} image: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: test-gtk-image.py <image-path>")
        # Try to find a wallpaper
        wallpaper_dir = Path.home() / "Pictures" / "Wallpapers"
        if wallpaper_dir.exists():
            for ext in ['.jpg', '.png', '.jpeg']:
                test_images = list(wallpaper_dir.glob(f"*{ext}"))
                if test_images:
                    image_path = test_images[0]
                    print(f"Using test image: {image_path}")
                    break
            else:
                print("No test images found in ~/Pictures/Wallpapers/")
                return
        else:
            print("No wallpaper directory found")
            return
    else:
        image_path = Path(sys.argv[1])
        if not image_path.exists():
            print(f"Image not found: {image_path}")
            return

    app = Gtk.Application()
    
    def on_activate(app):
        window = TestImageWindow(app, image_path)
        window.present()
    
    app.connect('activate', on_activate)
    app.run()

if __name__ == "__main__":
    main()
