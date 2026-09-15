from __future__ import annotations

import os.path

import testrunner


mydir = os.path.dirname(__file__)


def testrunner_runtest_setup(item):
    if isinstance(item, testrunner.Function):
        if not item.fspath.relto(mydir):
            return
        mod = item.getparent(testrunner.Module).obj
        if hasattr(mod, "hello"):
            print(f"mod.hello {mod.hello!r}")
