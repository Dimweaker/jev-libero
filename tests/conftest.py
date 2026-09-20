import os
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--simulation",
        action="store_true",
        help="Run offline LIBERO tests (robot extra + LIBERO_ROOT required)",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--simulation"):
        for item in items:
            if "simulation" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="use --simulation to enable LIBERO tests"))


@pytest.fixture(autouse=True)
def without_live_api_credentials(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY_FILE", raising=False)


@pytest.fixture(scope="session")
def records_root():
    return Path(__file__).resolve().parents[1] / "examples" / "records"


@pytest.fixture(scope="session")
def simulator(tmp_path_factory):
    if not os.environ.get("LIBERO_ROOT"):
        pytest.fail("--simulation requires LIBERO_ROOT")
    os.environ.setdefault("MUJOCO_GL", "egl")
    os.environ.setdefault("JEV_LIBERO_CONFIG_DIR", str(tmp_path_factory.mktemp("libero-config")))
    from jev_libero.world import World

    return World
