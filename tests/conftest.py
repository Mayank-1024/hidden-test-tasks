import shutil
from pathlib import Path

import pytest

from htt.runner import LocalRunner
from htt.tasks import load_task

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def toy_root(tmp_path: Path) -> Path:
    """A private copy of the toy task (base tree + task dir) that tests may break."""
    root = tmp_path / "toy"
    shutil.copytree(FIXTURES / "toy_task", root)
    return root


@pytest.fixture
def toy_task(toy_root: Path):
    return load_task(toy_root / "task")


@pytest.fixture
def local_runner() -> LocalRunner:
    # Runs only the toy task's own code, with this interpreter.
    return LocalRunner()
