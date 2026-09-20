from types import SimpleNamespace

import numpy as np
import pytest

from jev_libero.config import expression, load_task
from jev_libero.measurements import Measurements, validate_measurements


def fake_world(specs):
    return SimpleNamespace(config={"binding": {}, "measurements": specs})


def test_empty_selection_does_not_touch_simulator():
    assert Measurements(fake_world({})).read() == {}


def test_initial_reference_is_fixed_and_dependencies_are_cached():
    w = fake_world(
        {
            "delta": {
                "kind": "expression",
                "value": {"sub": [{"ref": "raw.now"}, {"ref": "raw.start"}]},
            },
            "start": {"kind": "initial", "source": "now"},
            "now": {"kind": "joint_position"},
        }
    )
    w.qindex = 0
    w.data = SimpleNamespace(qpos=np.array([2.0]))
    m = Measurements(w)
    w.data.qpos[0] = 5
    assert m.read() == {"delta": 3, "start": 2, "now": 5}
    w.data.qpos[0] = 2
    assert m.read()["delta"] == 0
    assert set(m.cache) == set(w.config["measurements"])


@pytest.mark.parametrize(
    "specs",
    [
        {"a": {"kind": "unknown"}},
        {"a": {"kind": "initial", "source": "missing"}},
        {"a": {"kind": "initial", "source": "b"}, "b": {"kind": "initial", "source": "a"}},
        {"a": {"kind": "expression", "value": {"ref": "before.x"}}},
        {"a": {"kind": "bounds_mm", "entity": {"group": "unknown"}}},
        {"a": {"kind": "center_mm", "entity": {"object": "x"}, "typo": True}},
    ],
)
def test_invalid_declarations(specs):
    with pytest.raises(ValueError):
        validate_measurements(specs)


def test_all_tasks_share_measurement_interface():
    for task in ("microwave", "top_drawer", "alphabet_soup"):
        c = load_task(task)
        assert "measurements" in c
        assert "grasp_measurements" not in c["binding"]
    assert expression({"count": [1, 2]}, {}) == 2


def test_geometry_is_selected_and_cached_without_contact_queries():
    selector = {"group": "target"}
    w = fake_world(
        {
            "center": {"kind": "center_mm", "entity": selector},
            "bounds": {"kind": "bounds_mm", "entity": selector},
        }
    )
    calls = []
    w.scene = SimpleNamespace(
        moving={0},
        padgroups={},
        local_vertices=lambda g: calls.append(g) or np.array([[0, 0, 0], [1, 2, 3]]),
    )
    w.gripper_geoms = []
    w.data = SimpleNamespace(geom_xmat=np.array([np.eye(3).flatten()]), geom_xpos=np.zeros((1, 3)))
    m = Measurements(w)
    assert not calls  # No initial-reference measurements: no eager geometry work.
    assert m.read() == {"center": [500, 1000, 1500], "bounds": [[0, 0, 0], [1000, 2000, 3000]]}
    assert calls == [0]
    w.data.geom_xpos[0, 0] = 1
    assert m.read()["center"][0] == 1500
    assert calls == [0]


def test_contact_count_does_not_require_names_or_geometry_vertices():
    w = fake_world(
        {
            "count": {
                "kind": "external_contact_count",
                "entity": {"group": "target"},
                "exclude": [{"group": "gripper"}],
                "min_normal_force_N": 0.05,
            }
        }
    )
    w.config["contact"] = {"min_normal_force_N": 1}
    w.scene = SimpleNamespace(moving={0}, padgroups={})
    w.gripper_geoms = [1]
    w.data = SimpleNamespace(ncon=3, contact=[SimpleNamespace(geom1=0, geom2=g) for g in (1, 2, 3)])
    w.model = None

    def force(model, data, i, out):
        out[0] = [2, 0.1, 0.01][i]

    w.mujoco = SimpleNamespace(mj_contactForce=force)
    assert Measurements(w).read() == {"count": 1}
