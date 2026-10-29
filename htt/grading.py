"""Grade a tree: run visible + hidden tests against the tree's source code."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from htt.runner import PytestRun, Runner
from htt.tasks import HIDDEN_TESTS_DIR, VISIBLE_TESTS_DIR, Task
from htt.workspace import build_grading_tree

OUTPUT_TAIL_CHARS = 6000


@dataclass
class Grade:
    resolved: bool
    fail_to_pass: dict[str, str]
    pass_to_pass: dict[str, str]
    visible: dict[str, str]
    missing: list[str] = field(default_factory=list)
    other: dict[str, str] = field(default_factory=dict)
    timed_out: bool = False
    duration_s: float = 0.0
    output_tail: str = ""

    @staticmethod
    def count(group: dict[str, str], outcome: str = "passed") -> int:
        return sum(1 for v in group.values() if v == outcome)

    def summary(self) -> dict[str, str]:
        def frac(group: dict[str, str]) -> str:
            return f"{self.count(group)}/{len(group)}"

        skipped = self.count(self.visible, "skipped")
        return {
            "fail_to_pass": frac(self.fail_to_pass),
            "pass_to_pass": frac(self.pass_to_pass),
            "visible": frac(self.visible) + (f" ({skipped} skipped)" if skipped else ""),
        }

    def to_dict(self) -> dict:
        return asdict(self)


def expected_ids(task: Task) -> set[str] | None:
    """Hidden test ids recorded by the last successful verification, if any."""
    record = task.root / "verification.json"
    if not record.exists():
        return None
    data = json.loads(record.read_text(encoding="utf-8"))
    return set(data.get("hidden_test_ids", [])) or None


def grade_run(run: PytestRun, expected: set[str] | None = None) -> Grade:
    f2p = run.group("fail_to_pass")
    p2p = run.group("pass_to_pass")
    visible = run.group("visible")
    other = run.group("other")
    missing = sorted(expected - (set(f2p) | set(p2p))) if expected else []
    resolved = (
        not run.timed_out
        and bool(f2p)
        and all(v == "passed" for v in f2p.values())
        and all(v == "passed" for v in p2p.values())
        and bool(visible)
        and all(v in ("passed", "skipped") for v in visible.values())
        and not any(v in ("failed", "error") for v in other.values())
        and not missing
    )
    return Grade(
        resolved=resolved,
        fail_to_pass=f2p,
        pass_to_pass=p2p,
        visible=visible,
        missing=missing,
        other=other,
        timed_out=run.timed_out,
        duration_s=round(run.duration_s, 2),
        output_tail=run.output[-OUTPUT_TAIL_CHARS:],
    )


def grade_tree(task: Task, tree: Path, runner: Runner, use_expected: bool = True) -> Grade:
    """Grade the source in ``tree`` against pristine visible tests and the hidden tests."""
    tmp = Path(tempfile.mkdtemp(prefix=f"htt-grade-{task.id}-"))
    try:
        grading = build_grading_tree(task, tree, tmp / "tree")
        run = runner.run_pytest(
            task, grading, [VISIBLE_TESTS_DIR, HIDDEN_TESTS_DIR], task.timeout_seconds
        )
        return grade_run(run, expected_ids(task) if use_expected else None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
