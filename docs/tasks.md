# Task configuration

A task is a JSON document loaded by name or path:

```bash
jev-libero tasks
jev-libero validate-task microwave
jev-libero run --task ./my-task.json --out runs/my-task
```

Start with the complete [`microwave`](../src/jev_libero/tasks/microwave.json) or [`top_drawer`](../src/jev_libero/tasks/top_drawer.json) configuration. The CLI saves the resolved configuration in every run.

## Sections

| Section | Responsibility |
|---|---|
| `binding` | Suite, exact task name, target object, optional joint suffix, named body/site sensors; original LIBERO success predicate |
| `contact` | Force threshold, permitted other geometry contacts, contact-part labels, obstacle rejection and release-pair priority |
| `features` | Task-facing measurements derived from common sensors |
| `predictions` | Effect formulas evaluated from branch start/end observations |
| `thresholds` | Progress and approach deadbands; the public runner uses the collision-aware profile |
| `contracts` | Boolean eligibility condition for each local intent |
| `policy` | Intent descriptions; per-layer prompts, projections, summaries, review conditions and feedback |
| `search` | Lexicographic ranking of a second-step witness for each first input |
| `display` | Task value, label, units and progress field for logs/media |

The drawer configuration changes object/joint bindings, task wording, and progress units from degrees to millimeters, including a 0.01mm progress deadband. It does not introduce a new executor or action sequence.

## Expressions, not embedded code

An expression is a scalar/list literal or an object with exactly one operator. Example: meters of joint motion converted to millimeters.

```json
{
  "closing_mm": {
    "mul": [
      {"sub": [{"ref": "after.qpos_m"}, {"ref": "before.qpos_m"}]},
      1000.0
    ]
  }
}
```

Operators:

- `ref`: a dotted field reference.
- `add`, `sub`, `mul`, `div`: scalar or vector arithmetic.
- `ge`, `gt`, `le`, `lt`, `eq`: comparisons.
- `all`, `any`, `not`: Boolean conditions.
- `norm`: Euclidean norm; `index`: select a vector element; `round`: numeric presentation.

There is no `eval`, dynamic Python import, or executable task script. Unknown operators raise errors.

Available contexts:

| Expression location | Context |
|---|---|
| Task features | `raw.joint_position`, `raw.body_positions.NAME`, `raw.site_positions.NAME` |
| Prediction metrics | `before`, `after` |
| Goal contracts | `before`, `after`, `p` (prediction), `thresholds`, `released_required_contacts`, `has_reposition_witness` |
| Witness ranking | `before`, `after`, `p`, `effects.GOAL_NAME` |
| Model projections/feedback | The corresponding `before`, `after`, and/or `p` fields shown in the examples |

Body/site sensor names are bound explicitly in `binding.bodies` / `binding.sites`. The common measurements also expose end-effector pose, jaw gap, target/obstacle contacts, force sums, and the approach gap. Summary reducers support `any` or a rounded `[min,max]` range over candidate fields.

## What a contract means

The current configurations offer approach, establish contact, advance, release contact, and reposition. These are effect conditions, not a fixed sequence. An already-established contact does not remain an unachieved "establish contact" goal.

When all one-step pools are empty, a two-step witness may admit a repositioning input. The terminal effect is evaluated relative to the **original** state, avoiding a spurious "move away then return" improvement. The solver chooses a witness to describe each candidate; Jev still chooses the actual first input. The second input is never executed automatically.

Contact rules currently observe gripper contacts at control-step boundaries. `allowed_other_geoms` contains exact MuJoCo geometry names whose contacts should not count as obstacles. Such permission is task semantics, not a claim of physical safety.

## Boundaries

Configuration externalizes the existing task-dependent logic; it is not a universal task compiler. The engine has one active target, a Panda/OSC interface, and the listed measurements/operators. Stable grasp estimation, multi-target selection, and more elaborate temporal goals need reusable engine capabilities before a JSON file can express them. Model-mutating switch/light tasks are explicitly rejected by the snapshot contract.

Keep LIBERO's success predicate authoritative. A convenient progress score is not a substitute for task completion, and a passive joint drift is not necessarily an action's causal contribution.
