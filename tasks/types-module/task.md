# Refactor: move the JMESPath type model into `jmespath/types.py`

This repository is the `jmespath` Python library (a query language for JSON).
This is a **behavior-preserving refactor**. No user of the library should be
able to tell that anything changed, except that a new module exists.

## Why

The knowledge of "which JMESPath type is this Python value" is spread over two
modules. `jmespath/functions.py` owns the Python-type-name tables and the
argument type checker, and `jmespath/visitor.py` has its own private helpers
for "is this a number" and "can this be ordered". We want one module that owns
the type model, so the next feature that needs it does not add a third copy.

## What to do

Create `jmespath/types.py` with this public API:

- `TYPES_MAP` and `REVERSE_TYPES_MAP`: the two mapping tables that live in
  `jmespath/functions.py` today, moved (same keys, same values).
- `jmespath_type(value) -> str`: the JMESPath type name that the function
  argument type checker assigns to `value` today (for example `"number"`,
  `"string"`, `"boolean"`, `"array"`, `"object"`, `"null"`, `"expref"`), or
  `"unknown"` for a value the type checker does not recognize.
- `is_number(value) -> bool`: what the interpreter currently treats as a
  number (booleans are not numbers).
- `is_comparable(value) -> bool`: what the interpreter currently allows in an
  ordering comparison (`<`, `<=`, `>`, `>=`).

Then make `jmespath/functions.py` and `jmespath/visitor.py` use it:

- `functions.py` must no longer define its own `TYPES_MAP` or
  `REVERSE_TYPES_MAP`. Existing code imports them from `jmespath.functions`,
  so `from jmespath.functions import TYPES_MAP, REVERSE_TYPES_MAP` must keep
  working and give the *same objects* as `jmespath.types`.
- `visitor.py` must no longer define its own number or comparability helper
  functions; it uses `jmespath.types`.
- `Functions._convert_to_jmespath_type` is used by custom function subclasses
  in the wild. Keep it working, with the same results.
- `jmespath/types.py` must not import anything from the `jmespath` package,
  so that any module can import it without an import cycle.

## What must not change

Everything observable stays identical, for every input: return values and
their Python types, which exception is raised, and exception messages. This
includes inputs that are not plain JSON values, such as `bool` versus `int`,
`collections.OrderedDict`, subclasses of `dict`, `list`, `str` and `int`,
`decimal.Decimal`, `fractions.Fraction` and tuples. Some of today's behavior
for those values may look surprising. Do not "fix" it in this change; a
refactor that changes behavior will be rejected.

The existing test suite in `tests/` must still pass. You can run it with the
`run_visible_tests` tool. When you are done, reply with a short summary of the
change.
