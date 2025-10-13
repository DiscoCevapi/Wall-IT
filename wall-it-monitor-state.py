#!/usr/bin/env python3
"""
Wall-IT Per-Monitor State Manager
Tracks wallpaper state independently for each monitor
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import importlib.util

# Import backend manager
def _import_backend_manager():
    """Import the backend manager dynamically"""
    backend_path = Path(__file__).parent / "wall-it-backend-manager.py"
    spec = importlib.util.spec_from_file_location("backend_manager", backend_path)
    backend_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend_module)
    return backend_module.BackendManager

class MonitorStateManager:
    """Manages per-monitor wallpaper state"""
    
    def __init__(self):
        self.state_file = Path.home() / ".cache" / "wall-it" / "monitor_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
        
        # Initialize backend manager
        try:
            BackendManager = _import_backend_manager()
            self.backend_manager = BackendManager()
        except Exception as e:
            print(f"Warning: Could not initialize backend manager: {e}", file=sys.stderr)
            self.backend_manager = None
    
    def _load_state(self) -> Dict:
        """Load monitor state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading monitor state: {e}", file=sys.stderr)
        
        return {"monitors": {}}
    
    def _save_state(self):
        """Save monitor state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Error saving monitor state: {e}", file=sys.stderr)
    
    def get_wallpaper_list(self) -> List[Path]:
        """Get list of all available wallpapers"""
        wallpaper_dir = Path.home() / "Pictures" / "Wallpapers"
        if not wallpaper_dir.exists():
            return []
        
        extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff'}
        wallpapers = []
        for file_path in wallpaper_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                wallpapers.append(file_path)
        
        return sorted(wallpapers)
    
    def get_current_wallpaper(self, monitor: str) -> Optional[Path]:
        """Get current wallpaper for specific monitor"""
        monitor_data = self.state["monitors"].get(monitor, {})
        current_path = monitor_data.get("current_wallpaper")
        if current_path and Path(current_path).exists():
            return Path(current_path)
        return None
    
    def set_current_wallpaper(self, monitor: str, wallpaper_path: Path):
        """Set current wallpaper for specific monitor"""
        if monitor not in self.state["monitors"]:
            self.state["monitors"][monitor] = {}
        
        self.state["monitors"][monitor]["current_wallpaper"] = str(wallpaper_path)
        self._save_state()
    
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
    
    def get_monitor_state(self, monitor: str) -> Dict:
        """Get all state data for a monitor"""
        return self.state["monitors"].get(monitor, {})
    
    def sync_from_global_state(self):
        """Sync from global .current-wallpaper link (for backwards compatibility)"""
        try:
            current_link = Path.home() / ".current-wallpaper"
            if current_link.exists():
                current_global = Path(current_link.readlink())
                
                # If we don't have any monitor states, initialize them with the global state
                if not self.state["monitors"] and self.backend_manager:
                    # Use backend manager to get monitor list
                    try:
                        monitors = self.backend_manager.get_monitors()
                        for monitor in monitors:
                            monitor_name = monitor.get('connector', monitor.get('name', ''))
                            if monitor_name:
                                self.set_current_wallpaper(monitor_name, current_global)
                    except Exception as e:
                        print(f"Warning: Could not sync monitors: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error syncing from global state: {e}", file=sys.stderr)

if __name__ == "__main__":
    # Test/utility script
    manager = MonitorStateManager()
    manager.sync_from_global_state()
    
    print("Monitor State:")
    for monitor, state in manager.state["monitors"].items():
        current = state.get("current_wallpaper", "None")
        print(f"  {monitor}: {Path(current).name if current != 'None' else current}")
