import importlib.util
from pathlib import Path


def load_common_module(tmp_path, monkeypatch):
    """Load wall-it-common.py with isolated test paths via env overrides."""
    monkeypatch.setenv("WALLIT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WALLIT_WALLPAPER_DIR", str(tmp_path / "wallpapers"))
    monkeypatch.setenv("WALLIT_CURRENT_WALLPAPER", str(tmp_path / ".current-wallpaper"))

    module_path = Path(__file__).resolve().parents[1] / "wall-it-common.py"
    spec = importlib.util.spec_from_file_location("wall_it_common_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rewire_config_paths(common, tmp_path):
    """Point config/cache files to temporary test paths."""
    cache_dir = tmp_path / "cache"
    wallpaper_dir = tmp_path / "wallpapers"
    temp_dir = cache_dir / "temp"

    common.config.CACHE_DIR = cache_dir
    common.config.WALLPAPER_DIR = wallpaper_dir
    common.config.TEMP_DIR = temp_dir
    common.config.TRANSITION_FILE = cache_dir / "transition_effect"
    common.config.EFFECT_FILE = cache_dir / "current_effect"
    common.config.SCALING_FILE = cache_dir / "wallpaper_scaling"
    common.config.KEYBIND_MODE_FILE = cache_dir / "keybind_mode"
    common.config.MATUGEN_ENABLED_FILE = cache_dir / "matugen_enabled"
    common.config.MATUGEN_SCHEME_FILE = cache_dir / "matugen_scheme"

    common.DEFAULT_CACHE_VALUES = {
        common.config.TRANSITION_FILE: common.config.DEFAULT_TRANSITION,
        common.config.EFFECT_FILE: common.config.DEFAULT_EFFECT,
        common.config.SCALING_FILE: common.config.DEFAULT_SCALING,
        common.config.KEYBIND_MODE_FILE: common.config.DEFAULT_KEYBIND_MODE,
        common.config.MATUGEN_ENABLED_FILE: str(common.config.DEFAULT_MATUGEN_ENABLED).lower(),
        common.config.MATUGEN_SCHEME_FILE: common.config.DEFAULT_MATUGEN_SCHEME,
    }
    common.FIRST_RUN_MARKER = cache_dir / ".first_run_complete"

    return cache_dir, wallpaper_dir, temp_dir


def test_initialize_first_run_creates_defaults(tmp_path, monkeypatch):
    common = load_common_module(tmp_path, monkeypatch)
    cache_dir, wallpaper_dir, temp_dir = rewire_config_paths(common, tmp_path)

    common.initialize_first_run_state(caller="pytest")

    assert cache_dir.exists()
    assert wallpaper_dir.exists()
    assert temp_dir.exists()
    assert common.FIRST_RUN_MARKER.exists()

    for file_path, expected in common.DEFAULT_CACHE_VALUES.items():
        assert file_path.exists()
        assert file_path.read_text().strip() == expected


def test_validate_runtime_fails_when_awww_missing(tmp_path, monkeypatch):
    common = load_common_module(tmp_path, monkeypatch)
    rewire_config_paths(common, tmp_path)

    monkeypatch.setattr(common, "_is_command_available", lambda _cmd: False)

    ok, backend = common.validate_runtime(
        caller="pytest",
        require_awww=True,
    )

    assert ok is False
    assert backend is None


def test_validate_runtime_fails_when_backend_unavailable(tmp_path, monkeypatch):
    common = load_common_module(tmp_path, monkeypatch)
    rewire_config_paths(common, tmp_path)

    class BackendUnavailable:
        def is_available(self):
            return False

    monkeypatch.setattr(common, "get_backend_manager", lambda: BackendUnavailable())
    monkeypatch.setattr(common, "_is_command_available", lambda _cmd: True)
    monkeypatch.setattr(common, "is_matugen_enabled", lambda: False)

    ok, backend = common.validate_runtime(
        caller="pytest",
        require_backend=True,
    )

    assert ok is False
    assert backend is None


def test_validate_runtime_success_with_backend_and_wallpapers(tmp_path, monkeypatch):
    common = load_common_module(tmp_path, monkeypatch)
    rewire_config_paths(common, tmp_path)

    class BackendAvailable:
        def is_available(self):
            return True

    backend = BackendAvailable()
    monkeypatch.setattr(common, "get_backend_manager", lambda: backend)
    monkeypatch.setattr(common, "get_wallpaper_list", lambda: [tmp_path / "wallpapers" / "one.jpg"])
    monkeypatch.setattr(common, "_is_command_available", lambda _cmd: True)
    monkeypatch.setattr(common, "is_matugen_enabled", lambda: False)

    ok, resolved_backend = common.validate_runtime(
        caller="pytest",
        require_backend=True,
        require_wallpapers=True,
    )

    assert ok is True
    assert resolved_backend is backend
