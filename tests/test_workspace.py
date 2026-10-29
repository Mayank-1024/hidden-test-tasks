"""Diffs and patches: a solver's diff must re-apply to the base tree exactly."""

import pytest

from htt.workspace import PatchError, apply_patch, changed_files, diff_trees, materialize


def test_diff_round_trips_through_git_apply(toy_task, tmp_path):
    work = materialize(toy_task, tmp_path / "work")
    (work / "toylib" / "stats.py").write_text("def mean(values):\n    return 0\n")
    (work / "toylib" / "new.py").write_text("X = 1\n")
    (work / "toylib" / "__init__.py").unlink()
    (work / "notes.txt").write_text("no trailing newline")
    diff = diff_trees(toy_task.base, work)
    assert changed_files(diff) == [
        "notes.txt",
        "toylib/__init__.py",
        "toylib/new.py",
        "toylib/stats.py",
    ]

    replay = materialize(toy_task, tmp_path / "replay")
    apply_patch(diff, replay)
    assert diff_trees(work, replay) == ""


def test_no_changes_gives_an_empty_diff(toy_task, tmp_path):
    work = materialize(toy_task, tmp_path / "work")
    assert diff_trees(toy_task.base, work) == ""


def test_caches_are_ignored(toy_task, tmp_path):
    work = materialize(toy_task, tmp_path / "work")
    (work / "toylib" / "__pycache__").mkdir()
    (work / "toylib" / "__pycache__" / "x.pyc").write_bytes(b"\0\1")
    assert diff_trees(toy_task.base, work) == ""


def test_patch_that_does_not_apply_raises(toy_task, tmp_path):
    work = materialize(toy_task, tmp_path / "work")
    bad = (
        "diff --git a/toylib/stats.py b/toylib/stats.py\n--- a/toylib/stats.py\n"
        "+++ b/toylib/stats.py\n@@ -1,1 +1,1 @@\n-nothing like this\n+x\n"
    )
    with pytest.raises(PatchError):
        apply_patch(bad, work)


def test_patch_cannot_write_outside_the_tree(toy_task, tmp_path):
    work = materialize(toy_task, tmp_path / "work")
    evil = (
        "diff --git a/../evil.txt b/../evil.txt\nnew file mode 100644\n"
        "--- /dev/null\n+++ b/../evil.txt\n@@ -0,0 +1 @@\n+pwned\n"
    )
    with pytest.raises(PatchError):
        apply_patch(evil, work)
    assert not (tmp_path / "evil.txt").exists()
