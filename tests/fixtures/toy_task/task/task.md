# Bug: mean() of an empty list raises ZeroDivisionError

`toylib.stats.mean([])` should return `None` instead of raising.
