"""Read plain or compressed run records, and replay without calling Jev."""

import gzip
import json
from pathlib import Path

import numpy as np

from .config import load_task


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        path = path.with_suffix(path.suffix + ".gz")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def inspect(folder):
    return json.loads((Path(folder) / "summary.json").read_text())


def replay(folder, libero_root=None, config_dir=None):
    from .world import World

    folder = Path(folder)
    config = json.loads((folder / "config.json").read_text())
    expected_summary = inspect(folder)
    trajectory = np.load(folder / "sim_trajectory.npz")
    world = World(
        seed=config["seed"],
        init_index=config["initial_state"],
        task_config=load_task(folder / "task_config.json"),
        libero_root=libero_root,
        config_dir=config_dir,
    )
    error = 0.0
    try:
        if not len(trajectory["actions"]):
            raise ValueError("This record contains no executed controls to replay.")
        np.testing.assert_allclose(
            world.env.sim.get_state().flatten(), trajectory["states_before"][0], atol=1e-8, rtol=0
        )
        for i, action in enumerate(trajectory["actions"]):
            world.obs, _, _, _ = world.env.step(action)
            # Exercise the geometry path during the replay too.
            if world.features()["distance_to_moving_geometry_mm"] < 0:
                raise RuntimeError("Negative approach gap")
            expected = (
                trajectory["states_before"][i + 1]
                if i + 1 < len(trajectory["actions"])
                else trajectory["final_state"]
            )
            error = max(
                error, float(np.max(np.abs(world.env.sim.get_state().flatten() - expected)))
            )
        success = bool(world.env.check_success())
        if error > 1e-8 or success != expected_summary["success"]:
            raise RuntimeError(f"Replay mismatch: max_state_error={error}, success={success}")
        return {
            "steps": len(trajectory["actions"]),
            "max_state_error": error,
            "success": success,
            "api_calls": 0,
        }
    finally:
        world.close()
