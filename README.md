# Wall-IT v2.1.0

🖼️ **Professional wallpaper manager with advanced features and compositor integration**

![Wall-IT Screenshot](assets/wall-it-banner.png)

## 🌟 Features

### 🎯 Core Functionality
- **Smart Wallpaper Management** - Organized collection with thumbnail previews
- **Multi-Monitor Support** - Individual wallpaper control per monitor
- **Auto Timer** - Automatic wallpaper rotation with customizable intervals
- **Drag & Drop** - Easy wallpaper import from file manager

### 🎨 Visual Effects
- **27 Photo Effects** - From subtle enhancements to artistic transformations
- **17 Transition Effects** - Smooth animations between wallpaper changes
- **12 Weather Animations** - Dynamic weather-based visual overlays
- **7 Scaling Modes** - Perfect fit for any screen size and aspect ratio

### 🖥️ Compositor Support
- **NIRI** - Full native integration
- **Hyprland** - Advanced features with dynamic scaling
- **KDE Plasma** - Multi-monitor and scaling support
- **GNOME** - Basic wallpaper setting support

### ⚡ Advanced Features
- **Keybind Integration** - System-wide hotkeys for quick wallpaper changes
- **Monitor-Aware Keybinds** - Target specific monitors or all at once
- **Color Integration** - Dynamic color scheme generation with matugen
- **Enhanced File Browser** - Grid-based wallpaper selection with bulk import

## 🚀 Installation

### Prerequisites
```bash
# Install dependencies
sudo pacman -S python python-gobject gtk4 python-pillow

# Optional: For dynamic colors
paru -S matugen
```

### Installation Steps
1. **Clone the repository:**
   ```bash
   git clone https://github.com/DiscoNiri/Wall-IT.git
   cd Wall-IT
   ```

2. **Install to user directory:**
   ```bash
   cp *.py ~/.local/bin/
   chmod +x ~/.local/bin/wallpaper-gui.py
   ```

3. **Create desktop entry:**
   ```bash
   cp wall-it.desktop ~/.local/share/applications/
   ```

## 🎮 Usage

### GUI Application
```bash
python ~/.local/bin/wallpaper-gui.py
```

### Command Line
```bash
# Set random wallpaper
python ~/.local/bin/wallpaper-gui.py --random

# Apply photo effect
python ~/.local/bin/wallpaper-gui.py --effect sepia

# Set keybind mode
python ~/.local/bin/wallpaper-gui.py --keybind-mode active

# Show version
python ~/.local/bin/wallpaper-gui.py --version
```

### Keybind Integration

#### NIRI Configuration
Add to `~/.config/niri/config.kdl`:
```kdl
binds {
    // Wall-IT controls
    Mod+W { spawn "python" "~/.local/bin/wallpaper-gui.py" "--random"; }
    Mod+Shift+W { spawn "python" "~/.local/bin/wallpaper-gui.py" "--effect" "vintage"; }
}
```

#### Hyprland Configuration
Add to `~/.config/hypr/hyprland.conf`:
```conf
# Wall-IT keybinds
bind = SUPER, W, exec, python ~/.local/bin/wallpaper-gui.py --random
bind = SUPER_SHIFT, W, exec, python ~/.local/bin/wallpaper-gui.py --effect sepia
```

## 🎨 Photo Effects

Wall-IT includes 27 professional photo effects:

**Basic Effects:**
- Original, Blur, Sharp, Enhance, Vintage, Black/White

**Artistic Effects:**
- Oil Painting, Watercolor, Sketch, Cross Hatch, Posterize, Solarize

**Color Effects:**
- Sepia, Warm, Cool, Vibrant, Muted, High/Low Contrast

**Creative Effects:**
- Emboss, Edge Enhance, Smooth, Grain, Vignette, Invert, Rotate Hue

**Advanced Effects:**
- Dreamy, Cyberpunk, Film Noir, Vintage Film

## 🔄 Transition Effects

Choose from 17 smooth transition animations:
- **Directional:** Slide Left/Right, Slide Up/Down
- **Organic:** Wave, Grow, Center, Outer  
- **Creative:** Wipe, Dissolve, Pixelize, Diamond, Spiral
- **Random:** Any, Random Mix, Simple

## 🌤️ Weather Animations

12 dynamic weather overlays:
- **Precipitation:** Rain, Heavy Rain, Snow, Blizzard, Thunderstorm
- **Atmospheric:** Fog, Wind, Clear Skies
- **Special:** Aurora, Golden Hour, Partly Cloudy, Overcast

## 📐 Wallpaper Scaling

7 intelligent scaling modes:
- **Crop** - Maintain aspect ratio, crop to fit
- **Fit** - Maintain aspect ratio, add bars if needed
- **Fill** - Fill screen, stretch if necessary
- **Stretch** - Stretch to exact screen dimensions
- **Tile** - Repeat image pattern
- **Center** - Center without scaling
- **No Resize** - Use original image size

## ⚙️ Configuration

### Settings Dialog
Access via the settings button in the toolbar:
- System tray behavior
- Keybind targeting (all monitors vs active monitor)
- Feature availability status
- Directory information

### Monitor Configuration
- Automatic monitor detection
- Per-monitor wallpaper control
- Dynamic scaling support (Hyprland)
- Resolution and scaling information

## 🔧 Technical Details

### Architecture
- **GTK4** - Modern UI framework
- **PIL/Pillow** - Advanced image processing
- **Backend System** - Modular compositor support
- **Caching** - Efficient thumbnail management

### Supported Image Formats
- JPEG, PNG, WebP, AVIF, HEIC, HEIF
- BMP, TIFF, TIF
- High-resolution and ultrawide support

## 📊 Version 2.1.0 Highlights

### New in This Release
- ✨ **27 Photo Effects** - Professional image processing
- 🎬 **17 Transition Effects** - Smooth wallpaper animations  
- 🌦️ **12 Weather Animations** - Dynamic weather overlays
- 🖥️ **Enhanced Multi-Monitor** - Improved monitor detection
- 📐 **7 Scaling Modes** - Perfect wallpaper fitting
- 🎯 **Hyprland Support** - Full Hyprland compositor integration
- 🛠️ **Streamlined UI** - Cleaner settings and better tooltips

### Performance Improvements
- 🚀 Faster startup and thumbnail generation
- 🧠 Lower memory usage for large collections
- ⚡ Non-blocking operations for better responsiveness

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, and pull requests.

### Development Setup
1. Fork the repository
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **NIRI** - For the excellent Wayland compositor
- **Hyprland** - For dynamic compositor features
- **swww** - For smooth wallpaper transitions
- **matugen** - For dynamic color generation
- **PIL/Pillow** - For image processing capabilities

---

**Wall-IT v2.1.0** - Professional wallpaper management for Linux desktop environments.

*Made with ❤️ by DiscoNiri*