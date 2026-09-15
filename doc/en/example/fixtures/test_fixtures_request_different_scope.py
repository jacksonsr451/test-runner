from __future__ import annotations

import testrunner


@testrunner.fixture
def order():
    return []


@testrunner.fixture
def outer(order, inner):
    order.append("outer")


class TestOne:
    @testrunner.fixture
    def inner(self, order):
        order.append("one")

    def test_order(self, order, outer):
        assert order == ["one", "outer"]


class TestTwo:
    @testrunner.fixture
    def inner(self, order):
        order.append("two")

    def test_order(self, order, outer):
        assert order == ["two", "outer"]
