#!/usr/bin/env python3
"""
Wall-IT Keybind Configuration Module
Defines keybindings for wallpaper management with proper class structure
"""

from typing import Dict, List, NamedTuple


class KeybindAction(NamedTuple):
    """Represents an action to be performed when a keybind is triggered"""
    command: List[str]
    description: str


class Keybind(NamedTuple):
    """Represents a keybind with its associated action"""
    key_combination: str
    action: KeybindAction
    enabled: bool = True


class WallITKeybindConfig:
    """Configuration class for Wall-IT keybinds"""

    def __init__(self):
        # Define the keybinds
        self.keybinds = {
            'next_wallpaper': Keybind(
                key_combination='Super+Alt+N',
                action=KeybindAction(
                    command=['wall-it-next'],
                    description='Next wallpaper'
                ),
                enabled=True
            ),
            'prev_wallpaper': Keybind(
                key_combination='Super+Alt+P',
                action=KeybindAction(
                    command=['wall-it-prev'],
                    description='Previous wallpaper'
                ),
                enabled=True
            ),
            'open_gui': Keybind(
                key_combination='Super+Alt+G',
                action=KeybindAction(
                    command=['wallpaper-gui.py'],
                    description='Open Wall-IT GUI'
                ),
                enabled=True
            ),
            'start_daemon': Keybind(
                key_combination='Super+Alt+W',
                action=KeybindAction(
                    command=['start-wall-it'],
                    description='Start Wall-IT daemon'
                ),
                enabled=True
            )
        }

    def get_enabled_keybinds(self) -> List[Keybind]:
        """Return list of enabled keybinds"""
        return [kb for kb in self.keybinds.values() if kb.enabled]

    def get_keybind(self, name: str) -> Keybind:
        """Get a specific keybind by name"""
        return self.keybinds.get(name)

    def set_keybind_enabled(self, name: str, enabled: bool):
        """Enable or disable a specific keybind"""
        if name in self.keybinds:
            kb = self.keybinds[name]
            self.keybinds[name] = Keybind(
                key_combination=kb.key_combination,
                action=kb.action,
                enabled=enabled
            )


# For backward compatibility with the old format
KEYBINDS = {
    'next_wallpaper': {
        'keys': ['Super+Alt+N'],
        'command': ['wall-it-next'],
        'description': 'Next wallpaper'
    },
    'prev_wallpaper': {
        'keys': ['Super+Alt+P'],
        'command': ['wall-it-prev'],
        'description': 'Previous wallpaper'
    },
    'open_gui': {
        'keys': ['Super+Alt+G'],
        'command': ['wallpaper-gui.py'],
        'description': 'Open Wall-IT GUI'
    },
    'start_daemon': {
        'keys': ['Super+Alt+W'],
        'command': ['start-wall-it'],
        'description': 'Start Wall-IT daemon'
    }
}