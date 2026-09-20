# Alphabet soup: grasp, transport and lower

Seed 1, saved initial state 0. **40 decisions / 314 control steps / 62 TypeSafe calls**, estimated API cost **$0.003022530**.

[Video](../../../docs/media/alphabet-soup.mp4) · [Task configuration](../../../src/jev_libero/tasks/alphabet_soup.json) · [Results](../../../docs/results.md)

The object was lifted by up to 192.35 mm and carried to the basket. LIBERO's containment predicate passed during lowering. **The final state is still grasped, not released and settled.**

`task_config.json` expresses the captured task through the current unified measurement interface. The capture-time configuration and engine are preserved in `original_task_config.json` and `original_source.tar.gz`. API requests, responses, controls and per-step measurements are unchanged. `unified_measurements_check.json` verifies migration by replay: state error 0, measurement difference at floating-point precision, no new API calls.

```bash
jev-libero replay examples/records/alphabet_soup_seed1
```

The [initial unsuccessful trial](../alphabet_soup_seed1_initial) is retained separately.
