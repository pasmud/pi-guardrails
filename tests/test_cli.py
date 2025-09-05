"""CLI smoke and behavior tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "pi_guardrails", *args],
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class CliTests(unittest.TestCase):
    def test_help(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("check", result.stdout)
        self.assertIn("validate-policy", result.stdout)

    def test_validate_policy_command(self) -> None:
        policy = REPO_ROOT / "examples" / "policy.json"
        result = run_cli("validate-policy", "--policy", str(policy))
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["policy"]["version"], 1)

    def test_check_command_json_output(self) -> None:
        policy = REPO_ROOT / "examples" / "policy.json"
        calls = REPO_ROOT / "examples" / "calls.json"
        result = run_cli("check", "--policy", str(policy), "--calls", str(calls))
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["total"], 6)
        self.assertEqual(payload["summary"]["allowed"], 2)
        self.assertEqual(payload["summary"]["denied"], 2)
        self.assertEqual(payload["summary"]["require_approval"], 2)

    def test_check_fail_on_deny(self) -> None:
        policy = REPO_ROOT / "examples" / "policy.json"
        calls = REPO_ROOT / "examples" / "calls.json"
        result = run_cli(
            "check",
            "--policy",
            str(policy),
            "--calls",
            str(calls),
            "--fail-on-deny",
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertGreater(payload["summary"]["denied"], 0)

    def test_check_text_output(self) -> None:
        policy = REPO_ROOT / "examples" / "policy.json"
        calls = REPO_ROOT / "examples" / "calls.json"
        result = run_cli(
            "check",
            "--policy",
            str(policy),
            "--calls",
            str(calls),
            "--format",
            "text",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Summary:", result.stdout)
        self.assertIn("tool=read_file", result.stdout)

    def test_invalid_policy_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "bad.json"
            bad.write_text("{bad json", encoding="utf-8")
            calls = REPO_ROOT / "examples" / "calls.json"
            result = run_cli("check", "--policy", str(bad), "--calls", str(calls))
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("invalid JSON", payload["error"])


if __name__ == "__main__":
    unittest.main()
