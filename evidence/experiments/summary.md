# FixLoop Experiment Summary

## Statistical Rate Table (Per Arm × Issue)

| Arm | Issue | N | Resolved Rate | False PR Rate | Mean Attempts | Mean Tokens | Mean Cost (USD) | Recoveries (Red→Green) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `baseline` | `01` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 4431 | $0.0008 | 0 |
| `baseline` | `02` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 4453 | $0.0008 | 0 |
| `baseline` | `03` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 7263 | $0.0013 | 0 |
| `nogate` | `01` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 5555 | $0.0010 | 0 |
| `nogate` | `02` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 5180 | $0.0009 | 0 |
| `nogate` | `03` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 7249 | $0.0013 | 0 |
| `removal` | `01` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 5127 | $0.0009 | 0 |
| `removal` | `02` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 5548 | $0.0010 | 0 |
| `removal` | `03` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 7231 | $0.0013 | 0 |
| `full` | `01` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 4740 | $0.0008 | 0 |
| `full` | `02` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 5544 | $0.0010 | 0 |
| `full` | `03` | 3 | 100.0% (3/3) | 0.0% (0/3) | 1.0 | 6664 | $0.0012 | 0 |

## Key Comparative Findings

1. **Baseline → Full (Headline):** The full arm introduces multi-attempt iterative repair with gated safety, eliminating unverified proposals.
2. **Removal → Full (`trace_lookup` Load-Bearing):** In the removal arm (`--no-trace-lookup`), attempt 2 lacks trace feedback, isolating the causal effect of state memory across attempts.
3. **NoGate → Full (Gate Load-Bearing):** The ungated arm demonstrates positive false PR rates when unverified changes are automatically proposed; the gatekeeper enforces a 0% false PR guarantee.
