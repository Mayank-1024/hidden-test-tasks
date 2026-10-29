# Run report: 2026-10-29T10:29:04Z

- Solver: `claude`, model `claude-sonnet-5-5`, effort `medium`
- Test runner: `docker` (isolated container, --network none)
- Harness commit: `3e485ae`
- Limits per attempt: 30 model calls, 16000 output tokens per call, 1,500,000 total tokens, $0.9
- Run budget: $4.0
- Finished: 2026-10-29T10:32:15Z
- Note: The API key ran out of credit during attempt let-expressions #2 (HTTP 400, 'Your credit balance is too low'). That attempt and the 11 after it ended with an API error; the harness of commit 3e485ae still graded them as unresolved and kept starting attempts. They were relabeled as status 'error' (12 attempts) by the fixed harness, which excludes them from pass rates and stops a run at the first fatal API error. Finish the run with: htt solve --resume runs/2026-10-29-102904-v1 --attempts 5.

## Results by task

| Task | Kind | Resolved | Pass rate | Mean fail-to-pass passed | Mean cost | Mean turns | Mean test runs | Stops |
|---|---|---|---|---|---|---|---|---|
| let-expressions | feature | 1/1 | 100% | 100% | $0.160 | 11.0 | 2.0 | end_turn x1 |
| mixed-type-ordering | bugfix | 1/1 | 100% | 100% | $0.054 | 4.0 | 1.0 | end_turn x1 |
| types-module | refactor | 1/1 | 100% | 100% | $0.092 | 9.0 | 1.0 | end_turn x1 |

**Total:** 3/3 graded attempts resolved, 12 cut short by an API error (not scored). Spend $0.39 (all attempts). Tokens: 66 input, 60,066 cache write, 457,033 cache read, 14,943 output, over 29 model calls. Solver wall time 2.5 min.

## Attempts

| Attempt | Resolved | Fail-to-pass | Pass-to-pass | Visible | Stop | Turns | Test runs | Cost | Lines +/- | Flags |
|---|---|---|---|---|---|---|---|---|---|---|
| [let-expressions #1](trajectories/let-expressions-01.json) | yes | 35/35 | 29/29 | 991/992 (1 skipped) | end_turn | 11 | 2 | $0.160 | +90/-7 | - |
| [mixed-type-ordering #1](trajectories/mixed-type-ordering-01.json) | yes | 24/24 | 34/34 | 991/992 (1 skipped) | end_turn | 4 | 1 | $0.054 | +13/-3 | - |
| [types-module #1](trajectories/types-module-01.json) | yes | 41/41 | 756/756 | 991/992 (1 skipped) | end_turn | 9 | 1 | $0.092 | +54/-55 | - |
| [let-expressions #2](trajectories/let-expressions-02.json) | API error | 0/35 | 22/29 | 990/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 5 | 0 | $0.085 | +58/-8 | never_ran_visible_tests |
| [mixed-type-ordering #2](trajectories/mixed-type-ordering-02.json) | API error | 0/24 | 34/34 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [types-module #2](trajectories/types-module-02.json) | API error | 0/41 | 756/756 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [let-expressions #3](trajectories/let-expressions-03.json) | API error | 0/35 | 29/29 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [mixed-type-ordering #3](trajectories/mixed-type-ordering-03.json) | API error | 0/24 | 34/34 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [types-module #3](trajectories/types-module-03.json) | API error | 0/41 | 756/756 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [let-expressions #4](trajectories/let-expressions-04.json) | API error | 0/35 | 29/29 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [mixed-type-ordering #4](trajectories/mixed-type-ordering-04.json) | API error | 0/24 | 34/34 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [types-module #4](trajectories/types-module-04.json) | API error | 0/41 | 756/756 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [let-expressions #5](trajectories/let-expressions-05.json) | API error | 0/35 | 29/29 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [mixed-type-ordering #5](trajectories/mixed-type-ordering-05.json) | API error | 0/24 | 34/34 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |
| [types-module #5](trajectories/types-module-05.json) | API error | 0/41 | 756/756 | 991/992 (1 skipped) | api_error: BadRequestError: Error code: 400 - {'type': 'e... | 0 | 0 | $0.000 | +0/-0 | never_ran_visible_tests, no_changes |

## Hidden tests that failed most often
