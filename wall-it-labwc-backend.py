#!/usr/bin/env python3
"""
Wall-IT Labwc Backend v2.1.0
Provides Labwc-specific functionality for wallpaper management
Compatible with various shell setups (waybar, noctalia-shell, etc.)
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class LabwcBackend:
    """Backend for Labwc Wayland compositor"""
    
    def __init__(self):
        self.name = "Labwc"
        self.verify_tools()
        self.swww_available = self._check_swww_daemon()
    
    def verify_tools(self):
        """Verify that required Labwc tools are available"""
        required_tools = ['swww']  # We'll use swww for wallpaper management
        missing_tools = []
        
        for tool in required_tools:
            try:
                subprocess.run(['which', tool], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                missing_tools.append(tool)
        
        if missing_tools:
            print(f"Warning: Missing required tools for Labwc backend: {', '.join(missing_tools)}", file=sys.stderr)
    
    def _check_swww_daemon(self) -> bool:
        """Check if swww daemon is running"""
        try:
            result = subprocess.run(['swww', 'query'], capture_output=True, text=True, timeout=2)
            return result.returncode == 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def is_available(self) -> bool:
        """Check if Labwc backend is available on this system"""
        try:
            # Check if we're running Labwc
            import os
            current_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '')
            wayland_display = os.environ.get('WAYLAND_DISPLAY', '')
            
            # Check for labwc in various ways
            if 'labwc' in current_desktop.lower():
                return True
            if 'wlroots' in current_desktop.lower():
                return True
            if wayland_display and self._check_labwc_process():
                return True
            
            return False
        except Exception:
            return False
    
    def _check_labwc_process(self) -> bool:
        """Check if labwc process is running"""
        try:
            result = subprocess.run(['pgrep', 'labwc'], capture_output=True, text=True)
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False
    
    def get_monitors(self) -> List[Dict[str, str]]:
        """Get list of available monitors with their properties"""
        monitors = []
        
        try:
            # Use wlr-randr to get monitor information
            result = subprocess.run(['wlr-randr'], capture_output=True, text=True, check=True)
            
            current_monitor = None
            for line in result.stdout.split('\n'):
                line_stripped = line.strip()
                
                # Skip empty lines
                if not line_stripped:
                    continue
                    
                # Check if this is a monitor header (doesn't start with space and contains display info)
                if not line.startswith(' ') and '"' in line:
                    # This is a monitor line like: LVDS-1 "Chimei Innolux Corporation 0x15B8 (LVDS-1)"
                    name = line.split()[0]  # Get first part (monitor name)
                    current_monitor = {
                        'id': name,
                        'name': name,
                        'connector': name,
                        'resolution': 'Unknown',
                        'primary': False
                    }
                    monitors.append(current_monitor)
                        
                # Parse resolution from mode lines under "Modes:" section
                elif line.startswith('    ') and current_monitor and 'current' in line_stripped:
                    # Parse resolution from lines like "    1366x768 px, 60.046001 Hz (preferred, current)"
                    if 'x' in line_stripped and 'px' in line_stripped:
                        try:
                            res_part = line_stripped.split()[0]  # Get first part like "1366x768"
                            if 'x' in res_part and res_part.count('x') == 1:
                                # Validate it's actually a resolution (contains only digits and x)
                                parts = res_part.split('x')
                                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                                    current_monitor['resolution'] = res_part
                        except Exception:
                            pass
            
            # Set first monitor as primary if we found any
            if monitors:
                monitors[0]['primary'] = True
            
        except subprocess.CalledProcessError as e:
            print(f"Warning: wlr-randr not available, using fallback: {e}", file=sys.stderr)
            # Fallback: create a default monitor entry
            monitors = [{
                'id': 'default',
                'name': 'default',
                'connector': 'default',
                'resolution': 'Unknown',
                'primary': True
            }]
        
        return monitors
    
    def get_active_monitor(self) -> Optional[str]:
        """Get the currently active/focused monitor"""
        monitors = self.get_monitors()
        if monitors:
            return monitors[0]['name']  # Return first monitor as active
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
            print("Error: swww daemon is not running. Please start it with 'swww-daemon'", file=sys.stderr)
            return False
            
        try:
            # Generate colors with matugen first (SINGLE CALL - fixes slowness issue)
            matugen_success = self._generate_matugen_colors(wallpaper_path)
            
            cmd = ['swww', 'img', str(wallpaper_path)]
            
            # Add transition settings (using valid swww transitions)
            valid_transitions = ['none', 'fade', 'left', 'right', 'top', 'bottom', 
                               'wipe', 'wave', 'grow', 'center', 'outer']
            if transition not in valid_transitions:
                transition = 'fade'
            
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
            
            # Save current wallpaper path
            cache_dir = Path.home() / ".cache" / "wall-it"
            cache_dir.mkdir(parents=True, exist_ok=True)
            wallpaper_file = cache_dir / "current_wallpaper"
            wallpaper_file.write_text(str(wallpaper_path))
            
            if matugen_success:
                print(f"Wall-IT: Generated dynamic colors with matugen")
                # Apply colors to detected shell integrations
                self._apply_shell_integrations()
            
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
                if monitor in line and 'image:' in line:
                    # Try to extract the file path from swww query output
                    parts = line.split('image:')
                    if len(parts) >= 2:
                        path_str = parts[1].strip()
                        path = Path(path_str)
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
    
    def suggest_labwc_keybind_setup(self):
        """Suggest keybind setup commands for Labwc"""
        print("\n🔧 Labwc Keybind Setup Suggestions:")
        print("Add these lines to your Labwc config (~/.config/labwc/rc.xml):")
        print("\n<!-- Wall-IT Keybinds -->")
        print('<keybind key="W-A-n">')
        print('  <action name="Execute">')
        print('    <command>~/.local/bin/wall-it-next</command>')
        print('  </action>')
        print('</keybind>')
        print('<keybind key="W-A-p">')
        print('  <action name="Execute">')
        print('    <command>~/.local/bin/wall-it-prev</command>')
        print('  </action>')
        print('</keybind>')
        print('<keybind key="W-A-g">')
        print('  <action name="Execute">')
        print('    <command>~/.local/bin/wallpaper-gui.py</command>')
        print('  </action>')
        print('</keybind>')
    
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
            
            return True
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"Warning: matugen failed: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Warning: matugen error: {e}", file=sys.stderr)
            return False
    
    def _apply_shell_integrations(self):
        """Apply colors to detected shell and UI integrations"""
        cache_dir = Path.home() / ".cache" / "wall-it"
        colors_file = cache_dir / "matugen_colors.json"
        
        if not colors_file.exists():
            return
        
        try:
            colors_data = json.loads(colors_file.read_text())
            # Extract dark theme colors (matugen v2.x format)
            raw_colors = colors_data.get('colors', {})
            if 'dark' in raw_colors:
                colors = raw_colors['dark']  # Use dark theme colors
            else:
                colors = raw_colors  # Fallback for older format
            
            # Apply to common applications
            self._update_gtk_colors(colors)
            self._update_terminal_colors(colors)
            
            # Detect and apply to specific shell integrations
            self._detect_and_update_waybar(colors)
            self._detect_and_update_noctalia(colors)
            
        except Exception as e:
            print(f"Warning: Could not apply shell integrations: {e}", file=sys.stderr)
    
    def _detect_and_update_waybar(self, colors: Dict):
        """Detect and update waybar if present"""
        waybar_config = Path.home() / ".config" / "waybar"
        waybar_script = Path.home() / ".local" / "bin" / "waybar-wall-it-colors.py"
        
        if waybar_config.exists() or waybar_script.exists():
            try:
                # If waybar integration script exists, call its update function directly
                if waybar_script.exists():
                    # Import and call the update function from your waybar script
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("waybar_colors", str(waybar_script))
                    waybar_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(waybar_module)
                    waybar_module.update_waybar_colors()
                else:
                    # Basic waybar integration
                    self._basic_waybar_integration(colors, waybar_config)
                print("Wall-IT: Updated waybar colors")
            except Exception as e:
                print(f"Warning: Could not update waybar: {e}", file=sys.stderr)
    
    def _basic_waybar_integration(self, colors: Dict, waybar_config: Path):
        """Basic waybar color integration for users without custom scripts"""
        try:
            style_css = waybar_config / "style.css"
            if style_css.exists():
                # Create a basic CSS variable injection
                css_vars = f"""
/* Wall-IT Generated Colors */
:root {{
  --wall-it-primary: {colors.get('primary', '#6366f1')};
  --wall-it-secondary: {colors.get('secondary', '#8b5cf6')};
  --wall-it-background: {colors.get('surface', '#1f2937')};
  --wall-it-text: {colors.get('on_surface', '#ffffff')};
  --wall-it-accent: {colors.get('tertiary', '#f59e0b')};
}}
"""
                
                existing_css = style_css.read_text()
                
                # Remove old Wall-IT section if exists
                if "/* Wall-IT Generated Colors */" in existing_css:
                    lines = existing_css.split('\n')
                    new_lines = []
                    skip = False
                    for line in lines:
                        if "/* Wall-IT Generated Colors */" in line:
                            skip = True
                        elif skip and line.strip() == '}':
                            skip = False
                            continue
                        if not skip:
                            new_lines.append(line)
                    existing_css = '\n'.join(new_lines)
                
                # Add new colors
                new_css = css_vars + '\n' + existing_css
                style_css.write_text(new_css)
                
                # Send reload signal to waybar instead of restarting
                try:
                    subprocess.run(['pkill', '-SIGUSR2', 'waybar'], stderr=subprocess.DEVNULL)
                except:
                    # If signal fails, waybar might not be running or doesn't support reload
                    pass
                
        except Exception as e:
            print(f"Warning: Basic waybar integration failed: {e}", file=sys.stderr)
    
    def _detect_and_update_noctalia(self, colors: Dict):
        """Detect and update noctalia-shell if present"""
        noctalia_config = Path.home() / ".config" / "noctalia"
        noctalia_colors = noctalia_config / "colors.json"
        
        if noctalia_config.exists():
            try:
                # Convert matugen colors to noctalia format
                noctalia_color_format = {
                    "mError": colors.get('error', '#fd4663'),
                    "mOnError": colors.get('on_error', '#ffffff'),
                    "mOnPrimary": colors.get('on_primary', '#ffffff'),
                    "mOnSecondary": colors.get('on_secondary', '#ffffff'),
                    "mOnSurface": colors.get('on_surface', '#ffffff'),
                    "mOnSurfaceVariant": colors.get('on_surface_variant', '#cccccc'),
                    "mOnTertiary": colors.get('on_tertiary', '#ffffff'),
                    "mOutline": colors.get('outline', '#666666'),
                    "mPrimary": colors.get('primary', '#6366f1'),
                    "mSecondary": colors.get('secondary', '#8b5cf6'),
                    "mShadow": colors.get('shadow', '#000000'),
                    "mSurface": colors.get('surface', '#1f2937'),
                    "mSurfaceVariant": colors.get('surface_variant', '#374151'),
                    "mTertiary": colors.get('tertiary', '#f59e0b')
                }
                
                noctalia_colors.write_text(json.dumps(noctalia_color_format, indent=4))
                print("Wall-IT: Updated noctalia-shell colors")
                
                # Try to reload noctalia if it has a reload mechanism
                try:
                    subprocess.run(['pkill', '-SIGUSR1', 'noctalia'], stderr=subprocess.DEVNULL)
                except:
                    pass
                    
            except Exception as e:
                print(f"Warning: Could not update noctalia colors: {e}", file=sys.stderr)
    
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
  --wall-it-accent: {colors.get('tertiary', '#f59e0b')};
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


def test_labwc_backend():
    """Test function for Labwc backend"""
    backend = LabwcBackend()
    
    print("=" * 50)
    print("🚀 Wall-IT Labwc Backend v2.1.0 Test")
    print("=" * 50)
    
    # Basic availability
    print(f"Labwc Backend Available: {backend.is_available()}")
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
    
    # Detect shell integrations
    print(f"\n🔧 Shell Integration Detection:")
    waybar_config = Path.home() / ".config" / "waybar"
    noctalia_config = Path.home() / ".config" / "noctalia"
    waybar_script = Path.home() / ".local" / "bin" / "waybar-wall-it-colors.py"
    
    if waybar_config.exists():
        print(f"  ✅ Waybar configuration detected")
    if waybar_script.exists():
        print(f"  ✅ Custom waybar integration script detected")
    if noctalia_config.exists():
        print(f"  ✅ Noctalia-shell configuration detected")
    if not (waybar_config.exists() or noctalia_config.exists()):
        print(f"  ℹ️  No specific shell integrations detected - using generic GTK/terminal support")
    
    # Show keybind suggestions
    backend.suggest_labwc_keybind_setup()
    
    print("\n✅ Labwc Backend v2.1.0 Test Complete")


def restore_wallpaper():
    """Restore wallpaper from cache with effects"""
    cache_dir = Path.home() / ".cache" / "wall-it"
    wallpaper_file = cache_dir / "current_wallpaper"
    effect_file = cache_dir / "current_effect"
    
    if not wallpaper_file.exists() or not effect_file.exists():
        print("No wallpaper state to restore")
        return False
    
    try:
        wallpaper_path = Path(wallpaper_file.read_text().strip())
        effect = effect_file.read_text().strip()
        
        if wallpaper_path.exists():
            backend = LabwcBackend()
            print(f"Restoring wallpaper with effect: {effect}")
            return backend.set_wallpaper(wallpaper_path)
        else:
            print(f"Wallpaper file not found: {wallpaper_path}")
            return False
    except Exception as e:
        print(f"Error restoring wallpaper: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--restore':
        restore_wallpaper()
    else:
        test_labwc_backend()
