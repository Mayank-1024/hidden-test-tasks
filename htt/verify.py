"""Prove a task is well formed before any model is graded on it.

A task passes verification when all of these hold:

1. Static: the task files exist, the gold patch touches only source/doc files
   (never tests), and task.md does not quote the gold patch or name hidden
   tests.
2. Starting tree: every fail-to-pass hidden test fails, every pass-to-pass
   hidden test passes, and the visible suite passes.
3. Gold patch: it applies cleanly, and then every hidden test and the whole
   visible suite pass.
4. Stability: repeated gold runs give identical per-test outcomes.
5. Discrimination: every known-wrong patch in mutants/ (a plausible partial
   or incorrect solution) is rejected by at least one hidden test.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from htt.grading import Grade, grade_tree
from htt.runner import Runner
from htt.tasks import FAIL_TO_PASS_FILE, PASS_TO_PASS_FILE, VISIBLE_TESTS_DIR, Task
from htt.workspace import PatchError, apply_patch, changed_files, materialize

DOC_FILE = re.compile(r"^(CHANGELOG|CHANGES|README|HISTORY)[^/]*$", re.IGNORECASE)
MIN_LEAK_LINE = 30


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Verification:
    task_id: str
    ok: bool
    runner: str
    verified_at: str
    checks: list[Check] = field(default_factory=list)
    start: dict[str, str] = field(default_factory=dict)
    gold: dict[str, str] = field(default_factory=dict)
    hidden_test_ids: list[str] = field(default_factory=list)
    mutants: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _gold_added_lines(patch_text: str) -> list[str]:
    lines, current = [], ""
    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            current = line.split(" b/", 1)[1]
        elif line.startswith("+") and not line.startswith("+++"):
            if DOC_FILE.match(Path(current).name):
                continue
            stripped = line[1:].strip()
            if len(stripped) >= MIN_LEAK_LINE:
                lines.append(stripped)
    return lines


def _hidden_test_names(task: Task) -> list[str]:
    names = []
    for path in sorted(task.hidden_tests.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names += [
            n.name
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
        ]
    return names


def static_checks(task: Task) -> list[Check]:
    checks = []
    for label, path in [
        ("task.md exists", task.task_md),
        ("gold.patch exists", task.gold_patch),
        ("rubric.md exists", task.rubric),
        ("Dockerfile exists", task.dockerfile),
        (f"hidden {FAIL_TO_PASS_FILE} exists", task.hidden_tests / FAIL_TO_PASS_FILE),
        (f"hidden {PASS_TO_PASS_FILE} exists", task.hidden_tests / PASS_TO_PASS_FILE),
    ]:
        checks.append(Check(label, path.exists(), str(path.relative_to(task.root))))
    if not task.gold_patch.exists() or not task.task_md.exists():
        return checks

    patch_text = task.gold_patch.read_text(encoding="utf-8")
    touched = changed_files(patch_text)
    bad = [
        f
        for f in touched
        if not (f.split("/", 1)[0] in task.source_dirs or DOC_FILE.match(f))
        or f.startswith(f"{VISIBLE_TESTS_DIR}/")
    ]
    checks.append(
        Check(
            "gold patch touches only source and doc files",
            bool(touched) and not bad,
            f"touches {touched}" + (f"; not allowed: {bad}" if bad else ""),
        )
    )

    prompt = task.task_md.read_text(encoding="utf-8")
    leaked = [line for line in _gold_added_lines(patch_text) if line in prompt]
    checks.append(
        Check(
            "task.md does not quote the gold patch",
            not leaked,
            f"{len(leaked)} gold lines found in task.md" + (f": {leaked[:3]}" if leaked else ""),
        )
    )
    named = [n for n in _hidden_test_names(task) if n in prompt]
    checks.append(
        Check(
            "task.md does not name hidden tests",
            not named,
            ", ".join(named) if named else "no hidden test names in task.md",
        )
    )
    return checks


def _outcomes(grade: Grade) -> dict[str, str]:
    return {**grade.fail_to_pass, **grade.pass_to_pass, **grade.visible}


def run_checks(task: Task, runner: Runner, repeat: int = 1) -> tuple[list[Check], Grade, Grade]:
    checks = static_checks(task)
    tmp = Path(tempfile.mkdtemp(prefix=f"htt-verify-{task.id}-"))
    try:
        start = grade_tree(task, task.base, runner, use_expected=False)
        f2p_passing = sorted(k for k, v in start.fail_to_pass.items() if v == "passed")
        p2p_failing = sorted(k for k, v in start.pass_to_pass.items() if v != "passed")
        vis_failing = sorted(k for k, v in start.visible.items() if v not in ("passed", "skipped"))
        checks += [
            Check(
                "start: every fail-to-pass test fails",
                bool(start.fail_to_pass) and not f2p_passing,
                f"{len(start.fail_to_pass) - len(f2p_passing)}/{len(start.fail_to_pass)} fail"
                + (f"; passing: {f2p_passing[:5]}" if f2p_passing else ""),
            ),
            Check(
                "start: every pass-to-pass test passes",
                not p2p_failing,
                f"{start.count(start.pass_to_pass)}/{len(start.pass_to_pass)} pass"
                + (f"; failing: {p2p_failing[:5]}" if p2p_failing else ""),
            ),
            Check(
                "start: visible suite passes",
                bool(start.visible) and not vis_failing,
                f"{start.count(start.visible)}/{len(start.visible)} pass, "
                f"{start.count(start.visible, 'skipped')} skipped"
                + (f"; failing: {vis_failing[:5]}" if vis_failing else ""),
            ),
        ]

        gold_tree = materialize(task, tmp / "gold")
        try:
            apply_patch(task.gold_patch, gold_tree)
        except PatchError as e:
            checks.append(Check("gold patch applies cleanly", False, str(e)))
            return checks, start, start
        checks.append(Check("gold patch applies cleanly", True, ""))

        gold = grade_tree(task, gold_tree, runner, use_expected=False)
        hidden_failing = sorted(
            k for k, v in {**gold.fail_to_pass, **gold.pass_to_pass}.items() if v != "passed"
        )
        gold_vis_failing = sorted(
            k for k, v in gold.visible.items() if v not in ("passed", "skipped")
        )
        missing_on_start = sorted(set(gold.fail_to_pass) - set(start.fail_to_pass))
        checks += [
            Check(
                "gold: every hidden test passes",
                bool(gold.fail_to_pass) and not hidden_failing,
                f"{gold.count(gold.fail_to_pass)}/{len(gold.fail_to_pass)} fail-to-pass, "
                f"{gold.count(gold.pass_to_pass)}/{len(gold.pass_to_pass)} pass-to-pass"
                + (f"; failing: {hidden_failing[:5]}" if hidden_failing else ""),
            ),
            Check(
                "gold: visible suite still passes",
                bool(gold.visible) and not gold_vis_failing,
                f"{gold.count(gold.visible)}/{len(gold.visible)} pass"
                + (f"; failing: {gold_vis_failing[:5]}" if gold_vis_failing else ""),
            ),
            Check(
                "same fail-to-pass tests collected on start and gold",
                not missing_on_start,
                f"missing on start: {missing_on_start[:5]}" if missing_on_start else "",
            ),
        ]
        if repeat > 1:
            first = _outcomes(gold)
            unstable = []
            for _ in range(repeat - 1):
                again = _outcomes(grade_tree(task, gold_tree, runner, use_expected=False))
                unstable += [k for k in first if again.get(k) != first[k]]
            checks.append(
                Check(
                    f"gold outcomes identical over {repeat} runs",
                    not unstable,
                    f"unstable: {sorted(set(unstable))[:5]}" if unstable else "",
                )
            )
        return checks, start, gold
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_mutants(task: Task, runner: Runner) -> tuple[list[Check], dict[str, dict]]:
    """Grade every known-wrong patch; each must fail at least one hidden test."""
    checks, details = [], {}
    mutant_dir = task.root / "mutants"
    for patch in sorted(mutant_dir.glob("*.patch")) if mutant_dir.is_dir() else []:
        tmp = Path(tempfile.mkdtemp(prefix=f"htt-mutant-{task.id}-"))
        try:
            tree = materialize(task, tmp / "tree")
            try:
                apply_patch(patch, tree)
            except PatchError as e:
                checks.append(Check(f"mutant {patch.stem} applies", False, str(e)))
                continue
            grade = grade_tree(task, tree, runner, use_expected=False)
            caught = sorted(
                k for k, v in {**grade.fail_to_pass, **grade.pass_to_pass}.items() if v != "passed"
            )
            details[patch.stem] = {
                "rejected": not grade.resolved,
                "failing_hidden_tests": len(caught),
                "examples": [c.split("::", 1)[1] for c in caught[:3]],
                "summary": grade.summary(),
            }
            checks.append(
                Check(
                    f"mutant {patch.stem} is rejected",
                    not grade.resolved and bool(caught),
                    f"{len(caught)} hidden tests fail, e.g. {details[patch.stem]['examples'][:2]}",
                )
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return checks, details


def verify_task(task: Task, runner: Runner, repeat: int = 1, write: bool = True) -> Verification:
    checks, start, gold = run_checks(task, runner, repeat=repeat)
    mutant_checks, mutants = check_mutants(task, runner)
    checks += mutant_checks
    ok = all(c.ok for c in checks)
    result = Verification(
        task_id=task.id,
        ok=ok,
        runner=runner.name,
        verified_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        checks=checks,
        start=start.summary(),
        gold=gold.summary(),
        hidden_test_ids=sorted({**gold.fail_to_pass, **gold.pass_to_pass}),
        mutants=mutants,
    )
    if write and ok:
        (task.root / "verification.json").write_text(
            json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8"
        )
    return result


def format_verification(v: Verification) -> str:
    lines = [f"{v.task_id}: {'VERIFIED' if v.ok else 'FAILED'} (runner: {v.runner})"]
    for c in v.checks:
        lines.append(
            f"  [{'ok' if c.ok else 'FAIL'}] {c.name}" + (f"  ({c.detail})" if c.detail else "")
        )
    lines.append(f"  start tree: {v.start}")
    lines.append(f"  gold patch: {v.gold}")
    return "\n".join(lines)
