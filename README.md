# Wall-IT

A flexible wallpaper management tool for Linux desktop environments, primarily designed for Niri Wayland compositor with optional KDE Plasma support.

## Features

- Multi-backend support (primarily for Niri/swww)
- Per-monitor wallpaper support
- Wallpaper transition effects (requires swww)
- Automatic desktop environment detection

## Requirements

### Required Packages
- `python3` (3.6 or newer)
- `niri` (Wayland compositor)
- `swww` (wallpaper daemon)
- `python-pathlib` (Python path handling)
- `find` (for wallpaper discovery)
- `readlink` (for wallpaper tracking)

### Directory Structure
```bash
# These will be created during installation
~/Pictures/Wallpapers/     # Your wallpaper directory
~/.local/bin/             # Scripts directory
~/.current-wallpaper      # Symlink to current wallpaper
```

### Optional Dependencies
- `KDE Plasma` (alternative backend, auto-detected)
  - `qdbus`
  - `plasma-apply-wallpaperimage`

### For Arch/CachyOS Users
```bash
# Install required packages
yay -S python niri swww python-pathlib coreutils

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

4. KDE-related errors
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
