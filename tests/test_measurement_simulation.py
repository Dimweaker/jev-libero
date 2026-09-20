import numpy as np
import pytest

from jev_libero.config import load_task

pytestmark = pytest.mark.simulation


def test_selected_measurements_restore_after_previews(simulator):
    world = simulator(seed=1, task_config=load_task("alphabet_soup"))
    try:
        before = world.features()
        state = world.env.sim.get_state().flatten().copy()
        assert "target_bounds_mm" not in before
        assert "initial_bottom_mm" not in before
        assert before["target_lift_mm"] == 0
        world.predict_all()
        np.testing.assert_array_equal(state, world.env.sim.get_state().flatten())
        assert before == world.features()
        executed = world.execute("y-3mm", record=True)
        expected = set(world.config["record_features"]) | {"sim_time_s"}
        assert len(executed["feature_trace"]) == executed["steps"]
        assert all(set(row) == expected for row in executed["feature_trace"])
    finally:
        world.close()


def test_legacy_and_explicit_joint_measurements_match(simulator):
    explicit = load_task("top_drawer")
    legacy = load_task(explicit)
    del legacy["measurements"]
    a = simulator(seed=1, task_config=explicit)
    try:
        b = simulator(seed=1, task_config=legacy)
        try:
            assert a.features() == b.features()
        finally:
            b.close()
    finally:
        a.close()
