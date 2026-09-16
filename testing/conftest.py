# mypy: allow-untyped-defs
from __future__ import annotations

from collections.abc import Generator
import importlib.metadata
import re
import sys

from packaging.version import Version

from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.testrunnerer import Testrunnerer
import testrunner


if sys.gettrace():

    @testrunner.fixture(autouse=True)
    def restore_tracing():
        """Restore tracing function (when run with Coverage.py).

        https://bugs.python.org/issue37011
        """
        orig_trace = sys.gettrace()
        yield
        if sys.gettrace() != orig_trace:
            sys.settrace(orig_trace)


@testrunner.fixture(autouse=True)
def set_column_width(monkeypatch: testrunner.MonkeyPatch) -> None:
    """
    Force terminal width to 80: some tests check the formatting of --help, which is sensible
    to terminal width.
    """
    monkeypatch.setenv("COLUMNS", "80")


@testrunner.fixture(autouse=True)
def reset_colors(monkeypatch: testrunner.MonkeyPatch) -> None:
    """
    Reset all color-related variables to prevent them from affecting internal testrunner output
    in tests that depend on it.
    """
    monkeypatch.delenv("PY_COLORS", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)


@testrunner.hookimpl(wrapper=True, tryfirst=True)
def testrunner_collection_modifyitems(items) -> Generator[None]:
    """Prefer faster tests.

    Use a hook wrapper to do this in the beginning, so e.g. --ff still works
    correctly.
    """
    fast_items = []
    slow_items = []
    slowest_items = []
    neutral_items = []

    spawn_names = {"spawn_testrunner", "spawn"}

    for item in items:
        try:
            fixtures = item.fixturenames
        except AttributeError:
            # doctest at least
            # (https://github.com/jacksonsr451/test-runner/issues/5070)
            neutral_items.append(item)
        else:
            if "testrunnerer" in fixtures:
                co_names = item.function.__code__.co_names
                if spawn_names.intersection(co_names):
                    item.add_marker(testrunner.mark.uses_pexpect)
                    slowest_items.append(item)
                elif "runtestrunner_subprocess" in co_names:
                    slowest_items.append(item)
                else:
                    slow_items.append(item)
                item.add_marker(testrunner.mark.slow)
            else:
                marker = item.get_closest_marker("slow")
                if marker:
                    slowest_items.append(item)
                else:
                    fast_items.append(item)

    items[:] = fast_items + neutral_items + slow_items + slowest_items

    return (yield)


@testrunner.fixture
def tw_mock():
    """Returns a mock terminal writer"""

    class TWMock:
        WRITE = object()

        def __init__(self):
            self.lines = []
            self.is_writing = False

        def sep(self, sep, line=None):
            self.lines.append((sep, line))

        def write(self, msg, **kw):
            self.lines.append((TWMock.WRITE, msg))

        def _write_source(self, lines, indents=()):
            if not indents:
                indents = [""] * len(lines)
            for indent, line in zip(indents, lines, strict=True):
                self.line(indent + line)

        def line(self, line, **kw):
            self.lines.append(line)

        def markup(self, text, **kw):
            return text

        def get_write_msg(self, idx):
            assert self.lines[idx][0] == TWMock.WRITE
            msg = self.lines[idx][1]
            return msg

        fullwidth = 80

    return TWMock()


@testrunner.fixture
def dummy_yaml_custom_test(testrunnerer: Testrunnerer) -> None:
    """Writes a conftest file that collects and executes a dummy yaml test.

    Taken from the docs, but stripped down to the bare minimum, useful for
    tests which needs custom items collected.
    """
    testrunnerer.makeconftest(
        """
        import testrunner

        def testrunner_collect_file(parent, file_path):
            if file_path.suffix == ".yaml" and file_path.name.startswith("test"):
                return YamlFile.from_parent(path=file_path, parent=parent)

        class YamlFile(testrunner.File):
            def collect(self):
                yield YamlItem.from_parent(name=self.path.name, parent=self)

        class YamlItem(testrunner.Item):
            def runtest(self):
                pass
    """
    )
    testrunnerer.makefile(".yaml", test1="")


@testrunner.fixture
def testrunnerer(testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch) -> Testrunnerer:
    monkeypatch.setenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", "1")
    return testrunnerer


@testrunner.fixture(scope="session")
def color_mapping():
    """Returns a utility class which can replace keys in strings in the form "{NAME}"
    by their equivalent ASCII codes in the terminal.

    Used by tests which check the actual colors output by testrunner.
    """
    # https://github.com/pygments/pygments/commit/d24e272894a56a98b1b718d9ac5fabc20124882a
    pygments_version = Version(importlib.metadata.version("pygments"))
    pygments_has_kwspace_hl = pygments_version >= Version("2.19")

    class ColorMapping:
        COLORS = {
            "red": "\x1b[31m",
            "green": "\x1b[32m",
            "yellow": "\x1b[33m",
            "light-gray": "\x1b[90m",
            "light-red": "\x1b[91m",
            "light-green": "\x1b[92m",
            "bold": "\x1b[1m",
            "reset": "\x1b[0m",
            "kw": "\x1b[94m",
            "kwspace": "\x1b[90m \x1b[39;49;00m" if pygments_has_kwspace_hl else " ",
            "hl-reset": "\x1b[39;49;00m",
            "function": "\x1b[92m",
            "number": "\x1b[94m",
            "str": "\x1b[33m",
            "print": "\x1b[96m",
            "endline": "\x1b[90m\x1b[39;49;00m",
        }
        RE_COLORS = {k: re.escape(v) for k, v in COLORS.items()}
        NO_COLORS = {k: "" for k in COLORS}

        @classmethod
        def format(cls, lines: list[str]) -> list[str]:
            """Straightforward replacement of color names to their ASCII codes."""
            return [line.format(**cls.COLORS) for line in lines]

        @classmethod
        def format_for_fnmatch(cls, lines: list[str]) -> list[str]:
            """Replace color names for use with LineMatcher.fnmatch_lines"""
            return [line.format(**cls.COLORS).replace("[", "[[]") for line in lines]

        @classmethod
        def format_for_rematch(cls, lines: list[str]) -> list[str]:
            """Replace color names for use with LineMatcher.re_match_lines"""
            return [line.format(**cls.RE_COLORS) for line in lines]

        @classmethod
        def strip_colors(cls, lines: list[str]) -> list[str]:
            """Entirely remove every color code"""
            return [line.format(**cls.NO_COLORS) for line in lines]

    return ColorMapping


@testrunner.fixture
def mock_timing(monkeypatch: MonkeyPatch):
    """Mocks _testrunner.timing with a known object that can be used to control timing in tests
    deterministically.

    testrunner itself should always use functions from `_testrunner.timing` instead of `time` directly.

    This then allows us more control over time during testing, if testing code also
    uses `_testrunner.timing` functions.

    Time is static, and only advances through `sleep` calls, thus tests might sleep over large
    numbers and obtain accurate time() calls at the end, making tests reliable and instant.
    """
    from _testrunner.timing import MockTiming

    result = MockTiming()
    result.patch(monkeypatch)
    return result


@testrunner.fixture(autouse=True)
def remove_ci_env_var(
    monkeypatch: MonkeyPatch, request: testrunner.FixtureRequest
) -> None:
    """Make the test insensitive if it is running in CI or not.

    Use `@testrunner.mark.keep_ci_var` in a test to avoid applying this fixture, letting the test
    see the real `CI` variable (if present).
    """
    has_keep_ci_mark = request.node.get_closest_marker("keep_ci_var") is not None
    if not has_keep_ci_mark:
        monkeypatch.delenv("CI", raising=False)
