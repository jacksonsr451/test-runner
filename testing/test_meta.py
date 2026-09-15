"""Test importing of all internal packages and modules.

This ensures all internal packages can be imported without needing the testrunner
namespace being set, which is critical for the initialization of xdist.
"""

from __future__ import annotations

import pkgutil
import subprocess
import sys

import _testrunner
import testrunner


def _modules() -> list[str]:
    testrunner_pkg: str = _testrunner.__path__  # type: ignore
    return sorted(
        n
        for _, n, _ in pkgutil.walk_packages(testrunner_pkg, prefix=_testrunner.__name__ + ".")
    )


@testrunner.mark.slow
@testrunner.mark.parametrize("module", _modules())
def test_no_warnings(module: str) -> None:
    # fmt: off
    subprocess.check_call((
        sys.executable,
        "-W", "error",
        "-c", f"__import__({module!r})",
    ))
    # fmt: on
