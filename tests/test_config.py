import copy
import json
import subprocess
import sys

import pytest

from jev_libero.actions import ACTIONS
from jev_libero.config import expression, load_task, project


def test_action_vocabulary():
    assert len(ACTIONS) == 27
    assert sum("axis" in spec for spec in ACTIONS.values()) == 18
    assert sum("rot_axis" in spec for spec in ACTIONS.values()) == 6
    assert {"open", "close", "hold"} <= ACTIONS.keys()


@pytest.mark.parametrize("name", ["microwave", "top_drawer"])
def test_bundled_configs(name):
    cfg = load_task(name)
    assert cfg["binding"]["success"] == "libero"
    assert cfg["display"]["progress_field"] in cfg["predictions"]
    assert cfg["display"]["field"] in cfg["features"]
    assert set(cfg["contracts"]) == set(cfg["policy"]["intent_descriptions"])


def test_safe_expressions():
    assert expression({"norm": {"sub": [[1, 2, 3], [1, 2, 5]]}}, {}) == 2
    assert project({"yes": {"all": [True, {"ge": [3, 2]}]}}, {}) == {"yes": True}
    cfg = copy.deepcopy(load_task())
    cfg["contracts"]["advance_target"] = {"python": "arbitrary code"}
    with pytest.raises(ValueError, match="Unsupported expression"):
        load_task(cfg)


def test_custom_config_path(tmp_path):
    cfg = load_task("top_drawer")
    path = tmp_path / "custom.json"
    path.write_text(json.dumps(cfg))
    assert load_task(path) == cfg


def test_core_imports_do_not_load_robot_stack():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from jev_libero.cli import main; main(['tasks']); assert 'mujoco' not in sys.modules; assert 'libero' not in sys.modules",
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "top_drawer" in result.stdout
