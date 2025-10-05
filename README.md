# Wall-IT

A flexible wallpaper management tool for Linux desktop environments, primarily designed for Niri Wayland compositor with optional KDE Plasma support.

## Features

- Multi-backend support (primarily for Niri/swww)
- Per-monitor wallpaper support
- Wallpaper transition effects (requires swww)
- Automatic desktop environment detection

## Requirements

Core requirements:
- Python 3.x
- A wallpaper directory at `~/Pictures/Wallpapers`
- For Niri (primary backend):
  - Niri Wayland compositor
  - swww (wallpaper daemon)

Optional:
- KDE Plasma (alternative backend, auto-detected if running KDE)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/DiscoCevapi/Wall-IT.git
   cd Wall-IT
   ```

2. Create your wallpapers directory:
   ```bash
   mkdir -p ~/Pictures/Wallpapers
   ```

3. Copy your wallpapers into the directory:
   ```bash
   # Add some wallpapers
   cp /path/to/your/wallpapers/*.{jpg,png} ~/Pictures/Wallpapers/
   ```

4. Copy all scripts to your local bin directory:
   ```bash
   cp src/wall-it-*.py src/wall-it-{next,prev} ~/.local/bin/
   ```

5. Make all scripts executable:
   ```bash
   chmod +x ~/.local/bin/wall-it-*
   ```

6. Initialize the wallpaper symlink:
   ```bash
   # Use any wallpaper as your initial wallpaper
   ln -sf ~/Pictures/Wallpapers/your-wallpaper.jpg ~/.current-wallpaper
   ```

## Usage

Wall-IT will automatically detect your desktop environment (primarily supporting Niri):

- Set next wallpaper: `wall-it-next`
- Set previous wallpaper: `wall-it-prev`
- Check monitor status: `wall-it-monitor-state.py`
- Test backend detection: `wall-it-backend-manager.py`

## Keybindings

Default keybindings:
- Super + F2: Next wallpaper
- Super + F1: Previous wallpaper

To customize keybindings:
```bash
vim ~/.local/bin/wall-it-keybind-config.py
```

## License

MIT License
