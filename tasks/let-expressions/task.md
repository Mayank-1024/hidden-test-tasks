# Add `let` expressions (lexical scoping) to jmespath

This repository is the `jmespath` Python library (a query language for JSON).
Add support for **let expressions** and **variable references**, so a query
can bind a value once and refer to it from anywhere inside a sub-expression.

## Motivation

Today there is no way to refer to a value from an outer context once a
projection or filter has moved the current node (`@`) to an element. For
example, "the names of people at least as old as `minimum_age`" cannot be
written, because inside `people[?...]` the current node is a person, not the
root object. With this change it can be:

```
let $minimum_age = minimum_age in people[?age >= $minimum_age].name
```

## Grammar

```
let-expression = "let" binding *( "," binding ) "in" expression
binding        = variable-ref "=" expression
variable-ref   = "$" identifier
```

`identifier` uses the same characters as an unquoted identifier
(`[A-Za-z_][A-Za-z0-9_]*`). There must be no whitespace between `$` and the
name. A variable reference (`$name`) is an expression in its own right and can
appear anywhere an expression can, for example `$x`, `$x.foo`, `$x[0]`,
`foo[?bar == $x]`, `{a: $x}` or as a function argument.

## Semantics

1. A let expression evaluates each binding's expression against the current
   node (the value the let expression itself is evaluated against), then
   evaluates the body (the expression after `in`) against that same current
   node with the new variables in scope. The let expression's value is the
   body's value.
2. The bindings of one let expression are evaluated in the *enclosing* scope.
   They cannot see each other: in `let $a = x, $b = $a in $b`, the `$a` inside
   the second binding refers to an outer `$a`, if there is one.
3. Scopes nest lexically. An inner let expression may rebind a name; the inner
   binding shadows the outer one inside the inner body only. Outside the inner
   let expression the outer value is visible again.
4. Variables are visible everywhere inside the body, including inside
   projections, filters, multi-select lists and hashes, pipes, function
   arguments and expression references (`&expr`).
5. An expression reference captures the variables that are in scope where the
   `&` expression is written. When a function such as `sort_by`, `max_by` or
   `map` later evaluates it, it sees those variables, even if the reference
   was produced somewhere other than where the function call is written.
6. A variable can be bound to `null`. Referencing it gives `null`, not an
   error.
7. Referencing a variable that is not in scope raises
   `jmespath.exceptions.UndefinedVariableError`, a new subclass of
   `jmespath.exceptions.JMESPathError`. The error is raised when the
   expression is evaluated (`search`), not when it is compiled.
8. The body extends as far to the right as possible:
   `let $x = a in b | c` means `let $x = a in (b | c)`. A binding's expression
   ends at the next top-level `,` or `in`, so `let $x = a | b in c` binds
   `a | b`.
9. `let` and `in` are **not** reserved words. They keep working as field
   names (`let`, `in`, `foo.let`, `{let: a, in: b}`). `let` only starts a let
   expression when it is directly followed by a variable reference.

## Errors at compile time

Malformed let expressions must raise `jmespath.exceptions.ParseError` (or one
of its existing subclasses, such as `LexerError` or
`IncompleteExpressionError`) from `jmespath.compile`. For example: a missing
`in`, a missing `=`, a `$` with no name after it, or a let expression that
ends right after `in`.

A `=` that is not part of a binding (for example `foo = bar`) is still an
error at compile time, as it is today.

## Constraints

- Everything that works today must keep working. The existing test suite in
  `tests/` must still pass.
- A compiled expression can be searched many times, with different data; the
  variables of one search must never leak into another.
- Keep the existing public API (`jmespath.search`, `jmespath.compile`,
  `Options`, custom functions) unchanged.

You can run the existing test suite with the `run_visible_tests` tool. When
you are done, reply with a short summary of your change.
