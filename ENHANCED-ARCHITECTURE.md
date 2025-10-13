# Enhanced Wall-IT Architecture Design

## New Features to Implement

### 1. Per-Workspace Wallpapers
- **Concept**: Different wallpapers for each virtual desktop/workspace
- **Storage**: Track current workspace and associated wallpaper
- **Sync**: Automatically change wallpaper when switching workspaces
- **Fallback**: Global wallpaper when no workspace-specific wallpaper is set

### 2. Multi-Monitor Support  
- **Individual Control**: Each monitor can have different wallpapers
- **Synchronized Mode**: Option to use same wallpaper across all monitors
- **Per-Monitor Settings**: Different scaling/resize options per monitor

### 3. Display Scaling Options
- **Universal Config**: Scaling options that work across all Wayland compositors
- **Per-Monitor Scaling**: Different scaling for different monitors
- **Compositor Integration**: Leverage compositor-specific scaling when available

## Technical Architecture

### Configuration Structure
```
~/.config/wall-it/
├── config.toml                 # Main configuration
├── workspaces/                 # Per-workspace settings
│   ├── workspace-1.toml
│   ├── workspace-2.toml
│   └── ...
├── monitors/                   # Per-monitor settings
│   ├── HDMI-A-1.toml
│   ├── DP-1.toml
│   └── ...
├── profiles/                   # Wallpaper profiles/themes
│   ├── work.toml
│   ├── gaming.toml
│   └── ...
└── cache/                      # Runtime state
    ├── current-workspace
    ├── current-monitor-state
    └── last-wallpapers.json
```

### Universal Compositor Integration

#### Workspace Detection:
- **Niri**: `niri msg workspaces`
- **Hyprland**: `hyprctl workspaces -j`
- **Sway**: `swaymsg -t get_workspaces`
- **River**: `riverctl list-inputs` (with river-status)
- **Wayfire**: Through IPC if available

#### Monitor Detection:
- **Universal**: `swww query` (works with all swww-compatible compositors)
- **Niri**: `niri msg outputs`
- **Hyprland**: `hyprctl monitors -j`
- **Sway**: `swaymsg -t get_outputs`

## Features Implementation Plan

### Phase 1: Multi-Monitor Support
1. **Monitor Detection**: Universal monitor discovery
2. **Per-Monitor Wallpapers**: Individual wallpaper management
3. **Monitor-Specific Settings**: Scaling, resize options per monitor

### Phase 2: Per-Workspace Wallpapers  
1. **Workspace Detection**: Universal workspace detection
2. **Workspace State Tracking**: Monitor workspace changes
3. **Automatic Wallpaper Switching**: Change wallpaper on workspace switch

### Phase 3: Advanced Features
1. **Wallpaper Profiles**: Themed collections of wallpapers
2. **Smart Scaling**: Adaptive scaling based on monitor characteristics  
3. **Transition Effects**: Advanced transitions between wallpapers
4. **Schedule Support**: Time-based wallpaper changes

## Configuration Format

### Main Config (`config.toml`)
```toml
[wall-it]
version = "2.0"
compositor = "auto"  # auto-detect or specify: niri, hyprland, sway, etc.

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

[scaling]
auto_detect = true
global_scale = 1.0
per_monitor_scale = true
```

### Per-Monitor Config (`monitors/HDMI-A-1.toml`)
```toml
[monitor]
name = "HDMI-A-1"
resolution = "3440x1440"
scale = 1.4
position = [0, 0]

[wallpaper]
current = "/home/user/Pictures/Wallpapers/monitor1.jpg"
resize_mode = "crop"
fill_color = "000000"

[workspace_wallpapers]
workspace_1 = "/path/to/workspace1.jpg"
workspace_2 = "/path/to/workspace2.jpg"
```

### Per-Workspace Config (`workspaces/workspace-1.toml`)
```toml
[workspace]
id = 1
name = "workspace-1"
active = false

[wallpapers]
# Per-monitor wallpapers for this workspace
"HDMI-A-1" = "/path/to/workspace1-monitor1.jpg"
"DP-1" = "/path/to/workspace1-monitor2.jpg"

[settings]
matugen_enabled = true
matugen_scheme = "scheme-tonal-spot"
transition_type = "fade"
```

## Benefits

### Universal Compatibility
- **Works across all major Wayland compositors**
- **Consistent experience regardless of desktop environment**
- **Fallback mechanisms for unsupported features**

### Enhanced User Experience
- **Context-aware wallpapers** (different wallpapers for work vs gaming workspaces)
- **Multi-monitor optimization** (proper scaling and positioning)
- **Seamless integration** with existing matugen color theming

### Scalability
- **Modular design** allows adding new features easily
- **Profile system** for easy wallpaper theme switching
- **Smart caching** for performance optimization

This architecture will make Wall-IT the most comprehensive wallpaper management solution for Wayland compositors!
