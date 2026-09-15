# mypy: allow-untyped-defs
from __future__ import annotations


def testrunner_configure(config):
    import testrunner

    raise testrunner.UsageError("hello")


def testrunner_unconfigure(config):
    print("testrunner_unconfigure_called")
