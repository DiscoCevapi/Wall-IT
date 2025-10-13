#!/usr/bin/env python3
"""
Test script to verify monitor mapping in Wall-IT
"""

import sys
from pathlib import Path

# Add the Wall-IT directory to the path
wall_it_dir = Path(__file__).parent
sys.path.insert(0, str(wall_it_dir))

def test_monitor_mapping():
    """Test the monitor mapping logic"""
    print("🖥️  Testing Wall-IT Monitor Mapping")
    print("=" * 50)
    
    # Import and test backend manager
    try:
        from pathlib import Path
        backend_manager_path = wall_it_dir / "wall-it-backend-manager.py"
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("backend_manager", backend_manager_path)
        backend_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend_module)
        
        # Create backend manager instance
        backend_manager = backend_module.BackendManager()
        
        print(f"Backend Available: {backend_manager.is_available()}")
        print(f"Backend Name: {backend_manager.get_backend_name()}")
        print()
        
        # Test monitor detection
        monitors = backend_manager.get_monitors()
        print(f"Detected Monitors ({len(monitors)}):")
        for i, monitor in enumerate(monitors):
            connector = monitor.get('connector', monitor.get('name', 'Unknown'))
            print(f"  [{i}] {connector} - {monitor}")
        print()
        
        # Test monitor list creation (simulate what the GUI does)
        available_monitors = [m.get('connector', m.get('name', '')) for m in monitors if m.get('connector') or m.get('name')]
        
        print("Monitor Dropdown Mapping:")
        print("  [0] All Monitors")
        for i, monitor in enumerate(available_monitors):
            print(f"  [{i + 1}] {monitor}")
        print()
        
        print("Selection Test:")
        for selection_index in range(len(available_monitors) + 1):
            if selection_index == 0:
                print(f"  Selection {selection_index} -> All Monitors")
            else:
                monitor_index = selection_index - 1
                if monitor_index < len(available_monitors):
                    monitor = available_monitors[monitor_index]
                    print(f"  Selection {selection_index} -> Monitor: {monitor}")
                else:
                    print(f"  Selection {selection_index} -> ERROR: Index out of range")
        
        print()
        print("✅ Monitor mapping test complete!")
        
        # Test active monitor detection
        active_monitor = backend_manager.get_active_monitor()
        print(f"🎯 Currently Active Monitor: {active_monitor}")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_monitor_mapping()
