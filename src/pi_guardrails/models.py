"""Data models for pi_guardrails."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DecisionAction(str, Enum):
    """Outcome of evaluating a tool call."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class Violation:
    """A single policy or budget violation."""
