"""Optional, entirely offline simulation tests. Never calls OpenRouter."""

import json

import numpy as np
import pytest

from jev_libero.policy import contracts
from jev_libero.records import read_jsonl

pytestmark = pytest.mark.simulation


@pytest.mark.parametrize(
    "name", ["microwave_seed1", "microwave_seed2", "microwave_seed3", "top_drawer_seed1"]
)
def test_published_controls_replay(simulator, records_root, name):
    from jev_libero.records import replay

    result = replay(records_root / name)
    assert result["max_state_error"] == 0 and result["api_calls"] == 0


@pytest.mark.parametrize("seed,action", [(1, "y-10mm"), (2, "x+10mm"), (3, "y+40mm")])
def test_false_zero_distance_regression(simulator, seed, action):
    world = simulator(seed=seed)
    try:
        state = world.env.sim.get_state().flatten().copy()
        before, pred = world.predict_all()
        np.testing.assert_array_equal(state, world.env.sim.get_state().flatten())
        eligible, _ = contracts(before, pred, True, world.config)
        assert action not in eligible.get("approach_target", {})
        assert "z-40mm" in eligible["approach_target"]
        world.execute(action)
        assert world.features()["distance_to_moving_geometry_mm"] > 60
        np.testing.assert_array_equal(
            world.env.sim.get_state().flatten(), pred[action]["sim_state_after"]
        )
    finally:
        world.close()


def test_two_step_witness_and_restore(simulator, records_root):
    from jev_libero.world import Snapshot

    folder = records_root / "microwave_seed3"
    predictions = read_jsonl(folder / "predictions.jsonl")
    row = next(p for p in predictions if p["two_step_evaluations"] > 0)
    trace = read_jsonl(folder / "trace.jsonl")
    boundary = sum(
        predictions[i]["predictions"][t["choice"]]["steps"]
        for i, t in enumerate(trace[: row["step"]])
    )
    trajectory = np.load(folder / "sim_trajectory.npz")
    world = simulator(seed=3)
    try:
        for action in trajectory["actions"][:boundary]:
            world.obs, _, _, _ = world.env.step(action)
        state = world.env.sim.get_state().flatten().copy()
        grip = float(trajectory["actions"][boundary - 1, -1])
        witnesses, count = world.two_step_witnesses(grip)
        np.testing.assert_array_equal(state, world.env.sim.get_state().flatten())
        assert count > 0 and witnesses
        snap = Snapshot(world)
        before = world.features()
        for first, proof in witnesses.items():
            snap.restore()
            one = world.execute(first, grip)
            two = world.execute(proof["second_input"], one["grip"])
            from jev_libero.config import project

            progress = project(
                world.config["predictions"], {"before": before, "after": two["features"]}
            )
            assert progress[world.config["search"]["progress_field"]] == pytest.approx(
                proof["net_progress"]
            )
        snap.restore()
    finally:
        world.close()


def test_runner_without_video_or_network(simulator, records_root, tmp_path, monkeypatch):
    """Execute the new runner with recorded answers, not a paid model call."""
    import jev_libero.runner as runner

    folder = records_root / "top_drawer_seed1"
    calls = read_jsonl(folder / "api.jsonl")

    class OfflineAPI:
        def __init__(self, *args, **kwargs):
            self.total = 0.0
            self.calls = 0

        def choose(self, step, layer, state, instructions, criteria):
            c = calls[self.calls]
            self.calls += 1
            assert (step, layer) == (c["step"], c["layer"])
            assert state == c["request"]["state"]
            assert criteria == c["request"]["questions"][layer]["criteria"]
            assert instructions == c["request"]["questions"][layer]["instructions"]
            self.total += c["response"]["usage"]["cost"]
            return c["response"]["answers"][layer]["choice"]

        def close(self):
            pass

    monkeypatch.setattr(runner, "Decisions", OfflineAPI)
    out = tmp_path / "run"
    result = runner.run("top_drawer", out, seed=1, render=False)
    assert result["success"] and result["decisions"] == 20 and result["sim_steps"] == 155
    assert (out / "sim_trajectory.npz").exists() and not (out / "trajectory.gif").exists()
    np.testing.assert_array_equal(
        np.load(out / "sim_trajectory.npz")["actions"],
        np.load(folder / "sim_trajectory.npz")["actions"],
    )
    assert json.loads((out / "summary.json").read_text())["termination"] == "success"
