import json

import pytest
import requests

from jev_libero.client import BudgetExceeded, Decisions


class Response:
    status_code = 200

    def __init__(self, choice="hold"):
        self.choice = choice

    def json(self):
        return {"answers": {"motor": {"choice": self.choice}}, "usage": {"cost": 0.001}}

    def raise_for_status(self):
        pass


class Session:
    def __init__(self, choice="hold"):
        self.headers = {}
        self.choice = choice
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.choice)

    def close(self):
        pass


def test_request_logging_and_no_credential_leak(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-secret-not-a-real-key")
    session = Session()
    api = Decisions(tmp_path, session=session)
    assert api.choose(0, "motor", {}, "Choose.", {"hold": "stay"}) == "hold"
    assert api.calls == 1 and api.total == 0.001
    text = (tmp_path / "api.jsonl").read_text()
    assert "test-only-secret" not in text and "Authorization" not in text
    assert json.loads(text)["request"] == session.calls[0][1]["json"]


def test_budget_stops_before_request(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    session = Session()
    api = Decisions(tmp_path, budget_usd=0.004, session=session)
    with pytest.raises(BudgetExceeded):
        api.choose(0, "motor", {}, "Choose.", {"hold": "stay"})
    assert not session.calls


def test_invalid_choice_is_not_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    api = Decisions(tmp_path, session=Session("invented"))
    with pytest.raises(ValueError, match="Invalid motor choice"):
        api.choose(0, "motor", {}, "Choose.", {"hold": "stay"})
    assert api.calls == 1  # The response was billed, even though it was rejected.


def test_tls_retry_is_logged(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("jev_libero.client.time.sleep", lambda _: None)
    session = Session()
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise requests.exceptions.SSLError("test transport failure")
        return Response()

    session.post = post
    api = Decisions(tmp_path, session=session)
    assert api.choose(0, "motor", {}, "Choose.", {"hold": "stay"}) == "hold"
    assert len(calls) == 2 and (tmp_path / "transport_errors.jsonl").exists()
