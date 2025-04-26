"""Policy evaluation engine."""

from __future__ import annotations

import fnmatch
import json
import re
from typing import Any

from .models import (
    BudgetState,
    Decision,
    DecisionAction,
    EvaluationReport,
    Policy,
    Rule,
    ToolCall,
    Violation,
)


_ACTION_PRIORITY = {
    DecisionAction.ALLOW: 0,
    DecisionAction.REQUIRE_APPROVAL: 1,
    DecisionAction.DENY: 2,
}


class GuardrailEngine:
    """Evaluate tool calls against a policy and session budgets.

    The engine is deterministic and stateful: budget counters are updated only
    when a call is allowed. Denied and approval-required calls do not consume
    budget.
    """

    def __init__(self, policy: Policy):
        self.policy = policy
        self.state = BudgetState()

    def reset(self) -> None:
        self.state = BudgetState()

    def evaluate(self, call: ToolCall | dict[str, Any]) -> Decision:
        tool_call = call if isinstance(call, ToolCall) else ToolCall.from_dict(call)
        violations: list[Violation] = []
        reasons: list[str] = []
        matched_rules: list[Rule] = []

        # 1) Explicit tool lists. denied_tools is a hard deny; require_approval_tools
        # is an approval floor; allowed_tools marks a tool as explicitly allowed.
        hard_deny = any(
            _tool_matches(pattern, tool_call.tool) for pattern in self.policy.denied_tools
        )
        list_requires_approval = any(
            _tool_matches(pattern, tool_call.tool)
            for pattern in self.policy.require_approval_tools
        )
        list_allows = any(
            _tool_matches(pattern, tool_call.tool) for pattern in self.policy.allowed_tools
        )

        if hard_deny:
            reasons.append("tool list matched: deny")
            violations.append(
                Violation(
                    code="tool_list",
                    message=f"tool '{tool_call.tool}' matched deny list",
                    severity="error",
                    details={"tool": tool_call.tool, "action": DecisionAction.DENY.value},
                )
            )
        elif list_requires_approval:
            reasons.append("tool list matched: require_approval")
            violations.append(
                Violation(
                    code="tool_list",
                    message=f"tool '{tool_call.tool}' matched require_approval list",
                    severity="warning",
                    details={
                        "tool": tool_call.tool,
                        "action": DecisionAction.REQUIRE_APPROVAL.value,
                    },
                )
            )
        elif list_allows:
            reasons.append("tool list matched: allow")

        # 2) Rules. Evaluate all matching rules; the most restrictive matching rule
        # determines the rule verdict. A matching allow rule can override default deny,
        # but never a hard deny list or an approval floor from tool lists.
        for rule in self.policy.rules:
            if not self._rule_matches(rule, tool_call):
                continue
            matched_rules.append(rule)
            reason = rule.reason or rule.description or f"rule {rule.id} matched"
            reasons.append(f"[{rule.id}] {reason}")
            if rule.action != DecisionAction.ALLOW:
                violations.append(
                    Violation(
                        code="rule_match",
                        message=reason,
                        rule_id=rule.id,
                        severity="error" if rule.action == DecisionAction.DENY else "warning",
                        details={"action": rule.action.value, "tool": tool_call.tool},
                    )
                )

        if hard_deny:
            action = DecisionAction.DENY
        else:
            if matched_rules:
                rule_action = max(
                    (rule.action for rule in matched_rules),
                    key=lambda a: _ACTION_PRIORITY[a],
                )
                action = rule_action
            elif list_requires_approval:
                action = DecisionAction.REQUIRE_APPROVAL
            elif list_allows:
                action = DecisionAction.ALLOW
            elif self.policy.allowed_tools and not list_allows:
                # Allowlist configured but tool is not listed and no rule matched:
                # fall back to default_action (typically deny for strict allowlists).
                action = self.policy.default_action
            else:
                action = self.policy.default_action

            if list_requires_approval and _ACTION_PRIORITY[action] < _ACTION_PRIORITY[
                DecisionAction.REQUIRE_APPROVAL
            ]:
                action = DecisionAction.REQUIRE_APPROVAL

        # 3) Budget checks apply to calls that would otherwise execute.
        # We check projected usage to avoid overshoot.
        budget_violations = self._check_budget(tool_call)
        if budget_violations:
            violations.extend(budget_violations)
            for violation in budget_violations:
                reasons.append(violation.message)
            action = DecisionAction.DENY

        # 4) If no rule/list matched and default is allow, include a reason.
        if not reasons:
            reasons.append(f"default action: {action.value}")

        # Deduplicate reasons while preserving order.
        deduped_reasons = list(dict.fromkeys(reasons))

        decision = Decision(
            action=action,
            tool=tool_call.tool,
            reasons=deduped_reasons,
            violations=violations,
            metadata={
                "matched_rules": [r.id for r in matched_rules],
                "policy_version": self.policy.version,
            },
        )

        if decision.action == DecisionAction.ALLOW:
            self._consume_budget(tool_call)

        return decision

    def evaluate_many(self, calls: list[ToolCall | dict[str, Any]]) -> EvaluationReport:
        decisions = [self.evaluate(call) for call in calls]
        return EvaluationReport(
            decisions=decisions,
            budget_state=self.state,
            policy_version=self.policy.version,
        )

    # _action_from_tool_lists removed: list handling is in evaluate() to allow
    # rule-based allow overrides while preserving deny/approval floors.
    def _rule_matches(self, rule: Rule, call: ToolCall) -> bool:
        if rule.tools and not any(_tool_matches(pattern, call.tool) for pattern in rule.tools):
            return False
        return _when_matches(rule.when, call)

    def _check_budget(self, call: ToolCall) -> list[Violation]:
        violations: list[Violation] = []
        b = self.policy.budget
        projected_calls = self.state.total_calls + 1
        arg_chars = _arg_chars(call.args)
        projected_arg_chars = self.state.total_arg_chars + arg_chars
        projected_cost = self.state.total_estimated_cost + max(call.estimated_cost, 0)
        projected_tool_calls = self.state.per_tool_calls.get(call.tool, 0) + 1

        if b.max_calls is not None and projected_calls > b.max_calls:
            violations.append(
                Violation(
                    code="budget.max_calls",
                    message=(
                        f"max_calls exceeded: projected {projected_calls} > limit {b.max_calls}"
                    ),
                    severity="error",
                    details={"projected": projected_calls, "limit": b.max_calls},
                )
            )

        tool_limit = b.per_tool_max_calls.get(call.tool)
        if tool_limit is not None and projected_tool_calls > tool_limit:
            violations.append(
                Violation(
                    code="budget.per_tool_max_calls",
                    message=(
                        f"per-tool max calls exceeded for '{call.tool}': "
                        f"projected {projected_tool_calls} > limit {tool_limit}"
                    ),
                    severity="error",
                    details={
                        "tool": call.tool,
                        "projected": projected_tool_calls,
                        "limit": tool_limit,
                    },
                )
            )

        if b.max_total_arg_chars is not None and projected_arg_chars > b.max_total_arg_chars:
            violations.append(
                Violation(
                    code="budget.max_total_arg_chars",
                    message=(
                        "max_total_arg_chars exceeded: "
                        f"projected {projected_arg_chars} > limit {b.max_total_arg_chars}"
                    ),
                    severity="error",
                    details={
                        "projected": projected_arg_chars,
                        "limit": b.max_total_arg_chars,
                    },
                )
            )

        if b.max_estimated_cost is not None and projected_cost > b.max_estimated_cost:
            violations.append(
                Violation(
                    code="budget.max_estimated_cost",
                    message=(
                        "max_estimated_cost exceeded: "
                        f"projected {projected_cost} > limit {b.max_estimated_cost}"
                    ),
                    severity="error",
                    details={"projected": projected_cost, "limit": b.max_estimated_cost},
                )
            )

        return violations

    def _consume_budget(self, call: ToolCall) -> None:
        self.state.total_calls += 1
        self.state.total_arg_chars += _arg_chars(call.args)
        self.state.total_estimated_cost += max(call.estimated_cost, 0)
        self.state.per_tool_calls[call.tool] = (
            self.state.per_tool_calls.get(call.tool, 0) + 1
        )


def _tool_matches(pattern: str, tool: str) -> bool:
    # fnmatch gives simple glob semantics: *, ?, [seq].
    return fnmatch.fnmatch(tool, pattern)


def _arg_chars(args: dict[str, Any]) -> int:
    try:
        return len(json.dumps(args, sort_keys=True, separators=(",", ":")))
    except (TypeError, ValueError):
        return len(str(args))


def _when_matches(when: dict[str, Any], call: ToolCall) -> bool:
    if not when:
        return True

    for key, expected in when.get("arg_equals", {}).items():
        if _get_arg(call.args, key) != expected:
            return False

    for key, substring in when.get("arg_contains", {}).items():
        value = _get_arg(call.args, key)
        if not isinstance(value, str) or substring not in value:
            return False

    for key, pattern in when.get("arg_matches", {}).items():
        value = _get_arg(call.args, key)
        if not isinstance(value, str) or re.search(pattern, value) is None:
            return False

    for key in when.get("arg_exists", []):
        if not _arg_exists(call.args, key):
            return False

    for key in when.get("arg_missing", []):
        if _arg_exists(call.args, key):
            return False

    if "actor_equals" in when:
        if call.actor != when["actor_equals"]:
            return False

    if "actor_in" in when:
        if call.actor not in when["actor_in"]:
            return False

    if "intent_contains" in when:
        if not isinstance(call.intent, str) or when["intent_contains"] not in call.intent:
            return False

    if "intent_matches" in when:
        if not isinstance(call.intent, str) or re.search(when["intent_matches"], call.intent) is None:
            return False

    if "estimated_cost_gte" in when:
        if call.estimated_cost < when["estimated_cost_gte"]:
            return False

    if "estimated_cost_lte" in when:
        if call.estimated_cost > when["estimated_cost_lte"]:
            return False

    return True


def _arg_exists(args: dict[str, Any], path: str) -> bool:
    sentinel = object()
    return _get_arg(args, path, default=sentinel) is not sentinel


def _get_arg(args: dict[str, Any], path: str, default: Any = None) -> Any:
    """Resolve dotted path with optional [index] segments."""

    current: Any = args
    for token in _iter_path_tokens(path):
        if isinstance(token, str):
            if not isinstance(current, dict) or token not in current:
                return default
            current = current[token]
        else:
            if not isinstance(current, list):
                return default
            index = token
            if index < 0 or index >= len(current):
                return default
            current = current[index]
    return current


_PATH_RE = re.compile(r"([^[.\]]+)|\[(\d+)\]")


def _iter_path_tokens(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for match in _PATH_RE.finditer(path):
        name, index = match.groups()
        if name is not None:
            tokens.append(name)
        else:
            tokens.append(int(index))
    if not tokens:
        # Fallback for unusual keys: treat whole path as one key.
        return [path]
    # Ensure we consumed meaningful chars; otherwise use raw path.
    rebuilt = "".join(f"[{t}]" if isinstance(t, int) else t for t in tokens)
    # Allow dot separators in original by checking token coverage loosely.
    cleaned_original = path.replace(".", "")
    cleaned_rebuilt = rebuilt.replace(".", "")
    if cleaned_rebuilt != cleaned_original:
        return [path]
