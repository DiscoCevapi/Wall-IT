#!/usr/bin/env python3
"""
Wall-IT Per-Monitor State Manager
Tracks wallpaper state independently for each monitor
"""

import json
import sys
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import configuration
try:
    import wall_it_config as config
except ImportError:
    config_path = Path(__file__).parent / "wall-it-config.py"
    spec = importlib.util.spec_from_file_location("wall_it_config", config_path)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    config = config_module

# Import backend manager
def _import_backend_manager():
    """Import the backend manager dynamically."""
    backend_path = Path(__file__).parent / "wall-it-backend-manager.py"
    spec = importlib.util.spec_from_file_location("backend_manager", backend_path)
    backend_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend_module)
    return backend_module.BackendManager

class MonitorStateManager:
    """Manages per-monitor wallpaper state."""
    
    def __init__(self):
        self.state_file: Path = config.MONITOR_STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state: Dict[str, Any] = self._load_state()
        self.backend_manager: Optional[Any] = None
        
        # Initialize backend manager
        try:
            BackendManager = _import_backend_manager()
            self.backend_manager = BackendManager()
        except Exception as e:
            print(f"Warning: Could not initialize backend manager: {e}", file=sys.stderr)
    
    def _load_state(self) -> Dict[str, Any]:
        """Load monitor state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    # Validate state structure
                    if isinstance(state, dict) and "monitors" in state:
                        return state
                    else:
                        print(f"Warning: Invalid state file format, resetting", file=sys.stderr)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in monitor state file: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Error loading monitor state: {e}", file=sys.stderr)
        
        return {"monitors": {}}
    
    def _save_state(self) -> bool:
        """Save monitor state to file."""
        try:
            # Write to temporary file first for atomic operation
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            # Atomic replace
            temp_file.replace(self.state_file)
            return True
        except Exception as e:
            print(f"Error saving monitor state: {e}", file=sys.stderr)
            return False
    
    def get_wallpaper_list(self) -> List[Path]:
        """Get list of all available wallpapers."""
        if not config.WALLPAPER_DIR.exists():
            return []
        
        wallpapers: List[Path] = []
        try:
            for file_path in config.WALLPAPER_DIR.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in config.IMAGE_EXTENSIONS:
                    wallpapers.append(file_path)
        except Exception as e:
            print(f"Error reading wallpaper directory: {e}", file=sys.stderr)
            return []
        
        return sorted(wallpapers)
    
    def get_current_wallpaper(self, monitor: str) -> Optional[Path]:
        """Get current wallpaper for specific monitor."""
        monitor_data: Dict[str, Any] = self.state["monitors"].get(monitor, {})
        current_path: Optional[str] = monitor_data.get("current_wallpaper")
        if current_path:
            path = Path(current_path)
            if path.exists():
                return path
        return None
    
    def set_current_wallpaper(self, monitor: str, wallpaper_path: Path) -> bool:
        """Set current wallpaper for specific monitor."""
        if monitor not in self.state["monitors"]:
            self.state["monitors"][monitor] = {}
        
        self.state["monitors"][monitor]["current_wallpaper"] = str(wallpaper_path)
        return self._save_state()
    
    def get_next_wallpaper(self, monitor: str) -> Optional[Path]:
        """Get next wallpaper for specific monitor"""
        wallpapers = self.get_wallpaper_list()
        if not wallpapers:
            return None
        
        current_wallpaper = self.get_current_wallpaper(monitor)
        current_index = 0
        
        if current_wallpaper and current_wallpaper in wallpapers:
            current_index = wallpapers.index(current_wallpaper)
        
        next_index = (current_index + 1) % len(wallpapers)
        return wallpapers[next_index]
    
    def get_prev_wallpaper(self, monitor: str) -> Optional[Path]:
        """Get previous wallpaper for specific monitor"""
        wallpapers = self.get_wallpaper_list()
        if not wallpapers:
            return None
        
        current_wallpaper = self.get_current_wallpaper(monitor)
        current_index = 0
        
        if current_wallpaper and current_wallpaper in wallpapers:
            current_index = wallpapers.index(current_wallpaper)
        
        prev_index = (current_index - 1) % len(wallpapers)
        return wallpapers[prev_index]
    
    def get_monitor_state(self, monitor: str) -> Dict[str, Any]:
        """Get all state data for a monitor."""
        return self.state["monitors"].get(monitor, {})
    
    def sync_from_global_state(self) -> bool:
        """Sync from global .current-wallpaper link (for backwards compatibility)."""
        try:
            if config.CURRENT_WALLPAPER_LINK.exists():
                current_global = Path(config.CURRENT_WALLPAPER_LINK.readlink())
                
                # If we don't have any monitor states, initialize them with the global state
                if not self.state["monitors"] and self.backend_manager:
                    # Use backend manager to get monitor list
                    try:
                        monitors = self.backend_manager.get_monitors()
                        for monitor in monitors:
                            monitor_name: str = monitor.get('connector', monitor.get('name', ''))
                            if monitor_name:
                                self.set_current_wallpaper(monitor_name, current_global)
                        return True
                    except Exception as e:
                        print(f"Warning: Could not sync monitors: {e}", file=sys.stderr)
                        return False
        except Exception as e:
            print(f"Error syncing from global state: {e}", file=sys.stderr)
            return False
        return True

if __name__ == "__main__":
    # Test/utility script
    manager = MonitorStateManager()
    manager.sync_from_global_state()
    
    print("Monitor State:")
    for monitor, state in manager.state["monitors"].items():
        current = state.get("current_wallpaper", "None")
        print(f"  {monitor}: {Path(current).name if current != 'None' else current}")
