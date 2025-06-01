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

    max_calls: int | None = None
    max_total_arg_chars: int | None = None
    max_estimated_cost: int | None = None
    per_tool_max_calls: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Budget":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("budget must be an object")
        max_calls = _optional_non_negative_int(data.get("max_calls"), "max_calls")
        max_total_arg_chars = _optional_non_negative_int(
            data.get("max_total_arg_chars"), "max_total_arg_chars"
        )
        max_estimated_cost = _optional_non_negative_int(
            data.get("max_estimated_cost"), "max_estimated_cost"
        )
        per_tool_raw = data.get("per_tool_max_calls", {})
        if not isinstance(per_tool_raw, dict):
            raise ValueError("per_tool_max_calls must be an object")
        per_tool: dict[str, int] = {}
        for key, value in per_tool_raw.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("per_tool_max_calls keys must be non-empty strings")
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"per_tool_max_calls['{key}'] must be a non-negative integer")
            per_tool[key] = value
        return cls(
            max_calls=max_calls,
            max_total_arg_chars=max_total_arg_chars,
            max_estimated_cost=max_estimated_cost,
            per_tool_max_calls=per_tool,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.max_calls is not None:
            data["max_calls"] = self.max_calls
        if self.max_total_arg_chars is not None:
            data["max_total_arg_chars"] = self.max_total_arg_chars
        if self.max_estimated_cost is not None:
            data["max_estimated_cost"] = self.max_estimated_cost
        if self.per_tool_max_calls:
            data["per_tool_max_calls"] = dict(self.per_tool_max_calls)
        return data


@dataclass
class Rule:
    """A policy rule applied to tool calls."""

    id: str
    description: str = ""
