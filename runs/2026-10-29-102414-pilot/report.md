# Run report: 2026-10-29T10:24:14Z

- Solver: `claude`, model `claude-sonnet-5-5`, effort `medium`
- Test runner: `docker` (isolated container, --network none)
- Harness commit: `3aa3198`
- Limits per attempt: 30 model calls, 16000 output tokens per call, 1,500,000 total tokens, $0.9
- Finished: 2026-10-29T10:24:35Z
- Note: Pilot before the full run. Harness code was the same as commit 49a9957 but not yet committed (the recorded commit is the one before it). Hidden tests were reformatted by ruff afterwards; their content did not change.

## Results by task

| Task | Kind | Resolved | Pass rate | Mean fail-to-pass passed | Mean cost | Mean turns | Mean test runs | Stops |
|---|---|---|---|---|---|---|---|---|
| mixed-type-ordering | bugfix | 1/1 | 100% | 100% | $0.056 | 4.0 | 1.0 | end_turn x1 |

**Total:** 1/1 graded attempts resolved. Spend $0.06 (all attempts). Tokens: 10 input, 13,440 cache write, 20,842 cache read, 1,787 output, over 4 model calls. Solver wall time 0.3 min.

## Attempts

| Attempt | Resolved | Fail-to-pass | Pass-to-pass | Visible | Stop | Turns | Test runs | Cost | Lines +/- | Flags |
|---|---|---|---|---|---|---|---|---|---|---|
| [mixed-type-ordering #1](trajectories/mixed-type-ordering-01.json) | yes | 24/24 | 34/34 | 991/992 (1 skipped) | end_turn | 4 | 1 | $0.056 | +12/-2 | - |

## Hidden tests that failed most often
