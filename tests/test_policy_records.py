import json

import pytest

from jev_libero.config import load_task
from jev_libero.policy import NoFeasibleAction, ValidatedPolicy, contracts
from jev_libero.records import read_jsonl


class RecordedAnswers:
    """An offline API substitute that requires exactly the recorded request."""

    def __init__(self, folder):
        self.calls = read_jsonl(folder / "api.jsonl")
        self.index = 0

    def choose(self, step, layer, state, instructions, criteria):
        original = self.calls[self.index]
        self.index += 1
        assert (step, layer) == (original["step"], original["layer"])
        assert state == original["request"]["state"]
        question = original["request"]["questions"][layer]
        assert instructions == question["instructions"]
        assert criteria == question["criteria"]
        return original["response"]["answers"][layer]["choice"]


@pytest.mark.parametrize(
    "name",
    [
        "microwave_seed1",
        "microwave_seed2",
        "microwave_seed3",
        "top_drawer_seed1",
        "alphabet_soup_seed1",
        "alphabet_soup_seed1_initial",
    ],
)
def test_all_recorded_requests_preserved(records_root, name):
    folder = records_root / name
    cfg = load_task(folder / "task_config.json")
    api = RecordedAnswers(folder)
    policy = ValidatedPolicy(True, cfg)
    trace = read_jsonl(folder / "trace.jsonl")
    predictions = read_jsonl(folder / "predictions.jsonl")
    for row, old in zip(predictions, trace):
        choice, routing = policy.choose(api, row["step"], row["before"], row["predictions"])
        assert choice == old["choice"]
        assert routing["eligible_by_intent"] == old["eligible_by_intent"]
        policy.feedback(choice, row["before"], row["predictions"][choice]["after"])
    assert api.index == len(api.calls)
    if len(predictions) > len(trace):
        last = predictions[-1]
        with pytest.raises(NoFeasibleAction):
            policy.choose(api, last["step"], last["before"], last["predictions"])


def test_configuration_controls_eligibility(records_root):
    folder = records_root / "microwave_seed1"
    rows = read_jsonl(folder / "predictions.jsonl")
    cfg = load_task(folder / "task_config.json")
    row = next(
        r
        for r in rows
        if "advance_target" in contracts(r["before"], r["predictions"], True, cfg)[0]
    )
    cfg["contracts"]["advance_target"] = False
    assert "advance_target" not in contracts(row["before"], row["predictions"], True, cfg)[0]


def test_recorded_costs_and_successes(records_root):
    successes = {}
    for folder in sorted(p for p in records_root.iterdir() if p.is_dir()):
        summary = json.loads((folder / "summary.json").read_text())
        calls = read_jsonl(folder / "api.jsonl")
        if summary.get("cost_basis") == "token-price estimate":
            estimates = read_jsonl(folder / "cost_estimates.jsonl")
            cost = sum(c["estimated_cost_usd"] for c in estimates)
            assert len(estimates) == len(calls)
            assert cost == pytest.approx(
                sum(c["response"]["usage"]["input_tokens"] for c in calls) * 0.042 / 1_000_000
            )
        else:
            cost = sum(c["response"]["usage"]["cost"] for c in calls)
        assert cost == pytest.approx(summary["cost_usd"])
        assert len(calls) == summary["api_calls"]
        successes[folder.name] = summary["success"]
    assert successes == {
        "microwave_seed1": True,
        "microwave_seed2": False,
        "microwave_seed3": True,
        "top_drawer_seed1": True,
        "alphabet_soup_seed1": True,
        "alphabet_soup_seed1_initial": False,
    }
