from __future__ import annotations

import testrunner


@testrunner.fixture(scope="class")
def order():
    return []


@testrunner.fixture(scope="class", autouse=True)
def c1(order):
    order.append("c1")


@testrunner.fixture(scope="class")
def c2(order):
    order.append("c2")


@testrunner.fixture(scope="class")
def c3(order, c1):
    order.append("c3")


class TestClassWithC1Request:
    def test_order(self, order, c1, c3):
        assert order == ["c1", "c3"]


class TestClassWithoutC1Request:
    def test_order(self, order, c2):
        assert order == ["c1", "c2"]
