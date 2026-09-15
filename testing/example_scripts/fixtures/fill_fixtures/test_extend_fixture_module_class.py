# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.fixture
def spam():
    return "spam"


class TestSpam:
    @testrunner.fixture
    def spam(self, spam):
        return spam * 2

    def test_spam(self, spam):
        assert spam == "spamspam"
