"""Policy loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Policy


class PolicyError(ValueError):
    """Raised when a policy cannot be loaded or validated."""


def load_policy(source: str | Path | dict[str, Any]) -> Policy:
    """Load a policy from a dict, JSON string, or file path.

    The loader is intentionally strict: malformed input raises ``PolicyError``.
    """

    if isinstance(source, Policy):
        return source
    if isinstance(source, dict):
        data = source
    elif isinstance(source, Path):
        data = _load_from_path(source)
    elif isinstance(source, str):
        data = _load_from_string(source)
    else:
        raise PolicyError(f"unsupported policy source type: {type(source).__name__}")

    try:
        policy = Policy.from_dict(data)
    except ValueError as exc:
        raise PolicyError(str(exc)) from exc
    validate_policy(policy)
    return policy


def _load_from_path(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyError(f"cannot read policy file '{path}': {exc}") from exc
    return _parse_json(text, source=str(path))


def _load_from_string(value: str) -> dict[str, Any]:
    stripped = value.strip()
    if not stripped:
        raise PolicyError("policy string is empty")
    # Heuristic: if it looks like JSON, parse directly; otherwise treat as path.
    if stripped.startswith("{"):
        return _parse_json(stripped, source="<string>")
    path = Path(stripped)
    if path.exists() and path.is_file():
        return _load_from_path(path)
    # Fall back to parsing JSON to give a useful error for malformed inline JSON.
    return _parse_json(stripped, source="<string>")


def _parse_json(text: str, *, source: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PolicyError(f"invalid JSON in policy {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyError(f"policy {source} must contain a JSON object")
    return data


def validate_policy(policy: Policy) -> None:
    """Perform semantic validation beyond structural parsing."""

    seen_ids: set[str] = set()
    for rule in policy.rules:
        if rule.id in seen_ids:
            raise PolicyError(f"duplicate rule id: '{rule.id}'")
        seen_ids.add(rule.id)
        _validate_when(rule.id, rule.when)

    for tool_list_name in ("allowed_tools", "denied_tools", "require_approval_tools"):
        values = getattr(policy, tool_list_name)
        if len(values) != len(set(values)):
            raise PolicyError(f"{tool_list_name} contains duplicates")

    overlap = set(policy.allowed_tools) & set(policy.denied_tools)
    if overlap:
        raise PolicyError(
            "tools cannot be both allowed and denied: " + ", ".join(sorted(overlap))
        )


_ALLOWED_WHEN_KEYS = {
    "arg_equals",
    "arg_contains",
    "arg_matches",
    "arg_exists",
    "arg_missing",
    "actor_equals",
    "actor_in",
    "intent_contains",
    "intent_matches",
    "estimated_cost_gte",
    "estimated_cost_lte",
}


def _validate_when(rule_id: str, when: dict[str, Any]) -> None:
    unknown = set(when) - _ALLOWED_WHEN_KEYS
    if unknown:
        allowed = ", ".join(sorted(_ALLOWED_WHEN_KEYS))
        raise PolicyError(
            f"rule '{rule_id}' has unknown when keys: {', '.join(sorted(unknown))}; "
            f"allowed: {allowed}"
        )

    for key in ("arg_equals", "arg_contains", "arg_matches"):
        value = when.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise PolicyError(f"rule '{rule_id}' when.{key} must be an object")
        for arg_name, matcher in value.items():
            if not isinstance(arg_name, str) or not arg_name:
                raise PolicyError(f"rule '{rule_id}' when.{key} keys must be non-empty strings")
            if key == "arg_equals":
                _ensure_json_scalar(rule_id, f"when.{key}.{arg_name}", matcher)
            elif key == "arg_contains":
                if not isinstance(matcher, str):
                    raise PolicyError(
                        f"rule '{rule_id}' when.{key}.{arg_name} must be a string"
                    )
            elif key == "arg_matches":
                if not isinstance(matcher, str):
                    raise PolicyError(
                        f"rule '{rule_id}' when.{key}.{arg_name} must be a regex string"
                    )
                _ensure_regex(rule_id, matcher)

    for key in ("arg_exists", "arg_missing"):
        value = when.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            raise PolicyError(f"rule '{rule_id}' when.{key} must be a list of strings")

    if "actor_equals" in when and not isinstance(when["actor_equals"], str):
        raise PolicyError(f"rule '{rule_id}' when.actor_equals must be a string")
    if "actor_in" in when:
        actor_in = when["actor_in"]
        if not isinstance(actor_in, list) or not all(isinstance(a, str) for a in actor_in):
            raise PolicyError(f"rule '{rule_id}' when.actor_in must be a list of strings")
    if "intent_contains" in when and not isinstance(when["intent_contains"], str):
        raise PolicyError(f"rule '{rule_id}' when.intent_contains must be a string")
    if "intent_matches" in when:
        pattern = when["intent_matches"]
        if not isinstance(pattern, str):
            raise PolicyError(f"rule '{rule_id}' when.intent_matches must be a regex string")
        _ensure_regex(rule_id, pattern)
    for key in ("estimated_cost_gte", "estimated_cost_lte"):
        if key in when:
            value = when[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise PolicyError(
                    f"rule '{rule_id}' when.{key} must be a non-negative integer"
                )
