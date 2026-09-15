# shim for pylib going away
# if pylib is installed this file will get skipped
# (`py/__init__.py` has higher precedence)
from __future__ import annotations

import sys

import _testrunner._py.error as error
import _testrunner._py.path as path


sys.modules["py.error"] = error
sys.modules["py.path"] = path

__all__ = ["error", "path"]
