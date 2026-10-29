# Walkthrough: Hidden-Test Coding Tasks

Interview prep. What each file does, why it is built that way, and the
questions I expect, with honest answers. Numbers are from the 2026-10-29 runs
in `runs/`.

## The 60-second version

I took a real library (jmespath.py 1.1.0, MIT) and wrote three tasks on it the
way coding post-training data is made: a feature, a root-cause bug fix and a
behavior-preserving refactor. Each has a task statement, hidden tests split
into fail-to-pass and pass-to-pass, a gold patch, a rubric, a pinned Docker
environment and a set of known-wrong patches. `htt verify` proves each task is
sound: the new tests fail before, pass after, nothing else breaks, results are
stable, and every wrong patch is rejected. Then a small Claude tool-use loop
attempts the tasks with five confined tools, and the harness grades the result
on the hidden tests. Six completed attempts resolved 6 of 6 for $0.71 before
the API credit ran out. The most useful finding was that none of them added a
test or a changelog entry, which hidden tests cannot see but the rubric can.

## Walking the code in order

1. **`upstream/`**: the vendored library, byte-for-byte, with `NOTICE.md`
   (repo, tag, commit SHA, license, what was left out, why this library).
   Ruff skips it so formatting never drifts from upstream.
2. **`tasks/<id>/task.toml`**: metadata. `base` points at the vendored tree,
   `source_dirs = ["jmespath"]` says which directories count as the solver's
   work.
3. **`tasks/<id>/task.md`**: the only thing the solver reads. Written so every
   hidden test traces to a sentence in it.
4. **`tasks/<id>/hidden_tests/`**: `test_fail_to_pass.py` and
   `test_pass_to_pass.py`. New names (like `jmespath.types`) are imported inside
   each test so the module always collects; otherwise one import error would
   hide every per-test result. The refactor task adds `corpus.py` and a
   748-entry `behavior_snapshot.json` recorded on the starting tree in Docker.
5. **`tasks/<id>/gold.patch` and `mutants/*.patch`**: one correct solution and
   two or three plausible wrong ones.
6. **`htt/tasks.py`**: loads a task directory into a `Task` dataclass.
7. **`htt/workspace.py`**: copies trees, applies patches with `git apply`
   (which refuses paths outside the tree), produces diffs, and builds the
   grading tree: pristine base, then only the solver's `jmespath/`, then the
   hidden tests.
8. **`htt/runner.py`**: runs pytest and parses the junit XML into per-test
   outcomes. `DockerRunner` uses `--network none`, a read-only mount,
   `--cap-drop ALL`, no-new-privileges, memory/CPU/PID limits, a non-root user
   and a timeout that kills the container. `LocalRunner` is the same without
   isolation, for the offline tests and as a fallback.
9. **`htt/grading.py`**: groups results into fail-to-pass, pass-to-pass and
   visible, and decides "resolved" (all hidden pass, visible pass or skip,
   no timeout, no expected test missing).
10. **`htt/verify.py`**: the core. Static checks, then start-tree run,
    gold run, repeat run and mutant runs. Writes `verification.json` only when
    every check passes.
11. **`htt/sandbox.py`**: the five tools and path confinement.
12. **`htt/solver.py`**: the Claude loop plus the two fake solvers (gold patch,
    no-op).
13. **`htt/attempt.py`**: one attempt end to end, the round-robin run loop,
    run budget, fatal-error stop and `--resume`.
14. **`htt/report.py`** and **`htt/pricing.py`**: report.json/report.md and
    cost from the usage the API returns.
15. **`tests/`**: 86 offline tests. A toy task under `tests/fixtures/` (my own
    10-line library with a bug) lets the verification and grading logic run
    for real with the local runner, without running vendored code locally.

## Decisions and why

- **jmespath over something bigger.** A solver has to be able to read the
  whole package in one attempt, and I have to be able to explain every line of
  every gold patch. 1,700 lines with five clear layers is the sweet spot. The
  992-test suite and the written spec matter just as much: the suite is the
  visible test signal, and the spec lets task statements be precise.
- **A real bug instead of an injected one.** The mixed-type bug exists in
  1.1.0 as released. I probed it in the container before writing the task.
  Injected bugs tend to be one-line reverts that are easy to grep for.
- **Fail-to-pass and pass-to-pass, checked both ways.** A fail-to-pass test
  that passes on the starting tree measures nothing, and verification fails
  the task if one does. Pass-to-pass tests catch "fixes" that break something
  else, such as catching `TypeError` too broadly.
- **Mutants.** Gold passing only shows the tests can be satisfied. Mutants show
  they discriminate. The `dynamic-scope` mutant fails exactly one hidden test,
  which told me that test is load-bearing and must never be dropped.
- **Snapshot for the refactor.** "Behavior-preserving" is only testable against
  recorded behavior. The snapshot includes the odd cases on purpose, because
  those are what a cleanup-minded refactor changes.
- **Grade only the source directory.** The grading tree takes `jmespath/` from
  the solver and everything else from the pristine base, so edited tests or a
  planted `conftest.py` have no effect.
- **No shell for the model.** Five narrow tools are easy to confine and audit.
  `run_visible_tests` takes no arguments, so the model cannot choose what runs;
  it can only write files that the fixed test command then imports, inside a
  container with no network and a read-only mount.
- **Manual loop instead of the SDK's tool runner.** I wanted explicit control
  over the per-attempt limits, the handling of each stop reason (`max_tokens`
  with a half-written tool call is answered with an error result and never
  executed) and the trajectory format.
- **Sonnet 5.5 at effort medium, caching on.** Medium is the documented
  starting point for agentic coding. Automatic caching moved the cache
  breakpoint forward each turn, so 714,339 input tokens were cache reads and
  only 108 were uncached.
- **No refusal fallback.** Falling back to another model mid-attempt would
  credit one model with another model's work.
- **Errors are not failures.** When the credit ran out, the first version of
  the harness graded 12 dead attempts as unresolved. A pass rate that mixes
  infrastructure failures with model failures is wrong, so those now get
  status `error` and are excluded.

## Likely questions

**1. How do you know a task is correct and not just passable?**
Five layers. Hidden fail-to-pass tests fail on the starting tree (all 35, 24
and 41 did). They pass with the gold patch along with every pass-to-pass test
and the 991 visible tests. Two gold runs gave identical outcomes. And 8 of 8
mutants were rejected, so the tests separate right from plausibly wrong. What
this does not prove is that the tests cover every reasonable reading of the
statement; that needs a second author to review them.

**2. Aren't the tasks too easy if the model solved all of them?**
Possibly, and I say so in the README. Six of six resolved, the bug fix in 4
model calls. Part of the reason is that I wrote the statements so every hidden
test is justified by a sentence, which also tells the solver what to check.
With only two attempts per task I did not change the tasks mid-run, because
that would make the remaining attempts incomparable. If the rest look the same,
the first change is removing the `max_by` hint from the bug report.

**3. What did the trajectories teach you that the pass rate didn't?**
That a 100% pass rate hid a quality gap: no attempt added a test or a
changelog entry, and one said so in its own summary. Also that the model
called a `bash` tool that does not exist in 4 of 7 attempts, apparently
looking for a search tool.

**4. How could a solver cheat, and what stops it?**
It could edit or delete the visible tests (grading uses a pristine copy), add
a `conftest.py` (only `jmespath/` is copied into the grading tree), read the
hidden tests (they are never in its tree, and paths outside the tree are
rejected), or reach the network (the container runs with `--network none`).
What remains is code inside `jmespath/` that patches pytest at import time.
The report flags terms like `pytest` and `sys.modules` in source diffs, but
that is a pointer for a reviewer, not a guarantee.

**5. How does path confinement work, and what did you test?**
Each path must be relative, is resolved with symlinks followed, and must stay
inside the resolved root by path components, not by string prefix. Tests cover
`..`, absolute paths, `~`, NUL bytes, `.git`, a sibling directory that shares
the root's name as a prefix, a symlinked file and a symlinked directory that
point outside. Gold patches go through `git apply`, which also refuses `..`
paths; there is a test for that too.

**6. Why split fail-to-pass and pass-to-pass instead of one test file?**
They answer different questions. Fail-to-pass asks "was the change made";
pass-to-pass asks "did anything else break". Verification checks them in
opposite directions on the starting tree, which is how it catches a test that
was filed in the wrong group.

**7. What does the rubric add if tests already decide correctness?**
Everything tests cannot see: whether the fix is at the cause, whether new
tests and docs were added, whether the diff is proportionate. In these runs
the rubric's "tests added" item would have scored 0 for every attempt while
the hidden tests scored 100%. Scoring the rubric is still manual; the report
only computes objective signals such as "no tests added".

**8. What happened with the budget, and how did you handle it?**
I estimated first: a one-attempt pilot per task projected $1.61 for 15 attempts
against an $8 cap. The run then stopped after $0.71 total because the API key
ran out of credit. I fixed the harness so errored attempts are not scored and
a fatal error stops the run, relabeled the stored report, and added `--resume`.
The remaining 12 attempts are projected at $1.25.

**9. How would you scale this to hundreds of tasks?**
Keep the task format and `htt verify` as the gate, and run verification in CI
for every new task. Add a second author review of hidden tests against the
statement, more base repositories, per-task difficulty calibration (several
models, several attempts, keep tasks in a useful pass-rate band), and a grader
for the rubric with spot checks by people.

**10. What would you change first?**
Add a confined `search_files` tool, since the model went looking for one.
Make the bug-fix statement less leading. Finish the remaining 12 attempts and
score the rubric for all of them. Then add a task where the statement is a
realistic, vaguer issue report, to measure how much the explicit statements
are doing.

## Numbers to remember

- Base: jmespath.py 1.1.0, about 1,700 lines, 992 visible tests (991 pass, 1
  skipped on CPython 3.13).
- Hidden tests: 35/29 (feature), 24/34 (bug fix), 41/756 (refactor)
  fail-to-pass/pass-to-pass. 8 mutants, all rejected.
- Model runs: 6 completed attempts, 6 resolved, $0.71 spent in total, $0.054
  to $0.189 per attempt, 4 to 11 model calls per attempt.
- 86 offline tests.
