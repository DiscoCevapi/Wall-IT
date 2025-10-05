# Wall-IT

A flexible wallpaper management tool for Linux desktop environments, with special support for Niri Wayland compositor and KDE Plasma.

## Features

- Multi-backend support (Niri/swww, KDE Plasma)
- Per-monitor wallpaper support
- Wallpaper transition effects
- Automatic desktop environment detection
- Keyboard shortcut support

## Components

- `wall-it-backend-manager.py`: Core backend management and auto-detection
- `wall-it-kde-backend.py`: KDE Plasma backend implementation
- `wall-it-keybind-config.py`: Keyboard shortcut configuration
- `wall-it-keyd-manager.py`: Key binding manager
- `wall-it-monitor-state.py`: Monitor state detection and management
- `wall-it-next`: Next wallpaper command
- `wall-it-prev`: Previous wallpaper command

## Requirements

- Python 3.x
- For Niri backend:
  - Niri Wayland compositor
  - swww (wallpaper daemon)
- For KDE backend:
  - KDE Plasma desktop environment

## Installation

1. Copy the Python scripts to your local bin directory:
   ```bash
   cp src/wall-it-*.py ~/.local/bin/
   ```

2. Make the scripts executable:
   ```bash
   chmod +x ~/.local/bin/wall-it-*.py
   ```

3. Set up keyboard shortcuts (optional):
   ```bash
   ~/.local/bin/wall-it-keybind-config.py
   ```

## Usage

Wall-IT will automatically detect your desktop environment and use the appropriate backend.

- Set wallpaper: `wall-it-next`
- Previous wallpaper: `wall-it-prev`
- Check monitor status: `wall-it-monitor-state.py`

## License

MIT License