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
| `binding` | Suite, exact task name, target object, optional joint suffix; original LIBERO success predicate |
| `measurements` | Named, read-only measurements to compute, with explicit entities and dependencies |
| `record_features` | Optional list of feature names to record at every executed control step |
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
- `norm`: Euclidean norm; `index`: select a vector element; `round`: numeric presentation; `count`: list length.

There is no `eval`, dynamic Python import, or executable task script. Unknown operators raise errors.

Available contexts:

| Expression location | Context |
|---|---|
| Measurement expressions | `raw.NAME` referring to another declared measurement |
| Task features | `raw.NAME` from the task's declared measurements |
| Prediction metrics | `before`, `after` |
| Goal contracts | `before`, `after`, `p` (prediction), `thresholds`, `released_required_contacts`, `has_reposition_witness` |
| Witness ranking | `before`, `after`, `p`, `effects.GOAL_NAME` |
| Model projections/feedback | The corresponding `before`, `after`, and/or `p` fields shown in the examples |

The executor retains its mandatory end-effector pose, jaw gap, target/obstacle contacts, force sums, approach gap, and native success check. These support control and feasibility checking independently of task-selected measurements. Summary reducers support `any` or a rounded `[min,max]` range over candidate fields.

## Select measurements, then select outputs

All tasks use the same `measurements` interface. For example, a drawer only needs:

```json
{
  "measurements": {
    "joint_position": {"kind": "joint_position"}
  },
  "features": {
    "remaining_open_mm": {"mul": [{"ref": "raw.joint_position"}, -1000]}
  }
}
```

This does not compute object bounds, external target contacts, or initial-height references. An explicit empty `measurements` object requests no additional measurements. For compatibility, archived schema-1 configurations without this section retain their former joint/body/site sensors.

| Kind | Arguments and result |
|---|---|
| `joint_position` | Active bound joint value, or null for a free object |
| `positions` | `entity`: `body` or `site`; `names`: alias-to-simulator-name map; positions in meters |
| `bounds_mm`, `center_mm` | `entity`: collision-geometry selector; world AABB bounds or its center |
| `pair_center_mm`, `axis`, `gap_mm` | `left`, `right`: geometry selectors; midpoint of point-cloud means, normalized left-to-right axis, or signed surface gap along that axis |
| `span_mm` | `entity`: selector; `axis`: name of an axis measurement; projected collision-shape width |
| `contact_groups` | `entity`: selector; `groups`: label-to-selector map; labels touching the entity |
| `external_contacts`, `external_contact_count` | `entity`: selector; `exclude`: selector list; contact records or count, excluding self-contact and excluded geometry |
| `expression` | `value`: expression combining declared measurements |
| `initial` | `source`: measurement name; value captured at world initialization, unchanged by previews/restores |

Geometry selectors are `{"object": "LIBERO_OBJECT_NAME"}` or `{"group": "target"}`. Built-in groups also include `gripper`, `left_fingerpad`, and `right_fingerpad`. Contact measurements accept `min_normal_force_N`; otherwise they use the task's contact threshold. Counts count contact records, not unique objects. Contact details include geometry name and normal force; the count-only kind does not construct those details.

Dependencies are validated for unknown references and cycles. Measurements and shared point clouds are cached within a read, and only declared operations are evaluated. Intermediate measurements remain in `raw`; **only `features` projections are exported**. The existing `policy.intent_state`, `strategy_state`, and `motor_options` independently select what each Jev layer receives. `record_features` separately controls per-step local logging to `measurements.jsonl`.

The [`alphabet_soup`](../src/jev_libero/tasks/alphabet_soup.json) configuration composes geometry, contact groups, initial values, and expressions through this same interface. It introduces no task-specific measurement class or executor branch. Bilateral contact and lift remain separate observations, not a universal stable-grasp classifier. LIBERO can declare containment while the gripper still holds the object; this configuration does not add a release-and-settle success requirement.

## What a contract means

The current configurations offer approach, establish contact, advance, release contact, and reposition. These are effect conditions, not a fixed sequence. An already-established contact does not remain an unachieved "establish contact" goal.

When all one-step pools are empty, a two-step witness may admit a repositioning input. The terminal effect is evaluated relative to the **original** state, avoiding a spurious "move away then return" improvement. The solver chooses a witness to describe each candidate; Jev still chooses the actual first input. The second input is never executed automatically.

Contact rules currently observe gripper contacts at control-step boundaries. `allowed_other_geoms` contains exact MuJoCo geometry names whose contacts should not count as obstacles. Such permission is task semantics, not a claim of physical safety.

## Boundaries

Configuration externalizes the existing task-dependent logic; it is not a universal task compiler. The engine has one active target, a Panda/OSC interface, and the listed measurements/operators. Stable grasp estimation, multi-target selection, and more elaborate temporal goals need reusable engine capabilities before a JSON file can express them. Model-mutating switch/light tasks are explicitly rejected by the snapshot contract.

Keep LIBERO's success predicate authoritative. A convenient progress score is not a substitute for task completion, and a passive joint drift is not necessarily an action's causal contribution.
