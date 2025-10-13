# Wall-IT Changelog

## Version 2.1.0 - Major Feature Release

### 🎯 New Features

#### **Enhanced Wallpaper Scaling Options**
- **Multiple Scaling Modes**: Added comprehensive wallpaper sizing options including:
  - `Crop` - Crop image to fit screen (maintain aspect ratio)
  - `Fit` - Fit image to screen with bars (maintain aspect ratio) 
  - `Fill` - Fill screen stretching if needed
  - `Stretch` - Stretch image to exact screen dimensions
  - `Tile` - Repeat image to fill screen
  - `Center` - Center image without scaling
  - `No Resize` - Use image original size
- **Smart Tooltips**: Comprehensive tooltips explain each scaling mode's behavior
- **Persistent Settings**: Selected scaling mode is saved and remembered across sessions

#### **Expanded Photo Effects System**
- **27 Photo Effects**: Comprehensive collection including:
  - **Basic Effects**: Original, Blur, Sharp, Enhance, Vintage, Black/White
  - **Artistic Effects**: Oil Painting, Watercolor, Sketch, Cross Hatch, Posterize, Solarize
  - **Color Effects**: Sepia, Warm, Cool, Vibrant, Muted, High Contrast, Low Contrast
  - **Creative Effects**: Emboss, Edge Enhance, Smooth, Grain, Vignette, Invert, Rotate Hue
  - **Advanced Effects**: Dreamy, Cyberpunk, Film Noir, Vintage Film
- **Real-time Processing**: Effects are applied dynamically using PIL/Pillow
- **Effect Persistence**: Current effect setting persists across wallpaper changes

#### **Advanced Transition Effects**
- **14 Transition Types**: All valid swww transition effects:
  - **Directional**: Slide Left/Right, Slide Up/Down
  - **Organic**: Wave, Grow, Center, Outer
  - **Creative**: Wipe, Fade, Simple
  - **Random**: Any, Random Mix, None
- **Enhanced Animation**: Smooth transitions between wallpapers
- **Compositor Integration**: Optimized for swww and backend-specific effects

#### **Rich Weather Animation System**
- **12 Weather Types**: Comprehensive weather-based wallpaper animations:
  - **Precipitation**: Rain, Heavy Rain, Snow, Blizzard, Thunderstorm
  - **Atmospheric**: Fog, Wind, Clear Skies
  - **Special**: Aurora, Sunrise/Sunset Golden Hour, Partly Cloudy, Overcast
- **Dynamic Visual Effects**: Each weather type has unique animated overlays
- **Smart Detection**: Can integrate with weather data for automatic mode switching

#### **Hyprland Compositor Support**
- **Native Hyprland Backend**: Full support for Hyprland compositor
- **Monitor Management**: Multi-monitor support with Hyprland-specific optimizations
- **Dynamic Scaling**: Real-time monitor scaling adjustments
- **Seamless Integration**: Works alongside existing NIRI, KDE, and GNOME backends

### 🔧 UI/UX Improvements

#### **Streamlined Settings Dialog**
- **Simplified Interface**: Removed complex tabs, focused on essential settings
- **Clean General Tab**: System tray and keybind behavior settings in one place
- **Better Organization**: Logical grouping of related settings
- **Responsive Design**: Improved layout for different screen sizes

#### **Enhanced Toolbar Experience**
- **Compact Controls**: Optimized control spacing for laptop screens
- **Smart Tooltips**: Detailed tooltips for all controls explaining their function
- **Visual Feedback**: Clear icons and labels for better usability
- **Responsive Layout**: Two-row toolbar design for better organization

#### **Improved Status System**
- **Rich Status Messages**: Detailed feedback with emoji icons
- **Progress Indicators**: Better feedback during long operations
- **Error Handling**: More informative error messages with recovery suggestions

### 🛠️ Technical Enhancements

#### **Code Architecture**
- **Modular Effects System**: Cleanly separated photo effects processing
- **Backend Abstraction**: Improved backend management for multiple compositors
- **Error Resilience**: Better error handling and recovery mechanisms
- **Performance Optimization**: Reduced memory usage and faster thumbnail generation

#### **Compatibility Improvements**
- **GTK4 Optimization**: Better GTK4 integration and widget usage
- **Python 3.13 Support**: Full compatibility with latest Python versions
- **PIL/Pillow Integration**: Enhanced image processing capabilities
- **Cross-compositor Support**: Works across NIRI, Hyprland, KDE, and GNOME

### 🐛 Bug Fixes

- **Fixed Settings Dialog**: Removed duplicate tabs and UI elements
- **Monitor Detection**: Improved monitor discovery and configuration
- **Memory Leaks**: Fixed thumbnail caching and image processing memory issues  
- **UI Responsiveness**: Better GUI responsiveness during heavy operations
- **File Handling**: Improved wallpaper file management and validation

### 📈 Performance

- **Faster Startup**: Reduced application initialization time
- **Efficient Thumbnails**: Optimized thumbnail generation and caching
- **Memory Usage**: Lower memory footprint for large wallpaper collections
- **Background Processing**: Non-blocking operations for better user experience

### 🔄 Migration Notes

- **Backward Compatibility**: All existing wallpapers and settings are preserved
- **Automatic Upgrades**: Settings automatically migrate to new format
- **Configuration Preservation**: User preferences and customizations maintained

---

## Previous Versions

### Version 2.0.0 - Enhanced Wall-IT
- Initial enhanced release with system tray support
- Multi-monitor configuration
- Basic photo effects
- Timer functionality
- Drag and drop support

### Version 1.x - Original Wall-IT
- Basic wallpaper management
- Single monitor support  
- Simple file browser
- NIRI compositor integration