"""Task definitions: what the solver sees, what stays hidden, and how to grade.

A task directory holds:

    task.toml        metadata (id, kind, base tree, source dirs, timeout)
    task.md          the only text the solver is given
    gold.patch       a reference solution (unified diff against the base tree)
    rubric.md        how to judge the qualities tests cannot see
    Dockerfile       the environment the tests run in
    hidden_tests/    tests the solver never sees
        test_fail_to_pass.py   must fail on the base tree, pass with the gold patch
        test_pass_to_pass.py   must pass on both (regression guards)
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"

FAIL_TO_PASS_FILE = "test_fail_to_pass.py"
PASS_TO_PASS_FILE = "test_pass_to_pass.py"
VISIBLE_TESTS_DIR = "tests"
HIDDEN_TESTS_DIR = "hidden_tests"


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    title: str
    root: Path
    base: Path
    source_dirs: tuple[str, ...]
    timeout_seconds: int

    @property
    def task_md(self) -> Path:
        return self.root / "task.md"

    @property
    def gold_patch(self) -> Path:
        return self.root / "gold.patch"

    @property
    def rubric(self) -> Path:
        return self.root / "rubric.md"

    @property
    def dockerfile(self) -> Path:
        return self.root / "Dockerfile"

    @property
    def hidden_tests(self) -> Path:
        return self.root / HIDDEN_TESTS_DIR

    @property
    def image(self) -> str:
        return f"htt-{self.id}:py313"

    def prompt(self) -> str:
        return self.task_md.read_text(encoding="utf-8")


def load_task(path_or_id: str | Path, tasks_dir: Path = TASKS_DIR) -> Task:
    """Load a task by id (a folder under tasks/) or by its directory path."""
    root = Path(path_or_id)
    if not (root / "task.toml").exists():
        root = tasks_dir / str(path_or_id)
    meta_path = root / "task.toml"
    if not meta_path.exists():
        raise FileNotFoundError(f"no task.toml for task {path_or_id!r} (looked in {root})")
    meta = tomllib.loads(meta_path.read_text(encoding="utf-8"))
    base = (root / meta["base"]).resolve()
    if not base.is_dir():
        raise FileNotFoundError(f"task {meta['id']!r}: base tree {base} does not exist")
    return Task(
        id=meta["id"],
        kind=meta["kind"],
        title=meta["title"],
        root=root.resolve(),
        base=base,
        source_dirs=tuple(meta["source_dirs"]),
        timeout_seconds=int(meta.get("timeout_seconds", 120)),
    )


def list_tasks(tasks_dir: Path = TASKS_DIR) -> list[Task]:
    return [load_task(p) for p in sorted(tasks_dir.iterdir()) if (p / "task.toml").exists()]
