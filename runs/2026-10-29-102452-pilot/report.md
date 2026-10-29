# Run report: 2026-10-29T10:24:52Z

- Solver: `claude`, model `claude-sonnet-5-5`, effort `medium`
- Test runner: `docker` (isolated container, --network none)
- Harness commit: `3aa3198`
- Limits per attempt: 30 model calls, 16000 output tokens per call, 1,500,000 total tokens, $0.9
- Finished: 2026-10-29T10:26:17Z
- Note: Pilot before the full run. Harness code was the same as commit 49a9957 but not yet committed (the recorded commit is the one before it). Hidden tests were reformatted by ruff afterwards; their content did not change.

## Results by task

| Task | Kind | Resolved | Pass rate | Mean fail-to-pass passed | Mean cost | Mean turns | Mean test runs | Added tests | Calls to unknown tools | Stops |
|---|---|---|---|---|---|---|---|---|---|---|
| let-expressions | feature | 1/1 | 100% | 100% | $0.189 | 9.0 | 2.0 | 0/1 | 0 | end_turn x1 |
| types-module | refactor | 1/1 | 100% | 100% | $0.077 | 5.0 | 1.0 | 0/1 | 1 | end_turn x1 |

**Total:** 2/2 graded attempts resolved. Spend $0.27 (all attempts). Tokens: 32 input, 51,097 cache write, 236,464 cache read, 9,053 output, over 14 model calls. Solver wall time 1.3 min.

## Attempts

| Attempt | Resolved | Fail-to-pass | Pass-to-pass | Visible | Stop | Turns | Test runs | Cost | Lines +/- | Flags |
|---|---|---|---|---|---|---|---|---|---|---|
| [let-expressions #1](trajectories/let-expressions-01.json) | yes | 35/35 | 29/29 | 991/992 (1 skipped) | end_turn | 9 | 2 | $0.189 | +93/-11 | no_tests_added, no_changelog |
| [types-module #1](trajectories/types-module-01.json) | yes | 41/41 | 756/756 | 991/992 (1 skipped) | end_turn | 5 | 1 | $0.077 | +57/-56 | no_tests_added, no_changelog |

## Hidden tests that failed most often
