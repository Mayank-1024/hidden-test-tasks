from toylib.stats import mean


def test_empty_returns_none():
    assert mean([]) is None


def test_empty_tuple_returns_none():
    assert mean(()) is None
