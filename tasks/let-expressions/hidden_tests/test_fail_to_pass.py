"""Hidden tests for let expressions. Each one fails on the starting tree.

Imports of new names happen inside the tests, so the module always collects
and every test reports its own result.
"""

import threading
from collections import OrderedDict

import jmespath
import pytest
from jmespath import exceptions

PEOPLE = {
    "minimum_age": 30,
    "prefix": "id-",
    "people": [
        {"name": "ana", "age": 41, "team": "red"},
        {"name": "bo", "age": 29, "team": "blue"},
        {"name": "cy", "age": 30, "team": "red"},
    ],
}


def undefined_variable_error():
    return exceptions.UndefinedVariableError


@pytest.mark.parametrize(
    "expression, data, expected",
    [
        ("let $x = foo in $x", {"foo": 7}, 7),
        ("let $x = foo in $x.bar[1]", {"foo": {"bar": [1, 2, 3]}}, 2),
        ("let $a = a, $b = b in [$b, $a]", {"a": 1, "b": 2}, [2, 1]),
        # A variable seen from inside a filter, where @ is the element.
        (
            "let $min = minimum_age in people[?age >= $min].name",
            PEOPLE,
            ["ana", "cy"],
        ),
        # ... and from inside a projection body.
        (
            "let $p = prefix in people[*].[name, $p]",
            PEOPLE,
            [["ana", "id-"], ["bo", "id-"], ["cy", "id-"]],
        ),
        # Bind the current node itself.
        (
            "let $root = @ in people[?age > `40`].{n: name, cutoff: $root.minimum_age}",
            PEOPLE,
            [{"n": "ana", "cutoff": 30}],
        ),
        # Function arguments and exprefs see the variable.
        (
            "let $t = team in people[?team == $t] | length(@)",
            {"team": "red", "people": PEOPLE["people"]},
            2,
        ),
        (
            "let $tag = prefix in map(&join('', [$tag, name]), people)",
            PEOPLE,
            ["id-ana", "id-bo", "id-cy"],
        ),
        (
            "let $p = prefix in max_by(people, &age).[name, $p]",
            PEOPLE,
            ["ana", "id-"],
        ),
        # Nested scopes: the inner binding sees the outer variable.
        ("let $a = a in let $b = [$a, b] in $b", {"a": 1, "b": 2}, [1, 2]),
        # Shadowing ends with the inner let expression.
        ("let $x = `1` in [let $x = `2` in $x, $x]", {}, [2, 1]),
        (
            "let $x = a in [let $x = b in $x, $x, let $y = c in [$x, $y]]",
            {"a": 1, "b": 2, "c": 3},
            [2, 1, [1, 3]],
        ),
        # Bound to null is not the same as undefined.
        ("let $x = missing in $x", {"a": 1}, None),
        ("let $x = missing in [$x, a]", {"a": 1}, [None, 1]),
        ("let $x = missing in not_null($x, a)", {"a": 1}, 1),
        # The body extends to the right through a pipe.
        ("let $x = a in b | $x", {"a": "from-a", "b": {"z": 1}}, "from-a"),
        # A binding ends at "in", so a pipe inside a binding is bound whole.
        ("let $x = foo | bar in $x", {"foo": {"bar": 5}}, 5),
        # A binding ends at a top-level comma.
        ("let $x = a, $y = [b, c] in $y", {"a": 0, "b": 1, "c": 2}, [1, 2]),
        # Let expressions are expressions: pipe rhs, multi-select, filter.
        ("foo | let $x = bar in $x.baz", {"foo": {"bar": {"baz": "q"}}}, "q"),
        ("{x: let $v = a in $v, y: b}", {"a": 1, "b": 2}, {"x": 1, "y": 2}),
        (
            "people[?let $n = name in starts_with($n, 'c')].age",
            PEOPLE,
            [30],
        ),
        # Variables survive into a sort_by key expression.
        (
            "let $k = `10` in sort_by(people, &age)[?age < `40`].[name, $k]",
            PEOPLE,
            [["bo", 10], ["cy", 10]],
        ),
    ],
)
def test_let_expression_result(expression, data, expected):
    assert jmespath.search(expression, data) == expected


def test_let_keyword_whitespace_variants():
    data = {"a": {"b": 3}}
    assert jmespath.search("let   $x=a   in   $x.b", data) == 3
    assert jmespath.search("let\n$x = a\nin\n$x.b", data) == 3


def test_bindings_do_not_see_each_other():
    with pytest.raises(undefined_variable_error()):
        jmespath.search("let $a = `1`, $b = $a in $b", {})


def test_sibling_binding_refers_to_outer_scope():
    expression = "let $a = `1` in let $a = `2`, $b = $a in [$a, $b]"
    assert jmespath.search(expression, {}) == [2, 1]


def test_undefined_variable_raises_at_search_time():
    compiled = jmespath.compile("$nope")
    with pytest.raises(undefined_variable_error()) as info:
        compiled.search({"nope": 1})
    assert isinstance(info.value, exceptions.JMESPathError)
    assert "nope" in str(info.value)


def test_variable_out_of_scope_after_let_ends():
    with pytest.raises(undefined_variable_error()):
        jmespath.search("[let $x = a in $x, $x]", {"a": 1})


def test_undefined_variable_inside_projection():
    with pytest.raises(undefined_variable_error()):
        jmespath.search("people[*].[name, $who]", PEOPLE)


def test_expref_captures_scope_where_written():
    # The expref is produced by an inner let and evaluated by map() after
    # that let has finished. It must still see the inner $x.
    data = {"nums": [1, 2]}
    expression = "let $x = 'outer' in map(let $x = 'inner' in &$x, nums)"
    assert jmespath.search(expression, data) == ["inner", "inner"]


def test_expref_closure_outer_variable():
    data = {"nums": [1, 2]}
    assert jmespath.search("let $x = 'outer' in map(&$x, nums)", data) == [
        "outer",
        "outer",
    ]


def test_compiled_expression_reused_with_new_data():
    compiled = jmespath.compile("let $x = a in items[?v > $x].v")
    assert compiled.search({"a": 1, "items": [{"v": 1}, {"v": 2}]}) == [2]
    assert compiled.search({"a": 0, "items": [{"v": 1}, {"v": 2}]}) == [1, 2]


def test_error_in_one_search_does_not_leak_scope():
    with pytest.raises(undefined_variable_error()):
        jmespath.search("let $x = a in $y", {"a": 1})
    with pytest.raises(undefined_variable_error()):
        jmespath.search("$x", {"a": 1})


def test_scopes_are_per_search_across_threads():
    compiled = jmespath.compile("let $v = v in items[*].[$v, @]")
    errors = []

    def worker(value):
        try:
            for _ in range(200):
                result = compiled.search({"v": value, "items": [1, 2]})
                assert result == [[value, 1], [value, 2]]
        except Exception as e:  # pragma: no cover - reported below
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


def test_dict_cls_option_still_applies_inside_let():
    options = jmespath.Options(dict_cls=OrderedDict)
    result = jmespath.search("let $x = a in {b: $x, a: $x}", {"a": 1}, options)
    assert isinstance(result, OrderedDict)
    assert list(result.items()) == [("b", 1), ("a", 1)]


def test_custom_function_receives_variable_value():
    from jmespath import functions

    class Custom(functions.Functions):
        @functions.signature({"types": ["string"]}, {"types": ["number"]})
        def _func_repeat(self, s, n):
            return s * n

    options = jmespath.Options(custom_functions=Custom())
    expression = "let $n = times in people[*].repeat(name, $n)"
    data = {"times": 2, "people": [{"name": "ab"}]}
    assert jmespath.search(expression, data, options) == ["abab"]
