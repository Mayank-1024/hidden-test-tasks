# Bug: a raw `TypeError` escapes `jmespath.search` on mixed string/number data

This repository is the `jmespath` Python library (a query language for JSON).

## Report

Our service runs user-supplied JMESPath filters over records we receive from
partners. We wrap every call in `except jmespath.exceptions.JMESPathError`
and show the user a "bad query" message. Last week one partner started sending
`"age": "unknown"` instead of a number for some records, and requests began
failing with a 500:

```python
>>> import jmespath
>>> data = {"people": [{"name": "a", "age": 40}, {"name": "b", "age": "unknown"}]}
>>> jmespath.search("people[?age > `30`].name", data)
Traceback (most recent call last):
  ...
TypeError: '>' not supported between instances of 'str' and 'int'
```

We expected `["a"]`. A second team reports a similar crash from
`max_by(...)` on the same kind of data, and suspects the same cause.

## Expected behavior

Find the root cause and fix it everywhere it occurs, not only for the query
above.

1. An ordering comparison (`<`, `<=`, `>`, `>=`) between a string and a number,
   in either order, evaluates to `null`, the same as an ordering comparison on
   any other pair of types the library does not order (for example a boolean
   and a number). Inside a filter, `null` is false, so the element is skipped.
   Comparisons between two numbers or two strings are unchanged.
2. Built-in functions that order values taken from the input data must raise
   `jmespath.exceptions.JMESPathTypeError` when they are asked to order a mix
   of strings and numbers, instead of a raw `TypeError`. Functions that already
   raise `JMESPathTypeError` for this must keep doing so.
3. Exceptions raised by user-registered custom functions (see
   `jmespath.Options(custom_functions=...)`) must still propagate unchanged,
   with their original type, wherever the custom function is called. Do not
   hide errors that the library did not cause.
4. Everything else stays as it is: equality (`==`, `!=`) semantics, the rule
   that booleans are not numbers, and the results for valid data.

The existing test suite in `tests/` must still pass. You can run it with the
`run_visible_tests` tool. When you are done, reply with a short summary of the
root cause and your fix.
