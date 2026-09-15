# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.fixture
def spam(spam):
    return spam * 2


def test_spam(spam):
    assert spam == "spamspam"
