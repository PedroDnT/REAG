"""Detection-quality evaluation harness.

Distinct from the unit tests. Tests check that a detector behaves as written;
these measure whether it actually detects, by running it over synthetic fund
universes with known injected fraud and scoring the result against ground truth.
"""
