"""Run reports: report.json (everything) and report.md (for people)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def _get(a: Any, key: str, default: Any = None) -> Any:
    return a.get(key, default) if isinstance(a, dict) else getattr(a, key, default)


def _as_dict(a: Any) -> dict:
    return a if isinstance(a, dict) else a.to_dict()


def _f2p_counts(a: dict) -> tuple[int, int]:
    f2p = a.get("fail_to_pass") or {}
    return sum(1 for v in f2p.values() if v == "passed"), len(f2p)


def summarize(attempts: list[dict]) -> dict:
    """Pass rates count graded attempts only. Attempts the API cut short ("error")
    are listed and their spend is counted, but they are not scored as failures."""
    graded = [a for a in attempts if a["status"] == "graded"]
    errored = [a for a in attempts if a["status"] == "error"]
    spent = graded + errored
    per_task: dict[str, dict] = {}
    for task_id in sorted({a["task_id"] for a in attempts}):
        rows = [a for a in graded if a["task_id"] == task_id]
        skipped = sum(1 for a in attempts if a["task_id"] == task_id and a["status"] == "skipped")
        errors = [a for a in errored if a["task_id"] == task_id]
        resolved = sum(1 for a in rows if a["resolved"])
        failed_tests: Counter[str] = Counter()
        for a in rows:
            failed_tests.update(
                k for k, v in (a.get("fail_to_pass") or {}).items() if v != "passed"
            )
            failed_tests.update(a.get("failing_pass_to_pass") or [])
        f2p_fracs = [p / t for p, t in (_f2p_counts(a) for a in rows) if t]
        n = len(rows)
        per_task[task_id] = {
            "kind": rows[0]["kind"] if rows else "",
            "attempts": n,
            "skipped": skipped,
            "errors": len(errors),
            "resolved": resolved,
            "pass_rate": round(resolved / n, 3) if n else None,
            "mean_fail_to_pass_fraction": round(sum(f2p_fracs) / len(f2p_fracs), 3)
            if f2p_fracs
            else None,
            "cost_usd": round(sum(a["cost_usd"] for a in rows + errors), 4),
            "mean_cost_usd": round(sum(a["cost_usd"] for a in rows) / n, 4) if n else None,
            "mean_turns": round(sum(a["turns"] for a in rows) / n, 1) if n else None,
            "mean_test_runs": round(sum(a["test_runs"] for a in rows) / n, 1) if n else None,
            "mean_solve_s": round(sum(a["solve_s"] for a in rows) / n, 1) if n else None,
            "stops": dict(Counter(a["stop"] for a in rows)),
            "most_failed_hidden_tests": failed_tests.most_common(8),
        }
    usage_keys = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "total_tokens",
        "calls",
    )
    totals = {k: sum((a.get("usage") or {}).get(k, 0) for a in spent) for k in usage_keys}
    totals.update(
        {
            "attempts": len(graded),
            "errors": len(errored),
            "skipped": sum(1 for a in attempts if a["status"] == "skipped"),
            "resolved": sum(1 for a in graded if a["resolved"]),
            "cost_usd": round(sum(a["cost_usd"] for a in spent), 4),
            "solve_s": round(sum(a["solve_s"] for a in spent), 1),
        }
    )
    return {"per_task": per_task, "totals": totals}


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def render_markdown(meta: dict, attempts: list[dict], summary: dict) -> str:
    cfg = meta.get("config") or {}
    t = summary["totals"]
    lines = [
        f"# Run report: {meta.get('started_at', '')}",
        "",
        f"- Solver: `{meta.get('solver')}`"
        + (f", model `{cfg.get('model')}`, effort `{cfg.get('effort')}`" if cfg else ""),
        f"- Test runner: `{meta.get('runner')}`"
        + (
            " (isolated container, --network none)"
            if meta.get("runner_isolated")
            else " (no isolation)"
        ),
        f"- Harness commit: `{meta.get('harness_commit')}`",
    ]
    if cfg:
        lines.append(
            f"- Limits per attempt: {cfg.get('max_turns')} model calls, "
            f"{cfg.get('max_output_tokens')} output tokens per call, "
            f"{cfg.get('max_total_tokens'):,} total tokens, ${cfg.get('max_cost_usd')}"
        )
    if meta.get("budget_usd") is not None:
        lines.append(f"- Run budget: ${meta['budget_usd']}")
    if meta.get("finished_at"):
        lines.append(f"- Finished: {meta['finished_at']}")
    if meta.get("resumed_at"):
        lines.append(f"- Resumed: {', '.join(meta['resumed_at'])}")
    if meta.get("note"):
        lines.append(f"- Note: {meta['note']}")
    lines += [
        "",
        "## Results by task",
        "",
        "| Task | Kind | Resolved | Pass rate | Mean fail-to-pass passed | Mean cost | "
        "Mean turns | Mean test runs | Stops |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for task_id, s in summary["per_task"].items():
        stops = ", ".join(f"{k} x{v}" for k, v in s["stops"].items())
        mean_cost = "n/a" if s["mean_cost_usd"] is None else f"${s['mean_cost_usd']:.3f}"
        lines.append(
            f"| {task_id} | {s['kind']} | {s['resolved']}/{s['attempts']} | "
            f"{_pct(s['pass_rate'])} | {_pct(s['mean_fail_to_pass_fraction'])} | "
            f"{mean_cost} | {s['mean_turns']} | {s['mean_test_runs']} | {stops} |"
        )
    lines += [
        "",
        f"**Total:** {t['resolved']}/{t['attempts']} graded attempts resolved"
        + (f", {t['errors']} cut short by an API error (not scored)" if t["errors"] else "")
        + (f", {t['skipped']} not run" if t["skipped"] else "")
        + f". Spend ${t['cost_usd']:.2f} (all attempts). Tokens: {t['input_tokens']:,} input, "
        f"{t['cache_creation_input_tokens']:,} cache write, {t['cache_read_input_tokens']:,} "
        f"cache read, {t['output_tokens']:,} output, over {t['calls']} model calls. "
        f"Solver wall time {t['solve_s'] / 60:.1f} min.",
        "",
        "## Attempts",
        "",
        "| Attempt | Resolved | Fail-to-pass | Pass-to-pass | Visible | Stop | Turns | "
        "Test runs | Cost | Lines +/- | Flags |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for a in attempts:
        if a["status"] == "skipped":
            lines.append(
                f"| {a['task_id']} #{a['attempt']} | not run | | | | {a['stop']} | | | | | |"
            )
            continue
        s = a["summary"]
        verdict = "API error" if a["status"] == "error" else ("yes" if a["resolved"] else "no")
        stop = a["stop"] if len(a["stop"]) <= 60 else a["stop"][:57] + "..."
        lines.append(
            f"| [{a['task_id']} #{a['attempt']}]({a['trajectory_file']}) | "
            f"{verdict} | {s.get('fail_to_pass')} | "
            f"{s.get('pass_to_pass')} | {s.get('visible')} | {stop} | {a['turns']} | "
            f"{a['test_runs']} | ${a['cost_usd']:.3f} | +{a['lines_added']}/-{a['lines_removed']}"
            f" | {', '.join(a['flags']) or '-'} |"
        )
    lines += ["", "## Hidden tests that failed most often", ""]
    for task_id, s in summary["per_task"].items():
        if not s["most_failed_hidden_tests"]:
            continue
        lines.append(f"**{task_id}**")
        lines.append("")
        for test_id, count in s["most_failed_hidden_tests"]:
            lines.append(f"- `{test_id.split('::', 1)[-1]}`: failed in {count} attempt(s)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(out_dir: Path, meta: dict, attempts: list[Any]) -> Path:
    rows = [_as_dict(a) for a in attempts]
    summary = summarize(rows)
    data = {"meta": meta, "summary": summary, "attempts": rows}
    (out_dir / "report.json").write_text(
        json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8"
    )
    md = out_dir / "report.md"
    md.write_text(render_markdown(meta, rows, summary), encoding="utf-8")
    return md


def rebuild_report(run_dir: Path) -> Path:
    data = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    return write_report(run_dir, data["meta"], data["attempts"])
