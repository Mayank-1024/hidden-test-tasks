"""Verification logic, on a toy task run with the local runner.

Each "broken" variant breaks the toy task in one specific way and checks that
verification names that failure.
"""

import json

from htt.tasks import load_task
from htt.verify import verify_task


def _failed(result):
    return {c.name for c in result.checks if not c.ok}


def test_toy_task_verifies(toy_task, local_runner):
    result = verify_task(toy_task, local_runner, repeat=2, write=True)
    assert result.ok, _failed(result)
    assert result.start == {"fail_to_pass": "0/2", "pass_to_pass": "1/1", "visible": "2/2"}
    assert result.gold == {"fail_to_pass": "2/2", "pass_to_pass": "1/1", "visible": "2/2"}
    assert result.mutants["returns-zero"]["rejected"] is True
    record = json.loads((toy_task.root / "verification.json").read_text())
    assert record["ok"] is True
    assert len(record["hidden_test_ids"]) == 3


def test_gold_patch_that_does_not_fix_fails(toy_root, local_runner):
    gold = toy_root / "task" / "gold.patch"
    gold.write_text(gold.read_text().replace("return None", "return 0"))
    result = verify_task(load_task(toy_root / "task"), local_runner, write=True)
    assert not result.ok
    assert "gold: every hidden test passes" in _failed(result)
    # A failed verification never writes a verification record.
    assert not (toy_root / "task" / "verification.json").exists()


def test_fail_to_pass_test_that_already_passes_fails(toy_root, local_runner):
    f2p = toy_root / "task" / "hidden_tests" / "test_fail_to_pass.py"
    f2p.write_text(f2p.read_text() + "\n\ndef test_trivial():\n    assert mean([2, 4]) == 3\n")
    result = verify_task(load_task(toy_root / "task"), local_runner, write=False)
    assert "start: every fail-to-pass test fails" in _failed(result)


def test_pass_to_pass_test_that_fails_on_start_fails(toy_root, local_runner):
    p2p = toy_root / "task" / "hidden_tests" / "test_pass_to_pass.py"
    p2p.write_text(p2p.read_text() + "\n\ndef test_needs_fix():\n    assert mean([]) is None\n")
    result = verify_task(load_task(toy_root / "task"), local_runner, write=False)
    assert "start: every pass-to-pass test passes" in _failed(result)


def test_gold_patch_that_breaks_visible_tests_fails(toy_root, local_runner):
    gold = toy_root / "task" / "gold.patch"
    gold.write_text(
        gold.read_text().replace(
            "     return sum(values) / len(values)",
            "-    return sum(values) / len(values)\n+    return sum(values) // len(values)",
        )
    )
    result = verify_task(load_task(toy_root / "task"), local_runner, write=False)
    assert "gold: visible suite still passes" in _failed(result)


def test_gold_patch_that_edits_tests_fails_static_check(toy_root, local_runner):
    gold = toy_root / "task" / "gold.patch"
    gold.write_text(
        gold.read_text() + "diff --git a/tests/test_stats.py b/tests/test_stats.py\n"
        "--- a/tests/test_stats.py\n+++ b/tests/test_stats.py\n"
        "@@ -1,3 +1,3 @@\n from toylib.stats import mean\n \n-\n+# edited\n"
    )
    result = verify_task(load_task(toy_root / "task"), local_runner, write=False)
    assert "gold patch touches only source and doc files" in _failed(result)


def test_task_md_that_quotes_the_gold_patch_fails(toy_root, local_runner):
    line = "if len(values) == 0:  # an empty sequence has no mean"
    gold = toy_root / "task" / "gold.patch"
    gold.write_text(gold.read_text().replace("if len(values) == 0:", line))
    md = toy_root / "task" / "task.md"
    md.write_text(md.read_text() + f"\nHint: `{line}`\n")
    result = verify_task(load_task(toy_root / "task"), local_runner, write=False)
    assert "task.md does not quote the gold patch" in _failed(result)
    # The gold patch itself still works; only the leak check fails.
    assert _failed(result) == {"task.md does not quote the gold patch"}


def test_task_md_that_names_a_hidden_test_fails(toy_root, local_runner):
    md = toy_root / "task" / "task.md"
    md.write_text(md.read_text() + "\nMake test_empty_returns_none pass.\n")
    result = verify_task(load_task(toy_root / "task"), local_runner, write=False)
    assert "task.md does not name hidden tests" in _failed(result)


def test_mutant_that_is_actually_correct_fails(toy_root, local_runner):
    gold = (toy_root / "task" / "gold.patch").read_text()
    (toy_root / "task" / "mutants" / "same-as-gold.patch").write_text(gold)
    result = verify_task(load_task(toy_root / "task"), local_runner, write=False)
    assert "mutant same-as-gold is rejected" in _failed(result)
    assert "mutant returns-zero is rejected" not in _failed(result)


def test_gold_patch_that_does_not_apply_fails(toy_root, local_runner):
    gold = toy_root / "task" / "gold.patch"
    gold.write_text(gold.read_text().replace("def mean(values):", "def average(values):"))
    result = verify_task(load_task(toy_root / "task"), local_runner, write=False)
    assert "gold patch applies cleanly" in _failed(result)


def test_missing_rubric_fails(toy_root, local_runner):
    (toy_root / "task" / "rubric.md").unlink()
    result = verify_task(load_task(toy_root / "task"), local_runner, write=False)
    assert "rubric.md exists" in _failed(result)
