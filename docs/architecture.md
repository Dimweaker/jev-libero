# Architecture

## Modules

- `actions.py`: 18 translations (world xyz × ±3/10/40mm), 6 rotations (xyz × ±10°), open/close/hold.
- `environment.py`, `scene.py`: isolated LIBERO setup and target collision bindings, without historical rollout-script imports.
- `world.py`: generic Cartesian execution, contact features, full snapshots and reversible one-/two-step previews.
- `geometry.py`: independent FCL distance queries over MuJoCo collision shapes.
- `config.py`, `policy.py`: safe expressions, effect eligibility, and serial Jev decisions.
- `client.py`: OpenRouter or official TypeSafe requests, cost admission checks and credential-free request-body logs. Official token-based cost estimates are recorded separately from raw API responses.
- `runner.py`, `records.py`, `cli.py`: bounded runs, artifacts, inspection and offline control replay.

The public package contains no replay-based task controller. `replay` is a separate, explicitly offline verification command.

## Control and snapshots

Each chosen primitive lasts at most eight 20Hz environment steps. Translation uses Cartesian feedback toward a fixed local target. Rotation is applied on the first control step; zero rotation then retains the OSC orientation target. The gripper command persists unless Jev chooses open/close. Success can end a primitive early.

A branch snapshot includes MuJoCo data, OSC controller state, gripper command accumulation, robot buffers, observation caches, environment clocks, and Python/NumPy random states. Saving only qpos/qvel is insufficient. Every branch starts from the same full snapshot; previews do not advance the actual episode.

After execution, the saved predicted and actual flattened simulator states are compared. A discrepancy stops the run. This verifies branch/live consistency, not real-world model accuracy.

## Geometry

The tested MuJoCo 3.5.0 native distance query produced false zeros for some separated mesh/box pairs. At one recorded checkpoint, it returned zero while its own witness points were about 108mm apart. This polluted an approach metric even though dynamics replay was exact.

The engine therefore uses FCL over the same collision-enabled primitives and mesh convex hulls. It updates their transforms from MuJoCo for every query; the live simulator's collision solver and model are unchanged. Signed distance handles separation and penetration through one interface; `max(0, signed_distance)` defines the approach gap. MuJoCo contact forces independently determine force-bearing contact.

Invalid distance/witness results raise errors; they are not replaced by guessed values. Shape checks, original false-zero regressions, snapshot checks and recorded controls cover different failure modes. No single state-equality check proves all derived geometry features correct.

## Policy and responsibility

The hierarchy is serial: intent → predicted contact/motion family → motor input. Intent reviews are triggered by configured conditions; strategies remain active while eligible, with a review if another family can finish the task. These mechanisms do not prescribe a task-stage script.

Code owns candidate generation, dynamics predictions and eligibility. Jev owns selection among the offered candidates. A single eligible input is still submitted but should not be presented as meaningful reasoning. Two-step search is local planning performed by code, not hidden Jev reasoning.

Short horizons and restrictive contracts can reject useful temporary regressions. Absolute predicted progress can also include passive motion. The published failed run exposes these limitations rather than substituting an unlogged fallback controller.

## Runtime artifacts

| File | Content |
|---|---|
| `config.json`, `task_config.json` | Run options and exact task definition |
| `api.jsonl` | Request bodies, responses, usage and latency; no Authorization headers |
| `predictions.jsonl` | Counterfactual outcomes, timing and any two-step witnesses |
| `trace.jsonl`, `metrics.jsonl` | Chosen inputs, hierarchy routing, outcomes and progress |
| `sim_trajectory.npz` | `states_before`, seven-dimensional controls, `final_state` |
| `summary.json` | Explicit success/termination/error and recorded API spend |
| `source/` | Runtime package snapshot |
| `trajectory.gif`, `storyboard.jpg` | Optional images of actual execution |

Rendered media omits preview/API waiting. Artifacts are not a standard LIBERO training-demonstration HDF5 dataset. Flattened simulator state also excludes static model geometry: the task configuration, seed, assets and engine version matter for replay.
