"""Small, auditable adapter for OpenRouter's Jev Decisions API."""

import json
import os
import time
from pathlib import Path

import requests

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"


class BudgetExceeded(RuntimeError):
    pass


def append_json(path, record):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def api_key(key_file=None):
    if key_file or os.environ.get("OPENROUTER_API_KEY_FILE"):
        value = (
            Path(key_file or os.environ["OPENROUTER_API_KEY_FILE"]).expanduser().read_text().strip()
        )
    else:
        value = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not value:
        raise ValueError(
            "Set OPENROUTER_API_KEY or OPENROUTER_API_KEY_FILE (never commit credentials)."
        )
    return value


class Decisions:
    def __init__(self, out, budget_usd=0.10, key_file=None, model=MODEL, session=None):
        self.out = Path(out)
        self.budget_usd = budget_usd
        self.model = model
        self.total = 0.0
        self.calls = 0
        self.session = session if session is not None else requests.Session()
        self.session.headers["Authorization"] = "Bearer " + api_key(key_file)

    def choose(self, step, layer, state, instructions, criteria):
        if self.total + 0.005 > self.budget_usd:
            raise BudgetExceeded(
                f"API cost guard reached (${self.total:.6f}, budget ${self.budget_usd:.2f})"
            )
        body = {
            "model": self.model,
            "state": state,
            "questions": {
                layer: {"type": "choice", "instructions": instructions, "criteria": criteria}
            },
        }
        for attempt in range(2):
            start = time.perf_counter()
            try:
                response = self.session.post(ENDPOINT, json=body, timeout=45)
                break
            except requests.exceptions.SSLError as exc:
                append_json(
                    self.out / "transport_errors.jsonl",
                    {
                        "step": step,
                        "layer": layer,
                        "attempt": attempt,
                        "request": body,
                        "error": str(exc),
                    },
                )
                if attempt:
                    raise
                time.sleep(2)
        elapsed = time.perf_counter() - start
        try:
            result = response.json()
        except ValueError:
            append_json(
                self.out / "api.jsonl",
                {
                    "step": step,
                    "layer": layer,
                    "request": body,
                    "http_status": response.status_code,
                    "response_text": response.text,
                    "latency_s": elapsed,
                },
            )
            response.raise_for_status()
            raise
        # Only body and response are logged; never request headers or credentials.
        append_json(
            self.out / "api.jsonl",
            {
                "step": step,
                "layer": layer,
                "request": body,
                "response": result,
                "http_status": response.status_code,
                "latency_s": elapsed,
            },
        )
        response.raise_for_status()
        self.total += result["usage"]["cost"]
        self.calls += 1
        choice = result["answers"][layer]["choice"]
        if choice not in criteria:
            raise ValueError(f"Invalid {layer} choice returned: {choice}")
        return choice

    def close(self):
        self.session.close()
