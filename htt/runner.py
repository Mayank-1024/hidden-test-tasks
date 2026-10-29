"""Run pytest in a task's environment and collect per-test results.

Two backends:

- DockerRunner (default): the task's Dockerfile image, the tree mounted
  read-only, --network none, no capabilities, memory/CPU/PID limits, a
  non-root user and a wall-clock timeout. Model-written code only ever runs
  here.
- LocalRunner: plain subprocess with the current interpreter. No isolation.
  Used for the offline test suite (which only runs code from this repo) and as
  a fallback when Docker is not running.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from htt.tasks import FAIL_TO_PASS_FILE, HIDDEN_TESTS_DIR, PASS_TO_PASS_FILE, Task

PYTEST_ARGS = ["-q", "-p", "no:cacheprovider", "--tb=short", "-o", "console_output_style=classic"]


@dataclass
class PytestRun:
    returncode: int
    output: str
    duration_s: float
    timed_out: bool = False
    # test id -> "passed" | "failed" | "error" | "skipped"
    cases: dict[str, str] = field(default_factory=dict)

    def group(self, name: str) -> dict[str, str]:
        return {k: v for k, v in self.cases.items() if classify_test(k) == name}


def classify_test(test_id: str) -> str:
    """Classify a junit test id as fail_to_pass, pass_to_pass, visible or other."""
    module = test_id.split("::", 1)[0]
    f2p = f"{HIDDEN_TESTS_DIR}.{FAIL_TO_PASS_FILE.removesuffix('.py')}"
    p2p = f"{HIDDEN_TESTS_DIR}.{PASS_TO_PASS_FILE.removesuffix('.py')}"
    if module.startswith(f2p):
        return "fail_to_pass"
    if module.startswith(p2p):
        return "pass_to_pass"
    if module.startswith("tests.") or module == "tests":
        return "visible"
    return "other"


def parse_junit(xml_text: str) -> dict[str, str]:
    cases: dict[str, str] = {}
    if not xml_text.strip():
        return cases
    root = ET.fromstring(xml_text)
    for case in root.iter("testcase"):
        classname = case.get("classname") or ""
        name = case.get("name") or ""
        # Collection errors come through with an empty classname and the
        # module path as the name.
        test_id = f"{classname}::{name}" if classname else f"{name}::<collection>"
        outcome = "passed"
        for child in case:
            if child.tag in ("failure",):
                outcome = "failed"
            elif child.tag == "error":
                outcome = "error"
            elif child.tag == "skipped":
                outcome = "skipped"
        cases[test_id] = outcome
    return cases


class Runner:
    name = "base"
    isolated = False

    def run_pytest(self, task: Task, tree: Path, paths: list[str], timeout_s: int) -> PytestRun:
        raise NotImplementedError

    def prepare(self, task: Task) -> None:
        """Make sure the environment for ``task`` exists (no-op by default)."""


def _out_dir() -> Path:
    out = Path(tempfile.mkdtemp(prefix="htt-out-"))
    out.chmod(0o777)  # the container's non-root user writes the junit file here
    return out


class LocalRunner(Runner):
    name = "local"
    isolated = False

    def __init__(self, python: str | None = None):
        self.python = python or sys.executable

    def run_pytest(self, task: Task, tree: Path, paths: list[str], timeout_s: int) -> PytestRun:
        out = _out_dir()
        junit = out / "junit.xml"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": str(tree),
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(out),
        }
        cmd = [self.python, "-m", "pytest", *PYTEST_ARGS, f"--junitxml={junit}", *paths]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=tree, env=env, capture_output=True, text=True, timeout=timeout_s
            )
            returncode, output, timed_out = proc.returncode, proc.stdout + proc.stderr, False
        except subprocess.TimeoutExpired as e:
            returncode, timed_out = -1, True
            output = _decode(e.stdout) + _decode(e.stderr) + f"\n[timed out after {timeout_s}s]"
        duration = time.monotonic() - start
        cases = parse_junit(junit.read_text(encoding="utf-8")) if junit.exists() else {}
        shutil.rmtree(out, ignore_errors=True)
        return PytestRun(returncode, output, duration, timed_out, cases)


class DockerRunner(Runner):
    name = "docker"
    isolated = True

    def __init__(self, memory: str = "1g", cpus: str = "2", pids: int = 256):
        self.memory, self.cpus, self.pids = memory, cpus, pids
        self._prepared: set[str] = set()

    def prepare(self, task: Task, rebuild: bool = False) -> None:
        if task.image in self._prepared and not rebuild:
            return
        exists = (
            subprocess.run(
                ["docker", "image", "inspect", task.image], capture_output=True, check=False
            ).returncode
            == 0
        )
        if rebuild or not exists:
            subprocess.run(
                [
                    "docker",
                    "build",
                    "-q",
                    "-t",
                    task.image,
                    "-f",
                    str(task.dockerfile),
                    str(task.root),
                ],
                check=True,
                capture_output=True,
            )
        self._prepared.add(task.image)

    def command(self, task: Task, tree: Path, out: Path, paths: list[str], name: str) -> list[str]:
        return [
            "docker", "run", "--rm", "--name", name,
            "--network", "none",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m,mode=1777",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--memory", self.memory, "--cpus", self.cpus, "--pids-limit", str(self.pids),
            "-e", "PYTHONPATH=/work", "-e", "HOME=/tmp",
            "-v", f"{tree.resolve()}:/work:ro",
            "-v", f"{out.resolve()}:/out:rw",
            "-w", "/work",
            task.image,
            "python", "-m", "pytest", *PYTEST_ARGS, "--junitxml=/out/junit.xml", *paths,
        ]  # fmt: skip

    def run_pytest(self, task: Task, tree: Path, paths: list[str], timeout_s: int) -> PytestRun:
        self.prepare(task)
        out = _out_dir()
        name = f"htt-{uuid.uuid4().hex[:12]}"
        cmd = self.command(task, tree, out, paths, name)
        start = time.monotonic()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
            returncode, output, timed_out = proc.returncode, proc.stdout + proc.stderr, False
        except subprocess.TimeoutExpired as e:
            subprocess.run(["docker", "kill", name], capture_output=True, check=False)
            returncode, timed_out = -1, True
            output = _decode(e.stdout) + _decode(e.stderr) + f"\n[timed out after {timeout_s}s]"
        duration = time.monotonic() - start
        junit = out / "junit.xml"
        cases = parse_junit(junit.read_text(encoding="utf-8")) if junit.exists() else {}
        shutil.rmtree(out, ignore_errors=True)
        return PytestRun(returncode, output, duration, timed_out, cases)


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    return data if isinstance(data, str) else data.decode("utf-8", "replace")


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    proc = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return proc.returncode == 0


def make_runner(kind: str = "auto") -> Runner:
    if kind == "docker":
        return DockerRunner()
    if kind == "local":
        return LocalRunner()
    if docker_available():
        return DockerRunner()
    print(
        "warning: Docker is not running; falling back to LocalRunner (no isolation)",
        file=sys.stderr,
    )
    return LocalRunner()
