"""TestRunner bootstrap for pytest-xdist's execnet worker protocol.

The xdist remote module is intentionally self-contained because execnet sends
its source to a worker.  We adapt that source at this one process boundary so
the worker starts TestRunner rather than the unrelated upstream pytest package.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
from pathlib import Path


def _replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            "pytest-xdist 3.8.0 compatibility bootstrap is incompatible with "
            f"the installed xdist.remote source: expected one {old!r}, found {count}"
        )
    return source.replace(old, new)


def _replace_expected(source: str, old: str, new: str, expected: int) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(
            "pytest-xdist 3.8.0 compatibility bootstrap is incompatible with "
            f"the installed xdist.remote source: expected {expected} {old!r}, "
            f"found {count}"
        )
    return source.replace(old, new)


def _testrunner_remote_source() -> str:
    version = importlib.metadata.version("pytest-xdist")
    if version != "3.8.0":
        raise RuntimeError(
            "TestRunner's xdist compatibility bootstrap supports pytest-xdist "
            f"3.8.0, found {version}"
        )
    spec = importlib.util.find_spec("xdist.remote")
    if spec is None or spec.origin is None:
        raise ImportError("pytest-xdist remote module is not available")
    source = Path(spec.origin).read_text(encoding="utf-8")
    source = _replace_once(
        source,
        "from _pytest.config import _prepareconfig",
        "from _testrunner.config import _prepareconfig",
    )
    source = _replace_once(source, "import pytest", "import testrunner as pytest")
    source = _replace_expected(source, ".hook.pytest_", ".hook.testrunner_", 4)
    source = _replace_once(
        source,
        "    config = _prepareconfig(args, None)",
        '    os.environ["TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD"] = "1"\n'
        "    import xdist.plugin\n"
        "    config = _prepareconfig(args, [xdist.plugin])\n"
        "    config.workerinput = workerinput\n"
        "    config.workeroutput = {}",
    )
    return source


if __name__ == "__channelexec__":
    exec(compile(_testrunner_remote_source(), "xdist.remote", "exec"))
