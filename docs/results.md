# Results & reproducibility

## Included records

These are the four post-distance-fix research runs preserved before the public-package cleanup. They are not new model trials performed during packaging. Only their JSONL storage was losslessly compressed; the package was regression-tested against their original requests and controls.

| Record | Success | Decisions | Environment steps | API calls | API cost, USD |
|---|---|---:|---:|---:|---:|
| [Microwave seed 1](../examples/records/microwave_seed1) | Yes | 14 | 111 | 26 | 0.001248870 |
| [Microwave seed 2](../examples/records/microwave_seed2) | No | 75 | 600 | 127 | 0.005854128 |
| [Microwave seed 3](../examples/records/microwave_seed3) | Yes | 53 | 417 | 128 | 0.004186560 |
| [Top drawer seed 1](../examples/records/top_drawer_seed1) | Yes | 20 | 155 | 30 | 0.001417626 |

Recorded API spend totals **$0.012707184**, excluding local computation. These sample counts do not establish a stable success rate. No VLA comparison or broad LIBERO benchmark claim is made.

All use saved initial-state index 0. Different simulator seeds still change static model placements: a saved flattened state does not contain all model parameters. The remote model's randomness is not controlled by the simulator seed.

## Grasping with the shared measurement interface

| Record | Original LIBERO criterion | Decisions | Environment steps | API calls | Estimated TypeSafe cost, USD |
|---|---|---:|---:|---:|---:|
| [Alphabet soup, initial trial](../examples/records/alphabet_soup_seed1_initial) | Not reached | 60 | 480 | 120 | 0.005692344 |
| [Alphabet soup, corrected configuration](../examples/records/alphabet_soup_seed1) | Passed; object still held | 40 | 314 | 62 | 0.003022530 |

Both use seed 1 and saved initial state 0. The initial trial grasped and transported the object but alternated lifting and lowering over the basket. The retry changed only the lifting contract: transport-clearance lifting is not enabled when already horizontally aligned with the destination. It needed no two-step search.

The featured retry lifted the object's collision-shape bottom by up to **192.35 mm**. Bilateral pad contact, at least 30 mm lift, and no external target contacts held over 206 consecutive sampled frames (10.25 seconds between the first and last). The native containment predicate passed during lowering; the object was still grasped with no external support contact. **Release and settling were not demonstrated.**

These episodes were captured before measurement-interface unification. Their original configurations and engine snapshots are retained alongside a migrated `task_config.json` for current replay. No model calls or controls were rewritten. Offline replay through the unified interface reproduced all 314 controls with state error 0 and maximum task-measurement difference 5.7×10⁻¹⁴. This is migration verification, not another autonomous trial. The current task uses the same declarative measurement interface as microwave and drawer, with no grasp-specific engine branch.

## What succeeded

The microwave successes finish at roughly 0.1901° and 0.1407° open, satisfying the original LIBERO close predicate. The drawer finishes at joint qpos ≈ +0.001157m, satisfying its original predicate. Small zero-limit overshoots are permitted by the simulator's soft joint limits; a negative signed "remaining" display is not a negative geometry gap.

All actual primitives were chosen through Jev calls. The two tasks used identical engine source files and different task JSON. Independent replay of successful records reproduced every recorded state with maximum difference 0 in the tested stack. The public package additionally replays the failed record to its expected failed outcome.

The drawer's 20 decisions included 5 intent and 5 strategy calls, for 30 model calls total. It did not need two-step witness search. It remains a **single task/seed/initial-state demonstration**, not a universally validated drawer controller.

## The failure is included

Microwave seed 2 stops at about 28.33°. At the final checkpoint, the approach gap is about 7.084mm, not the earlier erroneous zero. Holding was predicted to reopen the door by about 1.570°; none of the short branches satisfied the current net-effect conditions. One-/two-step eligibility cannot represent every useful braking or temporary-regression maneuver.

Earlier in this episode, 24 `advance_target` inputs had predicted joint progress within the configured deadband of `hold`. This highlights a limitation of absolute joint progress as an action-quality metric; the implementation does not silently replace it with a different objective after observing failure.

## Verify without paying for inference

```bash
jev-libero inspect examples/records/microwave_seed2
jev-libero replay examples/records/microwave_seed1
jev-libero replay examples/records/top_drawer_seed1
pytest --simulation
```

Use the [tested environment](setup.md). Core policy tests reproduce the state, instructions, criteria and choices for all **493 recorded requests**, including both grasp trials. Optional simulation tests check complete control replay, the original geometry failures, full snapshot restoration, two-step witnesses, and a new runner episode driven by recorded responses rather than a live model.

A replay success verifies a stored trajectory. It is not a new autonomous success and must not be added to the model's success count. Exact live-model reproduction is not promised by a hosted, evolving API.

## Media and time

README GIFs are 320px, 10fps views sampled from recorded renders. MP4s use the original render source. Their simulation-time durations are preserved: 5.55 seconds for the featured microwave run, 7.75 seconds for the drawer, and 15.70 seconds for grasping. They exclude decision and branch-computation latency. The original drawer process took about 131 seconds wall time.

To rebuild media from a new rendered episode:

```bash
pip install -e '.[media]'
python tools/build_media.py runs/my-run/trajectory.gif docs/media/my-demo
```

The repository intentionally omits large redundant research directories and upstream assets. Compact evidence for the four original runs and both grasp trials is included, including failures. The grasp records also preserve their original engine source snapshots. Credentials, unrelated experiments and upstream assets are not published.
