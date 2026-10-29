"""Hidden tests for the mixed string/number ordering bug.

Each one fails on the starting tree (a raw TypeError escapes).
"""

import pytest

import jmespath
from jmespath import exceptions

MIXED = {
    "people": [
        {"name": "a", "age": 40},
        {"name": "b", "age": "unknown"},
        {"name": "c", "age": 25},
    ]
}


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("people[?age > `30`].name", ["a"]),
        ("people[?age >= `25`].name", ["a", "c"]),
        ("people[?age < `30`].name", ["c"]),
        ("people[?age <= `40`].name", ["a", "c"]),
        ("people[?`30` < age].name", ["a"]),
        # The comparison is null for "b", so its negation is true.
        ("people[?!(age > `30`)].name", ["b", "c"]),
        ("people[?age > `30` || name == 'b'].name", ["a", "b"]),
    ],
)
def test_filter_skips_string_number_comparisons(expression, expected):
    assert jmespath.search(expression, MIXED) == expected


@pytest.mark.parametrize(
    "expression",
    [
        '`"a"` < `1`',
        '`"a"` <= `1`',
        '`"a"` > `1`',
        '`"a"` >= `1`',
        '`1` < `"a"`',
        '`1.5` >= `"a"`',
        "a < b",
    ],
)
def test_string_number_ordering_is_null(expression):
    assert jmespath.search(expression, {"a": "x", "b": 2}) is None


def test_multiselect_comparisons_are_null():
    data = {"s": "10", "n": 10}
    assert jmespath.search("[s < n, n > s, n == n]", data) == [None, None, True]


@pytest.mark.parametrize("function_name", ["max_by", "min_by"])
@pytest.mark.parametrize(
    "ages",
    [
        [40, "unknown", 25],
        ["unknown", 40],
        [1, 2, 3, "x"],
        [1.5, "x"],
    ],
)
def test_by_functions_raise_jmespath_type_error(function_name, ages):
    data = {"people": [{"age": age} for age in ages]}
    with pytest.raises(exceptions.JMESPathTypeError) as info:
        jmespath.search("%s(people, &age)" % function_name, data)
    assert isinstance(info.value, exceptions.JMESPathError)
    assert function_name in str(info.value)


def test_service_style_error_handling():
    # The reporter's wrapper: every failure must be a JMESPathError.
    queries = [
        "people[?age > `30`].name",
        "max_by(people, &age).name",
        "min_by(people, &age).name",
        "sort_by(people, &age)[].name",
    ]
    outcomes = []
    for query in queries:
        try:
            outcomes.append(jmespath.search(query, MIXED))
        except exceptions.JMESPathError:
            outcomes.append("bad query")
    assert outcomes == [["a"], "bad query", "bad query", "bad query"]
