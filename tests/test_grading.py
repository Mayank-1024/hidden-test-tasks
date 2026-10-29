"""Junit parsing, grading rules and the grading tree."""

from htt.grading import grade_run, grade_tree
from htt.runner import PytestRun, classify_test, parse_junit
from htt.workspace import build_grading_tree, materialize

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest">
  <testcase classname="tests.test_stats" name="test_mean" time="0.001"/>
  <testcase classname="tests.test_stats" name="test_skip" time="0.0">
    <skipped message="skip"/></testcase>
  <testcase classname="hidden_tests.test_fail_to_pass" name="test_a[x-1]" time="0.0">
    <failure message="assert">trace</failure></testcase>
  <testcase classname="hidden_tests.test_pass_to_pass" name="test_b" time="0.0">
    <error message="fixture">trace</error></testcase>
  <testcase classname="" name="hidden_tests.test_fail_to_pass" time="0.0">
    <error message="collection failure">ImportError</error></testcase>
</testsuite></testsuites>"""


def test_parse_junit_outcomes():
    cases = parse_junit(JUNIT)
    assert cases == {
        "tests.test_stats::test_mean": "passed",
        "tests.test_stats::test_skip": "skipped",
        "hidden_tests.test_fail_to_pass::test_a[x-1]": "failed",
        "hidden_tests.test_pass_to_pass::test_b": "error",
        "hidden_tests.test_fail_to_pass::<collection>": "error",
    }


def test_groups():
    assert classify_test("tests.test_stats::test_mean") == "visible"
    assert classify_test("tests.unit.test_x.TestY::test_z") == "visible"
    assert classify_test("hidden_tests.test_fail_to_pass::t") == "fail_to_pass"
    assert classify_test("hidden_tests.test_pass_to_pass::t") == "pass_to_pass"
    assert classify_test("hidden_tests.test_fail_to_pass::<collection>") == "fail_to_pass"
    assert classify_test("other.module::t") == "other"


def run(cases, timed_out=False):
    return PytestRun(returncode=0, output="", duration_s=0.1, timed_out=timed_out, cases=cases)


ALL_PASS = {
    "tests.t::a": "passed",
    "tests.t::skipped": "skipped",
    "hidden_tests.test_fail_to_pass::f": "passed",
    "hidden_tests.test_pass_to_pass::p": "passed",
}


def test_resolved_requires_every_group():
    assert grade_run(run(ALL_PASS)).resolved
    for key, outcome in [
        ("hidden_tests.test_fail_to_pass::f", "failed"),
        ("hidden_tests.test_pass_to_pass::p", "error"),
        ("tests.t::a", "failed"),
    ]:
        assert not grade_run(run({**ALL_PASS, key: outcome})).resolved, key


def test_unresolved_when_nothing_ran_or_timed_out():
    assert not grade_run(run({})).resolved
    assert not grade_run(run(ALL_PASS, timed_out=True)).resolved
    no_f2p = {k: v for k, v in ALL_PASS.items() if "fail_to_pass" not in k}
    assert not grade_run(run(no_f2p)).resolved


def test_missing_expected_hidden_test_is_unresolved():
    expected = {"hidden_tests.test_fail_to_pass::f", "hidden_tests.test_fail_to_pass::g"}
    grade = grade_run(run(ALL_PASS), expected=expected)
    assert not grade.resolved
    assert grade.missing == ["hidden_tests.test_fail_to_pass::g"]


def test_grading_tree_ignores_solver_test_edits(toy_task, tmp_path):
    solved = materialize(toy_task, tmp_path / "solved")
    (solved / "tests" / "test_stats.py").write_text("def test_mean():\n    assert True\n")
    (solved / "tests" / "test_new.py").write_text("def test_x():\n    assert True\n")
    (solved / "conftest.py").write_text("import pytest\n")
    (solved / "toylib" / "stats.py").write_text("def mean(v):\n    return None\n")
    tree = build_grading_tree(toy_task, solved, tmp_path / "grade")
    assert (tree / "tests" / "test_stats.py").read_text() == (
        toy_task.base / "tests" / "test_stats.py"
    ).read_text()
    assert not (tree / "tests" / "test_new.py").exists()
    assert not (tree / "conftest.py").exists()
    assert (tree / "toylib" / "stats.py").read_text() == "def mean(v):\n    return None\n"
    assert (tree / "hidden_tests" / "test_fail_to_pass.py").exists()


def test_deleting_visible_tests_does_not_help(toy_task, local_runner, tmp_path):
    solved = materialize(toy_task, tmp_path / "solved")
    for path in (solved / "tests").glob("test_*.py"):
        path.unlink()
    grade = grade_tree(toy_task, solved, local_runner)
    assert len(grade.visible) == 2  # pristine tests still ran
    assert not grade.resolved  # and the bug is still there
