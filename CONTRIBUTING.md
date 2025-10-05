# Contributing to Wall-IT

Thank you for your interest in contributing to Wall-IT! We welcome contributions from everyone.

## Getting Started

1. Fork the repository
2. Create a new branch for your feature/fix
3. Make your changes
4. Submit a pull request

## Development Setup

1. Clone your fork:
```bash
git clone https://github.com/YOUR-USERNAME/Wall-IT.git
cd Wall-IT
```

2. Install development dependencies:
```bash
# Install system dependencies (Arch/CachyOS example)
yay -S gtk4 python-gobject python-cairo gdk-pixbuf2 libadwaita python-pathlib

# Install Python dependencies
pip install --user -r requirements.txt
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Document new functions and classes
- Keep code modular and maintainable

## Testing

Before submitting a PR:
1. Test your changes with different desktop environments
2. Ensure all scripts run without errors
3. Check for any GTK warnings or errors
4. Test with different monitor configurations

## Pull Request Process

1. Update documentation if needed
2. Add yourself to CONTRIBUTORS.md if you're not already there
3. Describe your changes in the PR description
4. Link any related issues

## Questions?

Feel free to open an issue for any questions about contributing.