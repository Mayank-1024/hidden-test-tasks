"""Solvers. The Claude solver is a minimal manual tool-use loop.

The loop follows the Messages API tool-use contract: send the conversation
with the tool definitions; when stop_reason is "tool_use", run every tool_use
block, return all tool_result blocks in one user message, and call again. The
full assistant content (including thinking blocks) is appended unchanged.

Limits per attempt: max_turns model calls, max_output_tokens per call, and a
token and dollar ceiling across the attempt. The loop never sees hidden tests;
grading happens after it returns, in htt.attempt.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from htt.pricing import Usage, cost_usd
from htt.sandbox import TOOL_DEFINITIONS, Sandbox, summarize_input
from htt.tasks import Task
from htt.workspace import apply_patch

SYSTEM_PROMPT = """\
You are a software engineer working in a Python repository. You can only act \
through the tools you are given: list_files, read_file, write_file, edit_file \
and run_visible_tests. There is no shell and no network. All paths are \
relative to the repository root.

Work on the task in the user's message until it is done. Read the relevant \
code before you change it, keep the change focused, and run the visible test \
suite to check your work. Your result will also be graded by tests you cannot \
see, written from the task description, so make sure every requirement in it \
is handled, including edge cases it spells out. There is no one to answer \
questions: make reasonable decisions yourself. When you are finished, reply \
with a short summary of what you changed and do not call any more tools."""

TOOL_RESULT_TRAJECTORY_CHARS = 4000


@dataclass
class SolveConfig:
    model: str = "claude-sonnet-5-5"
    effort: str = "medium"
    max_turns: int = 30
    max_output_tokens: int = 16000
    max_total_tokens: int = 1_500_000
    max_cost_usd: float = 0.90


@dataclass
class SolveOutcome:
    stop: str
    turns: int = 0
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    final_text: str = ""
    trajectory: list[dict] = field(default_factory=list)
    model: str = ""


class Solver(Protocol):
    name: str

    def solve(self, task: Task, sandbox: Sandbox) -> SolveOutcome: ...


class NoopSolver:
    """Changes nothing. Every attempt must come out unresolved."""

    name = "noop"

    def solve(self, task: Task, sandbox: Sandbox) -> SolveOutcome:
        return SolveOutcome(stop="end_turn", final_text="(no changes)", model="noop")


class GoldPatchSolver:
    """Applies the task's gold patch. Every attempt must come out resolved."""

    name = "gold"

    def solve(self, task: Task, sandbox: Sandbox) -> SolveOutcome:
        apply_patch(task.gold_patch, sandbox.root)
        return SolveOutcome(stop="end_turn", final_text="(applied gold.patch)", model="gold")


def _block_to_dict(block: Any) -> dict:
    kind = getattr(block, "type", "unknown")
    if kind == "text":
        return {"type": "text", "text": block.text}
    if kind == "thinking":
        return {"type": "thinking", "thinking": getattr(block, "thinking", "") or ""}
    if kind == "redacted_thinking":
        return {"type": "redacted_thinking"}
    if kind == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": kind}


def _usage_dict(usage: Any) -> dict:
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens")
    return {k: getattr(usage, k, 0) or 0 for k in keys}


class ClaudeSolver:
    name = "claude"

    def __init__(self, config: SolveConfig, client: Any = None):
        self.config = config
        if client is None:
            import anthropic

            # SDK retries cover 429/5xx/connection errors with backoff.
            client = anthropic.Anthropic(max_retries=4, timeout=600.0)
        self.client = client

    def _request(self, messages: list[dict]) -> Any:
        return self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_output_tokens,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": self.config.effort},
            # Automatic prompt caching: the cache breakpoint moves to the end
            # of the conversation on every call, so each turn re-reads the
            # previous turns from cache instead of paying full input price.
            cache_control={"type": "ephemeral"},
        )

    def solve(self, task: Task, sandbox: Sandbox) -> SolveOutcome:
        cfg = self.config
        out = SolveOutcome(stop="max_turns", model=cfg.model)
        messages: list[dict] = [{"role": "user", "content": task.prompt()}]
        started = time.monotonic()

        for turn in range(1, cfg.max_turns + 1):
            if out.cost_usd >= cfg.max_cost_usd:
                out.stop = "cost_limit"
                break
            if out.usage.total_tokens >= cfg.max_total_tokens:
                out.stop = "token_limit"
                break
            try:
                response = self._request(messages)
            except Exception as e:  # noqa: BLE001 - recorded, attempt ends
                out.stop = f"api_error: {type(e).__name__}: {str(e)[:300]}"
                break

            out.turns = turn
            out.usage.add(response.usage)
            out.cost_usd = cost_usd(out.usage, cfg.model)
            blocks = [_block_to_dict(b) for b in response.content]
            out.trajectory.append({
                "turn": turn,
                "role": "assistant",
                "stop_reason": response.stop_reason,
                "usage": _usage_dict(response.usage),
                "blocks": blocks,
            })
            messages.append({"role": "assistant", "content": response.content})
            tool_uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]

            if response.stop_reason not in ("tool_use", "max_tokens") or (
                response.stop_reason == "tool_use" and not tool_uses
            ):
                # end_turn (done), refusal, pause_turn, stop_sequence: the attempt ends.
                out.stop = response.stop_reason or "unknown"
                out.final_text = "\n".join(b["text"] for b in blocks if b["type"] == "text")
                break

            if response.stop_reason == "max_tokens":
                if not tool_uses:
                    messages.append({"role": "user", "content": (
                        "Your last response hit the output token limit. Continue, and keep "
                        "each tool call small (edit_file instead of rewriting large files).")})
                    out.trajectory.append({"turn": turn, "role": "harness",
                                           "note": "max_tokens without tool calls"})
                    continue
                # A truncated tool call is never executed.
                results = [{
                    "type": "tool_result", "tool_use_id": b.id, "is_error": True,
                    "content": "This tool call was cut off by the output token limit and was "
                               "not run. Retry with a smaller edit.",
                } for b in tool_uses]
                messages.append({"role": "user", "content": results})
                out.trajectory.append({"turn": turn, "role": "tool", "results": [
                    {"name": b.name, "is_error": True, "content": "truncated; not run"}
                    for b in tool_uses]})
                continue

            results, traj = [], []
            for b in tool_uses:
                content, is_error = sandbox.call(b.name, b.input)
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": content, "is_error": is_error})
                traj.append({
                    "name": b.name,
                    "input": summarize_input(b.input),
                    "is_error": is_error,
                    "content": content[:TOOL_RESULT_TRAJECTORY_CHARS],
                })
            messages.append({"role": "user", "content": results})
            out.trajectory.append({"turn": turn, "role": "tool", "results": traj})

        out.elapsed_s = round(time.monotonic() - started, 1)
        return out


def make_solver(kind: str, config: SolveConfig | None = None, client: Any = None) -> Solver:
    if kind == "claude":
        return ClaudeSolver(config or SolveConfig(), client=client)
    if kind == "gold":
        return GoldPatchSolver()
    if kind == "noop":
        return NoopSolver()
    raise ValueError(f"unknown solver {kind!r}")
