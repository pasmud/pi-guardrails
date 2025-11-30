# pi-guardrails

`pi-guardrails` is a small, deterministic Python library and CLI for **PI-style agent guardrails**: evaluating tool calls against policy rules, enforcing session budgets, and producing structured decisions.

It is designed for agent runtimes that need a clear "should this tool call run?" gate before execution.

## Features

- **Policy checks**: allow, deny, or require approval for tool calls.
- **Tool matching**: exact names and glob patterns (`shell_*`, `http_*`).
- **Rule conditions**: match on tool args (equals/contains/regex/exists/missing), actor, intent, and estimated cost.
- **Budgets**: cap total calls, per-tool calls, total argument payload size, and cumulative estimated cost.
- **Deterministic reports**: JSON/text output for single calls or batches.
- **Offline & stdlib-first**: core library uses Python standard library only.

## Install

From source:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

For development/testing with pytest:

```bash
python -m pip install -e ".[dev]"
```

## Quick start

### 1) Validate a policy

```bash
python -m pi_guardrails validate-policy --policy examples/policy.json
```

### 2) Check tool calls against a policy

```bash
python -m pi_guardrails check \
  --policy examples/policy.json \
  --calls examples/calls.json
```

Text report:

```bash
python -m pi_guardrails check \
  --policy examples/policy.json \
  --calls examples/calls.json \
  --format text
```

Exit non-zero when any call is denied or requires approval:

```bash
python -m pi_guardrails check \
  --policy examples/policy.json \
  --calls examples/calls.json \
  --fail-on-deny
```

### 3) Run the demo script

```bash
PYTHONPATH=src python examples/demo.py
```

## Policy format

Policies are JSON objects. See [`examples/policy.json`](examples/policy.json) for a full example.

```json
{
  "version": 1,
  "default_action": "deny",
  "allowed_tools": ["search_docs", "read_file"],
  "denied_tools": ["shell_exec"],
  "require_approval_tools": ["send_email"],
  "budget": {
    "max_calls": 5,
    "max_total_arg_chars": 2000,
    "max_estimated_cost": 10,
    "per_tool_max_calls": {"search_docs": 3}
  },
  "rules": [
    {
      "id": "allow-read-docs",
      "tools": ["read_file"],
      "action": "allow",
      "reason": "read_file is limited to docs/",
      "when": {
        "arg_matches": {"path": "^docs/[A-Za-z0-9_./-]+$"}
      }
    }
  ]
}
```

### Top-level fields

| Field | Type | Description |
|---|---|---|
| `version` | int | Policy schema version (positive integer). |
| `default_action` | string | `allow`, `deny`, or `require_approval` when no stronger decision applies. |
| `allowed_tools` | list[str] | Tool names/globs explicitly allowed by list. |
| `denied_tools` | list[str] | Tool names/globs explicitly denied by list. |
| `require_approval_tools` | list[str] | Tool names/globs requiring approval by list. |
| `budget` | object | Session budget limits. |
| `rules` | list[object] | Ordered rule definitions; matching rules influence decision by action severity. |

### Rule `when` conditions

All conditions present in a rule must match (logical AND).

| Key | Value | Meaning |
|---|---|---|
| `arg_equals` | object | Dotted arg path equals scalar value. |
| `arg_contains` | object | Dotted arg path string contains substring. |
| `arg_matches` | object | Dotted arg path string matches regex. |
| `arg_exists` | list[str] | Dotted arg paths must exist. |
| `arg_missing` | list[str] | Dotted arg paths must be absent. |
| `actor_equals` | string | Call actor equals value. |
| `actor_in` | list[str] | Call actor is in list. |
| `intent_contains` | string | Intent contains substring. |
| `intent_matches` | string | Intent matches regex. |
| `estimated_cost_gte` | int | Call estimated cost >= value. |
| `estimated_cost_lte` | int | Call estimated cost <= value. |

