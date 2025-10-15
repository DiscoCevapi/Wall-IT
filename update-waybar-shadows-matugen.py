#!/usr/bin/env python3
"""
Efficient Waybar Shadow Color Updater
Uses existing matugen colors instead of doing separate image analysis
"""

import json
import re
import subprocess
import sys
from pathlib import Path
import colorsys


class MatugenShadowUpdater:
    def __init__(self):
        self.waybar_style_path = Path.home() / ".config" / "waybar" / "style.css"
        self.matugen_colors_path = Path.home() / ".cache" / "wall-it" / "matugen_colors.json"
        self.cache_dir = Path.home() / ".cache" / "wall-it"
        
    def load_matugen_colors(self):
        """Load colors from matugen cache"""
        try:
            if not self.matugen_colors_path.exists():
                return None
                
            with open(self.matugen_colors_path, 'r') as f:
                data = json.load(f)
                
            # Extract dark theme colors (preferred for shadows)
            colors = data.get('colors', {}).get('dark', {})
            if not colors:
                colors = data.get('colors', {}).get('light', {})
                
            return colors
            
        except Exception as e:
            print(f"Error loading matugen colors: {e}")
            return None
    
    def select_shadow_color_from_matugen(self, colors):
        """Select best color for shadows from matugen palette"""
        if not colors:
            return (255, 95, 31)  # fallback orange
        
        # Priority order for shadow colors
        color_priorities = [
            'primary',           # Main accent color
            'tertiary',         # Third accent color  
            'secondary',        # Secondary color
            'surface_tint',     # Surface tint
            'primary_container', # Primary container
            'tertiary_container' # Tertiary container
        ]
        
        # Try each priority color
        for color_key in color_priorities:
            if color_key in colors:
                hex_color = colors[color_key]
                rgb = self.hex_to_rgb(hex_color)
                if rgb and self.is_suitable_for_shadow(rgb):
                    return self.enhance_for_shadow(rgb)
        
        # Fallback: try any colorful color
        for key, hex_color in colors.items():
            if 'on_' not in key and 'outline' not in key and 'shadow' not in key:
                rgb = self.hex_to_rgb(hex_color)
                if rgb and self.is_suitable_for_shadow(rgb):
                    return self.enhance_for_shadow(rgb)
        
        return (255, 95, 31)  # final fallback
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        try:
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except:
            pass
        return None
    
    def is_suitable_for_shadow(self, rgb):
        """Check if color is suitable for shadow (not too dark/light, has saturation)"""
        r, g, b = rgb
        brightness = (r + g + b) / 3
        
        # Convert to HSV to check saturation
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        
        # Accept colors with reasonable brightness and some saturation
        return 30 < brightness < 200 and s > 0.1
    
    def enhance_for_shadow(self, rgb):
        """Enhance color for maximum shadow visibility"""
        r, g, b = rgb
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        
        # Maximize saturation and brightness for vivid shadows
        s = min(1.0, s * 1.3)  # Boost saturation
        v = 0.95  # Near maximum brightness for visibility
        
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return (int(r * 255), int(g * 255), int(b * 255))
    
    def update_waybar_css(self, shadow_color):
        """Update waybar CSS with new shadow color"""
        try:
            if not self.waybar_style_path.exists():
                print(f"Waybar style file not found: {self.waybar_style_path}")
                return False
            
            r, g, b = shadow_color
            new_shadow = f"rgba({r}, {g}, {b}, 1.0)"
            
            # Read current CSS
            css_content = self.waybar_style_path.read_text()
            
            # Replace ONLY box-shadow declarations
            shadow_pattern = r'(box-shadow:\s*0\s+0\s+7px\s+)rgba\([^)]+\);'
            new_shadow_declaration = rf'\g<1>{new_shadow};'
            
            updated_css = re.sub(shadow_pattern, new_shadow_declaration, css_content)
            
            # Write back to file
            self.waybar_style_path.write_text(updated_css)
            
            print(f"✅ Updated waybar shadows to: {new_shadow}")
            return True
            
        except Exception as e:
            print(f"Error updating waybar CSS: {e}")
            return False
    
    def reload_waybar(self):
        """Reload waybar to apply new styles"""
        try:
            # Send SIGUSR2 to waybar to reload
            result = subprocess.run(['pkill', '-SIGUSR2', 'waybar'], 
                                 capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Waybar reloaded")
                return True
        except Exception as e:
            print(f"Error reloading waybar: {e}")
        return False
    
    def update_from_matugen(self):
        """Main function to update shadows from matugen colors"""
        print("🎨 Updating waybar shadows from matugen colors")
        
        # Load matugen colors
        colors = self.load_matugen_colors()
        if not colors:
            print("❌ No matugen colors found - run wallpaper change first")
            return False
        
        # Select shadow color
        shadow_color = self.select_shadow_color_from_matugen(colors)
        print(f"✨ Selected shadow color: rgb{shadow_color}")
        
        # Update CSS and reload
        if self.update_waybar_css(shadow_color):
            self.reload_waybar()
            return True
        
        return False


def main():
    updater = MatugenShadowUpdater()
    success = updater.update_from_matugen()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()