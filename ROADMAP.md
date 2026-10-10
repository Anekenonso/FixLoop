# FixLoop Roadmap

> **Engineering Discipline Notice:** All items in this roadmap represent forward-looking plans and architectural designs. They are **never** presented as claims of current system capability. FixLoop's verified, measured claims are strictly documented in [`docs/claims-audit.md`](docs/claims-audit.md).

---

## 1. Reproduce-First Mode (High Priority)
- **Current Limitation:** FixLoop currently requires a pre-existing failing test node (`TEST_NODE`) to anchor its verification loop. Many real-world issues only provide unstructured bug reports or stack traces without a repro test.
- **Planned Solution:** A two-stage workflow where an isolated subagent drafts a reproduction test case in a quarantined directory (`repro/test_repro.py`). A human engineer approves the reproduction test node with one click, after which FixLoop's standard gated repair loop takes over.

---

## 2. GitHub Actions CI/CD Integration
- **Concept:** Run FixLoop directly inside GitHub Actions on newly opened issue tickets or failing triage runs.
- **Workflow:**
  1. Trigger on issue labeled `fixloop-triage`.
  2. Parse reproduction test from issue metadata or run reproduction step.
  3. Spin up an isolated runner, attempt gated repair up to 2 attempts.
  4. If verification passes: Open pull request containing the deterministic Trust Receipt in the PR body.
  5. If verification fails: Post comment detailing the recorded stop reason, diff stats, and Neatlogs trace link. Zero unverified PRs opened.

---

## 3. Multi-Language & Test Runner Expansion
- **Current Support:** Python + `pytest`.
- **Planned Runners:**
  - TypeScript / JavaScript: `vitest` and `jest`.
  - Rust: `cargo test`.
  - Go: `go test`.
- **Architecture:** Abstract the test execution interface behind a pluggable runner protocol (`TestRunner`) while retaining the immutable gatekeeper guarantees (diff bounds, test preservation, oracle verification).

---

## 4. Outcome-Based SaaS Pricing (Derived from cfo.ai Plan)
- **Business Model:** Align vendor incentives directly with engineering integrity:
  - **$40.00 per verified merged PR**: Billed only when the exact failing test passes gate verification and is merged upstream.
  - **100% Refund / Zero-Charge on Stops**: If FixLoop exhausts attempts or halts due to a gate violation, the run is completely free of charge.
- **Unit Economics Viability:** As validated in [`plans/unit-economics.md`](plans/unit-economics.md), FixLoop operates at a **99.95% gross margin** with a mean model cost of **$0.001007 USD** per run, making an outcome-based guarantee economically dominant over traditional subscription models.
