from __future__ import annotations

import testrunner


@testrunner.fixture
def order():
    return []


@testrunner.fixture
def c1(order):
    order.append("c1")


@testrunner.fixture
def c2(order):
    order.append("c2")


class TestClassWithAutouse:
    @testrunner.fixture(autouse=True)
    def c3(self, order, c2):
        order.append("c3")

    def test_req(self, order, c1):
        assert order == ["c2", "c3", "c1"]

    def test_no_req(self, order):
        assert order == ["c2", "c3"]


class TestClassWithoutAutouse:
    def test_req(self, order, c1):
        assert order == ["c1"]

    def test_no_req(self, order):
        assert order == []
