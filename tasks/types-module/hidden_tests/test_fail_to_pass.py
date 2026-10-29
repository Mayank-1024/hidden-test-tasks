"""Hidden tests for the types refactor. Each one fails on the starting tree.

`jmespath.types` is imported inside each test so the module always collects.
"""

import ast
import importlib
import os
from collections import OrderedDict
from decimal import Decimal
from fractions import Fraction

import jmespath
import pytest

from .corpus import MyDict, MyInt, MyList, MyStr

PACKAGE_DIR = os.path.dirname(jmespath.__file__)

ORIGINAL_TYPES_MAP = {
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "NoneType": "null",
    "unicode": "string",
    "str": "string",
    "float": "number",
    "int": "number",
    "long": "number",
    "OrderedDict": "object",
    "_Projection": "array",
    "_Expression": "expref",
}

ORIGINAL_REVERSE_TYPES_MAP = {
    "boolean": ("bool",),
    "array": ("list", "_Projection"),
    "object": ("dict", "OrderedDict"),
    "null": ("NoneType",),
    "string": ("unicode", "str"),
    "number": ("float", "int", "long"),
    "expref": ("_Expression",),
}


def types_module():
    return importlib.import_module("jmespath.types")


def module_tree(name):
    with open(os.path.join(PACKAGE_DIR, name), encoding="utf-8") as f:
        return ast.parse(f.read())


def test_tables_moved_with_same_contents():
    types = types_module()
    assert types.TYPES_MAP == ORIGINAL_TYPES_MAP
    assert types.REVERSE_TYPES_MAP == ORIGINAL_REVERSE_TYPES_MAP


def test_functions_reexports_the_same_objects():
    types = types_module()
    from jmespath import functions
    from jmespath.functions import REVERSE_TYPES_MAP, TYPES_MAP

    assert TYPES_MAP is types.TYPES_MAP
    assert REVERSE_TYPES_MAP is types.REVERSE_TYPES_MAP
    assert functions.TYPES_MAP is types.TYPES_MAP


def _expression_value():
    from jmespath.visitor import _Expression

    return _Expression(None, None)


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, "boolean"),
        (False, "boolean"),
        (0, "number"),
        (1.5, "number"),
        ("s", "string"),
        (None, "null"),
        ([], "array"),
        ({}, "object"),
        (OrderedDict(), "object"),
        (MyDict(), "unknown"),
        (MyList(), "unknown"),
        (MyStr("x"), "unknown"),
        (MyInt(3), "unknown"),
        (Decimal("1"), "unknown"),
        (Fraction(1, 2), "unknown"),
        ((1, 2), "unknown"),
        (b"x", "unknown"),
    ],
)
def test_jmespath_type(value, expected):
    assert types_module().jmespath_type(value) == expected


def test_jmespath_type_of_expref():
    assert types_module().jmespath_type(_expression_value()) == "expref"


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, False),
        (False, False),
        (0, True),
        (1.5, True),
        (MyInt(2), True),
        (Decimal("1"), True),
        (Fraction(1, 3), True),
        ("1", False),
        (None, False),
        ([1], False),
    ],
)
def test_is_number(value, expected):
    assert types_module().is_number(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("a", True),
        (MyStr("a"), True),
        (1, True),
        (Decimal("1"), True),
        (True, False),
        (None, False),
        ([], False),
        ({}, False),
    ],
)
def test_is_comparable(value, expected):
    assert types_module().is_comparable(value) is expected


def test_functions_module_no_longer_defines_the_tables():
    defined = set()
    for node in module_tree("functions.py").body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)
    assert not defined & {"TYPES_MAP", "REVERSE_TYPES_MAP"}


def test_visitor_no_longer_defines_type_helpers():
    names = {
        node.name for node in module_tree("visitor.py").body if isinstance(node, ast.FunctionDef)
    }
    assert not names & {"_is_actual_number", "_is_comparable"}


def test_types_module_imports_nothing_from_jmespath():
    types_module()
    tree = module_tree("types.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "jmespath" for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert (node.module or "").split(".")[0] != "jmespath"
