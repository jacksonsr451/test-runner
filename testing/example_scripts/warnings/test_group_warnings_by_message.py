# mypy: allow-untyped-defs
from __future__ import annotations

import warnings

import testrunner


def func(msg):
    warnings.warn(UserWarning(msg))


@testrunner.mark.parametrize("i", range(5))
def test_foo(i):
    func("foo")


def test_foo_1():
    func("foo")


@testrunner.mark.parametrize("i", range(5))
def test_bar(i):
    func("bar")
