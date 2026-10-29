"""The Claude tool-use loop, driven by a scripted fake client (no API calls)."""

from types import SimpleNamespace

import pytest

from htt.pricing import Usage, cost_usd
from htt.sandbox import Sandbox
from htt.solver import ClaudeSolver, SolveConfig
from htt.workspace import materialize
from tests.test_sandbox import RecordingRunner


def text(t):
    return SimpleNamespace(type="text", text=t)


def thinking(t):
    return SimpleNamespace(type="thinking", thinking=t, signature="sig")


def tool(name, tool_input, tool_id):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=tool_id)


def response(blocks, stop, usage=None):
    usage = usage or SimpleNamespace(
        input_tokens=10,
        output_tokens=20,
        cache_creation_input_tokens=100,
        cache_read_input_tokens=1000,
    )
    return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage)


class FakeMessages:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    def create(self, **kwargs):
        # Copy the message list: the loop appends to it after each call.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, script):
        self.messages = FakeMessages(script)


@pytest.fixture
def sandbox(toy_task, tmp_path):
    return Sandbox(materialize(toy_task, tmp_path / "work"), toy_task, RecordingRunner())


def solve(toy_task, sandbox, script, **config):
    client = FakeClient(script)
    outcome = ClaudeSolver(SolveConfig(**config), client=client).solve(toy_task, sandbox)
    return outcome, client.messages.requests


def test_happy_path_runs_tools_and_stops_on_end_turn(toy_task, sandbox):
    script = [
        response(
            [thinking("look first"), tool("read_file", {"path": "toylib/stats.py"}, "t1")],
            "tool_use",
        ),
        response(
            [
                tool(
                    "edit_file",
                    {
                        "path": "toylib/stats.py",
                        "old_text": "    return sum",
                        "new_text": "    if not values:\n        return None\n    return sum",
                    },
                    "t2",
                ),
                tool("run_visible_tests", {}, "t3"),
            ],
            "tool_use",
        ),
        response([text("Fixed mean() for empty input.")], "end_turn"),
    ]
    outcome, requests = solve(toy_task, sandbox, script)
    assert outcome.stop == "end_turn"
    assert outcome.turns == 3
    assert outcome.final_text == "Fixed mean() for empty input."
    assert "return None" in (sandbox.root / "toylib" / "stats.py").read_text()
    assert sandbox.test_runs == 1
    # All results of one assistant turn go back in a single user message.
    second_turn_results = requests[2]["messages"][-1]
    assert second_turn_results["role"] == "user"
    assert [r["tool_use_id"] for r in second_turn_results["content"]] == ["t2", "t3"]
    # Usage is summed across calls and priced.
    assert outcome.usage.calls == 3
    assert outcome.usage.output_tokens == 60
    assert outcome.cost_usd == pytest.approx(cost_usd(outcome.usage, "claude-sonnet-5-5"))
    # The trajectory keeps thinking summaries, tool inputs and results.
    first = outcome.trajectory[0]
    assert first["blocks"][0] == {"type": "thinking", "thinking": "look first"}
    assert outcome.trajectory[1]["results"][0]["name"] == "read_file"


def test_request_shape(toy_task, sandbox):
    _, requests = solve(toy_task, sandbox, [response([text("done")], "end_turn")])
    (req,) = requests
    assert req["model"] == "claude-sonnet-5-5"
    assert req["output_config"] == {"effort": "medium"}
    assert req["thinking"]["type"] == "adaptive"
    assert req["cache_control"] == {"type": "ephemeral"}
    assert req["max_tokens"] == 16000
    assert "tool_choice" not in req  # forced tool use is rejected on this model
    assert sorted(t["name"] for t in req["tools"]) == [
        "edit_file",
        "list_files",
        "read_file",
        "run_visible_tests",
        "write_file",
    ]
    assert req["messages"][0] == {"role": "user", "content": toy_task.prompt()}


def test_escape_attempt_comes_back_as_tool_error(toy_task, sandbox):
    script = [
        response([tool("read_file", {"path": "../../../etc/passwd"}, "t1")], "tool_use"),
        response([text("ok")], "end_turn"),
    ]
    _, requests = solve(toy_task, sandbox, script)
    (result,) = requests[1]["messages"][-1]["content"]
    assert result["is_error"] is True
    assert "escapes" in result["content"]


def test_max_turns_stops_the_attempt(toy_task, sandbox):
    script = [response([tool("list_files", {}, f"t{i}")], "tool_use") for i in range(5)]
    outcome, requests = solve(toy_task, sandbox, script, max_turns=3)
    assert outcome.stop == "max_turns"
    assert outcome.turns == 3
    assert len(requests) == 3


def test_cost_limit_stops_before_the_next_call(toy_task, sandbox):
    expensive = SimpleNamespace(
        input_tokens=0,
        output_tokens=200_000,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    script = [response([tool("list_files", {}, "t1")], "tool_use", usage=expensive)] * 3
    outcome, requests = solve(toy_task, sandbox, script, max_cost_usd=1.0)
    assert outcome.stop == "cost_limit"
    assert len(requests) == 1  # $2.00 spent after one call, so no second call


def test_token_limit_stops_the_attempt(toy_task, sandbox):
    script = [response([tool("list_files", {}, f"t{i}")], "tool_use") for i in range(4)]
    outcome, requests = solve(toy_task, sandbox, script, max_total_tokens=2000)
    assert outcome.stop == "token_limit"
    assert len(requests) == 2  # 1,130 tokens per call


def test_refusal_ends_the_attempt(toy_task, sandbox):
    outcome, _ = solve(toy_task, sandbox, [response([], "refusal")])
    assert outcome.stop == "refusal"


def test_truncated_tool_call_is_not_executed(toy_task, sandbox):
    script = [
        response(
            [tool("write_file", {"path": "toylib/stats.py", "content": "BROKEN"}, "t1")],
            "max_tokens",
        ),
        response([text("done")], "end_turn"),
    ]
    _, requests = solve(toy_task, sandbox, script)
    assert "BROKEN" not in (sandbox.root / "toylib" / "stats.py").read_text()
    (result,) = requests[1]["messages"][-1]["content"]
    assert result["is_error"] is True


def test_api_error_is_recorded(toy_task, sandbox):
    outcome, _ = solve(toy_task, sandbox, [RuntimeError("overloaded")])
    assert outcome.stop.startswith("api_error: RuntimeError")
    assert outcome.turns == 0


def test_usage_accounting_handles_missing_cache_fields():
    usage = Usage()
    usage.add(
        SimpleNamespace(
            input_tokens=1_000_000,
            output_tokens=100_000,
            cache_creation_input_tokens=None,
            cache_read_input_tokens=None,
        )
    )
    assert usage.total_tokens == 1_100_000
    assert cost_usd(usage, "claude-sonnet-5-5") == pytest.approx(2.0 + 1.0)
