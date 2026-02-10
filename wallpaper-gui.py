#!/usr/bin/env python3
"""
Wall-IT
Professional wallpaper manager with system tray, monitor scaling, timer, drag&drop, photo effects, and matugen integration
"""

import os
import sys
import threading
import subprocess
import hashlib
import random
import shutil
import json
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import importlib.util

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')

from gi.repository import Gtk, GdkPixbuf, Gdk, Gio, GLib, Pango
import cairo

# Wall-IT Version
__version__ = "2.1.0"

# System tray support - Using separate process to avoid GTK3/GTK4 conflicts
import subprocess
import threading
import time
from pathlib import Path

TRAY_AVAILABLE = True  # Now available via separate process
tray_process = None
print("ℹ️ System tray available via separate process")

# Import image processing libraries for effects
try:
    from PIL import Image, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
    print("✅ PIL/Pillow available - Photo effects enabled")
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL/Pillow not available - Install with: paru -S python-pillow")

class EnhancedFolderBrowser(Gtk.Window):
    """Enhanced folder browser with thumbnail grid and individual file selection"""
    
    def __init__(self, parent, config):
        super().__init__()
        self.parent = parent
        self.config = config
        self.selected_files = set()
        self.current_folder = Path.home()
        self.thumbnail_cache = {}  # Cache thumbnails to avoid regenerating
        
        self.set_title("🖼️ Select Wallpapers from Folder")
        self.set_default_size(1000, 700)
        self.set_transient_for(parent)
        self.set_modal(True)
        
        self.setup_ui()
        self.load_current_folder()
    
    def setup_ui(self):
        """Setup the dialog UI"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        self.set_child(main_box)
        
        # Header with folder navigation
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        up_btn = Gtk.Button.new_from_icon_name("go-up-symbolic")
        up_btn.set_tooltip_text("Go to parent folder")
        up_btn.connect('clicked', self.on_up_clicked)
        
        home_btn = Gtk.Button.new_from_icon_name("go-home-symbolic")
        home_btn.set_tooltip_text("Go to home folder")
        home_btn.connect('clicked', self.on_home_clicked)
        
        self.path_label = Gtk.Label()
        self.path_label.set_halign(Gtk.Align.START)
        self.path_label.set_hexpand(True)
        self.path_label.set_ellipsize(Pango.EllipsizeMode.START)
        
        header_box.append(up_btn)
        header_box.append(home_btn)
        header_box.append(self.path_label)
        
        main_box.append(header_box)
        
        # Create thumbnail grid
        self.setup_thumbnail_grid(main_box)
        
        # Selection controls
        selection_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        select_all_btn = Gtk.Button(label="✅ Select All")
        select_all_btn.connect('clicked', self.on_select_all)
        
        select_none_btn = Gtk.Button(label="❌ Select None")
        select_none_btn.connect('clicked', self.on_select_none)
        
        self.selection_label = Gtk.Label()
        self.update_selection_label()
        
        selection_box.append(select_all_btn)
        selection_box.append(select_none_btn)
        selection_box.append(Gtk.Box())  # Spacer
        selection_box.append(self.selection_label)
        
        main_box.append(selection_box)
        
        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect('clicked', self.on_cancel)
        
        import_btn = Gtk.Button(label="📥 Import Selected")
        import_btn.add_css_class("suggested-action")
        import_btn.connect('clicked', self.on_import)
        
        button_box.append(cancel_btn)
        button_box.append(import_btn)
        
        main_box.append(button_box)
    
    def setup_thumbnail_grid(self, parent_box):
        """Setup scrollable thumbnail grid"""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        # Use FlowBox for responsive grid layout - match main wall-it grid
        self.flow_box = Gtk.FlowBox()
        self.flow_box.set_valign(Gtk.Align.START)
        self.flow_box.set_max_children_per_line(5)  # Good balance for 150px thumbnails
        self.flow_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow_box.set_column_spacing(12)
        self.flow_box.set_row_spacing(12)
        
        scrolled.set_child(self.flow_box)
        parent_box.append(scrolled)
    
    def load_current_folder(self):
        """Load contents of current folder"""
        self.path_label.set_text(f"📁 {self.current_folder}")
        
        # Clear existing items
        child = self.flow_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.flow_box.remove(child)
            child = next_child
        
        self.selected_files.clear()
        self.thumbnail_cache.clear()  # Clear cache to regenerate thumbnails with new size
        self.update_selection_label()
        
        try:
            # Get folders and image files
            folders = []
            images = []
            
            for item in self.current_folder.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    folders.append(item)
                elif item.is_file() and item.suffix.lower() in self.config.image_extensions:
                    images.append(item)
            
            # Sort items
            folders.sort(key=lambda x: x.name.lower())
            images.sort(key=lambda x: x.name.lower())
            
            # Add folders first
            for folder in folders:
                self.add_folder_item(folder)
            
            # Add image thumbnails with progress feedback
            total_images = len(images)
            if total_images > 0:
                # Show progress for many images
                for i, image in enumerate(images):
                    self.add_image_item(image)
                    
                    # Update progress every 10 images or at the end
                    if (i + 1) % 10 == 0 or i == total_images - 1:
                        # Force GUI update to show thumbnails as they load
                        # In GTK4, we use GLib.MainContext instead of Gtk.main_iteration_do
                        context = GLib.MainContext.default()
                        while context.pending():
                            context.iteration(False)
        
        except PermissionError:
            # Add permission denied message
            error_widget = Gtk.Label(label="❌ Permission denied")
            error_widget.add_css_class("error")
            self.flow_box.append(error_widget)
        except Exception as e:
            print(f"Error loading folder {self.current_folder}: {e}")
    
    def add_folder_item(self, folder_path):
        """Add folder item to grid"""
        folder_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        folder_box.set_size_request(150, 180)
        
        # Folder icon
        icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        icon.set_icon_size(Gtk.IconSize.LARGE)
        
        # Folder name
        name_label = Gtk.Label(label=folder_path.name)
        name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        name_label.set_max_width_chars(12)
        
        folder_box.append(icon)
        folder_box.append(name_label)
        
        # Make clickable
        gesture = Gtk.GestureClick()
        gesture.connect('released', lambda g, n, x, y, path=folder_path: self.enter_folder(path))
        folder_box.add_controller(gesture)
        
        self.flow_box.append(folder_box)
    
    def add_image_item(self, image_path):
        """Add image item with thumbnail and checkbox to grid"""
        item_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        item_box.set_size_request(150, 200)
        
        # Checkbox overlay container
        overlay = Gtk.Overlay()
        
        # Thumbnail without frame to avoid white bars
        thumbnail = self.create_thumbnail(image_path)
        overlay.set_child(thumbnail)
        
        # Checkbox in top-right corner
        checkbox = Gtk.CheckButton()
        checkbox.set_halign(Gtk.Align.END)
        checkbox.set_valign(Gtk.Align.START)
        checkbox.set_margin_top(4)
        checkbox.set_margin_end(4)
        checkbox.connect('toggled', lambda cb, path=image_path: self.on_image_toggled(cb, path))
        
        overlay.add_overlay(checkbox)
        
        # Image name
        name_label = Gtk.Label(label=image_path.name)
        name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        name_label.set_max_width_chars(16)  # Match main grid sizing
        name_label.add_css_class("caption")
        
        item_box.append(overlay)
        item_box.append(name_label)
        
        # Store checkbox reference
        item_box.checkbox = checkbox
        item_box.image_path = image_path
        
        self.flow_box.append(item_box)
    
    def create_thumbnail(self, image_path):
        """Create thumbnail for image using PIL and GTK4"""
        try:
            # Check cache first
            cache_key = str(image_path)
            if cache_key in self.thumbnail_cache:
                cached_pixbuf = self.thumbnail_cache[cache_key]
                thumbnail_widget = Gtk.DrawingArea()
                thumbnail_widget.set_size_request(150, 150)
                thumbnail_widget.set_draw_func(self.draw_thumbnail, cached_pixbuf)
                # Store pixbuf reference to prevent garbage collection
                thumbnail_widget._pixbuf = cached_pixbuf
                return thumbnail_widget
            
            if not PIL_AVAILABLE:
                # Fallback to generic icon if PIL not available
                icon = Gtk.Image.new_from_icon_name("image-x-generic-symbolic")
                icon.set_icon_size(Gtk.IconSize.LARGE)
                icon.set_size_request(150, 150)
                return icon
            
            # Fast path: use GdkPixbuf to load and scale directly (handles PNG/JPEG/WebP with alpha)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(image_path), 150, 150, True)

            # Cache the pixbuf for future use
            self.thumbnail_cache[cache_key] = pixbuf

            # Create DrawingArea for better size control (like main grid)
            thumbnail_widget = Gtk.DrawingArea()
            thumbnail_widget.set_size_request(150, 150)
            thumbnail_widget.set_draw_func(self.draw_thumbnail, pixbuf)
            # Store pixbuf reference to prevent garbage collection
            thumbnail_widget._pixbuf = pixbuf
            return thumbnail_widget
                
        except Exception as e:
            print(f"Error creating thumbnail for {image_path}: {e}")
            # Fallback to generic image icon
            icon = Gtk.Image.new_from_icon_name("image-x-generic-symbolic")
            icon.set_icon_size(Gtk.IconSize.LARGE)
            icon.set_size_request(150, 150)
            return icon
    
    def draw_thumbnail(self, area, cr, width, height, pixbuf):
        """Draw pixbuf properly scaled and centered (same as main grid)"""
        if pixbuf:
            # Get pixbuf dimensions
            pb_width = pixbuf.get_width()
            pb_height = pixbuf.get_height()
            
            # Calculate scale to fit pixbuf in the drawing area
            scale_x = width / pb_width
            scale_y = height / pb_height
            scale = min(scale_x, scale_y)  # Maintain aspect ratio
            
            # Calculate position to center the image
            scaled_width = pb_width * scale
            scaled_height = pb_height * scale
            x_offset = (width - scaled_width) / 2
            y_offset = (height - scaled_height) / 2
            
            # Apply transformations and draw
            cr.save()
            cr.translate(x_offset, y_offset)
            cr.scale(scale, scale)
            
            # Use newer surface-based approach instead of deprecated cairo_set_source_pixbuf
            try:
                surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, 1, None)
                cr.set_source_surface(surface, 0, 0)
            except:
                # Fallback to deprecated method if new one fails
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
            
            cr.paint()
            cr.restore()
    
    def enter_folder(self, folder_path):
        """Enter selected folder"""
        self.current_folder = folder_path
        self.load_current_folder()
    
    def on_up_clicked(self, button):
        """Go to parent folder"""
        if self.current_folder.parent != self.current_folder:
            self.current_folder = self.current_folder.parent
            self.load_current_folder()
    
    def on_home_clicked(self, button):
        """Go to home folder"""
        self.current_folder = Path.home()
        self.load_current_folder()
    
    def on_image_toggled(self, checkbox, image_path):
        """Handle image checkbox toggle"""
        if checkbox.get_active():
            self.selected_files.add(image_path)
        else:
            self.selected_files.discard(image_path)
        
        self.update_selection_label()
    
    def on_select_all(self, button):
        """Select all images in current folder"""
        child = self.flow_box.get_first_child()
        while child:
            if hasattr(child, 'checkbox'):
                child.checkbox.set_active(True)
            child = child.get_next_sibling()
    
    def on_select_none(self, button):
        """Deselect all images"""
        child = self.flow_box.get_first_child()
        while child:
            if hasattr(child, 'checkbox'):
                child.checkbox.set_active(False)
            child = child.get_next_sibling()
    
    def update_selection_label(self):
        """Update selection count label"""
        count = len(self.selected_files)
        self.selection_label.set_text(f"📋 {count} image{'s' if count != 1 else ''} selected")
    
    def on_cancel(self, button):
        """Cancel dialog"""
        self.destroy()
    
    def on_import(self, button):
        """Import selected files"""
        if not self.selected_files:
            return
        
        # Convert Path objects to Gio.File objects for compatibility
        gio_files = []
        for file_path in self.selected_files:
            gio_files.append(Gio.File.new_for_path(str(file_path)))
        
        # Use existing copy method
        self.parent.copy_selected_files(gio_files)
        self.destroy()

class WeatherSync:
    """Weather-based wallpaper selection similar to Asteroid app"""
    
    # Realistic weather condition mappings based on actual weather
    WEATHER_MAPPINGS = {
        'clear-day': ['sunny', 'bright', 'clear', 'blue sky', 'sunshine'],
        'clear-night': ['night', 'dark', 'stars', 'moon', 'nighttime'],
        'rain': ['rain', 'rainy', 'storm', 'drops', 'wet'],
        'snow': ['snow', 'winter', 'snowy', 'white', 'cold'],
        'sleet': ['sleet', 'ice', 'winter', 'cold'],
        'wind': ['wind', 'windy', 'trees', 'movement'],
        'fog': ['fog', 'mist', 'misty', 'cloudy', 'gray'],
        'cloudy': ['cloudy', 'overcast', 'gray', 'clouds'],
        'partly-cloudy-day': ['clouds', 'partly cloudy', 'scattered'],
        'partly-cloudy-night': ['night', 'clouds', 'moon', 'dark']
    }

    # Time-based mappings
    TIME_MAPPINGS = {
        'dawn': ['dawn', 'sunrise', 'morning', 'golden', 'orange'],
        'morning': ['morning', 'bright', 'fresh', 'green'],
        'noon': ['noon', 'bright', 'sunny', 'clear'],
        'afternoon': ['afternoon', 'warm', 'golden'],
        'sunset_transition': ['sunset', 'orange', 'red', 'golden', 'dusk', 'evening'],
        'sunset': ['sunset', 'orange', 'red', 'golden', 'dusk'],
        'night': ['night', 'dark', 'moon', 'stars', 'city lights']
    }
    
    def __init__(self):
        self.api_key = None
        self.location = None
        self.current_weather = None
        self.current_time_period = self.get_current_time_period()
        
    def get_current_time_period(self):
        """Get current time period for wallpaper selection"""
        import datetime
        current_time = datetime.datetime.now()
        hour = current_time.hour
        
        if 5 <= hour < 7:
            return 'dawn'
        elif 7 <= hour < 11:
            return 'morning'
        elif 11 <= hour < 14:
            return 'noon'
        elif 14 <= hour < 16:  # Earlier afternoon
            return 'afternoon'
        elif 16 <= hour < 18:  # Later afternoon/sunset transition
            return 'sunset_transition'  # New time period for sunset-like effects
        elif 18 <= hour < 20:
            return 'sunset'
        else:
            return 'night'
    
    def get_weather_description(self):
        """Get current weather and time description"""
        time_period = self.get_current_time_period()

        # Simulate realistic weather conditions based on time of day
        # In a real implementation, this would come from a weather API
        import random
        
        # For demo purposes, simulate different weather conditions
        weather_conditions = [
            'clear-day', 'clear-night', 'partly-cloudy-day', 'cloudy', 
            'rain', 'fog', 'sunny'
        ]
        
        # Determine likely weather based on time of day
        if time_period in ['night', 'dawn', 'morning', 'noon', 'afternoon', 'sunset', 'sunset_transition']:
            # Common weather conditions for daytime
            simulated_weather = random.choices(
                ['clear-day', 'partly-cloudy-day', 'cloudy', 'sunny'],
                weights=[60, 20, 15, 5],  # Clear days are most common
                k=1
            )[0]
        else:
            simulated_weather = 'clear-night'

        # For sunset/sunset_transition times, make it more likely to have colorful skies
        if time_period in ['sunset', 'sunset_transition']:
            # Increase chance of colorful sunset conditions
            simulated_weather = random.choices(
                ['clear-day', 'partly-cloudy-day', 'cloudy'],
                weights=[30, 40, 30],  # Clouds at sunset create beautiful effects
                k=1
            )[0]

        # Return appropriate description based on time period
        if time_period == 'night':
            return {
                'condition': 'clear-night',
                'description': '🌙 Clear Night',
                'time_period': 'night',
                'emoji': '🌙',
                'recommended_keywords': ['night', 'dark', 'moon', 'stars', 'city lights', 'nighttime']
            }
        elif time_period == 'dawn':
            return {
                'condition': simulated_weather,
                'description': '🌅 Dawn',
                'time_period': 'dawn',
                'emoji': '🌅',
                'recommended_keywords': ['dawn', 'sunrise', 'morning', 'golden', 'orange']
            }
        elif time_period == 'morning':
            return {
                'condition': simulated_weather,
                'description': '🌤️ Morning',
                'time_period': 'morning',
                'emoji': '🌤️',
                'recommended_keywords': ['morning', 'bright', 'fresh', 'green']
            }
        elif time_period == 'noon':
            return {
                'condition': simulated_weather,
                'description': '☀️ Midday',
                'time_period': 'noon',
                'emoji': '☀️',
                'recommended_keywords': ['noon', 'bright', 'sunny', 'clear']
            }
        elif time_period == 'afternoon':
            return {
                'condition': simulated_weather,
                'description': '⛅ Afternoon',
                'time_period': 'afternoon',
                'emoji': '⛅',
                'recommended_keywords': ['afternoon', 'warm', 'partly cloudy']
            }
        elif time_period == 'sunset_transition':
            return {
                'condition': simulated_weather,
                'description': '🌆 Sunset Approaching',
                'time_period': 'sunset_transition',
                'emoji': '🌆',
                'recommended_keywords': ['sunset', 'orange', 'red', 'golden', 'dusk', 'evening']
            }
        elif time_period == 'sunset':
            return {
                'condition': simulated_weather,
                'description': '🌇 Sunset',
                'time_period': 'sunset',
                'emoji': '🌇',
                'recommended_keywords': ['sunset', 'orange', 'red', 'golden', 'dusk']
            }
        else:
            return {
                'condition': simulated_weather,
                'description': '🌤️ Day',
                'time_period': 'day',
                'emoji': '🌤️',
                'recommended_keywords': ['day', 'bright', 'clear']
            }
    
    def find_matching_wallpapers(self, wallpapers):
        """Find wallpapers that match current weather/time conditions"""
        weather_info = self.get_weather_description()
        keywords = weather_info['recommended_keywords']
        
        matching_wallpapers = []
        
        for wallpaper in wallpapers:
            filename_lower = wallpaper.name.lower()
            
            # Check if any keywords match the filename
            for keyword in keywords:
                if keyword in filename_lower:
                    matching_wallpapers.append(wallpaper)
                    break
        
        # If no specific matches, return all wallpapers
        return matching_wallpapers if matching_wallpapers else wallpapers
    
    def get_recommended_wallpaper(self, wallpapers):
        """Get a recommended wallpaper based on current conditions"""
        matching = self.find_matching_wallpapers(wallpapers)
        if matching:
            import random
            return random.choice(matching)
        return None

class WeatherAnimationOverlay:
    """Animated weather effects overlay (inspired by Asteroid app)"""
    
    def __init__(self, weather_sync):
        self.weather_sync = weather_sync
        self.animation_enabled = True
        self.overlay_process = None
        
    def create_weather_animation_script(self, weather_condition, wallpaper_path):
        """Create a script that generates animated weather overlay using Cairo/GTK"""
        script_content = f'''#!/usr/bin/env python3
# Animated Weather Overlay Script (Asteroid-inspired)
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Gio
import cairo
import math
import random
import time

class WeatherOverlay(Gtk.ApplicationWindow):
    def __init__(self, app, wallpaper_path, weather_condition):
        super().__init__(application=app)
        self.wallpaper_path = wallpaper_path
        self.weather_condition = "{weather_condition}"
        self.particles = []
        self.animation_time = 0
        
        # Make window fullscreen and transparent
        self.set_default_size(1920, 1080)
        self.set_decorated(False)
        self.fullscreen()
        
        # Create drawing area
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_draw_func(self.draw_weather_overlay)
        self.set_child(self.drawing_area)
        
        # Initialize particles based on weather condition
        self.init_particles()
        
        # Start animation timer
        GLib.timeout_add(33, self.update_animation)  # ~30 FPS
        
    def init_particles(self):
        """Initialize particles based on weather condition"""
        if self.weather_condition == "rain":
            # Rain drops
            for _ in range(150):
                self.particles.append({{
                    'x': random.uniform(0, 1920),
                    'y': random.uniform(-200, 1080),
                    'speed': random.uniform(8, 15),
                    'length': random.uniform(10, 25)
                }})
        elif self.weather_condition == "snow":
            # Snow flakes
            for _ in range(80):
                self.particles.append({{
                    'x': random.uniform(0, 1920),
                    'y': random.uniform(-200, 1080),
                    'speed': random.uniform(1, 4),
                    'size': random.uniform(3, 8),
                    'rotation': random.uniform(0, 360)
                }})
        elif self.weather_condition == "night":
            # Stars twinkling
            for _ in range(40):
                self.particles.append({{
                    'x': random.uniform(0, 1920),
                    'y': random.uniform(0, 400),  # Upper portion of screen
                    'brightness': random.uniform(0.3, 1.0),
                    'twinkle_speed': random.uniform(0.02, 0.1)
                }})
                
    def draw_weather_overlay(self, area, cr, width, height):
        """Draw animated weather overlay"""
        # Clear background (transparent)
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        
        if self.weather_condition == "rain":
            self.draw_rain(cr)
        elif self.weather_condition == "snow":
            self.draw_snow(cr)
        elif self.weather_condition == "night":
            self.draw_stars(cr)
        elif self.weather_condition == "clouds":
            self.draw_clouds(cr)
            
    def draw_rain(self, cr):
        """Draw animated rain drops"""
        cr.set_source_rgba(0.7, 0.8, 1.0, 0.6)  # Light blue rain
        cr.set_line_width(2)
        
        for particle in self.particles:
            cr.move_to(particle['x'], particle['y'])
            cr.line_to(particle['x'] + 3, particle['y'] + particle['length'])
            cr.stroke()
            
    def draw_snow(self, cr):
        """Draw animated snow flakes"""
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.8)  # White snow
        
        for particle in self.particles:
            # Draw snowflake as a small circle
            cr.arc(particle['x'], particle['y'], particle['size'], 0, 2 * math.pi)
            cr.fill()
            
    def draw_stars(self, cr):
        """Draw twinkling stars for night mode"""
        for particle in self.particles:
            # Twinkling effect
            brightness = particle['brightness'] * (0.5 + 0.5 * math.sin(self.animation_time * particle['twinkle_speed']))
            cr.set_source_rgba(1.0, 1.0, 0.9, brightness)  # Warm white stars
            
            # Draw star as small diamond
            size = 2
            cr.move_to(particle['x'], particle['y'] - size)
            cr.line_to(particle['x'] + size, particle['y'])
            cr.line_to(particle['x'], particle['y'] + size)
            cr.line_to(particle['x'] - size, particle['y'])
            cr.close_path()
            cr.fill()
            
    def draw_clouds(self, cr):
        """Draw moving clouds"""
        # Simple cloud shapes that move across screen
        cloud_alpha = 0.3
        cr.set_source_rgba(0.9, 0.9, 0.9, cloud_alpha)
        
        # Draw a few cloud shapes
        cloud_offset = (self.animation_time * 0.5) % 2000
        for i in range(3):
            x = (i * 600 + cloud_offset) % 2000 - 200
            y = 100 + i * 50
            
            # Draw cloud as overlapping circles
            for j in range(5):
                cr.arc(x + j * 30, y + random.uniform(-10, 10), 25, 0, 2 * math.pi)
                cr.fill()
            
    def update_animation(self):
        """Update particle positions and redraw"""
        self.animation_time += 1
        
        for particle in self.particles:
            if self.weather_condition == "rain":
                particle['y'] += particle['speed']
                if particle['y'] > 1200:
                    particle['y'] = random.uniform(-100, -50)
                    particle['x'] = random.uniform(0, 1920)
                    
            elif self.weather_condition == "snow":
                particle['y'] += particle['speed']
                particle['x'] += random.uniform(-1, 1)  # Drift effect
                if particle['y'] > 1200:
                    particle['y'] = random.uniform(-100, -50)
                    particle['x'] = random.uniform(0, 1920)
        
        # Redraw
        self.drawing_area.queue_draw()
        return True  # Continue animation
        
    def on_key_press(self, controller, keyval, keycode, state):
        """Handle key press to exit overlay"""
        if keyval == Gdk.KEY_Escape or keyval == Gdk.KEY_q:
            self.get_application().quit()
            
class WeatherOverlayApp(Gtk.Application):
    def __init__(self, wallpaper_path, weather_condition):
        super().__init__()
        self.wallpaper_path = wallpaper_path
        self.weather_condition = weather_condition
        
    def do_activate(self):
        window = WeatherOverlay(self, self.wallpaper_path, self.weather_condition)
        window.present()
        
        # Add key controller for escape
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', window.on_key_press)
        window.add_controller(key_controller)

if __name__ == "__main__":
    import sys
    wallpaper_path = sys.argv[1] if len(sys.argv) > 1 else ""
    weather_condition = sys.argv[2] if len(sys.argv) > 2 else "rain"
    
    app = WeatherOverlayApp(wallpaper_path, weather_condition)
    app.run()
'''
        return script_content
    
    def show_weather_overlay(self, main_window, duration=10):
        """Show animated weather overlay optimized for desktop environment"""
        print(f"🎬 show_weather_overlay called with main_window={main_window is not None}, duration={duration}")
        
        if not self.animation_enabled:
            print("🎬 Weather animations are disabled, returning early")
            return

        weather_info = self.weather_sync.get_weather_description()
        condition = weather_info['time_period']
        actual_condition = weather_info['condition']  # Get the actual weather condition
        print(f"🎬 Weather time period detected: {condition}")
        print(f"🎬 Actual weather condition: {actual_condition}")
        print(f"🎬 Full weather info: {weather_info}")

        # Map actual weather conditions to animation types (higher priority)
        # Then fall back to time-based animations
        weather_animation_map = {
            'rain': 'rain',           # Rain drops
            'snow': 'snow',           # Snow flakes
            'sleet': 'snow',          # Sleet treated as snow
            'fog': 'fog',             # Fog/mist
            'wind': 'wind',           # Wind effects
            'cloudy': 'clouds',       # Moving clouds
            'partly-cloudy-day': 'partly_cloudy',  # Partial clouds with sun
            'partly-cloudy-night': 'partly_cloudy_night',  # Partial clouds at night
            'clear-night': 'night',   # Night stars
            'clear-day': 'sunny',     # Sunny day with sun rays
        }

        # Time-based animations as fallback
        time_animation_map = {
            'night': 'night',         # Twinkling stars
            'sunset': 'sunset',       # Sunset colors/effects
            'dawn': 'dawn',           # Dawn colors
            'noon': 'sunny',          # Sunny day with sun rays
            'morning': 'sunny',       # Morning sun rays
            'afternoon': 'partly_cloudy', # Afternoon with possible clouds
        }

        # First try to use actual weather condition, then time period
        if actual_condition in weather_animation_map:
            animation_type = weather_animation_map[actual_condition]
            print(f"🎬 Using actual weather condition animation: {animation_type}")
        elif condition in time_animation_map:
            animation_type = time_animation_map[condition]
            print(f"🎬 Using time-based animation: {animation_type}")
        else:
            animation_type = 'day'  # Default
            print(f"🎬 Using default animation: {animation_type}")

        print(f"🎬 Final mapped animation type: {animation_type}")

        # Detect desktop environment for optimal overlay behavior
        import os
        desktop_env = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        print(f"🎬 Desktop environment detected: {desktop_env}")

        # Also check if running under Wayland
        wayland_display = os.environ.get('WAYLAND_DISPLAY')
        is_wayland = bool(wayland_display)
        print(f"🎬 Running under Wayland: {is_wayland}")

        if desktop_env == 'kde':
            print("🎬 Using KDE desktop overlay method")
            self._show_kde_desktop_overlay(main_window, animation_type, duration)
        elif is_wayland:
            print("🎬 Using Wayland-compatible overlay method")
            # Check if specifically running under niri
            if desktop_env == 'niri':
                print("🎬 Detected niri compositor, using niri-specific overlay method")
                self._show_niri_overlay(main_window, animation_type, duration)
            else:
                self._show_standard_overlay(main_window, animation_type, duration)
        else:
            print(f"🎬 Using standard overlay method for environment: {desktop_env}")
            self._show_standard_overlay(main_window, animation_type, duration)
    
    def _show_kde_desktop_overlay(self, main_window, animation_type, duration):
        """Create KDE-optimized desktop overlay window"""
        try:
            from gi.repository import Gtk, GLib, Gdk
            import cairo, math, random
            
            # Create overlay window optimized for KDE
            overlay_window = Gtk.Window()
            
            # KDE-specific window properties for desktop overlay
            overlay_window.set_decorated(False)
            overlay_window.set_resizable(False)
            overlay_window.set_modal(False)
            overlay_window.set_deletable(False)
            
            # Don't make it transient - we want it as desktop overlay
            # overlay_window.set_transient_for(main_window)  # Commented out for KDE
            
            # Make window span all monitors
            overlay_window.fullscreen()
            
            # Set up GTK4 transparency
            try:
                css_provider = Gtk.CssProvider()
                css_provider.load_from_data(b"""
                window {
                    background: rgba(0, 0, 0, 0);
                    background-color: transparent;
                }
                """)
                
                display = Gdk.Display.get_default()
                Gtk.StyleContext.add_provider_for_display(
                    display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                print("✅ KDE overlay transparency setup complete")
            except Exception as e:
                print(f"Warning: CSS transparency setup failed: {e}")
            
            # Create drawing area with transparent background
            drawing_area = Gtk.DrawingArea()
            drawing_area.set_draw_func(self._draw_kde_overlay_animation)
            overlay_window.set_child(drawing_area)
            
            # Store animation data
            overlay_window.animation_type = animation_type
            overlay_window.particles = self._init_overlay_particles(animation_type)
            overlay_window.animation_time = 0
            
            # Connect key press to close (Escape key)
            key_controller = Gtk.EventControllerKey()
            key_controller.connect('key-pressed', lambda c, k, kc, s: self._close_overlay(overlay_window) if k == Gdk.KEY_Escape else False)
            overlay_window.add_controller(key_controller)
            
            # Set window title for wmctrl targeting
            overlay_window.set_title("Wall_IT_Weather_Overlay")
            
            # Show overlay
            overlay_window.present()
            
            # Force window to desktop layer after brief delay
            GLib.timeout_add(500, lambda: self._ensure_kde_desktop_layer(overlay_window))
            
            # Start animation timer
            def update_overlay():
                if not overlay_window.get_mapped():
                    return False
                overlay_window.animation_time += 1
                self._update_overlay_particles(overlay_window.particles, animation_type)
                drawing_area.queue_draw()
                return True
            
            timer_id = GLib.timeout_add(33, update_overlay)  # ~30 FPS
            
            # Store timer ID for cleanup
            overlay_window._timer_id = timer_id
            
            # Auto-close after duration
            def close_overlay():
                self._close_overlay(overlay_window)
                return False
            
            GLib.timeout_add_seconds(duration, close_overlay)
            
            print(f"KDE Desktop overlay created for {animation_type} animation")
            
        except Exception as e:
            print(f"Error creating KDE weather overlay: {e}")
            # Fallback to standard overlay
            self._show_standard_overlay(main_window, animation_type, duration)
    
    def _show_standard_overlay(self, main_window, animation_type, duration):
        """Create standard overlay window for non-KDE environments"""
        try:
            from gi.repository import Gtk, GLib, Gdk
            import cairo, math, random

            print(f"🎬 _show_standard_overlay: Creating overlay for animation type: {animation_type}")
            print(f"🎬 _show_standard_overlay: Duration: {duration}")
            print(f"🎬 _show_standard_overlay: Main window provided: {main_window is not None}")

            # Create overlay window with Wayland/Niri compatibility
            overlay_window = Gtk.Window()
            print(f"🎬 _show_standard_overlay: Created overlay window object")

            overlay_window.set_modal(False)
            overlay_window.set_decorated(False)
            overlay_window.set_resizable(False)

            # Get screen dimensions for proper fullscreen
            try:
                display = Gdk.Display.get_default()
                if display:
                    print(f"🎬 _show_standard_overlay: Got display object")
                    # Get monitor geometry for proper sizing
                    monitor = display.get_primary_monitor()
                    if monitor:
                        print(f"🎬 _show_standard_overlay: Got primary monitor")
                        geometry = monitor.get_geometry()
                        print(f"🎬 _show_standard_overlay: Monitor geometry - Width: {geometry.width}, Height: {geometry.height}")
                        overlay_window.set_default_size(geometry.width, geometry.height)

                        # For Wayland/Niri, try different approaches
                        # Try to set the window as a popup or override-redirect
                        try:
                            # Use Gdk.WindowTypeHint.DIALOG which might work better with Niri
                            overlay_window.set_type_hint(Gdk.WindowTypeHint.DIALOG)
                            print(f"🎬 _show_standard_overlay: Set window type hint to DIALOG")
                        except Exception as hint_error:
                            print(f"🎬 _show_standard_overlay: Error setting window type hint: {hint_error}")
                            try:
                                # Fallback to UTILITY which might work better for overlays
                                overlay_window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
                                print(f"🎬 _show_standard_overlay: Set window type hint to UTILITY")
                            except Exception as utility_error:
                                print(f"🎬 _show_standard_overlay: Error setting utility type hint: {utility_error}")
                                pass
                    else:
                        print(f"🎬 _show_standard_overlay: No primary monitor found, using fallback")
                        # Fallback to common resolution
                        overlay_window.set_default_size(1920, 1080)
                else:
                    print(f"🎬 _show_standard_overlay: No display object, using fallback resolution")
                    overlay_window.set_default_size(1920, 1080)
            except Exception as display_error:
                print(f"🎬 _show_standard_overlay: Error getting display info: {display_error}")
                # Fallback to common resolution
                overlay_window.set_default_size(1920, 1080)

            # Make window stay on top and be visible
            try:
                overlay_window.set_keep_above(True)
                print(f"🎬 _show_standard_overlay: Set window to stay above")
            except Exception as keep_above_error:
                print(f"🎬 _show_standard_overlay: Error setting keep_above: {keep_above_error}")

            overlay_window.set_accept_focus(False)  # Don't steal focus in Wayland
            print(f"🎬 _show_standard_overlay: Set window to not accept focus")

            # For Wayland/Niri, try to set opacity and visual properties
            try:
                overlay_window.set_opacity(0.95)  # Nearly opaque but not fully to ensure visibility
                print(f"🎬 _show_standard_overlay: Set window opacity to 0.95")
            except Exception as opacity_error:
                print(f"🎬 _show_standard_overlay: Error setting opacity: {opacity_error}")
                pass

            # Create drawing area
            drawing_area = Gtk.DrawingArea()
            drawing_area.set_hexpand(True)
            drawing_area.set_vexpand(True)
            # Set drawing area size to match window
            drawing_area.set_size_request(overlay_window.get_default_width(), overlay_window.get_default_height())
            drawing_area.set_draw_func(self._draw_overlay_animation)
            overlay_window.set_child(drawing_area)
            print(f"🎬 _show_standard_overlay: Created and configured drawing area")

            # Store animation data
            overlay_window.animation_type = animation_type
            overlay_window.particles = self._init_overlay_particles(animation_type)
            overlay_window.animation_time = 0
            print(f"🎬 _show_standard_overlay: Initialized animation data - Particles: {len(overlay_window.particles)}")

            # Connect key press to close
            key_controller = Gtk.EventControllerKey()
            key_controller.connect('key-pressed', lambda c, k, kc, s: overlay_window.destroy() if k == Gdk.KEY_Escape else False)
            overlay_window.add_controller(key_controller)
            print(f"🎬 _show_standard_overlay: Connected key controller for ESC key")

            # For Niri Wayland, we need to handle window presentation differently
            # Show overlay - try different approaches for Wayland/Niri
            # First try present, then show, then realize
            print(f"🎬 _show_standard_overlay: Attempting to present overlay window...")
            
            # For Wayland/Niri, we need to ensure the window is properly mapped
            def show_overlay():
                try:
                    overlay_window.present()
                    print(f"🎬 _show_standard_overlay: Called overlay_window.present()")
                    
                    overlay_window.show()
                    print(f"🎬 _show_standard_overlay: Called overlay_window.show()")
                    
                    # Force realization
                    overlay_window.realize()
                    print(f"🎬 _show_standard_overlay: Called overlay_window.realize()")
                    
                    # Get the GDK surface and try to configure it for Wayland
                    try:
                        surface = overlay_window.get_surface()
                        if surface:
                            # Request surface to be shown on top layer in Wayland
                            print(f"🎬 _show_standard_overlay: Got surface, attempting to configure for Wayland")
                            
                            # Try to set surface properties for overlay
                            try:
                                # For Wayland compositors, we may need to set hints
                                gdk_window = overlay_window.get_window()
                                if gdk_window:
                                    # Try to set the window as an overlay type
                                    try:
                                        gdk_window.set_type_hint(Gdk.WindowTypeHint.DIALOG)
                                    except:
                                        pass
                                    
                                    # Try to raise the window to the top
                                    gdk_window.focus(Gdk.CURRENT_TIME)
                                    gdk_window.raise_()
                                    print(f"🎬 _show_standard_overlay: Raised and focused window")
                            except Exception as window_props_error:
                                print(f"🎬 _show_standard_overlay: Error setting window properties: {window_props_error}")
                    except Exception as surface_error:
                        print(f"🎬 _show_standard_overlay: Error getting surface: {surface_error}")
                        
                except Exception as show_error:
                    print(f"🎬 _show_standard_overlay: Error showing overlay: {show_error}")
                    import traceback
                    traceback.print_exc()

            # Schedule the showing to happen after the window is properly initialized
            GLib.idle_add(show_overlay)
            print(f"🎬 _show_standard_overlay: Scheduled overlay presentation")

            print(f"🎬 _show_standard_overlay: Overlay window created for {animation_type}. Size: {overlay_window.get_default_width()}x{overlay_window.get_default_height()}")

            # Start animation timer
            def update_overlay():
                try:
                    overlay_window.animation_time += 1
                    self._update_overlay_particles(overlay_window.particles, animation_type)
                    drawing_area.queue_draw()
                    return True
                except Exception as update_error:
                    print(f"🎬 _show_standard_overlay: Error in update_overlay: {update_error}")
                    return False

            timer_id = GLib.timeout_add(33, update_overlay)  # ~30 FPS
            print(f"🎬 _show_standard_overlay: Started animation timer with ID: {timer_id}")

            # Auto-close after duration
            def close_overlay():
                print(f"🎬 _show_standard_overlay: Closing overlay after {duration} seconds")
                try:
                    GLib.source_remove(timer_id)
                except:
                    pass
                if overlay_window:
                    try:
                        overlay_window.destroy()
                        print(f"🎬 _show_standard_overlay: Destroyed overlay window")
                    except Exception as destroy_error:
                        print(f"🎬 _show_standard_overlay: Error destroying overlay: {destroy_error}")
                return False

            GLib.timeout_add_seconds(duration, close_overlay)
            print(f"🎬 _show_standard_overlay: Set up auto-close timer for {duration} seconds")

        except Exception as e:
            print(f"🎬 _show_standard_overlay: Error creating weather overlay: {e}")
            import traceback
            traceback.print_exc()

    def _show_niri_overlay(self, main_window, animation_type, duration):
        """Create Niri Wayland-specific overlay window"""
        try:
            from gi.repository import Gtk, GLib, Gdk
            import cairo, math, random

            print(f"🎬 _show_niri_overlay: Creating overlay for animation type: {animation_type}")
            print(f"🎬 _show_niri_overlay: Duration: {duration}")
            print(f"🎬 _show_niri_overlay: Main window provided: {main_window is not None}")

            # Create overlay window optimized for Niri
            overlay_window = Gtk.Window()
            print(f"🎬 _show_niri_overlay: Created overlay window object")

            overlay_window.set_modal(False)
            overlay_window.set_decorated(False)
            overlay_window.set_resizable(False)

            # Get screen dimensions for proper fullscreen
            try:
                display = Gdk.Display.get_default()
                if display:
                    print(f"🎬 _show_niri_overlay: Got display object")
                    # Get monitor geometry for proper sizing
                    monitor = display.get_primary_monitor()
                    if monitor:
                        print(f"🎬 _show_niri_overlay: Got primary monitor")
                        geometry = monitor.get_geometry()
                        print(f"🎬 _show_niri_overlay: Monitor geometry - Width: {geometry.width}, Height: {geometry.height}")
                        overlay_window.set_default_size(geometry.width, geometry.height)

                        # For Niri, try to set the window as a popup which might work better
                        try:
                            # Use Gdk.WindowTypeHint.SPLASHSCREEN or UTILITY for overlays
                            overlay_window.set_type_hint(Gdk.WindowTypeHint.SPLASHSCREEN)
                            print(f"🎬 _show_niri_overlay: Set window type hint to SPLASHSCREEN")
                        except Exception as hint_error:
                            print(f"🎬 _show_niri_overlay: Error setting SPLASHSCREEN type hint: {hint_error}")
                            try:
                                # Fallback to UTILITY
                                overlay_window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
                                print(f"🎬 _show_niri_overlay: Set window type hint to UTILITY")
                            except Exception as utility_error:
                                print(f"🎬 _show_niri_overlay: Error setting UTILITY type hint: {utility_error}")
                    else:
                        print(f"🎬 _show_niri_overlay: No primary monitor found, using fallback")
                        # Fallback to common resolution
                        overlay_window.set_default_size(1920, 1080)
                else:
                    print(f"🎬 _show_niri_overlay: No display object, using fallback resolution")
                    overlay_window.set_default_size(1920, 1080)
            except Exception as display_error:
                print(f"🎬 _show_niri_overlay: Error getting display info: {display_error}")
                # Fallback to common resolution
                overlay_window.set_default_size(1920, 1080)

            # Make window stay on top and be visible
            try:
                overlay_window.set_keep_above(True)
                print(f"🎬 _show_niri_overlay: Set window to stay above")
            except Exception as keep_above_error:
                print(f"🎬 _show_niri_overlay: Error setting keep_above: {keep_above_error}")

            # Don't set accept_focus for Niri to avoid stealing focus
            overlay_window.set_accept_focus(False)
            print(f"🎬 _show_niri_overlay: Set window to not accept focus")

            # For Niri Wayland, try to set opacity and visual properties
            try:
                overlay_window.set_opacity(0.9)  # Slightly less opaque to ensure visibility
                print(f"🎬 _show_niri_overlay: Set window opacity to 0.9")
            except Exception as opacity_error:
                print(f"🎬 _show_niri_overlay: Error setting opacity: {opacity_error}")
                pass

            # Create drawing area
            drawing_area = Gtk.DrawingArea()
            drawing_area.set_hexpand(True)
            drawing_area.set_vexpand(True)
            # Set drawing area size to match window
            drawing_area.set_size_request(overlay_window.get_default_width(), overlay_window.get_default_height())
            drawing_area.set_draw_func(self._draw_overlay_animation)
            overlay_window.set_child(drawing_area)
            print(f"🎬 _show_niri_overlay: Created and configured drawing area")

            # Store animation data
            overlay_window.animation_type = animation_type
            overlay_window.particles = self._init_overlay_particles(animation_type)
            overlay_window.animation_time = 0
            print(f"🎬 _show_niri_overlay: Initialized animation data - Particles: {len(overlay_window.particles)}")

            # Connect key press to close
            key_controller = Gtk.EventControllerKey()
            key_controller.connect('key-pressed', lambda c, k, kc, s: overlay_window.destroy() if k == Gdk.KEY_Escape else False)
            overlay_window.add_controller(key_controller)
            print(f"🎬 _show_niri_overlay: Connected key controller for ESC key")

            # For Niri, we need to ensure the window is properly shown
            def show_niri_overlay():
                try:
                    # Realize the window first
                    overlay_window.realize()
                    print(f"🎬 _show_niri_overlay: Window realized")
                    
                    # Then show the window
                    overlay_window.show()
                    print(f"🎬 _show_niri_overlay: Window shown")
                    
                    # Present the window to bring it to attention
                    overlay_window.present()
                    print(f"🎬 _show_niri_overlay: Window presented")
                    
                    # Get the GDK surface and try to configure it for Niri
                    try:
                        gdk_window = overlay_window.get_window()
                        if gdk_window:
                            print(f"🎬 _show_niri_overlay: Got GDK window, attempting to configure for Niri")
                            
                            # Try to set window properties specific to Niri
                            try:
                                # Set the window as an overlay - this is important for Niri
                                gdk_window.set_accept_focus(False)
                                
                                # Try to raise the window to ensure it's visible
                                gdk_window.raise_()
                                print(f"🎬 _show_niri_overlay: Window raised")
                                
                                # Focus the window with current time
                                gdk_window.focus(Gdk.CURRENT_TIME)
                                print(f"🎬 _show_niri_overlay: Window focused")
                                
                            except Exception as window_props_error:
                                print(f"🎬 _show_niri_overlay: Error setting window properties: {window_props_error}")
                    except Exception as surface_error:
                        print(f"🎬 _show_niri_overlay: Error getting GDK window: {surface_error}")
                        
                except Exception as show_error:
                    print(f"🎬 _show_niri_overlay: Error showing overlay: {show_error}")
                    import traceback
                    traceback.print_exc()

            # Schedule the showing to happen after the window is properly initialized
            GLib.idle_add(show_niri_overlay)
            print(f"🎬 _show_niri_overlay: Scheduled Niri overlay presentation")

            print(f"🎬 _show_niri_overlay: Niri overlay window created for {animation_type}. Size: {overlay_window.get_default_width()}x{overlay_window.get_default_height()}")

            # Start animation timer
            def update_overlay():
                try:
                    overlay_window.animation_time += 1
                    self._update_overlay_particles(overlay_window.particles, animation_type)
                    drawing_area.queue_draw()
                    return True
                except Exception as update_error:
                    print(f"🎬 _show_niri_overlay: Error in update_overlay: {update_error}")
                    return False

            timer_id = GLib.timeout_add(33, update_overlay)  # ~30 FPS
            print(f"🎬 _show_niri_overlay: Started animation timer with ID: {timer_id}")

            # Auto-close after duration
            def close_overlay():
                print(f"🎬 _show_niri_overlay: Closing overlay after {duration} seconds")
                try:
                    GLib.source_remove(timer_id)
                except:
                    pass
                if overlay_window:
                    try:
                        overlay_window.destroy()
                        print(f"🎬 _show_niri_overlay: Destroyed overlay window")
                    except Exception as destroy_error:
                        print(f"🎬 _show_niri_overlay: Error destroying overlay: {destroy_error}")
                return False

            GLib.timeout_add_seconds(duration, close_overlay)
            print(f"🎬 _show_niri_overlay: Set up auto-close timer for {duration} seconds")

        except Exception as e:
            print(f"🎬 _show_niri_overlay: Error creating weather overlay: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to standard overlay if Niri-specific fails
            self._show_standard_overlay(main_window, animation_type, duration)

    def _ensure_kde_desktop_layer(self, window):
        """Ensure window stays as desktop overlay in KDE"""
        try:
            import subprocess
            
            # Use wmctrl to set window as desktop-like overlay
            try:
                result = subprocess.run([
                    'wmctrl', '-r', 'Wall_IT_Weather_Overlay',
                    '-b', 'add,below,sticky'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("✅ wmctrl: Weather overlay set to desktop layer")
                else:
                    print(f"⚠️  wmctrl failed: {result.stderr}")
                    
            except FileNotFoundError:
                print("⚠️  wmctrl not available for window management")
            
            # Try GTK methods if available (GTK3 compatibility)
            try:
                if hasattr(window, 'set_keep_below'):
                    window.set_keep_below(True)
                if hasattr(window, 'lower'):
                    window.lower()
                print("✅ GTK stacking methods applied")
            except Exception as e:
                print(f"GTK stacking failed: {e}")
            
            # Additional KDE-specific DBus commands
            try:
                # Get all KWin windows and modify our overlay
                subprocess.run([
                    'qdbus', 'org.kde.KWin', '/KWin',
                    'org.kde.KWin.showDebugConsole'
                ], capture_output=True, check=False)
            except:
                pass
                
        except Exception as e:
            print(f"Warning: Could not enforce KDE desktop layer: {e}")
        
        return False  # Don't repeat timer
    
    def _close_overlay(self, overlay_window):
        """Properly close overlay window and cleanup resources"""
        try:
            if hasattr(overlay_window, '_timer_id'):
                GLib.source_remove(overlay_window._timer_id)
            overlay_window.destroy()
        except:
            pass
    
    def _draw_kde_overlay_animation(self, area, cr, width, height, data=None):
        """Draw KDE-optimized overlay animation with proper transparency"""
        import math
        import random

        # Get window data
        window = area.get_root()
        if not hasattr(window, 'animation_type'):
            return

        animation_type = window.animation_type
        particles = window.particles
        animation_time = window.animation_time

        # Semi-transparent background for better visibility against any wallpaper
        cr.set_operator(cairo.OPERATOR_SOURCE)  # Changed from OPERATOR_CLEAR to SOURCE for better visibility
        cr.set_source_rgba(0, 0, 0, 0.05)  # Very slightly transparent black for contrast
        cr.paint()

        # Draw effects with enhanced visibility for desktop overlay
        if animation_type in ['clear-night', 'night']:
            # Stars/sparkles with improved twinkling - increased visibility
            for particle in particles:
                # Use phase offset for varied twinkling
                brightness = particle['brightness'] * (0.4 + 0.6 * abs(math.sin(animation_time * particle['twinkle_speed'] + particle['twinkle_phase'])))

                # Consistent night stars regardless of specific type
                cr.set_source_rgba(1.0, 1.0, 0.95, brightness * 0.9)  # More visible white night stars

                # Draw enhanced star with glow effect
                size = particle['size'] * 2.0  # Larger for better visibility
                x, y = particle['x'], particle['y']

                # Main star
                cr.arc(x, y, size, 0, 2 * math.pi)
                cr.fill()

                # Add enhanced glow for better visibility
                if brightness > 0.6:
                    glow_alpha = brightness * 0.5
                    cr.set_source_rgba(1.0, 1.0, 0.95, glow_alpha)
                    cr.arc(x, y, size * 2.5, 0, 2 * math.pi)
                    cr.fill()

        elif animation_type in ['partly-cloudy-day', 'cloudy', 'sunset', 'sunset_transition', 'dawn']:
            # Atmospheric/sunset effects - colorful skies with subtle particles
            for particle in particles:
                # Calculate pulsing effect for atmospheric particles
                pulse = 0.5 + 0.5 * math.sin(animation_time * particle['pulse_speed'] + particle['pulse_phase'])
                opacity = particle['opacity'] * pulse

                # Color varies based on time period for realistic atmospheric effects
                if animation_type in ['sunset', 'sunset_transition']:
                    # Sunset colors: oranges, reds, purples
                    hue = random.choice([(1.0, 0.4, 0.2), (1.0, 0.6, 0.2), (0.9, 0.7, 0.3)])  # Red-orange-yellow
                elif animation_type == 'dawn':
                    # Dawn colors: soft pinks, oranges, yellows
                    hue = random.choice([(1.0, 0.7, 0.5), (1.0, 0.8, 0.4), (0.9, 0.8, 0.6)])  # Pink-orange-yellow
                elif animation_type in ['cloudy', 'partly-cloudy-day']:
                    # Cloudy/day colors: soft blues, grays, whites
                    hue = random.choice([(0.7, 0.8, 1.0), (0.8, 0.8, 0.9), (0.9, 0.9, 1.0)])  # Soft blues/grays
                else:
                    # Fallback to sunset colors
                    hue = (1.0, 0.6, 0.3)

                if particle['ray_type'] == 'ray':
                    # Draw atmospheric rays - softer and more colorful
                    cr.set_source_rgba(hue[0], hue[1], hue[2], opacity * 0.5)
                    cr.set_line_width(particle['thickness'] * 1.5)

                    # Draw ray from center outward
                    end_x = particle['x'] + math.cos(particle['angle']) * particle['length'] * pulse
                    end_y = particle['y'] + math.sin(particle['angle']) * particle['length'] * pulse

                    cr.move_to(particle['x'], particle['y'])
                    cr.line_to(end_x, end_y)
                    cr.stroke()
                elif particle['ray_type'] == 'glow':
                    # Draw atmospheric glow - soft and colorful
                    cr.set_source_rgba(hue[0], hue[1], hue[2], opacity * 0.4)
                    radius = 45 * pulse
                    cr.arc(particle['x'], particle['y'], radius, 0, 2 * math.pi)
                    cr.fill()
                elif particle['ray_type'] == 'atmosphere':
                    # Draw atmospheric haze/particles - soft and diffused
                    cr.set_source_rgba(hue[0], hue[1], hue[2], opacity * 0.3)
                    # Draw as a soft ellipse for atmospheric effect
                    cr.save()
                    cr.translate(particle['x'], particle['y'])
                    cr.scale(1.8, 1.0)  # Elliptical shape for atmospheric effect
                    cr.arc(0, 0, 25 * pulse, 0, 2 * math.pi)
                    cr.fill()
                    cr.restore()

        elif animation_type in ['clear-day', 'sunny', 'noon', 'morning', 'afternoon', 'day']:
            # Draw sun rays or light particles for daytime (KDE version) - with distinct characteristics
            for particle in particles:
                # Calculate pulsing effect
                pulse = 0.5 + 0.5 * math.sin(animation_time * particle['pulse_speed'] + particle['pulse_phase'])
                opacity = particle['opacity'] * pulse

                # Adjust appearance based on specific time period
                if animation_type == 'noon':
                    # Noon: More intense, direct sunlight
                    base_color = (1.0, 0.95, 0.7)  # Brighter yellow
                    intensity_factor = 1.3
                elif animation_type == 'morning':
                    # Morning: Softer, warmer tones
                    base_color = (1.0, 0.85, 0.6)  # Warmer, softer
                    intensity_factor = 1.0
                elif animation_type in ['afternoon', 'clear-day', 'sunny', 'day']:
                    # Afternoon/clear day: Golden, warm but not as intense as noon
                    base_color = (1.0, 0.88, 0.65)  # Golden tone
                    intensity_factor = 1.15
                else:  # day (fallback)
                    base_color = (1.0, 0.9, 0.7)
                    intensity_factor = 1.0

                if particle['ray_type'] == 'ray':
                    # Draw sun rays emanating from center - more visible
                    cr.set_source_rgba(base_color[0], base_color[1], base_color[2], opacity * 0.7 * intensity_factor)
                    cr.set_line_width(particle['thickness'] * 2.0 * intensity_factor)  # Much thicker for visibility

                    # Draw ray from center outward
                    end_x = particle['x'] + math.cos(particle['angle']) * particle['length'] * pulse
                    end_y = particle['y'] + math.sin(particle['angle']) * particle['length'] * pulse

                    cr.move_to(particle['x'], particle['y'])
                    cr.line_to(end_x, end_y)
                    cr.stroke()

                elif particle['ray_type'] == 'glow':
                    # Draw circular glow effect - more visible
                    cr.set_source_rgba(base_color[0], base_color[1], base_color[2]*0.9, opacity * 0.5 * intensity_factor)
                    radius = 40 * pulse * intensity_factor  # Larger radius
                    cr.arc(particle['x'], particle['y'], radius, 0, 2 * math.pi)
                    cr.fill()

                elif particle['ray_type'] == 'beam':
                    # Draw vertical light beam - more visible
                    cr.set_source_rgba(base_color[0], base_color[1]*0.95, base_color[2]*0.9, opacity * 0.6 * intensity_factor)
                    x = particle['x']
                    y_top = particle['y']
                    y_bottom = y_top + particle['length']

                    # Create gradient for beam
                    gradient = cairo.LinearGradient(x, y_top, x, y_bottom)
                    gradient.add_color_stop_rgba(0, base_color[0], base_color[1]*0.95, base_color[2]*0.9, opacity * 0.8 * intensity_factor)
                    gradient.add_color_stop_rgba(1, base_color[0], base_color[1]*0.95, base_color[2]*0.9, 0)
                    cr.set_source(gradient)

                    # Draw beam as rectangle - wider for visibility
                    width_factor = 8 * intensity_factor
                    cr.rectangle(x - width_factor, y_top, width_factor * 2, particle['length'])
                    cr.fill()

        elif animation_type == 'rain':
            # Enhanced rain with variable thickness - more visible
            for particle in particles:
                # Calculate brightness based on length
                alpha = 0.9 * (particle['length'] / 35.0)  # Higher base alpha
                cr.set_source_rgba(0.5, 0.6, 0.9, alpha)  # More vibrant blue
                cr.set_line_width(particle['thickness'] * 2.0)  # Much thicker for visibility
                cr.move_to(particle['x'], particle['y'])
                cr.line_to(particle['x'] + 4, particle['y'] + particle['length'])  # Longer lines
                cr.stroke()

        elif animation_type == 'snow':
            # Enhanced snow with oscillation effect - more visible
            for particle in particles:
                # Calculate opacity based on size
                alpha = 0.9 + (particle['size'] / 7.0) * 0.1  # Higher base alpha
                cr.set_source_rgba(0.95, 1.0, 1.0, alpha)  # Slightly bluish-white

                # Add gentle oscillation to position
                oscillation_offset = math.sin(particle['oscillation']) * 3
                x_pos = particle['x'] + oscillation_offset

                # Draw snowflake (larger for better visibility)
                size = particle['size'] * 1.8
                cr.arc(x_pos, particle['y'], size, 0, 2 * math.pi)
                cr.fill()

                # Add subtle highlight for better visibility
                cr.set_source_rgba(1.0, 1.0, 1.0, alpha * 0.7)
                cr.arc(x_pos - 1, particle['y'] - 1, size * 0.8, 0, 2 * math.pi)
                cr.fill()

        elif animation_type == 'fog':
            # Draw fog/mist particles - soft and translucent
            for particle in particles:
                # Soft gray/white fog particles
                alpha = particle['opacity']
                cr.set_source_rgba(0.9, 0.92, 0.95, alpha)  # Light grayish-white
                
                # Draw as soft circles for fog effect
                size = particle['size']
                x, y = particle['x'], particle['y']
                
                # Draw soft fog cloud
                cr.arc(x, y, size, 0, 2 * math.pi)
                cr.fill()
                
                # Add subtle glow for mist effect
                cr.set_source_rgba(0.95, 0.97, 1.0, alpha * 0.4)
                cr.arc(x, y, size * 1.8, 0, 2 * math.pi)
                cr.fill()

        # Ensure the drawing is properly flushed
        cr.stroke_preserve()
    
    def toggle_animation(self):
        """Toggle weather animation on/off"""
        self.animation_enabled = not self.animation_enabled
        return self.animation_enabled
    
    def _init_overlay_particles(self, animation_type):
        """Initialize particles for overlay animation"""
        import random
        particles = []

        # Get screen dimensions dynamically
        try:
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
            monitor = display.get_primary_monitor() if display.get_primary_monitor() else display.get_monitor(0)
            geometry = monitor.get_geometry()
            screen_width = geometry.width
            screen_height = geometry.height
        except:
            # Fallback to common resolution
            screen_width = 1920
            screen_height = 1080

        # Handle actual weather conditions first, then fallback to time-based
        if animation_type in ['clear-night', 'night']:
            # Stars/sparkles - increase density for better visual effect
            for _ in range(120):  # Increased for better visibility
                particles.append({
                    'x': random.uniform(0, screen_width),
                    'y': random.uniform(0, screen_height * 0.6),  # Top 60% of screen
                    'brightness': random.uniform(0.5, 1.0),  # Higher minimum brightness
                    'twinkle_speed': random.uniform(0.03, 0.12),  # Slightly faster twinkling
                    'size': random.uniform(2, 4),  # Larger size for better visibility
                    'twinkle_phase': random.uniform(0, 2 * math.pi)  # Phase offset for twinkling
                })
        elif animation_type in ['partly_cloudy', 'partly_cloudy_day', 'partly-cloudy-day']:
            # Partly cloudy with sun rays - mix of clouds and sun effects
            # Add cloud-like particles
            for _ in range(15):  # Fewer clouds
                particles.append({
                    'x': random.uniform(0, screen_width),
                    'y': random.uniform(0, screen_height * 0.4),  # Top portion
                    'size': random.uniform(30, 80),  # Larger cloud-like particles
                    'speed_x': random.uniform(-0.5, 0.5),  # Slow horizontal movement
                    'opacity': random.uniform(0.3, 0.6),  # Semi-transparent
                    'type': 'cloud'
                })
            # Add some sun rays
            for _ in range(20):  # Fewer sun rays than clear day
                particles.append({
                    'x': random.uniform(screen_width * 0.3, screen_width * 0.7),  # Center area
                    'y': random.uniform(screen_height * 0.1, screen_height * 0.3),  # Top area
                    'angle': random.uniform(0, 2 * math.pi),  # Direction of ray
                    'length': random.uniform(30, 90),  # Shorter rays for partly cloudy
                    'thickness': random.uniform(2.0, 4.5),  # Medium thickness
                    'opacity': random.uniform(0.3, 0.6),  # More subtle
                    'pulse_speed': random.uniform(0.05, 0.09),  # Gentle pulsing
                    'pulse_phase': random.uniform(0, 2 * math.pi),  # Phase for pulsing
                    'ray_type': random.choice(['ray', 'glow']),  # Sun rays and glows
                    'type': 'sun_ray'
                })
        elif animation_type in ['partly_cloudy_night', 'partly-cloudy-night']:
            # Partly cloudy at night - mix of clouds and stars
            # Add cloud-like particles
            for _ in range(15):  # Fewer clouds
                particles.append({
                    'x': random.uniform(0, screen_width),
                    'y': random.uniform(0, screen_height * 0.4),  # Top portion
                    'size': random.uniform(30, 80),  # Larger cloud-like particles
                    'speed_x': random.uniform(-0.3, 0.3),  # Slow horizontal movement
                    'opacity': random.uniform(0.4, 0.7),  # Slightly more opaque at night
                    'type': 'cloud'
                })
            # Add some stars
            for _ in range(60):  # Fewer stars due to clouds
                particles.append({
                    'x': random.uniform(0, screen_width),
                    'y': random.uniform(0, screen_height * 0.5),  # Top half
                    'brightness': random.uniform(0.4, 0.9),  # Variable brightness
                    'twinkle_speed': random.uniform(0.02, 0.1),  # Twinkling
                    'size': random.uniform(1.5, 3),  # Smaller stars
                    'twinkle_phase': random.uniform(0, 2 * math.pi),  # Phase offset for twinkling
                    'type': 'star'
                })
        elif animation_type in ['clear-day', 'sunny', 'noon', 'morning', 'afternoon', 'day']:
            # Sun rays or light particles for daytime - with distinct characteristics
            num_particles = 45

            # Determine characteristics based on specific time period if provided
            if animation_type == 'noon':
                # Noon: More intense, direct rays
                length_range = (40, 140)  # Longer rays
                thickness_range = (3, 7)   # Thicker rays
                opacity_range = (0.5, 0.9) # Higher opacity
                pulse_range = (0.07, 0.13) # Slightly faster pulsing
            elif animation_type == 'morning':
                # Morning: Softer, gentler rays
                length_range = (25, 100)   # Shorter rays
                thickness_range = (2, 5)   # Thinner rays
                opacity_range = (0.3, 0.7) # Lower opacity
                pulse_range = (0.05, 0.10) # Slower pulsing
            elif animation_type == 'afternoon':
                # Afternoon: Golden, warm rays
                length_range = (30, 120)   # Medium rays
                thickness_range = (2.5, 6) # Medium thickness
                opacity_range = (0.4, 0.8) # Medium opacity
                pulse_range = (0.06, 0.12) # Medium pulsing
            elif animation_type in ['clear-day', 'sunny', 'day']:
                # General clear/sunny day
                length_range = (35, 130)   # Balanced rays
                thickness_range = (2.5, 6.5) # Balanced thickness
                opacity_range = (0.45, 0.85) # Balanced opacity
                pulse_range = (0.06, 0.11) # Balanced pulsing
            else:  # fallback
                length_range = (30, 120)
                thickness_range = (2, 6)
                opacity_range = (0.4, 0.8)
                pulse_range = (0.06, 0.12)

            for _ in range(num_particles):
                particles.append({
                    'x': random.uniform(screen_width * 0.2, screen_width * 0.8),  # Wider center area
                    'y': random.uniform(screen_height * 0.05, screen_height * 0.5),  # Higher top area
                    'angle': random.uniform(0, 2 * math.pi),  # Direction of ray
                    'length': random.uniform(length_range[0], length_range[1]),  # Length of sun ray
                    'thickness': random.uniform(thickness_range[0], thickness_range[1]),  # Thickness of ray
                    'opacity': random.uniform(opacity_range[0], opacity_range[1]),  # Opacity of ray
                    'pulse_speed': random.uniform(pulse_range[0], pulse_range[1]),  # Pulsing speed
                    'pulse_phase': random.uniform(0, 2 * math.pi),  # Phase for pulsing
                    'ray_type': random.choice(['ray', 'glow', 'beam'])  # Type of light effect
                })
        elif animation_type in ['cloudy', 'sunset', 'sunset_transition', 'dawn']:
            # For cloudy/sunset conditions - mix of atmospheric effects
            # More atmospheric particles for colorful skies
            for _ in range(30):  # Fewer rays but more atmosphere
                particles.append({
                    'x': random.uniform(screen_width * 0.1, screen_width * 0.9),  # Wider spread
                    'y': random.uniform(screen_height * 0.05, screen_height * 0.6),  # Higher area
                    'angle': random.uniform(0, 2 * math.pi),
                    'length': random.uniform(20, 100),  # Shorter for atmospheric effect
                    'thickness': random.uniform(1.5, 4),  # Thinner for subtle effect
                    'opacity': random.uniform(0.2, 0.6),  # More variation for atmosphere
                    'pulse_speed': random.uniform(0.04, 0.09),  # Slower pulsing
                    'pulse_phase': random.uniform(0, 2 * math.pi),
                    'ray_type': random.choice(['ray', 'glow', 'atmosphere'])  # Include atmospheric effects
                })
        elif animation_type == 'rain':
            # Rain drops - adjust for screen size
            for _ in range(int(200 * (screen_width / 1920))):  # Increased for better visibility
                particles.append({
                    'x': random.uniform(0, screen_width),
                    'y': random.uniform(-200, screen_height),
                    'speed': random.uniform(15, 25),  # Faster for better effect
                    'length': random.uniform(20, 45),  # Longer for visibility
                    'thickness': random.uniform(2.0, 4.0)  # Thicker for visibility
                })
        elif animation_type == 'snow':
            # Snow flakes - adjust for screen size
            for _ in range(int(120 * (screen_width / 1920))):  # Increased for better visibility
                particles.append({
                    'x': random.uniform(0, screen_width),
                    'y': random.uniform(-200, screen_height),
                    'speed': random.uniform(1.5, 4),  # Slightly faster
                    'size': random.uniform(4, 9),  # Larger for better visibility
                    'drift': random.uniform(-1.5, 1.5),  # More drift variation
                    'oscillation': random.uniform(0, 2 * math.pi),  # Side-to-side movement
                    'oscillation_speed': random.uniform(0.03, 0.07)  # Slightly faster oscillation
                })
        elif animation_type == 'fog':
            # Fog/mist particles - slow moving, low opacity
            for _ in range(int(150 * (screen_width / 1920))):
                particles.append({
                    'x': random.uniform(0, screen_width),
                    'y': random.uniform(0, screen_height),
                    'speed_x': random.uniform(-0.5, 0.5),  # Slow horizontal movement
                    'speed_y': random.uniform(-0.2, 0.2),  # Very slow vertical movement
                    'size': random.uniform(15, 40),  # Large soft particles
                    'opacity': random.uniform(0.1, 0.3),  # Low opacity for fog effect
                    'drift': random.uniform(0, 2 * math.pi),  # Slow drifting
                    'drift_speed': random.uniform(0.01, 0.03)  # Very slow drift
                })
        elif animation_type == 'wind':
            # Wind effect - moving particles representing air movement
            for _ in range(int(80 * (screen_width / 1920))):
                particles.append({
                    'x': random.uniform(0, screen_width),
                    'y': random.uniform(0, screen_height),
                    'speed_x': random.uniform(1.0, 4.0),  # Horizontal movement
                    'speed_y': random.uniform(-1.0, 1.0), # Some vertical movement
                    'length': random.uniform(10, 30),  # Short lines representing wind
                    'opacity': random.uniform(0.2, 0.5),  # Subtle visibility
                    'type': 'wind'
                })

        return particles
    
    def _update_overlay_particles(self, particles, animation_type):
        """Update particle positions"""
        import random

        # Get screen dimensions dynamically
        try:
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
            monitor = display.get_primary_monitor() if display.get_primary_monitor() else display.get_monitor(0)
            geometry = monitor.get_geometry()
            screen_width = geometry.width
            screen_height = geometry.height
        except:
            # Fallback to common resolution
            screen_width = 1920
            screen_height = 1080

        for particle in particles:
            if animation_type == 'rain':
                particle['y'] += particle['speed']
                if particle['y'] > screen_height + 100:
                    particle['y'] = random.uniform(-100, -50)
                    particle['x'] = random.uniform(0, screen_width)
            elif animation_type == 'snow':
                particle['y'] += particle['speed']
                # Add oscillation for more natural snow movement
                particle['oscillation'] += particle['oscillation_speed']
                particle['x'] += particle['drift'] + math.sin(particle['oscillation']) * 0.5  # Gentle side-to-side motion
                if particle['y'] > screen_height + 100:
                    particle['y'] = random.uniform(-100, -50)
                    particle['x'] = random.uniform(0, screen_width)
            elif animation_type == 'fog':
                # Update fog particles with slow movement
                particle['x'] += particle['speed_x']
                particle['y'] += particle['speed_y']

                # Wrap around screen edges
                if particle['x'] > screen_width:
                    particle['x'] = 0
                elif particle['x'] < 0:
                    particle['x'] = screen_width

                if particle['y'] > screen_height:
                    particle['y'] = 0
                elif particle['y'] < 0:
                    particle['y'] = screen_height

                # Update drift for natural movement
                particle['drift'] += particle['drift_speed']
            elif animation_type in ['partly_cloudy', 'partly_cloudy_day', 'partly-cloudy-day', 'cloudy']:
                # Update cloud particles for partly cloudy animation
                if 'speed_x' in particle and particle.get('type') == 'cloud':
                    particle['x'] += particle['speed_x']
                    # Wrap around screen edges
                    if particle['x'] > screen_width + 50:
                        particle['x'] = -50
                    elif particle['x'] < -50:
                        particle['x'] = screen_width + 50
            elif animation_type in ['partly_cloudy_night', 'partly-cloudy-night']:
                # Update cloud particles for partly cloudy night
                if 'speed_x' in particle and particle.get('type') == 'cloud':
                    particle['x'] += particle['speed_x']
                    # Wrap around screen edges
                    if particle['x'] > screen_width + 50:
                        particle['x'] = -50
                    elif particle['x'] < -50:
                        particle['x'] = screen_width + 50
            elif animation_type == 'wind':
                # Update wind particles
                if particle.get('type') == 'wind':
                    particle['x'] += particle['speed_x']
                    particle['y'] += particle['speed_y']
                    
                    # Wrap around screen edges
                    if particle['x'] > screen_width + 20:
                        particle['x'] = -20
                        particle['y'] = random.uniform(0, screen_height)
                    elif particle['x'] < -20:
                        particle['x'] = screen_width + 20
                        particle['y'] = random.uniform(0, screen_height)
                    
                    # Reset Y if it goes too far off screen
                    if particle['y'] > screen_height + 20:
                        particle['y'] = -20
                        particle['x'] = random.uniform(0, screen_width)
                    elif particle['y'] < -20:
                        particle['y'] = screen_height + 20
                        particle['x'] = random.uniform(0, screen_width)
            # For daytime animations (noon, morning, afternoon, day), particles are stationary with pulsing effects
            # so no position updates are needed
    
    def _draw_overlay_animation(self, area, cr, width, height, data=None):
        """Draw overlay animation"""
        import math
        import random

        # Get window data
        window = area.get_root()
        if not hasattr(window, 'animation_type'):
            return

        animation_type = window.animation_type
        particles = window.particles
        animation_time = window.animation_time

        # Semi-transparent background for better visibility against any wallpaper
        cr.set_operator(cairo.OPERATOR_SOURCE)  # Changed from OPERATOR_CLEAR to SOURCE for better visibility
        cr.set_source_rgba(0, 0, 0, 0.05)  # Very slightly transparent black for contrast
        cr.paint()

        # Draw effects based on actual weather conditions first, then fallback to time-based
        if animation_type in ['clear-night', 'night']:
            # Stars/sparkles with improved twinkling - increased visibility
            for particle in particles:
                # Use phase offset for varied twinkling
                brightness = particle['brightness'] * (0.4 + 0.6 * abs(math.sin(animation_time * particle['twinkle_speed'] + particle['twinkle_phase'])))

                # Consistent night stars regardless of specific type
                cr.set_source_rgba(1.0, 1.0, 0.95, brightness * 0.9)  # More visible white night stars

                # Draw star with glow effect
                size = particle['size'] * 1.5  # Larger for better visibility
                x, y = particle['x'], particle['y']

                # Main star
                cr.arc(x, y, size, 0, 2 * math.pi)
                cr.fill()

                # Enhanced glow for brighter stars
                if brightness > 0.6:
                    glow_alpha = brightness * 0.4
                    cr.set_source_rgba(1.0, 1.0, 0.95, glow_alpha)
                    cr.arc(x, y, size * 2.0, 0, 2 * math.pi)
                    cr.fill()

        elif animation_type in ['partly_cloudy', 'partly_cloudy_day', 'partly-cloudy-day']:
            # Partly cloudy with sun rays - mix of clouds and sun effects
            for particle in particles:
                if particle.get('type') == 'cloud':
                    # Draw cloud-like particles
                    cr.set_source_rgba(0.8, 0.85, 0.9, particle['opacity'])
                    # Draw fluffy cloud shape using multiple circles
                    x, y = particle['x'], particle['y']
                    size = particle['size']
                    
                    # Draw cloud as a cluster of circles
                    for i in range(4):
                        offset_x = (i - 1.5) * size * 0.4
                        cr.arc(x + offset_x, y, size * 0.5, 0, 2 * math.pi)
                        cr.fill()
                        
                    # Add subtle outline
                    cr.set_source_rgba(0.7, 0.75, 0.85, particle['opacity'] * 0.6)
                    cr.arc(x, y, size * 0.5, 0, 2 * math.pi)
                    cr.stroke()
                    
                elif particle.get('type') == 'sun_ray':
                    # Calculate pulsing effect for sun rays
                    pulse = 0.5 + 0.5 * math.sin(animation_time * particle['pulse_speed'] + particle['pulse_phase'])
                    opacity = particle['opacity'] * pulse
                    
                    # Draw sun rays emanating from center - more visible
                    base_color = (1.0, 0.9, 0.6)  # Golden tone for partly cloudy
                    cr.set_source_rgba(base_color[0], base_color[1], base_color[2], opacity * 0.5)
                    cr.set_line_width(particle['thickness'] * 1.2)  # Thicker lines

                    # Draw ray from center outward
                    end_x = particle['x'] + math.cos(particle['angle']) * particle['length'] * pulse
                    end_y = particle['y'] + math.sin(particle['angle']) * particle['length'] * pulse

                    cr.move_to(particle['x'], particle['y'])
                    cr.line_to(end_x, end_y)
                    cr.stroke()
        elif animation_type in ['partly_cloudy_night', 'partly-cloudy-night']:
            # Partly cloudy at night - mix of clouds and stars
            for particle in particles:
                if particle.get('type') == 'cloud':
                    # Draw cloud-like particles (darker for night)
                    cr.set_source_rgba(0.3, 0.35, 0.45, particle['opacity'])
                    # Draw fluffy cloud shape using multiple circles
                    x, y = particle['x'], particle['y']
                    size = particle['size']
                    
                    # Draw cloud as a cluster of circles
                    for i in range(4):
                        offset_x = (i - 1.5) * size * 0.4
                        cr.arc(x + offset_x, y, size * 0.5, 0, 2 * math.pi)
                        cr.fill()
                        
                elif particle.get('type') == 'star':
                    # Use phase offset for varied twinkling
                    brightness = particle['brightness'] * (0.4 + 0.6 * abs(math.sin(animation_time * particle['twinkle_speed'] + particle['twinkle_phase'])))

                    # Night stars
                    cr.set_source_rgba(1.0, 1.0, 0.95, brightness * 0.8)  # More visible white night stars

                    # Draw star with glow effect
                    size = particle['size'] * 1.3  # Larger for better visibility
                    x, y = particle['x'], particle['y']

                    # Main star
                    cr.arc(x, y, size, 0, 2 * math.pi)
                    cr.fill()

                    # Enhanced glow for brighter stars
                    if brightness > 0.6:
                        glow_alpha = brightness * 0.3
                        cr.set_source_rgba(1.0, 1.0, 0.95, glow_alpha)
                        cr.arc(x, y, size * 1.8, 0, 2 * math.pi)
                        cr.fill()
        elif animation_type in ['cloudy', 'sunset', 'sunset_transition', 'dawn']:
            # Atmospheric/sunset effects - colorful skies with subtle particles
            for particle in particles:
                # Calculate pulsing effect for atmospheric particles
                pulse = 0.5 + 0.5 * math.sin(animation_time * particle['pulse_speed'] + particle['pulse_phase'])
                opacity = particle['opacity'] * pulse

                # Color varies based on time period for realistic atmospheric effects
                if animation_type in ['sunset', 'sunset_transition']:
                    # Sunset colors: oranges, reds, purples
                    hue = random.choice([(1.0, 0.4, 0.2), (1.0, 0.6, 0.2), (0.9, 0.7, 0.3)])  # Red-orange-yellow
                elif animation_type == 'dawn':
                    # Dawn colors: soft pinks, oranges, yellows
                    hue = random.choice([(1.0, 0.7, 0.5), (1.0, 0.8, 0.4), (0.9, 0.8, 0.6)])  # Pink-orange-yellow
                elif animation_type in ['cloudy', 'partly-cloudy-day']:
                    # Cloudy/day colors: soft blues, grays, whites
                    hue = random.choice([(0.7, 0.8, 1.0), (0.8, 0.8, 0.9), (0.9, 0.9, 1.0)])  # Soft blues/grays
                else:
                    # Fallback to sunset colors
                    hue = (1.0, 0.6, 0.3)

                if particle['ray_type'] == 'ray':
                    # Draw atmospheric rays - softer and more colorful
                    cr.set_source_rgba(hue[0], hue[1], hue[2], opacity * 0.4)
                    cr.set_line_width(particle['thickness'] * 1.0)

                    # Draw ray from center outward
                    end_x = particle['x'] + math.cos(particle['angle']) * particle['length'] * pulse
                    end_y = particle['y'] + math.sin(particle['angle']) * particle['length'] * pulse

                    cr.move_to(particle['x'], particle['y'])
                    cr.line_to(end_x, end_y)
                    cr.stroke()
                elif particle['ray_type'] == 'glow':
                    # Draw atmospheric glow - soft and colorful
                    cr.set_source_rgba(hue[0], hue[1], hue[2], opacity * 0.3)
                    radius = 35 * pulse
                    cr.arc(particle['x'], particle['y'], radius, 0, 2 * math.pi)
                    cr.fill()
                elif particle['ray_type'] == 'atmosphere':
                    # Draw atmospheric haze/particles - soft and diffused
                    cr.set_source_rgba(hue[0], hue[1], hue[2], opacity * 0.2)
                    # Draw as a soft ellipse for atmospheric effect
                    cr.save()
                    cr.translate(particle['x'], particle['y'])
                    cr.scale(1.5, 0.8)  # Elliptical shape for atmospheric effect
                    cr.arc(0, 0, 20 * pulse, 0, 2 * math.pi)
                    cr.fill()
                    cr.restore()

        elif animation_type in ['clear-day', 'sunny', 'noon', 'morning', 'afternoon', 'day']:
            # Sun rays or light particles for daytime - with distinct characteristics
            for particle in particles:
                # Calculate pulsing effect
                pulse = 0.5 + 0.5 * math.sin(animation_time * particle['pulse_speed'] + particle['pulse_phase'])
                opacity = particle['opacity'] * pulse

                # Adjust appearance based on specific time period
                if animation_type == 'noon':
                    # Noon: More intense, direct sunlight
                    base_color = (1.0, 0.95, 0.7)  # Brighter yellow
                    intensity_factor = 1.2
                elif animation_type == 'morning':
                    # Morning: Softer, warmer tones
                    base_color = (1.0, 0.85, 0.6)  # Warmer, softer
                    intensity_factor = 1.0
                elif animation_type in ['afternoon', 'clear-day', 'sunny', 'day']:
                    # Afternoon/clear day: Golden, warm but not as intense as noon
                    base_color = (1.0, 0.88, 0.65)  # Golden tone
                    intensity_factor = 1.1
                else:  # day (fallback)
                    base_color = (1.0, 0.9, 0.7)
                    intensity_factor = 1.0

                if particle['ray_type'] == 'ray':
                    # Draw sun rays emanating from center - more visible
                    cr.set_source_rgba(base_color[0], base_color[1], base_color[2], opacity * 0.6 * intensity_factor)
                    cr.set_line_width(particle['thickness'] * 1.5 * intensity_factor)  # Thicker lines

                    # Draw ray from center outward
                    end_x = particle['x'] + math.cos(particle['angle']) * particle['length'] * pulse
                    end_y = particle['y'] + math.sin(particle['angle']) * particle['length'] * pulse

                    cr.move_to(particle['x'], particle['y'])
                    cr.line_to(end_x, end_y)
                    cr.stroke()

                elif particle['ray_type'] == 'glow':
                    # Draw circular glow effect - more visible
                    cr.set_source_rgba(base_color[0], base_color[1], base_color[2]*0.9, opacity * 0.4 * intensity_factor)
                    radius = 35 * pulse * intensity_factor
                    cr.arc(particle['x'], particle['y'], radius, 0, 2 * math.pi)
                    cr.fill()

                elif particle['ray_type'] == 'beam':
                    # Draw vertical light beam - more visible
                    cr.set_source_rgba(base_color[0], base_color[1]*0.95, base_color[2]*0.9, opacity * 0.5 * intensity_factor)
                    x = particle['x']
                    y_top = particle['y']
                    y_bottom = y_top + particle['length']

                    # Create gradient for beam
                    gradient = cairo.LinearGradient(x, y_top, x, y_bottom)
                    gradient.add_color_stop_rgba(0, base_color[0], base_color[1]*0.95, base_color[2]*0.9, opacity * 0.7 * intensity_factor)
                    gradient.add_color_stop_rgba(1, base_color[0], base_color[1]*0.95, base_color[2]*0.9, 0)
                    cr.set_source(gradient)

                    # Draw beam as rectangle - wider for visibility
                    width_factor = 7 * intensity_factor
                    cr.rectangle(x - width_factor, y_top, width_factor * 2, particle['length'])
                    cr.fill()

        elif animation_type == 'rain':
            # Enhanced rain with variable thickness - more visible
            for particle in particles:
                # Calculate brightness based on length
                alpha = 0.8 * (particle['length'] / 35.0)  # Higher base alpha
                cr.set_source_rgba(0.4, 0.6, 0.9, alpha)  # More vibrant blue-gray for rain
                cr.set_line_width(particle['thickness'] * 1.5)  # Thicker lines
                cr.move_to(particle['x'], particle['y'])
                cr.line_to(particle['x'] + 2, particle['y'] + particle['length'])  # Longer lines
                cr.stroke()

        elif animation_type == 'snow':
            # Enhanced snow with oscillation effect - more visible
            for particle in particles:
                # Calculate opacity based on size
                alpha = 0.8 + (particle['size'] / 9.0) * 0.2  # Higher base alpha
                cr.set_source_rgba(0.95, 1.0, 1.0, alpha)  # Slightly bluish-white

                # Add gentle oscillation to position
                oscillation_offset = math.sin(particle['oscillation']) * 3
                x_pos = particle['x'] + oscillation_offset

                # Draw snowflake - larger for better visibility
                size = particle['size'] * 1.3
                cr.arc(x_pos, particle['y'], size, 0, 2 * math.pi)
                cr.fill()

                # Add subtle highlight for better visibility
                cr.set_source_rgba(1.0, 1.0, 1.0, alpha * 0.6)
                cr.arc(x_pos - 0.5, particle['y'] - 0.5, size * 0.7, 0, 2 * math.pi)
                cr.fill()

        elif animation_type == 'fog':
            # Draw fog/mist particles - soft and translucent
            for particle in particles:
                # Soft gray/white fog particles
                alpha = particle['opacity']
                cr.set_source_rgba(0.9, 0.92, 0.95, alpha)  # Light grayish-white

                # Draw as soft circles for fog effect
                size = particle['size']
                x, y = particle['x'], particle['y']

                # Draw soft fog cloud
                cr.arc(x, y, size, 0, 2 * math.pi)
                cr.fill()

                # Add subtle glow for mist effect
                cr.set_source_rgba(0.95, 0.97, 1.0, alpha * 0.3)
                cr.arc(x, y, size * 1.5, 0, 2 * math.pi)
                cr.fill()

        elif animation_type == 'wind':
            # Draw wind particles - represented as short lines indicating air movement
            for particle in particles:
                if particle.get('type') == 'wind':
                    # Draw wind direction indicators
                    alpha = particle['opacity']
                    cr.set_source_rgba(0.7, 0.8, 0.9, alpha)  # Light blue-gray for wind
                    cr.set_line_width(1.5)
                    
                    # Draw short lines in direction of wind
                    x, y = particle['x'], particle['y']
                    end_x = x + particle['length'] * 0.7
                    end_y = y + particle['speed_y'] * 0.5  # Include vertical component
                    
                    cr.move_to(x, y)
                    cr.line_to(end_x, end_y)
                    cr.stroke()
                    
                    # Add arrowhead to indicate direction
                    cr.move_to(end_x, end_y)
                    cr.line_to(end_x - 4, end_y - 2)
                    cr.move_to(end_x, end_y)
                    cr.line_to(end_x - 4, end_y + 2)
                    cr.stroke()

        # Ensure the drawing is properly flushed
        cr.stroke_preserve()

class WeatherWidget(Gtk.Box):
    """Weather widget for toolbar showing current conditions and recommendations"""
    
    def __init__(self, weather_sync, animation_overlay, main_window=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.weather_sync = weather_sync
        self.animation_overlay = animation_overlay
        self.main_window = main_window  # Store reference to main window

        # Weather condition button
        self.weather_label = Gtk.Label()
        self.weather_button = Gtk.Button()
        self.weather_button.set_child(self.weather_label)
        self.weather_button.set_tooltip_text("Set weather-based wallpaper")
        self.weather_button.connect('clicked', self.on_weather_clicked)

        # Animation toggle button
        self.animation_button = Gtk.Button()
        self.animation_button.set_icon_name("media-playback-start-symbolic")
        self.animation_button.set_tooltip_text("Show animated weather overlay (Asteroid-style)")
        self.animation_button.connect('clicked', self.on_animation_clicked)

        self.append(self.weather_button)
        self.append(self.animation_button)
        self.update_weather_display()
    
    def update_weather_display(self):
        """Update weather display"""
        weather_info = self.weather_sync.get_weather_description()
        self.weather_label.set_text(f"{weather_info['emoji']} {weather_info['time_period'].title()}")
        
        tooltip = f"{weather_info['description']}\nRecommended: {', '.join(weather_info['recommended_keywords'][:3])}\nClick to set matching wallpaper"
        self.weather_button.set_tooltip_text(tooltip)
        
        # Update animation button state
        if self.animation_overlay.animation_enabled:
            self.animation_button.set_icon_name("media-playback-start-symbolic")
            self.animation_button.set_tooltip_text(f"Show {weather_info['time_period']} animation overlay")
        else:
            self.animation_button.set_icon_name("media-playback-pause-symbolic")
            self.animation_button.set_tooltip_text("Weather animations disabled")
    
    def on_weather_clicked(self, button):
        """Handle weather button click - show weather-based wallpaper suggestions"""
        # This will be connected to the main app's weather wallpaper function
        pass
    
    def on_animation_clicked(self, button):
        """Handle animation button click - show weather overlay"""
        print("🎮 Weather animation play button clicked!")

        # Get weather info before triggering animation
        weather_info = self.weather_sync.get_weather_description()
        print(f"🎮 Current weather condition: {weather_info['condition']}")
        print(f"🎮 Current time period: {weather_info['time_period']}")
        print(f"🎮 Recommended keywords: {weather_info['recommended_keywords']}")
        print(f"🎮 Full weather info: {weather_info}")

        # Call the main app's animation function if we have a reference to main window
        if self.main_window:
            print("🎮 Main window reference available, calling show_weather_overlay...")
            try:
                self.animation_overlay.show_weather_overlay(self.main_window, duration=15)
                print(f"🎮 Weather animation triggered from WeatherWidget for {weather_info['time_period']} at {time.strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"🎮 Error showing weather overlay: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("🎮 No main window reference available, using fallback")
            # Fallback: try to call without main window (may not work properly in all cases)
            try:
                self.animation_overlay.show_weather_overlay(None, duration=15)
                print(f"🎮 Weather animation triggered with fallback method for {weather_info['time_period']} at {time.strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"🎮 Error showing weather overlay with fallback: {e}")
                import traceback
                traceback.print_exc()

class PhotoEffects:
    """Photo effects and filters processor"""
    
    EFFECTS = {
        'none': 'Original',
        'blur': 'Blur',
        'blur_heavy': 'Heavy Blur',
        'sharpen': 'Sharpen',
        'brightness_up': 'Brightness+',
        'brightness_down': 'Brightness-',
        'contrast_up': 'Contrast+',
        'contrast_down': 'Contrast-',
        'saturation_up': 'Saturation+',
        'saturation_down': 'Saturation-',
        'warmth': 'Warm Tone',
        'cool': 'Cool Tone',
        'sepia': 'Sepia',
        'grayscale': 'Grayscale',
        'vintage': 'Vintage',
        'retro': 'Retro',
        'dramatic': 'Dramatic',
        'cinematic': 'Cinematic',
        'soft': 'Soft Focus',
        'vivid': 'Vivid Colors',
        'pastel': 'Pastel',
        'neon': 'Neon Glow',
        'monochrome_blue': 'Blue Tint',
        'monochrome_red': 'Red Tint',
        'monochrome_green': 'Green Tint',
        'high_contrast': 'High Contrast',
        'invert': 'Invert Colors',
        'cyberpunk': 'Cyberpunk',
        'dreamy': 'Dreamy'
    }
    
    @staticmethod
    def apply_effect(image_path: Path, effect: str, temp_dir: Path) -> Optional[Path]:
        """Apply photo effect to image and return temp file path"""
        if not PIL_AVAILABLE or effect == 'none':
            return image_path

        try:
            # Open image
            img = Image.open(image_path)

            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Apply effects
            if effect == 'blur':
                img = img.filter(ImageFilter.GaussianBlur(radius=2))
            elif effect == 'blur_heavy':
                img = img.filter(ImageFilter.GaussianBlur(radius=5))
            elif effect == 'sharpen':
                img = img.filter(ImageFilter.SHARPEN)
            elif effect == 'brightness_up':
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(1.3)
            elif effect == 'brightness_down':
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(0.7)
            elif effect == 'contrast_up':
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)
            elif effect == 'contrast_down':
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(0.5)
            elif effect == 'saturation_up':
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(1.5)
            elif effect == 'saturation_down':
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(0.5)
            elif effect == 'warmth':
                # Warm tone - boost reds and reduce blues
                r, g, b = img.split()
                r = r.point(lambda x: min(255, int(x * 1.1)))
                b = b.point(lambda x: int(x * 0.9))
                img = Image.merge('RGB', (r, g, b))
            elif effect == 'cool':
                # Cool tone - boost blues and reduce reds
                r, g, b = img.split()
                r = r.point(lambda x: int(x * 0.9))
                b = b.point(lambda x: min(255, int(x * 1.1)))
                img = Image.merge('RGB', (r, g, b))
            elif effect == 'sepia':
                # Fast sepia using PIL only - much faster than numpy approach
                # Convert to grayscale first, then apply sepia tint
                grayscale = img.convert('L')
                # Create sepia-tinted version by combining with brown overlay
                img = Image.merge('RGB', (
                    grayscale.point(lambda x: min(255, int(x * 1.0))),     # Red channel
                    grayscale.point(lambda x: min(255, int(x * 0.85))),    # Green channel
                    grayscale.point(lambda x: min(255, int(x * 0.65)))     # Blue channel
                ))
            elif effect == 'grayscale':
                img = img.convert('L').convert('RGB')
            elif effect == 'vintage':
                # Optimized vintage effect using PIL enhancers only
                # Apply contrast boost
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.2)

                # Reduce saturation for vintage look
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(0.7)

                # Add slight warm tone
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(1.05)

                # Add slight sepia tone using color balance (faster approximation)
                try:
                    import numpy as np
                    img_array = np.array(img).astype(np.float32)
                    # Apply subtle sepia transformation (lighter than full sepia)
                    img_array[:, :, 0] = np.clip(img_array[:, :, 0] * 1.1, 0, 255)  # Boost red
                    img_array[:, :, 1] = np.clip(img_array[:, :, 1] * 1.05, 0, 255)  # Slight green boost
                    img_array[:, :, 2] = np.clip(img_array[:, :, 2] * 0.9, 0, 255)   # Reduce blue
                    img = Image.fromarray(img_array.astype(np.uint8))
                except ImportError:
                    # If numpy not available, just use the contrast and saturation changes
                    pass
            elif effect == 'dramatic':
                # High contrast with boosted saturation
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.8)
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(1.3)
            elif effect == 'soft':
                # Soft focus with slight blur and brightness
                img = img.filter(ImageFilter.GaussianBlur(radius=1))
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(1.1)
            elif effect == 'vivid':
                # Vivid colors - boost saturation and contrast
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(1.6)
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.2)
            elif effect == 'monochrome_blue':
                # Blue tinted monochrome
                grayscale = img.convert('L')
                img = Image.merge('RGB', (
                    grayscale.point(lambda x: int(x * 0.8)),    # Red channel
                    grayscale.point(lambda x: int(x * 0.9)),    # Green channel
                    grayscale.point(lambda x: min(255, int(x * 1.2)))  # Blue channel
                ))
            elif effect == 'monochrome_red':
                # Red tinted monochrome
                grayscale = img.convert('L')
                img = Image.merge('RGB', (
                    grayscale.point(lambda x: min(255, int(x * 1.2))),  # Red channel
                    grayscale.point(lambda x: int(x * 0.8)),    # Green channel
                    grayscale.point(lambda x: int(x * 0.7))     # Blue channel
                ))
            elif effect == 'high_contrast':
                # Extreme contrast
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)
            elif effect == 'retro':
                # Retro effect with reduced saturation and contrast
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(0.8)
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.3)
                # Add yellow/orange tint
                r, g, b = img.split()
                r = r.point(lambda x: min(255, int(x * 1.05)))
                g = g.point(lambda x: min(255, int(x * 1.02)))
                b = b.point(lambda x: int(x * 0.85))
                img = Image.merge('RGB', (r, g, b))
            elif effect == 'cinematic':
                # Cinematic effect with letterbox feel
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.4)
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(1.2)
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(0.9)
            elif effect == 'pastel':
                # Pastel colors - soft and light
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(0.6)
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(1.2)
            elif effect == 'neon':
                # Neon glow effect
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(2.0)
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(1.1)
            elif effect == 'monochrome_green':
                # Green tinted monochrome
                grayscale = img.convert('L')
                img = Image.merge('RGB', (
                    grayscale.point(lambda x: int(x * 0.7)),
                    grayscale.point(lambda x: min(255, int(x * 1.2))),
                    grayscale.point(lambda x: int(x * 0.8))
                ))
            elif effect == 'invert':
                # Invert colors
                from PIL import ImageOps
                img = ImageOps.invert(img)
            elif effect == 'cyberpunk':
                # Cyberpunk style - high contrast with blue/purple tint
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.6)
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(1.4)
                # Apply blue/purple tint
                r, g, b = img.split()
                r = r.point(lambda x: int(x * 0.9))
                g = g.point(lambda x: int(x * 0.95))
                b = b.point(lambda x: min(255, int(x * 1.15)))
                img = Image.merge('RGB', (r, g, b))
            elif effect == 'dreamy':
                # Dreamy effect - soft with warm tone
                img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(1.15)
                # Add slight warm tone
                r, g, b = img.split()
                r = r.point(lambda x: min(255, int(x * 1.05)))
                b = b.point(lambda x: int(x * 0.95))
                img = Image.merge('RGB', (r, g, b))

            # Save to temp file
            temp_path = temp_dir / f"effect_{effect}_{image_path.name}"
            img.save(temp_path, quality=95)
            return temp_path

        except Exception as e:
            print(f"Error applying effect {effect}: {e}")
            return image_path


class HighResImageHandler:
    """Handles high resolution images with optimized loading and processing"""
    
    MAX_PREVIEW_SIZE = (400, 400)
    MAX_THUMBNAIL_SIZE = (200, 200)
    
    @staticmethod
    def is_high_res(image_path: Path) -> bool:
        """Check if image is high resolution"""
        try:
            if PIL_AVAILABLE:
                with Image.open(image_path) as img:
                    width, height = img.size
                    return width > 2560 or height > 1440
            else:
                # Fallback: check file size
                return image_path.stat().st_size > 5 * 1024 * 1024  # 5MB
        except Exception:
            return False
    
    @staticmethod
    def create_optimized_preview(image_path: Path, cache_dir: Path) -> Optional[Path]:
        """Create optimized preview for high-res images"""
        if not PIL_AVAILABLE:
            return image_path
        
        try:
            preview_path = cache_dir / f"preview_{image_path.stem}.jpg"
            
            if preview_path.exists():
                return preview_path
            
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calculate new size maintaining aspect ratio
                img.thumbnail(HighResImageHandler.MAX_PREVIEW_SIZE, Image.Resampling.LANCZOS)
                
                # Save optimized preview
                img.save(preview_path, 'JPEG', quality=85, optimize=True)
                return preview_path
        except Exception as e:
            print(f"Error creating preview for {image_path}: {e}")
            return image_path
    
    @staticmethod
    def get_image_info(image_path: Path) -> Dict:
        """Get detailed image information"""
        try:
            if PIL_AVAILABLE:
                with Image.open(image_path) as img:
                    return {
                        'width': img.width,
                        'height': img.height,
                        'format': img.format,
                        'mode': img.mode,
                        'size_mb': image_path.stat().st_size / (1024 * 1024)
                    }
            else:
                # Fallback info
                return {
                    'width': 0,
                    'height': 0,
                    'format': 'Unknown',
                    'mode': 'Unknown',
                    'size_mb': image_path.stat().st_size / (1024 * 1024)
                }
        except Exception:
            return {'width': 0, 'height': 0, 'format': 'Unknown', 'mode': 'Unknown', 'size_mb': 0}

class NotificationManager:
    """Manages integration with Wayland notification daemons"""
    
    SUPPORTED_DAEMONS = {
        'mako': {
            'name': 'mako',
            'process': 'mako',
            'config_file': '~/.config/mako/config',
            'reload_command': ['makoctl', 'reload'],
            'color_format': 'hex'
        },
        'dunst': {
            'name': 'dunst', 
            'process': 'dunst',
            'config_file': '~/.config/dunst/dunstrc',
            'reload_command': ['killall', '-SIGUSR2', 'dunst'],
            'color_format': 'hex'
        },
        'swaync': {
            'name': 'SwayNotificationCenter',
            'process': 'swaync',
            'config_file': '~/.config/swaync/config.json',
            'reload_command': ['swaync-client', '--reload-config'],
            'color_format': 'hex'
        }
    }
    
    @staticmethod
    def detect_notification_daemon() -> Optional[str]:
        """Detect the currently running notification daemon"""
        try:
            result = subprocess.run(['pgrep', '-l', '-u', str(os.getuid())], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                processes = result.stdout.lower()
                for daemon_id, info in NotificationManager.SUPPORTED_DAEMONS.items():
                    if info['process'].lower() in processes:
                        try:
                            test_result = subprocess.run(info['reload_command'], 
                                                       capture_output=True, timeout=2)
                            if test_result.returncode == 0:
                                return daemon_id
                        except Exception:
                            return daemon_id
                            
        except Exception as e:
            print(f"Error detecting notification daemon: {e}")
        
        return None
    
    @staticmethod
    def update_mako_colors(colors: Dict[str, str]) -> bool:
        """Update mako configuration with new colors"""
        try:
            config_path = Path.home() / '.config' / 'mako' / 'config'
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            existing_config = ""
            if config_path.exists():
                existing_config = config_path.read_text()
            
            config_lines = []
            color_keys = {'background-color', 'text-color', 'border-color', 'progress-color'}
            
            for line in existing_config.split('\n'):
                line = line.strip()
                if not any(line.startswith(key + '=') for key in color_keys):
                    config_lines.append(line)
            
            config_lines.extend([
                f"background-color={colors.get('background', '#2e2e2e')}",
                f"text-color={colors.get('text', '#ffffff')}",
                f"border-color={colors.get('border', '#6366f1')}",
                f"progress-color={colors.get('progress', '#6366f1')}",
            ])
            
            config_content = '\n'.join(line for line in config_lines if line.strip())
            config_path.write_text(config_content)
            
            subprocess.run(['makoctl', 'reload'], capture_output=True)
            return True
            
        except Exception as e:
            print(f"Error updating mako colors: {e}")
            return False

class CompositorDetector:
    """Detects and provides configuration for different Wayland compositors"""
    
    SUPPORTED_COMPOSITORS = {
        'hyprland': {'name': 'Hyprland', 'process': 'Hyprland'},
        'niri': {'name': 'niri', 'process': 'niri'},
        'sway': {'name': 'Sway', 'process': 'sway'},
        'river': {'name': 'River', 'process': 'river'},
        'wayfire': {'name': 'Wayfire', 'process': 'wayfire'}
    }
    
    @staticmethod
    def detect_compositor() -> Optional[str]:
        """Detect the currently running Wayland compositor"""
        try:
            if os.environ.get('XDG_CURRENT_DESKTOP'):
                desktop = os.environ['XDG_CURRENT_DESKTOP'].lower()
                if 'hyprland' in desktop:
                    return 'hyprland'
                elif 'niri' in desktop:
                    return 'niri'
            
            result = subprocess.run(['pgrep', '-l', '-u', str(os.getuid())], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                processes = result.stdout.lower()
                for compositor_id, info in CompositorDetector.SUPPORTED_COMPOSITORS.items():
                    if info['process'].lower() in processes:
                        return compositor_id
                
        except Exception as e:
            print(f"Error detecting compositor: {e}")
        
        return None

class MonitorManager:
    """Advanced monitor detection and configuration management"""
    
    def __init__(self, compositor: Optional[str] = None):
        self.compositor = compositor
        self.monitors = {}
        self.refresh_monitors()
    
    def refresh_monitors(self) -> Dict[str, Dict]:
        """Detect all available monitors and their capabilities"""
        self.monitors = {}
        
        if self.compositor == 'hyprland':
            self.monitors = self._detect_hyprland_monitors()
        elif self.compositor == 'niri':
            self.monitors = self._detect_niri_monitors()
        else:
            # Fallback to generic detection
            self.monitors = self._detect_generic_monitors()
        
        return self.monitors
    
    def _detect_hyprland_monitors(self) -> Dict[str, Dict]:
        """Detect Hyprland monitors with detailed capabilities"""
        monitors = {}
        try:
            # Get active monitors
            result = subprocess.run(['hyprctl', 'monitors', '-j'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                monitor_data = json.loads(result.stdout)
                for monitor in monitor_data:
                    monitors[monitor['name']] = {
                        'active': True,
                        'width': monitor['width'],
                        'height': monitor['height'],
                        'refresh': monitor['refreshRate'],
                        'scale': monitor['scale'],
                        'x': monitor['x'],
                        'y': monitor['y']
                    }
        except Exception as e:
            print(f"Error detecting Hyprland monitors: {e}")
        
        return monitors
    
    def _detect_niri_monitors(self) -> Dict[str, Dict]:
        """Detect niri monitors with detailed capabilities"""
        monitors = {}
        try:
            # Get active monitors with detailed info
            result = subprocess.run(['niri', 'msg', 'outputs'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                # Parse niri output format
                current_monitor = None
                current_monitor_id = None
                
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    
                    # Monitor header: Output "Monitor Name" (ID)
                    if line.startswith('Output "') and '(' in line and ')' in line:
                        # Extract monitor name and ID
                        parts = line.split('"')
                        if len(parts) >= 3:
                            monitor_name = parts[1]
                            id_part = line.split('(')[1].split(')')[0]
                            current_monitor = monitor_name
                            current_monitor_id = id_part
                            monitors[current_monitor_id] = {
                                'name': monitor_name,
                                'active': True,
                                'width': 1920,  # Will be updated when we parse mode
                                'height': 1080,
                                'refresh': 60.0,
                                'scale': 1.0,
                                'x': 0,
                                'y': 0
                            }
                    
                    # Current mode line
                    elif 'Current mode:' in line and current_monitor_id:
                        try:
                            # Extract resolution and refresh rate: "3440x1440 @ 100.000 Hz"
                            mode_part = line.split('Current mode:')[1].strip()
                            if 'x' in mode_part and '@' in mode_part:
                                res_part = mode_part.split('@')[0].strip()
                                refresh_part = mode_part.split('@')[1].strip().replace('Hz', '').strip()
                                
                                # Handle "100.000 (preferred)" format by taking only the number part
                                if ' ' in refresh_part:
                                    refresh_part = refresh_part.split()[0]
                                
                                if 'x' in res_part:
                                    width, height = res_part.split('x')
                                    monitors[current_monitor_id]['width'] = int(width)
                                    monitors[current_monitor_id]['height'] = int(height)
                                    monitors[current_monitor_id]['refresh'] = float(refresh_part)
                        except Exception as parse_error:
                            print(f"Error parsing mode for {current_monitor}: {parse_error}")
                    
                    # Scale line
                    elif 'Scale:' in line and current_monitor_id:
                        try:
                            scale_str = line.split('Scale:')[1].strip()
                            monitors[current_monitor_id]['scale'] = float(scale_str)
                        except Exception as parse_error:
                            print(f"Error parsing scale for {current_monitor}: {parse_error}")
                    
                    # Logical position line
                    elif 'Logical position:' in line and current_monitor_id:
                        try:
                            pos_part = line.split('Logical position:')[1].strip()
                            if ',' in pos_part:
                                x_str, y_str = pos_part.split(',')
                                monitors[current_monitor_id]['x'] = int(x_str.strip())
                                monitors[current_monitor_id]['y'] = int(y_str.strip())
                        except Exception as parse_error:
                            print(f"Error parsing position for {current_monitor}: {parse_error}")
                            
        except Exception as e:
            print(f"Error detecting niri monitors: {e}")
        
        return monitors
    
    def _detect_generic_monitors(self) -> Dict[str, Dict]:
        """Generic monitor detection using wlr-randr or similar"""
        monitors = {}
        try:
            # Try wlr-randr
            result = subprocess.run(['wlr-randr'], capture_output=True, text=True)
            if result.returncode == 0:
                current_monitor = None
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and not line.startswith(' '):
                        # Monitor name line
                        current_monitor = line.split()[0]
                        monitors[current_monitor] = {
                            'active': False,
                            'width': 1920,
                            'height': 1080,
                            'refresh': 60.0,
                            'scale': 1.0,
                            'x': 0,
                            'y': 0
                        }
                    elif current_monitor and 'current' in line:
                        # Current mode line
                        monitors[current_monitor]['active'] = True
                        # Parse resolution and refresh rate
                        parts = line.split()
                        for part in parts:
                            if 'x' in part and '@' in part:
                                res_part, refresh_part = part.split('@')
                                width, height = res_part.split('x')
                                monitors[current_monitor]['width'] = int(width)
                                monitors[current_monitor]['height'] = int(height)
                                monitors[current_monitor]['refresh'] = float(refresh_part.replace('Hz', ''))
        except Exception as e:
            print(f"Error with generic monitor detection: {e}")
            # Fallback to single monitor
            monitors['Unknown'] = {
                'active': True,
                'width': 1920,
                'height': 1080,
                'refresh': 60.0,
                'scale': 1.0,
                'x': 0,
                'y': 0
            }
        
        return monitors
    
    def get_active_monitors(self) -> List[str]:
        """Get list of active monitor names"""
        return [name for name, info in self.monitors.items() if info.get('active', False)]
    
    def get_monitor_info(self, monitor_name: str) -> Optional[Dict]:
        """Get detailed info for a specific monitor"""
        return self.monitors.get(monitor_name)
    
    def set_monitor_resolution(self, monitor: str, width: int, height: int, refresh: float = 60.0) -> bool:
        """Set monitor resolution"""
        try:
            if self.compositor == 'hyprland':
                cmd = ['hyprctl', 'keyword', 'monitor', f'{monitor},{width}x{height}@{refresh},0x0,1']
                result = subprocess.run(cmd, capture_output=True, text=True)
                return result.returncode == 0
            elif self.compositor == 'niri':
                # niri doesn't support dynamic resolution changes
                print("niri doesn't support dynamic resolution changes")
                return False
            else:
                # Try wlr-randr
                cmd = ['wlr-randr', '--output', monitor, '--mode', f'{width}x{height}@{refresh}Hz']
                result = subprocess.run(cmd, capture_output=True, text=True)
                return result.returncode == 0
        except Exception as e:
            print(f"Error setting monitor resolution: {e}")
            return False
    
    def set_monitor_scale(self, monitor: str, scale: float) -> bool:
        """Set monitor scaling"""
        try:
            if self.compositor == 'hyprland':
                cmd = ['hyprctl', 'keyword', 'monitor', f'{monitor},preferred,auto,{scale}']
                result = subprocess.run(cmd, capture_output=True, text=True)
                return result.returncode == 0
            elif self.compositor == 'niri':
                # niri doesn't support dynamic scaling changes
                print("niri doesn't support dynamic scaling changes")
                return False
            else:
                # Try wlr-randr
                cmd = ['wlr-randr', '--output', monitor, '--scale', str(scale)]
                result = subprocess.run(cmd, capture_output=True, text=True)
                return result.returncode == 0
        except Exception as e:
            print(f"Error setting monitor scale: {e}")
            return False
    
    def get_focused_monitor(self) -> Optional[str]:
        """Get the currently focused/active monitor"""
        try:
            if self.compositor == 'niri':
                return self._get_niri_focused_monitor()
            elif self.compositor == 'hyprland':
                return self._get_hyprland_focused_monitor()
            elif self.compositor == 'sway':
                return self._get_sway_focused_monitor()
            else:
                # Fallback: return first active monitor
                active_monitors = self.get_active_monitors()
                return active_monitors[0] if active_monitors else None
        except Exception as e:
            print(f"Error getting focused monitor: {e}")
            return None
    
    def _get_niri_focused_monitor(self) -> Optional[str]:
        """Get focused monitor in niri by checking focused workspace/window"""
        try:
            # Method 1: Try to get focused window and its workspace ID, then map to monitor
            focused_window_result = subprocess.run(['niri', 'msg', 'focused-window'], 
                                                 capture_output=True, text=True)
            
            focused_workspace_id = None
            if focused_window_result.returncode == 0 and focused_window_result.stdout.strip():
                # Parse the focused window output to get workspace ID
                lines = focused_window_result.stdout.split('\n')
                for line in lines:
                    if 'Workspace ID:' in line:
                        try:
                            focused_workspace_id = int(line.split('Workspace ID:')[1].strip())
                            break
                        except:
                            continue
            
            # Method 2: Get workspace info and find which monitor has the focused workspace
            workspaces_result = subprocess.run(['niri', 'msg', 'workspaces'], 
                                              capture_output=True, text=True)
            
            if workspaces_result.returncode == 0:
                lines = workspaces_result.stdout.split('\n')
                current_output = None
                
                for line in lines:
                    line = line.strip()
                    
                    # Check for output line (e.g., 'Output "HDMI-A-1":')
                    if line.startswith('Output "') and line.endswith('":'):
                        # Extract output name from quotes
                        start = line.find('"') + 1
                        end = line.rfind('"')
                        if start > 0 and end > start:
                            current_output = line[start:end]
                    
                    # Check for workspace with focus indicator
                    elif current_output and line:
                        # Look for the focused workspace (marked with *)
                        if line.startswith('* '):
                            workspace_num = line[2:].strip()
                            try:
                                workspace_id = int(workspace_num)
                                # If we have a focused workspace ID from window, match it
                                if focused_workspace_id and workspace_id == focused_workspace_id:
                                    print(f"🎯 Detected focused monitor: {current_output} (workspace {workspace_id})")
                                    return current_output
                                # Otherwise, just return the first monitor with a focused workspace
                                elif not focused_workspace_id:
                                    print(f"🎯 Detected focused monitor: {current_output} (active workspace {workspace_id})")
                                    return current_output
                            except ValueError:
                                continue
            
            # Method 3: Fallback - use cursor position or other heuristics
            print("🎯 Using fallback monitor detection")
            active_monitors = self.get_active_monitors()
            if active_monitors:
                # Just return the first monitor as fallback
                fallback_monitor = active_monitors[0]
                print(f"🎯 Fallback to first monitor: {fallback_monitor}")
                return fallback_monitor
                    
        except Exception as e:
            print(f"Error getting niri focused monitor: {e}")
        
        return None
    
    def _get_hyprland_focused_monitor(self) -> Optional[str]:
        """Get focused monitor in Hyprland"""
        try:
            result = subprocess.run(['hyprctl', 'monitors', '-j'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                monitors_data = json.loads(result.stdout)
                for monitor in monitors_data:
                    if monitor.get('focused', False):
                        return monitor['name']
        except Exception as e:
            print(f"Error getting hyprland focused monitor: {e}")
        return None
    
    def _get_sway_focused_monitor(self) -> Optional[str]:
        """Get focused monitor in Sway"""
        try:
            result = subprocess.run(['swaymsg', '-t', 'get_outputs'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                outputs_data = json.loads(result.stdout)
                for output in outputs_data:
                    if output.get('focused', False) or output.get('active', False):
                        return output['name']
        except Exception as e:
            print(f"Error getting sway focused monitor: {e}")
        return None

class WallpaperConfig:
    """Enhanced configuration for wallpaper paths and settings"""
    def __init__(self):
        self.home = Path.home()
        self.wallpaper_dir = self.home / "Pictures" / "Wallpapers"
        self.cache_dir = self.home / ".cache" / "wall-it"
        self.temp_dir = self.cache_dir / "temp"
        self.current_wallpaper = self.home / ".current-wallpaper"
        
        # Create directories if they don't exist
        self.wallpaper_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Enhanced config files
        self.matugen_state_file = self.cache_dir / "matugen_enabled"
        self.matugen_scheme_file = self.cache_dir / "matugen_scheme"
        self.notification_preference_file = self.cache_dir / "notification_preference"
        self.auto_change_enabled_file = self.cache_dir / "auto_change_enabled"
        self.auto_change_interval_file = self.cache_dir / "auto_change_interval"
        self.wallpaper_scaling_file = self.cache_dir / "wallpaper_scaling"
        self.monitor_config_enabled_file = self.cache_dir / "monitor_config_enabled"
        self.keybinds_enabled_file = self.cache_dir / "keybinds_enabled"
        self.keybinds_config_file = self.cache_dir / "keybinds_config.json"
        self.transition_effect_file = self.cache_dir / "transition_effect"
        self.current_effect_file = self.cache_dir / "current_effect"
        self.system_tray_enabled_file = self.cache_dir / "system_tray_enabled"
        
        # Per-monitor state tracking
        self.monitor_wallpapers_file = self.cache_dir / "monitor_wallpapers.json"
        self.keybind_mode_file = self.cache_dir / "keybind_mode"  # 'all' or 'active'
        
        # Enhanced image format support for high-res images
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', '.avif', '.heic', '.heif'}
        
        # Matugen color schemes (matching available schemes on system)
        self.matugen_schemes = {
            'scheme-content': 'Content',
            'scheme-expressive': 'Expressive',
            'scheme-fidelity': 'Fidelity',
            'scheme-fruit-salad': 'Fruit Salad',
            'scheme-monochrome': 'Monochrome',
            'scheme-neutral': 'Neutral',
            'scheme-rainbow': 'Rainbow',
            'scheme-tonal-spot': 'Tonal Spot'
        }

class ThumbnailManager:
    """Enhanced thumbnail manager with high-res support"""
    def __init__(self, config: WallpaperConfig):
        self.config = config
        self.cache_dir = config.cache_dir / "thumbnails"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_path(self, image_path: Path) -> Path:
        """Get cache path for thumbnail"""
        # Use PNG to support transparency (avoids RGBA->JPEG errors)
        return self.cache_dir / f"{hashlib.md5(str(image_path).encode()).hexdigest()}.png"
    
    def create_thumbnail(self, image_path: Path, size: Tuple[int, int] = (150, 150)) -> Optional[GdkPixbuf.Pixbuf]:
        """Create thumbnail with high-res support"""
        # Validate image file first
        try:
            if not image_path.exists():
                print(f"Error: Image file does not exist: {image_path}")
                return None
            if image_path.stat().st_size == 0:
                print(f"Error: Empty image file: {image_path}")
                return None
        except Exception as e:
            print(f"Error validating image file {image_path}: {e}")
            return None

        cache_path = self.get_cache_path(image_path)
        
        # Check if cached thumbnail exists and is newer than source
        if cache_path.exists():
            try:
                cache_mtime = cache_path.stat().st_mtime
                source_mtime = image_path.stat().st_mtime
                if cache_mtime >= source_mtime:
                    return GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        str(cache_path), size[0], size[1], True)
            except Exception:
                pass
        
        # Create new thumbnail
        try:
            # Disable high-res processing for debugging - use original image directly
            source_path = image_path
            
            # Create thumbnail
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(source_path), size[0], size[1], True)
            
            # Save to cache as PNG to support images with alpha channel
            pixbuf.savev(str(cache_path), "png", [], [])
            
            return pixbuf
            
        except Exception as e:
            print(f"Error creating thumbnail for {image_path}: {e}")
            return None

class WallpaperTimer:
    """Timer for automatic wallpaper changing"""
    
    def __init__(self, app):
        self.app = app
        self.timer_id = None
        self.running = False
        self.interval = 300  # 5 minutes default
    
    def start(self, interval_seconds: int):
        """Start the timer"""
        self.stop()  # Stop any existing timer
        self.interval = interval_seconds
        self.running = True
        self.timer_id = GLib.timeout_add_seconds(interval_seconds, self._on_timer)
        print(f"✅ Auto-change timer started: {interval_seconds // 60} minutes")
    
    def stop(self):
        """Stop the timer"""
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None
        self.running = False
        print("🛑 Auto-change timer stopped")
    
    def _on_timer(self):
        """Timer callback"""
        if not self.running:
            return False
        
        try:
            # Change to random wallpaper
            if self.app.grid_view.wallpapers:
                random_wallpaper = random.choice(self.app.grid_view.wallpapers)
                current_effect = self.app.wallpaper_setter.get_current_effect()
                print(f"⏰ Auto-changing to: {random_wallpaper.name}")
                GLib.idle_add(self.app.set_wallpaper_with_effect, random_wallpaper, current_effect)
        except Exception as e:
            print(f"Error in auto-change timer: {e}")
        
        return self.running  # Continue timer if still running

def _import_backend_manager():
    """Import the backend manager dynamically"""
    try:
        backend_path = Path(__file__).parent / "wall-it-backend-manager.py"
        spec = importlib.util.spec_from_file_location("backend_manager", backend_path)
        backend_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend_module)
        return backend_module.BackendManager()
    except Exception as e:
        print(f"Warning: Could not load backend manager: {e}")
        return None

class WallpaperSetter:
    """Enhanced wallpaper setter with effects and high-res support"""
    def __init__(self, config: WallpaperConfig):
        self.config = config
        self.state_file = config.cache_dir / "current_index"
        self.current_effect = 'none'  # Default to original images
        
        # Initialize backend manager
        self.backend_manager = _import_backend_manager()
    
    def _apply_fit_blur(self, image_path: Path) -> Path:
        """Apply fit-blur processing for ultrawide monitors."""
        try:
            # Import image processor
            processor_path = Path(__file__).parent / "wall-it-image-processor.py"
            spec = importlib.util.spec_from_file_location("image_processor", processor_path)
            processor_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(processor_module)
            
            # Process image
            output_dir = self.config.cache_dir / "fit-blur"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate cache filename
            input_hash = str(hash(str(image_path)))[-8:]
            output_path = output_dir / f"{image_path.stem}_fitblur_{input_hash}.jpg"
            
            # Check cache
            if output_path.exists() and output_path.stat().st_mtime >= image_path.stat().st_mtime:
                return output_path
            
            # Process with fit-blur
            result = processor_module.create_fit_blur_wallpaper(image_path, output_path)
            print(f"Wall-IT: Applied fit-blur processing for ultrawide")
            return result
            
        except Exception as e:
            print(f"Warning: Could not apply fit-blur: {e}")
            return image_path
    
    def set_wallpaper(self, image_path: Path, monitor: str = None, transition: str = "fade", effect: str = 'none') -> bool:
        """Set wallpaper with effects and transitions"""
        try:
            # Rate limiting: check if we're changing too fast
            current_time = time.time()
            if hasattr(self, '_last_change_time'):
                time_since_last = current_time - self._last_change_time
                if time_since_last < 1.0:  # Less than 1000ms since last change
                    time.sleep(1.0 - time_since_last)  # Wait until 1000ms have passed
            self._last_change_time = current_time
            # Get current effect before any processing
            current_effect = self.get_current_effect()
            effect_changing = (effect != current_effect)
            
            # Clean up effect files when changing effects
            if effect_changing:
                self._aggressive_effect_cleanup()
            
            # Clean up any remaining old temporary effect files
            self._cleanup_temp_files()
            
            # Apply photo effect
            processed_path = image_path
            if effect != 'none' and PIL_AVAILABLE:
                processed_path = PhotoEffects.apply_effect(image_path, effect, self.config.temp_dir)
                if processed_path:
                    self.set_current_effect(effect)
                else:
                    # If effect processing fails, fall back to original
                    processed_path = image_path
                    self.set_current_effect('none')
            else:
                # Use original image for 'none' effect or if PIL not available
                processed_path = image_path
                self.set_current_effect(effect)
            
            # Get wallpaper scaling mode
            scaling = self.get_wallpaper_scaling()
            
            # Apply fit-blur processing if needed
            if scaling == 'fit-blur':
                processed_path = self._apply_fit_blur(processed_path)
                scaling = 'crop'  # Use crop mode since image is already sized to screen
            
            # Use backend manager to set wallpaper if available
            if self.backend_manager and self.backend_manager.is_available():
                # Handle transitions based on backend support
                if not self.backend_manager.supports_transitions():
                    transition = 'none'  # KDE doesn't support transitions
                else:
                    # Safety check: never use 'none' or 'random' transitions as they can cause overlap issues
                    if transition == 'none':
                        transition = 'fade'  # Fall back to fade transition
                        print("⚠️ Prevented 'none' transition - using fade instead")
                    elif transition == 'random':
                        transition = 'fade'  # Random can pick 'none', so use fade instead
                        print("⚠️ Prevented 'random' transition - using fade instead")
                
                # Set wallpaper using backend manager
                success = self.backend_manager.set_wallpaper(processed_path, monitor, transition, scaling)
                
                if success:
                    # Update current wallpaper link (always use original image, not processed)
                    if self.config.current_wallpaper.exists() or self.config.current_wallpaper.is_symlink():
                        self.config.current_wallpaper.unlink()
                    self.config.current_wallpaper.symlink_to(image_path)
                    
                    # Track per-monitor wallpaper if monitor is specified
                    if monitor:
                        self.set_monitor_wallpaper(monitor, image_path)
                    else:
                        # If no monitor specified, update all monitors
                        monitors = self.backend_manager.get_monitors()
                        for monitor_info in monitors:
                            monitor_name = monitor_info.get('connector', monitor_info.get('name', ''))
                            if monitor_name:
                                self.set_monitor_wallpaper(monitor_name, image_path)
                    
                    # Update matugen colors if enabled - use original image for better colors
                    if self.is_matugen_enabled():
                        self.update_matugen_colors(image_path)
                    
                    self.update_current_index(image_path)
                    return True
                else:
                    print("Error: Backend manager failed to set wallpaper")
                    return False
            
            # Fallback: Use swww directly (for compatibility)
            # Ensure swww daemon is running
            try:
                # Test if daemon is responding
                test_result = subprocess.run(['swww', 'query'], capture_output=True, text=True, timeout=2)
                if test_result.returncode != 0:
                    # Start daemon if not running
                    subprocess.Popen(['swww-daemon'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1)  # Give daemon time to start
            except subprocess.TimeoutExpired:
                # Daemon might be stuck, restart it
                subprocess.run(['swww', 'kill'], capture_output=True, text=True)
                time.sleep(0.5)
                subprocess.Popen(['swww-daemon'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1)
            
            # Clear when switching effects on all monitors to avoid overlap
            if effect_changing and not monitor:
                try:
                    subprocess.run(['swww', 'clear'], capture_output=True, timeout=1)
                except:
                    pass
            
            # Set wallpaper using swww with proper effect and monitor handling
            cmd = ['swww', 'img']
            
            if monitor:
                cmd.extend(['--outputs', monitor])
            
            # Safety check: never use 'none' or 'random' transitions as they can cause overlap issues
            if transition == 'none':
                transition = 'fade'  # Fall back to fade transition
                print("⚠️ Prevented 'none' transition - using fade instead")
            elif transition == 'random':
                transition = 'fade'  # Random can pick 'none', so use fade instead
                print("⚠️ Prevented 'random' transition - using fade instead")
            
            # Adjust transition settings based on effect change type
            if effect_changing:
                # Use slower, more stable transition when changing effects
                cmd.extend([
                    '--transition-type', 'fade',  # Force fade for effect changes
                    '--transition-fps', '30',     # Lower FPS to reduce conflicts
                    '--transition-duration', '1.2', # Slower duration for stable effect changes
                    '--resize', scaling,
                    str(processed_path)
                ])
            else:
                # Use regular settings - differentiate by monitor
                if monitor:
                    # Individual monitor - stable transition
                    cmd.extend([
                        '--transition-type', transition,
                        '--transition-fps', '30',
                        '--transition-duration', '0.8',  # Slower for stability
                        '--resize', scaling,
                        str(processed_path)
                    ])
                else:
                    # All monitors - normal transition
                    cmd.extend([
                        '--transition-type', transition,
                        '--transition-fps', '30',
                        '--transition-duration', '1.5',
                        '--resize', scaling,
                        str(processed_path)
                    ])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Update current wallpaper link (always use original image, not processed)
                if self.config.current_wallpaper.exists() or self.config.current_wallpaper.is_symlink():
                    self.config.current_wallpaper.unlink()
                self.config.current_wallpaper.symlink_to(image_path)
                
                # Track per-monitor wallpaper if monitor is specified
                if monitor:
                    self.set_monitor_wallpaper(monitor, image_path)
                else:
                    # If no monitor specified, update all monitors
                    monitor_manager = MonitorManager(CompositorDetector.detect_compositor())
                    for monitor_id in monitor_manager.get_active_monitors():
                        self.set_monitor_wallpaper(monitor_id, image_path)
                
                # Update matugen colors if enabled - use original image for better colors
                if self.is_matugen_enabled():
                    self.update_matugen_colors(image_path)
                
                self.update_current_index(image_path)
                return True
            else:
                print(f"Error setting wallpaper: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error setting wallpaper: {e}")
            return False
    
    def _cleanup_temp_files(self):
        """Clean up old temporary effect files"""
        try:
            temp_dir = self.config.temp_dir
            if temp_dir.exists():
                current_time = time.time()
                for temp_file in temp_dir.glob('effect_*'):
                    try:
                        # Remove files older than 2 minutes (faster cleanup)
                        file_age = current_time - temp_file.stat().st_mtime
                        if file_age > 120:  # 2 minutes instead of 5
                            temp_file.unlink()
                            print(f"🗑️ Cleaned up old effect file: {temp_file.name}")
                    except Exception:
                        pass
        except Exception as e:
            print(f"Warning: Could not clean temp files: {e}")
    
    def _aggressive_effect_cleanup(self):
        """Aggressively clean up ALL effect files when changing effects"""
        try:
            temp_dir = self.config.temp_dir
            if temp_dir.exists():
                effect_files_removed = 0
                preview_files_removed = 0
                
                # Remove effect files
                for temp_file in temp_dir.glob('effect_*'):
                    try:
                        temp_file.unlink()
                        effect_files_removed += 1
                    except Exception:
                        pass
                
                # Also remove any preview files that might cause issues
                for temp_file in temp_dir.glob('preview_*'):
                    try:
                        temp_file.unlink()
                        preview_files_removed += 1
                    except Exception:
                        pass
                
                # Force sync filesystem to ensure files are actually removed
                import subprocess
                try:
                    subprocess.run(['sync'], timeout=1)
                except:
                    pass
                
                total_removed = effect_files_removed + preview_files_removed
                if total_removed > 0:
                    print(f"🧹 Cleaned up {total_removed} temp files for smooth transition")
        except Exception as e:
            print(f"Warning: Could not perform aggressive cleanup: {e}")
    
    def get_current_effect(self) -> str:
        """Get current photo effect"""
        try:
            if self.config.current_effect_file.exists():
                content = self.config.current_effect_file.read_text().strip()
                # Handle the cache format "monitor_scale|effect" or just "effect"
                if '|' in content:
                    parts = content.split('|')
                    if len(parts) >= 2:
                        return parts[1]  # Return the effect part
                return content
        except Exception:
            pass
        return 'none'  # Default to original images
    
    def set_current_effect(self, effect: str):
        """Set current photo effect"""
        try:
            # Read current content to preserve format if it exists
            current_content = None
            if self.config.current_effect_file.exists():
                current_content = self.config.current_effect_file.read_text().strip()
            
            # Preserve monitor scale part if format is "scale|effect"
            if current_content and '|' in current_content:
                parts = current_content.split('|')
                if len(parts) >= 2:
                    monitor_scale = parts[0]
                    new_content = f"{monitor_scale}|{effect}"
                else:
                    new_content = effect
            else:
                new_content = effect
            
            self.config.current_effect_file.write_text(new_content)
            self.current_effect = effect
        except Exception as e:
            print(f"Error saving current effect: {e}")
    
    def is_matugen_enabled(self) -> bool:
        """Check if matugen integration is enabled"""
        try:
            return self.config.matugen_state_file.read_text().strip().lower() == 'true'
        except:
            return False
    
    def set_matugen_enabled(self, enabled: bool):
        """Enable/disable matugen integration"""
        self.config.matugen_state_file.write_text('true' if enabled else 'false')
    
    def get_matugen_scheme(self) -> str:
        """Get current matugen color scheme"""
        try:
            scheme = self.config.matugen_scheme_file.read_text().strip()
            # Fix old scheme names to new format
            if scheme in ['content', 'expressive', 'fidelity', 'fruit-salad', 'monochrome', 'neutral', 'rainbow', 'tonal-spot']:
                scheme = f'scheme-{scheme}'
            return scheme
        except:
            return 'scheme-expressive'
    
    def set_matugen_scheme(self, scheme: str):
        """Set matugen color scheme"""
        self.config.matugen_scheme_file.write_text(scheme)
    
    def update_matugen_colors(self, image_path: Path) -> bool:
        """Update system colors using matugen - FIXED"""
        try:
            scheme = self.get_matugen_scheme()
            print(f"🎨 Updating colors with matugen for {image_path.name} using {scheme} scheme")
            
            # Run matugen with proper arguments for new version
            cmd = ['matugen', 'image', str(image_path), '-t', scheme, '--json', 'hex']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                try:
                    # Parse matugen JSON output
                    colors_data = json.loads(result.stdout)
                    
                    # Extract colors for notification daemon
                    if 'colors' in colors_data:
                        colors = colors_data['colors']
                        
                        # Map matugen colors to notification daemon format
                        notification_colors = {
                            'background': colors.get('primary', '#2e2e2e'),
                            'text': colors.get('on_primary', '#ffffff'), 
                            'border': colors.get('secondary', '#6366f1'),
                            'progress': colors.get('tertiary', '#6366f1')
                        }
                        
                        # Update notification daemon colors
                        daemon = NotificationManager.detect_notification_daemon()
                        if daemon == 'mako':
                            NotificationManager.update_mako_colors(notification_colors)
                            print(f"✅ Updated {daemon} colors")
                    
                    print("✅ Matugen colors updated successfully")
                    return True
                    
                except json.JSONDecodeError as e:
                    print(f"Error parsing matugen JSON: {e}")
                    # Fallback: just run matugen without JSON parsing
                    cmd_fallback = ['matugen', 'image', str(image_path), '-t', scheme]
                    fallback_result = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=30)
                    return fallback_result.returncode == 0
            else:
                print(f"Matugen error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("Matugen timed out")
            return False
        except Exception as e:
            print(f"Error updating matugen colors: {e}")
            return False
    
    def get_wallpaper_scaling(self) -> str:
        """Get wallpaper scaling mode"""
        try:
            content = self.config.wallpaper_scaling_file.read_text().strip()
            # Handle the cache format "monitor_scale|wallpaper_mode"
            if '|' in content:
                parts = content.split('|')
                if len(parts) >= 2:
                    return parts[1]  # Return the wallpaper scaling mode part
            return content
        except:
            return 'crop'
    
    def set_wallpaper_scaling(self, scaling: str):
        """Set wallpaper scaling mode"""
        try:
            # Read current content to preserve monitor scale if it exists
            current_content = self.config.wallpaper_scaling_file.read_text().strip()
            if '|' in current_content:
                parts = current_content.split('|')
                if len(parts) >= 2:
                    # Preserve monitor scale, update wallpaper mode
                    monitor_scale = parts[0]
                    new_content = f"{monitor_scale}|{scaling}"
                else:
                    new_content = scaling
            else:
                new_content = scaling
        except:
            new_content = scaling
        
        self.config.wallpaper_scaling_file.write_text(new_content)
    
    def get_transition_effect(self) -> str:
        """Get transition effect"""
        try:
            return self.config.transition_effect_file.read_text().strip()
        except:
            return 'fade'
    
    def set_transition_effect(self, effect: str):
        """Set transition effect"""
        self.config.transition_effect_file.write_text(effect)
    
    def is_auto_change_enabled(self) -> bool:
        """Check if auto-change timer is enabled"""
        try:
            return self.config.auto_change_enabled_file.read_text().strip().lower() == 'true'
        except:
            return False
    
    def set_auto_change_enabled(self, enabled: bool):
        """Enable/disable auto-change timer"""
        self.config.auto_change_enabled_file.write_text('true' if enabled else 'false')
    
    def get_auto_change_interval(self) -> int:
        """Get auto-change interval in seconds"""
        try:
            return int(self.config.auto_change_interval_file.read_text().strip())
        except:
            return 300  # 5 minutes default
    
    def set_auto_change_interval(self, seconds: int):
        """Set auto-change interval"""
        self.config.auto_change_interval_file.write_text(str(seconds))
    
    def is_monitor_config_enabled(self) -> bool:
        """Check if monitor configuration is enabled"""
        try:
            return self.config.monitor_config_enabled_file.read_text().strip().lower() == 'true'
        except:
            return True  # Default enabled
    
    def set_monitor_config_enabled(self, enabled: bool):
        """Enable/disable monitor configuration"""
        self.config.monitor_config_enabled_file.write_text('true' if enabled else 'false')
    
    
    def is_system_tray_enabled(self) -> bool:
        """Check if system tray is enabled"""
        try:
            return self.config.system_tray_enabled_file.read_text().strip().lower() == 'true'
        except:
            return TRAY_AVAILABLE  # Default to available if supported
    
    def set_system_tray_enabled(self, enabled: bool):
        """Enable/disable system tray integration"""
        self.config.system_tray_enabled_file.write_text('true' if enabled else 'false')
    
    def get_monitor_wallpapers(self) -> Dict[str, str]:
        """Get current wallpaper for each monitor"""
        try:
            if self.config.monitor_wallpapers_file.exists():
                content = self.config.monitor_wallpapers_file.read_text()
                return json.loads(content)
        except Exception as e:
            print(f"Error reading monitor wallpapers: {e}")
        return {}
    
    def set_monitor_wallpaper(self, monitor: str, wallpaper_path: Path):
        """Set wallpaper for specific monitor and update tracking"""
        try:
            monitor_wallpapers = self.get_monitor_wallpapers()
            monitor_wallpapers[monitor] = str(wallpaper_path)
            self.config.monitor_wallpapers_file.write_text(json.dumps(monitor_wallpapers, indent=2))
        except Exception as e:
            print(f"Error updating monitor wallpaper tracking: {e}")
    
    def get_keybind_mode(self) -> str:
        """Get keybind behavior mode: 'all' (sync all monitors) or 'active' (active monitor only)"""
        try:
            if self.config.keybind_mode_file.exists():
                return self.config.keybind_mode_file.read_text().strip()
        except Exception:
            pass
        return 'all'  # Default to syncing all monitors
    
    def set_keybind_mode(self, mode: str):
        """Set keybind behavior mode: 'all' or 'active'"""
        if mode in ['all', 'active']:
            self.config.keybind_mode_file.write_text(mode)
    
    def monitors_have_different_wallpapers(self) -> bool:
        """Check if monitors currently have different wallpapers set"""
        monitor_wallpapers = self.get_monitor_wallpapers()
        if len(monitor_wallpapers) <= 1:
            return False
        
        # Check if all monitors have the same wallpaper
        wallpapers = list(monitor_wallpapers.values())
        return len(set(wallpapers)) > 1
    
    def update_current_index(self, image_path: Path):
        """Update the current index for keybind sync"""
        try:
            wallpapers = []
            for file_path in self.config.wallpaper_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in self.config.image_extensions:
                    wallpapers.append(file_path)
            
            wallpapers.sort(key=lambda x: str(x))
            
            try:
                current_index = wallpapers.index(image_path)
                self.state_file.write_text(str(current_index))
            except ValueError:
                self.state_file.write_text("0")
                
        except Exception as e:
            print(f"Error updating current index: {e}")

class SystemTrayManager:
    """Manages system tray integration using separate process"""

    def __init__(self, app):
        self.app = app
        self.tray_process = None
        self.ipc_monitor_thread = None
        self.monitoring = False

    def create_tray_icon(self):
        """Create system tray icon in separate process"""
        global tray_process
        if not TRAY_AVAILABLE:
            return False

        try:
            # Start the tray process
            tray_script_path = Path(__file__).parent / "wall-it-tray.py"
            self.tray_process = subprocess.Popen([sys.executable, str(tray_script_path)])
            tray_process = self.tray_process  # Store globally for cleanup
            
            # Start IPC monitor to listen for commands from tray
            self.start_ipc_monitor()
            
            print("✅ System tray icon created in separate process")
            return True

        except Exception as e:
            print(f"Error creating tray icon: {e}")
            return False
    
    def start_ipc_monitor(self):
        """Start monitoring for IPC commands from tray"""
        self.monitoring = True
        self.ipc_monitor_thread = threading.Thread(target=self._monitor_ipc_commands, daemon=True)
        self.ipc_monitor_thread.start()
    
    def _monitor_ipc_commands(self):
        """Monitor for commands from the tray process"""
        ipc_dir = Path.home() / ".cache" / "wall-it" / "ipc"
        ipc_dir.mkdir(parents=True, exist_ok=True)
        
        processed_files = set()
        
        while self.monitoring:
            try:
                # Look for command files
                for cmd_file in ipc_dir.glob("command_*"):
                    if cmd_file.name in processed_files:
                        continue
                    
                    if cmd_file.exists():
                        try:
                            command = cmd_file.read_text().strip()
                            
                            # Process the command on the main thread
                            if command == "random_wallpaper":
                                GLib.idle_add(self.app.on_random_clicked, None)
                            elif command == "next_wallpaper":
                                GLib.idle_add(self._handle_next_wallpaper)
                            elif command == "toggle_auto_change":
                                current_state = self.app.wallpaper_setter.is_auto_change_enabled()
                                GLib.idle_add(self.app.set_auto_change, not current_state)
                            elif command == "quit_app":
                                GLib.idle_add(self.app.quit_application)
                            elif command == "show_window":
                                GLib.idle_add(self.app.show_window)
                            
                            # Mark as processed and remove the file
                            processed_files.add(cmd_file.name)
                            cmd_file.unlink(missing_ok=True)
                            
                        except Exception as e:
                            print(f"Error processing IPC command: {e}")
                
                # Clean up old processed files from memory
                current_time = time.time()
                processed_files = {f for f in processed_files 
                                 if (ipc_dir / f).exists() and 
                                 current_time - (ipc_dir / f).stat().st_mtime < 300}  # 5 minutes
                
                time.sleep(0.5)  # Check every half second
                
            except Exception as e:
                print(f"Error in IPC monitor: {e}")
                time.sleep(1)
    
    def _handle_next_wallpaper(self):
        """Handle next wallpaper command"""
        if self.app.grid_view.wallpapers:
            # Find current wallpaper and go to next
            try:
                current_path = self.app.config.current_wallpaper.resolve()
                current_index = self.app.grid_view.wallpapers.index(current_path)
                next_index = (current_index + 1) % len(self.app.grid_view.wallpapers)
                next_wallpaper = self.app.grid_view.wallpapers[next_index]
                current_effect = self.app.wallpaper_setter.get_current_effect()
                self.app.set_wallpaper_with_effect(next_wallpaper, current_effect)
            except:
                # Fallback to first wallpaper
                self.app.on_random_clicked(None)

    def stop_tray_icon(self):
        """Stop the tray process"""
        self.monitoring = False
        if self.tray_process:
            try:
                self.tray_process.terminate()
                try:
                    self.tray_process.wait(timeout=2)  # Wait up to 2 seconds
                except subprocess.TimeoutExpired:
                    self.tray_process.kill()  # Force kill if it doesn't terminate
            except Exception as e:
                print(f"Error stopping tray process: {e}")
        
        global tray_process
        tray_process = None  # Clear global reference

    def update_auto_toggle(self, enabled: bool):
        """Update auto-change toggle state"""
        # In separate process implementation, we don't need to manually update the toggle state
        # as it's handled by the separate tray process
        pass

class WallpaperGridView(Gtk.ScrolledWindow):
    """Enhanced grid view with drag&drop and high-res support"""
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_vexpand(True)
        self.set_hexpand(True)
        
        # Create flow box for thumbnails - optimized for larger HiDPI thumbnails
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(8)  # Original layout
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_activate_on_single_click(False)
        self.flowbox.set_row_spacing(12)
        self.flowbox.set_column_spacing(12)
        self.flowbox.connect('child-activated', self.on_wallpaper_activated)
        self.flowbox.connect('selected-children-changed', self.on_selection_changed)
        
        self.set_child(self.flowbox)
        
        # Setup drag and drop
        self.setup_drag_and_drop()
        
        self.wallpapers = []
        self.selected_wallpaper_path = None
        self.selected_wallpapers = set()
    
    def setup_drag_and_drop(self):
        """Setup drag and drop functionality"""
        # Create drop target for files
        drop_target = Gtk.DropTarget.new(Gdk.FileList.__gtype__, Gdk.DragAction.COPY)
        drop_target.connect('drop', self.on_drop)
        drop_target.connect('enter', self.on_drag_enter)
        drop_target.connect('leave', self.on_drag_leave)
        
        # Add to flowbox
        self.flowbox.add_controller(drop_target)
    
    def on_drag_enter(self, drop_target, x, y):
        """Handle drag enter event"""
        self.flowbox.add_css_class("drop-hover")
        return Gdk.DragAction.COPY
    
    def on_drag_leave(self, drop_target):
        """Handle drag leave event"""
        self.flowbox.remove_css_class("drop-hover")
    
    def on_drop(self, drop_target, value, x, y):
        """Handle file drop"""
        try:
            if hasattr(value, 'get_files'):
                files = value.get_files()
                for file in files:
                    file_path = Path(file.get_path())
                    self.handle_dropped_file(file_path)
            else:
                print(f"Unsupported drop value type: {type(value)}")
        except Exception as e:
            print(f"Error handling drop: {e}")
        return True
    
    def handle_dropped_file(self, file_path: Path):
        """Handle a dropped file"""
        try:
            if file_path.is_file() and file_path.suffix.lower() in self.app.config.image_extensions:
                # Copy to wallpaper directory
                dest_path = self.app.config.wallpaper_dir / file_path.name
                
                if not dest_path.exists():
                    shutil.copy2(file_path, dest_path)
                    self.app.update_status(f"✅ Added wallpaper: {file_path.name}")
                    # Add small delay then reload
                    def delayed_reload():
                        import time
                        time.sleep(0.1)  # Small delay for file system sync
                        GLib.idle_add(self.load_wallpapers)
                    
                    thread = threading.Thread(target=delayed_reload)
                    thread.daemon = True
                    thread.start()
                else:
                    self.app.update_status(f"⚠️ Wallpaper already exists: {file_path.name}")
            elif file_path.is_dir():
                # Handle dropped folder
                self.app.copy_wallpapers_from_folder(file_path)
            else:
                self.app.update_status(f"❌ Unsupported file type: {file_path.suffix}")
        except Exception as e:
            self.app.update_status(f"❌ Error adding dropped file: {e}")
    
    def load_wallpapers(self):
        """Load wallpapers from directory"""
        self.wallpapers = []
        
        if not self.app.config.wallpaper_dir.exists():
            print(f"Wallpaper directory does not exist: {self.app.config.wallpaper_dir}")
            return
        
        total_files = 0
        for file_path in self.app.config.wallpaper_dir.iterdir():
            total_files += 1
            # Skip directories (including .removed) and load only image files
            if (file_path.is_file() and 
                file_path.suffix.lower() in self.app.config.image_extensions):
                self.wallpapers.append(file_path)
        
        print(f"Debug: Found {len(self.wallpapers)} wallpapers out of {total_files} total files in {self.app.config.wallpaper_dir}")
        print(f"Debug: Image extensions: {self.app.config.image_extensions}")
        
        self.wallpapers.sort(key=lambda x: x.name.lower())
        self.update_grid()
    
    def update_grid(self):
        """Update the thumbnail grid"""
        print(f"Debug: Updating grid with {len(self.wallpapers)} wallpapers")
        
        child = self.flowbox.get_first_child()
        removed_count = 0
        while child:
            next_child = child.get_next_sibling()
            self.flowbox.remove(child)
            child = next_child
            removed_count += 1
        
        print(f"Debug: Removed {removed_count} old thumbnails")
        
        for i, wallpaper_path in enumerate(self.wallpapers):
            self.add_thumbnail(wallpaper_path)
        
        print(f"Debug: Added {len(self.wallpapers)} new thumbnails")
    
    def add_thumbnail(self, image_path: Path):
        """Add a thumbnail to the grid with enhanced info"""
        def create_thumb():
            pixbuf = self.app.thumbnail_manager.create_thumbnail(image_path)
            image_info = HighResImageHandler.get_image_info(image_path)
            GLib.idle_add(self.add_thumbnail_widget, image_path, pixbuf, image_info)
        
        thread = threading.Thread(target=create_thumb)
        thread.daemon = True
        thread.start()
    
    def add_thumbnail_widget(self, image_path: Path, pixbuf: Optional[GdkPixbuf.Pixbuf], image_info: Dict):
        """Add enhanced thumbnail widget to flowbox"""
        if pixbuf is None:
            return
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        
        # Use DrawingArea instead of Gtk.Image to bypass scaling issues
        image = Gtk.DrawingArea()
        image.set_size_request(150, 150)
        image.set_draw_func(self.draw_pixbuf, pixbuf)
        
        # Store pixbuf reference to prevent garbage collection
        image._pixbuf = pixbuf
        
        frame = Gtk.Frame()
        frame.set_child(image)
        
        # Enhanced label with resolution info
        label_text = image_path.stem
        if image_info['width'] > 0:
            label_text = f"{image_path.stem}\n{image_info['width']}x{image_info['height']}"
            if image_info['size_mb'] > 1:
                label_text += f"\n{image_info['size_mb']:.1f}MB"
        
        label = Gtk.Label()
        label.set_text(label_text)
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        label.set_max_width_chars(20)
        label.set_justify(Gtk.Justification.CENTER)
        
        # Add high-res indicator
        if HighResImageHandler.is_high_res(image_path):
            hires_label = Gtk.Label()
            hires_label.set_text("🖼️ HD")
            hires_label.add_css_class("high-res-indicator")
            box.append(hires_label)
        
        box.append(frame)
        box.append(label)
        
        box.image_path = image_path
        box.image_info = image_info
        
        self.flowbox.append(box)
    
    def draw_pixbuf(self, area, cr, width, height, pixbuf):
        """Draw pixbuf properly scaled and centered"""
        if pixbuf:
            # Get pixbuf dimensions
            pb_width = pixbuf.get_width()
            pb_height = pixbuf.get_height()
            
            # Calculate scale to fit pixbuf in the drawing area
            scale_x = width / pb_width
            scale_y = height / pb_height
            scale = min(scale_x, scale_y)  # Maintain aspect ratio
            
            # Calculate position to center the image
            scaled_width = pb_width * scale
            scaled_height = pb_height * scale
            x_offset = (width - scaled_width) / 2
            y_offset = (height - scaled_height) / 2
            
            # Apply transformations and draw
            cr.save()
            cr.translate(x_offset, y_offset)
            cr.scale(scale, scale)
            
            # Use newer surface-based approach instead of deprecated cairo_set_source_pixbuf
            try:
                surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, 1, None)
                cr.set_source_surface(surface, 0, 0)
            except:
                # Fallback to deprecated method if new one fails
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
            
            cr.paint()
            cr.restore()
    
    def on_wallpaper_activated(self, flowbox, child):
        """Handle wallpaper double-click"""
        box = child.get_child()
        if hasattr(box, 'image_path'):
            # Apply current effect when setting wallpaper
            current_effect = self.app.wallpaper_setter.get_current_effect()
            self.app.set_wallpaper_with_effect(box.image_path, current_effect)
    
    def on_selection_changed(self, flowbox):
        """Handle wallpaper selection change"""
        selected = flowbox.get_selected_children()
        
        # Update selected wallpapers set
        self.selected_wallpapers.clear()
        for child in selected:
            box = child.get_child()
            if hasattr(box, 'image_path'):
                self.selected_wallpapers.add(box.image_path)
        
        # Update primary selection and status
        if selected:
            child = selected[0]
            box = child.get_child()
            if hasattr(box, 'image_path'):
                self.selected_wallpaper_path = box.image_path
                if len(selected) == 1:
                    # Single selection
                    info = getattr(box, 'image_info', {})
                    status_text = f"Selected: {box.image_path.name}"
                    if info.get('width', 0) > 0:
                        status_text += f" ({info['width']}x{info['height']}"
                        if info.get('size_mb', 0) > 1:
                            status_text += f", {info['size_mb']:.1f}MB"
                        status_text += ")"
                    self.app.update_status(status_text)
                else:
                    # Multiple selection
                    self.app.update_status(f"Selected {len(selected)} wallpapers")
        else:
            self.selected_wallpaper_path = None
            self.app.update_status("Ready - Drag & drop images or folders to add wallpapers")

class WallpaperApp(Gtk.ApplicationWindow):
    """Enhanced Wall-IT application with system tray, monitor scaling, and timer"""
    def __init__(self, app):
        super().__init__(application=app)
        self.app = app
        
        # Initialize configuration and managers
        self.config = WallpaperConfig()
        self.compositor = CompositorDetector.detect_compositor()
        # Use backend manager instead of old MonitorManager
        self.backend_manager = _import_backend_manager()
        self.thumbnail_manager = ThumbnailManager(self.config)
        self.wallpaper_setter = WallpaperSetter(self.config)
        self.wallpaper_timer = WallpaperTimer(self)
        self.system_tray = None
        
        # Initialize weather sync (inspired by Asteroid app)
        self.weather_sync = WeatherSync()
        self.weather_animation = WeatherAnimationOverlay(self.weather_sync)
        self.weather_widget = None
        
        # Initialize UI
        self.init_ui()
        
        # Setup system tray if enabled
        if self.wallpaper_setter.is_system_tray_enabled() and TRAY_AVAILABLE:
            self.system_tray_manager = SystemTrayManager(self)
            self.system_tray_manager.create_tray_icon()
        
        
        # Setup auto-change timer if enabled
        if self.wallpaper_setter.is_auto_change_enabled():
            interval = self.wallpaper_setter.get_auto_change_interval()
            self.wallpaper_timer.start(interval)
        
        # Load wallpapers
        self.load_wallpapers()
        
        # Connect window close signal for system tray
        self.connect('close-request', self.on_close_request)
    
    def init_ui(self):
        """Initialize the user interface"""
        self.set_title("🪩 Wall-IT")
        self.set_resizable(True)  # Allow resizing
        self.set_default_size(800, 600)  # Terminal-like size
        # Set minimum size so Niri can narrow the column
        self.set_size_request(400, 300)
        
        # Try to set a custom icon (disco ball theme)
        try:
            # Create a simple disco ball icon using text
            self.set_icon_name("image-x-generic")  # Fallback icon
        except Exception:
            pass
        
        # Create main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_box)
        
        # Create toolbar
        toolbar_container = self.create_enhanced_toolbar()
        main_box.append(toolbar_container)
        
        # Create main content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        content_box.set_margin_top(1)
        content_box.set_margin_bottom(1)
        content_box.set_margin_start(1)
        content_box.set_margin_end(1)
        main_box.append(content_box)
        
        # Create wallpaper grid
        self.grid_view = WallpaperGridView(self)
        content_box.append(self.grid_view)
        
        # Create status bar
        status_bar = self.create_enhanced_status_bar()
        main_box.append(status_bar)
        
        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()
        
        # Apply CSS styling
        self.apply_css_styling()
    
    def create_enhanced_toolbar(self):
        """Create enhanced toolbar with all features"""
        # Make toolbar scrollable
        toolbar_scroll = Gtk.ScrolledWindow()
        toolbar_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        toolbar.set_margin_top(2)
        toolbar.set_margin_bottom(2)
        toolbar.set_margin_start(2)
        toolbar.set_margin_end(2)
        toolbar.add_css_class("toolbar")
        
        toolbar_scroll.set_child(toolbar)
        
        # Weather sync widget (inspired by Asteroid)
        self.weather_widget = WeatherWidget(self.weather_sync, self.weather_animation, self)
        self.weather_widget.weather_button.connect('clicked', self.on_weather_wallpaper_clicked)
        # Note: animation button is handled by WeatherWidget.on_animation_clicked method
        toolbar.append(self.weather_widget)
        toolbar.append(Gtk.Separator())
        
        # Matugen controls
        matugen_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        matugen_label = Gtk.Label()
        matugen_label.set_text("🎨")
        matugen_label.set_tooltip_text("Dynamic colors")
        
        self.matugen_switch = Gtk.Switch()
        self.matugen_switch.set_active(self.wallpaper_setter.is_matugen_enabled())
        self.matugen_switch.set_tooltip_text("Enable dynamic color theming")
        self.matugen_switch.connect('state-set', self.on_matugen_toggled)
        # Make switch compact
        self.matugen_switch.add_css_class("compact-switch")
        
        matugen_box.append(matugen_label)
        matugen_box.append(self.matugen_switch)
        
        # Matugen scheme dropdown
        scheme_options = list(self.config.matugen_schemes.items())
        scheme_names = [display_name for _, display_name in scheme_options]
        
        scheme_string_list = Gtk.StringList()
        for name in scheme_names:
            scheme_string_list.append(name)
        
        self.scheme_dropdown = Gtk.DropDown()
        self.scheme_dropdown.set_model(scheme_string_list)
        self.scheme_dropdown.set_tooltip_text("Matugen color scheme")
        # Very compact width for laptop
        self.scheme_dropdown.set_size_request(50, -1)
        self.scheme_dropdown.set_hexpand(False)
        
        # Set current scheme
        current_scheme = self.wallpaper_setter.get_matugen_scheme()
        scheme_ids = [item[0] for item in scheme_options]
        if current_scheme in scheme_ids:
            self.scheme_dropdown.set_selected(scheme_ids.index(current_scheme))
        else:
            self.scheme_dropdown.set_selected(0)
        self.scheme_dropdown.connect('notify::selected', self.on_scheme_changed)
        # Use opacity instead of visibility to prevent layout shifts
        self.scheme_dropdown.set_opacity(1.0 if self.matugen_switch.get_active() else 0.3)
        self.scheme_dropdown.set_sensitive(self.matugen_switch.get_active())
        
        # Timer controls
        timer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        timer_label = Gtk.Label()
        timer_label.set_text("⏰")
        timer_label.set_tooltip_text("Auto-change timer")
        
        self.timer_switch = Gtk.Switch()
        self.timer_switch.set_active(self.wallpaper_setter.is_auto_change_enabled())
        self.timer_switch.set_tooltip_text("Enable automatic wallpaper changing")
        self.timer_switch.connect('state-set', self.on_timer_toggled)
        # Make switch compact
        self.timer_switch.add_css_class("compact-switch")
        
        timer_box.append(timer_label)
        timer_box.append(self.timer_switch)
        
        # Timer interval dropdown
        interval_options = [(300, '5 min'), (600, '10 min'), (900, '15 min'), (1800, '30 min'), (3600, '1 hour')]
        interval_names = [display_name for _, display_name in interval_options]
        
        interval_string_list = Gtk.StringList()
        for name in interval_names:
            interval_string_list.append(name)
        
        self.interval_dropdown = Gtk.DropDown()
        self.interval_dropdown.set_model(interval_string_list)
        self.interval_dropdown.set_tooltip_text("Auto-change interval")
        # Very compact width for laptop
        self.interval_dropdown.set_size_request(40, -1)
        self.interval_dropdown.set_hexpand(False)
        
        # Set current interval
        current_interval = self.wallpaper_setter.get_auto_change_interval()
        interval_values = [item[0] for item in interval_options]
        if current_interval in interval_values:
            self.interval_dropdown.set_selected(interval_values.index(current_interval))
        else:
            self.interval_dropdown.set_selected(0)  # Default to 5 min
        self.interval_dropdown.connect('notify::selected', self.on_interval_changed)
        # Use opacity instead of visibility to prevent layout shifts
        self.interval_dropdown.set_opacity(1.0 if self.timer_switch.get_active() else 0.3)
        self.interval_dropdown.set_sensitive(self.timer_switch.get_active())
        
        # Monitor configuration controls
        monitor_config_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        monitor_config_label = Gtk.Label()
        monitor_config_label.set_text("🖥️")
        monitor_config_label.set_tooltip_text("Monitor configuration")
        
        self.monitor_config_switch = Gtk.Switch()
        self.monitor_config_switch.set_active(self.wallpaper_setter.is_monitor_config_enabled())
        self.monitor_config_switch.set_tooltip_text("Enable monitor resolution/scaling controls")
        self.monitor_config_switch.connect('state-set', self.on_monitor_config_toggled)
        # Make switch compact
        self.monitor_config_switch.add_css_class("compact-switch")
        
        monitor_config_box.append(monitor_config_label)
        monitor_config_box.append(self.monitor_config_switch)
        
        # Monitor selection controls
        monitor_label = Gtk.Label()
        monitor_label.set_text("📺")
        monitor_label.set_tooltip_text("Target monitor for wallpaper")
        
        # Get monitors from backend manager
        self.available_monitors = []  # Store monitor connectors in order
        if self.backend_manager and self.backend_manager.is_available():
            monitors = self.backend_manager.get_monitors()
            self.available_monitors = [m.get('connector', m.get('name', '')) for m in monitors if m.get('connector') or m.get('name')]
        
        monitor_string_list = Gtk.StringList()
        # Always add "All Monitors" first
        monitor_string_list.append('All Monitors')
        
        # Add each monitor with details for better identification
        for monitor in self.available_monitors:
            # Find monitor info from backend manager
            monitor_info = None
            if self.backend_manager:
                monitors = self.backend_manager.get_monitors()
                for m in monitors:
                    if m.get('connector') == monitor or m.get('name') == monitor:
                        monitor_info = m
                        break
            
            if monitor_info:
                # Show resolution and scale for better identification
                resolution = monitor_info.get('resolution', 'Unknown')
                scale = monitor_info.get('scale', 1.0)
                
                # Format display text with resolution and scale
                if scale != 1.0:
                    display_text = f"{monitor} ({resolution}, {scale}x)"
                else:
                    display_text = f"{monitor} ({resolution})"
                monitor_string_list.append(display_text)
            else:
                monitor_string_list.append(monitor)
        
        self.monitor_dropdown = Gtk.DropDown()
        self.monitor_dropdown.set_model(monitor_string_list)
        self.monitor_dropdown.set_tooltip_text("Choose target monitor for wallpaper setting")
        self.monitor_dropdown.set_size_request(80, -1)  # Compact width for laptop
        self.monitor_dropdown.set_hexpand(False)  # Prevent horizontal expansion
        self.monitor_dropdown.set_selected(0)  # Default to "All Monitors"
        self.monitor_dropdown.connect('notify::selected', self.on_monitor_changed)
        
        # Photo effects controls
        effects_label = Gtk.Label()
        effects_label.set_text("✨")
        effects_label.set_tooltip_text("Photo effects")
        effects_label.set_margin_end(2)  # Small margin for better spacing
        
        effects_options = list(PhotoEffects.EFFECTS.items())
        effects_names = [display_name for _, display_name in effects_options]
        
        effects_string_list = Gtk.StringList()
        for name in effects_names:
            effects_string_list.append(name)
        
        self.effects_dropdown = Gtk.DropDown()
        self.effects_dropdown.set_model(effects_string_list)
        self.effects_dropdown.set_tooltip_text("Choose photo effect for wallpapers")
        self.effects_dropdown.set_size_request(60, -1)  # Very compact for laptop
        self.effects_dropdown.set_hexpand(False)
        
        # Set current effect
        current_effect = self.wallpaper_setter.get_current_effect()
        effects_ids = [item[0] for item in effects_options]
        if current_effect in effects_ids:
            self.effects_dropdown.set_selected(effects_ids.index(current_effect))
        else:
            self.effects_dropdown.set_selected(0)
        self.effects_dropdown.connect('notify::selected', self.on_effect_changed)
        
        # Wallpaper scaling controls
        scaling_label = Gtk.Label()
        scaling_label.set_text("🖼️")
        scaling_label.set_tooltip_text("Wallpaper scaling")
        
        scaling_options = [
            ('crop', 'Crop'),
            ('fit', 'Fit'),
            ('stretch', 'Stretch'),
            ('no', 'No Resize')
        ]
        scaling_names = [display_name for _, display_name in scaling_options]
        
        scaling_string_list = Gtk.StringList()
        for name in scaling_names:
            scaling_string_list.append(name)
        
        self.scaling_dropdown = Gtk.DropDown()
        self.scaling_dropdown.set_model(scaling_string_list)
        self.scaling_dropdown.set_tooltip_text("Wallpaper scaling mode:\n• Crop: Crop image to fit screen (maintain aspect ratio)\n• Fit: Fit image to screen with bars (maintain aspect ratio)\n• Stretch: Stretch image to exact screen dimensions\n• No Resize: Use image original size")
        self.scaling_dropdown.set_size_request(90, -1)  # Fixed width to prevent expansion
        self.scaling_dropdown.set_hexpand(False)  # Prevent horizontal expansion
        
        # Set current scaling mode
        current_scaling = self.wallpaper_setter.get_wallpaper_scaling()
        scaling_ids = [item[0] for item in scaling_options]
        if current_scaling in scaling_ids:
            self.scaling_dropdown.set_selected(scaling_ids.index(current_scaling))
        else:
            self.scaling_dropdown.set_selected(0)
        self.scaling_dropdown.connect('notify::selected', self.on_scaling_changed)
        
        # Transition effects controls
        transition_label = Gtk.Label()
        transition_label.set_text("🔄")
        transition_label.set_tooltip_text("Transition effects")
        
        transition_options = [
            ('simple', 'Simple'),
            ('fade', 'Fade'),
            ('left', 'Slide Left'),
            ('right', 'Slide Right'),
            ('top', 'Slide Down'),
            ('bottom', 'Slide Up'),
            ('wipe', 'Wipe'),
            ('wave', 'Wave'),
            ('grow', 'Grow'),
            ('center', 'Center'),
            ('outer', 'Outer'),
            ('none', 'None')
        ]
        transition_names = [display_name for _, display_name in transition_options]
        
        transition_string_list = Gtk.StringList()
        for name in transition_names:
            transition_string_list.append(name)
        
        self.transition_dropdown = Gtk.DropDown()
        self.transition_dropdown.set_model(transition_string_list)
        self.transition_dropdown.set_tooltip_text("Choose transition effect")
        self.transition_dropdown.set_size_request(60, -1)  # Very compact for laptop
        self.transition_dropdown.set_hexpand(False)
        
        # Set current transition effect
        current_transition = self.wallpaper_setter.get_transition_effect()
        transition_ids = [item[0] for item in transition_options]
        if current_transition in transition_ids:
            self.transition_dropdown.set_selected(transition_ids.index(current_transition))
        else:
            self.transition_dropdown.set_selected(0)
        self.transition_dropdown.connect('notify::selected', self.on_transition_changed)
        
        
        # Action buttons
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh wallpapers")
        refresh_btn.connect('clicked', self.on_refresh_clicked)
        
        random_btn = Gtk.Button.new_from_icon_name("media-playlist-shuffle-symbolic")
        random_btn.set_tooltip_text("Set random wallpaper")
        random_btn.connect('clicked', self.on_random_clicked)
        
        browse_btn = Gtk.Button.new_from_icon_name("document-open-symbolic")
        browse_btn.set_tooltip_text("Select and add individual wallpaper files")
        browse_btn.connect('clicked', self.on_browse_files_clicked)
        
        folder_add_btn = Gtk.Button.new_from_icon_name("folder-symbolic")
        folder_add_btn.set_tooltip_text("Add all images from a folder")
        folder_add_btn.connect('clicked', self.on_browse_files_clicked)
        
        settings_btn = Gtk.Button.new_from_icon_name("preferences-system-symbolic")
        settings_btn.set_tooltip_text("Settings")
        settings_btn.connect('clicked', self.on_settings_clicked)

        # Close button
        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close_btn.set_tooltip_text("Close Window (to system tray if enabled)")
        close_btn.connect('clicked', self.on_close_button_clicked)

        # Create a two-row toolbar layout
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)

        # Add main controls to top row
        top_row.append(refresh_btn)
        top_row.append(random_btn)
        top_row.append(browse_btn)
        top_row.append(settings_btn)
        top_row.append(close_btn)
        top_row.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        top_row.append(effects_label)
        top_row.append(self.effects_dropdown)
        top_row.append(scaling_label)
        top_row.append(self.scaling_dropdown)
        top_row.append(transition_label)
        top_row.append(self.transition_dropdown)
        
        # Add secondary controls to bottom row
        bottom_row.append(monitor_label)
        bottom_row.append(self.monitor_dropdown)
        bottom_row.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        bottom_row.append(matugen_box)
        bottom_row.append(self.scheme_dropdown)
        bottom_row.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        bottom_row.append(timer_box)
        bottom_row.append(self.interval_dropdown)
        
        # Create vertical box for rows
        rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        rows_box.set_margin_top(1)
        rows_box.set_margin_bottom(1)
        rows_box.set_hexpand(True)  # Make sure rows expand to fill width
        rows_box.append(top_row)
        rows_box.append(bottom_row)
        
        # Make the rows expand horizontally
        top_row.set_hexpand(True)
        bottom_row.set_hexpand(True)
        
        # Add rows to toolbar
        toolbar.append(rows_box)
        
        return toolbar_scroll
    
    def create_enhanced_status_bar(self):
        """Create enhanced status bar"""
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        # Main status label
        self.status_label = Gtk.Label()
        self.status_label.set_text("Ready - Drag & drop images or folders to add wallpapers")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_hexpand(True)
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        
        # Enhanced status info
        self.enhanced_status_label = Gtk.Label()
        self.enhanced_status_label.set_halign(Gtk.Align.END)
        self.enhanced_status_label.set_ellipsize(Pango.EllipsizeMode.START)
        self.update_enhanced_status()
        
        status_box.append(self.status_label)
        status_box.append(self.enhanced_status_label)
        
        status_box.add_css_class("status-bar")
        
        return status_box
    
    def update_enhanced_status(self):
        """Update enhanced status information"""
        try:
            # Count wallpapers
            wallpaper_count = len(self.grid_view.wallpapers) if self.grid_view else 0
            
            # Get current effect
            current_effect = self.wallpaper_setter.get_current_effect()
            effect_display = PhotoEffects.EFFECTS.get(current_effect, 'Blur')
            
            # Get current monitor info with resolution
            monitor_info = "Monitor: Unknown"
            try:
                if self.backend_manager and self.backend_manager.is_available():
                    monitors = self.backend_manager.get_monitors()
                    if monitors:
                        primary_monitor = monitors[0]
                        connector = primary_monitor.get('connector', primary_monitor.get('name', 'Unknown'))
                        resolution = primary_monitor.get('resolution', 'Unknown')
                        scale = primary_monitor.get('scale', 1.0)
                        
                        if scale != 1.0:
                            monitor_info = f"Monitor: {connector} [{resolution}, {scale}x]"
                        else:
                            monitor_info = f"Monitor: {connector} [{resolution}]"
            except Exception as e:
                print(f"Error getting monitor info for status: {e}")
                monitor_info = "Monitor: Unknown"
            
            status_text = f"🖼️ {wallpaper_count} • {monitor_info}"
            
            # Show selected target monitor if not "All Monitors"
            if hasattr(self, 'monitor_dropdown'):
                selected = self.monitor_dropdown.get_selected()
                if selected != Gtk.INVALID_LIST_POSITION and selected > 0:  # 0 is "All Monitors"
                    if self.backend_manager and self.backend_manager.is_available():
                        monitors = self.backend_manager.get_monitors()
                        active_monitors = [m.get('connector', m.get('name', '')) for m in monitors if m.get('connector') or m.get('name')]
                        if selected - 1 < len(active_monitors):
                            target_monitor = active_monitors[selected - 1]
                            status_text += f" • 🎯 {target_monitor}"
            
            # Show effect if it's not 'none' (original)
            if current_effect != 'none':
                status_text += f" • ✨ {effect_display}"
            if self.matugen_switch and self.matugen_switch.get_active():
                status_text += " • 🎨 Colors"
            if hasattr(self, 'timer_switch') and self.timer_switch.get_active():
                interval = self.wallpaper_setter.get_auto_change_interval()
                minutes = interval // 60
                status_text += f" • ⏰ Auto {minutes}min"
            if hasattr(self, 'monitor_config_switch') and self.monitor_config_switch.get_active():
                status_text += " • 🖥️ Monitor Config"
            
            self.enhanced_status_label.set_text(status_text)
        except Exception as e:
            print(f"Error updating status: {e}")
    
    def apply_css_styling(self):
        """Apply CSS styling with drag&drop visual feedback"""
        css = """
        .toolbar {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            padding: 2px;
        }
        
        .toolbar box {
            padding: 1px;
            margin: 1px;
        }
        
        .toolbar separator {
            margin: 2px 4px;
            opacity: 0.2;
        }
        
        /* Override default button height */
        .toolbar button {
            min-height: 24px;
            min-width: 24px;
            padding: 2px;
            margin: 1px;
        }
        
        .toolbar dropdown {
            min-height: 24px;
            margin: 1px;
        }
        
        .toolbar dropdown > button {
            min-height: 24px;
            padding: 1px 4px;
        }
        
        .toolbar > box > box {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
            margin: 1px;
        }
        
        .status-bar {
            padding: 8px;
            background: rgba(0, 0, 0, 0.1);
            border-radius: 0 0 8px 8px;
        }
        
        .drop-hover {
            background: rgba(99, 102, 241, 0.2);
            border: 2px dashed rgba(99, 102, 241, 0.5);
            border-radius: 8px;
        }
        
        .high-res-indicator {
            font-size: 10px;
            color: #10b981;
            font-weight: bold;
        }
        
        button {
            min-height: 32px;
        }
        
        switch {
            min-height: 24px;
        }
        
        /* Compact switches - much shorter height with extended dark background like reference image */
        .compact-switch {
            min-height: 8px;
            max-height: 8px;
            min-width: 32px;  /* Wider for better proportion */
            margin: 1px;
            padding: 2px;     /* Add padding for extended background */
            background: rgba(0, 0, 0, 0.4);  /* Dark background like reference */
            border-radius: 8px;  /* Extended rounded background */
        }
        
        .compact-switch > slider {
            min-height: 6px;
            max-height: 6px;
            min-width: 6px;
            max-width: 6px;
            margin: 1px;
            border-radius: 3px;
            background: #ffffff;
            border: none;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
        }
        
        .compact-switch > trough {
            min-height: 8px;
            max-height: 8px;
            min-width: 28px;  /* Proportional to switch width */
            border-radius: 6px;
            background: rgba(60, 60, 60, 0.8);  /* Darker trough like reference */
            border: 1px solid rgba(40, 40, 40, 0.9);
        }
        
        .compact-switch:checked > trough {
            background: #ffffff;  /* White inner background when selected/enabled */
            border: 1px solid rgba(200, 200, 200, 0.8);
        }
        
        .compact-switch:checked > slider {
            background: rgba(99, 102, 241, 0.9);  /* Blue slider when active */
            border: none;
        }
        
        /* Prevent dropdown expansion issues */
        dropdown {
            max-width: 200px;
        }
        
        dropdown > button {
            max-width: 200px;
            text-overflow: ellipsis;
        }
        """
        
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self.on_key_pressed)
        self.add_controller(key_controller)
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events"""
        if keyval == Gdk.KEY_Delete or keyval == Gdk.KEY_KP_Delete:
            if self.grid_view.selected_wallpaper_path:
                self.delete_selected_wallpaper()
                return True
        elif keyval == Gdk.KEY_F2:
            self.show_settings_dialog()
            return True
        elif keyval == Gdk.KEY_F5:
            self.load_wallpapers()
            return True
        elif keyval == Gdk.KEY_space and (state & Gdk.ModifierType.CONTROL_MASK):
            self.on_random_clicked(None)
            return True
        return False
    
    def on_close_request(self, *args):
        """Handle window close request"""
        if TRAY_AVAILABLE and self.wallpaper_setter.is_system_tray_enabled():
            # Hide to system tray instead of quitting
            self.set_visible(False)
            return True  # Prevent default close behavior
        else:
            # Normal quit
            self.quit_application()
            return False

    def show_window(self):
        """Show the main window"""
        self.set_visible(True)
        self.present()
    
    # Event handlers
    def load_wallpapers(self):
        """Load wallpapers in background"""
        def load_in_background():
            GLib.idle_add(self.grid_view.load_wallpapers)
            GLib.idle_add(self.update_status, f"Found {len(self.grid_view.wallpapers)} wallpapers")
            GLib.idle_add(self.update_enhanced_status)
        
        thread = threading.Thread(target=load_in_background)
        thread.daemon = True
        thread.start()
    
    def set_wallpaper_with_effect(self, image_path: Path, effect: str = None):
        """Set wallpaper with current effect"""
        if effect is None:
            effect = self.wallpaper_setter.get_current_effect()
        
        transition = self.wallpaper_setter.get_transition_effect()
        
        # Get selected monitor using stored monitor list
        monitor = None
        if hasattr(self, 'monitor_dropdown'):
            selected = self.monitor_dropdown.get_selected()
            if selected != Gtk.INVALID_LIST_POSITION and selected > 0:  # 0 is "All Monitors"
                # Use stored monitor list for consistent mapping
                if hasattr(self, 'available_monitors') and (selected - 1) < len(self.available_monitors):
                    monitor = self.available_monitors[selected - 1]  # -1 because "All Monitors" is at index 0
        
        effect_display = PhotoEffects.EFFECTS.get(effect, 'no')
        monitor_text = f" on {monitor}" if monitor else ""
        self.update_status(f"Setting wallpaper with {effect_display} effect{monitor_text}...")
        
        def set_in_background():
            success = self.wallpaper_setter.set_wallpaper(image_path, monitor, transition, effect)
            if success:
                effect_display = PhotoEffects.EFFECTS.get(effect, 'blur')
                status_msg = f"✅ Set wallpaper: {image_path.name}"
                if effect != 'none':
                    status_msg += f" ({effect_display})"
                if monitor:
                    status_msg += f" on {monitor}"
                
                # Update matugen colors if enabled
                if self.wallpaper_setter.is_matugen_enabled():
                    self.wallpaper_setter.update_matugen_colors(image_path)
                
                GLib.idle_add(self.update_status, status_msg)
                GLib.idle_add(self.update_enhanced_status)
            else:
                GLib.idle_add(self.update_status, "❌ Failed to set wallpaper")
        
        thread = threading.Thread(target=set_in_background)
        thread.daemon = True
        thread.start()
    
    def update_status(self, message: str):
        """Update status label"""
        if self.status_label:
            self.status_label.set_text(message)
    
    def on_refresh_clicked(self, button):
        """Handle refresh button click"""
        self.load_wallpapers()
    
    def on_random_clicked(self, button):
        """Handle random wallpaper button click"""
        if self.grid_view.wallpapers:
            random_wallpaper = random.choice(self.grid_view.wallpapers)
            current_effect = self.wallpaper_setter.get_current_effect()
            self.set_wallpaper_with_effect(random_wallpaper, current_effect)

    def on_close_button_clicked(self, button):
        """Handle close button click - hide to tray or quit"""
        # Trigger the same behavior as the window close event
        self.close()
    
    def on_weather_wallpaper_clicked(self, button):
        """Handle weather-based wallpaper recommendation"""
        if not self.grid_view.wallpapers:
            self.update_status("❌ No wallpapers available")
            return
        
        # Get weather-recommended wallpaper
        recommended_wallpaper = self.weather_sync.get_recommended_wallpaper(self.grid_view.wallpapers)
        
        if recommended_wallpaper:
            current_effect = self.wallpaper_setter.get_current_effect()
            self.set_wallpaper_with_effect(recommended_wallpaper, current_effect)
            
            # Show weather info in status
            weather_info = self.weather_sync.get_weather_description()
            self.update_status(f"{weather_info['emoji']} Set {weather_info['time_period']} wallpaper: {recommended_wallpaper.name}")
        else:
            # Fallback to random
            self.on_random_clicked(button)
    
    def on_weather_animation_clicked(self, button):
        """Handle weather animation button click - show Asteroid-style overlay"""
        # Get weather info first
        weather_info = self.weather_sync.get_weather_description()
        
        print(f"DEBUG: Weather animation button clicked!")
        print(f"DEBUG: Current weather condition: {weather_info['condition']}")
        print(f"DEBUG: Current time period: {weather_info['time_period']}")
        print(f"DEBUG: Recommended keywords: {weather_info['recommended_keywords']}")
        
        # Show animated weather overlay regardless of wallpaper
        self.weather_animation.show_weather_overlay(self, duration=15)

        # Update status
        self.update_status(f"🎆 Showing {weather_info['time_period']} animation overlay for 15s (Press ESC to close)")
        
        # Log for debugging
        print(f"DEBUG: Weather animation triggered for {weather_info['time_period']} at {time.strftime('%H:%M:%S')}")
    
    def on_browse_files_clicked(self, button):
        """Handle browse files button click - Open enhanced folder browser"""
        dialog = EnhancedFolderBrowser(self, self.config)
        dialog.present()
    
    def copy_selected_files(self, files):
        """Copy individually selected files"""
        if not files:
            self.update_status("❌ No files selected")
            return
        
        copied_count = 0
        total_files = len(files)
        
        for i, file in enumerate(files):
            file_path = Path(file.get_path())
            
            # Check if it's an image file
            if file_path.suffix.lower() not in self.config.image_extensions:
                continue
                
            dest_path = self.config.wallpaper_dir / file_path.name
            if not dest_path.exists():
                try:
                    shutil.copy2(file_path, dest_path)
                    copied_count += 1
                except Exception as e:
                    print(f"Error copying {file_path.name}: {e}")
            
            # Update progress
            if i % 5 == 0 or i == total_files - 1:
                self.update_status(f"📋 Copying files... {i+1}/{total_files}")
        
        if copied_count > 0:
            self.update_status(f"✅ Added {copied_count} wallpaper{'s' if copied_count != 1 else ''}")
            self.grid_view.load_wallpapers()  # Direct call to grid view's load method
        else:
            self.update_status("⚠️ No new wallpapers to copy - all already exist")
    
    def copy_wallpapers_from_folder(self, source_folder: Path):
        """Copy wallpapers from selected folder"""
        if not source_folder.exists() or not source_folder.is_dir():
            self.update_status("❌ Invalid folder selected")
            return
        
        self.update_status(f"🔍 Scanning folder: {source_folder.name}...")
        
        image_files = []
        for file_path in source_folder.rglob("*"):  # Recursive search
            if file_path.is_file() and file_path.suffix.lower() in self.config.image_extensions:
                image_files.append(file_path)
        
        if not image_files:
            self.update_status(f"❌ No wallpapers found in {source_folder.name}")
            return
        
        copied_count = 0
        for source_path in image_files:
            dest_path = self.config.wallpaper_dir / source_path.name
            
            if not dest_path.exists():
                try:
                    shutil.copy2(source_path, dest_path)
                    copied_count += 1
                except Exception as e:
                    print(f"Error copying {source_path.name}: {e}")
        
        if copied_count > 0:
            self.update_status(f"✅ Added {copied_count} wallpaper{'s' if copied_count > 1 else ''} from {source_folder.name}")
            self.grid_view.load_wallpapers()  # Direct call to grid view's load method
        else:
            self.update_status("⚠️ No new wallpapers to copy - all already exist")
    
    def on_folder_clicked(self, button):
        """Handle open folder button click"""
        try:
            subprocess.Popen(['xdg-open', str(self.config.wallpaper_dir)])
            self.update_status(f"📁 Opened wallpaper folder: {self.config.wallpaper_dir}")
        except Exception as e:
            self.update_status(f"❌ Error opening folder: {e}")
    
    def on_matugen_toggled(self, switch, state):
        """Handle matugen toggle"""
        self.wallpaper_setter.set_matugen_enabled(state)
        # Use opacity instead of visibility to prevent layout shifts
        self.scheme_dropdown.set_opacity(1.0 if state else 0.3)
        self.scheme_dropdown.set_sensitive(state)
        self.update_enhanced_status()
        
        status = "enabled" if state else "disabled"
        self.update_status(f"🎨 Dynamic colors {status}")
    
    def on_scheme_changed(self, dropdown, pspec):
        """Handle color scheme change"""
        selected = dropdown.get_selected()
        if selected != Gtk.INVALID_LIST_POSITION:
            scheme_options = list(self.config.matugen_schemes.keys())
            if selected < len(scheme_options):
                scheme_id = scheme_options[selected]
                self.wallpaper_setter.set_matugen_scheme(scheme_id)
                scheme_name = self.config.matugen_schemes.get(scheme_id, scheme_id)
                self.update_status(f"🎨 Color scheme set to: {scheme_name}")
    
    def on_timer_toggled(self, switch, state):
        """Handle timer toggle"""
        self.wallpaper_setter.set_auto_change_enabled(state)
        # Use opacity instead of visibility to prevent layout shifts
        self.interval_dropdown.set_opacity(1.0 if state else 0.3)
        self.interval_dropdown.set_sensitive(state)
        
        if state:
            interval = self.wallpaper_setter.get_auto_change_interval()
            self.wallpaper_timer.start(interval)
        else:
            self.wallpaper_timer.stop()
        
        self.update_enhanced_status()
        
        # Update system tray
        if hasattr(self, 'system_tray_manager') and self.system_tray_manager:
            self.system_tray_manager.update_auto_toggle(state)
        
        status = "enabled" if state else "disabled"
        self.update_status(f"⏰ Auto-change timer {status}")
    
    def on_interval_changed(self, dropdown, pspec):
        """Handle interval change"""
        selected = dropdown.get_selected()
        if selected != Gtk.INVALID_LIST_POSITION:
            interval_options = [300, 600, 900, 1800, 3600]  # seconds
            if selected < len(interval_options):
                interval = interval_options[selected]
                self.wallpaper_setter.set_auto_change_interval(interval)
                
                # Restart timer if it's running
                if self.wallpaper_timer.running:
                    self.wallpaper_timer.start(interval)
                
                self.update_enhanced_status()
                minutes = interval // 60
                self.update_status(f"⏰ Auto-change interval set to {minutes} minutes")
    
    def on_monitor_config_toggled(self, switch, state):
        """Handle monitor config toggle"""
        self.wallpaper_setter.set_monitor_config_enabled(state)
        self.update_enhanced_status()
        
        status = "enabled" if state else "disabled"
        self.update_status(f"🖥️ Monitor configuration {status}")
    
    def on_effect_changed(self, dropdown, pspec):
        """Handle photo effect change"""
        selected = dropdown.get_selected()
        if selected != Gtk.INVALID_LIST_POSITION:
            effects_list = list(PhotoEffects.EFFECTS.keys())
            if selected < len(effects_list):
                effect_id = effects_list[selected]
                self.wallpaper_setter.set_current_effect(effect_id)
                self.update_enhanced_status()
                effect_name = PhotoEffects.EFFECTS.get(effect_id, 'Blur')
                self.update_status(f"✨ Photo effect set to: {effect_name}")
    
    def on_scaling_changed(self, dropdown, pspec):
        """Handle scaling change"""
        selected = dropdown.get_selected()
        if selected != Gtk.INVALID_LIST_POSITION:
            # Must match the order in the dropdown definition
            scaling_options = ['crop', 'fit', 'stretch', 'no']
            if selected < len(scaling_options):
                scaling_id = scaling_options[selected]
                self.wallpaper_setter.set_wallpaper_scaling(scaling_id)
                self.update_status(f"🖼️ Wallpaper scaling set to: {scaling_id}")
    
    def on_transition_changed(self, dropdown, pspec):
        """Handle transition change"""
        selected = dropdown.get_selected()
        if selected != Gtk.INVALID_LIST_POSITION:
            # Must match the order in the dropdown definition
            transition_options = ['simple', 'fade', 'left', 'right', 'top', 'bottom', 'wipe', 'wave', 'grow', 'center', 'outer', 'none']
            if selected < len(transition_options):
                transition_id = transition_options[selected]
                self.wallpaper_setter.set_transition_effect(transition_id)
                self.update_status(f"🔄 Transition effect set to: {transition_id}")
    
    def on_monitor_changed(self, dropdown, pspec):
        """Handle monitor selection change"""
        selected = dropdown.get_selected()
        if selected != Gtk.INVALID_LIST_POSITION:
            # Use the stored monitor list for consistent mapping
            if selected == 0:
                # "All Monitors" selected
                self.update_status("📺 Target monitor set to: All Monitors")
            else:
                # Specific monitor selected - use stored monitor list
                if hasattr(self, 'available_monitors') and (selected - 1) < len(self.available_monitors):
                    monitor_id = self.available_monitors[selected - 1]  # -1 because "All Monitors" is at index 0
                    
                    # Find monitor info from backend manager
                    monitor_info = None
                    if self.backend_manager:
                        monitors = self.backend_manager.get_monitors()
                        for m in monitors:
                            if m.get('connector') == monitor_id or m.get('name') == monitor_id:
                                monitor_info = m
                                break
                    
                    if monitor_info:
                        resolution = monitor_info.get('resolution', 'Unknown')
                        self.update_status(f"📺 Target monitor: {monitor_id} ({resolution})")
                    else:
                        self.update_status(f"📺 Target monitor set to: {monitor_id}")
    
    
    def on_settings_clicked(self, button):
        """Show settings dialog"""
        self.show_settings_dialog()
    
    
    
    def show_settings_dialog(self):
        """Show enhanced settings dialog"""
        dialog = Gtk.Dialog(
            title="Wall-IT Settings",
            parent=self,
            modal=True
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Apply", Gtk.ResponseType.OK
        )
        dialog.set_default_size(600, 400)
        
        content_area = dialog.get_content_area()
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)
        
        # Create notebook for tabs
        notebook = Gtk.Notebook()
        notebook.set_hexpand(True)
        notebook.set_vexpand(True)
        content_area.append(notebook)
        
        # ============= GENERAL TAB =============
        general_page = Gtk.ScrolledWindow()
        general_page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        general_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        general_box.set_margin_top(20)
        general_box.set_margin_bottom(20)
        general_box.set_margin_start(20)
        general_box.set_margin_end(20)
        
        # System tray settings
        tray_enable_switch = None
        if TRAY_AVAILABLE:
            tray_frame = Gtk.Frame()
            tray_frame.set_label("System Tray Settings")
            tray_frame.set_margin_bottom(12)
            
            tray_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            tray_box.set_margin_top(8)
            tray_box.set_margin_bottom(8)
            tray_box.set_margin_start(12)
            tray_box.set_margin_end(12)
            
            tray_enable_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            tray_enable_label = Gtk.Label()
            tray_enable_label.set_text("Enable System Tray:")
            tray_enable_label.set_size_request(150, -1)
            
            tray_enable_switch = Gtk.Switch()
            tray_enable_switch.set_active(self.wallpaper_setter.is_system_tray_enabled())
            
            tray_enable_box.append(tray_enable_label)
            tray_enable_box.append(tray_enable_switch)
            tray_box.append(tray_enable_box)
            
            tray_info = Gtk.Label()
            tray_info.set_markup('<span size="small">When enabled, Wall-IT will minimize to system tray instead of closing</span>')
            tray_info.set_wrap(True)
            tray_box.append(tray_info)
            
            tray_frame.set_child(tray_box)
            general_box.append(tray_frame)
        
        # Keybind Behavior Settings
        keybind_frame = Gtk.Frame()
        keybind_frame.set_label("Keybind Behavior")
        keybind_frame.set_margin_bottom(12)
        
        keybind_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        keybind_box.set_margin_top(8)
        keybind_box.set_margin_bottom(8)
        keybind_box.set_margin_start(12)
        keybind_box.set_margin_end(12)
        
        # Keybind mode selection
        keybind_mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        keybind_mode_label = Gtk.Label()
        keybind_mode_label.set_text("Keybind Target:")
        keybind_mode_label.set_size_request(150, -1)
        
        keybind_mode_dropdown = Gtk.DropDown()
        keybind_mode_options = Gtk.StringList()
        keybind_mode_options.append("All Monitors (Sync)")
        keybind_mode_options.append("Active Monitor Only")
        keybind_mode_dropdown.set_model(keybind_mode_options)
        
        # Set current mode
        current_mode = self.wallpaper_setter.get_keybind_mode()
        keybind_mode_dropdown.set_selected(0 if current_mode == 'all' else 1)
        
        keybind_mode_box.append(keybind_mode_label)
        keybind_mode_box.append(keybind_mode_dropdown)
        keybind_box.append(keybind_mode_box)
        
        # Description
        keybind_info = Gtk.Label()
        keybind_info.set_markup('<span size="small"><b>All Monitors:</b> Keybinds change wallpapers on all monitors (current behavior)\n<b>Active Monitor Only:</b> Keybinds only change wallpaper on currently focused monitor</span>')
        keybind_info.set_wrap(True)
        keybind_info.set_halign(Gtk.Align.START)
        keybind_box.append(keybind_info)
        
        keybind_frame.set_child(keybind_box)
        general_box.append(keybind_frame)
        
        general_page.set_child(general_box)
        notebook.append_page(general_page, Gtk.Label(label="General"))
        
        # ============= FEATURE STATUS TAB =============
        feature_page = Gtk.ScrolledWindow()
        feature_page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        feature_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        feature_box.set_margin_top(20)
        feature_box.set_margin_bottom(20)
        feature_box.set_margin_start(20)
        feature_box.set_margin_end(20)
        
        # Feature availability
        feature_frame = Gtk.Frame()
        feature_frame.set_label("Feature Availability")
        
        availability_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        availability_box.set_margin_top(8)
        availability_box.set_margin_bottom(8)
        availability_box.set_margin_start(12)
        availability_box.set_margin_end(12)
        
        if PIL_AVAILABLE:
            pil_label = Gtk.Label()
            pil_label.set_markup('<span color="green">✅ PIL/Pillow available - Photo effects enabled</span>')
            availability_box.append(pil_label)
        else:
            pil_label = Gtk.Label()
            pil_label.set_markup('<span color="orange">⚠️ PIL/Pillow not available - paru -S python-pillow</span>')
            availability_box.append(pil_label)
        
        if TRAY_AVAILABLE:
            tray_label = Gtk.Label()
            tray_label.set_markup('<span color="green">✅ System tray support available</span>')
            availability_box.append(tray_label)
        else:
            # System tray is disabled in GTK4, but don't prominently display this
            # as it's not essential functionality
            pass  # No need to show this limitation
        
        # Compositor info
        compositor_label = Gtk.Label()
        if self.compositor:
            compositor_label.set_markup(f'<span color="green">✅ Compositor detected: {self.compositor}</span>')
        else:
            compositor_label.set_markup('<span color="orange">⚠️ No supported compositor detected</span>')
        availability_box.append(compositor_label)
        
        # Matugen availability
        try:
            subprocess.run(['matugen', '--version'], capture_output=True, timeout=2)
            matugen_label = Gtk.Label()
            matugen_label.set_markup('<span color="green">✅ matugen available - Dynamic colors enabled</span>')
            availability_box.append(matugen_label)
        except:
            matugen_label = Gtk.Label()
            matugen_label.set_markup('<span color="orange">⚠️ matugen not available</span>')
            availability_box.append(matugen_label)
        
        feature_frame.set_child(availability_box)
        feature_box.append(feature_frame)
        
        # Directory info
        dir_frame = Gtk.Frame()
        dir_frame.set_label("Directory Information")
        
        dir_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dir_box.set_margin_top(8)
        dir_box.set_margin_bottom(8)
        dir_box.set_margin_start(12)
        dir_box.set_margin_end(12)
        
        wallpaper_dir_label = Gtk.Label()
        wallpaper_dir_label.set_markup(f'<b>Wallpaper Directory:</b>\n{self.config.wallpaper_dir}')
        wallpaper_dir_label.set_selectable(True)
        wallpaper_dir_label.set_wrap(True)
        dir_box.append(wallpaper_dir_label)
        
        cache_dir_label = Gtk.Label()
        cache_dir_label.set_markup(f'<b>Cache Directory:</b>\n{self.config.cache_dir}')
        cache_dir_label.set_selectable(True)
        cache_dir_label.set_wrap(True)
        dir_box.append(cache_dir_label)
        
        dir_frame.set_child(dir_box)
        feature_box.append(dir_frame)
        
        feature_page.set_child(feature_box)
        notebook.append_page(feature_page, Gtk.Label(label="System Info"))
        
        # Keybinds are now managed via Niri configuration
        # See ~/.config/niri/config.kdl for keybind settings
        
        def on_dialog_response(dialog, response):
            if response == Gtk.ResponseType.OK:
                
                # Save system tray setting
                if TRAY_AVAILABLE:
                    tray_enabled = tray_enable_switch.get_active()
                    self.wallpaper_setter.set_system_tray_enabled(tray_enabled)
                    
                    if tray_enabled and not hasattr(self, 'system_tray_manager'):
                        self.system_tray_manager = SystemTrayManager(self)
                        self.system_tray_manager.create_tray_icon()
                        self.update_status("📟 System tray enabled")
                
                # Save keybind mode setting
                keybind_mode_selected = keybind_mode_dropdown.get_selected()
                new_mode = 'all' if keybind_mode_selected == 0 else 'active'
                self.wallpaper_setter.set_keybind_mode(new_mode)
                mode_text = "All Monitors" if new_mode == 'all' else "Active Monitor Only"
                self.update_status(f"⌨️ Keybind behavior set to: {mode_text}")
            
            dialog.destroy()
        
        dialog.connect('response', on_dialog_response)
        dialog.present()
    
    def delete_selected_wallpaper(self):
        """Remove the currently selected wallpaper from Wall-IT collection"""
        if not self.grid_view.selected_wallpaper_path:
            self.update_status("❌ No wallpaper selected for removal")
            return
        
        wallpaper_path = self.grid_view.selected_wallpaper_path
        wallpaper_name = wallpaper_path.name
        
        dialog = Gtk.AlertDialog(
            modal=True,
            message=f"Remove '{wallpaper_name}' from Wall-IT?",
            detail=f"This will remove the wallpaper from Wall-IT's collection.\nThe original file will remain on your system."
        )
        dialog.set_buttons(["Cancel", "Remove from Wall-IT"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(1)  # Default to remove
        
        def on_dialog_response(dialog, result):
            try:
                response = dialog.choose_finish(result)
                if response == 1:  # Remove from Wall-IT
                    self.remove_wallpaper_from_collection(wallpaper_path)
            except Exception as e:
                print(f"Dialog error: {e}")
        
        dialog.choose(self, None, on_dialog_response)
    
    def remove_wallpaper_from_collection(self, wallpaper_path: Path):
        """Remove wallpaper from Wall-IT collection without deleting the original file"""
        try:
            # Check if this is a file that was copied to Wall-IT directory
            is_in_wallit_dir = wallpaper_path.parent == self.config.wallpaper_dir
            
            # Remove thumbnail from cache
            cache_path = self.thumbnail_manager.get_cache_path(wallpaper_path)
            if cache_path.exists():
                cache_path.unlink()
            
            if is_in_wallit_dir:
                # Create a backup/removed folder and move the file there instead of deleting
                removed_dir = self.config.wallpaper_dir / ".removed"
                removed_dir.mkdir(exist_ok=True)
                
                backup_path = removed_dir / wallpaper_path.name
                # Handle name conflicts
                counter = 1
                while backup_path.exists():
                    name_parts = wallpaper_path.stem, counter, wallpaper_path.suffix
                    backup_path = removed_dir / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
                    counter += 1
                
                # Move file to removed folder instead of deleting
                import shutil
                shutil.move(str(wallpaper_path), str(backup_path))
                
                self.update_status(f"✅ Removed from Wall-IT: {wallpaper_path.name} (moved to .removed folder)")
            else:
                # For external files, we can't move them, so just remove from collection
                # This case shouldn't happen often since Wall-IT typically copies files to its directory
                self.update_status(f"✅ Removed from Wall-IT: {wallpaper_path.name} (original file preserved)")
            
            # Update UI
            self.grid_view.load_wallpapers()  # Direct call to grid view's load method
            
        except Exception as e:
            self.update_status(f"❌ Error removing wallpaper: {e}")
    
    def set_auto_change(self, enabled: bool):
        """Set auto-change from external call (e.g., system tray)"""
        self.timer_switch.set_active(enabled)
        
        # Update system tray if available
        if hasattr(self, 'system_tray_manager') and self.system_tray_manager:
            try:
                # Refresh the tray menu to reflect the new state
                self.system_tray_manager.update_auto_toggle(enabled)
            except Exception as e:
                print(f"Error updating tray menu: {e}")
    
    
    def quit_application(self):
        """Quit the application completely"""
        # Stop timer
        if hasattr(self, 'wallpaper_timer'):
            self.wallpaper_timer.stop()

        # Stop system tray icon if available
        if hasattr(self, 'system_tray_manager') and self.system_tray_manager:
            try:
                self.system_tray_manager.stop_tray_icon()
            except Exception as e:
                print(f"Error stopping tray icon: {e}")

        # Quit application
        self.get_application().quit()

class WallpaperApplication(Gtk.Application):
    """Main application class"""
    def __init__(self):
        super().__init__(application_id="com.wallit.app")
        self.window = None
    
    def do_activate(self):
        if not self.window:
            self.window = WallpaperApp(self)
        self.window.present()

def handle_command_line_args(args):
    """Handle command line arguments for keybind actions"""
    if len(args) < 2:
        return False
    
    # Import our config and wallpaper setter
    config = WallpaperConfig()
    wallpaper_setter = WallpaperSetter(config)
    
    # Get compositor and monitor manager for monitor support
    compositor = CompositorDetector.detect_compositor()
    monitor_manager = MonitorManager(compositor)
    
    command = args[1]
    
    # Parse optional monitor parameter
    monitor = None
    if "--monitor" in args:
        monitor_idx = args.index("--monitor")
        if monitor_idx + 1 < len(args):
            monitor = args[monitor_idx + 1]
    
    # Parse optional matugen scheme parameter
    matugen_scheme = None
    if "--matugen" in args:
        matugen_idx = args.index("--matugen")
        if matugen_idx + 1 < len(args):
            scheme_name = args[matugen_idx + 1]
            # Ensure scheme has proper prefix
            if not scheme_name.startswith('scheme-'):
                scheme_name = f'scheme-{scheme_name}'
            matugen_scheme = scheme_name
            # Set the scheme for this session
            wallpaper_setter.set_matugen_scheme(matugen_scheme)
            print(f"🎨 Using matugen scheme: {matugen_scheme}")
    
    if command == "--random":
        # Set random wallpaper with monitor-aware behavior
        wallpapers = []
        for file_path in config.wallpaper_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in config.image_extensions:
                wallpapers.append(file_path)
        
        if wallpapers:
            import random
            random_wallpaper = random.choice(wallpapers)
            current_effect = wallpaper_setter.get_current_effect()
            transition = wallpaper_setter.get_transition_effect()
            
            # Check keybind mode and determine target monitor
            keybind_mode = wallpaper_setter.get_keybind_mode()
            target_monitor = monitor  # Use explicit monitor if provided
            
            if not target_monitor and keybind_mode == 'active':
                # Get focused monitor for active-only mode
                target_monitor = monitor_manager.get_focused_monitor()
                if target_monitor:
                    print(f"🎯 Targeting active monitor: {target_monitor}")
            
            success = wallpaper_setter.set_wallpaper(random_wallpaper, target_monitor, transition, current_effect)
            if success:
                if target_monitor:
                    monitor_text = f" on {target_monitor}"
                elif keybind_mode == 'active':
                    monitor_text = " on active monitor"
                else:
                    monitor_text = " on all monitors"
                print(f"✅ Set random wallpaper: {random_wallpaper.name}{monitor_text}")
            else:
                print("❌ Failed to set random wallpaper")
        else:
            print("❌ No wallpapers found")
        return True
    
    elif command == "--effect" and len(args) >= 3:
        # Set photo effect and apply to current wallpaper with monitor-aware behavior
        effect = args[2]
        
        # Get current wallpaper
        current_wallpaper_link = config.current_wallpaper
        if current_wallpaper_link.exists():
            try:
                current_wallpaper = Path(current_wallpaper_link.readlink())
                transition = wallpaper_setter.get_transition_effect()
                
                # Check keybind mode and determine target monitor
                keybind_mode = wallpaper_setter.get_keybind_mode()
                target_monitor = monitor  # Use explicit monitor if provided
                
                if not target_monitor and keybind_mode == 'active':
                    # Get focused monitor for active-only mode
                    target_monitor = monitor_manager.get_focused_monitor()
                    if target_monitor:
                        print(f"🎯 Targeting active monitor: {target_monitor}")
                
                # Apply the new effect to the current wallpaper
                success = wallpaper_setter.set_wallpaper(current_wallpaper, target_monitor, transition, effect)
                if success:
                    if target_monitor:
                        monitor_text = f" on {target_monitor}"
                    elif keybind_mode == 'active':
                        monitor_text = " on active monitor"
                    else:
                        monitor_text = " on all monitors"
                    print(f"✅ Applied {effect} effect to current wallpaper{monitor_text}")
                else:
                    print(f"❌ Failed to apply {effect} effect")
            except Exception as e:
                print(f"❌ Error applying effect: {e}")
        else:
            # No current wallpaper, just set the effect for future use
            wallpaper_setter.set_current_effect(effect)
            print(f"✅ Set photo effect: {effect} (will apply to next wallpaper)")
        
        return True
    
    elif command == "--keybind-mode":
        # Set or get keybind mode
        if len(args) >= 3:
            mode = args[2].lower()
            if mode in ['all', 'active']:
                wallpaper_setter.set_keybind_mode(mode)
                mode_text = "All Monitors" if mode == 'all' else "Active Monitor Only"
                print(f"⌨️ Keybind behavior set to: {mode_text}")
            else:
                print("❌ Invalid mode. Use 'all' or 'active'")
        else:
            # Get current mode
            current_mode = wallpaper_setter.get_keybind_mode()
            mode_text = "All Monitors" if current_mode == 'all' else "Active Monitor Only"
            print(f"⌨️ Current keybind behavior: {mode_text} ({current_mode})")
        return True
    
    elif command == "--refresh-colors":
        # Refresh matugen colors for current wallpaper
        if wallpaper_setter.is_matugen_enabled():
            current_wallpaper_link = config.current_wallpaper
            if current_wallpaper_link.exists():
                try:
                    current_wallpaper = Path(current_wallpaper_link.readlink())
                    success = wallpaper_setter.update_matugen_colors(current_wallpaper)
                    if success:
                        print("✅ Refreshed matugen colors")
                    else:
                        print("❌ Failed to refresh colors")
                except Exception as e:
                    print(f"❌ Error refreshing colors: {e}")
            else:
                print("❌ No current wallpaper found")
        else:
            print("❌ Matugen is not enabled")
        return True
    
    elif command == "--version":
        # Show version information
        print(f"Wall-IT v{__version__}")
        print("Professional wallpaper manager with system integration")
        print("Features: Monitor scaling, Photo effects, Weather animations, Hyprland support")
        return True
    
    
    return False

def main():
    """Main entry point"""
    # Handle command line arguments first
    if handle_command_line_args(sys.argv):
        return 0
    
    print("🖼️ Starting Wall-IT...")
    print("✅ Features: System tray, Monitor scaling, Timer, Photo effects, Web interface")
    app = WallpaperApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    main()
