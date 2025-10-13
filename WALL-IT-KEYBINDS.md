# Wall-IT Keybind System 

Wall-IT now includes a comprehensive global keybind system that allows you to control wallpaper functions from anywhere in your desktop environment.

## 🚀 Features

- **Global Hotkeys**: Control wallpapers from any application
- **Custom Keybinds**: Add your own key combinations and actions
- **Background Daemon**: Lightweight service that runs independently
- **GUI Management**: Easy-to-use settings interface in Wall-IT
- **Integration**: Works with your existing Wall-IT setup and niri compositor

## 📋 Default Keybinds

The system comes with these default keybinds (compatible with your current niri config):

- `Ctrl+Alt+Right` - Next wallpaper
- `Ctrl+Alt+Left` - Previous wallpaper  
- `Ctrl+Alt+R` - Random wallpaper
- `Ctrl+Alt+W` - Open Wall-IT GUI

## 🎮 Available Actions

### Navigation
- `next_wallpaper` - Switch to next wallpaper
- `prev_wallpaper` - Switch to previous wallpaper  
- `random_wallpaper` - Set random wallpaper

### Effects (requires PIL/Pillow)
- `toggle_blur` - Apply blur effect
- `toggle_grayscale` - Apply grayscale effect
- `toggle_sepia` - Apply sepia effect
- `no_effect` - Remove all effects

### Colors (requires matugen)
- `refresh_colors` - Refresh matugen colors for current wallpaper

### GUI
- `open_gui` - Open Wall-IT GUI

### Custom
- `custom_command` - Custom shell command (placeholder)

## 🛠 Management Commands

Use the `wall-it-keybinds` script for easy management:

```bash
# Start the keybind daemon
wall-it-keybinds start

# Check daemon status  
wall-it-keybinds status

# List current keybinds
wall-it-keybinds list

# Add new keybind interactively
wall-it-keybinds add

# Reload keybinds after changes
wall-it-keybinds reload

# Stop daemon
wall-it-keybinds stop

# Open Wall-IT GUI settings
wall-it-keybinds gui
```

## ⚙️ Advanced Usage

### Command Line Configuration

```bash
# List available actions
python3 ~/.local/bin/wall-it-keybind-config.py actions

# Add keybind manually
python3 ~/.local/bin/wall-it-keybind-config.py add "ctrl+shift+n" "next_wallpaper"

# Remove keybind
python3 ~/.local/bin/wall-it-keybind-config.py remove "ctrl+shift+n"

# Enable/disable keybind
python3 ~/.local/bin/wall-it-keybind-config.py disable "ctrl+alt+r"
python3 ~/.local/bin/wall-it-keybind-config.py enable "ctrl+alt+r"
```

### GUI Management

1. Open Wall-IT GUI: `python3 ~/.local/bin/wallpaper-gui-v3.1.py`
2. Click the Settings button (⚙️)
3. Go to the "Keybinds" tab
4. Manage daemon, view/edit keybinds, and see available actions

## 🔧 Configuration Files

- **Keybinds**: `~/.cache/wall-it/keybinds.json`
- **Daemon PID**: `~/.cache/wall-it/keybind_daemon.pid`
- **Wall-IT Cache**: `~/.cache/wall-it/`

## 🧩 Integration with niri

Your current niri keybinds will continue to work:

```kdl
// In ~/.config/niri/config.kdl
Super+Alt+G { spawn "/home/DiscoNiri/.local/bin/wallpaper-gui.py"; }
Super+Alt+N { spawn "/home/DiscoNiri/.local/bin/wall-it-next"; }
Super+Alt+P { spawn "/home/DiscoNiri/.local/bin/wall-it-prev"; }
```

The Wall-IT keybind system adds **global** hotkeys that work system-wide, complementing your existing niri shortcuts.

## 🚨 Requirements

- **Python 3.7+** with `pynput` package
- **Wall-IT Enhanced v3.1+**
- **Linux desktop environment** (tested with niri/Wayland)

### Install pynput if needed:
```bash
pip install pynput
# or
paru -S python-pynput
```

## 🔄 Startup Integration  

To automatically start the keybind daemon with your desktop session, add this to your compositor startup:

**For niri** (`~/.config/niri/config.kdl`):
```kdl
spawn-at-startup "/home/DiscoNiri/.local/bin/wall-it-keybinds" "start"
```

**For other systems**, add to your autostart:
```bash
wall-it-keybinds start
```

## 🐛 Troubleshooting

### Daemon won't start
- Check if pynput is installed: `python3 -c "import pynput"`
- Check for permission issues with `~/.cache/wall-it/`
- View daemon output: `python3 ~/.local/bin/wall-it-keybind-daemon.py`

### Keybinds not working
- Ensure daemon is running: `wall-it-keybinds status`
- Check for key conflicts with other applications
- Try reloading: `wall-it-keybinds reload`

### Permission errors
- Ensure scripts are executable: `chmod +x ~/.local/bin/wall-it-*`
- Check cache directory permissions: `ls -la ~/.cache/wall-it/`

## 💡 Tips

1. **Key Format**: Use lowercase with `+` separators: `ctrl+alt+key`
2. **Valid Modifiers**: `ctrl`, `alt`, `shift`, `super`/`cmd`
3. **Reload Required**: After adding keybinds, use `wall-it-keybinds reload`
4. **GUI Changes**: Changes in the GUI are applied immediately
5. **Conflicts**: The system will warn about duplicate key combinations

## 🎨 Customization

You can extend the system by:

1. Adding custom actions to the config file
2. Creating your own shell scripts for complex actions
3. Modifying the daemon to support additional key formats
4. Integrating with other wallpaper tools

## 📝 Example Workflow

```bash
# Start daemon
wall-it-keybinds start

# Add a custom blur keybind
wall-it-keybinds add
# Enter: ctrl+alt+b
# Enter: toggle_blur

# Test your new keybind by pressing Ctrl+Alt+B

# View all keybinds
wall-it-keybinds list

# Open GUI for advanced management
wall-it-keybinds gui
```

Enjoy your enhanced Wall-IT experience with global keybind support! 🎉
