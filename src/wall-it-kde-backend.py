#!/usr/bin/env python3
"""
Wall-IT KDE Backend
Provides KDE/Plasma-specific functionality for wallpaper management
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class KDEBackend:
    """Backend for KDE/Plasma desktop environment"""
    
    def __init__(self):
        self.name = "KDE"
        self.verify_tools()
        self.swww_available = self._check_swww_daemon()
    
    def verify_tools(self):
        """Verify that required KDE tools are available"""
        required_tools = ['qdbus', 'plasma-apply-wallpaperimage', 'xrandr']
        missing_tools = []
        
        for tool in required_tools:
            try:
                subprocess.run(['which', tool], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                missing_tools.append(tool)
        
        if missing_tools:
            print(f"Warning: Missing required tools for KDE backend: {', '.join(missing_tools)}", file=sys.stderr)
    
    def _check_swww_daemon(self) -> bool:
        """Check if swww daemon is running for hybrid transition support"""
        try:
            result = subprocess.run(['swww', 'query'], capture_output=True, text=True, timeout=2)
            return result.returncode == 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def is_available(self) -> bool:
        """Check if KDE backend is available on this system"""
        try:
            # Check if we're running KDE
            import os
            current_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '')
            if 'KDE' not in current_desktop:
                return False
            
            # Check if plasma is running
            subprocess.run(['qdbus', 'org.kde.plasmashell'], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_monitors(self) -> List[Dict[str, str]]:
        """Get list of available monitors with their properties"""
        monitors = []
        
        try:
            # Get monitor information from xrandr
            result = subprocess.run(['xrandr', '--listmonitors'], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')[1:]  # Skip header line
            
            for line in lines:
                if ':' in line:
                    parts = line.strip().split()
                    monitor_id = parts[0].rstrip(':')
                    monitor_name = parts[-1]  # Last part is usually the connector name
                    
                    # Extract resolution and position from the format like "+*DP-1 4763/920x1994/430+0+0  DP-1"
                    if 'x' in line and len(parts) >= 3:
                        res_part = parts[2]  # Get the resolution part (third element)
                        resolution_info = "Unknown"
                        
                        # Try to parse resolution from format like "4763/920x1994/430+0+0"
                        if 'x' in res_part:
                            try:
                                # Format: WIDTH/PHYSICALxHEIGHT/PHYSICAL+X+Y
                                # We want to extract the logical resolution (first numbers)
                                import re
                                match = re.match(r'[+*]?(\d+)/\d+x(\d+)/\d+', res_part)
                                if match:
                                    width, height = match.groups()
                                    resolution_info = f"{width}x{height}"
                                else:
                                    # Fallback parsing
                                    x_parts = res_part.split('x')
                                    if len(x_parts) >= 2:
                                        width = x_parts[0].split('/')[-1].lstrip('+*')
                                        height = x_parts[1].split('/')[0].split('+')[0]
                                        resolution_info = f"{width}x{height}"
                            except Exception:
                                resolution_info = "Unknown"
                        
                        # Check if this is the primary monitor (look in the original line for *)
                        is_primary = '*' in line
                        
                        monitors.append({
                            'id': monitor_id,
                            'name': monitor_name,
                            'connector': monitor_name,
                            'resolution': resolution_info,
                            'primary': is_primary
                        })
            
            # Also get KDE desktop information
            try:
                result = subprocess.run([
                    'qdbus', 'org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell.evaluateScript',
                    'for (i = 0; i < desktops().length; i++) { d = desktops()[i]; print("desktop:" + i + ":screen:" + d.screen); }'
                ], capture_output=True, text=True, check=True)
                
                desktop_info = {}
                for line in result.stdout.strip().split('\n'):
                    if 'desktop:' in line and 'screen:' in line:
                        parts = line.split(':')
                        if len(parts) >= 4:
                            desktop_id = parts[1]
                            screen_id = parts[3]
                            desktop_info[screen_id] = desktop_id
                
                # Add desktop info to monitors
                for i, monitor in enumerate(monitors):
                    monitor['kde_desktop_id'] = desktop_info.get(str(i), str(i))
                    
            except subprocess.CalledProcessError:
                # Fallback: assign desktop IDs based on order
                for i, monitor in enumerate(monitors):
                    monitor['kde_desktop_id'] = str(i)
                    
        except subprocess.CalledProcessError as e:
            print(f"Error getting monitors: {e}", file=sys.stderr)
        
        return monitors
    
    def get_active_monitor(self) -> Optional[str]:
        """Get the currently active/focused monitor"""
        try:
            # In KDE, we can try to detect the active monitor by looking at mouse position
            # or current window focus, but this is complex. For now, we'll use the primary monitor
            monitors = self.get_monitors()
            
            # First try to find primary monitor
            for monitor in monitors:
                if monitor.get('primary', False):
                    return monitor['connector']
            
            # Fallback to first monitor
            if monitors:
                return monitors[0]['connector']
                
        except Exception as e:
            print(f"Error getting active monitor: {e}", file=sys.stderr)
        
        return None
    
    def get_monitor_by_connector(self, connector: str) -> Optional[Dict[str, str]]:
        """Get monitor information by connector name (e.g., 'DP-1', 'HDMI-A-2')"""
        monitors = self.get_monitors()
        for monitor in monitors:
            if monitor['connector'] == connector:
                return monitor
        return None
    
    def set_wallpaper(self, wallpaper_path: Path, monitor: Optional[str] = None, transition: str = 'fade') -> bool:
        """Set wallpaper on specific monitor or all monitors (hybrid KDE+swww approach)"""
        try:
            # Hybrid approach: Use swww for transitions if available, KDE for monitor-specific control
            if self.swww_available and transition != 'none':
                return self._set_wallpaper_swww(wallpaper_path, monitor, transition)
            else:
                return self._set_wallpaper_kde_native(wallpaper_path, monitor)
            
        except Exception as e:
            print(f"Error setting wallpaper: {e}", file=sys.stderr)
            return False
    
    def _set_wallpaper_swww(self, wallpaper_path: Path, monitor: Optional[str] = None, transition: str = 'fade') -> bool:
        """Set wallpaper using swww for beautiful transitions with matugen support"""
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
                print(f"Wall-IT: Setting wallpaper on monitor {monitor} with {transition} transition (swww)")
            else:
                print(f"Wall-IT: Setting wallpaper on all monitors with {transition} transition (swww)")
            
            if matugen_success:
                print(f"Wall-IT: Generated dynamic colors with matugen")
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Apply KDE-specific color integration if matugen succeeded
            if matugen_success:
                self._apply_kde_colors()
            
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            print(f"Error setting wallpaper with swww: {error_msg}", file=sys.stderr)
            # Fallback to KDE native method
            print("Falling back to KDE native wallpaper setting", file=sys.stderr)
            return self._set_wallpaper_kde_native(wallpaper_path, monitor)
    
    def _set_wallpaper_kde_native(self, wallpaper_path: Path, monitor: Optional[str] = None) -> bool:
        """Set wallpaper using native KDE methods (no transitions) with matugen support"""
        try:
            # Generate colors with matugen for KDE native method too
            matugen_success = self._generate_matugen_colors(wallpaper_path)
            
            # Always use plasma-apply-wallpaperimage for reliability
            subprocess.run([
                'plasma-apply-wallpaperimage', str(wallpaper_path)
            ], check=True, capture_output=True)
            
            print(f"Wall-IT: Set wallpaper using KDE native method")
            
            # Apply KDE-specific color integration if matugen succeeded
            if matugen_success:
                self._apply_kde_colors()
                print(f"Wall-IT: Generated dynamic colors with matugen")
            
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            print(f"Error setting wallpaper with KDE: {error_msg}", file=sys.stderr)
            return False
    
    def get_current_wallpaper(self, monitor: Optional[str] = None) -> Optional[Path]:
        """Get current wallpaper for specific monitor or primary monitor"""
        try:
            if monitor:
                monitor_info = self.get_monitor_by_connector(monitor)
                if monitor_info:
                    kde_desktop_id = monitor_info.get('kde_desktop_id', '0')
                    
                    # Query current wallpaper using KDE's desktop scripting
                    script = f'''
                    var desktop = desktops()[{kde_desktop_id}];
                    if (desktop) {{
                        desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
                        var image = desktop.readConfig("Image");
                        print(image);
                    }}
                    '''
                    
                    result = subprocess.run([
                        'qdbus', 'org.kde.plasmashell', '/PlasmaShell', 
                        'org.kde.PlasmaShell.evaluateScript', script
                    ], capture_output=True, text=True, check=True)
                    
                    wallpaper_url = result.stdout.strip()
                    if wallpaper_url.startswith('file://'):
                        wallpaper_path = Path(wallpaper_url[7:])  # Remove 'file://' prefix
                        if wallpaper_path.exists():
                            return wallpaper_path
            else:
                # Fallback to reading from first monitor
                monitors = self.get_monitors()
                if monitors:
                    return self.get_current_wallpaper(monitors[0]['connector'])
                    
        except subprocess.CalledProcessError as e:
            print(f"Error getting current wallpaper: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error getting current wallpaper: {e}", file=sys.stderr)
        
        return None
    
    def supports_per_monitor_wallpapers(self) -> bool:
        """Check if the backend supports per-monitor wallpapers"""
        return True  # KDE supports per-monitor wallpapers
    
    def supports_transitions(self) -> bool:
        """Check if the backend supports wallpaper transitions"""
        # KDE supports transitions via swww if daemon is running (hybrid mode)
        return self.swww_available
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported wallpaper formats"""
        return ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.svg']
    
    def suggest_kde_keybind_setup(self):
        """Suggest keybind setup commands for KDE Plasma"""
        print("\n🔧 KDE Keybind Setup Suggestions:")
        print("1. Open System Settings → Shortcuts → Custom Shortcuts")
        print("2. Create a new group called 'Wall-IT'")
        print("3. Add these shortcuts:")
        print("   • Next Wallpaper: ~/.local/bin/wall-it-next (Ctrl+Alt+N)")
        print("   • Previous Wallpaper: ~/.local/bin/wall-it-prev (Ctrl+Alt+P)")
        print("   • Open GUI: ~/.local/bin/wallpaper-gui.py (Ctrl+Alt+G)")
        print("\n💡 Alternative: Use KDE's built-in shortcuts section in System Settings")
    
    def check_plasma_version(self) -> str:
        """Check Plasma version for compatibility"""
        try:
            result = subprocess.run([
                'qdbus', 'org.kde.plasmashell', '/PlasmaShell',
                'org.freedesktop.DBus.Properties.Get',
                'org.kde.PlasmaShell', 'plasmaVersion'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                version = result.stdout.strip()
                return version
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            # Fallback method
            try:
                result = subprocess.run(['plasmashell', '--version'], capture_output=True, text=True, timeout=3)
                for line in result.stdout.split('\n'):
                    if 'plasmashell' in line.lower():
                        parts = line.split()
                        if len(parts) > 1:
                            return parts[-1]
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        return "Unknown"
    
    def get_kde_theme_info(self) -> Dict[str, str]:
        """Get current KDE theme information"""
        theme_info = {}
        
        try:
            # Get Plasma theme
            result = subprocess.run([
                'kreadconfig5', '--group', 'Theme', '--key', 'name'
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                theme_info['plasma_theme'] = result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        try:
            # Get color scheme
            result = subprocess.run([
                'kreadconfig5', '--group', 'General', '--key', 'ColorScheme'
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                theme_info['color_scheme'] = result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return theme_info
    
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
        """Generate colors using matugen for KDE integration"""
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
            
            # Store the generated colors for KDE integration
            cache_dir = Path.home() / ".cache" / "wall-it"
            cache_dir.mkdir(parents=True, exist_ok=True)
            colors_file = cache_dir / "matugen_colors.json"
            colors_file.write_text(result.stdout)
            
            return True
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"Warning: matugen failed: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Warning: matugen error: {e}", file=sys.stderr)
            return False
    
    def _apply_kde_colors(self):
        """Apply matugen colors to KDE/Plasma themes and applications"""
        try:
            cache_dir = Path.home() / ".cache" / "wall-it"
            colors_file = cache_dir / "matugen_colors.json"
            
            if not colors_file.exists():
                return
            
            import json
            colors_data = json.loads(colors_file.read_text())
            
            if 'colors' not in colors_data:
                return
            
            colors = colors_data['colors']
            
            # Apply to common applications that respect matugen colors
            self._update_gtk_colors(colors)
            self._update_terminal_colors(colors)
            # Note: KDE/Plasma theming is complex and usually handled by dedicated theme tools
            # We focus on applications that can be easily themed
            
            print("Wall-IT: Applied dynamic colors to compatible applications")
            
        except Exception as e:
            print(f"Warning: Could not apply KDE colors: {e}", file=sys.stderr)
    
    def _update_gtk_colors(self, colors: Dict):
        """Update GTK applications with matugen colors"""
        try:
            # This is a simplified approach - full GTK theming would require more complex CSS generation
            gtk_config = Path.home() / ".config" / "gtk-3.0" / "gtk.css"
            gtk_config.parent.mkdir(parents=True, exist_ok=True)
            
            # Basic color variables that some GTK apps might use
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
        """Update terminal applications with matugen colors (basic support)"""
        try:
            # Export colors as environment variables for terminal apps that support them
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


def test_kde_backend():
    """Test function for KDE backend with hybrid support and enhanced features"""
    backend = KDEBackend()
    
    print("=" * 50)
    print("🪩 Wall-IT KDE Backend Test")
    print("=" * 50)
    
    # Basic availability
    print(f"KDE Backend Available: {backend.is_available()}")
    print(f"Plasma Version: {backend.check_plasma_version()}")
    
    # Feature support
    print(f"Supports Per-Monitor: {backend.supports_per_monitor_wallpapers()}")
    print(f"Supports Transitions: {backend.supports_transitions()}")
    print(f"swww Daemon Available: {backend.swww_available}")
    print(f"matugen Available: {backend._check_matugen_available()}")
    print(f"matugen Enabled: {backend._is_matugen_enabled()}")
    
    # Operating mode
    if backend.swww_available:
        matugen_text = " + matugen colors" if backend._check_matugen_available() else ""
        print(f"\n🎨 Operating Mode: Hybrid (KDE monitor detection + swww transitions{matugen_text})")
    else:
        matugen_text = " + matugen colors" if backend._check_matugen_available() else ""
        print(f"\n🖥️ Operating Mode: Native KDE wallpaper system{matugen_text}")
    
    # Theme information
    theme_info = backend.get_kde_theme_info()
    if theme_info:
        print(f"\n🎨 Current KDE Theme:")
        for key, value in theme_info.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
    
    # Monitor information
    monitors = backend.get_monitors()
    print(f"\n🖥️ Monitors ({len(monitors)}):")
    for monitor in monitors:
        primary_text = " (Primary)" if monitor.get('primary', False) else ""
        print(f"  {monitor['name']}: {monitor.get('resolution', 'Unknown')} - KDE Desktop {monitor.get('kde_desktop_id', '?')}{primary_text}")
    
    active = backend.get_active_monitor()
    print(f"\n📍 Active Monitor: {active}")
    
    # Current wallpapers
    print(f"\n🖼️ Current Wallpapers:")
    for monitor in monitors:
        current = backend.get_current_wallpaper(monitor['connector'])
        current_name = current.name if current else "None"
        print(f"  {monitor['connector']}: {current_name}")
    
    # Show keybind suggestions
    backend.suggest_kde_keybind_setup()
    
    print("\n✅ KDE Backend Test Complete")


if __name__ == "__main__":
    test_kde_backend()
