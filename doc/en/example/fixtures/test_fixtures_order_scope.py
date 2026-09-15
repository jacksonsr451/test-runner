from __future__ import annotations

import testrunner


@testrunner.fixture(scope="session")
def order():
    return []


@testrunner.fixture
def func(order):
    order.append("function")


@testrunner.fixture(scope="class")
def cls(order):
    order.append("class")


@testrunner.fixture(scope="module")
def mod(order):
    order.append("module")


@testrunner.fixture(scope="package")
def pack(order):
    order.append("package")


@testrunner.fixture(scope="session")
def sess(order):
    order.append("session")


class TestClass:
    def test_order(self, func, cls, mod, pack, sess, order):
        assert order == ["session", "package", "module", "class", "function"]
