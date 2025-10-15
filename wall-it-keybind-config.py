#!/usr/bin/env python3
"""
Wall-IT Keybind Configuration
Defines keybindings for wallpaper management
"""

# Keybind definitions for wallpaper management
KEYBINDS = {
    'next_wallpaper': {
        'keys': ['Super+Alt+N'],
        'command': '/home/DiscoLab/.local/bin/wall-it-next',
        'description': 'Next wallpaper'
    },
    'prev_wallpaper': {
        'keys': ['Super+Alt+P'], 
        'command': '/home/DiscoLab/.local/bin/wall-it-prev',
        'description': 'Previous wallpaper'
    },
    'open_gui': {
        'keys': ['Super+Alt+G'],
        'command': '/home/DiscoLab/.local/bin/wallpaper-gui.py',
        'description': 'Open Wall-IT GUI'
    },
    'start_daemon': {
        'keys': ['Super+Alt+W'],
        'command': '/home/DiscoLab/.local/bin/start-wall-it',
        'description': 'Start Wall-IT daemon'
    }
}

# Daemon settings
DAEMON_SETTINGS = {
    'poll_interval': 0.1,  # seconds
    'log_level': 'INFO'
}
