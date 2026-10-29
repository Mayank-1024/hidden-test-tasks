from toylib.stats import mean


def test_mean():
    assert mean([1, 2, 3]) == 2


def test_mean_float():
    assert mean([1, 2]) == 1.5
