"""Non-interactive LIBERO setup, isolated from the user's ~/.libero settings."""

import importlib
import json
import os
import sys
from pathlib import Path


def prepare_libero(root=None, config_dir=None):
    root = root or os.environ.get("LIBERO_ROOT")
    if not root:
        raise ValueError("Set LIBERO_ROOT to a LIBERO checkout, or pass --libero-root.")
    root = Path(root).expanduser().resolve()
    assets = root / "libero" / "libero"
    for name in ("bddl_files", "init_files", "assets"):
        if not (assets / name).is_dir():
            raise ValueError(f"Not a complete LIBERO checkout: missing {assets / name}")
    config_dir = (
        Path(
            config_dir
            or os.environ.get("JEV_LIBERO_CONFIG_DIR")
            or Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "jev-libero"
            / "libero"
        )
        .expanduser()
        .resolve()
    )
    config = {
        "benchmark_root": str(assets),
        "bddl_files": str(assets / "bddl_files"),
        "init_states": str(assets / "init_files"),
        "datasets": str(root / "libero" / "datasets"),
        "assets": str(assets / "assets"),
    }
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "config.yaml"
    if path.exists():
        # YAML also accepts JSON; use PyYAML only in the simulation extra.
        import yaml

        if yaml.safe_load(path.read_text()) != config:
            raise ValueError(
                f"{path} belongs to a different configuration. Use another --libero-config-dir; it will not be overwritten."
            )
    else:
        path.write_text(json.dumps(config, indent=2) + "\n")
    loaded = sys.modules.get("libero.libero")
    if loaded and Path(loaded.config_file).resolve() != path:
        raise RuntimeError(
            "LIBERO was already imported with another config directory. Start a new process."
        )
    os.environ["LIBERO_CONFIG_PATH"] = str(config_dir)
    os.environ.setdefault("MUJOCO_GL", "egl")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root, assets, config_dir


def load_libero(root=None, config_dir=None):
    root, assets, config_dir = prepare_libero(root, config_dir)
    benchmark = importlib.import_module("libero.libero.benchmark")
    wrapper = importlib.import_module("libero.libero.envs.env_wrapper")
    return benchmark, wrapper.ControlEnv, assets, config_dir
