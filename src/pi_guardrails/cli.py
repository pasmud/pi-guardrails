"""Command-line interface for pi_guardrails."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .engine import GuardrailEngine
from .models import ToolCall
from .policy import PolicyError, load_policy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pi-guardrails",
        description="PI-style guardrails for agent tool calls, budgets, and policy checks.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser(
        "check",
        help="Evaluate tool calls from a JSON file against a policy.",
    )
    check.add_argument("--policy", required=True, help="Path to policy JSON file.")
    check.add_argument(
        "--calls",
        required=True,
        help="Path to JSON file containing a tool call object or a list of tool calls.",
    )
    check.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json).",
    )
