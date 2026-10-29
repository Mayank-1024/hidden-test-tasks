"""Token accounting and cost.

Prices are USD per million tokens, from Anthropic's model price table as of
2026-10-06. A 5-minute cache write costs 1.25x the input price; a cache read
costs the listed cache-read price. Costs here are computed from the usage the
API returns, not read from a billing dashboard.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

PRICES_PER_MTOK = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.20},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20},
}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    calls: int = 0

    def add(self, usage: object) -> None:
        """Add one API response's usage (any object with the SDK's usage fields)."""
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_creation_input_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.calls += 1

    @property
    def total_tokens(self) -> int:
        return (self.input_tokens + self.output_tokens + self.cache_creation_input_tokens
                + self.cache_read_input_tokens)

    def to_dict(self) -> dict:
        return {**asdict(self), "total_tokens": self.total_tokens}


def cost_usd(usage: Usage, model: str) -> float:
    if model not in PRICES_PER_MTOK:
        raise KeyError(f"no price for model {model!r}; add it to PRICES_PER_MTOK")
    p = PRICES_PER_MTOK[model]
    return (
        usage.input_tokens * p["input"]
        + usage.output_tokens * p["output"]
        + usage.cache_creation_input_tokens * p["cache_write"]
        + usage.cache_read_input_tokens * p["cache_read"]
    ) / 1_000_000


def estimate_from_runs(runs_dir: Path, attempts_per_task: int, tasks: int) -> str:
    """Project the cost of a full run from the mean cost of recorded attempts."""
    costs: dict[str, list[float]] = {}
    for report in sorted(runs_dir.glob("*/report.json")):
        data = json.loads(report.read_text(encoding="utf-8"))
        for a in data.get("attempts", []):
            if a.get("solver") == "claude" and a.get("status") != "skipped":
                costs.setdefault(a["task_id"], []).append(a["cost_usd"])
    if not costs:
        return "no recorded Claude attempts under runs/; run a pilot first"
    lines, total = [], 0.0
    for task_id, values in sorted(costs.items()):
        mean, worst = sum(values) / len(values), max(values)
        total += mean * attempts_per_task
        lines.append(f"{task_id}: {len(values)} attempts recorded, mean ${mean:.3f}, "
                     f"max ${worst:.3f}")
    missing = tasks - len(costs)
    lines.append(f"projected for {attempts_per_task} attempts x {len(costs)} tasks: "
                 f"${total:.2f}" + (f" ({missing} tasks have no recorded attempts)"
                                    if missing > 0 else ""))
    return "\n".join(lines)
