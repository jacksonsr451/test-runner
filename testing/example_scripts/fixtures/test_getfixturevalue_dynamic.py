# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


@testrunner.fixture
def dynamic():
    pass


@testrunner.fixture
def a(request):
    request.getfixturevalue("dynamic")


@testrunner.fixture
def b(a):
    pass


def test(b, request):
    assert request.fixturenames == ["b", "a", "request", "dynamic"]
