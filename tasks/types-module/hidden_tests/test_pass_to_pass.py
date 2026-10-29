"""Hidden behavior-preservation tests for the types refactor.

The snapshot was recorded on the starting tree, so these pass there and must
still pass after the refactor.
"""

import json
import os

import pytest

from jmespath import functions

from .corpus import cases, describe

SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "behavior_snapshot.json")

with open(SNAPSHOT_PATH, encoding="utf-8") as f:
    SNAPSHOT = json.load(f)

CASES = list(cases())


def test_snapshot_covers_every_case():
    assert sorted(SNAPSHOT) == sorted(case_id for case_id, _, _ in CASES)


@pytest.mark.parametrize(
    "case_id, expression, value", CASES, ids=[case_id for case_id, _, _ in CASES]
)
def test_behavior_unchanged(case_id, expression, value):
    assert describe(expression, value) == SNAPSHOT[case_id]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("OrderedDict", "object"),
        ("bool", "boolean"),
        ("int", "number"),
        ("_Expression", "expref"),
        ("MyDict", "unknown"),
        ("Decimal", "unknown"),
    ],
)
def test_convert_to_jmespath_type_still_works(name, expected):
    assert functions.Functions()._convert_to_jmespath_type(name) == expected


def test_custom_function_subclass_can_use_converter():
    class Custom(functions.Functions):
        @functions.signature({"types": []})
        def _func_kind(self, value):
            return self._convert_to_jmespath_type(type(value).__name__)

    import jmespath

    options = jmespath.Options(custom_functions=Custom())
    assert jmespath.search("kind(a)", {"a": [1]}, options) == "array"
    assert jmespath.search("kind(a)", {"a": True}, options) == "boolean"
