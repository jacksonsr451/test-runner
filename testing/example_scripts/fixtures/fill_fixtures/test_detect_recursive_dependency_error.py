# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.fixture
def fix1(fix2):
    return 1


@testrunner.fixture
def fix2(fix1):
    return 1


def test(fix1):
    pass
