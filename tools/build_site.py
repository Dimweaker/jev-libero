"""Build the static trajectory explorer from published records; no API or simulator.

Usage: python tools/build_site.py --out _site
"""

import argparse
import gzip
import json
import math
import shutil
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EPISODES = (
    ("microwave", "microwave_seed1", "Close the microwave", "qpos_rad", -180 / math.pi),
    ("top-drawer", "top_drawer_seed1", "Close the top drawer", "qpos_m", -1000),
)


def read_lines(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def episode(slug, record, title, joint_field, scale):
    folder = ROOT / "examples" / "records" / record
    traces = read_lines(folder / "trace.jsonl.gz")
    predictions = read_lines(folder / "predictions.jsonl.gz")
    calls = read_lines(folder / "api.jsonl.gz")
    summary = json.loads((folder / "summary.json").read_text())
    final = json.loads((folder / "final_state.json").read_text())
    config = json.loads((folder / "config.json").read_text())
    with np.load(folder / "sim_trajectory.npz") as trajectory:
        states = np.vstack((trajectory["states_before"], trajectory["final_state"]))
        assert len(trajectory["actions"]) == summary["sim_steps"]
    assert len(traces) == len(predictions) == summary["decisions"]
    assert len(calls) == summary["api_calls"]
    # Identify the joint column by matching every recorded boundary, not a guessed
    # flat-state offset. Static scene parameters are not needed for this export.
    boundaries, frame = [], 0
    for trace, pred in zip(traces, predictions):
        boundaries.append((frame, pred["before"][joint_field]))
        frame += pred["predictions"][trace["choice"]]["steps"]
    boundaries.append((frame, final[joint_field]))
    columns = [
        col
        for col in range(states.shape[1])
        if all(abs(states[index, col] - value) < 1e-10 for index, value in boundaries)
    ]
    assert len(columns) == 1, f"Joint column is ambiguous: {columns}"
    assert frame == summary["sim_steps"]
    assert np.allclose(np.diff(states[:, 0]), 0.05, atol=1e-10, rtol=0)
    samples = (states[:, columns[0]] * scale).tolist()
    steps, active = [], {}
    for index, (trace, pred) in enumerate(zip(traces, predictions)):
        fresh = []
        for call_index, call in enumerate(calls):
            if call["step"] == index:
                layer = call["layer"]
                active[layer] = call_index
                fresh.append(layer)
                question = call["request"]["questions"][layer]
                answer = call["response"]["answers"][layer]
                assert answer["choice"] in question["criteria"]
                assert set(answer["probabilities"]) == set(question["criteria"])
        assert set(active) == {"intent", "strategy", "motor"}
        for layer, trace_key in (
            ("intent", "intent"),
            ("strategy", "strategy"),
            ("motor", "choice"),
        ):
            assert calls[active[layer]]["response"]["answers"][layer]["choice"] == trace[trace_key]
        after = predictions[index + 1]["before"] if index + 1 < len(predictions) else final
        start, end = boundaries[index][0], boundaries[index + 1][0]
        assert abs(samples[start] - trace["before_task_value"]) < 1e-8
        assert abs(samples[end] - trace["after_task_value"]) < 1e-8
        effects = {}
        for name, candidate in pred["predictions"].items():
            value = candidate["after"]
            effects[name] = {
                "gap": value["distance_to_moving_geometry_mm"],
                "progress": candidate.get("closing_degrees", candidate.get("closing_mm")),
                "contact": value["moving_contact"],
                "eef": value["eef_mm"],
            }
            assert effects[name]["progress"] is not None
        steps.append(
            {
                "index": index,
                "start": start / 20,
                "end": end / 20,
                "startFrame": start,
                "endFrame": end,
                "choice": trace["choice"],
                "intent": trace["intent"],
                "strategy": trace["strategy"],
                "layers": dict(active),
                "fresh": fresh,
                "eligible": trace["eligible_motor"],
                "feasible": list(
                    {a: None for pool in trace["eligible_by_intent"].values() for a in pool}
                ),
                "before": pred["before"],
                "after": after,
                "effects": effects,
                "cost": trace["cost_usd"],
                "apiCalls": trace["api_calls"],
                "actualProgress": trace["actual_progress"],
                "predictedProgress": trace["predicted_progress"],
                "success": trace["success"],
            }
        )
    return {
        "schema": 1,
        "id": slug,
        "title": title,
        "record": record,
        "fps": 20,
        "duration": frame / 20,
        "video": f"media/{slug}.mp4",
        "unit": "°" if joint_field == "qpos_rad" else "mm",
        "measure": "Door opening" if joint_field == "qpos_rad" else "Drawer remaining",
        "summary": summary,
        "actions": list(config["candidate_controls"]),
        "samples": samples,
        "steps": steps,
        "calls": calls,
    }


def build(out):
    out = out.resolve()
    if out == ROOT or out == ROOT / "site" or out in (ROOT / "site").parents:
        raise ValueError("Choose a separate build output directory, e.g. _site")
    out.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "style.css", "app.js", "replay.js", "favicon.svg"):
        shutil.copyfile(ROOT / "site" / name, out / name)
    (out / ".nojekyll").touch()
    for name in ("data", "media"):
        (out / name).mkdir(exist_ok=True)
    for spec in EPISODES:
        data = episode(*spec)
        (out / "data" / f"{spec[0]}.json").write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        shutil.copyfile(ROOT / "docs" / "media" / f"{spec[0]}.mp4", out / data["video"])
        print(
            f"{spec[0]}: {len(data['steps'])} decisions, {data['duration']:.2f}s, {len(data['calls'])} calls"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "_site")
    build(parser.parse_args().out)
