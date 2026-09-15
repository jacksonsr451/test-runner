# mypy: allow-untyped-defs
from __future__ import annotations

import unittest

import testrunner


@testrunner.fixture(params=[1, 2])
def two(request):
    return request.param


@testrunner.mark.usefixtures("two")
class TestSomethingElse(unittest.TestCase):
    def test_two(self):
        pass
