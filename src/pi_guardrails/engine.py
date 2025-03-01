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
