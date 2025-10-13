#!/usr/bin/env python3
"""
Wall-IT Keybind Configuration
Defines keybindings for wallpaper management
"""

# Keybind definitions for wallpaper management
KEYBINDS = {
    'next_wallpaper': {
        'keys': ['Super+F2'],
        'command': '/home/DiscoNiri/.local/bin/wall-it-next',
        'description': 'Next wallpaper'
    },
    'prev_wallpaper': {
        'keys': ['Super+F1'], 
        'command': '/home/DiscoNiri/.local/bin/wall-it-prev',
        'description': 'Previous wallpaper'
    }
}

# Daemon settings
DAEMON_SETTINGS = {
    'poll_interval': 0.1,  # seconds
    'log_level': 'INFO'
}
