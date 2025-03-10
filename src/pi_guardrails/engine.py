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
