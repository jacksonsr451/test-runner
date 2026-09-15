# mypy: allow-untyped-defs
from __future__ import annotations

from _testrunner.config import ExitCode
from _testrunner.testrunnerer import Testrunnerer
import testrunner


def test_version_verbose(testrunnerer: Testrunnerer, testrunnerconfig, monkeypatch) -> None:
    monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD")
    monkeypatch.delenv("TESTRUNNER_PLUGINS", raising=False)
    result = testrunnerer.runtestrunner("--version", "--version")
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines([f"*testrunner*{testrunner.__version__}*imported from*"])
    if testrunnerconfig.pluginmanager.list_plugin_distinfo():
        result.stdout.fnmatch_lines(["*registered third-party plugins:", "*at*"])


@testrunner.mark.parametrize("flag", ["--version", "-V"])
def test_version_less_verbose(testrunnerer: Testrunnerer, flag: str) -> None:
    """Single ``--version`` or ``-V`` should display only the testrunner version, without loading plugins (#13574)."""
    testrunnerer.makeconftest("print('This should not be printed')")
    result = testrunnerer.runtestrunner_subprocess(flag)
    assert result.ret == ExitCode.OK
    assert result.stdout.str().strip() == f"testrunner {testrunner.__version__}"


def test_versions() -> None:
    """Regression check for the public version attributes in testrunner."""
    assert isinstance(testrunner.__version__, str)
    assert isinstance(testrunner.version_tuple, tuple)


def test_help(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("--help")
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(
        """
          -m MARKEXPR           Only run tests matching given mark expression. For
                                example: -m 'mark1 and not mark2'.
        Reporting:
          --durations=N *
          -V, --version         Display testrunner version and information about plugins.
                                When given twice, also display information about
                                plugins.
        *setup.cfg*
        *minversion*
        *to see*markers*testrunner --markers*
        *to see*fixtures*testrunner --fixtures*
    """
    )


def test_help_ini_union_and_literal_types(testrunnerer: Testrunnerer) -> None:
    """Union and Literal ini options display their members/choices in --help."""
    testrunnerer.makeconftest(
        """
        from typing import Literal

        def testrunner_addoption(parser):
            parser.addini("ini_union", "union help", type=int | str, default=None)
            parser.addini(
                "ini_literal", "literal help", type=Literal["auto", "long"],
                default="auto",
            )
            parser.addini(
                "ini_mixed", "mixed help", type=int | Literal["auto"],
                default="auto",
            )
    """
    )
    result = testrunnerer.runtestrunner("--help")
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(
        [
            "*ini_union (int | string):*",
            "*union help*",
            "*ini_literal ('auto' | 'long'):*",
            "*literal help*",
            "*ini_mixed (int | 'auto'):*",
            "*mixed help*",
        ]
    )


def test_none_help_param_raises_exception(testrunnerer: Testrunnerer) -> None:
    """Test that a None help param raises a TypeError."""
    testrunnerer.makeconftest(
        """
        def testrunner_addoption(parser):
            parser.addini("test_ini", None, default=True, type="bool")
    """
    )
    result = testrunnerer.runtestrunner("--help")
    result.stderr.fnmatch_lines(
        ["*TypeError: help argument cannot be None for test_ini*"]
    )


def test_empty_help_param(testrunnerer: Testrunnerer) -> None:
    """Test that an empty help param is displayed correctly."""
    testrunnerer.makeconftest(
        """
        def testrunner_addoption(parser):
            parser.addini("test_ini", "", default=True, type="bool")
    """
    )
    result = testrunnerer.runtestrunner("--help")
    assert result.ret == ExitCode.OK
    lines = [
        "  required_plugins (args):",
        "                        Plugins that must be present for testrunner to run*",
        "  test_ini (bool):*",
        "Environment variables:",
    ]
    result.stdout.fnmatch_lines(lines, consecutive=True)


def test_parse_known_args_doesnt_quit_on_help(testrunnerer: Testrunnerer) -> None:
    """`parse_known_args` shouldn't exit on `--help`, unlike `parse`."""
    config = testrunnerer.parseconfig()
    # Doesn't raise or exit!
    config._parser.parse_known_args(["--help"])
    config._parser.parse_known_and_unknown_args(["--help"])


def test_hookvalidation_unknown(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
        def testrunner_hello(xyz):
            pass
    """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret != ExitCode.OK
    result.stdout.fnmatch_lines(["*unknown hook*testrunner_hello*"])


def test_hookvalidation_optional(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
        import testrunner
        @testrunner.hookimpl(optionalhook=True)
        def testrunner_hello(xyz):
            pass
    """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_traceconfig(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("--traceconfig")
    result.stdout.fnmatch_lines(["*using*testrunner*", "*active plugins*"])


def test_debug(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner_subprocess("--debug")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED
    p = testrunnerer.path.joinpath("testrunnerdebug.log")
    assert "testrunner_sessionstart" in p.read_text("utf-8")


def test_TESTRUNNER_DEBUG(testrunnerer: Testrunnerer, monkeypatch) -> None:
    monkeypatch.setenv("TESTRUNNER_DEBUG", "1")
    result = testrunnerer.runtestrunner_subprocess()
    assert result.ret == ExitCode.NO_TESTS_COLLECTED
    result.stderr.fnmatch_lines(
        ["*testrunner_plugin_registered*", "*manager*PluginManager*"]
    )
