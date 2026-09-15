# mypy: allow-untyped-defs
from __future__ import annotations

import sys
from textwrap import dedent

from _testrunner.testrunnerer import Testrunnerer
import testrunner


@testrunner.fixture()
def file_structure(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_foo="""
        from foo import foo

        def test_foo():
            assert foo() == 1
        """
    )

    testrunnerer.makepyfile(
        test_bar="""
        from bar import bar

        def test_bar():
            assert bar() == 2
        """
    )

    foo_py = testrunnerer.mkdir("sub") / "foo.py"
    content = dedent(
        """
        def foo():
            return 1
        """
    )
    foo_py.write_text(content, encoding="utf-8")

    bar_py = testrunnerer.mkdir("sub2") / "bar.py"
    content = dedent(
        """
        def bar():
            return 2
        """
    )
    bar_py.write_text(content, encoding="utf-8")


def test_one_dir(testrunnerer: Testrunnerer, file_structure) -> None:
    testrunnerer.makefile(".ini", testrunner="[testrunner]\npythonpath=sub\n")
    result = testrunnerer.runtestrunner("test_foo.py")
    assert result.ret == 0
    result.assert_outcomes(passed=1)


def test_two_dirs(testrunnerer: Testrunnerer, file_structure) -> None:
    testrunnerer.makefile(".ini", testrunner="[testrunner]\npythonpath=sub sub2\n")
    result = testrunnerer.runtestrunner("test_foo.py", "test_bar.py")
    assert result.ret == 0
    result.assert_outcomes(passed=2)


def test_local_plugin(testrunnerer: Testrunnerer, file_structure) -> None:
    """`pythonpath` kicks early enough to load plugins via -p (#11118)."""
    localplugin_py = testrunnerer.path / "sub" / "localplugin.py"
    content = dedent(
        """
        def testrunner_load_initial_conftests():
            print("local plugin load")

        def testrunner_unconfigure():
            print("local plugin unconfig")
        """
    )
    localplugin_py.write_text(content, encoding="utf-8")

    testrunnerer.makeini("[testrunner]\npythonpath=sub\n")
    result = testrunnerer.runtestrunner("-plocalplugin", "-s", "test_foo.py")
    result.stdout.fnmatch_lines(["local plugin load", "local plugin unconfig"])
    assert result.ret == 0
    result.assert_outcomes(passed=1)


def test_module_not_found(testrunnerer: Testrunnerer, file_structure) -> None:
    """Without the pythonpath setting, the module should not be found."""
    testrunnerer.makefile(".ini", testrunner="[testrunner]\n")
    result = testrunnerer.runtestrunner("test_foo.py")
    assert result.ret == testrunner.ExitCode.INTERRUPTED
    result.assert_outcomes(errors=1)
    expected_error = "E   ModuleNotFoundError: No module named 'foo'"
    result.stdout.fnmatch_lines([expected_error])


def test_no_config_file(testrunnerer: Testrunnerer, file_structure) -> None:
    """If no configuration file, test should error."""
    result = testrunnerer.runtestrunner("test_foo.py")
    assert result.ret == testrunner.ExitCode.INTERRUPTED
    result.assert_outcomes(errors=1)
    expected_error = "E   ModuleNotFoundError: No module named 'foo'"
    result.stdout.fnmatch_lines([expected_error])


def test_clean_up(testrunnerer: Testrunnerer) -> None:
    """Test that the plugin cleans up after itself."""
    # This is tough to test behaviorally because the cleanup really runs last.
    # So the test make several implementation assumptions:
    # - Cleanup is done in testrunner_unconfigure().
    # - Not a hook wrapper.
    # So we can add a hook wrapper ourselves to test what it does.
    testrunnerer.makefile(".ini", testrunner="[testrunner]\npythonpath=I_SHALL_BE_REMOVED\n")
    testrunnerer.makepyfile(test_foo="""def test_foo(): pass""")

    before: list[str] | None = None
    after: list[str] | None = None

    class Plugin:
        @testrunner.hookimpl(tryfirst=True)
        def testrunner_unconfigure(self) -> None:
            nonlocal before
            before = sys.path.copy()

    result = testrunnerer.runtestrunner_inprocess(plugins=[Plugin()])
    after = sys.path.copy()
    assert result.ret == 0

    assert before is not None
    assert after is not None
    assert any("I_SHALL_BE_REMOVED" in entry for entry in before)
    assert not any("I_SHALL_BE_REMOVED" in entry for entry in after)
