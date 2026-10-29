# Run report: 2026-10-29T10:29:04Z

- Solver: `claude`, model `claude-sonnet-5-5`, effort `medium`
- Test runner: `docker` (isolated container, --network none)
- Harness commit: `3e485ae`
- Limits per attempt: 30 model calls, 16000 output tokens per call, 1,500,000 total tokens, $0.9
- Run budget: $4.0
- Finished: 2026-10-29T13:26:48Z
- Resumed: 2026-10-29T13:18:51Z
- Note: The API key ran out of credit during attempt let-expressions #2 (HTTP 400, 'Your credit balance is too low'). That attempt and the 11 after it ended with an API error; the harness of commit 3e485ae still graded them as unresolved and kept starting attempts. They were relabeled as status 'error' (12 attempts) by the fixed harness, which excludes them from pass rates and stops a run at the first fatal API error. Finish the run with: htt solve --resume runs/2026-10-29-102904-v1 --attempts 5.

## Results by task

| Task | Kind | Resolved | Pass rate | Mean fail-to-pass passed | Mean cost | Mean turns | Mean test runs | Added tests | Calls to unknown tools | Stops |
|---|---|---|---|---|---|---|---|---|---|---|
| let-expressions | feature | 5/5 | 100% | 100% | $0.162 | 10.0 | 1.4 | 0/5 | 8 | end_turn x5 |
| mixed-type-ordering | bugfix | 5/5 | 100% | 100% | $0.041 | 4.0 | 1.0 | 0/5 | 0 | end_turn x5 |
| types-module | refactor | 5/5 | 100% | 100% | $0.075 | 6.0 | 1.0 | 0/5 | 7 | end_turn x5 |

**Total:** 15/15 graded attempts resolved. Spend $1.39 (all attempts). Tokens: 230 input, 217,205 cache write, 1,503,267 cache read, 54,602 output, over 100 model calls. Solver wall time 9.3 min.

## Attempts

| Attempt | Resolved | Fail-to-pass | Pass-to-pass | Visible | Stop | Turns | Test runs | Cost | Lines +/- | Flags |
|---|---|---|---|---|---|---|---|---|---|---|
| [let-expressions #1](trajectories/let-expressions-01.json) | yes | 35/35 | 29/29 | 991/992 (1 skipped) | end_turn | 11 | 2 | $0.160 | +90/-7 | no_tests_added, no_changelog |
| [mixed-type-ordering #1](trajectories/mixed-type-ordering-01.json) | yes | 24/24 | 34/34 | 991/992 (1 skipped) | end_turn | 4 | 1 | $0.054 | +13/-3 | no_tests_added, no_changelog |
| [types-module #1](trajectories/types-module-01.json) | yes | 41/41 | 756/756 | 991/992 (1 skipped) | end_turn | 9 | 1 | $0.092 | +54/-55 | no_tests_added, no_changelog |
| [let-expressions #2](trajectories/let-expressions-02.json) | yes | 35/35 | 29/29 | 991/992 (1 skipped) | end_turn | 11 | 1 | $0.175 | +88/-7 | no_tests_added, no_changelog |
| [mixed-type-ordering #2](trajectories/mixed-type-ordering-02.json) | yes | 24/24 | 34/34 | 991/992 (1 skipped) | end_turn | 4 | 1 | $0.056 | +11/-8 | no_tests_added, no_changelog |
| [types-module #2](trajectories/types-module-02.json) | yes | 41/41 | 756/756 | 991/992 (1 skipped) | end_turn | 5 | 1 | $0.079 | +59/-56 | no_tests_added, no_changelog |
| [let-expressions #3](trajectories/let-expressions-03.json) | yes | 35/35 | 29/29 | 991/992 (1 skipped) | end_turn | 11 | 1 | $0.186 | +91/-11 | no_tests_added, no_changelog |
| [mixed-type-ordering #3](trajectories/mixed-type-ordering-03.json) | yes | 24/24 | 34/34 | 991/992 (1 skipped) | end_turn | 4 | 1 | $0.039 | +14/-3 | no_tests_added, no_changelog |
| [types-module #3](trajectories/types-module-03.json) | yes | 41/41 | 756/756 | 991/992 (1 skipped) | end_turn | 4 | 1 | $0.070 | +59/-55 | no_tests_added, no_changelog |
| [let-expressions #4](trajectories/let-expressions-04.json) | yes | 35/35 | 29/29 | 991/992 (1 skipped) | end_turn | 6 | 2 | $0.122 | +87/-12 | no_tests_added, no_changelog |
| [mixed-type-ordering #4](trajectories/mixed-type-ordering-04.json) | yes | 24/24 | 34/34 | 991/992 (1 skipped) | end_turn | 4 | 1 | $0.026 | +10/-4 | no_tests_added, no_changelog |
| [types-module #4](trajectories/types-module-04.json) | yes | 41/41 | 756/756 | 991/992 (1 skipped) | end_turn | 6 | 1 | $0.077 | +58/-55 | no_tests_added, no_changelog |
| [let-expressions #5](trajectories/let-expressions-05.json) | yes | 35/35 | 29/29 | 991/992 (1 skipped) | end_turn | 11 | 1 | $0.168 | +88/-10 | no_tests_added, no_changelog |
| [mixed-type-ordering #5](trajectories/mixed-type-ordering-05.json) | yes | 24/24 | 34/34 | 991/992 (1 skipped) | end_turn | 4 | 1 | $0.028 | +19/-6 | no_tests_added, no_changelog |
| [types-module #5](trajectories/types-module-05.json) | yes | 41/41 | 756/756 | 991/992 (1 skipped) | end_turn | 6 | 1 | $0.058 | +58/-56 | no_tests_added, no_changelog |

## Hidden tests that failed most often
