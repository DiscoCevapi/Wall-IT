#!/usr/bin/env python3
"""
Wall-IT Image Processor
Advanced image processing for wallpapers including fit-blur for ultrawide monitors
"""

import sys
from pathlib import Path
from typing import Tuple, Optional

try:
    from PIL import Image, ImageFilter, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Error: PIL/Pillow not available. Install with: sudo pacman -S python-pillow", file=sys.stderr)
    sys.exit(1)


def get_screen_resolution() -> Optional[Tuple[int, int]]:
    """Get screen resolution from niri or other compositor."""
    import subprocess
    
    try:
        # Try niri first
        result = subprocess.run(['niri', 'msg', 'outputs'], 
                              capture_output=True, text=True, check=True)
        for line in result.stdout.split('\n'):
            if 'Current mode:' in line:
                # Parse: "Current mode: 3440x1440 @ 155.000 Hz"
                import re
                match = re.search(r'(\d+)x(\d+)', line)
                if match:
                    return (int(match.group(1)), int(match.group(2)))
    except:
        pass
    
    # Fallback: try to detect from environment or return common ultrawide
    return (3440, 1440)  # Default to 21:9 ultrawide


def create_fit_blur_wallpaper(input_path: Path, output_path: Path, 
                               target_resolution: Optional[Tuple[int, int]] = None,
                               blur_radius: int = 40,
                               blur_scale: float = 1.5) -> Path:
    """
    Create a fit-blur wallpaper for ultrawide monitors.
    
    The image is fitted to height, then the sides are filled with a zoomed,
    heavily blurred version of the image edges to avoid black bars.
    
    Args:
        input_path: Source image path
        output_path: Destination path
        target_resolution: Target screen resolution (width, height)
        blur_radius: Gaussian blur radius for the background
        blur_scale: How much to zoom the blurred background (1.5 = 150%)
    
    Returns:
        Path to the processed image
    """
    if not target_resolution:
        target_resolution = get_screen_resolution()
    
    target_width, target_height = target_resolution
    
    # Open the original image
    img = Image.open(input_path)
    original_width, original_height = img.size
    
    # Calculate aspect ratios
    target_aspect = target_width / target_height
    image_aspect = original_width / original_height
    
    # Create output canvas
    output = Image.new('RGB', (target_width, target_height), (0, 0, 0))
    
    # Step 1: Create blurred background
    # Scale image to fill screen (with some zoom for blur background)
    bg_scale = max(target_width / original_width, target_height / original_height) * blur_scale
    bg_width = int(original_width * bg_scale)
    bg_height = int(original_height * bg_scale)
    background = img.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
    
    # Center crop for background
    left = (bg_width - target_width) // 2
    top = (bg_height - target_height) // 2
    background = background.crop((left, top, left + target_width, top + target_height))
    
    # Apply heavy blur
    background = background.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    
    # Darken the background slightly for better contrast
    from PIL import ImageEnhance
    enhancer = ImageEnhance.Brightness(background)
    background = enhancer.enhance(0.7)  # 70% brightness
    
    # Paste blurred background
    output.paste(background, (0, 0))
    
    # Step 2: Fit the original image (preserve aspect ratio)
    if image_aspect > target_aspect:
        # Image is wider - fit to width
        fit_width = target_width
        fit_height = int(target_width / image_aspect)
    else:
        # Image is taller - fit to height
        fit_height = target_height
        fit_width = int(target_height * image_aspect)
    
    # Resize image with high quality
    fitted = img.resize((fit_width, fit_height), Image.Resampling.LANCZOS)
    
    # Center the fitted image on the canvas
    x_offset = (target_width - fit_width) // 2
    y_offset = (target_height - fit_height) // 2
    
    # Paste fitted image on top
    output.paste(fitted, (x_offset, y_offset))
    
    # Save with high quality
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path, 'JPEG', quality=95)
    
    return output_path


def process_wallpaper_with_mode(input_path: Path, output_dir: Path, 
                                 mode: str = 'fit-blur') -> Path:
    """
    Process wallpaper based on scaling mode.
    
    Args:
        input_path: Source image
        output_dir: Directory for processed images
        mode: Scaling mode ('fit-blur', 'crop', 'fit', 'stretch')
    
    Returns:
        Path to processed image
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate output filename
    input_hash = str(hash(input_path))[-8:]
    output_filename = f"{input_path.stem}_{mode}_{input_hash}.jpg"
    output_path = output_dir / output_filename
    
    # Check cache
    if output_path.exists() and output_path.stat().st_mtime >= input_path.stat().st_mtime:
        return output_path
    
    if mode == 'fit-blur':
        return create_fit_blur_wallpaper(input_path, output_path)
    elif mode in ['crop', 'fit', 'stretch']:
        # For other modes, just return original (handled by swww)
        return input_path
    else:
        print(f"Unknown mode: {mode}, using original image", file=sys.stderr)
        return input_path


if __name__ == "__main__":
    # CLI interface
    import argparse
    
    parser = argparse.ArgumentParser(description='Process wallpaper for ultrawide monitors')
    parser.add_argument('input', type=Path, help='Input image path')
    parser.add_argument('-o', '--output', type=Path, help='Output image path')
    parser.add_argument('-m', '--mode', default='fit-blur', 
                       choices=['fit-blur', 'crop', 'fit', 'stretch'],
                       help='Scaling mode')
    parser.add_argument('-r', '--resolution', type=str,
                       help='Target resolution (e.g., 3440x1440)')
    parser.add_argument('--blur-radius', type=int, default=40,
                       help='Blur radius for background (default: 40)')
    parser.add_argument('--blur-scale', type=float, default=1.5,
                       help='Background zoom factor (default: 1.5)')
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    # Parse resolution if provided
    resolution = None
    if args.resolution:
        try:
            w, h = args.resolution.split('x')
            resolution = (int(w), int(h))
        except:
            print(f"Error: Invalid resolution format. Use WIDTHxHEIGHT (e.g., 3440x1440)", 
                  file=sys.stderr)
            sys.exit(1)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_dir = Path.home() / '.cache' / 'wall-it' / 'processed'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{args.input.stem}_processed.jpg"
    
    # Process image
    if args.mode == 'fit-blur':
        result = create_fit_blur_wallpaper(
            args.input, output_path, 
            target_resolution=resolution,
            blur_radius=args.blur_radius,
            blur_scale=args.blur_scale
        )
        print(f"✅ Created fit-blur wallpaper: {result}")
    else:
        print(f"Mode '{args.mode}' doesn't require processing")
        result = args.input
    
    print(f"Output: {result}")
