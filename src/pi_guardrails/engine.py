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
