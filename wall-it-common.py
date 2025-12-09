#!/usr/bin/env python3
"""
Wall-IT Common Utilities
Shared functions and utilities for Wall-IT scripts
"""

import sys
import subprocess
import importlib.util
from pathlib import Path
from typing import Optional, List

# Import configuration
try:
    import wall_it_config as config
except ImportError:
    # Fallback to loading from file path
    config_path = Path(__file__).parent / "wall-it-config.py"
    spec = importlib.util.spec_from_file_location("wall_it_config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)


def read_cache_file(file_path: Path, default: str = "") -> str:
    """Read a cache file and return its content, or default if it doesn't exist."""
    try:
        if file_path.exists():
            content = file_path.read_text().strip()
            # Handle legacy format: "value1|value2"
            if '|' in content:
                parts = content.split('|')
                if len(parts) >= 2:
                    return parts[1]  # Return the second part
            return content
    except Exception as e:
        print(f"Error reading {file_path.name}: {e}", file=sys.stderr)
    return default


def write_cache_file(file_path: Path, content: str) -> bool:
    """Write content to a cache file."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return True
    except Exception as e:
        print(f"Error writing {file_path.name}: {e}", file=sys.stderr)
        return False


def get_transition_effect() -> str:
    """Get the current transition effect from Wall-IT config."""
    return read_cache_file(config.TRANSITION_FILE, config.DEFAULT_TRANSITION)


def is_matugen_enabled() -> bool:
    """Check if matugen is enabled in Wall-IT config."""
    value = read_cache_file(config.MATUGEN_ENABLED_FILE, str(config.DEFAULT_MATUGEN_ENABLED))
    return value.lower() == "true"


def get_matugen_scheme() -> str:
    """Get the current matugen color scheme."""
    scheme = read_cache_file(config.MATUGEN_SCHEME_FILE, config.DEFAULT_MATUGEN_SCHEME)
    # Fix old scheme names to new format
    if scheme in config.SCHEME_NAME_MAP:
        scheme = config.SCHEME_NAME_MAP[scheme]
    return scheme


def generate_colors_with_matugen(wallpaper_path: Path, scheme: str) -> bool:
    """Generate colors using matugen and save to cache with timeout."""
    try:
        cmd = [
            "matugen", "image", str(wallpaper_path),
            "--mode", "dark",
            "--type", scheme,
            "--json", "hex"
        ]
        # Set timeout to avoid blocking too long on large images
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5.0)
        
        # Save colors to cache
        if result.stdout:
            write_cache_file(config.MATUGEN_COLORS_FILE, result.stdout)
        
        print(f"Wall-IT: Generated colors using matugen with {scheme} scheme")
        return True
    except subprocess.TimeoutExpired:
        print("Warning: matugen timed out (image too large?)", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        print(f"Error running matugen: {error_msg}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("Error: matugen not found. Please install matugen.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error with matugen: {e}", file=sys.stderr)
        return False


def get_current_wallpaper() -> Optional[Path]:
    """Get the current wallpaper path from symlink."""
    try:
        if config.CURRENT_WALLPAPER_LINK.exists():
            return Path(config.CURRENT_WALLPAPER_LINK.readlink())
    except Exception as e:
        print(f"Error reading current wallpaper link: {e}", file=sys.stderr)
    return None


def get_wallpaper_list() -> List[Path]:
    """Get sorted list of wallpapers."""
    if not config.WALLPAPER_DIR.exists():
        return []
    
    wallpapers = []
    try:
        for file_path in config.WALLPAPER_DIR.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in config.IMAGE_EXTENSIONS:
                wallpapers.append(file_path)
    except Exception as e:
        print(f"Error reading wallpaper directory: {e}", file=sys.stderr)
        return []
    
    return sorted(wallpapers)


def get_current_effect() -> str:
    """Get current photo effect from Wall-IT config."""
    return read_cache_file(config.EFFECT_FILE, config.DEFAULT_EFFECT)


def get_wallpaper_scaling() -> str:
    """Get wallpaper scaling mode from Wall-IT config."""
    return read_cache_file(config.SCALING_FILE, config.DEFAULT_SCALING)


def get_keybind_mode() -> str:
    """Get the current keybind mode (all or active)."""
    return read_cache_file(config.KEYBIND_MODE_FILE, config.DEFAULT_KEYBIND_MODE)


def apply_effect(image_path: Path, effect: str, temp_dir: Path) -> Path:
    """Apply photo effect using the same implementation as GUI."""
    if effect == 'none':
        return image_path
    
    try:
        # Import PhotoEffects from wallpaper-gui
        gui_path = Path(__file__).parent / "wallpaper-gui.py"
        spec = importlib.util.spec_from_file_location("wallpaper_gui", gui_path)
        gui_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gui_module)
        
        # Use the GUI's PhotoEffects class
        return gui_module.PhotoEffects.apply_effect(image_path, effect, temp_dir)
        
    except Exception as e:
        print(f"Warning: Could not apply {effect} effect: {e}", file=sys.stderr)
        return image_path


def get_backend_manager():
    """Get backend manager instance."""
    backend_path = Path(__file__).parent / "wall-it-backend-manager.py"
    spec = importlib.util.spec_from_file_location("backend_manager", backend_path)
    backend_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend_module)
    return backend_module.BackendManager()


def get_active_monitor(backend_manager=None) -> Optional[str]:
    """Get the currently focused monitor using backend manager."""
    if not backend_manager:
        backend_manager = get_backend_manager()
    
    try:
        monitor = backend_manager.get_active_monitor()
        if monitor:
            print(f"Wall-IT: Detected focused monitor: {monitor}")
        return monitor
    except Exception as e:
        print(f"Warning: Could not detect focused monitor: {e}", file=sys.stderr)
        return None


def update_wallpaper_symlink(wallpaper_path: Path) -> bool:
    """Atomically update the current wallpaper symlink."""
    try:
        # Create temporary symlink first for atomic operation
        temp_link = config.CURRENT_WALLPAPER_LINK.with_suffix('.tmp')
        
        # Remove temp link if it exists
        if temp_link.exists() or temp_link.is_symlink():
            temp_link.unlink()
        
        # Create new symlink
        temp_link.symlink_to(wallpaper_path)
        
        # Atomic replace
        temp_link.replace(config.CURRENT_WALLPAPER_LINK)
        return True
        
    except Exception as e:
        print(f"Error updating wallpaper symlink: {e}", file=sys.stderr)
        return False


def validate_transition(transition: str, backend_supports_transitions: bool) -> str:
    """
    Validate and normalize transition value.
    
    The 'none' transition causes issues with swww - it results in no wallpaper change.
    This is a known issue, so we prevent it by defaulting to 'fade' instead.
    """
    if not backend_supports_transitions:
        return 'none'
    
    # Prevent problematic transitions
    if transition in ('none', 'random'):
        print(f"⚠️ Prevented '{transition}' transition - using fade instead")
        return 'fade'
    
    return transition


def set_wallpaper(wallpaper_path: Path, transition: str, effect: str = 'none', 
                  backend_manager=None) -> bool:
    """Set wallpaper using backend manager with transition effect and photo effects."""
    try:
        if not backend_manager:
            backend_manager = get_backend_manager()
        
        # Apply effect if needed
        processed_path = wallpaper_path
        if effect != 'none':
            config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
            processed_path = apply_effect(wallpaper_path, effect, config.TEMP_DIR)
        
        # Get keybind mode and determine target monitor
        keybind_mode = get_keybind_mode()
        target_monitor = None
        
        if keybind_mode == "active":
            target_monitor = get_active_monitor(backend_manager)
            if target_monitor:
                print(f"Wall-IT: Targeting active monitor: {target_monitor}")
        
        # Get scaling mode
        scaling = get_wallpaper_scaling()
        
        # Validate transition
        transition = validate_transition(transition, backend_manager.supports_transitions())
        
        # Set wallpaper using backend manager
        success = backend_manager.set_wallpaper(processed_path, target_monitor, transition, scaling)
        
        if success:
            # Update current wallpaper symlink (always use original image)
            update_wallpaper_symlink(wallpaper_path)
            
            effect_text = f" with {effect} effect" if effect != 'none' else ""
            transition_text = f" with {transition} transition" if transition != 'none' else ""
            scaling_text = f" using {scaling} scaling" if scaling != 'crop' else ""
            print(f"Wall-IT: Set wallpaper to {wallpaper_path.name}{transition_text}{effect_text}{scaling_text}")
        
        return success
        
    except Exception as e:
        print(f"Error setting wallpaper: {e}", file=sys.stderr)
        return False


def print_matugen_status(scheme: str) -> None:
    """Print matugen color generation status."""
    scheme_display = config.SCHEME_DISPLAY_NAMES.get(scheme, scheme)
    print(f"Wall-IT: Colors updated with {scheme_display} scheme")
