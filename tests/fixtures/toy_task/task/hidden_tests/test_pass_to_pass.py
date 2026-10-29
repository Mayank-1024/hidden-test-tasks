from toylib.stats import mean


def test_single_value():
    assert mean([4]) == 4
