"""Policy loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Policy


class PolicyError(ValueError):
    """Raised when a policy cannot be loaded or validated."""
