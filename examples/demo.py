"""Runnable demo for pi_guardrails.

Run with:
    PYTHONPATH=src python examples/demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pi_guardrails import GuardrailEngine, load_policy


def main() -> int:
    root = Path(__file__).resolve().parent
    policy = load_policy(root / "policy.json")
    calls_doc = json.loads((root / "calls.json").read_text(encoding="utf-8"))
    calls = calls_doc["calls"]

    engine = GuardrailEngine(policy)
    report = engine.evaluate_many(calls)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0
