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
    check.add_argument(
        "--fail-on-deny",
        action="store_true",
        help="Exit with code 2 if any call is denied or requires approval.",
    )

    validate = subparsers.add_parser(
        "validate-policy",
        help="Validate a policy file and report normalized policy details.",
    )
    validate.add_argument("--policy", required=True, help="Path to policy JSON file.")
    validate.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            return _cmd_check(args)
        if args.command == "validate-policy":
            return _cmd_validate_policy(args)
        parser.error(f"unknown command: {args.command}")
        return 2
    except PolicyError as exc:
        _emit_error(str(exc), getattr(args, "format", "json"))
        return 2
    except ValueError as exc:
        _emit_error(str(exc), getattr(args, "format", "json"))
        return 2
    except OSError as exc:
        _emit_error(str(exc), getattr(args, "format", "json"))
        return 2


def _cmd_check(args: argparse.Namespace) -> int:
    policy = load_policy(Path(args.policy))
    calls = _load_calls(Path(args.calls))
    engine = GuardrailEngine(policy)
    report = engine.evaluate_many(calls)

    payload = report.to_dict()
    if args.format == "json":
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_format_text_report(payload))

    has_block = report.denied_count > 0 or report.approval_count > 0
    if args.fail_on_deny and has_block:
        return 2
    return 0


def _cmd_validate_policy(args: argparse.Namespace) -> int:
    policy = load_policy(Path(args.policy))
    payload = {
        "ok": True,
        "policy": policy.to_dict(),
        "rules": len(policy.rules),
    }
    if args.format == "json":
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(
            f"Policy OK: version={policy.version} rules={len(policy.rules)} "
            f"default_action={policy.default_action.value}\n"
        )
    return 0


def _load_calls(path: Path) -> list[ToolCall]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read calls file '{path}': {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in calls file '{path}': {exc}") from exc

    if isinstance(data, dict):
        if "calls" in data:
            raw_calls = data["calls"]
        elif "tool" in data or "name" in data:
            raw_calls = [data]
        else:
            raise ValueError(
                "calls file object must contain a 'calls' list or be a tool call object"
            )
    elif isinstance(data, list):
        raw_calls = data
    else:
        raise ValueError("calls file must contain a JSON object or array")

    if not isinstance(raw_calls, list):
        raise ValueError("'calls' must be a list")

    calls: list[ToolCall] = []
    for index, item in enumerate(raw_calls):
        try:
            calls.append(ToolCall.from_dict(item))
        except ValueError as exc:
            raise ValueError(f"invalid call at index {index}: {exc}") from exc
    return calls


def _format_text_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = report["summary"]
    lines.append(
        "Summary: total={total} allowed={allowed} denied={denied} require_approval={require_approval}".format(
            **summary
        )
    )
    for idx, decision in enumerate(report["decisions"], start=1):
        lines.append(
            f"{idx}. tool={decision['tool']} action={decision['action']} allowed={str(decision['allowed']).lower()}"
        )
        for reason in decision.get("reasons", []):
            lines.append(f"   - {reason}")
    state = report["budget_state"]
    lines.append(
        "Budget: calls={total_calls} arg_chars={total_arg_chars} estimated_cost={total_estimated_cost}".format(
            **state
        )
    )
    return "\n".join(lines) + "\n"


def _emit_error(message: str, fmt: str) -> None:
    if fmt == "json":
        json.dump({"ok": False, "error": message}, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stderr.write(f"error: {message}\n")
