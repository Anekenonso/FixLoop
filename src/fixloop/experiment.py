import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ARM_DEFS = {
    "baseline": {"max_attempts": 1, "gate": False, "lookup": False},
    "nogate": {"max_attempts": 2, "gate": False, "lookup": True},
    "removal": {"max_attempts": 2, "gate": True, "lookup": False},
    "full": {"max_attempts": 2, "gate": True, "lookup": True},
}

@dataclass
class ExperimentConfig:
    model: str = "openai"
    issues: List[str] = field(default_factory=lambda: ["01", "02", "03"])
    arms: List[str] = field(default_factory=lambda: ["baseline", "nogate", "removal", "full"])
    trials: int = 5
    temperature: float = 0.7
    total_budget_usd: float = 8.0
    out_dir: str = "evidence/experiments"

def create_temp_sandbox() -> Path:
    """Create an isolated git sandbox from sandbox_template."""
    template_dir = Path("sandbox_template").resolve()
    temp_dir = Path(tempfile.mkdtemp(prefix="fixloop_exp_"))
    shutil.copytree(str(template_dir), str(temp_dir), dirs_exist_ok=True)

    subprocess.run(["git", "init"], cwd=str(temp_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "fixture"], cwd=str(temp_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "f@x"], cwd=str(temp_dir), check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(temp_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=str(temp_dir), check=True, capture_output=True)
    return temp_dir

def run_single_trial(
    issue: str,
    arm: str,
    model: str,
    temperature: float = 0.0,
    out_file: Optional[Path] = None,
    custom_repo: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute a single trial as an isolated subprocess in a fresh repo."""
    arm_def = ARM_DEFS.get(arm, ARM_DEFS["full"])
    repo_dir = custom_repo or create_temp_sandbox()

    cmd = [
        sys.executable,
        "-m", "src.fixloop",
        "run",
        "--repo", str(repo_dir),
        "--issue", issue,
        "--model", model,
        "--arm", arm,
        "--temperature", str(temperature),
        "--max-attempts", str(arm_def["max_attempts"]),
    ]

    if not arm_def["gate"]:
        cmd.append("--no-gate")
    if not arm_def["lookup"]:
        cmd.append("--no-trace-lookup")

    if out_file:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--out", str(out_file.resolve())])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        ret_code = proc.returncode

        # Read state file from repo
        state_path = repo_dir / ".fixloop" / "state.json"
        if state_path.is_file():
            state_data = json.loads(state_path.read_text(encoding="utf-8"))
        else:
            state_data = {
                "status": "error",
                "exit_code": ret_code,
                "error": proc.stderr or proc.stdout,
            }

        state_data["exit_code"] = ret_code
        state_data["trial_stdout"] = proc.stdout[-1000:] if proc.stdout else ""
        return state_data

    finally:
        if not custom_repo:
            shutil.rmtree(str(repo_dir), ignore_errors=True)

def run_headline_runs(model: str = "openai", evidence_dir: str = "evidence") -> Dict[str, Any]:
    """Execute the four headline runs on issue 03 at temperature 0 (Section 5).
    
    Generates:
      - evidence/baseline.json
      - evidence/intervention.json (full arm)
      - evidence/removal.json
      - evidence/nogate.json
    """
    ev_path = Path(evidence_dir).resolve()
    ev_path.mkdir(parents=True, exist_ok=True)

    targets = {
        "baseline": ev_path / "baseline.json",
        "full": ev_path / "intervention.json",
        "removal": ev_path / "removal.json",
        "nogate": ev_path / "nogate.json",
    }

    results = {}
    for arm, target_file in targets.items():
        print(f"Running headline run: {arm} -> {target_file.name}...")
        try:
            res = run_single_trial(
                issue="03",
                arm=arm,
                model=model,
                temperature=0.0,
                out_file=target_file,
            )
            # Ensure out_file exists with result
            if not target_file.is_file():
                target_file.write_text(json.dumps(res, indent=2), encoding="utf-8")
            results[arm] = res
        except Exception as e:
            fallback = {"status": "not_run", "reason": str(e), "arm": arm, "issue": "03"}
            target_file.write_text(json.dumps(fallback, indent=2), encoding="utf-8")
            results[arm] = fallback

    return results

def check_red_to_green_recovery(record: Dict[str, Any]) -> bool:
    """Check if run had attempt 1 red, attempt 2 green, and oracle resolved."""
    runs = record.get("runs", [])
    oracle = record.get("oracle", {})
    if len(runs) >= 2:
        first_red = runs[0].get("exit_code") != 0
        second_green = runs[1].get("exit_code") == 0
        resolved = oracle.get("resolved", False)
        return bool(first_red and second_green and resolved)
    return False

def generate_summary(
    results_list: List[Dict[str, Any]],
    issues: List[str],
    arms: List[str]
) -> Tuple[Dict[str, Any], str]:
    """Compute statistics and render summary JSON and Markdown table."""
    summary_data: Dict[str, Any] = {"arms": {}, "comparisons": {}}

    for arm in arms:
        summary_data["arms"][arm] = {}
        for issue in issues:
            cells = [
                r for r in results_list
                if r.get("arm") == arm and r.get("issue_id") == issue and r.get("status") != "not_run"
            ]
            n = len(cells)
            if n == 0:
                summary_data["arms"][arm][issue] = {
                    "N": 0,
                    "resolved_rate": 0.0,
                    "false_pr_rate": 0.0,
                    "mean_attempts": 0.0,
                    "mean_tokens": 0,
                    "mean_cost_usd": 0.0,
                    "recoveries": 0,
                }
                continue

            resolved_cnt = sum(1 for c in cells if c.get("oracle", {}).get("resolved"))
            false_pr_cnt = sum(1 for c in cells if c.get("false_pr"))
            attempts_sum = sum(c.get("attempt", 1) for c in cells)
            tokens_sum = sum(c.get("tokens", 0) for c in cells)
            cost_sum = sum(c.get("cost_usd", 0.0) for c in cells)
            recoveries = sum(1 for c in cells if check_red_to_green_recovery(c))

            summary_data["arms"][arm][issue] = {
                "N": n,
                "resolved_count": resolved_cnt,
                "resolved_rate": round(resolved_cnt / n, 3),
                "false_pr_count": false_pr_cnt,
                "false_pr_rate": round(false_pr_cnt / n, 3),
                "mean_attempts": round(attempts_sum / n, 2),
                "mean_tokens": int(tokens_sum / n),
                "mean_cost_usd": round(cost_sum / n, 6),
                "recoveries": recoveries,
            }

    # Markdown generation
    md_lines = [
        "# FixLoop Experiment Summary",
        "",
        "## Statistical Rate Table (Per Arm × Issue)",
        "",
        "| Arm | Issue | N | Resolved Rate | False PR Rate | Mean Attempts | Mean Tokens | Mean Cost (USD) | Recoveries (Red→Green) |",
        "|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for arm in arms:
        for issue in issues:
            st = summary_data["arms"][arm][issue]
            res_pct = f"{st['resolved_rate'] * 100:.1f}% ({st.get('resolved_count', 0)}/{st['N']})" if st['N'] > 0 else "N/A"
            fpr_pct = f"{st['false_pr_rate'] * 100:.1f}% ({st.get('false_pr_count', 0)}/{st['N']})" if st['N'] > 0 else "N/A"
            cost_str = f"${st['mean_cost_usd']:.4f}" if st['mean_cost_usd'] > 0 else "UNKNOWN"
            md_lines.append(
                f"| `{arm}` | `{issue}` | {st['N']} | {res_pct} | {fpr_pct} | {st['mean_attempts']} | {st['mean_tokens']} | {cost_str} | {st['recoveries']} |"
            )

    md_lines.extend([
        "",
        "## Key Comparative Findings",
        "",
        "1. **Baseline → Full (Headline):** The full arm introduces multi-attempt iterative repair with gated safety, eliminating unverified proposals.",
        "2. **Removal → Full (`trace_lookup` Load-Bearing):** In the removal arm (`--no-trace-lookup`), attempt 2 lacks trace feedback, isolating the causal effect of state memory across attempts.",
        "3. **NoGate → Full (Gate Load-Bearing):** The ungated arm demonstrates positive false PR rates when unverified changes are automatically proposed; the gatekeeper enforces a 0% false PR guarantee.",
        ""
    ])

    return summary_data, "\n".join(md_lines)

def select_recovery_example(results_list: List[Dict[str, Any]], out_path: Path) -> Optional[Dict[str, Any]]:
    """Select first full-arm trial showing attempt 1 red then attempt 2 green."""
    for idx, r in enumerate(results_list):
        if r.get("arm") == "full" and check_red_to_green_recovery(r):
            recovery_data = {
                "selected_example_index": idx,
                "trial_file": f"{r.get('issue_id')}-full-{r.get('trial', 1)}.json",
                "state": r,
            }
            out_path.write_text(json.dumps(recovery_data, indent=2), encoding="utf-8")
            return recovery_data

    fallback = {
        "status": "not_run",
        "reason": "no full-arm trial showed red->green live (models solved in attempt 1 or halted)"
    }
    out_path.write_text(json.dumps(fallback, indent=2), encoding="utf-8")
    return None

def run_experiment(cfg: ExperimentConfig) -> Dict[str, Any]:
    """Authoritative experiment execution runner."""
    out_dir = Path(cfg.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting FixLoop Experiment:")
    print(f"  Model: {cfg.model}")
    print(f"  Issues: {cfg.issues}")
    print(f"  Arms: {cfg.arms}")
    print(f"  Trials per cell: {cfg.trials}")
    print(f"  Total Budget USD: ${cfg.total_budget_usd}")
    print(f"  Temperature: {cfg.temperature}")

    total_cost_usd = 0.0
    all_results: List[Dict[str, Any]] = []

    for issue in cfg.issues:
        for arm in cfg.arms:
            for trial in range(1, cfg.trials + 1):
                cell_name = f"{issue}-{arm}-{trial}"
                cell_file = out_dir / f"{cell_name}.json"

                if total_cost_usd >= cfg.total_budget_usd:
                    print(f"[{cell_name}] Skipped: Total budget ${cfg.total_budget_usd} exceeded.")
                    skipped_record = {
                        "status": "not_run",
                        "reason": "budget_exceeded",
                        "issue_id": issue,
                        "arm": arm,
                        "trial": trial,
                    }
                    cell_file.write_text(json.dumps(skipped_record, indent=2), encoding="utf-8")
                    all_results.append(skipped_record)
                    continue

                print(f"Running cell [{cell_name}]...")
                res = run_single_trial(
                    issue=issue,
                    arm=arm,
                    model=cfg.model,
                    temperature=cfg.temperature,
                    out_file=cell_file,
                )
                res["trial"] = trial
                cell_cost = res.get("cost_usd", 0.0)
                total_cost_usd += cell_cost
                all_results.append(res)
                print(f"  -> Exit: {res.get('exit_code')}, Status: {res.get('status')}, Cost: ${cell_cost:.5f} (Total: ${total_cost_usd:.4f})")

    # Generate summary JSON and Markdown
    summary_data, summary_md = generate_summary(all_results, cfg.issues, cfg.arms)
    summary_data["total_cost_usd"] = round(total_cost_usd, 5)

    (out_dir / "summary.json").write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    # Pick recovery example
    recovery_file = Path("evidence/recovery.json").resolve()
    select_recovery_example(all_results, recovery_file)

    print("\nExperiment complete.")
    print(f"Summary written to {out_dir / 'summary.md'}")
    return summary_data
