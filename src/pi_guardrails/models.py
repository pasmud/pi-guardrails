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

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None
    actor: str | None = None
    intent: str | None = None
    estimated_cost: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCall":
        if not isinstance(data, dict):
            raise ValueError("tool call must be an object")
        tool = data.get("tool") or data.get("name")
        if not isinstance(tool, str) or not tool.strip():
            raise ValueError("tool call requires a non-empty 'tool' string")
        args = data.get("args", data.get("arguments", {}))
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise ValueError("'args' must be an object")
        call_id = data.get("call_id") or data.get("id")
        if call_id is not None and not isinstance(call_id, str):
            raise ValueError("'call_id' must be a string when provided")
        actor = data.get("actor")
        if actor is not None and not isinstance(actor, str):
            raise ValueError("'actor' must be a string when provided")
        intent = data.get("intent")
        if intent is not None and not isinstance(intent, str):
            raise ValueError("'intent' must be a string when provided")
        estimated_cost = data.get("estimated_cost", 0)
        if not isinstance(estimated_cost, int) or estimated_cost < 0:
            raise ValueError("'estimated_cost' must be a non-negative integer")
        return cls(
            tool=tool.strip(),
            args=dict(args),
            call_id=call_id,
            actor=actor,
            intent=intent,
            estimated_cost=estimated_cost,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"tool": self.tool, "args": dict(self.args)}
        if self.call_id is not None:
            data["call_id"] = self.call_id
        if self.actor is not None:
            data["actor"] = self.actor
        if self.intent is not None:
            data["intent"] = self.intent
        if self.estimated_cost:
            data["estimated_cost"] = self.estimated_cost
        return data


@dataclass
class Budget:
    """Budget limits for a session."""
