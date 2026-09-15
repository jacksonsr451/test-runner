# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.fixture
def some(request):
    return request.function.__name__


@testrunner.fixture
def other(request):
    return 42


def test_func(some, other):
    pass
