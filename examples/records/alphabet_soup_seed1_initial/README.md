# Alphabet soup: initial trial

Seed 1, saved initial state 0. **60 decisions / 480 control steps / 120 TypeSafe calls**, estimated API cost **$0.005692344**. Stopped at the decision limit without satisfying LIBERO's containment predicate.

The object was grasped and transported above the basket, but lifting and lowering objectives remained simultaneously eligible and the robot alternated between them. The [retry](../alphabet_soup_seed1) only changed lifting eligibility to exclude states already horizontally aligned with the destination.

Original calls, controls, measurements, configuration and source snapshot are retained. `task_config.json` migrates only the measurement declarations for current replay; `original_task_config.json` and `original_source.tar.gz` preserve the capture-time implementation.

```bash
jev-libero replay examples/records/alphabet_soup_seed1_initial
```
