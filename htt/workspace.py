"""Build working trees: the solver's copy, gold-patched copies and grading trees."""

from __future__ import annotations

import difflib
import os
import shutil
import subprocess
from pathlib import Path

from htt.tasks import HIDDEN_TESTS_DIR, VISIBLE_TESTS_DIR, Task

IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".git", ".ruff_cache"}


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in IGNORED_NAMES or n.endswith(".pyc")}


def copy_tree(src: Path, dest: Path) -> Path:
    shutil.copytree(src, dest, ignore=_ignore, symlinks=False)
    return dest


def materialize(task: Task, dest: Path) -> Path:
    """Copy the task's base tree to ``dest``. This is what the solver works on."""
    return copy_tree(task.base, dest)


class PatchError(RuntimeError):
    pass


def apply_patch(patch: Path | str, tree: Path) -> None:
    """Apply a unified diff (git format, a/ b/ prefixes) to ``tree``."""
    text = patch.read_text(encoding="utf-8") if isinstance(patch, Path) else patch
    if not text.strip():
        return
    # --unsafe-paths is NOT used, so git apply refuses paths that leave the
    # tree. The ceiling stops git from finding an enclosing repository.
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(tree.resolve().parent)}
    proc = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        input=text,
        cwd=tree,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise PatchError(proc.stderr.strip() or "git apply failed")


def _text_files(root: Path) -> dict[str, Path]:
    files = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in IGNORED_NAMES for part in rel.parts) or path.suffix == ".pyc":
            continue
        if path.is_file():
            files[rel.as_posix()] = path
    return files


def _read_lines(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return None


def diff_trees(before: Path, after: Path) -> str:
    """Unified diff of every text file that differs, in git's a/ b/ format."""
    old, new = _text_files(before), _text_files(after)
    chunks: list[str] = []
    for rel in sorted(set(old) | set(new)):
        a = _read_lines(old[rel]) if rel in old else []
        b = _read_lines(new[rel]) if rel in new else []
        if a is None or b is None:
            if rel not in old or rel not in new or old[rel].read_bytes() != new[rel].read_bytes():
                chunks.append(f"Binary file {rel} differs\n")
            continue
        if a == b:
            continue
        header = f"diff --git a/{rel} b/{rel}\n"
        if rel not in old:
            header += "new file mode 100644\n"
        elif rel not in new:
            header += "deleted file mode 100644\n"
        lines = list(
            difflib.unified_diff(
                a,
                b,
                fromfile=f"a/{rel}" if rel in old else "/dev/null",
                tofile=f"b/{rel}" if rel in new else "/dev/null",
            )
        )
        # difflib leaves the last line without "\n" if the file has none.
        body = "".join(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in lines
        )
        chunks.append(header + body)
    return "".join(chunks)


def changed_files(diff: str) -> list[str]:
    return [line.split(" b/", 1)[1] for line in diff.splitlines() if line.startswith("diff --git ")]


def build_grading_tree(task: Task, solved: Path, dest: Path) -> Path:
    """A tree that combines the solver's source with pristine tests.

    Only ``task.source_dirs`` are taken from the solver. Visible tests, config
    files and everything else come from the base tree, so editing or deleting
    tests (or adding a conftest.py) cannot change the grade. Hidden tests are
    added last.
    """
    copy_tree(task.base, dest)
    for name in task.source_dirs:
        target = dest / name
        if target.exists():
            shutil.rmtree(target)
        if (solved / name).is_dir():
            copy_tree(solved / name, target)
    if not (dest / VISIBLE_TESTS_DIR).is_dir():
        raise FileNotFoundError(f"base tree of {task.id} has no {VISIBLE_TESTS_DIR}/ directory")
    copy_tree(task.hidden_tests, dest / HIDDEN_TESTS_DIR)
    return dest
