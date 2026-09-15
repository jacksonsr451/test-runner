from __future__ import annotations

import testrunner


xfail = testrunner.mark.xfail


@xfail
def test_hello():
    assert 0


@xfail(run=False)
def test_hello2():
    assert 0


@xfail("hasattr(os, 'sep')")
def test_hello3():
    assert 0


@xfail(reason="bug 110")
def test_hello4():
    assert 0


@xfail('testrunner.__version__[0] != "17"')
def test_hello5():
    assert 0


def test_hello6():
    testrunner.xfail("reason")


@xfail(raises=IndexError)
def test_hello7():
    x = []
    x[1] = 1
