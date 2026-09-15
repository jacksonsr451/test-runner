# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.fixture
def request():
    pass


def test():
    pass
