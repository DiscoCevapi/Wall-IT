#!/usr/bin/env python3
"""
Simple test for pynput global hotkeys
"""

try:
    from pynput import keyboard
    print("pynput imported successfully")
    
    def on_activate():
        print("Hotkey activated! Alt+Super+t pressed")
    
    def test_simple_hotkey():
        print("Testing simple hotkey: Alt+Super+t")
        print("Press Alt+Super+t to test, or Ctrl+C to exit")
        
        hotkey = keyboard.GlobalHotKeys({
            '<alt>+<cmd>+t': on_activate
        })
        
        with hotkey:
            try:
                hotkey.join()
            except KeyboardInterrupt:
                print("\nTest ended")
    
    if __name__ == "__main__":
        test_simple_hotkey()
        
except ImportError as e:
    print(f"pynput import failed: {e}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
