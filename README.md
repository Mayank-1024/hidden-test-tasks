# Hidden-Test Coding Tasks

Three coding tasks on a real open-source library, each built the way coding
post-training data is built: a task statement the solver sees, hidden tests it
never sees, a gold patch, a rubric for what tests cannot check, and a pinned
environment. A verification command proves every task is well formed before
any model is graded on it. A minimal Claude tool-use harness then attempts the
tasks in a sandbox, and the harness (not the model) grades each attempt on the
hidden tests.

Built with Python 3.13, uv, pytest, Docker and the Anthropic Python SDK.

**Status (2026-10-29):** all three tasks verified, 8 of 8 known-wrong patches
rejected, 86 offline tests passing. The planned 15 model attempts are done:
**15 of 15 resolved, and none added a test.** The run was paused once when the
API credit ran out and resumed the same day (see [Results](#results)).

## The three tasks

The base tree for every task is an unmodified snapshot of
[jmespath.py](https://github.com/jmespath/jmespath.py) 1.1.0 (MIT), the JSON
query language used by the AWS CLI and boto3. See
[upstream/NOTICE.md](upstream/NOTICE.md) for the pinned commit and why this
library was chosen: MIT licensed, no dependencies or native code, about 1,700
lines across a lexer, a Pratt parser, an AST, an interpreter and a typed
function registry, and a 992-test suite generated mostly from the language's
JSON compliance files.

| Task | Kind | What the solver must do | Gold patch | Hidden tests |
|---|---|---|---|---|
| [let-expressions](tasks/let-expressions/task.md) | feature | Add `let $x = expr in body` and `$x` references: new tokens in the lexer, a new parse rule, new AST nodes, and lexical scope in the interpreter, including expression references (`&expr`) that keep the scope they were written in. | 6 files, +120/-8 | 35 fail-to-pass, 29 pass-to-pass |
| [mixed-type-ordering](tasks/mixed-type-ordering/task.md) | bug fix | A real bug in 1.1.0: `people[?age > \`30\`]` raises a raw `TypeError` when one record has a string age. The same per-value type check exists in `min_by`/`max_by`; `sort_by` already handles it. Fix the cause everywhere without swallowing errors from user-defined functions. | 3 files, +23/-4 | 24 fail-to-pass, 34 pass-to-pass |
| [types-module](tasks/types-module/task.md) | refactor | Move the type model into a new `jmespath/types.py`, make two modules use it, keep the old import paths working, and change nothing observable, including odd behavior for dict subclasses, `Decimal` and tuples. | 4 files, +78/-54 | 41 fail-to-pass, 756 pass-to-pass |

### Why hidden tests

If the solver can see the tests, the tests stop measuring the task. A model
can fit its code to the exact assertions, special-case the inputs, or edit the
tests. Hidden tests are written from the task statement, so they check whether
the stated behavior was built. Each task splits them in two:

- **fail-to-pass**: the new behavior. Every one must fail on the starting tree
  and pass with the gold patch. A test that already passes on the starting tree
  measures nothing.
- **pass-to-pass**: regression guards for behavior that must not change, for
  example `let` and `in` still working as field names, or errors from a user's
  custom function still propagating. They must pass both before and after.

The repository's own 992-test suite is the visible suite. The solver can run
it; the grader runs a pristine copy of it.

### What makes each task hard

- **let-expressions** touches four layers that have to agree. The traps the
  hidden tests check: bindings in one `let` must not see each other; a
  variable bound to `null` is not the same as an undefined one; `let` and `in`
  must stay usable as field names; a lone `=` must still be a compile error;
  and an expression reference created inside an inner `let` and evaluated
  later by `map()` must see the inner scope. The `dynamic-scope` mutant below,
  which keeps one scope stack and does not capture it in exprefs, fails
  exactly that one hidden test.
- **mixed-type-ordering** reports one symptom but has the same cause in three
  places. The tempting fix, `try/except TypeError`, makes the reported query
  work and also hides `TypeError`s raised by user-defined functions, which the
  pass-to-pass tests catch.
- **types-module** rewards doing less. The type model is keyed on Python type
  *names*, so a `dict` subclass is "unknown" and `type()` of a `Decimal`
  returns `null`. A refactor that "cleans up" with `isinstance` changes those
  results. A 748-case behavior snapshot (22 unusual values times 34
  expressions, recorded on the starting tree) pins every result, exception
  type and message.

### Known-wrong patches (mutants)

A gold patch passing proves the tests can be satisfied; it does not prove they
can tell a right answer from a plausible wrong one. Each task ships patches
that are wrong in a realistic way, and verification requires the hidden tests
to reject every one. In the verification run on 2026-10-29:

| Task | Mutant | Hidden tests that failed |
|---|---|---|
| let-expressions | `dynamic-scope`: exprefs do not capture scope | 1 |
| let-expressions | `null-is-undefined`: a `null` binding raises | 3 |
| let-expressions | `sequential-bindings`: bindings see earlier siblings | 2 |
| mixed-type-ordering | `comparator-only`: fixes filters, not `min_by`/`max_by` | 9 |
| mixed-type-ordering | `broad-except`: catches `TypeError` around evaluation | 4 |
| types-module | `copies-kept`: new module, but old copies left in place | 2 |
| types-module | `isinstance-types`: type model switched to `isinstance` | 7 |
| types-module | `rewired-type-function`: `type()` routed through the new helper | 9 |

## How a task is laid out

```
tasks/let-expressions/
  task.md              the only text the solver sees
  task.toml            id, kind, base tree, source dirs, timeout
  gold.patch           reference solution (git diff against the base tree)
  rubric.md            0-2 scoring for qualities tests cannot see
  Dockerfile           python:3.13-slim pinned by digest, pytest 8.4.1 pinned
  hidden_tests/        never copied into the solver's tree
    test_fail_to_pass.py
    test_pass_to_pass.py
  mutants/*.patch      known-wrong solutions the hidden tests must reject
  verification.json    the last successful verification (checks, counts, test ids)
```

## Running it

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/) and Docker. No API
key is needed for verification or the offline tests.

```bash
uv sync
uv run pytest                                   # 86 offline tests
uv run ruff check .
uv run python -m htt verify                     # verify all tasks in Docker
uv run python -m htt verify let-expressions     # one task
uv run python -m htt solve --solver gold        # fake solver: applies gold.patch
uv run python -m htt solve --solver noop        # fake solver: changes nothing
```

`htt verify` runs these checks and writes `verification.json` only if all pass:

1. Static: task files exist, the gold patch touches only source and changelog
   files (never tests), task.md does not quote any line of the gold patch, and
   task.md does not name a hidden test.
2. Starting tree: every fail-to-pass test fails, every pass-to-pass test
   passes, the visible suite passes.
3. Gold patch: applies cleanly, then every hidden test and the visible suite
   pass, and the same fail-to-pass tests are collected on both trees.
4. Stability: two gold runs give identical per-test outcomes.
5. Mutants: every patch in `mutants/` fails at least one hidden test.

If Docker is not running, `--runner local` runs the same checks with the
current interpreter and no isolation. Docker was running for every run in this
README.

### The solver harness

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY
uv run --env-file .env python -m htt solve --attempts 5 --budget-usd 8
```

- **Model call:** `client.messages.create` with `claude-sonnet-5-5`, adaptive
  thinking with summarized display (so trajectories show the model's
  reasoning), effort `medium`, and automatic prompt caching.
- **Tools:** `list_files`, `read_file`, `write_file`, `edit_file` and
  `run_visible_tests`. No shell. Every path is resolved against a temporary
  copy of the base tree and rejected if it is absolute, uses `..` to leave the
  tree, goes through a symlink that points outside, or names `.git`.
  `run_visible_tests` takes no arguments: it runs `python -m pytest tests` in
  the task container with `--network none`, a read-only mount, no
  capabilities, memory/CPU/PID limits, a non-root user and a 120 s timeout.
- **Limits per attempt:** 30 model calls, 16,000 output tokens per call,
  1,500,000 total tokens and $0.90, checked before each call. A run-level
  `--budget-usd` stops starting new attempts.
- **Grading:** after the solver returns, the harness copies only the solver's
  `jmespath/` directory next to a pristine copy of the visible tests and the
  hidden tests, and runs them in the container. Editing tests, deleting them or
  adding a `conftest.py` cannot change the grade.
- **Output:** `runs/<timestamp>/report.json` and `report.md` (pass rates,
  per-test results, tokens, cost, time, stop reasons), plus one diff and one
  trajectory per attempt.
- **Errors:** an attempt the API cuts short is recorded as `error`, counted in
  spend and excluded from pass rates. A 400/401/403/404 that survives the
  SDK's retries stops the run.

## Results

All numbers are from real runs on 2026-10-29 with `claude-sonnet-5-5` at
effort `medium`, tests in Docker. Reports, diffs and trajectories are
committed under [runs/](runs/). The main run is
[runs/2026-10-29-102904-v1](runs/2026-10-29-102904-v1/report.md); the two
pilot runs (one attempt per task) are next to it.

| Task | Kind | Resolved | Mean cost | Model calls per attempt | Visible test runs (mean) |
|---|---|---|---|---|---|
| let-expressions | feature | 5/5 | $0.162 | 11, 11, 11, 6, 11 | 1.4 |
| mixed-type-ordering | bugfix | 5/5 | $0.041 | 4, 4, 4, 4, 4 | 1.0 |
| types-module | refactor | 5/5 | $0.075 | 9, 5, 4, 6, 6 | 1.0 |

- **15 of 15 attempts resolved** in the main run: every fail-to-pass,
  pass-to-pass and visible test passed in each. The 3 pilot attempts also
  resolved.
- **Spend: $1.39** for the main run (100 model calls, 54,602 output tokens,
  1,503,267 input tokens read from the prompt cache), $0.32 for the pilots,
  and $0.085 for one attempt the API cut short: about $1.80 in total.
- **The run was paused once.** During let-expressions attempt 2 the API
  returned HTTP 400, "Your credit balance is too low". That attempt and the 11
  after it failed. The harness at that commit graded them as unresolved and
  kept starting attempts; I fixed both (they are now `error`, excluded from
  pass rates, and a fatal error stops the run) and relabeled the stored report.
  After a top-up, `htt solve --resume` kept the 3 graded attempts and reran
  the other 12, all on the same harness and settings.

### What the trajectories showed

- **The tasks do not separate models yet.** 15 of 15 is a ceiling. These
  tasks show that the pipeline works (statements, hidden tests, sandbox,
  grading), not how hard they are. The bug fix is the clearest case: all 5
  attempts read two files, made the same two fixes as the gold patch (a
  per-pair type check in the comparator, a first-key type check for
  `min_by`/`max_by`) and finished in 4 model calls for about $0.04. The next
  version should drop the second team's `max_by` report from task.md so the
  solver has to find the other call sites itself, and the other two
  statements should name fewer of the edge cases the hidden tests check.
- **No tests, no changelog.** None of the 15 attempts added a test or a
  CHANGELOG entry, although both are in every rubric. The first
  let-expressions attempt said so in its summary: "I didn't add tests for
  `let` itself, so the new behaviour hasn't been run." All 35 fail-to-pass
  tests passed anyway. Hidden tests alone score these attempts as perfect;
  the rubric does not.
- **Calls to tools that do not exist.** 9 of 15 attempts called `bash` or
  `bash_grep`, 15 calls in total, all in the feature and refactor tasks. The
  harness returned "unknown tool" and the model carried on with `read_file`.
  Where the reasoning before the call said anything, it was about finding a
  function definition; the tool set has no search tool. A confined
  `search_files` tool is the obvious addition, left out so every attempt ran
  on the same harness.
- **Edit misses.** In the first 7 attempts, 4 `edit_file` calls failed
  because `old_text` did not match the file exactly. In the one the model
  commented on, it was indentation ("Indentation mismatch; redo precisely."),
  fixed on the next call.

### Reproducing the run

```bash
uv run --env-file .env \
  python -m htt solve --attempts 5 --budget-usd 3
```

`uv run python -m htt estimate --attempts 5` projects the cost first.

## Limitations

- **Small sample, and at the ceiling.** 15 attempts on three tasks, all
  resolved: enough to show the pipeline works end to end, not to estimate a
  pass rate or rank models.
- **One library, one model.** All tasks share one base tree, and every attempt
  used `claude-sonnet-5-5` at effort `medium`.
- **Task statements are explicit.** Every hidden test traces to a sentence in
  task.md. That keeps grading fair but makes the tasks easier; real issue
  reports are vaguer.
- **The rubric is not scored automatically.** Reports flag objective signals
  (no tests added, no changelog, test files edited, source changes outside
  `jmespath/`, suspicious terms such as `pytest` or `sys.modules` in source).
  Scoring the rubric still needs a person or a grader model.
- **In-process tampering is possible.** Solver code runs inside the grading
  process. Grading uses pristine tests and the container has no network, but
  code in `jmespath/__init__.py` could still patch pytest at import time. The
  suspicious-terms flag points a reviewer at the diff; it does not prevent it.
- **No refusal fallback.** A refused request ends the attempt as `refusal`.
  The API's server-side fallback was left off because switching models
  mid-attempt would make the result belong to a different model.
- **Pilots before the commit.** The two pilot runs used the harness code of
  commit 49a9957 before it was committed, so their reports record the previous
  commit. Each report says this in its note.

## Repository layout

```
htt/          the harness: tasks, workspace, runner, grading, verify, sandbox,
              solver, attempt, report, pricing, cli
tasks/        the three tasks
upstream/     vendored jmespath.py 1.1.0 and NOTICE.md
runs/         committed run reports, diffs and trajectories
tests/        offline tests, with a toy task fixture under tests/fixtures/
```

## How this was built

Built by Mayank Bhadrasen with Claude Code.

## License

MIT for this repository, see [LICENSE](LICENSE). The vendored library keeps
its own MIT license, see [upstream/jmespath/LICENSE](upstream/jmespath/LICENSE).
