# Wall-IT - Professional Wallpaper Manager

**Version 2.1.0** - Refactored Edition

A professional, modular wallpaper manager for Linux with support for multiple desktop environments, per-monitor wallpaper management, photo effects, and Material You color theming via matugen.

## ✨ Features

- 🖼️ **Multi-Monitor Support** - Independent wallpaper management per monitor
- 🎨 **Photo Effects** - Blur, sharpen, grayscale, dramatic, vintage, and sepia effects
- 🌈 **Material You Integration** - Automatic color theme generation with matugen
- ⚡ **Fast Transitions** - Smooth wallpaper transitions with configurable effects
- 🖥️ **Multi-Backend Support** - Works with Niri, KDE, Hyprland, and LabWC
- ⌨️ **Keybind Support** - Switch wallpapers with keyboard shortcuts
- 🔄 **Configurable** - Environment variables for custom paths and settings
- 🎯 **Fit-Blur Mode** - Perfect for ultrawide monitors! Fits image and fills sides with blurred background

## 🚀 Performance Improvements (v2.1.0)

This refactored version includes significant performance and code quality improvements:

- **Faster Transitions**: Reduced transition duration from 1.5s to 0.8s (47% faster)
- **Smoother Animation**: Increased FPS from 30 to 60 for silky-smooth transitions
- **Matugen Timeout**: Added 5-second timeout to prevent blocking on large images
- **Code Deduplication**: Extracted 95% duplicate code into shared modules
- **Type Safety**: Added comprehensive type hints throughout
- **Atomic Operations**: Improved symlink updates with atomic file operations
- **Better Error Handling**: More specific error messages and FileNotFoundError handling
- **Robust Parsing**: Regex-based monitor parsing (more reliable than string splitting)
- **Configurable Constants**: Centralized configuration module for easy customization

## 📦 Installation

### Prerequisites

```bash
# Core dependencies
sudo pacman -S python python-pillow python-numpy gtk4 python-gobject

# Backend dependencies (install what you need)
sudo pacman -S swww  # For Niri/swww backend

# Optional
sudo pacman -S matugen  # For Material You color theming
```

### Install Wall-IT

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/wall-it.git
cd wall-it

# Install to ~/.local/bin
./install.sh

# Or manually:
cp wall-it-*.py ~/.local/bin/
cp wall-it-next ~/.local/bin/
cp wall-it-prev ~/.local/bin/
cp start-wall-it ~/.local/bin/
cp wallpaper-gui.py ~/.local/bin/
chmod +x ~/.local/bin/wall-it-* ~/.local/bin/start-wall-it ~/.local/bin/wallpaper-gui.py
```

## 🎮 Usage

### Command Line

```bash
# Switch to next wallpaper
wall-it-next

# Switch to previous wallpaper
wall-it-prev

# Start Wall-IT at login (add to your startup scripts)
start-wall-it

# Launch GUI
wallpaper-gui.py
```

### Keybindings

Add these to your compositor configuration:

#### Niri
```kdl
binds {
    Mod+W { spawn "wall-it-next"; }
    Mod+Shift+W { spawn "wall-it-prev"; }
}
```

#### Hyprland
```conf
bind = $mainMod, W, exec, wall-it-next
bind = $mainMod SHIFT, W, exec, wall-it-prev
```

## ⚙️ Configuration

Wall-IT uses a centralized configuration module that can be customized via environment variables:

### Environment Variables

```bash
# Custom wallpaper directory (default: ~/Pictures/Wallpapers)
export WALLIT_WALLPAPER_DIR="$HOME/Images/Wallpapers"

# Custom cache directory (default: ~/.cache/wall-it)
export WALLIT_CACHE_DIR="$HOME/.cache/my-wall-it"

# Custom current wallpaper symlink (default: ~/.current-wallpaper)
export WALLIT_CURRENT_WALLPAPER="$HOME/.current-wp"
```

### Configuration Files

Wall-IT stores its configuration in `~/.cache/wall-it/`:

- `transition_effect` - Current transition type (fade, wipe, grow, etc.)
- `current_effect` - Active photo effect (none, blur, vintage, etc.)
- `wallpaper_scaling` - Scaling mode (crop, fit, stretch, **fit-blur**)
- `keybind_mode` - Keybind behavior (all monitors or active only)
- `matugen_enabled` - Enable/disable Material You theming
- `matugen_scheme` - Color scheme (scheme-expressive, scheme-tonal-spot, etc.)
- `monitor_state.json` - Per-monitor wallpaper tracking

### Fit-Blur Mode for Ultrawide Monitors

Perfect for 21:9 or 32:9 ultrawides! The `fit-blur` scaling mode:
1. Fits the image to screen height (maintains aspect ratio)
2. Fills the sides with a zoomed, heavily blurred version of the image
3. Darkens the blurred background for better contrast
4. No black bars!

To enable:
```bash
echo "fit-blur" > ~/.cache/wall-it/wallpaper_scaling
```

Or use the GUI wallpaper manager to select "Fit-Blur" from the scaling options.

### Performance Tuning

Edit `wall-it-config.py` to adjust:

```python
# Transition speed (seconds)
TRANSITION_DURATION = 0.8  # Lower = faster (min 0.3)

# Transition smoothness (FPS)
TRANSITION_FPS = 60  # Higher = smoother (max 120)

# Matugen timeout (seconds)
# Adjust in wall-it-common.py, line 81
timeout=5.0  # Increase for very large images
```

## 🏗️ Architecture

### Module Structure

```
wall-it-config.py          # Centralized configuration and constants
wall-it-common.py          # Shared utility functions
wall-it-backend-manager.py # Multi-backend abstraction layer
wall-it-monitor-state.py   # Per-monitor state management
wall-it-next               # Next wallpaper script
wall-it-prev               # Previous wallpaper script
start-wall-it              # Startup/initialization script
wallpaper-gui.py           # GTK4 GUI application
```

### Backend Support

- **Niri** (via swww) - Full support with per-monitor and transitions
- **KDE Plasma** - Full support via plasma-apply-wallpaperimage
- **Hyprland** (via swww) - Full support with per-monitor and transitions
- **LabWC** - Basic support

## 🐛 Troubleshooting

### Wallpaper changes are slow

1. Check if matugen is blocking:
   ```bash
   # Disable matugen temporarily
   echo "false" > ~/.cache/wall-it/matugen_enabled
   ```

2. Adjust transition speed in `wall-it-config.py`:
   ```python
   TRANSITION_DURATION = 0.5  # Faster
   ```

### Transitions don't work

Ensure swww daemon is running:
```bash
pgrep swww-daemon || start-wall-it
```

### No wallpapers found

Check your wallpaper directory:
```bash
ls ~/Pictures/Wallpapers/
# Or check custom directory
echo $WALLIT_WALLPAPER_DIR
```

## 📝 Changelog

### Version 2.2.0 (2024-12-14) - Ultrawide Edition

#### New Features
- **Fit-Blur Scaling Mode** - Perfect for ultrawide monitors!
  - Fits standard 16:9/portrait images while preserving aspect ratio
  - Fills sides with beautifully blurred, darkened background
  - No more black bars on 21:9 or 32:9 displays
  - Automatic screen resolution detection (tested on 3440x1440)
  - Cached processing for instant wallpaper switching
  - Works with photo effects (effects applied first, then fit-blur)
  - Integrated in both CLI (keybinds) and GUI (double-click)

#### Technical
- New `wall-it-image-processor.py` module for advanced image processing
- Standalone CLI tool for testing: `wall-it-image-processor.py image.jpg -o output.jpg`
- Customizable blur radius (default: 40) and zoom factor (default: 1.5x)
- Smart caching based on file modification time

### Version 2.1.0 (2024-12-09) - Refactored Edition

#### Performance
- Reduced transition duration from 1.5s to 0.8s (47% faster)
- Increased transition FPS from 30 to 60 (100% smoother)
- Added 5-second timeout for matugen to prevent blocking

#### Code Quality
- Extracted duplicate code into `wall-it-common.py` module
- Created centralized `wall-it-config.py` for all constants
- Added comprehensive type hints throughout codebase
- Improved error handling with specific exception types
- Replaced string parsing with robust regex patterns

#### Reliability
- Atomic symlink updates to prevent race conditions
- Better FileNotFoundError handling for missing binaries
- Validated transition values to prevent 'none' transition bug
- Improved JSON state file handling with validation

#### Architecture
- Modular design with clear separation of concerns
- Configurable via environment variables
- DRY principle applied (wall-it-next and wall-it-prev share code)
- Documented transition safety checks

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

[Your chosen license here]

## 🙏 Credits

- Original concept and implementation
- Refactored by AI Assistant for improved performance and maintainability
- Community contributions welcome!

## 📧 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues first
- Provide system information and error messages
