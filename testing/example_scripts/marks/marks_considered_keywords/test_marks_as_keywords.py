# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.mark.foo
def test_mark():
    pass
