"""Path confinement and tool behavior for the solver sandbox."""

import os
from pathlib import Path

import pytest

from htt.runner import PytestRun
from htt.sandbox import TOOL_DEFINITIONS, Sandbox, ToolError
from htt.workspace import materialize


class RecordingRunner:
    name = "recording"
    isolated = False

    def __init__(self):
        self.calls = []

    def prepare(self, task):
        pass

    def run_pytest(self, task, tree, paths, timeout_s):
        self.calls.append((Path(tree), list(paths), timeout_s))
        return PytestRun(returncode=0, output="1 passed in 0.01s", duration_s=0.01)


@pytest.fixture
def sandbox(toy_task, tmp_path):
    work = materialize(toy_task, tmp_path / "work")
    return Sandbox(work, toy_task, RecordingRunner())


ESCAPES = [
    "../outside.txt",
    "../../etc/passwd",
    "toylib/../../outside.txt",
    "/etc/passwd",
    "~/.ssh/id_rsa",
    "toylib/\x00stats.py",
    "",
    "   ",
    ".git/config",
    "toylib/__pycache__/x.pyc",
]


@pytest.mark.parametrize("path", ESCAPES)
def test_read_escape_attempts_are_rejected(sandbox, path):
    content, is_error = sandbox.call("read_file", {"path": path})
    assert is_error
    assert content.startswith("error:")


@pytest.mark.parametrize("path", ESCAPES)
def test_write_escape_attempts_are_rejected(sandbox, path, tmp_path):
    content, is_error = sandbox.call("write_file", {"path": path, "content": "x"})
    assert is_error
    assert not (tmp_path / "outside.txt").exists()


def test_absolute_path_inside_root_is_still_rejected(sandbox):
    # Only relative paths are accepted, even if the absolute path is inside.
    absolute = str(sandbox.root / "toylib" / "stats.py")
    _, is_error = sandbox.call("read_file", {"path": absolute})
    assert is_error


def test_sibling_directory_with_shared_prefix_is_rejected(sandbox):
    # A string prefix check would accept "<root>-evil"; component checks do not.
    sibling = sandbox.root.parent / (sandbox.root.name + "-evil")
    sibling.mkdir()
    (sibling / "secret.txt").write_text("top-secret-value")
    content, is_error = sandbox.call(
        "read_file", {"path": f"../{sandbox.root.name}-evil/secret.txt"}
    )
    assert is_error
    assert "top-secret-value" not in content


def test_symlink_pointing_outside_is_rejected(sandbox, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("do not read")
    os.symlink(outside, sandbox.root / "link.txt")
    content, is_error = sandbox.call("read_file", {"path": "link.txt"})
    assert is_error and "escapes" in content
    _, is_error = sandbox.call("write_file", {"path": "link.txt", "content": "pwned"})
    assert is_error
    assert outside.read_text() == "do not read"


def test_symlinked_directory_pointing_outside_is_rejected(sandbox, tmp_path):
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    os.symlink(outside_dir, sandbox.root / "linkdir")
    _, is_error = sandbox.call("write_file", {"path": "linkdir/new.py", "content": "x"})
    assert is_error
    assert not (outside_dir / "new.py").exists()


def test_resolve_raises_tool_error_directly(sandbox):
    with pytest.raises(ToolError):
        sandbox.resolve("../x")
    assert sandbox.resolve("toylib/stats.py") == sandbox.root / "toylib" / "stats.py"


def test_read_file_numbers_lines_and_supports_ranges(sandbox):
    content, is_error = sandbox.call("read_file", {"path": "toylib/stats.py"})
    assert not is_error
    assert content.splitlines()[0].strip() == "1  def mean(values):"
    content, _ = sandbox.call("read_file", {"path": "toylib/stats.py", "start_line": 2})
    assert "def mean" not in content and "return sum" in content


def test_list_files_hides_caches(sandbox):
    (sandbox.root / "toylib" / "__pycache__").mkdir()
    (sandbox.root / "toylib" / "__pycache__" / "stats.cpython-313.pyc").write_bytes(b"\0")
    content, is_error = sandbox.call("list_files", {})
    assert not is_error
    assert "toylib/stats.py" in content.splitlines()
    assert "__pycache__" not in content


def test_write_file_creates_directories_inside_root(sandbox):
    content, is_error = sandbox.call(
        "write_file", {"path": "toylib/sub/new.py", "content": "X = 1\n"}
    )
    assert not is_error, content
    assert (sandbox.root / "toylib" / "sub" / "new.py").read_text() == "X = 1\n"
    assert sandbox.writes == ["toylib/sub/new.py"]


def test_edit_file_requires_a_unique_match(sandbox):
    path = {"path": "toylib/stats.py"}
    _, is_error = sandbox.call("edit_file", {**path, "old_text": "nope", "new_text": "x"})
    assert is_error
    (sandbox.root / "toylib" / "stats.py").write_text("a\na\n")
    content, is_error = sandbox.call("edit_file", {**path, "old_text": "a", "new_text": "b"})
    assert is_error and "2 times" in content
    content, is_error = sandbox.call("edit_file", {**path, "old_text": "a\na", "new_text": "b\nc"})
    assert not is_error
    assert (sandbox.root / "toylib" / "stats.py").read_text() == "b\nc\n"


def test_run_visible_tests_uses_a_fixed_command(sandbox):
    content, is_error = sandbox.call("run_visible_tests", {})
    assert not is_error and "1 passed" in content
    ((tree, paths, timeout),) = sandbox.runner.calls
    assert tree == sandbox.root
    assert paths == ["tests"]
    assert timeout == sandbox.task.timeout_seconds
    assert sandbox.test_runs == 1


def test_run_visible_tests_accepts_no_arguments(sandbox):
    content, is_error = sandbox.call("run_visible_tests", {"paths": ["/etc"]})
    assert is_error and "bad arguments" in content
    assert sandbox.runner.calls == []


def test_unknown_tool_and_bad_input(sandbox):
    assert sandbox.call("bash", {"command": "ls"})[1]
    assert sandbox.call("read_file", "toylib/stats.py")[1]
    assert sandbox.call("read_file", {"path": "toylib/stats.py", "mode": "rb"})[1]


def test_tool_definitions_are_exactly_the_five_tools():
    names = sorted(t["name"] for t in TOOL_DEFINITIONS)
    assert names == ["edit_file", "list_files", "read_file", "run_visible_tests", "write_file"]
    for tool in TOOL_DEFINITIONS:
        assert tool["input_schema"]["additionalProperties"] is False
