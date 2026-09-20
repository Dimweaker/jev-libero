# Contributing

Thank you for helping make small robot decisions easier to inspect and reproduce.

## Local checks

```bash
pip install -e '.[dev]'
ruff check src tests tools
ruff format --check src tests tools
pytest
```

With the robot extra and `LIBERO_ROOT` configured, run `pytest --simulation`. Tests use fixtures/mocks, never paid API calls. Simulation regression may take several minutes.

## Changes we can evaluate

- Keep reusable mechanics in the engine and task semantics in JSON. Do not add task-name conditionals or success-trajectory playback to the live controller.
- For geometry/control changes, include an offline regression and check state restoration as well as derived measurements.
- Preserve failed runs when reporting results. Record configuration, seeds, initial-state index, engine versions, actual controls and API costs. Distinguish replay from new inference.
- Do not quietly override a model choice, relax a success predicate, or substitute fallback values to hide a broken measurement.
- Keep real-world safety claims out of simulator-only results.

## Issues and pull requests

Describe the expected/observed behavior, exact command, task configuration, dependency versions and a minimal reproducible record. Review logs before uploading: remove credentials and any private user data or machine paths. Never include an API key. Avoid checking in entire local run directories, virtual environments, or upstream assets.

Small, focused PRs with explicit limitations are preferred to unverified success claims.
