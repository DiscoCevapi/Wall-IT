#!/usr/bin/env python3
"""
Alternative test using different GTK widgets
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from pathlib import Path

class AlternativeTestWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Alternative GTK Test")
        self.set_default_size(800, 600)
        
        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        self.set_child(main_box)
        
        # Test with different sized buttons to see if it's ALL widgets
        sizes = [(100, 30), (200, 50), (300, 70), (400, 90)]
        
        for width, height in sizes:
            button = Gtk.Button()
            button.set_label(f"Button {width}x{height}")
            button.set_size_request(width, height)
            main_box.append(button)
            print(f"✅ Created button {width}x{height}")
        
        # Add some colored rectangles using Drawing Area
        for i, color in enumerate(['red', 'blue', 'green', 'yellow']):
            drawing_area = Gtk.DrawingArea()
            size = 100 + (i * 50)  # 100, 150, 200, 250
            drawing_area.set_size_request(size, size)
            drawing_area.set_draw_func(self.draw_rectangle, color)
            main_box.append(drawing_area)
            print(f"✅ Created {color} rectangle {size}x{size}")
    
    def draw_rectangle(self, area, cr, width, height, color):
        """Draw a colored rectangle"""
        if color == 'red':
            cr.set_source_rgb(1.0, 0.0, 0.0)
        elif color == 'blue':
            cr.set_source_rgb(0.0, 0.0, 1.0)
        elif color == 'green':
            cr.set_source_rgb(0.0, 1.0, 0.0)
        else:  # yellow
            cr.set_source_rgb(1.0, 1.0, 0.0)
        
        cr.rectangle(0, 0, width, height)
        cr.fill()

def main():
    app = Gtk.Application()
    
    def on_activate(app):
        window = AlternativeTestWindow(app)
        window.present()
    
    app.connect('activate', on_activate)
    app.run()

if __name__ == "__main__":
    main()
