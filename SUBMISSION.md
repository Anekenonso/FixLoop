# neatHack Official Submission Document

**Submission Window:** Monday 12 Oct 2026, 7:00 PM – 11:55 PM IST  
**Official Submission Flow:** Submit via the official "Submit on X" flow on [neatlogs.com/hackathon](https://neatlogs.com/hackathon) inside the window. Keep the official neatlogs post attached to the quote-post.

---

## 1. Project Information
- **Team Name:** FixLoop
- **Project Name:** FixLoop
- **One-Sentence Thesis:** *"The model proposes. Code decides. A recorded stop beats a fabricated PR."*
- **Repository URL:** https://github.com/Anekenonso/FixLoop
- **Live Demo PR URL:** https://github.com/Anekenonso/fixloop-sandbox/pull/1
- **Live Demo Fixture Repository:** https://github.com/Anekenonso/fixloop-sandbox
- **Demo Video URL:** `<VIDEO_URL>` (3-minute demo recorded per [`docs/demo-script.md`](docs/demo-script.md))
- **Build-in-Public Posts Log:** [`docs/public-posts.md`](docs/public-posts.md)

---

## 2. Official Quote-Post Text

*(Note: Character count is strictly within standard X post limits; URLs count as 23 characters each)*

```
Team Fixloop · Fixloop — a gated issue fixer.
No PR unless the exact test that failed now passes. The retry must read the failed attempt's span, or it stops and says why.
Repo: https://github.com/Anekenonso/FixLoop
Demo (3 min): <VIDEO_URL>
#neatHack
```

---

## 3. Evidence & Claims Index

Every claim made during neatHack is directly verifiable by saved evidence files in this repository:

| Hackathon Criterion / Claim | Verified Evidence Artifact | Description |
|---|---|---|
| **0.0% False PR Rate** | [`evidence/experiments/summary.md`](evidence/experiments/summary.md) | Measured across 36 statistical trials and 3 real historical bug replays. |
| **Statistical Rate Table** | [`evidence/experiments/summary.json`](evidence/experiments/summary.json) | 4-arm ablation matrix (`baseline`, `nogate`, `removal`, `full`) across 3 issues. |
| **Three Real Bug Replays** | [`evidence/replay/summary.md`](evidence/replay/summary.md) | Live execution on SWE-bench Lite bugs from `pallets/flask` and `psf/requests`. |
| **Trust Receipts** | [`evidence/replay/receipt-case-01-flask.md`](evidence/replay/receipt-case-01-flask.md), [`evidence/replay/receipt-case-02-requests-863.md`](evidence/replay/receipt-case-02-requests-863.md), [`evidence/replay/receipt-case-03-flask-4992.md`](evidence/replay/receipt-case-03-flask-4992.md) | Deterministic, code-constructed verification receipts (zero model prose). |
| **20-Row Break Matrix** | [`docs/break-matrix.md`](docs/break-matrix.md), [`tests/test_break_matrix.py`](tests/test_break_matrix.py) | 20 adversarial attacks caught and blocked before git (test-tampering, skips, traversal). |
| **Neatlogs Telemetry** | [`evidence/trace-links.md`](evidence/trace-links.md), [`src/fixloop/tracing.py`](src/fixloop/tracing.py) | 14-field span telemetry powering `trace_lookup` causal recovery across attempts. |
| **Entire Development Provenance** | [`evidence/entire/`](evidence/entire/), Git commit trailers | Unrewritten build trajectory tracking every phase inside the hackathon window. |
| **cfo.ai Financial Plan** | [`plans/unit-economics.md`](plans/unit-economics.md) | Outcome-based SaaS pricing ($40/fix), 99.95% gross margin, 7,944 runs runway. |
| **Live Demonstration PR** | [`evidence/final-pr.json`](evidence/final-pr.json), [PR #1](https://github.com/Anekenonso/fixloop-sandbox/pull/1) | Live pull request opened against public sandbox repo with Trust Receipt embedded. |
| **AWS Compute Architecture** | [`plans/unit-economics.md`](plans/unit-economics.md), [`README.md`](README.md) | Ephemeral microVM test runner modeled on AWS Lambda / ECS Fargate (`us-east-1`). |
| **Crustdata Intelligence** | [`src/fixloop/enrichment.py`](src/fixloop/enrichment.py), [`tests/test_enrichment.py`](tests/test_enrichment.py) | Issue author profile enrichment & enterprise addressable market analysis. |
| **Offline Test Suite** | [`tests/`](tests/) | 86 unit tests passing with zero external network (`pytest -q` exits 0). |
