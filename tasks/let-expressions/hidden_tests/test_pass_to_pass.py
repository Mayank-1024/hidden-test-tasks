"""Hidden regression guards for let expressions.

These pass on the starting tree and must still pass after the change.
"""

import pytest

import jmespath
from jmespath import exceptions


@pytest.mark.parametrize(
    "expression, data, expected",
    [
        ("let", {"let": 1}, 1),
        ("in", {"in": 2}, 2),
        ("foo.let", {"foo": {"let": 3}}, 3),
        ("let.in", {"let": {"in": 4}}, 4),
        ("{let: a, in: b}", {"a": 1, "b": 2}, {"let": 1, "in": 2}),
        ("[let, in]", {"let": "l", "in": "i"}, ["l", "i"]),
        ("let[0]", {"let": [9]}, 9),
        ("items[?let == `1`].in", {"items": [{"let": 1, "in": "x"}]}, ["x"]),
        ("length(let)", {"let": "abc"}, 3),
        ('"let"', {"let": 5}, 5),
        ("foo[?a == `1`]", {"foo": [{"a": 1}, {"a": 2}]}, [{"a": 1}]),
        ("foo[?a != `1`]", {"foo": [{"a": 1}, {"a": 2}]}, [{"a": 2}]),
        ("a <= b", {"a": 1, "b": 2}, True),
        ("a >= b", {"a": 1, "b": 2}, False),
    ],
)
def test_existing_expressions_unchanged(expression, data, expected):
    assert jmespath.search(expression, data) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "foo = bar",
        "foo[?a = `1`]",
        "=",
        "a ==",
        "let $x = a",
        "let $x = a in",
        "let $x a in b",
        "let $x = a b",
        "let $x = a, in b",
        "let $ = a in b",
        "let $1 = a in b",
        "let $x = a in $",
        "$",
        "$ x",
        "$1",
    ],
)
def test_malformed_expressions_fail_to_compile(expression):
    with pytest.raises(exceptions.ParseError):
        jmespath.compile(expression)
