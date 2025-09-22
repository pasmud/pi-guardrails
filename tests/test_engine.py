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
