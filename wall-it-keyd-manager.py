#!/usr/bin/env python3
"""
Wall-IT Keyd Manager
Manages keyd configuration for Wall-IT global keybinds
Replaces the pynput-based daemon with keyd integration
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

try:
    from wall_it_keybind_config import WallITKeybindConfig, Keybind, KeybindAction
except ImportError:
    # Try with underscores replaced with hyphens (file naming convention)
    try:
        import importlib.util
        config_path = Path(__file__).parent / "wall-it-keybind-config.py"
        spec = importlib.util.spec_from_file_location("keybind_config", config_path)
        keybind_config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(keybind_config_module)
        WallITKeybindConfig = keybind_config_module.WallITKeybindConfig
        Keybind = keybind_config_module.Keybind
        KeybindAction = keybind_config_module.KeybindAction
    except Exception as e:
        print(f"❌ Could not import keybind configuration: {e}")
        sys.exit(1)

class WallITKeydManager:
    """Manages keyd configuration for Wall-IT keybinds"""
    
    def __init__(self):
        self.config = WallITKeybindConfig()
        self.keyd_config_file = Path("/etc/keyd/wall-it.conf")
        
    def _convert_key_combination(self, key_combo: str) -> str:
        """Convert Wall-IT key combination to keyd format"""
        # Wall-IT format: "Super+Alt+N" or "ctrl+shift+f12"
        # keyd format: "meta+alt+n" or "control+shift+f12"
        
        parts = [part.strip() for part in key_combo.split('+')]
        keyd_parts = []
        
        # Map keys to keyd format
        key_map = {
            'super': 'leftmeta',
            'ctrl': 'leftcontrol', 
            'control': 'leftcontrol',
            'alt': 'leftalt',
            'shift': 'leftshift',
            'cmd': 'leftmeta',
            'win': 'leftmeta',
            'windows': 'leftmeta'
        }
        
        for part in parts:
            part_lower = part.lower()
            if part_lower in key_map:
                keyd_parts.append(key_map[part_lower])
            else:
                # Regular keys (letters, numbers, function keys)
                keyd_parts.append(part_lower)
        
        return '+'.join(keyd_parts)
    
    def _generate_keyd_config(self) -> str:
        """Generate keyd configuration content"""
        config_lines = [
            "# Wall-IT Global Keybinds",
            "# Generated automatically - do not edit manually",
            "",
            "[ids]",
            "*",  # Apply to all keyboards
            "",
            "[main]",
            ""
        ]
        
        enabled_keybinds = self.config.get_enabled_keybinds()
        
        for keybind in enabled_keybinds:
            keyd_combo = self._convert_key_combination(keybind.key_combination)
            command_str = ' '.join(keybind.action.command)
            
            # keyd uses the format: key_combination = command_to_run
            config_lines.append(f"{keyd_combo} = command({command_str})")
            config_lines.append(f"# {keybind.action.description}")
            config_lines.append("")
        
        return '\n'.join(config_lines)
    
    def update_keyd_config(self) -> bool:
        """Update keyd configuration file"""
        try:
            config_content = self._generate_keyd_config()
            
            # Write to temporary file first
            temp_file = Path("/tmp/wall-it-keyd.conf")
            temp_file.write_text(config_content)
            
            # Copy to keyd directory with sudo
            result = subprocess.run([
                'sudo', 'cp', str(temp_file), str(self.keyd_config_file)
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ Error copying config: {result.stderr}")
                return False
            
            # Set proper permissions
            subprocess.run([
                'sudo', 'chown', 'root:root', str(self.keyd_config_file)
            ], capture_output=True)
            
            subprocess.run([
                'sudo', 'chmod', '644', str(self.keyd_config_file)
            ], capture_output=True)
            
            # Clean up temp file
            temp_file.unlink()
            
            print(f"✅ Updated keyd configuration: {self.keyd_config_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating keyd config: {e}")
            return False
    
    def reload_keyd(self) -> bool:
        """Reload keyd service to apply new configuration"""
        try:
            result = subprocess.run([
                'sudo', 'keyd', 'reload'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Keyd configuration reloaded")
                return True
            else:
                print(f"❌ Error reloading keyd: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error reloading keyd: {e}")
            return False
    
    def start(self) -> bool:
        """Start/update the keyd configuration"""
        print("🔧 Updating Wall-IT keyd configuration...")
        
        enabled_keybinds = self.config.get_enabled_keybinds()
        if not enabled_keybinds:
            print("⚠️ No enabled keybinds found")
            return self.remove_config()
        
        if not self.update_keyd_config():
            return False
        
        if not self.reload_keyd():
            return False
        
        print(f"✅ Wall-IT keybinds active: {len(enabled_keybinds)} keybinds registered")
        return True
    
    def stop(self) -> bool:
        """Stop Wall-IT keybinds by removing the configuration"""
        return self.remove_config()
    
    def remove_config(self) -> bool:
        """Remove Wall-IT keyd configuration"""
        try:
            if self.keyd_config_file.exists():
                result = subprocess.run([
                    'sudo', 'rm', str(self.keyd_config_file)
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.reload_keyd()
                    print("✅ Wall-IT keybinds removed")
                    return True
                else:
                    print(f"❌ Error removing config: {result.stderr}")
                    return False
            else:
                print("ℹ️ No Wall-IT keyd configuration found")
                return True
                
        except Exception as e:
            print(f"❌ Error removing keyd config: {e}")
            return False
    
    def status(self) -> bool:
        """Check if Wall-IT keybinds are active"""
        if self.keyd_config_file.exists():
            enabled_keybinds = self.config.get_enabled_keybinds()
            print(f"✅ Wall-IT keybinds active: {len(enabled_keybinds)} keybinds")
            return True
        else:
            print("❌ Wall-IT keybinds not active")
            return False
    
    def list_config(self):
        """Show current keyd configuration"""
        if self.keyd_config_file.exists():
            try:
                content = self.keyd_config_file.read_text()
                print("Current Wall-IT keyd configuration:")
                print("=" * 40)
                print(content)
            except Exception as e:
                print(f"❌ Error reading config: {e}")
        else:
            print("❌ No Wall-IT keyd configuration found")


def main():
    """Main entry point"""
    manager = WallITKeydManager()
    
    if len(sys.argv) < 2:
        print("Wall-IT Keyd Manager")
        print("Usage:")
        print("  wall-it-keyd-manager start    - Apply Wall-IT keybinds to keyd")
        print("  wall-it-keyd-manager stop     - Remove Wall-IT keybinds from keyd")
        print("  wall-it-keyd-manager reload   - Reload keyd configuration")
        print("  wall-it-keyd-manager status   - Check keybind status")
        print("  wall-it-keyd-manager show     - Show current configuration")
        return
    
    command = sys.argv[1]
    
    if command == "start":
        manager.start()
    elif command == "stop":
        manager.stop()
    elif command == "reload":
        manager.update_keyd_config()
        manager.reload_keyd()
    elif command == "status":
        manager.status()
    elif command == "show":
        manager.list_config()
    else:
        print(f"❌ Unknown command: {command}")


if __name__ == "__main__":
    main()
