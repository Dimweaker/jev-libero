# Recorded episodes

These are preserved research-run artifacts, not freshly executed model trials from the packaged CLI. See [results](../../docs/results.md) and [provenance.json](provenance.json).

Each directory contains:

- Original task/run configuration, summary, initial/final observations and audit.
- `api.jsonl.gz`: complete model request bodies, responses, usage and timings.
- `predictions.jsonl.gz`: complete recorded one-step forecasts and any two-step witnesses.
- `trace.jsonl.gz`: actual selected inputs and hierarchy routing.
- `sim_trajectory.npz`: actual low-level controls and flattened simulator states.
- `replay_check.json` where an independent success replay was recorded during research.

Compression is lossless. No credentials or Authorization headers are present. Physics-preview computations and actual executed controls are separate records.

```bash
jev-libero inspect examples/records/top_drawer_seed1
jev-libero replay examples/records/top_drawer_seed1  # requires robot stack, no API calls
```

Read compressed logs from Python:

```python
from jev_libero.records import read_jsonl
trace = read_jsonl("examples/records/top_drawer_seed1/trace.jsonl")
print(trace[-1]["success"])
```

The initial-state index alone does not specify the whole scene: seeds can affect static model geometry. Reproduce the engine versions and LIBERO revision as well. These arrays are not a standard LIBERO HDF5 training dataset.
