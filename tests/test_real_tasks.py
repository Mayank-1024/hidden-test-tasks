"""Static checks on the three real tasks. Nothing here executes vendored code."""

import json

import pytest

from htt.tasks import list_tasks
from htt.verify import static_checks
from htt.workspace import changed_files

TASKS = list_tasks()


def test_three_tasks_of_three_kinds():
    assert sorted(t.kind for t in TASKS) == ["bugfix", "feature", "refactor"]


@pytest.mark.parametrize("task", TASKS, ids=[t.id for t in TASKS])
def test_static_checks_pass(task):
    failed = [c for c in static_checks(task) if not c.ok]
    assert failed == []


@pytest.mark.parametrize("task", TASKS, ids=[t.id for t in TASKS])
def test_hidden_tests_live_outside_the_solver_tree(task):
    assert not task.hidden_tests.is_relative_to(task.base)
    assert not list(task.base.rglob("test_fail_to_pass.py"))
    assert "hidden_tests" not in task.prompt()


@pytest.mark.parametrize("task", TASKS, ids=[t.id for t in TASKS])
def test_gold_patch_is_multi_file_and_source_only(task):
    files = changed_files(task.gold_patch.read_text())
    source = [f for f in files if f.startswith("jmespath/")]
    assert len(source) >= 2, files
    assert not any(f.startswith("tests/") for f in files)


@pytest.mark.parametrize("task", TASKS, ids=[t.id for t in TASKS])
def test_task_was_verified(task):
    record = json.loads((task.root / "verification.json").read_text())
    assert record["ok"] is True
    assert record["task_id"] == task.id
    assert record["mutants"], "every task ships at least one mutant"
    assert all(m["rejected"] for m in record["mutants"].values())
