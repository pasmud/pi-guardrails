"""Tests for policy loading and validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pi_guardrails.policy import PolicyError, load_policy
