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
