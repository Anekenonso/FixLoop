# FixLoop Known Blockers & Limitations Ledger

> **Honesty Discipline:** This ledger transparently records all known blockers, environmental constraints, and architectural limitations discovered during development. No blocker is marked resolved unless provably demonstrated by code and evidence.

---

## Active Limitations & Architectural Boundaries

### 1. Named Test Requirement
- **Status:** **ACTIVE LIMITATION (Documented)**
- **Description:** FixLoop currently requires a pre-existing named failing test node (`TEST_NODE: path/to/test.py::test_name`). If an issue report does not contain an identifiable test node, FixLoop halts with `malformed_issue`.
- **Mitigation / Roadmap:** Planned for Reproduce-First mode (see [`ROADMAP.md`](../ROADMAP.md)).

### 2. Single Repository & Python Only
- **Status:** **ACTIVE LIMITATION (By Design)**
- **Description:** The current implementation supports single Python repositories running `pytest`. Multi-repo setups, polyglot environments, and monorepos are outside the v1 scope.

### 3. Attempt Bound (Fixed at 2 Attempts)
- **Status:** **ACTIVE INVARIANT (Core Thesis)**
- **Description:** FixLoop is intentionally bounded to at most 2 verifying attempts. If the second attempt fails to pass the exact target test node, FixLoop halts and records why rather than spiraling into hallucinatory trial-and-error loops.

### 4. Git Commit & Push Manual Boundary
- **Status:** **ACTIVE WORKFLOW CONSTRAINT**
- **Description:** By user rule, all git commits and remote pushes for the repository are executed manually by the human operator. Automated background agents are strictly forbidden from running `git push` or `git commit` on the main project repository.

---

## Resolved Blockers

### 1. Replay Packaging Collisions with Pytest Namespace (`_pytest`)
- **Resolved Date:** 2026-10-10
- **Resolution:** Replaced initial candidate pytest-internal bugs with clean third-party libraries (`pallets/flask` and `psf/requests`) whose modules do not collide with host pytest runtime namespaces.
- **Proof:** All 3 replay cases pass feasibility and live execution 100%.

### 2. Diff Contamination in Replay Directories
- **Resolved Date:** 2026-10-10
- **Resolution:** Updated `tools.edit_file()` to stage only the specifically edited target file rather than running `git add -A`. Added standard `.gitignore` templates to all replay fixtures.
- **Proof:** Clean diff stats on all three replay cases (zero gate rejections for protected path violations).
