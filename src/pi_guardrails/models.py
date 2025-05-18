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

    code: str
    message: str
    rule_id: str | None = None
    severity: str = "error"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data["details"]:
            data.pop("details")
        if data["rule_id"] is None:
            data.pop("rule_id")
        return data


@dataclass
class Decision:
    """Decision returned for a tool call."""

    action: DecisionAction
    tool: str
    reasons: list[str] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.action == DecisionAction.ALLOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "allowed": self.allowed,
            "tool": self.tool,
            "reasons": list(self.reasons),
            "violations": [v.to_dict() for v in self.violations],
            "metadata": dict(self.metadata),
        }


@dataclass
class ToolCall:
    """A tool invocation request to evaluate."""
