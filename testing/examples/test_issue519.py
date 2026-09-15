from __future__ import annotations

from _testrunner.testrunnerer import Testrunnerer


def test_519(testrunnerer: Testrunnerer) -> None:
    testrunnerer.copy_example("issue_519.py")
    res = testrunnerer.runtestrunner("issue_519.py")
    res.assert_outcomes(passed=8)
