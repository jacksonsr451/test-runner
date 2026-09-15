"""TestRunner bootstrap for pytest-xdist's execnet worker protocol.

The xdist remote module is intentionally self-contained because execnet sends
its source to a worker.  We adapt that source at this one process boundary so
the worker starts TestRunner rather than the unrelated upstream pytest package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _testrunner_remote_source() -> str:
    spec = importlib.util.find_spec("xdist.remote")
    if spec is None or spec.origin is None:
        raise ImportError("pytest-xdist remote module is not available")
    source = Path(spec.origin).read_text(encoding="utf-8")
    source = source.replace("from _pytest.config import _prepareconfig", "from _testrunner.config import _prepareconfig")
    source = source.replace("import pytest", "import testrunner as pytest")
    source = source.replace(".hook.pytest_", ".hook.testrunner_")
    source = source.replace(
        "    config = _prepareconfig(args, None)",
        '    os.environ["TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD"] = "1"\n'
        "    import xdist.plugin\n"
        "    config = _prepareconfig(args, [xdist.plugin])",
    )
    return source


if __name__ == "__channelexec__":
    exec(compile(_testrunner_remote_source(), "xdist.remote", "exec"))
