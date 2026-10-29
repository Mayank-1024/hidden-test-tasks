"""The solver's tools, confined to one temporary working copy.

The model gets five tools and nothing else: read_file, list_files,
write_file, edit_file and run_visible_tests. There is no shell. Every path is
resolved against the working copy root and rejected if it lands outside it
(absolute paths, "..", symlinks, NUL bytes). run_visible_tests takes no
arguments: it runs the repository's own pytest suite with a fixed command in
the task's container (read-only mount, --network none) under a timeout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from htt.runner import Runner
from htt.tasks import VISIBLE_TESTS_DIR, Task

MAX_READ_CHARS = 60_000
MAX_WRITE_CHARS = 200_000
MAX_LIST_ENTRIES = 500
TEST_OUTPUT_CHARS = 8_000
HIDDEN_NAMES = {"__pycache__", ".pytest_cache", ".git"}


class ToolError(Exception):
    """A tool call the harness refuses. Reported to the model as is_error."""


TOOL_DEFINITIONS = [
    {
        "name": "list_files",
        "description": (
            "List files in the repository, recursively, as paths relative to the repository "
            "root. Use path to list a subdirectory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory relative to the root."}
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a text file. Returns the content with 1-based line numbers. Use start_line "
            "and end_line to read part of a long file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a text file with the given content.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Replace one exact occurrence of old_text with new_text in a file. old_text must "
            "match the file exactly (including indentation) and appear exactly once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_visible_tests",
        "description": (
            "Run the repository's test suite (python -m pytest tests) and return the summary "
            "and the tail of the output. Takes no arguments."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


@dataclass
class Sandbox:
    root: Path
    task: Task
    runner: Runner
    test_runs: int = 0
    writes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve(strict=True)

    # -- path confinement -------------------------------------------------
    def resolve(self, path: str, must_exist: bool = False) -> Path:
        if not isinstance(path, str) or path.strip() == "":
            raise ToolError("path must be a non-empty string")
        if "\x00" in path:
            raise ToolError("path contains a NUL byte")
        candidate = Path(path)
        if candidate.is_absolute() or path.startswith("~"):
            raise ToolError(f"path must be relative to the repository root: {path!r}")
        if any(part in HIDDEN_NAMES for part in candidate.parts):
            raise ToolError(f"path is not available: {path!r}")
        target = (self.root / candidate).resolve(strict=False)
        # is_relative_to compares whole path components, so a sibling such as
        # "<root>-evil" does not pass the way a string prefix check would.
        if target != self.root and not target.is_relative_to(self.root):
            raise ToolError(f"path escapes the repository: {path!r}")
        if must_exist and not target.exists():
            raise ToolError(f"no such file: {path!r}")
        return target

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix() or "."

    # -- tools ------------------------------------------------------------
    def list_files(self, path: str = ".") -> str:
        base = self.resolve(path, must_exist=True)
        if not base.is_dir():
            raise ToolError(f"not a directory: {path!r}")
        entries = []
        for p in sorted(base.rglob("*")):
            rel_parts = p.relative_to(self.root).parts
            if any(part in HIDDEN_NAMES for part in rel_parts) or p.suffix == ".pyc":
                continue
            if p.is_file():
                entries.append(self.rel(p))
        if len(entries) > MAX_LIST_ENTRIES:
            shown = entries[:MAX_LIST_ENTRIES]
            return "\n".join(shown) + f"\n... ({len(entries) - MAX_LIST_ENTRIES} more)"
        return "\n".join(entries) if entries else "(no files)"

    def read_file(self, path: str, start_line: int | None = None,
                  end_line: int | None = None) -> str:
        target = self.resolve(path, must_exist=True)
        if not target.is_file():
            raise ToolError(f"not a file: {path!r}")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ToolError(f"not a UTF-8 text file: {path!r}") from e
        lines = text.splitlines()
        start = max(1, start_line or 1)
        end = min(len(lines), end_line or len(lines))
        numbered = "\n".join(f"{i:>5}  {lines[i - 1]}" for i in range(start, end + 1))
        if len(numbered) > MAX_READ_CHARS:
            numbered = numbered[:MAX_READ_CHARS] + (
                f"\n... (truncated; {len(lines)} lines in total, use start_line/end_line)"
            )
        return numbered or "(empty file)"

    def write_file(self, path: str, content: str) -> str:
        if not isinstance(content, str):
            raise ToolError("content must be a string")
        if len(content) > MAX_WRITE_CHARS:
            raise ToolError(f"content is larger than {MAX_WRITE_CHARS} characters")
        target = self.resolve(path)
        if target.is_dir():
            raise ToolError(f"is a directory: {path!r}")
        if target.is_symlink():
            raise ToolError(f"refusing to write through a symlink: {path!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Re-check after mkdir: a parent could not have been a symlink out,
        # because resolve() already followed every existing component.
        self.resolve(path)
        target.write_text(content, encoding="utf-8")
        self.writes.append(self.rel(target))
        return f"wrote {self.rel(target)} ({len(content.splitlines())} lines)"

    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        target = self.resolve(path, must_exist=True)
        if not target.is_file():
            raise ToolError(f"not a file: {path!r}")
        if target.is_symlink():
            raise ToolError(f"refusing to edit through a symlink: {path!r}")
        if old_text == "":
            raise ToolError("old_text must not be empty")
        text = target.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count == 0:
            raise ToolError("old_text was not found in the file")
        if count > 1:
            raise ToolError(f"old_text appears {count} times; include more context")
        target.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        self.writes.append(self.rel(target))
        return f"edited {self.rel(target)}"

    def run_visible_tests(self) -> str:
        self.test_runs += 1
        run = self.runner.run_pytest(
            self.task, self.root, [VISIBLE_TESTS_DIR], self.task.timeout_seconds
        )
        output = run.output
        if len(output) > TEST_OUTPUT_CHARS:
            output = "... (earlier output truncated)\n" + output[-TEST_OUTPUT_CHARS:]
        status = "timed out" if run.timed_out else f"exit code {run.returncode}"
        return f"pytest {status}\n{output}"

    # -- dispatch ---------------------------------------------------------
    def call(self, name: str, tool_input: dict) -> tuple[str, bool]:
        """Run one tool. Returns (content, is_error)."""
        handlers = {
            "list_files": self.list_files,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "run_visible_tests": self.run_visible_tests,
        }
        handler = handlers.get(name)
        if handler is None:
            return f"unknown tool: {name}", True
        if not isinstance(tool_input, dict):
            return "tool input must be an object", True
        try:
            return handler(**tool_input), False
        except ToolError as e:
            return f"error: {e}", True
        except TypeError as e:
            return f"error: bad arguments for {name}: {e}", True
        except OSError as e:
            return f"error: {type(e).__name__}: {e}", True


def summarize_input(tool_input: dict, limit: int = 300) -> str:
    """A short, JSON-safe rendering of a tool input for trajectories."""
    text = json.dumps(tool_input, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + f"... ({len(text)} chars)"
