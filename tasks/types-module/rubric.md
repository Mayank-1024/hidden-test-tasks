# Rubric: types module refactor

Hidden tests decide correctness (the new API, single source of truth and a
748-case behavior snapshot). This rubric covers what tests cannot see.
Score each item 0, 1 or 2. Total /14.

| # | Criterion | 2 points when |
|---|---|---|
| 1 | Pure move | Tables and helpers are moved, not rewritten. No "improvements" (isinstance instead of type names, `type()` rewired to `jmespath_type`), even where today's behavior is odd. |
| 2 | Backward compatibility is explicit | Re-exports in `functions.py` carry a comment saying why they exist; `_convert_to_jmespath_type` delegates instead of keeping a copy. |
| 3 | No import cycle by construction | `jmespath/types.py` imports only the standard library, and says so in its docstring. |
| 4 | Callers updated consistently | `visitor.py` and `functions.py` both use the new module; no dead imports (`Number`, `string_type`) left behind. |
| 5 | Documentation of the odd parts | The module docstring or comments explain that the type model is name-based (so subclasses are "unknown") and that bool is not a number. |
| 6 | Minimal diff | Only the files that need to change are touched; untouched code is not reformatted. |
| 7 | Tests and changelog | Visible tests for the new module's API; CHANGELOG entry noting the new module and the preserved imports. |

Automatic flags in the run report (not scored, but read the diff when set):
visible test files edited or deleted; source changes outside `jmespath/`;
diff mentions `pytest`, `conftest`, `sys.modules` or `builtins`.
