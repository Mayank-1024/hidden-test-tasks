"""Command line: verify tasks, run solver attempts, rebuild reports.

uv run python -m htt verify [TASK ...] [--runner docker|local] [--repeat N]
uv run python -m htt solve --task TASK [--attempts N] [--solver claude|gold|noop]
uv run python -m htt estimate
uv run python -m htt report RUN_DIR
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from htt.runner import make_runner
from htt.tasks import REPO_ROOT, list_tasks, load_task


def _tasks(names: list[str]):
    return [load_task(n) for n in names] if names else list_tasks()


def cmd_verify(args: argparse.Namespace) -> int:
    from htt.verify import format_verification, verify_task

    runner = make_runner(args.runner)
    all_ok = True
    for task in _tasks(args.tasks):
        result = verify_task(task, runner, repeat=args.repeat, write=not args.no_write)
        print(format_verification(result))
        all_ok &= result.ok
    return 0 if all_ok else 1


def cmd_solve(args: argparse.Namespace) -> int:
    from htt.attempt import SolveConfig, run_attempts

    config = SolveConfig(
        model=args.model,
        effort=args.effort,
        max_turns=args.max_turns,
        max_output_tokens=args.max_output_tokens,
        max_total_tokens=args.max_total_tokens,
        max_cost_usd=args.max_cost_usd,
    )
    runner = make_runner(args.runner)
    tasks = _tasks(args.task)
    out_dir = Path(args.out) if args.out else None
    run_dir = run_attempts(
        tasks,
        attempts=args.attempts,
        solver_kind=args.solver,
        config=config,
        runner=runner,
        out_dir=out_dir,
        label=args.label,
        budget_usd=args.budget_usd,
    )
    print(f"report: {run_dir / 'report.md'}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from htt.report import rebuild_report

    path = rebuild_report(Path(args.run_dir))
    print(path.read_text(encoding="utf-8"))
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    from htt.pricing import estimate_from_runs

    print(
        estimate_from_runs(
            REPO_ROOT / "runs", attempts_per_task=args.attempts, tasks=len(_tasks([]))
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="htt", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("verify", help="prove tasks are well formed")
    v.add_argument("tasks", nargs="*", help="task ids (default: all)")
    v.add_argument("--runner", default="auto", choices=["auto", "docker", "local"])
    v.add_argument("--repeat", type=int, default=2, help="gold runs to compare for stability")
    v.add_argument("--no-write", action="store_true", help="do not write verification.json")
    v.set_defaults(func=cmd_verify)

    s = sub.add_parser("solve", help="run solver attempts and grade them on hidden tests")
    s.add_argument("--task", action="append", default=[], help="task id (repeatable)")
    s.add_argument("--attempts", type=int, default=1)
    s.add_argument("--solver", default="claude", choices=["claude", "gold", "noop"])
    s.add_argument("--model", default="claude-sonnet-5-5")
    s.add_argument("--effort", default="medium", choices=["low", "medium", "high"])
    s.add_argument("--max-turns", type=int, default=30)
    s.add_argument("--max-output-tokens", type=int, default=16000, help="per model call")
    s.add_argument("--max-total-tokens", type=int, default=1_500_000, help="per attempt")
    s.add_argument("--max-cost-usd", type=float, default=0.90, help="per attempt")
    s.add_argument(
        "--budget-usd",
        type=float,
        default=None,
        help="stop starting new attempts once this much has been spent in the run",
    )
    s.add_argument("--runner", default="auto", choices=["auto", "docker", "local"])
    s.add_argument("--out", default=None, help="run directory (default: runs/<timestamp>)")
    s.add_argument("--label", default="", help="suffix for the run directory name")
    s.set_defaults(func=cmd_solve)

    r = sub.add_parser("report", help="rebuild report.md/report.json for a run directory")
    r.add_argument("run_dir")
    r.set_defaults(func=cmd_report)

    e = sub.add_parser("estimate", help="estimate the cost of a full run from past attempts")
    e.add_argument("--attempts", type=int, default=5)
    e.set_defaults(func=cmd_estimate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
