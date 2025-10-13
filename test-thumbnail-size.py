#!/usr/bin/env python3
"""
Test script to verify HiDPI thumbnail sizing
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk

def test_scaling():
    """Test scaling detection"""
    print("=== Thumbnail Scaling Test ===")
    
    # Initialize GTK (required for getting display info)
    app = Gtk.Application()
    
    try:
        # Get display info
        display = Gdk.Display.get_default()
        if display:
            print(f"Display: {display}")
            
            # Get primary monitor
            monitor = display.get_primary_monitor()
            if monitor:
                scale_factor = monitor.get_scale_factor()
                geometry = monitor.get_geometry()
                print(f"Primary Monitor Scale Factor: {scale_factor}")
                print(f"Primary Monitor Geometry: {geometry.width}x{geometry.height}")
                
                # Calculate thumbnail size
                base_size = 180
                adjusted_size = int(base_size * max(1.0, scale_factor * 0.8))
                print(f"Base thumbnail size: {base_size}x{base_size}")
                print(f"Adjusted thumbnail size: {adjusted_size}x{adjusted_size}")
            
            # List all monitors
            n_monitors = display.get_n_monitors()
            print(f"\nTotal monitors: {n_monitors}")
            for i in range(n_monitors):
                monitor = display.get_monitor(i)
                scale = monitor.get_scale_factor()
                geom = monitor.get_geometry()
                print(f"  Monitor {i}: {geom.width}x{geom.height} @ {scale}x scale")
        else:
            print("❌ Could not get display information")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n=== Manual Calculation ===")
    # Based on your wlr-randr output
    print("Your monitors:")
    print("  HDMI-A-1: 3440x1440 @ 1.398x scale")
    print("  HDMI-A-2: 3840x2160 @ 1.0x scale")
    
    scale_factors = [1.398, 1.0]
    base_size = 180
    
    for i, scale in enumerate(scale_factors):
        adjusted_size = int(base_size * max(1.0, scale * 0.8))
        print(f"  Monitor {i+1} thumbnail size: {adjusted_size}x{adjusted_size}")

if __name__ == "__main__":
    test_scaling()
