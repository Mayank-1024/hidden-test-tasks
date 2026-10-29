# Rubric: let expressions

Hidden tests decide correctness. This rubric covers what tests cannot see.
Score each item 0, 1 or 2 (0 = absent or wrong, 1 = partly, 2 = fully). Total /16.

| # | Criterion | 2 points when |
|---|---|---|
| 1 | Change lives in the right layers | The lexer emits variable/assign tokens, the parser builds AST nodes, the interpreter owns scope. No string matching on the raw expression outside the lexer. |
| 2 | Scope is real lexical scope | Scope is a chain (or equivalent) owned by one search. Exprefs capture it. No module-level or parser-level mutable state, nothing stored on the cached `ParsedResult`. |
| 3 | `let`/`in` stay non-reserved | Recognized only in context (`let` followed by a variable; `in` only where a let expects it). No new reserved-word table that could break field names. |
| 4 | Error quality | `UndefinedVariableError` subclasses `JMESPathError` and names the variable. Parse errors point at the offending token with the existing error classes. |
| 5 | Existing behavior untouched | No unrelated edits, no reformatting of untouched code, existing public signatures unchanged (`_Expression.visit`, custom function calls). |
| 6 | Tests added | The solver added visible tests for the new syntax (results, shadowing, errors), in the style of the existing suite. |
| 7 | Docs | CHANGELOG entry under "Next Release"; comments where the grammar decision is non-obvious (binding power of the body, why bindings use the enclosing scope). |
| 8 | Size and clarity | Diff is proportionate (the gold patch is about 120 added lines across 6 files); no dead code, debug prints or leftover TODOs. |

Automatic flags in the run report (not scored, but read the diff when set):
visible test files edited or deleted; source changes outside `jmespath/`;
diff mentions `pytest`, `conftest`, `sys.modules` or `builtins`.
