"""End-to-end with fake solvers (gold patch, do nothing) and report generation."""

import json

from htt.attempt import AttemptResult, run_attempts
from htt.report import rebuild_report, summarize, write_report
from htt.solver import SolveConfig


def test_gold_solver_resolves_and_noop_does_not(toy_task, local_runner, tmp_path):
    gold_dir = run_attempts(
        [toy_task], 2, "gold", SolveConfig(), local_runner, out_dir=tmp_path / "gold"
    )
    noop_dir = run_attempts(
        [toy_task], 1, "noop", SolveConfig(), local_runner, out_dir=tmp_path / "noop"
    )

    gold = json.loads((gold_dir / "report.json").read_text())
    assert gold["summary"]["per_task"]["toy-mean"]["resolved"] == 2
    assert gold["summary"]["per_task"]["toy-mean"]["pass_rate"] == 1.0
    first = gold["attempts"][0]
    assert first["summary"] == {"fail_to_pass": "2/2", "pass_to_pass": "1/1", "visible": "2/2"}
    assert first["changed_files"] == ["toylib/stats.py"]
    assert (gold_dir / first["diff_file"]).read_text().startswith("diff --git a/toylib/stats.py")
    assert (gold_dir / first["trajectory_file"]).exists()

    noop = json.loads((noop_dir / "report.json").read_text())
    (attempt,) = noop["attempts"]
    assert attempt["resolved"] is False
    assert attempt["summary"]["fail_to_pass"] == "0/2"
    assert "no_changes" in attempt["flags"]
    assert set(attempt["fail_to_pass"].values()) == {"failed"}


def test_run_budget_skips_remaining_attempts(toy_task, local_runner, tmp_path, monkeypatch):
    import htt.attempt as attempt_module

    real = attempt_module.run_attempt

    def priced(*args, **kwargs):
        result = real(*args, **kwargs)
        result.cost_usd = 0.6
        return result

    monkeypatch.setattr(attempt_module, "run_attempt", priced)
    run_dir = run_attempts(
        [toy_task],
        3,
        "gold",
        SolveConfig(),
        local_runner,
        out_dir=tmp_path / "budget",
        budget_usd=1.0,
    )
    data = json.loads((run_dir / "report.json").read_text())
    statuses = [a["status"] for a in data["attempts"]]
    assert statuses == ["graded", "graded", "skipped"]
    assert data["summary"]["totals"]["cost_usd"] == 1.2
    assert "1 not run" in (run_dir / "report.md").read_text()
    assert data["attempts"][2]["stop"] == "not run: run budget reached"


def attempt(task_id, n, resolved, cost, f2p, stop="end_turn", kind="feature"):
    return AttemptResult(
        task_id=task_id,
        kind=kind,
        attempt=n,
        solver="claude",
        model="claude-sonnet-5-5",
        status="graded",
        resolved=resolved,
        stop=stop,
        turns=4 + n,
        test_runs=1,
        usage={
            "input_tokens": 10,
            "output_tokens": 100,
            "cache_creation_input_tokens": 1000,
            "cache_read_input_tokens": 5000,
            "total_tokens": 6110,
            "calls": 4,
        },
        cost_usd=cost,
        solve_s=30.0,
        summary={"fail_to_pass": "x", "pass_to_pass": "y", "visible": "z"},
        fail_to_pass=f2p,
        diff_file=f"diffs/{task_id}-{n:02d}.diff",
        trajectory_file=f"trajectories/{task_id}-{n:02d}.json",
    )


def test_summary_and_markdown(tmp_path):
    rows = [
        attempt("a", 1, True, 0.10, {"m::t1": "passed", "m::t2": "passed"}),
        attempt("a", 2, False, 0.20, {"m::t1": "passed", "m::t2": "failed"}),
        attempt("a", 3, False, 0.30, {"m::t1": "failed", "m::t2": "failed"}, stop="max_turns"),
        attempt("b", 1, True, 0.05, {"m::t3": "passed"}, kind="bugfix"),
    ]
    summary = summarize([r.to_dict() for r in rows])
    a = summary["per_task"]["a"]
    assert a["resolved"] == 1 and a["attempts"] == 3
    assert a["pass_rate"] == 0.333
    assert a["mean_fail_to_pass_fraction"] == 0.5
    assert a["cost_usd"] == 0.6
    assert a["stops"] == {"end_turn": 2, "max_turns": 1}
    assert a["most_failed_hidden_tests"][0] == ("m::t2", 2)
    assert summary["totals"]["resolved"] == 2
    assert summary["totals"]["cost_usd"] == 0.65
    assert summary["totals"]["cache_read_input_tokens"] == 20000

    meta = {
        "started_at": "2026-10-29T00:00:00Z",
        "solver": "claude",
        "config": {
            "model": "claude-sonnet-5-5",
            "effort": "medium",
            "max_turns": 30,
            "max_output_tokens": 16000,
            "max_total_tokens": 1500000,
            "max_cost_usd": 0.9,
        },
        "runner": "docker",
        "runner_isolated": True,
        "harness_commit": "abc1234",
    }
    md_path = write_report(tmp_path, meta, rows)
    md = md_path.read_text()
    assert "| a | feature | 1/3 | 33% | 50% | $0.200 |" in md
    assert "| b | bugfix | 1/1 | 100% |" in md
    assert "**Total:** 2/4 graded attempts resolved. Spend $0.65 (all attempts)." in md
    assert "`t2`: failed in 2 attempt(s)" in md
    assert "(isolated container, --network none)" in md

    # Rebuilding from report.json gives the same Markdown.
    assert rebuild_report(tmp_path).read_text() == md


class BillingError(Exception):
    status_code = 400


class ScriptedClient:
    """Answers every call from a list; an Exception item is raised instead."""

    def __init__(self, script):
        from tests.test_solver_loop import FakeMessages

        self.messages = FakeMessages(script)


def _done():
    from tests.test_solver_loop import response, text

    return response([text("done")], "end_turn")


def test_fatal_api_error_stops_the_run_and_is_not_scored(toy_task, local_runner, tmp_path):
    client = ScriptedClient([_done(), BillingError("Your credit balance is too low")])
    run_dir = run_attempts(
        [toy_task],
        3,
        "claude",
        SolveConfig(),
        local_runner,
        out_dir=tmp_path / "run",
        client=client,
    )
    data = json.loads((run_dir / "report.json").read_text())
    statuses = [a["status"] for a in data["attempts"]]
    assert statuses == ["graded", "error", "skipped"]
    assert data["attempts"][1]["fatal"] is True
    assert data["attempts"][2]["stop"] == "not run: earlier attempt hit a fatal API error"
    per_task = data["summary"]["per_task"]["toy-mean"]
    # The errored attempt is not counted as a failure.
    assert per_task["attempts"] == 1 and per_task["errors"] == 1 and per_task["skipped"] == 1
    assert "API error" in (run_dir / "report.md").read_text()


def test_resume_runs_only_missing_attempts(toy_task, local_runner, tmp_path):
    client = ScriptedClient([_done(), BillingError("Your credit balance is too low")])
    run_dir = run_attempts(
        [toy_task],
        3,
        "claude",
        SolveConfig(),
        local_runner,
        out_dir=tmp_path / "run",
        client=client,
    )
    first = json.loads((run_dir / "report.json").read_text())["attempts"][0]

    client = ScriptedClient([_done(), _done()])
    run_attempts(
        [toy_task],
        3,
        "claude",
        SolveConfig(),
        local_runner,
        out_dir=run_dir,
        client=client,
        resume=True,
    )
    data = json.loads((run_dir / "report.json").read_text())
    assert [a["status"] for a in data["attempts"]] == ["graded", "graded", "graded"]
    assert data["attempts"][0] == first  # kept, not re-run
    assert len(client.messages.requests) == 2  # only attempts 2 and 3 called the model
    assert data["meta"]["resumed_at"]
