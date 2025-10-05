# Wall-IT

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A modern wallpaper management tool for Linux desktop environments, featuring a GTK4-based GUI and powerful wallpaper effects. Primary support for Niri Wayland compositor with optional KDE Plasma integration.

![Wall-IT Screenshot](docs/screenshot.png)

## Features

- Multi-backend support (primarily for Niri/swww)
- Per-monitor wallpaper support
- Wallpaper transition effects (requires swww)
- Automatic desktop environment detection
- Built-in graphical interface (wallpaper-gui.py)

## Quick Start

```bash
# Install dependencies (Arch/CachyOS)
yay -S gtk4 python-gobject python-cairo gdk-pixbuf2 libadwaita niri swww

# Clone and install
git clone https://github.com/DiscoCevapi/Wall-IT.git
cd Wall-IT
cp src/wall-it-*.py src/wall-it-{next,prev} ~/.local/bin/
chmod +x ~/.local/bin/wall-it-*

# Start GUI
wallpaper-gui.py
```

For detailed installation instructions for all distributions, see [INSTALL.md](INSTALL.md).

## Requirements

### Required Packages
- `python3` (3.6 or newer)
- `niri` (Wayland compositor)
- `swww` (wallpaper daemon)
- `gtk4` (for GUI interface)
- `python-gobject` (for GTK4 bindings)
- `python-cairo` (for drawing support)
- `gdk-pixbuf2` (for image handling)
- `libadwaita` (for modern GTK widgets)
- `python-pathlib` (Python path handling)
- `find` (for wallpaper discovery)
- `readlink` (for wallpaper tracking)

### Image Requirements
- Supported formats: JPG, PNG, WebP, BMP, TIFF, AVIF, HEIC
- Images must be valid and non-empty
- High-resolution images are automatically optimized

### Directory Structure
```bash
# These will be created during installation
~/Pictures/Wallpapers/     # Your wallpaper directory
~/.local/bin/             # Scripts directory
~/.current-wallpaper      # Symlink to current wallpaper
```

### Optional Dependencies
- `python-pillow` (for image effects)
- `matugen` (for color scheme generation)
- `wmctrl` (for window management)
- `KDE Plasma` (alternative backend, auto-detected)
  - `qdbus`
  - `plasma-apply-wallpaperimage`

### For Arch/CachyOS Users
```bash
# Install required packages
yay -S python niri swww gtk4 python-gobject python-cairo gdk-pixbuf2 libadwaita python-pathlib coreutils

# Optional: For KDE support
yay -S plasma-desktop qt5-tools
```

### For Other Distros
Ensure you have:
1. Niri compositor installed and running
2. swww daemon installed and running
3. Python 3.6 or newer
4. Basic Unix tools (find, readlink)

## Installation

1. Install required packages (see Requirements section above)

2. Start swww daemon if not running:
   ```bash
   # First time setup:
   systemctl --user enable --now swww.service
   
   # Or manually start it:
   swww-daemon & disown
   sleep 1  # Wait for daemon to start
   ```

3. Clone this repository:
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

5. Make all scripts executable and update PATH:
   ```bash
   chmod +x ~/.local/bin/wall-it-*
   
   # Add ~/.local/bin to PATH
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc  # For zsh
   # OR
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc  # For bash
   
   # Apply PATH change
   export PATH="$HOME/.local/bin:$PATH"
   ```

6. Initialize the wallpaper symlink:
   ```bash
   # Use any wallpaper as your initial wallpaper
   ln -sf ~/Pictures/Wallpapers/your-wallpaper.jpg ~/.current-wallpaper
   ```

## Usage

### First Run
Test if everything is working:
```bash
# Should show "Using NIRI backend"
wall-it-backend-manager.py

# Set your first wallpaper
wall-it-next
```

### Regular Use
Wall-IT will automatically detect your desktop environment (primarily supporting Niri):

#### Command Line
- Set next wallpaper: `wall-it-next`
- Set previous wallpaper: `wall-it-prev`
- Check monitor status: `wall-it-monitor-state.py`
- Test backend detection: `wall-it-backend-manager.py`

#### Graphical Interface
- Start the GUI: `wallpaper-gui.py`
- Browse and preview wallpapers
- Set wallpapers with a click
- See current wallpaper status

## Keybindings

Default keybindings:
- Super + F2: Next wallpaper
- Super + F1: Previous wallpaper

To customize keybindings:
```bash
vim ~/.local/bin/wall-it-keybind-config.py
```

## Troubleshooting

### Common Issues

1. "Command not found"
   ```bash
   # Add ~/.local/bin to your PATH:
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc  # For zsh
   # OR
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc  # For bash
   ```

2. "No wallpapers found"
   ```bash
   # Make sure you have wallpapers in the right directory
   ls ~/Pictures/Wallpapers/*.{jpg,png,jpeg}
   ```

3. "swww daemon not running"
   ```bash
   # Start swww daemon:
   swww-daemon & disown
   sleep 1  # Wait for daemon to start
   
   # Check if it's running:
   swww query
   ```

4. "gi.repository.GLib.Error: gtk-error-quark" or other GTK errors
   ```bash
   # Make sure you have all GTK4 dependencies installed:
   yay -S gtk4 python-gobject python-cairo gdk-pixbuf2 libadwaita
   
   # For other distros, install equivalent packages:
   # Ubuntu/Debian: libgtk-4-1 python3-gi python3-cairo gdk-pixbuf2 libadwaita-1-0
   # Fedora: gtk4 python3-gobject python3-cairo gdk-pixbuf2 libadwaita
   ```

5. KDE-related errors
   - These can be ignored if you're not using KDE
   - Only relevant if you're actually running KDE Plasma

### Getting Help
If you encounter issues:
1. Run `wall-it-backend-manager.py` to see backend status
2. Check your wallpaper directory exists
3. Ensure swww daemon is running
4. Make sure scripts are executable

## License

MIT License
