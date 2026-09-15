# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


class TestClass:
    @testrunner.fixture
    def something(self, request):
        return request.instance

    def test_method(self, something):
        assert something is self
