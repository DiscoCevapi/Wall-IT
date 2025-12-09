#!/usr/bin/env python3
"""
Wall-IT Configuration Module
Centralized configuration and constants for Wall-IT
"""

import os
from pathlib import Path
from typing import Set

# Version
VERSION = "2.1.0"

# Paths - can be overridden by environment variables
WALLPAPER_DIR = Path(os.environ.get("WALLIT_WALLPAPER_DIR", Path.home() / "Pictures" / "Wallpapers"))
CACHE_DIR = Path(os.environ.get("WALLIT_CACHE_DIR", Path.home() / ".cache" / "wall-it"))
CURRENT_WALLPAPER_LINK = Path(os.environ.get("WALLIT_CURRENT_WALLPAPER", Path.home() / ".current-wallpaper"))

# Ensure directories exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)
if not WALLPAPER_DIR.exists():
    WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)

# Cache file paths
TRANSITION_FILE = CACHE_DIR / "transition_effect"
MATUGEN_ENABLED_FILE = CACHE_DIR / "matugen_enabled"
MATUGEN_SCHEME_FILE = CACHE_DIR / "matugen_scheme"
MATUGEN_COLORS_FILE = CACHE_DIR / "matugen_colors.json"
EFFECT_FILE = CACHE_DIR / "current_effect"
SCALING_FILE = CACHE_DIR / "wallpaper_scaling"
KEYBIND_MODE_FILE = CACHE_DIR / "keybind_mode"
MONITOR_STATE_FILE = CACHE_DIR / "monitor_state.json"
TEMP_DIR = CACHE_DIR / "temp"
LOG_FILE = CACHE_DIR / "launcher.log"

# Supported image extensions
IMAGE_EXTENSIONS: Set[str] = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff'}

# Transition constants
DEFAULT_TRANSITION = "fade"
TRANSITION_FPS = 60  # Increased from 30 for smoother transitions
TRANSITION_DURATION = 0.8  # Reduced from 1.5 for faster wallpaper changes
STARTUP_TRANSITION_FPS = 60
STARTUP_TRANSITION_DURATION = 0.5

# Scaling constants
DEFAULT_SCALING = "crop"

# Effect constants
DEFAULT_EFFECT = "none"

# Keybind constants
DEFAULT_KEYBIND_MODE = "all"

# Matugen constants
DEFAULT_MATUGEN_ENABLED = True
DEFAULT_MATUGEN_SCHEME = "scheme-expressive"

# Old scheme name mapping (for backwards compatibility)
SCHEME_NAME_MAP = {
    'content': 'scheme-content',
    'expressive': 'scheme-expressive',
    'fidelity': 'scheme-fidelity',
    'fruit-salad': 'scheme-fruit-salad',
    'monochrome': 'scheme-monochrome',
    'neutral': 'scheme-neutral',
    'rainbow': 'scheme-rainbow',
    'tonal-spot': 'scheme-tonal-spot'
}

# Scheme display names
SCHEME_DISPLAY_NAMES = {
    'scheme-tonal-spot': 'Tonal Spot',
    'scheme-content': 'Content',
    'scheme-expressive': 'Expressive',
    'scheme-fidelity': 'Fidelity',
    'scheme-fruit-salad': 'Fruit Salad',
    'scheme-monochrome': 'Monochrome',
    'scheme-neutral': 'Neutral',
    'scheme-rainbow': 'Rainbow'
}

# Daemon constants
SWWW_DAEMON_NAME = 'swww-daemon'
SWWW_INIT_DELAY = 1.0

# Photo effect quality
EFFECT_JPEG_QUALITY = 95
