# mypy: allow-untyped-defs
from __future__ import annotations

from _testrunner.fixtures import FixtureLookupError
import testrunner


@testrunner.fixture
def arg2(request):
    with testrunner.raises(FixtureLookupError):
        request.getfixturevalue("arg1")
