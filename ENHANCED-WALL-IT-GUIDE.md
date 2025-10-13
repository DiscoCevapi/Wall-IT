# Enhanced Wall-IT 2.0 - Universal Wayland Wallpaper Manager

Enhanced Wall-IT is a comprehensive wallpaper management system that supports per-workspace wallpapers, multi-monitor setups, and universal Wayland compositor integration.

## New Features in 2.0

### 🖥️ Per-Workspace Wallpapers
- **Different wallpapers for each virtual desktop/workspace**
- **Automatic wallpaper switching** when changing workspaces
- **Per-workspace matugen color schemes**
- **Persistent settings** across sessions

### 🖼️ Multi-Monitor Support
- **Individual wallpapers** for each monitor
- **Per-monitor scaling and resize options**
- **Synchronized mode** to use same wallpaper across all monitors
- **Monitor hotplug support** for dynamic setups

### 🌈 Enhanced Display Scaling
- **Universal scaling** that works across all Wayland compositors
- **Per-monitor scaling configuration**
- **Automatic detection** of monitor characteristics
- **Smart resize modes**: crop, fit, stretch, no-resize

### 🔄 Universal Compositor Support
- **Automatic detection** of running compositor
- **Unified interface** across different compositors
- **Fallback mechanisms** for unsupported features
- **Supports**: niri, Hyprland, Sway, River, Wayfire, and more

## Installation

### Requirements
- **Python 3.6+** with `toml` library
- **swww** for wallpaper management
- **matugen** for dynamic color theming (optional)
- A supported Wayland compositor

### Install Python Dependencies
On Arch Linux:
```bash
sudo pacman -S python-toml
```

On other distributions:
```bash
pip install toml  # or use your package manager
```

### Setup Enhanced Wall-IT
1. **Copy enhanced scripts** to your Wall-IT directory
2. **Run initial setup**:
   ```bash
   python3 wall-it-enhanced.py status
   ```
3. **This will create** the configuration structure in `~/.config/wall-it/`

## Usage

### Command Line Interface

#### Basic Commands
```bash
# Cycle to next wallpaper (supports per-workspace)
python3 wall-it-enhanced.py next

# Cycle to previous wallpaper  
python3 wall-it-enhanced.py prev

# Show current status and configuration
python3 wall-it-enhanced.py status

# Restore wallpapers for current workspace
python3 wall-it-enhanced.py restore
```

#### Advanced Commands
```bash
# Set wallpaper for specific workspace
python3 wall-it-enhanced.py workspace -w /path/to/wallpaper.jpg -ws 2

# Set wallpaper for specific monitor
python3 wall-it-enhanced.py monitor -w /path/to/wallpaper.jpg -m HDMI-A-1

# Sync same wallpaper to all monitors
python3 wall-it-enhanced.py sync -w /path/to/wallpaper.jpg
```

### Drop-in Replacement Scripts

Enhanced Wall-IT provides drop-in replacement scripts that automatically use the new features:

```bash
# Use enhanced scripts (backward compatible)
./wallpaper-next-enhanced
./wallpaper-prev-enhanced
```

These will automatically:
- Use per-workspace wallpapers if enabled
- Handle multi-monitor setups correctly
- Fall back to original scripts if enhanced version unavailable

## Configuration

### Main Configuration (`~/.config/wall-it/config.toml`)

```toml
[wall-it]
version = "2.0"
compositor = "auto"  # or specify: niri, hyprland, sway, etc.

[features]
per_workspace_wallpapers = true
per_monitor_wallpapers = true  
matugen_integration = true
transition_effects = true

[defaults]
wallpaper_directory = "~/Pictures/Wallpapers"
resize_mode = "crop"  # crop, fit, stretch, no
transition_type = "fade"
transition_duration = 1.5
matugen_scheme = "scheme-tonal-spot"
matugen_enabled = true

[scaling]
auto_detect = true
global_scale = 1.0
per_monitor_scale = true
```

### Per-Monitor Configuration

Each monitor gets its own configuration file in `~/.config/wall-it/monitors/`:

```toml
# ~/.config/wall-it/monitors/HDMI-A-1.toml
[monitor]
name = "HDMI-A-1"
scale = 1.4
position = [0, 0]

[wallpaper]
current = "/home/user/Pictures/Wallpapers/monitor1.jpg"
resize_mode = "crop"
fill_color = "000000"

[workspace_wallpapers]
# Per-workspace wallpapers for this monitor
# These get populated automatically
```

### Per-Workspace Configuration

Each workspace gets its own configuration in `~/.config/wall-it/workspaces/`:

```toml  
# ~/.config/wall-it/workspaces/workspace-1.toml
[workspace]
id = 1
name = "workspace-1"

[wallpapers]
# Per-monitor wallpapers for this workspace
"HDMI-A-1" = "/path/to/workspace1-monitor1.jpg"
"DP-1" = "/path/to/workspace1-monitor2.jpg"

[settings]
matugen_enabled = true
matugen_scheme = "scheme-tonal-spot"
transition_type = "fade"
```

## Compositor Integration

### Keybinds Setup

#### Niri (`~/.config/niri/config.kdl`)
```kdl
binds {
    // Enhanced Wall-IT keybinds
    Super+Alt+G { spawn "python3" "/path/to/wall-it-enhanced.py" "status"; }
    Super+Alt+N { spawn "/path/to/wallpaper-next-enhanced"; }  
    Super+Alt+P { spawn "/path/to/wallpaper-prev-enhanced"; }
    
    // Additional enhanced features
    Super+Alt+W { spawn "python3" "/path/to/wall-it-enhanced.py" "restore"; }
    Super+Alt+M { spawn "python3" "/path/to/wall-it-enhanced.py" "sync" "-w" "$(swww query | grep currently | cut -d' ' -f6)"; }
}
```

#### Hyprland (`~/.config/hypr/hyprland.conf`)
```conf
# Enhanced Wall-IT keybinds
bind = SUPER ALT, G, exec, python3 /path/to/wall-it-enhanced.py status
bind = SUPER ALT, N, exec, /path/to/wallpaper-next-enhanced
bind = SUPER ALT, P, exec, /path/to/wallpaper-prev-enhanced
bind = SUPER ALT, W, exec, python3 /path/to/wall-it-enhanced.py restore
```

#### Sway (`~/.config/sway/config`)
```conf
# Enhanced Wall-IT keybinds  
bindsym $mod+Alt+g exec python3 /path/to/wall-it-enhanced.py status
bindsym $mod+Alt+n exec /path/to/wallpaper-next-enhanced
bindsym $mod+Alt+p exec /path/to/wallpaper-prev-enhanced
bindsym $mod+Alt+w exec python3 /path/to/wall-it-enhanced.py restore
```

### Workspace Change Integration

For automatic wallpaper switching on workspace changes, you can set up hooks:

#### Niri (using niri-msg)
```bash
# Add to your shell startup script
niri msg event-stream | while read -r event; do
    if echo "$event" | grep -q "WorkspaceChanged"; then
        python3 /path/to/wall-it-enhanced.py restore
    fi
done &
```

#### Hyprland (using hyprland-socket)
```bash
# Add to hyprland.conf
exec-once = socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock | while read -r event; do
    case "$event" in
        workspace*) python3 /path/to/wall-it-enhanced.py restore ;;
    esac
done
```

## Advanced Usage

### Wallpaper Profiles

Create themed wallpaper collections:

```bash
# Create a work profile
mkdir ~/.config/wall-it/profiles/
cat > ~/.config/wall-it/profiles/work.toml << EOF
[profile]
name = "work"
description = "Professional wallpapers for work"

[wallpapers]
workspace_1 = "/path/to/professional1.jpg"
workspace_2 = "/path/to/professional2.jpg"

[settings] 
matugen_scheme = "scheme-neutral"
transition_type = "simple"
EOF
```

### Multi-Monitor Scenarios

#### Scenario 1: Gaming Setup
- **Primary monitor**: Gaming wallpapers
- **Secondary monitor**: System monitoring wallpapers
- **Different scaling** per monitor

#### Scenario 2: Work Setup  
- **Workspace 1** (Development): Code-themed wallpapers
- **Workspace 2** (Communication): Clean, minimal wallpapers
- **Workspace 3** (Design): Creative, colorful wallpapers

#### Scenario 3: Ultrawide Setup
- **Single ultrawide monitor** with different wallpapers per workspace
- **Custom scaling** for optimal display
- **Synchronized** color themes across all applications

### Performance Tuning

For better performance with many wallpapers:

```toml
[performance]
cache_wallpapers = true
preload_workspace_wallpapers = false  # Set to true for instant switching
max_cache_size_mb = 512
cleanup_cache_on_exit = false
```

## Troubleshooting

### Common Issues

#### 1. "No compositor detected"
- Ensure your compositor is running
- Check if compositor is supported
- Try setting manual compositor in config: `compositor = "niri"`

#### 2. "Matugen failed"
- Ensure matugen is installed and in PATH
- Check if matugen config exists
- Try running matugen manually to test

#### 3. "Per-workspace wallpapers not working"
- Verify workspace detection: `python3 wall-it-enhanced.py status`
- Check if compositor supports workspace queries
- Enable debug mode: `debug = true` in config

#### 4. "Wallpapers not changing"
- Ensure swww-daemon is running
- Check wallpaper directory permissions
- Verify swww can access the image files

### Debug Mode

Enable detailed logging:

```toml
[wall-it]
debug = true
```

Then run with verbose output:
```bash
python3 wall-it-enhanced.py status
```

### Reset Configuration

To reset to defaults:
```bash
rm -rf ~/.config/wall-it/
python3 wall-it-enhanced.py status  # Recreates default config
```

## Migration from Original Wall-IT

Enhanced Wall-IT is backward compatible:

1. **Existing keybinds** continue to work
2. **Configuration** is migrated automatically
3. **Fallback scripts** ensure compatibility
4. **Gradual migration** - enable new features as needed

### Migration Steps

1. **Install enhanced scripts** alongside original ones
2. **Test with enhanced wrapper scripts**:
   ```bash
   /path/to/wallpaper-next-enhanced
   ```
3. **Update keybinds** to use enhanced features when ready
4. **Configure per-workspace wallpapers** as desired
5. **Set up multi-monitor configuration** if applicable

## Future Enhancements

### Planned Features
- **GUI interface** with per-workspace and multi-monitor support
- **Wallpaper scheduling** (time-based changes)
- **Smart wallpaper selection** based on content/mood
- **Cloud sync** for configurations
- **Advanced transition effects**
- **Integration with other theming tools**

## Contributing

Enhanced Wall-IT is designed to be:
- **Universal** - works across all Wayland compositors
- **Extensible** - easy to add new features
- **Maintainable** - clean, documented code
- **Compatible** - doesn't break existing setups

Feel free to contribute new compositor support, features, or bug fixes!

---

**Enhanced Wall-IT 2.0** - Making wallpaper management universal, powerful, and beautiful on Wayland! 🎨✨
