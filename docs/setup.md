# Setup & troubleshooting

## Tested simulation stack

The recorded runs used Linux x86-64 and Python 3.10 with:

| Component | Version |
|---|---|
| LIBERO | `8f1084e3132a39270c3a13ebe37270a43ece2a01` |
| robosuite | 1.4.1 |
| MuJoCo | 3.5.0 |
| NumPy | 1.26.4 |
| PyTorch | 2.2.0 |
| python-fcl | 0.7.0.11 |
| SciPy | 1.15.3 |
| BDDL | 3.6.0 |

Core tests also target Python 3.11; exact simulator replay is validated on the stack above. The robot extra pins the sensitive engine versions. Numerical/asset changes in another stack can invalidate exact replay.

## Install

Follow the [README](../README.md#quick-start). Use a virtual environment. Install our `.[robot]` extra and use the LIBERO checkout as a source/assets tree; **do not additionally install LIBERO's historical requirements file**, which pins a different stack.

CPU PyTorch is enough: Jev runs remotely, and local physics uses MuJoCo. Install the CPU PyTorch wheel first if you do not need CUDA. The renderer is separate from PyTorch.

`LIBERO_ROOT` must point to the repository root containing `libero/libero/{assets,bddl_files,init_files}`. A datasets-directory warning is expected when demonstration datasets have not been downloaded; these tasks do not require those datasets.

## Headless rendering

Set `MUJOCO_GL=egl` **before** importing the simulator. EGL requires a functioning driver/OpenGL installation, including inside a container. GPU access and EGL device visibility must be passed through by the host.

For a machine without EGL, MuJoCo also supports `MUJOCO_GL=osmesa` with system OSMesa libraries installed (for example `libosmesa6` on Debian/Ubuntu). This alternative is not the renderer used for the published examples.

You can avoid camera output entirely:

```bash
jev-libero run --task top_drawer --out runs/no-camera --no-render
```

This still makes paid Jev calls. `jev-libero replay ...` runs without cameras or API calls.

## Configuration and credentials

| Setting | Purpose |
|---|---|
| `LIBERO_ROOT` / `--libero-root` | External LIBERO checkout |
| `JEV_LIBERO_CONFIG_DIR` / `--libero-config-dir` | App-owned LIBERO configuration directory |
| `MUJOCO_GL` | Renderer backend; defaults to `egl` during environment setup |
| `OPENROUTER_API_KEY` | API credential supplied through the environment |
| `OPENROUTER_API_KEY_FILE` / `--api-key-file` | Alternative private credential file |
| `TYPESAFE_API_KEY` | Official TypeSafe credential; select `--provider typesafe` |
| `TYPESAFE_API_KEY_FILE` | Official credential file; `--api-key-file` also works for the selected provider |
| Standard `HTTPS_PROXY` / `HTTP_PROXY` | Optional network proxy, handled by requests |

The default generated LIBERO configuration is under `$XDG_CACHE_HOME/jev-libero/libero` or `~/.cache/jev-libero/libero`, not `~/.libero`. A conflicting existing configuration is not overwritten. Use another config directory or deliberately remove the app-owned cache when changing checkouts. LIBERO captures its config path at import time, so use a new process when changing it.

The package does not load `.env` automatically. `.env.example` documents variable names; export values yourself or use your preferred environment manager. Never paste a real key into an issue or commit it.

## Official API

[Official documentation](https://docs.typesafe.ai/introduction/quickstart) · [API keys](https://console.typesafe.ai/settings/keys)

Use `--provider typesafe` to call `POST https://api.typesafe.ai/v1/systemone` with `jev-latest`. The account's available model names can be listed at `GET https://api.typesafe.ai/v1/models`. OpenRouter stays the default, using `typesafe/jev-1.13`; the official API exposes a moving alias rather than that pinned OpenRouter name. Only transport, credentials, model naming and cost accounting differ—not policy or physics.

## Common outcomes

- **No feasible action:** an explicit policy stop, not an automatically executed fallback. Inspect the last prediction and the configured contracts. The published microwave seed-2 case demonstrates this limit.
- **Replay mismatch:** check engine versions, task JSON, seed, initial-state index, and LIBERO revision. Do not loosen tolerances just to claim a match.
- **Distance/witness inconsistency:** a geometry error. The run stops rather than treating an invalid zero as successful contact. See [architecture](architecture.md#geometry).
- **Budget limit:** the client reserves $0.005 before another call. OpenRouter returns dollar costs; the official TypeSafe API returns token counts, so official costs are estimated at the published $0.042/million input tokens, with free output. Estimates are stored separately without modifying the raw response. This is admission control, not a guaranteed provider-side maximum.
- **TLS/HTTP failure:** logs retain the attempted decision. One TLS retry is made; other errors are not silently retried. Inspect the output before deciding whether to start a new run, since requests may incur costs.

## Local validation

```bash
pip install -e '.[dev]'
pytest
LIBERO_ROOT=/path/to/LIBERO pytest --simulation
```

Tests use mock or recorded responses; no API key is required and no tests call OpenRouter. The simulation suite can take several minutes due to counterfactual physics branches.
