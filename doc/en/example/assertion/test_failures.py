from __future__ import annotations

import os.path
import shutil


failure_demo = os.path.join(os.path.dirname(__file__), "failure_demo.py")
testrunner_plugins = ("testrunnerer",)


def test_failure_demo_fails_properly(testrunnerer):
    target = testrunnerer.path.joinpath(os.path.basename(failure_demo))
    shutil.copy(failure_demo, target)
    result = testrunnerer.runtestrunner(target, syspathinsert=True)
    result.stdout.fnmatch_lines(["*44 failed*"])
    assert result.ret != 0
