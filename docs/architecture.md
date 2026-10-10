# FixLoop Architectural Specification

## Overview

FixLoop is an autonomous bug-fixing agent designed around a strict separation of authority:
> **The model proposes. Code decides. A recorded stop beats a fabricated PR.**

The system consists of five distinct components:
1. **The Driver Loop (`src/fixloop/driver.py`):** Orchestrates turns, maintains invariant boundaries, and coordinates attempts.
2. **The Six Tools (`src/fixloop/tools.py`):** Minimal, atomic capabilities exposed to the LLM.
3. **The State Projection (`src/fixloop/state.py`):** Immutable file-backed ledger persisting execution history across process turns.
4. **The Gatekeeper (`src/fixloop/gate.py`):** Deterministic inspector enforcing 6 prioritized safety and correctness invariants before any pull request can be opened.
5. **Causal Telemetry (`src/fixloop/tracing.py`):** Neatlogs span collector recording 14-field execution telemetry and powering `trace_lookup` across repair attempts.

---

## System Architecture Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer / Issue
    participant Driver as FixLoop Driver Loop
    participant Model as Stateless Model (LLM)
    participant Tools as Atomic Tools (6)
    participant Gate as Gatekeeper Inspector
    participant Neatlogs as Neatlogs Telemetry

    Dev->>Driver: fixloop run --issue ISSUE_ID
    Driver->>Tools: run_tests(target_node)
    Tools-->>Driver: Baseline Failed (Exit 1)
    Driver->>Neatlogs: Emit span_base

    loop Attempt 1..2 (Max 2 Attempts)
        Driver->>Model: Prompt(State + Issue + Tools)
        Model->>Driver: Tool Call (read_file / edit_file / run_tests)
        Driver->>Tools: Execute Action
        Tools-->>Driver: Result + Diff Update
        Driver->>Neatlogs: Emit 14-field span
        
        alt Attempt 2 and lookup needed
            Model->>Tools: trace_lookup(run_id)
            Tools->>Neatlogs: Fetch prior failed spans
            Tools-->>Model: Return failure context & diff
        end
    end

    Model->>Tools: open_pr(title, body)
    Tools->>Gate: evaluate(state, diff_text, verify())
    
    alt Gate Rejection (Tests modified, node red, diff &gt; 80 lines)
        Gate-->>Driver: Rejected (reason)
        Driver->>Driver: Increment gate_rejects
        Driver->>Driver: Write stop file (NOT FIXED)
    else Gate Approval (Node green, diff confined, tests untouched)
        Gate-->>Driver: Approved
        Driver->>Tools: git checkout -b branch && gh pr create
        Driver->>Driver: Emit Trust Receipt (evidence/receipt-RUN_ID.md)
    end
```

---

## The Six Atomic Tools

FixLoop intentionally avoids arbitrary bash execution (`subprocess.run("bash")` is strictly prohibited). The model is confined to exactly six discrete tools:

1. **`read_issue(issue_id)`**: Reads the problem statement and extracts the invariant `TEST_NODE`.
2. **`read_file(path, start, end)`**: Reads a specified line range from an existing file. Fails if outside repo or outside `--edit-root`.
3. **`edit_file(path, old, new)`**: Performs exact substring replacement. Fails if `old` is not unique, if file is outside `--edit-root`, or if `new` attempts to inject test-skipping directives (`pytest.skip`, `xfail`). Automatically commits the change to git.
4. **`run_tests(node_id)`**: Runs pytest in a sanitized subprocess without passing external environment variables or credentials. Confined strictly to the exact target node.
5. **`trace_lookup(run_id)`**: Reads the causal Neatlogs execution span from the prior attempt, enabling the model to learn from its previous failure without polluting the prompt context.
6. **`open_pr(title, body)`**: Triggers the Gatekeeper. If approved, opens the pull request (or records dry-run evidence) embedding the deterministic Trust Receipt.

---

## Gatekeeper Invariant Hierarchy

When `open_pr` is called, [`src/fixloop/gate.py`](../src/fixloop/gate.py) runs an unbending, deterministic inspection. First failure wins, in strict priority order:

| Priority | Invariant Check | Rationale / Defense |
|---|---|---|
| **1** | **`node_not_green`** | Re-runs the exact target test node in a clean verification subprocess. Must exit 0. |
| **2** | **`regression_failed`** | Runs the entire parent test file. Must exit 0 to ensure adjacent behaviors were not broken. |
| **3** | **`protected_path_touched`** | Diff inspection: all modified files must be confined strictly inside `--edit-root` (e.g. `src/`). Any touch to `tests/`, `pytest.ini`, or `.github/` is instantly rejected. |
| **4** | **`diff_too_large`** | Total added + removed lines must be ≤ 80 lines. Stops model sprawl and over-generation. |
| **5** | **`assert_deleted`** | Scans removed lines (`-`) for `assert `. Prevents models from passing tests by deleting assertions. |
| **6** | **`test_skipped`** | Scans added lines (`+`) for skip directives (`pytest.skip`, `xfail`, `skipif`). Prevents artificial green statuses. |

---

## Causal Memory (`trace_lookup`) vs Naive Agents

In naive single-shot agents, when a patch fails, the model is either restarted blind or hallucinates past attempts. FixLoop decouples the model from execution memory:
- The model is stateless across turns.
- Execution history is projected into structured telemetry (`spans.jsonl` and Neatlogs).
- On attempt 2, the model calls `trace_lookup(run_id)` to inspect the exact failure output, exit code, and modified diff of attempt 1.
- This creates an observable, causal audit trail where recovery is driven by verified feedback rather than lucky prompting.
