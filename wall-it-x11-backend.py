#!/usr/bin/env python3
"""
Wall-IT X11/Openbox Backend
Provides X11-specific wallpaper management for Openbox and other X11 window managers
(i3, bspwm, xmonad, Fluxbox, IceWM, XFCE, LXDE, etc.)

Wallpaper setters (in priority order):
  1. feh          -- most common, all-monitor only
  2. xwallpaper   -- per-output support via --output <name>
  3. nitrogen     -- GUI-friendly, all-monitor only

Per-monitor wallpapers are supported only when xwallpaper is installed.
Animated transitions are not available on X11.
"""

import os
import re
import subprocess
import sys
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional

# Import configuration
try:
    import wall_it_config as _config
except ImportError:
    _config_path = Path(__file__).parent / "wall-it-config.py"
    _spec = importlib.util.spec_from_file_location("wall_it_config", _config_path)
    _config = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_config)


class X11Backend:
    """Backend for X11 window managers (Openbox, i3, bspwm, xmonad, XFCE, etc.)"""

    # Wall-IT scaling mode → feh flag
    _FEH_SCALING: Dict[str, str] = {
        'crop':     '--bg-fill',    # fill frame, crop excess
        'fit':      '--bg-scale',   # scale to fit (may letterbox)
        'stretch':  '--bg-stretch', # stretch to exact dimensions
        'fit-blur': '--bg-fill',    # feh can't do fit-blur; treat as fill
    }

    # Wall-IT scaling mode → xwallpaper option name (used as --<mode>)
    _XWALLPAPER_SCALING: Dict[str, str] = {
        'crop':     'fill',
        'fit':      'zoom',
        'stretch':  'stretch',
        'fit-blur': 'fill',
    }

    # X11 window managers / desktop sessions we explicitly recognise
    _KNOWN_X11_SESSIONS = [
        'openbox', 'i3', 'bspwm', 'xmonad', 'awesome',
        'fluxbox', 'icewm', 'jwm', 'xfce', 'lxde', 'lxqt',
        'herbstluftwm', 'spectrwm', 'dwm', 'qtile',
    ]

    def __init__(self):
        self.name = "X11"
        self._feh_available = self._check_tool('feh')
        self._xwallpaper_available = self._check_tool('xwallpaper')
        self._nitrogen_available = self._check_tool('nitrogen')
        self._xrandr_available = self._check_tool('xrandr')
        self.verify_tools()

    # ------------------------------------------------------------------
    # Tool detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_tool(name: str) -> bool:
        """Return True if *name* exists on PATH."""
        try:
            subprocess.run(['which', name], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def verify_tools(self):
        """Warn early if no wallpaper setter is available."""
        if not (self._feh_available or self._xwallpaper_available or self._nitrogen_available):
            print(
                "Warning: No X11 wallpaper setter found. "
                "Install feh, xwallpaper, or nitrogen.",
                file=sys.stderr,
            )

    # ------------------------------------------------------------------
    # Availability check
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """
        Return True when:
          - DISPLAY is set (X11 session is active)
          - WAYLAND_DISPLAY is NOT set (pure X11, not XWayland)
          - at least one wallpaper setter is installed
          - Openbox (or another known X11 WM) is running, OR
            we are in a generic X11 session with no Wayland compositor
        """
        display = os.environ.get('DISPLAY', '')
        wayland = os.environ.get('WAYLAND_DISPLAY', '')

        if not display or wayland:
            return False

        if not (self._feh_available or self._xwallpaper_available or self._nitrogen_available):
            return False

        # Explicit Openbox process check
        if self._is_openbox_running():
            return True

        # Known X11 sessions via environment variables
        current_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        desktop_session = os.environ.get('DESKTOP_SESSION', '').lower()
        for wm in self._KNOWN_X11_SESSIONS:
            if wm in current_desktop or wm in desktop_session:
                return True

        # Generic X11 fallback: DISPLAY is set, no Wayland — we can still try
        return True

    def _is_openbox_running(self) -> bool:
        """Check whether an openbox process is currently running."""
        try:
            result = subprocess.run(['pgrep', '-x', 'openbox'], capture_output=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    # ------------------------------------------------------------------
    # Monitor enumeration
    # ------------------------------------------------------------------

    def get_monitors(self) -> List[Dict[str, str]]:
        """
        Return connected monitors via ``xrandr --listmonitors``.

        Example xrandr output::

            Monitors: 2
             0: +*eDP-1 1920/344x1080/194+0+0  eDP-1
             1: +DP-1 2560/553x1440/311+1920+0  DP-1
        """
        if not self._xrandr_available:
            return [self._fallback_monitor()]

        try:
            result = subprocess.run(
                ['xrandr', '--listmonitors'],
                capture_output=True, text=True, check=True,
            )
            monitors = []
            for line in result.stdout.strip().splitlines()[1:]:  # skip "Monitors: N" header
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 4:
                    continue

                idx = parts[0].rstrip(':')
                flags = parts[1]          # e.g. "+*" or "+"
                res_part = parts[2]       # e.g. "1920/344x1080/194+0+0"
                connector = parts[-1]     # e.g. "eDP-1"
                is_primary = '*' in flags

                resolution = 'Unknown'
                match = re.match(r'[+*]?(\d+)/\d+x(\d+)/\d+', res_part)
                if match:
                    resolution = f"{match.group(1)}x{match.group(2)}"

                monitors.append({
                    'id': idx,
                    'name': connector,
                    'connector': connector,
                    'resolution': resolution,
                    'primary': is_primary,
                })

            if monitors:
                return monitors

        except subprocess.CalledProcessError as e:
            print(f"Warning: xrandr --listmonitors failed: {e}", file=sys.stderr)

        return [self._fallback_monitor()]

    @staticmethod
    def _fallback_monitor() -> Dict[str, str]:
        return {'id': '0', 'name': 'default', 'connector': 'default',
                'resolution': 'Unknown', 'primary': True}

    def get_active_monitor(self) -> Optional[str]:
        """
        Return the primary monitor connector.
        X11 has no reliable 'focused output' API, so we return the primary display.
        """
        monitors = self.get_monitors()
        for m in monitors:
            if m.get('primary'):
                return m['connector']
        return monitors[0]['connector'] if monitors else None

    def get_monitor_by_connector(self, connector: str) -> Optional[Dict[str, str]]:
        """Look up a monitor dict by its connector name."""
        for m in self.get_monitors():
            if m['connector'] == connector:
                return m
        return None

    # ------------------------------------------------------------------
    # Wallpaper setting
    # ------------------------------------------------------------------

    def set_wallpaper(
        self,
        wallpaper_path: Path,
        monitor: Optional[str] = None,
        transition: str = 'fade',
        scaling: str = 'crop',
    ) -> bool:
        """
        Set wallpaper using the best available X11 setter.

        Priority:
          - If a specific *monitor* is requested and xwallpaper is available → xwallpaper
          - Otherwise feh → xwallpaper (all outputs) → nitrogen

        Transitions are silently ignored (not supported on X11).
        """
        matugen_success = self._generate_matugen_colors(wallpaper_path)

        success = False
        if monitor and self._xwallpaper_available:
            success = self._set_via_xwallpaper(wallpaper_path, monitor, scaling)
        elif self._feh_available:
            success = self._set_via_feh(wallpaper_path, scaling)
        elif self._xwallpaper_available:
            success = self._set_via_xwallpaper(wallpaper_path, None, scaling)
        elif self._nitrogen_available:
            success = self._set_via_nitrogen(wallpaper_path)
        else:
            print(
                "Error: No X11 wallpaper setter available. "
                "Install feh, xwallpaper, or nitrogen.",
                file=sys.stderr,
            )
            return False

        if success:
            self._save_current_wallpaper(wallpaper_path)
            if matugen_success:
                print("Wall-IT: Generated dynamic colors with matugen")

        return success

    def _set_via_feh(self, wallpaper_path: Path, scaling: str) -> bool:
        """Apply wallpaper to all monitors using feh."""
        flag = self._FEH_SCALING.get(scaling, '--bg-fill')
        try:
            subprocess.run(['feh', flag, str(wallpaper_path)],
                           check=True, capture_output=True)
            print(f"Wall-IT: Set wallpaper via feh ({flag})")
            return True
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
            print(f"Error setting wallpaper with feh: {err}", file=sys.stderr)
            return False
        except FileNotFoundError:
            print("Error: feh not found.", file=sys.stderr)
            return False

    def _set_via_xwallpaper(
        self,
        wallpaper_path: Path,
        monitor: Optional[str],
        scaling: str,
    ) -> bool:
        """Apply wallpaper using xwallpaper, optionally targeting a single output."""
        mode = self._XWALLPAPER_SCALING.get(scaling, 'fill')
        try:
            if monitor:
                cmd = ['xwallpaper', '--output', monitor,
                       f'--{mode}', str(wallpaper_path)]
                print(f"Wall-IT: Set wallpaper on {monitor} via xwallpaper (--{mode})")
            else:
                # Build a command that covers every connected output
                monitors = self.get_monitors()
                cmd = ['xwallpaper']
                for m in monitors:
                    cmd += ['--output', m['connector'],
                            f'--{mode}', str(wallpaper_path)]
                print(f"Wall-IT: Set wallpaper on all monitors via xwallpaper (--{mode})")

            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
            print(f"Error setting wallpaper with xwallpaper: {err}", file=sys.stderr)
            return False
        except FileNotFoundError:
            print("Error: xwallpaper not found.", file=sys.stderr)
            return False

    def _set_via_nitrogen(self, wallpaper_path: Path) -> bool:
        """Apply wallpaper using nitrogen (all monitors, zoom-fill mode)."""
        try:
            subprocess.run(['nitrogen', '--set-zoom-fill', str(wallpaper_path)],
                           check=True, capture_output=True)
            print("Wall-IT: Set wallpaper via nitrogen (--set-zoom-fill)")
            return True
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
            print(f"Error setting wallpaper with nitrogen: {err}", file=sys.stderr)
            return False
        except FileNotFoundError:
            print("Error: nitrogen not found.", file=sys.stderr)
            return False

    def _save_current_wallpaper(self, wallpaper_path: Path):
        """Persist the active wallpaper path to cache so get_current_wallpaper works."""
        try:
            cache_dir = Path.home() / ".cache" / "wall-it"
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / "current_wallpaper").write_text(str(wallpaper_path))
        except Exception as e:
            print(f"Warning: Could not save wallpaper state: {e}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Current wallpaper
    # ------------------------------------------------------------------

    def get_current_wallpaper(self, monitor: Optional[str] = None) -> Optional[Path]:
        """
        Return the last wallpaper set by Wall-IT, stored in the cache.
        (X11 setters like feh do not expose a live query interface.)
        """
        try:
            wallpaper_file = Path.home() / ".cache" / "wall-it" / "current_wallpaper"
            if wallpaper_file.exists():
                path = Path(wallpaper_file.read_text().strip())
                if path.exists():
                    return path
        except Exception as e:
            print(f"Error getting current wallpaper: {e}", file=sys.stderr)
        return None

    # ------------------------------------------------------------------
    # Capability flags
    # ------------------------------------------------------------------

    def supports_per_monitor_wallpapers(self) -> bool:
        """Per-monitor support requires xwallpaper."""
        return self._xwallpaper_available

    def supports_transitions(self) -> bool:
        """X11 wallpaper setters do not support animated transitions."""
        return False

    def get_supported_formats(self) -> List[str]:
        return ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp']

    # ------------------------------------------------------------------
    # Keybind suggestion
    # ------------------------------------------------------------------

    def suggest_openbox_keybind_setup(self):
        """Print ready-to-paste keybind XML for ~/.config/openbox/rc.xml."""
        print("\nOpenbox Keybind Setup:")
        print("Add these inside the <keyboard> section of ~/.config/openbox/rc.xml:\n")
        entries = [
            ("W-A-n", "wall-it-next",  "Next wallpaper"),
            ("W-A-p", "wall-it-prev",  "Previous wallpaper"),
            ("W-A-g", "wall-it-gui",   "Open Wall-IT GUI"),
        ]
        print("<!-- Wall-IT Keybinds -->")
        for key, cmd, _ in entries:
            print(f'<keybind key="{key}">')
            print(f'  <action name="Execute">')
            print(f'    <command>{cmd}</command>')
            print(f'  </action>')
            print(f'</keybind>')
        print("\nThen reload Openbox config:")
        print("  openbox --reconfigure")

    # ------------------------------------------------------------------
    # matugen helpers  (mirrors labwc backend exactly)
    # ------------------------------------------------------------------

    def _check_matugen_available(self) -> bool:
        try:
            subprocess.run(['matugen', '--version'],
                           capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _get_matugen_scheme(self) -> str:
        try:
            scheme_file = Path.home() / ".cache" / "wall-it" / "matugen_scheme"
            if scheme_file.exists():
                scheme = scheme_file.read_text().strip()
                if scheme in ['content', 'expressive', 'fidelity', 'fruit-salad',
                               'monochrome', 'neutral', 'rainbow', 'tonal-spot']:
                    scheme = f'scheme-{scheme}'
                return scheme
        except Exception:
            pass
        return 'scheme-expressive'

    def _is_matugen_enabled(self) -> bool:
        try:
            flag_file = Path.home() / ".cache" / "wall-it" / "matugen_enabled"
            if flag_file.exists():
                return flag_file.read_text().strip().lower() == 'true'
        except Exception:
            pass
        return True

    def _get_matugen_mode(self) -> str:
        try:
            theme_file = Path.home() / ".cache" / "wall-it" / "theme"
            if theme_file.exists() and theme_file.read_text().strip() == 'light':
                return 'light'
        except Exception:
            pass
        return 'dark'

    def _generate_matugen_colors(self, wallpaper_path: Path) -> bool:
        if not self._check_matugen_available() or not self._is_matugen_enabled():
            return False
        try:
            scheme = self._get_matugen_scheme()
            mode = self._get_matugen_mode()
            cmd = [
                'matugen', 'image', str(wallpaper_path),
                '--mode', mode,
                '--type', scheme,
                '--json', 'hex',
                '--prefer', 'saturation',
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15,
                check=True, stdin=subprocess.DEVNULL,
            )
            cache_dir = Path.home() / ".cache" / "wall-it"
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / "matugen_colors.json").write_text(result.stdout)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"Warning: matugen failed: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Warning: matugen error: {e}", file=sys.stderr)
            return False

    @staticmethod
    def _extract_hex(entry, mode: str, fallback: str = '#000000') -> str:
        """Handle both flat '#hex' strings and matugen 4.x nested dicts."""
        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            variant = entry.get(mode) or entry.get('default') or entry.get('dark') or {}
            if isinstance(variant, dict):
                return variant.get('color', fallback)
        return fallback

    def _get_colors_flat(self, colors_data: dict) -> Dict[str, str]:
        """Flatten matugen 4.x JSON colors into a simple {name: '#hex'} dict."""
        mode = self._get_matugen_mode()
        raw = colors_data.get('colors', {})
        return {name: self._extract_hex(entry, mode) for name, entry in raw.items()}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def test_x11_backend():
    backend = X11Backend()

    print("=" * 50)
    print("Wall-IT X11/Openbox Backend Test")
    print("=" * 50)

    print(f"X11 Backend Available:    {backend.is_available()}")
    print(f"Openbox Running:          {backend._is_openbox_running()}")
    print(f"DISPLAY:                  {os.environ.get('DISPLAY', '(not set)')}")
    print(f"WAYLAND_DISPLAY:          {os.environ.get('WAYLAND_DISPLAY', '(not set)')}")
    print()
    print(f"feh Available:            {backend._feh_available}")
    print(f"xwallpaper Available:     {backend._xwallpaper_available}")
    print(f"nitrogen Available:       {backend._nitrogen_available}")
    print(f"xrandr Available:         {backend._xrandr_available}")
    print()
    print(f"matugen Available:        {backend._check_matugen_available()}")
    print(f"matugen Enabled:          {backend._is_matugen_enabled()}")
    print(f"Supports Per-Monitor:     {backend.supports_per_monitor_wallpapers()}")
    print(f"Supports Transitions:     {backend.supports_transitions()}")

    monitors = backend.get_monitors()
    print(f"\nMonitors ({len(monitors)}):")
    for m in monitors:
        primary = " (Primary)" if m.get('primary') else ""
        print(f"  {m['connector']}: {m.get('resolution', 'Unknown')}{primary}")

    active = backend.get_active_monitor()
    print(f"\nActive Monitor: {active}")

    current = backend.get_current_wallpaper()
    print(f"Current Wallpaper: {current or 'None'}")

    backend.suggest_openbox_keybind_setup()
    print("\nX11/Openbox Backend Test Complete")


if __name__ == "__main__":
    test_x11_backend()
