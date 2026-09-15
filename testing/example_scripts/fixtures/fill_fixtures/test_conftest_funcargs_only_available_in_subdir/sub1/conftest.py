# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.fixture
def arg1(request):
    with testrunner.raises(testrunner.FixtureLookupError):
        request.getfixturevalue("arg2")
