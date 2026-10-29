"""Hidden regression guards for the mixed-type ordering fix.

These pass on the starting tree and must still pass after the fix.
"""

import pytest

import jmespath
from jmespath import exceptions, functions


class Boom(functions.Functions):
    @functions.signature({"types": []})
    def _func_boom(self, value):
        raise TypeError("boom from a custom function")

    @functions.signature({"types": []})
    def _func_boom_value(self, value):
        raise ValueError("custom value error")


OPTIONS = jmespath.Options(custom_functions=Boom())


@pytest.mark.parametrize(
    "expression, expected",
    [
        ('`"a"` < `"b"`', True),
        ('`"b"` <= `"a"`', False),
        ("`1` < `1.5`", True),
        ("`2` >= `2`", True),
        ("`true` < `1`", None),
        ("`1` > `false`", None),
        ("`null` < `1`", None),
        ('`[1]` < `"a"`', None),
        ('`"1"` == `1`', False),
        ('`"1"` != `1`', True),
        ("`1` == `1.0`", True),
        ("`0` == `false`", False),
    ],
)
def test_comparisons_unchanged(expression, expected):
    result = jmespath.search(expression, {})
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("max_by(people, &age).name", "a"),
        ("min_by(people, &age).name", "c"),
        ("max_by(people, &name).name", "c"),
        ("min_by(people, &name).name", "a"),
        ("sort_by(people, &age)[].name", ["c", "b", "a"]),
        ("max_by(`[]`, &age)", None),
        ("min_by(`[]`, &age)", None),
        ("max_by(people[:1], &age).name", "a"),
    ],
)
def test_by_functions_on_valid_data(expression, expected):
    data = {
        "people": [
            {"name": "a", "age": 40},
            {"name": "b", "age": 30.5},
            {"name": "c", "age": 25},
        ]
    }
    assert jmespath.search(expression, data) == expected


def test_sort_by_mixed_still_raises_type_error():
    data = {"people": [{"age": 1}, {"age": "x"}]}
    with pytest.raises(exceptions.JMESPathTypeError):
        jmespath.search("sort_by(people, &age)", data)


@pytest.mark.parametrize("expression", ["max_by(people, &age)", "min_by(people, &age)"])
def test_by_functions_still_reject_non_orderable_keys(expression):
    data = {"people": [{"age": True}, {"age": False}]}
    with pytest.raises(exceptions.JMESPathTypeError):
        jmespath.search(expression, data)


@pytest.mark.parametrize(
    "expression",
    [
        "items[?boom(@) > `1`]",
        "boom(a) < `1`",
        "max_by(items, &boom(@))",
        "min_by(items, &boom(@))",
        "sort_by(items, &boom(@))",
    ],
)
def test_custom_function_type_error_propagates(expression):
    data = {"a": 1, "items": [1, 2]}
    with pytest.raises(TypeError, match="boom from a custom function"):
        jmespath.search(expression, data, OPTIONS)


def test_custom_function_value_error_propagates():
    with pytest.raises(ValueError, match="custom value error"):
        jmespath.search("items[?boom_value(@) < `1`]", {"items": [1]}, OPTIONS)


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("max(`[1, 3, 2]`)", 3),
        ('min(`["b", "a"]`)', "a"),
        ('sort(`["b", "a"]`)', ["a", "b"]),
    ],
)
def test_array_functions_unchanged(expression, expected):
    assert jmespath.search(expression, {}) == expected


@pytest.mark.parametrize("expression", ['max(`[1, "a"]`)', 'sort(`[1, "a"]`)'])
def test_array_functions_still_reject_mixed(expression):
    with pytest.raises(exceptions.JMESPathTypeError):
        jmespath.search(expression, {})
