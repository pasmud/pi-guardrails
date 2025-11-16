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

