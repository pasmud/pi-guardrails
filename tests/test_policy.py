"""Tests for policy loading and validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pi_guardrails.policy import PolicyError, load_policy


class PolicyLoadingTests(unittest.TestCase):
    def test_load_policy_from_dict(self) -> None:
        policy = load_policy(
            {
                "version": 1,
                "default_action": "allow",
                "rules": [{"id": "r1", "action": "deny", "tools": ["shell_exec"]}],
            }
        )
        self.assertEqual(policy.version, 1)
        self.assertEqual(len(policy.rules), 1)
        self.assertEqual(policy.rules[0].id, "r1")

    def test_load_policy_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "policy.json"
            path.write_text(
                json.dumps({"version": 1, "default_action": "deny", "rules": []}),
                encoding="utf-8",
            )
            policy = load_policy(path)
            self.assertEqual(policy.default_action.value, "deny")

    def test_reject_duplicate_rule_ids(self) -> None:
        with self.assertRaises(PolicyError):
            load_policy(
                {
                    "version": 1,
                    "default_action": "allow",
                    "rules": [
                        {"id": "dup", "action": "deny", "tools": ["a"]},
                        {"id": "dup", "action": "deny", "tools": ["b"]},
                    ],
                }
            )

    def test_reject_unknown_when_key(self) -> None:
        with self.assertRaises(PolicyError):
            load_policy(
                {
                    "version": 1,
                    "default_action": "allow",
                    "rules": [
                        {
                            "id": "r1",
                            "action": "deny",
                            "when": {"unknown_key": "value"},
                        }
                    ],
                }
            )

    def test_reject_invalid_regex(self) -> None:
        with self.assertRaises(PolicyError):
            load_policy(
                {
                    "version": 1,
                    "default_action": "allow",
                    "rules": [
                        {
                            "id": "r1",
                            "action": "deny",
                            "when": {"arg_matches": {"path": "["}},
                        }
                    ],
                }
            )

    def test_reject_allow_deny_overlap(self) -> None:
        with self.assertRaises(PolicyError):
            load_policy(
                {
                    "version": 1,
                    "default_action": "allow",
                    "allowed_tools": ["tool_a"],
                    "denied_tools": ["tool_a"],
                }
            )

    def test_reject_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(PolicyError):
                load_policy(path)


if __name__ == "__main__":
    unittest.main()
