# orchestrate-kit

English | [正體中文](README.zh-TW.md)

A Claude Code plugin that makes Claude work like a tech lead: diagnose the task, cut narrow work orders, dispatch Sonnet/Opus executor subagents, verify the result itself, grade the risk of the change, send medium/high-risk changes to an adversarial reviewer, adjudicate the findings, and close with a report.

## What's inside

| Component | Type | Role |
| --- | --- | --- |
| `orchestrate-v2` | skill (manual invocation) | The 7-phase flow: diagnose → work orders → dispatch → verify → risk-graded review → adjudicate → close. Rules, templates and scripts load only at the step that needs them. |
| `risk-grade` | skill | Three-layer funnel for a code change: hard gates → safe-change allowlist → judgement. Every grade is written to a ledger. |
| `risk-calibrate` | skill | Compares ledger grades with what actually happened and proposes wording changes to the risk policy. Never edits the policy itself. |
| `debug-by-evidence` | skill | Evidence before fixes. Phase 1 uses it for bug / failing-test / flaky / performance tasks. |
| `executable-spec` | skill | Three-layer executable specifications. The flow stops and asks for one when a task needs a SPEC that does not exist yet. |
| `sonnet-lite-executor`, `sonnet-executor`, `opus-executor` | agents | Work-order executors, routed by difficulty and by risk signals. They only do what the work order says and never touch git. |
| `opus-reviewer` | agent | Adversarial reviewer for medium/high-risk changes. Returns raw findings; the orchestrator adjudicates. |

## Requirements

- Claude Code with plugin support, on a plan that can run both Sonnet and Opus (the agents pin their models).
- [`uv`](https://docs.astral.sh/uv/) — the scripts are single-file PEP 723 scripts run with `uv run`.
- Python 3.10+ and `git` on PATH.
- Windows: set `PYTHONUTF8=1` once (`setx PYTHONUTF8 1`) so script output containing CJK text is not mangled by the CP950 console.

## Install

```
/plugin marketplace add a951753abc/orchestrate-kit
/plugin install orchestrate-kit@orchestrate-kit
```

Start a new Claude Code session after installing.

## Usage

```
/orchestrate-kit:orchestrate-v2 <task description>
```

What happens:

1. **Diagnose** — reads the task and the code, classifies assumptions; product decisions that need you are raised before any work order is cut.
2. **Work orders** — each order has a goal, an allowed-file list, executable acceptance commands and prohibitions; a risk-signal estimate per order drives executor routing.
3. **Dispatch** — acceptance commands are run first on the current tree to prove they can fail; a baseline snapshot is taken before every dispatch.
4. **Verify** — baseline compare (out-of-scope files → redo) plus the orchestrator re-running every acceptance command itself. Executor reports are not evidence.
5. **Review** — `risk-grade` decides; medium/high goes to `opus-reviewer` with a four-aspect focus text, low is self-verified.
6. **Adjudicate** — every finding is checked against the code: real → new narrow work order, false → rejected with a reason, plausible → handed to you.
7. **Close** — report, and the ledger outcome is written back. Nothing is committed unless you say so.

Standalone use:

- `/orchestrate-kit:risk-grade <scope and context>` — grade a change without the full flow.
- `/orchestrate-kit:risk-calibrate [project dir]` — once a project has roughly ten graded changes with outcomes.
- `debug-by-evidence` and `executable-spec` are picked up automatically from their descriptions, or invoke them by name.

Where state lives:

- Per-project risk policy: `.claude/risk-policy.yaml` (created from the bundled template on request; declares your sensitive paths and safe-change paths).
- Global ledger: `~/.claude/risk-grade/ledger.jsonl`.
- Baseline manifests: `<system temp>/claude-orchestrate/<repo hash>/`.

## Optional: Codex as reviewer or rescue

Not bundled. By default the flow reviews with `opus-reviewer` and, after two executor failures on the same order, switches executor lineage (Sonnet ↔ Opus) for rescue. If you have the OpenAI Codex CLI and want a heterogeneous model in the loop:

1. Install [ai-orchestra](https://github.com/jason201385-commits/ai-orchestra). Its `dispatch.py` exposes a read-only `codex-review` provider and a full-access `codex-full` provider.
2. Add `~/.claude/agents/codex-reviewer.md` (tools: `Bash`). Its contract: write the focus text to a temp file, run `cd <repo> && cat <file> | PYTHONUTF8=1 python <ai-orchestra>/scripts/dispatch.py codex-review --label <name> --timeout <seconds>` in the background, wait for the completion notification, and return Codex's final message verbatim as findings — no fixing, no filtering. The review sandbox is read-only, so the prompt must tell Codex to run `git diff` itself.
3. Nothing else to configure: the review rule prefers `codex-reviewer` when it exists and falls back to `opus-reviewer` after one failure, without retrying. Rescue can be pointed at `codex-full` the same way.

## Language

Skill bodies, rules and templates are written in Traditional Chinese. Claude follows them in any session language; if you want reports in English, say so in your `CLAUDE.md`.

## Updating

```
/plugin update orchestrate-kit@orchestrate-kit
```

Then start a new session.

## License

MIT
