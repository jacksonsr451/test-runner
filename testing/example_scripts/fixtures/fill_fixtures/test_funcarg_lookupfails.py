# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.fixture
def xyzsomething(request):
    return 42


def test_func(some):
    pass
