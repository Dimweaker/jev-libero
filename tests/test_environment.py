import json
import os

import pytest

from jev_libero.environment import prepare_libero


def test_isolated_noninteractive_configuration(tmp_path, monkeypatch):
    root = tmp_path / "LIBERO"
    for name in ("assets", "bddl_files", "init_files"):
        (root / "libero" / "libero" / name).mkdir(parents=True)
    config_dir = tmp_path / "isolated"
    monkeypatch.setenv("LIBERO_CONFIG_PATH", str(tmp_path / "unrelated-user-config"))
    result = prepare_libero(root, config_dir)
    assert result[0] == root
    cfg = json.loads((config_dir / "config.yaml").read_text())
    assert cfg["assets"] == str(root / "libero" / "libero" / "assets")
    assert not (tmp_path / "unrelated-user-config").exists()
    assert os.environ["LIBERO_CONFIG_PATH"] == str(config_dir)
    assert prepare_libero(root, config_dir) == result
    (config_dir / "config.yaml").write_text("{}")
    with pytest.raises(ValueError, match="will not be overwritten"):
        prepare_libero(root, config_dir)


def test_missing_checkout_is_actionable(tmp_path):
    with pytest.raises(ValueError, match="complete LIBERO checkout"):
        prepare_libero(tmp_path, tmp_path / "config")
