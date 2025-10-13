#!/usr/bin/env python3
"""
Wall-IT Hyprland Backend
Provides Hyprland-specific functionality for wallpaper management
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class HyprlandBackend:
    """Backend for Hyprland Wayland compositor"""
    
    def __init__(self):
        self.name = "Hyprland"
        self.verify_tools()
        self.swww_available = self._check_swww_daemon()
    
    def verify_tools(self):
        """Verify that required Hyprland tools are available"""
        required_tools = ['hyprctl', 'swww']
        missing_tools = []
        
        for tool in required_tools:
            try:
                subprocess.run(['which', tool], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                missing_tools.append(tool)
        
        if missing_tools:
            print(f"Warning: Missing required tools for Hyprland backend: {', '.join(missing_tools)}", file=sys.stderr)
    
    def _check_swww_daemon(self) -> bool:
        """Check if swww daemon is running"""
        try:
            result = subprocess.run(['swww', 'query'], capture_output=True, text=True, timeout=2)
            return result.returncode == 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def is_available(self) -> bool:
        """Check if Hyprland backend is available on this system"""
        try:
            # Check if we're running Hyprland
            import os
            current_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '')
            if 'Hyprland' not in current_desktop:
                return False
            
            # Check if hyprctl is available and responding
            subprocess.run(['hyprctl', 'monitors'], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_monitors(self) -> List[Dict[str, str]]:
        """Get list of available monitors with their properties"""
        monitors = []
        
        try:
            # Get monitor information from hyprctl
            result = subprocess.run(['hyprctl', 'monitors', '-j'], capture_output=True, text=True, check=True)
            monitors_data = json.loads(result.stdout)
            
            for monitor in monitors_data:
                name = monitor.get('name', 'Unknown')
                width = monitor.get('width', 0)
                height = monitor.get('height', 0)
                is_primary = monitor.get('focused', False)
                
                monitors.append({
                    'id': name,
                    'name': name,
                    'connector': name,
                    'resolution': f"{width}x{height}",
                    'primary': is_primary
                })
            
        except subprocess.CalledProcessError as e:
            print(f"Error getting monitors: {e}", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"Error parsing monitor data: {e}", file=sys.stderr)
        
        return monitors
    
    def get_active_monitor(self) -> Optional[str]:
        """Get the currently active/focused monitor"""
        try:
            result = subprocess.run(['hyprctl', 'monitors', '-j'], capture_output=True, text=True, check=True)
            monitors_data = json.loads(result.stdout)
            
            for monitor in monitors_data:
                if monitor.get('focused', False):
                    return monitor.get('name')
            
            # Fallback to first monitor if no focused monitor found
            if monitors_data:
                return monitors_data[0].get('name')
                
        except Exception as e:
            print(f"Error getting active monitor: {e}", file=sys.stderr)
        
        return None
    
    def get_monitor_by_connector(self, connector: str) -> Optional[Dict[str, str]]:
        """Get monitor information by connector name"""
        monitors = self.get_monitors()
        for monitor in monitors:
            if monitor['connector'] == connector:
                return monitor
        return None
    
    def set_wallpaper(self, wallpaper_path: Path, monitor: Optional[str] = None, transition: str = 'fade') -> bool:
        """Set wallpaper on specific monitor or all monitors using swww"""
        if not self.swww_available:
            print("Error: swww daemon is not running. Please start it with 'swww init'", file=sys.stderr)
            return False
            
        try:
            # Generate colors with matugen first (before setting wallpaper)
            matugen_success = self._generate_matugen_colors(wallpaper_path)
            
            cmd = ['swww', 'img', str(wallpaper_path)]
            
            # Add transition settings
            if transition != 'none':
                cmd.extend([
                    '--transition-type', transition,
                    '--transition-fps', '30',
                    '--transition-duration', '1.5'
                ])
            
            # Add monitor targeting if specified
            if monitor:
                cmd.extend(['--outputs', monitor])
                print(f"Wall-IT: Setting wallpaper on monitor {monitor} with {transition} transition")
            else:
                print(f"Wall-IT: Setting wallpaper on all monitors with {transition} transition")
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            if matugen_success:
                print(f"Wall-IT: Generated dynamic colors with matugen")
            
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            print(f"Error setting wallpaper with swww: {error_msg}", file=sys.stderr)
            return False
    
    def get_current_wallpaper(self, monitor: Optional[str] = None) -> Optional[Path]:
        """Get current wallpaper for specific monitor or primary monitor"""
        try:
            if not monitor:
                monitor = self.get_active_monitor()
                if not monitor:
                    return None
            
            result = subprocess.run(['swww', 'query'], capture_output=True, text=True, check=True)
            for line in result.stdout.split('\n'):
                if f"Output {monitor}:" in line:
                    # Try to extract the file path
                    parts = line.split("'")
                    if len(parts) >= 2:
                        path = Path(parts[1])
                        if path.exists():
                            return path
                    break
                    
        except subprocess.CalledProcessError as e:
            print(f"Error getting current wallpaper: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error getting current wallpaper: {e}", file=sys.stderr)
        
        return None
    
    def supports_per_monitor_wallpapers(self) -> bool:
        """Check if the backend supports per-monitor wallpapers"""
        return self.swww_available  # swww supports per-monitor wallpapers
    
    def supports_transitions(self) -> bool:
        """Check if the backend supports wallpaper transitions"""
        return self.swww_available  # swww provides transition support
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported wallpaper formats"""
        return ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff']
    
    def suggest_hyprland_keybind_setup(self):
        """Suggest keybind setup commands for Hyprland"""
        print("\n🔧 Hyprland Keybind Setup Suggestions:")
        print("Add these lines to your Hyprland config (~/.config/hypr/hyprland.conf):")
        print("\n# Wall-IT Keybinds")
        print("bind = $mainMod ALT, N, exec, ~/.local/bin/wall-it-next")
        print("bind = $mainMod ALT, P, exec, ~/.local/bin/wall-it-prev")
        print("bind = $mainMod ALT, G, exec, ~/.local/bin/wallpaper-gui.py")
    
    def _check_matugen_available(self) -> bool:
        """Check if matugen is available for color generation"""
        try:
            subprocess.run(['matugen', '--version'], capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _get_matugen_scheme(self) -> str:
        """Get matugen color scheme from cache or use default"""
        try:
            cache_dir = Path.home() / ".cache" / "wall-it"
            scheme_file = cache_dir / "matugen_scheme"
            if scheme_file.exists():
                scheme = scheme_file.read_text().strip()
                # Fix old scheme names to new format
                if scheme in ['content', 'expressive', 'fidelity', 'fruit-salad', 'monochrome', 'neutral', 'rainbow', 'tonal-spot']:
                    scheme = f'scheme-{scheme}'
                return scheme
        except Exception:
            pass
        return 'scheme-expressive'  # Default scheme
    
    def _is_matugen_enabled(self) -> bool:
        """Check if matugen is enabled in Wall-IT config"""
        try:
            cache_dir = Path.home() / ".cache" / "wall-it"
            matugen_file = cache_dir / "matugen_enabled"
            if matugen_file.exists():
                return matugen_file.read_text().strip().lower() == 'true'
        except Exception:
            pass
        return True  # Default to enabled if matugen is available
    
    def _generate_matugen_colors(self, wallpaper_path: Path) -> bool:
        """Generate colors using matugen for theme integration"""
        if not self._check_matugen_available() or not self._is_matugen_enabled():
            return False
        
        try:
            scheme = self._get_matugen_scheme()
            cmd = [
                'matugen', 'image', str(wallpaper_path),
                '--mode', 'dark',
                '--type', scheme,
                '--json', 'hex'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
            
            # Store the generated colors for integration
            cache_dir = Path.home() / ".cache" / "wall-it"
            cache_dir.mkdir(parents=True, exist_ok=True)
            colors_file = cache_dir / "matugen_colors.json"
            colors_file.write_text(result.stdout)
            
            # Apply colors to compatible applications
            self._update_gtk_colors(json.loads(result.stdout).get('colors', {}))
            self._update_terminal_colors(json.loads(result.stdout).get('colors', {}))
            
            return True
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"Warning: matugen failed: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Warning: matugen error: {e}", file=sys.stderr)
            return False
    
    def _update_gtk_colors(self, colors: Dict):
        """Update GTK applications with matugen colors"""
        try:
            # Update GTK theme colors
            gtk_config = Path.home() / ".config" / "gtk-3.0" / "gtk.css"
            gtk_config.parent.mkdir(parents=True, exist_ok=True)
            
            css_content = f"""/* Wall-IT Generated Colors */
:root {{
  --wall-it-primary: {colors.get('primary', '#6366f1')};
  --wall-it-secondary: {colors.get('secondary', '#8b5cf6')};
  --wall-it-background: {colors.get('surface', '#1f2937')};
  --wall-it-text: {colors.get('on_surface', '#ffffff')};
}}
"""
            
            # Append to existing GTK CSS (don't overwrite)
            if gtk_config.exists():
                existing = gtk_config.read_text()
                if "/* Wall-IT Generated Colors */" not in existing:
                    css_content = existing + "\n\n" + css_content
                else:
                    # Replace existing Wall-IT section
                    lines = existing.split('\n')
                    new_lines = []
                    skip = False
                    for line in lines:
                        if "/* Wall-IT Generated Colors */" in line:
                            skip = True
                        elif skip and line.startswith('}'):
                            skip = False
                            continue
                        if not skip:
                            new_lines.append(line)
                    css_content = '\n'.join(new_lines) + "\n\n" + css_content
            
            gtk_config.write_text(css_content)
            
        except Exception as e:
            print(f"Warning: Could not update GTK colors: {e}", file=sys.stderr)
    
    def _update_terminal_colors(self, colors: Dict):
        """Update terminal applications with matugen colors"""
        try:
            # Export colors as environment variables
            color_env = Path.home() / ".cache" / "wall-it" / "terminal_colors.sh"
            
            env_content = f"""#!/bin/bash
# Wall-IT Generated Terminal Colors
export WALL_IT_PRIMARY='{colors.get('primary', '#6366f1')}'
export WALL_IT_SECONDARY='{colors.get('secondary', '#8b5cf6')}'
export WALL_IT_BACKGROUND='{colors.get('surface', '#1f2937')}'
export WALL_IT_TEXT='{colors.get('on_surface', '#ffffff')}'
export WALL_IT_ACCENT='{colors.get('tertiary', '#f59e0b')}'
"""
            
            color_env.write_text(env_content)
            color_env.chmod(0o755)
            
        except Exception as e:
            print(f"Warning: Could not update terminal colors: {e}", file=sys.stderr)


def test_hyprland_backend():
    """Test function for Hyprland backend"""
    backend = HyprlandBackend()
    
    print("=" * 50)
    print("🚀 Wall-IT Hyprland Backend Test")
    print("=" * 50)
    
    # Basic availability
    print(f"Hyprland Backend Available: {backend.is_available()}")
    print(f"swww Daemon Available: {backend.swww_available}")
    print(f"matugen Available: {backend._check_matugen_available()}")
    print(f"matugen Enabled: {backend._is_matugen_enabled()}")
    
    # Feature support
    print(f"Supports Per-Monitor: {backend.supports_per_monitor_wallpapers()}")
    print(f"Supports Transitions: {backend.supports_transitions()}")
    
    # Monitor information
    monitors = backend.get_monitors()
    print(f"\n🖥️ Monitors ({len(monitors)}):")
    for monitor in monitors:
        primary_text = " (Primary)" if monitor.get('primary', False) else ""
        print(f"  {monitor['name']}: {monitor.get('resolution', 'Unknown')}{primary_text}")
    
    active = backend.get_active_monitor()
    print(f"\n📍 Active Monitor: {active}")
    
    # Current wallpapers
    print(f"\n🖼️ Current Wallpapers:")
    for monitor in monitors:
        current = backend.get_current_wallpaper(monitor['connector'])
        current_name = current.name if current else "None"
        print(f"  {monitor['connector']}: {current_name}")
    
    # Show keybind suggestions
    backend.suggest_hyprland_keybind_setup()
    
    print("\n✅ Hyprland Backend Test Complete")


if __name__ == "__main__":
    test_hyprland_backend()