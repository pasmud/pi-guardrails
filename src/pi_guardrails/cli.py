"""Command-line interface for pi_guardrails."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .engine import GuardrailEngine
from .models import ToolCall
