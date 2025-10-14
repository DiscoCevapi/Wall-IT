#!/usr/bin/env python3
import json
import os
import time
from pathlib import Path
import subprocess

def load_settings():
    settings = {'opacity': '0.85', 'position': 'top'}
    try:
        with open(str(Path.home() / '.config/waybar/settings.conf')) as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=')
                    settings[key] = value
    except Exception:
        pass
    return settings

def read_original_css():
    """Read the original CSS file and extract the structure"""
    try:
        with open(str(Path.home() / '.config/waybar/style.css'), 'r') as f:
            return f.read()
    except Exception:
        return ""

def generate_waybar_css(colors):
    settings = load_settings()
    original_css = read_original_css()

    # Extract any existing CSS variables
    css_vars = ""
    if ':root {' in original_css:
        start = original_css.find(':root {')
        end = original_css.find('}', start)
        if start != -1 and end != -1:
            css_vars = original_css[start:end+1] + '\n\n'

    # Update opacity in the original CSS
    css = original_css
    for opacity_pattern in ['background: rgba(0, 0, 0, [0-9.]+)', 'background-color: rgba(0, 0, 0, [0-9.]+)']:
        import re
        matches = re.findall(opacity_pattern, css)
        for match in matches:
            css = css.replace(match, match.rsplit(',', 1)[0] + f", {settings['opacity']})")

    return css

def hex_to_rgb(hex_color):
    # Remove the '#' if present
    hex_color = hex_color.lstrip('#')
    # Convert to RGB values
    r = int(hex_color[:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:], 16)
    return f"{r}, {g}, {b}"

def update_waybar_colors():
    cache_dir = Path.home() / ".cache" / "wall-it"
    colors_file = cache_dir / "matugen_colors.json"
    css_file = Path.home() / ".config" / "waybar" / "style.css"
    
    if not colors_file.exists():
        print("No matugen colors found")
        return
    
    try:
        with open(colors_file) as f:
            data = json.load(f)
            raw_colors = data.get('colors', {})
            
            # Handle matugen v2.x format with dark/light themes
            if 'dark' in raw_colors:
                colors = raw_colors['dark']  # Use dark theme colors
            else:
                colors = raw_colors  # Fallback for older format
            
        # Convert hex colors to RGB for CSS
        css_colors = {}
        for key, value in colors.items():
            css_colors[key] = hex_to_rgb(value)
        
        # Generate and save CSS
        css_content = generate_waybar_css(css_colors)
        css_file.parent.mkdir(parents=True, exist_ok=True)
        css_file.write_text(css_content)
        
        # Send reload signal to waybar instead of restarting
        try:
            subprocess.run(['pkill', '-SIGUSR2', 'waybar'], stderr=subprocess.DEVNULL)
        except:
            # If signal fails, waybar might not be running or doesn't support reload
            pass
        
        print("Updated waybar colors")
        
    except Exception as e:
        print(f"Error updating waybar colors: {e}")

def main():
    last_mtime = 0
    cache_dir = Path.home() / ".cache" / "wall-it"
    colors_file = cache_dir / "matugen_colors.json"
    
    while True:
        try:
            if colors_file.exists():
                mtime = colors_file.stat().st_mtime
                if mtime > last_mtime:
                    update_waybar_colors()
                    last_mtime = mtime
            time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()