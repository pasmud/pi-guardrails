"""Unit tests for the guardrail engine."""

from __future__ import annotations

import unittest

from pi_guardrails import DecisionAction, GuardrailEngine, load_policy
from pi_guardrails.models import ToolCall


class GuardrailEngineTests(unittest.TestCase):
    def test_default_deny_blocks_unlisted_tool(self) -> None:
        policy = load_policy(
            {
                "version": 1,
                "default_action": "deny",
                "allowed_tools": ["search_docs"],
                "rules": [],
            }
        )
        engine = GuardrailEngine(policy)
        decision = engine.evaluate({"tool": "shell_exec", "args": {"cmd": "ls"}})
        self.assertEqual(decision.action, DecisionAction.DENY)
        self.assertFalse(decision.allowed)

    def test_deny_rule_overrides_allowlist(self) -> None:
        policy = load_policy(
            {
                "version": 1,
                "default_action": "deny",
                "allowed_tools": ["read_file"],
                "rules": [
                    {
                        "id": "deny-secrets",
                        "tools": ["read_file"],
                        "action": "deny",
                        "reason": "secret path",
                        "when": {"arg_contains": {"path": "secret"}},
                    }
                ],
            }
        )
        engine = GuardrailEngine(policy)
        decision = engine.evaluate({"tool": "read_file", "args": {"path": "docs/secret.txt"}})
        self.assertEqual(decision.action, DecisionAction.DENY)
        self.assertTrue(any(v.rule_id == "deny-secrets" for v in decision.violations))

    def test_require_approval_rule(self) -> None:
        policy = load_policy(
            {
                "version": 1,
                "default_action": "allow",
                "rules": [
                    {
                        "id": "approval-email",
                        "tools": ["send_email"],
                        "action": "require_approval",
                        "reason": "email requires review",
                    }
                ],
            }
        )
        engine = GuardrailEngine(policy)
        decision = engine.evaluate({"tool": "send_email", "args": {"to": "a@example.com"}})
        self.assertEqual(decision.action, DecisionAction.REQUIRE_APPROVAL)
        self.assertFalse(decision.allowed)

    def test_budget_max_calls_denies_after_limit(self) -> None:
        policy = load_policy(
            {
                "version": 1,
                "default_action": "allow",
                "budget": {"max_calls": 2},
            }
        )
        engine = GuardrailEngine(policy)
        self.assertEqual(engine.evaluate({"tool": "a", "args": {}}).action, DecisionAction.ALLOW)
        self.assertEqual(engine.evaluate({"tool": "b", "args": {}}).action, DecisionAction.ALLOW)
        third = engine.evaluate({"tool": "c", "args": {}})
        self.assertEqual(third.action, DecisionAction.DENY)
        self.assertTrue(any(v.code == "budget.max_calls" for v in third.violations))
        self.assertEqual(engine.state.total_calls, 2)

    def test_per_tool_budget(self) -> None:
        policy = load_policy(
            {
                "version": 1,
                "default_action": "allow",
                "budget": {"per_tool_max_calls": {"search_docs": 1}},
            }
        )
        engine = GuardrailEngine(policy)
        first = engine.evaluate({"tool": "search_docs", "args": {"q": "a"}})
        second = engine.evaluate({"tool": "search_docs", "args": {"q": "b"}})
        self.assertEqual(first.action, DecisionAction.ALLOW)
        self.assertEqual(second.action, DecisionAction.DENY)
        self.assertEqual(engine.state.per_tool_calls["search_docs"], 1)

    def test_arg_chars_budget(self) -> None:
        policy = load_policy(
            {
                "version": 1,
                "default_action": "allow",
                "budget": {"max_total_arg_chars": 30},
            }
        )
        engine = GuardrailEngine(policy)
        ok = engine.evaluate({"tool": "x", "args": {"a": "12345"}})
        denied = engine.evaluate({"tool": "x", "args": {"a": "12345678901234567890"}})
        self.assertEqual(ok.action, DecisionAction.ALLOW)
        self.assertEqual(denied.action, DecisionAction.DENY)
        self.assertTrue(any(v.code == "budget.max_total_arg_chars" for v in denied.violations))

    def test_estimated_cost_budget(self) -> None:
        policy = load_policy(
            {
                "version": 1,
                "default_action": "allow",
                "budget": {"max_estimated_cost": 5},
            }
        )
        engine = GuardrailEngine(policy)
        ok = engine.evaluate({"tool": "x", "args": {}, "estimated_cost": 3})
        denied = engine.evaluate({"tool": "y", "args": {}, "estimated_cost": 3})
        self.assertEqual(ok.action, DecisionAction.ALLOW)
        self.assertEqual(denied.action, DecisionAction.DENY)
        self.assertTrue(any(v.code == "budget.max_estimated_cost" for v in denied.violations))
