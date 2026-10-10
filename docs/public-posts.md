# FixLoop Build-in-Public Posts Log (#neatHack)

> **Owner Guidelines:** This document contains drafted text and attached evidence paths for posts published by the human author during neatHack (10–12 Oct 2026). All posts are tagged `#neatHack`.

---

## Post 1: Kickoff & The Core Thesis
- **Status:** Ready to post
- **Suggested Timing:** Early window (10 Oct 2026)
- **Draft Copy:**
  > Agents that fix GitHub issues usually open the pull request whether or not the fix works.
  > 
  > I'm building FixLoop for #neatHack: an AI bug-fixer with a strict gatekeeper. It refuses to open a PR unless the exact test that failed now passes. The model proposes. Code decides. A recorded stop beats a fabricated PR.
- **Evidence Attached:**
  - Architecture diagram: [`docs/architecture.md`](architecture.md)
  - Build plan: [`FIXLOOP_BUILD_PLAN.md`](../FIXLOOP_BUILD_PLAN.md)

---

## Post 2: The Naive Agent Failure (Baseline)
- **Status:** Ready to post
- **Suggested Timing:** Mid window
- **Draft Copy:**
  > What happens when an ungated agent tries to fix an issue?
  > 
  > In our baseline trial on Issue 03, the model submitted a patch that just added a comment, left the test failing, and declared victory.
  > 
  > FixLoop caught it, re-ran the exact failing test, and rejected the pull request with a deterministic Trust Receipt.
- **Evidence Attached:**
  - Baseline trial log: [`evidence/baseline.json`](../evidence/baseline.json)
  - Gate reject evidence: [`evidence/gate-reject.txt`](../evidence/gate-reject.txt)
  - Baseline Neatlogs trace: [`evidence/trace-links.md`](../evidence/trace-links.md)

---

## Post 3: Adversarial Self-Testing (The Break Matrix)
- **Status:** Ready to post
- **Suggested Timing:** Mid window
- **Draft Copy:**
  > How I tried to break my own agent:
  > 
  > Built an automated 20-row Break Matrix testing test-deletion, assertion stripping, skips (`pytest.skip`), path traversal (`../../`), and oversize diffs.
  > 
  > 20/20 attacks caught and blocked before touching git. Code is the authority, not the model. #neatHack
- **Evidence Attached:**
  - Full Break Matrix: [`docs/break-matrix.md`](break-matrix.md)
  - Test Suite: [`tests/test_break_matrix.py`](../tests/test_break_matrix.py)

---

## Post 4: Measured Statistical Rates & Real Historical Bugs
- **Status:** Ready to post
- **Suggested Timing:** Late window (11–12 Oct)
- **Draft Copy:**
  > Measured results from 36 statistical trials + 3 real historical SWE-bench bug replays (Flask & Requests):
  > 
  > - False PR rate on gated runs: 0.0% (0 fabricated PRs)
  > - Real bug resolve rate: 3/3 (100%)
  > - Mean cost per fix: $0.0010 USD
  > 
  > Full evidence repo + Neatlogs traces attached. #neatHack
- **Evidence Attached:**
  - Experiment Summary: [`evidence/experiments/summary.md`](../evidence/experiments/summary.md)
  - Replay Summary: [`evidence/replay/summary.md`](../evidence/replay/summary.md)
  - Unit Economics: [`plans/unit-economics.md`](../plans/unit-economics.md)

---

## Post 4b: Live Demonstration Pull Request on GitHub
- **Status:** Ready to post
- **Suggested Timing:** Pre-submission window (12 Oct)
- **Draft Copy:**
  > Just executed FixLoop live on GitHub against a public fixture repository.
  > 
  > The model resolved the swallowed exception in `cache.py`, proved exit code 0 via the code gatekeeper, and opened a real PR on GitHub embedded with a deterministic Trust Receipt.
  > 
  > Live PR: https://github.com/Anekenonso/fixloop-sandbox/pull/1
  > 0 false PRs on gated runs. #neatHack
- **Evidence Attached:**
  - Live PR: [https://github.com/Anekenonso/fixloop-sandbox/pull/1](https://github.com/Anekenonso/fixloop-sandbox/pull/1)
  - Run Evidence: [`evidence/final-pr.json`](../evidence/final-pr.json)
  - Trust Receipt: [`evidence/receipt-final-pr.md`](../evidence/receipt-final-pr.md)

---

## Post 5: Final Demo & Submission Quote-Post
- **Status:** Scheduled for official submission window (12 Oct, 7:00–11:55 PM IST)
- **Official Submission Quote-Post Draft:**
  > Team Fixloop · Fixloop — a gated issue fixer.
  > No PR unless the exact test that failed now passes. The retry must read the failed attempt's span, or it stops and says why.
  > Repo: https://github.com/Anekenonso/FixLoop
  > Demo (3 min): <VIDEO_URL>
  > #neatHack
