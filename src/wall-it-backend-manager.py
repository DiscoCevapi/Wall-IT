#!/usr/bin/env python3
"""
Wall-IT Backend Manager
Manages multiple desktop environment backends and auto-detects the appropriate one
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Type
from abc import ABC, abstractmethod


class WallpaperBackend(ABC):
    """Abstract base class for wallpaper backends"""
    
    @abstractmethod
    def __init__(self):
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current system"""
        pass
    
    @abstractmethod
    def get_monitors(self) -> List[Dict[str, str]]:
        """Get list of available monitors"""
        pass
    
    @abstractmethod
    def get_active_monitor(self) -> Optional[str]:
        """Get the currently active/focused monitor"""
        pass
    
    @abstractmethod
    def set_wallpaper(self, wallpaper_path: Path, monitor: Optional[str] = None, transition: str = 'fade') -> bool:
        """Set wallpaper on specific monitor or all monitors"""
        pass
    
    @abstractmethod
    def get_current_wallpaper(self, monitor: Optional[str] = None) -> Optional[Path]:
        """Get current wallpaper for specific monitor"""
        pass
    
    @abstractmethod
    def supports_per_monitor_wallpapers(self) -> bool:
        """Check if the backend supports per-monitor wallpapers"""
        pass
    
    @abstractmethod
    def supports_transitions(self) -> bool:
        """Check if the backend supports wallpaper transitions"""
        pass


class NiriBackend(WallpaperBackend):
    """Backend for Niri Wayland compositor using swww"""
    
    def __init__(self):
        self.name = "Niri"
        self.verify_tools()
    
    def verify_tools(self):
        """Verify that required tools are available"""
        required_tools = ['swww', 'niri']
        missing_tools = []
        
        for tool in required_tools:
            try:
                subprocess.run(['which', tool], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                missing_tools.append(tool)
        
        if missing_tools:
            print(f"Warning: Missing required tools for Niri backend: {', '.join(missing_tools)}", file=sys.stderr)
    
    def is_available(self) -> bool:
        """Check if Niri backend is available"""
        try:
            # Check if swww is running
            subprocess.run(['swww', 'query'], check=True, capture_output=True)
            # Check if niri is available
            subprocess.run(['which', 'niri'], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_monitors(self) -> List[Dict[str, str]]:
        """Get detailed list of monitors from niri msg outputs"""
        monitors = []
        try:
            # Get detailed monitor information from niri
            result = subprocess.run(['niri', 'msg', 'outputs'], capture_output=True, text=True, check=True)
            
            current_monitor = None
            lines = result.stdout.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                # Parse monitor header line: Output "Monitor Name" (CONNECTOR)
                if line.startswith('Output "') and '(' in line and ')' in line:
                    # Save previous monitor before starting new one
                    if current_monitor:
                        monitors.append(current_monitor)
                    
                    # Extract monitor name and connector
                    try:
                        # Find the quoted name
                        start_quote = line.find('"') + 1
                        end_quote = line.find('"', start_quote)
                        monitor_name = line[start_quote:end_quote] if start_quote > 0 and end_quote > start_quote else "Unknown"
                        
                        # Find the connector in parentheses
                        start_paren = line.rfind('(') + 1
                        end_paren = line.rfind(')')
                        connector = line[start_paren:end_paren] if start_paren > 0 and end_paren > start_paren else "Unknown"
                        
                        # Initialize monitor info
                        current_monitor = {
                            'name': monitor_name,
                            'connector': connector,
                            'backend': 'niri',
                            'resolution': 'Unknown',
                            'scale': '1.0',
                            'refresh_rate': '60.0'
                        }
                        
                    except Exception as parse_error:
                        print(f"Warning: Could not parse monitor line '{line}': {parse_error}", file=sys.stderr)
                        continue
                
                # Parse current mode line: Current mode: 3440x1440 @ 155.000 Hz
                elif line.startswith('Current mode:') and current_monitor:
                    try:
                        mode_part = line.split('Current mode:')[1].strip()
                        if '@' in mode_part:
                            resolution_part = mode_part.split('@')[0].strip()
                            refresh_part = mode_part.split('@')[1].strip().replace('Hz', '').strip()
                            
                            # Clean up refresh rate (remove " (preferred)" etc.)
                            if ' ' in refresh_part:
                                refresh_part = refresh_part.split()[0]
                            
                            current_monitor['resolution'] = resolution_part
                            current_monitor['refresh_rate'] = refresh_part
                    except Exception as parse_error:
                        print(f"Warning: Could not parse mode line '{line}': {parse_error}", file=sys.stderr)
                
                # Parse scale line: Scale: 1.4
                elif line.startswith('Scale:') and current_monitor:
                    try:
                        scale_value = line.split('Scale:')[1].strip()
                        current_monitor['scale'] = scale_value
                    except Exception as parse_error:
                        print(f"Warning: Could not parse scale line '{line}': {parse_error}", file=sys.stderr)
            
            # Add the last monitor after parsing all lines
            if current_monitor:
                monitors.append(current_monitor)
                
        except subprocess.CalledProcessError as e:
            print(f"Error getting monitors from niri: {e}", file=sys.stderr)
            # Fallback to swww query if niri command fails
            try:
                result = subprocess.run(['swww', 'query'], capture_output=True, text=True, check=True)
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        monitor_name = line.split(':')[1].strip().split(':')[0]
                        monitors.append({
                            'name': monitor_name,
                            'connector': monitor_name,
                            'backend': 'niri',
                            'resolution': 'Unknown',
                            'scale': '1.0',
                            'refresh_rate': '60.0'
                        })
            except subprocess.CalledProcessError:
                print("Warning: Both niri and swww monitor detection failed", file=sys.stderr)
        
        return monitors
    
    def get_active_monitor(self) -> Optional[str]:
        """Get currently focused monitor using Niri"""
        try:
            result = subprocess.run(['niri', 'msg', 'focused-output'], capture_output=True, text=True, check=True)
            output_lines = result.stdout.strip().split('\n')
            
            for line in output_lines:
                if line.startswith('Output') and '(' in line and ')' in line:
                    start_paren = line.rfind('(')
                    end_paren = line.rfind(')')
                    if start_paren != -1 and end_paren != -1:
                        return line[start_paren + 1:end_paren]
            
            # Fallback to first monitor
            monitors = self.get_monitors()
            if monitors:
                return monitors[0]['connector']
        except subprocess.CalledProcessError as e:
            print(f"Error getting active monitor: {e}", file=sys.stderr)
        return None
    
    def set_wallpaper(self, wallpaper_path: Path, monitor: Optional[str] = None, transition: str = 'fade') -> bool:
        """Set wallpaper using swww"""
        try:
            cmd = [
                'swww', 'img', str(wallpaper_path),
                '--transition-type', transition,
                '--transition-fps', '30',
                '--transition-duration', '1.5'
            ]
            
            if monitor:
                cmd.extend(['--outputs', monitor])
            
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"Wall-IT: Set wallpaper via Niri/swww")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error setting wallpaper: {e}", file=sys.stderr)
            return False
    
    def get_current_wallpaper(self, monitor: Optional[str] = None) -> Optional[Path]:
        """Get current wallpaper from symlink"""
        try:
            current_link = Path.home() / ".current-wallpaper"
            if current_link.exists():
                return Path(current_link.readlink())
        except Exception as e:
            print(f"Error getting current wallpaper: {e}", file=sys.stderr)
        return None
    
    def supports_per_monitor_wallpapers(self) -> bool:
        return True
    
    def supports_transitions(self) -> bool:
        return True


class BackendManager:
    """Manages wallpaper backends and auto-detects the appropriate one"""
    
    def __init__(self):
        self.backends = {}
        self._active_backend = None
        self._load_backends()
        self._detect_backend()
    
    def _load_backends(self):
        """Load all available backends"""
        # Import KDE backend
        try:
            from pathlib import Path
            kde_backend_path = Path(__file__).parent / "wall-it-kde-backend.py"
            if kde_backend_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("kde_backend", kde_backend_path)
                kde_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(kde_module)
                self.backends['kde'] = kde_module.KDEBackend
            
        except Exception as e:
            print(f"Warning: Could not load KDE backend: {e}", file=sys.stderr)
        
        # Register Niri backend
        self.backends['niri'] = NiriBackend
    
    def _detect_backend(self):
        """Auto-detect the appropriate backend"""
        # Try each backend in order of preference
        for name, backend_class in self.backends.items():
            try:
                backend = backend_class()
                if backend.is_available():
                    self._active_backend = backend
                    print(f"Wall-IT: Using {name.upper()} backend")
                    return
            except Exception as e:
                print(f"Warning: Error testing {name} backend: {e}", file=sys.stderr)
        
        print("Error: No compatible wallpaper backend found!", file=sys.stderr)
    
    def get_backend(self) -> Optional[WallpaperBackend]:
        """Get the active backend"""
        return self._active_backend
    
    def is_available(self) -> bool:
        """Check if any backend is available"""
        return self._active_backend is not None
    
    def get_backend_name(self) -> str:
        """Get the name of the active backend"""
        if self._active_backend:
            return self._active_backend.name
        return "None"
    
    # Proxy methods to active backend
    def get_monitors(self) -> List[Dict[str, str]]:
        """Get list of available monitors"""
        if self._active_backend:
            return self._active_backend.get_monitors()
        return []
    
    def get_active_monitor(self) -> Optional[str]:
        """Get the currently active monitor"""
        if self._active_backend:
            return self._active_backend.get_active_monitor()
        return None
    
    def set_wallpaper(self, wallpaper_path: Path, monitor: Optional[str] = None, transition: str = 'fade') -> bool:
        """Set wallpaper"""
        if self._active_backend:
            return self._active_backend.set_wallpaper(wallpaper_path, monitor, transition)
        return False
    
    def get_current_wallpaper(self, monitor: Optional[str] = None) -> Optional[Path]:
        """Get current wallpaper"""
        if self._active_backend:
            return self._active_backend.get_current_wallpaper(monitor)
        return None
    
    def supports_per_monitor_wallpapers(self) -> bool:
        """Check if per-monitor wallpapers are supported"""
        if self._active_backend:
            return self._active_backend.supports_per_monitor_wallpapers()
        return False
    
    def supports_transitions(self) -> bool:
        """Check if transitions are supported"""
        if self._active_backend:
            return self._active_backend.supports_transitions()
        return False


def test_backend_manager():
    """Test the backend manager"""
    manager = BackendManager()
    
    print(f"Backend Available: {manager.is_available()}")
    print(f"Backend Name: {manager.get_backend_name()}")
    print(f"Supports Per-Monitor: {manager.supports_per_monitor_wallpapers()}")
    print(f"Supports Transitions: {manager.supports_transitions()}")
    
    monitors = manager.get_monitors()
    print(f"Monitors ({len(monitors)}):")
    for monitor in monitors:
        print(f"  {monitor}")
    
    active = manager.get_active_monitor()
    print(f"Active Monitor: {active}")


if __name__ == "__main__":
    test_backend_manager()
