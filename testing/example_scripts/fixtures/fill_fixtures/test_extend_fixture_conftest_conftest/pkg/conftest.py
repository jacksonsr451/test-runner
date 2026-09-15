# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.fixture
def spam(spam):
    return spam * 2
