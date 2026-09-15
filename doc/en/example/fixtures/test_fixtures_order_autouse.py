from __future__ import annotations

import testrunner


@testrunner.fixture
def order():
    return []


@testrunner.fixture
def a(order):
    order.append("a")


@testrunner.fixture
def b(a, order):
    order.append("b")


@testrunner.fixture(autouse=True)
def c(b, order):
    order.append("c")


@testrunner.fixture
def d(b, order):
    order.append("d")


@testrunner.fixture
def e(d, order):
    order.append("e")


@testrunner.fixture
def f(e, order):
    order.append("f")


@testrunner.fixture
def g(f, c, order):
    order.append("g")


def test_order_and_g(g, order):
    assert order == ["a", "b", "c", "d", "e", "f", "g"]
