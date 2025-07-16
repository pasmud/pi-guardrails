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
