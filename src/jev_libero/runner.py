"""Bounded closed-loop execution and complete local records."""

import json
import math
import shutil
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import __version__
from .actions import ACTIONS
from .client import BudgetExceeded, Decisions, append_json
from .config import load_task, project
from .policy import NoFeasibleAction, ValidatedPolicy, contracts


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_media(out, frames, records, display, frame_ends):
    if not frames:
        return
    frames[0].save(
        out / "trajectory.gif", save_all=True, append_images=frames[1:], duration=50, loop=0
    )
    selected = sorted(set([0, len(records) - 1] + list(range(4, len(records), 5))))
    sheet = Image.new("RGB", (1152, 424 * math.ceil(len(selected) / 3)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, j in enumerate(selected):
        x, y = i % 3 * 384, i // 3 * 424
        sheet.paste(frames[frame_ends[j] - 1], (x, y))
        draw.text(
            (x + 8, y + 388),
            f"{j + 1}: {records[j]['choice']}\n{display['label']} {records[j]['after_task_value']:.2f} {display['unit']}",
            fill="black",
        )
    sheet.save(out / "storyboard.jpg")


def run(
    task,
    out,
    seed=0,
    init_state=0,
    max_decisions=100,
    budget_usd=0.10,
    lookahead=2,
    render=True,
    libero_root=None,
    config_dir=None,
    key_file=None,
):
    from .world import World

    cfg = load_task(task)
    if max_decisions < 1 or budget_usd <= 0 or lookahead not in (1, 2):
        raise ValueError("Use positive decision/budget limits and lookahead 1 or 2.")
    out = Path(out).expanduser()
    out.mkdir(parents=True, exist_ok=False)  # Never overwrite or accidentally rebill a run.
    save_json(out / "task_config.json", cfg)
    save_json(
        out / "config.json",
        {
            "version": __version__,
            "task": cfg["policy"]["task_text"],
            "initial_state": init_state,
            "seed": seed,
            "max_decisions": max_decisions,
            "budget_usd": budget_usd,
            "candidate_controls": ACTIONS,
            "horizon_environment_steps": 8,
            "collision_aware": True,
            "two_step_reposition_witnesses": lookahead == 2,
            "geometry_distance_backend": "FCL signed query; nonnegative collision-shape gap",
            "render": render,
            "known_successful_trajectory_used_at_runtime": False,
            "automatic_skills": False,
        },
    )
    shutil.copytree(
        Path(__file__).parent,
        out / "source" / "jev_libero",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    policy = ValidatedPolicy(collision_aware=True, task_config=cfg)
    display = cfg["display"]
    value_key = display["field"]
    progress_key = display["progress_field"]
    world = api = None
    frames, states, commands, records, frame_ends = [], [], [], [], []
    grip = -1.0
    success = False
    error = None
    termination = "decision_limit"
    final = None
    try:
        api = Decisions(out, budget_usd=budget_usd, key_file=key_file)
        world = World(
            init_index=init_state,
            render=render,
            seed=seed,
            task_config=cfg,
            libero_root=libero_root,
            config_dir=config_dir,
        )
        save_json(out / "environment.json", {"libero_config_dir": str(world.config_dir)})
        initial = world.features()
        if initial["success"]:
            raise RuntimeError(
                "Initial state is already successful; refusing to count a trivial success."
            )
        save_json(out / "initial_state.json", initial)
        np.save(out / "initial_sim_state.npy", world.env.sim.get_state().flatten())
        if render:
            Image.fromarray(
                world.env.sim.render(width=384, height=384, camera_name="agentview")[::-1]
            ).save(out / "initial.png")
        for step in range(max_decisions):
            start = time.perf_counter()
            before, predictions = world.predict_all(grip)
            second_branches = 0
            if lookahead == 2 and not contracts(before, predictions, True, cfg)[0]:
                witnesses, second_branches = world.two_step_witnesses(grip)
                for name, witness in witnesses.items():
                    predictions[name]["reposition_witness"] = witness
            prediction_time = time.perf_counter() - start
            append_json(
                out / "predictions.jsonl",
                {
                    "step": step,
                    "before": before,
                    "predictions": predictions,
                    "prediction_seconds": prediction_time,
                    "two_step_evaluations": second_branches,
                },
            )
            start = time.perf_counter()
            choice, routing = policy.choose(api, step, before, predictions)
            decision_time = time.perf_counter() - start
            executed = world.execute(choice, grip, record=True)
            grip = executed["grip"]
            after = executed["features"]
            states.extend(executed["states"])
            commands.extend(executed["commands"])
            frames.extend(Image.fromarray(frame) for frame in executed["frames"])
            frame_ends.append(len(frames))
            expected = predictions[choice]
            state_error = float(
                np.max(
                    np.abs(
                        world.env.sim.get_state().flatten() - np.array(expected["sim_state_after"])
                    )
                )
            )
            success = after["success"]
            policy.feedback(choice, before, after)
            record = {
                "step": step,
                "choice": choice,
                **routing,
                "before_task_value": before[value_key],
                "after_task_value": after[value_key],
                "predicted_progress": expected[progress_key],
                "actual_progress": project(cfg["predictions"], {"before": before, "after": after})[
                    progress_key
                ],
                "prediction_state_max_error": state_error,
                "success": success,
                "cost_usd": api.total,
                "api_calls": api.calls,
                "prediction_seconds": prediction_time,
                "decision_seconds": decision_time,
                "two_step_evaluations": second_branches,
            }
            records.append(record)
            append_json(out / "trace.jsonl", record)
            append_json(
                out / "metrics.jsonl",
                {
                    "step": step + 1,
                    "total": max_decisions,
                    "metrics": {
                        "success": int(success),
                        "task_value": after[value_key],
                        "cost_usd": api.total,
                        "prediction_seconds": prediction_time,
                        "decision_seconds": decision_time,
                        "prediction_error": state_error,
                    },
                },
            )
            if frames:
                frames[-1].save(out / "latest.png")
            print(
                f"{step + 1:03d} {policy.intent} / {policy.strategy} / {choice}: "
                f"{display['label']}={after[value_key]:.4f}{display['unit']} "
                f"success={success} cost=${api.total:.6f}",
                flush=True,
            )
            if state_error > 1e-7:
                raise RuntimeError(f"Prediction/execution mismatch: {state_error}")
            if success:
                termination = "success"
                break
    except (NoFeasibleAction, BudgetExceeded) as exc:
        termination = "no_feasible_action" if isinstance(exc, NoFeasibleAction) else "budget_limit"
        error = str(exc)
    except KeyboardInterrupt:
        termination = "interrupted"
        error = "Interrupted by user"
    except Exception as exc:
        termination = "error"
        error = str(exc)
        (out / "error.log").write_text(traceback.format_exc())
    finally:
        if world is not None:
            try:
                final = world.features()
                save_json(out / "final_state.json", final)
            except Exception as exc:
                termination = "error"
                error = f"{error or ''}; final measurement failed: {exc}"
            np.savez_compressed(
                out / "sim_trajectory.npz",
                states_before=np.asarray(states),
                actions=np.asarray(commands).reshape(-1, 7),
                final_state=world.env.sim.get_state().flatten(),
            )
            world.close()
        if api is not None:
            api.close()
        summary = {
            "success": bool(success and termination == "success"),
            "termination": termination,
            "decisions": len(records),
            "sim_steps": len(commands),
            "api_calls": api.calls if api else 0,
            "intent_calls": policy.intent_calls,
            "strategy_calls": policy.strategy_calls,
            "cost_usd": api.total if api else 0.0,
            "initial_state": init_state,
            "seed": seed,
            "task_config_name": cfg["name"],
            "final_task_value": final[value_key] if final else None,
            "task_value_unit": display["unit"],
            "error": error,
        }
        save_json(out / "summary.json", summary)
        save_media(out, frames, records, display, frame_ends)
    return summary
