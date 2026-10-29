"""A behavior corpus for the types refactor.

Every case runs one expression against data holding one unusual Python value
and describes the outcome as plain JSON (result repr and type, or exception
type and message). `behavior_snapshot.json` holds the outcomes recorded on the
starting tree; the refactor must reproduce them exactly.

Run `python -m hidden_tests.corpus` from a tree root to print a fresh snapshot.
"""

import json
from collections import OrderedDict
from decimal import Decimal
from fractions import Fraction


class MyDict(dict):
    pass


class MyList(list):
    pass


class MyStr(str):
    pass


class MyInt(int):
    pass


def values():
    return [
        ("true", True),
        ("int", 1),
        ("zero", 0),
        ("float", 1.5),
        ("str", "abc"),
        ("none", None),
        ("list", [3, 1, 2]),
        ("dict", {"a": 1}),
        ("ordered_dict", OrderedDict(a=1)),
        ("my_dict", MyDict(a=1)),
        ("my_list", MyList([3, 1, 2])),
        ("my_str", MyStr("abc")),
        ("my_int", MyInt(5)),
        ("decimal", Decimal("2.5")),
        ("fraction", Fraction(1, 3)),
        ("tuple", (3, 1, 2)),
        ("bools", [True, False]),
        ("strs", ["b", "a"]),
        ("mixed", [1, "a"]),
        ("my_strs", [MyStr("b"), MyStr("a")]),
        ("decimals", [Decimal("2"), Decimal("1")]),
        ("dict_list", [{"k": Decimal("1")}, {"k": 2}]),
    ]


EXPRESSIONS = [
    "type(v)",
    "length(v)",
    "abs(v)",
    "ceil(v)",
    "keys(v)",
    "values(v)",
    "to_string(v)",
    "to_number(v)",
    "to_array(v)",
    "not_null(v)",
    "reverse(v)",
    "sort(v)",
    "max(v)",
    "min(v)",
    "sum(v)",
    "avg(v)",
    "join(',', v)",
    "contains(v, 'a')",
    "starts_with(v, 'a')",
    "merge(v, `{}`)",
    "sort_by(v, &@)",
    "max_by(v, &@)",
    "min_by(v, &k)",
    "map(&type(@), v)",
    "v > `1`",
    'v <= `"b"`',
    "v == `1`",
    "!v",
    "v[0]",
    "v.a",
    "v[*]",
    "v[]",
    "v[?@ > `1`]",
    'v || `"fallback"`',
]


def describe(expression, value):
    import jmespath

    try:
        result = jmespath.search(expression, {"v": value})
    except Exception as e:  # noqa: BLE001 - the exception is the outcome
        return {"error": type(e).__name__, "message": str(e)}
    return {"repr": repr(result), "type": type(result).__name__}


def cases():
    for value_name, value in values():
        for expression in EXPRESSIONS:
            yield f"{value_name} | {expression}", expression, value


def snapshot():
    return {case_id: describe(expression, value) for case_id, expression, value in cases()}


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=1, sort_keys=True))
