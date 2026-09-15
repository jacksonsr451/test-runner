# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


def test_foo():
    assert True


@testrunner.mark.parametrize("i", range(3))
def test_bar(i):
    assert True
