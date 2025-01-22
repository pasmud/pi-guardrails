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
