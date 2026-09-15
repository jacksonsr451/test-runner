from __future__ import annotations

import testrunner


SKIP = True


@testrunner.mark.parametrize("x", range(5000))
def test_foo(x):
    if SKIP:
        testrunner.skip("heh")
