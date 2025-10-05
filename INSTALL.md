# Detailed Installation Guide

## System Requirements

### Arch Linux / CachyOS / Manjaro
```bash
# Install required packages
yay -S gtk4 python-gobject python-cairo gdk-pixbuf2 libadwaita python-pathlib coreutils niri swww

# Optional packages
yay -S python-pillow matugen wmctrl

# For KDE support (optional)
yay -S plasma-desktop qt5-tools
```

### Ubuntu / Debian
```bash
# Install required packages
sudo apt update
sudo apt install python3 python3-gi python3-cairo gir1.2-gtk-4.0 libgdk-pixbuf2.0-0 libadwaita-1-0 coreutils

# Optional packages
sudo apt install python3-pil wmctrl

# Install swww (manual installation required)
# See: https://github.com/LGFae/swww
```

### Fedora
```bash
# Install required packages
sudo dnf install python3 gtk4 python3-gobject python3-cairo gdk-pixbuf2 libadwaita coreutils

# Optional packages
sudo dnf install python3-pillow wmctrl

# Install swww (manual installation required)
# See: https://github.com/LGFae/swww
```

## Python Dependencies

Install Python dependencies using pip:
```bash
# Install required packages
pip install --user -r requirements.txt
```

## Setting up Wall-IT

1. Create required directories:
```bash
# Create wallpapers directory
mkdir -p ~/Pictures/Wallpapers

# Create local bin directory (if it doesn't exist)
mkdir -p ~/.local/bin
```

2. Clone and install Wall-IT:
```bash
# Clone repository
git clone https://github.com/DiscoCevapi/Wall-IT.git
cd Wall-IT

# Copy scripts to ~/.local/bin
cp src/wall-it-*.py src/wall-it-{next,prev} ~/.local/bin/

# Make scripts executable
chmod +x ~/.local/bin/wall-it-*
```

3. Add ~/.local/bin to PATH:
```bash
# For zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# For bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

4. Start swww daemon:
```bash
# Start swww daemon (if not running)
swww-daemon & disown
sleep 1  # Wait for daemon to start

# Alternatively, enable as a systemd service
systemctl --user enable --now swww.service
```

5. Initialize wallpaper symlink:
```bash
# Add some wallpapers first
cp /path/to/your/wallpapers/*.{jpg,png} ~/Pictures/Wallpapers/

# Create initial symlink (use any wallpaper as your first wallpaper)
ln -sf ~/Pictures/Wallpapers/your-wallpaper.jpg ~/.current-wallpaper
```

## Verifying Installation

Test if everything is working:
```bash
# Check backend detection
wall-it-backend-manager.py

# Start GUI
wallpaper-gui.py

# Try setting wallpaper
wall-it-next
```

## Troubleshooting

### GTK Errors
If you see GTK-related errors:
1. Verify GTK4 installation:
```bash
# Check if GTK4 is properly installed
pkg-config --modversion gtk4
```

2. Check Python GTK bindings:
```python
# Try in Python console
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
```

### Missing Dependencies
If you see ImportError or similar:
```bash
# Reinstall Python dependencies
pip install --user -r requirements.txt --force-reinstall

# For system packages, reinstall GTK dependencies
# Arch:
yay -S --needed gtk4 python-gobject python-cairo gdk-pixbuf2 libadwaita

# Ubuntu:
sudo apt install --reinstall python3-gi python3-cairo gir1.2-gtk-4.0

# Fedora:
sudo dnf reinstall gtk4 python3-gobject python3-cairo
```

### Path Issues
If commands aren't found:
```bash
# Add to PATH manually
export PATH="$HOME/.local/bin:$PATH"

# Check if scripts are in path
which wall-it-next
which wallpaper-gui.py
```

### Permission Issues
If scripts aren't executable:
```bash
# Make all scripts executable
chmod +x ~/.local/bin/wall-it-*

# Verify permissions
ls -l ~/.local/bin/wall-it-*
```