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

