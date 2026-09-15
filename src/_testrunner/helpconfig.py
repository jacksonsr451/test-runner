# mypy: allow-untyped-defs
"""Version info, help messages, tracing configuration."""

from __future__ import annotations

import argparse
from collections.abc import Generator
from collections.abc import Sequence
import os
import sys
from typing import Any

from _testrunner.config import Config
from _testrunner.config import ExitCode
from _testrunner.config import PrintHelp
from _testrunner.config.argparsing import _ini_type_repr
from _testrunner.config.argparsing import Parser
from _testrunner.terminal import TerminalReporter
import testrunner


class HelpAction(argparse.Action):
    """An argparse Action that will raise a PrintHelp exception in order to skip
    the rest of the argument parsing when --help is passed.

    This prevents argparse from raising UsageError when `--help` is used along
    with missing required arguments when any are defined, for example by
    ``testrunner_addoption``. This is similar to the way that the builtin argparse
    --help option is implemented by raising SystemExit.

    To opt in to this behavior, the parse caller must set
    `namespace._raise_print_help = True`. Otherwise it just sets the option.
    """

    def __init__(
        self, option_strings: Sequence[str], dest: str, *, help: str | None = None
    ) -> None:
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=True,
            default=False,
            help=help,
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        setattr(namespace, self.dest, self.const)

        if getattr(namespace, "_raise_print_help", False):
            raise PrintHelp


def testrunner_addoption(parser: Parser) -> None:
    group = parser.getgroup("debugconfig")
    group.addoption(
        "-V",
        "--version",
        action="count",
        default=0,
        dest="version",
        help="Display testrunner version and information about plugins. "
        "When given twice, also display information about plugins.",
    )
    group._addoption(  # private to use reserved lower-case short option
        "-h",
        "--help",
        action=HelpAction,
        dest="help",
        help="Show help message and configuration info",
    )
    group._addoption(  # private to use reserved lower-case short option
        "-p",
        action="append",
        dest="plugins",
        default=[],
        metavar="name",
        help="Early-load given plugin module name or entry point (multi-allowed). "
        "To avoid loading of plugins, use the `no:` prefix, e.g. "
        "`no:doctest`. See also --disable-plugin-autoload.",
    )
    group.addoption(
        "--disable-plugin-autoload",
        action="store_true",
        default=False,
        help="Disable plugin auto-loading through entry point packaging metadata. "
        "Only plugins explicitly specified in -p or env var TESTRUNNER_PLUGINS will be loaded.",
    )
    group.addoption(
        "--traceconfig",
        "--trace-config",
        action="store_true",
        default=False,
        help="Trace considerations of conftest.py files",
    )
    group.addoption(
        "--debug",
        action="store",
        nargs="?",
        const="testrunnerdebug.log",
        dest="debug",
        metavar="DEBUG_FILE_NAME",
        help="Store internal tracing debug information in this log file. "
        "This file is opened with 'w' and truncated as a result, care advised. "
        "Default: testrunnerdebug.log.",
    )
    group._addoption(  # private to use reserved lower-case short option
        "-o",
        "--override-ini",
        dest="override_ini",
        action="append",
        help='Override configuration option with "option=value" style, '
        "e.g. `-o strict_xfail=True -o cache_dir=cache`.",
    )


@testrunner.hookimpl(wrapper=True)
def testrunner_cmdline_parse() -> Generator[None, Config, Config]:
    config = yield

    if config.option.debug:
        # --debug | --debug <file.log> was provided.
        path = config.option.debug
        debugfile = open(path, "w", encoding="utf-8")
        debugfile.write(
            "versions testrunner-{}, "
            "python-{}\ninvocation_dir={}\ncwd={}\nargs={}\n\n".format(
                testrunner.__version__,
                ".".join(map(str, sys.version_info)),
                config.invocation_params.dir,
                os.getcwd(),
                config.invocation_params.args,
            )
        )
        config.trace.root.setwriter(debugfile.write)
        undo_tracing = config.pluginmanager.enable_tracing()
        sys.stderr.write(f"writing testrunner debug information to {path}\n")

        def unset_tracing() -> None:
            debugfile.close()
            sys.stderr.write(f"wrote testrunner debug information to {debugfile.name}\n")
            config.trace.root.setwriter(None)
            undo_tracing()

        config.add_cleanup(unset_tracing)

    return config


def show_version_verbose(config: Config) -> None:
    """Show verbose testrunner version installation, including plugins."""
    sys.stdout.write(
        f"This is testrunner version {testrunner.__version__}, imported from {testrunner.__file__}\n"
    )
    plugininfo = getpluginversioninfo(config)
    if plugininfo:
        for line in plugininfo:
            sys.stdout.write(line + "\n")


def testrunner_cmdline_main(config: Config) -> int | ExitCode | None:
    # Note: a single `--version` argument is handled directly by `Config.main()` to avoid starting up the entire
    # testrunner infrastructure just to display the version (#13574).
    if config.option.version > 1:
        show_version_verbose(config)
        return ExitCode.OK
    elif config.option.help:
        config._do_configure()
        showhelp(config)
        config._ensure_unconfigure()
        return ExitCode.OK
    return None


def showhelp(config: Config) -> None:
    import textwrap

    reporter: TerminalReporter | None = config.pluginmanager.get_plugin(
        "terminalreporter"
    )
    assert reporter is not None
    tw = reporter._tw
    tw.write(config._parser.optparser.format_help())
    tw.line()
    tw.line(
        "[testrunner] configuration options in the first "
        "testrunner.toml|testrunner.ini|tox.ini|setup.cfg|pyproject.toml file found:"
    )
    tw.line()

    columns = tw.fullwidth  # costly call
    indent_len = 24  # based on argparse's max_help_position=24
    indent = " " * indent_len
    for name in config._parser._inidict:
        help, type, _default = config._parser._inidict[name]
        if help is None:
            raise TypeError(f"help argument cannot be None for {name}")
        spec = f"{name} ({_ini_type_repr(type)}):"
        tw.write(f"  {spec}")
        spec_len = len(spec)
        if spec_len > (indent_len - 3):
            # Display help starting at a new line.
            tw.line()
            helplines = textwrap.wrap(
                help,
                columns,
                initial_indent=indent,
                subsequent_indent=indent,
                break_on_hyphens=False,
            )

            for line in helplines:
                tw.line(line)
        else:
            # Display help starting after the spec, following lines indented.
            tw.write(" " * (indent_len - spec_len - 2))
            wrapped = textwrap.wrap(help, columns - indent_len, break_on_hyphens=False)

            if wrapped:
                tw.line(wrapped[0])
                for line in wrapped[1:]:
                    tw.line(indent + line)

    tw.line()
    tw.line("Environment variables:")
    vars = [
        (
            "CI",
            "When set to a non-empty value, testrunner knows it is running in a "
            "CI process and does not truncate summary info",
        ),
        ("BUILD_NUMBER", "Equivalent to CI"),
        ("TESTRUNNER_ADDOPTS", "Extra command line options"),
        ("TESTRUNNER_PLUGINS", "Comma-separated plugins to load during startup"),
        ("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", "Set to disable plugin auto-loading"),
        ("TESTRUNNER_DEBUG", "Set to enable debug tracing of testrunner's internals"),
        ("TESTRUNNER_DEBUG_TEMPROOT", "Override the system temporary directory"),
        ("TESTRUNNER_THEME", "The Pygments style to use for code output"),
        ("TESTRUNNER_THEME_MODE", "Set the TESTRUNNER_THEME to be either 'dark' or 'light'"),
    ]
    for name, help in vars:
        tw.line(f"  {name:<24} {help}")
    tw.line()
    tw.line()

    tw.line("to see available markers type: testrunner --markers")
    tw.line("to see available fixtures type: testrunner --fixtures")
    tw.line(
        "(shown according to specified file_or_dir or current dir "
        "if not specified; fixtures with leading '_' are only shown "
        "with the '-v' option"
    )

    for warningreport in reporter.stats.get("warnings", []):
        tw.line("warning : " + warningreport.message, red=True)


def getpluginversioninfo(config: Config) -> list[str]:
    lines = []
    plugininfo = config.pluginmanager.list_plugin_distinfo()
    if plugininfo:
        lines.append("registered third-party plugins:")
        for plugin, dist in plugininfo:
            loc = getattr(plugin, "__file__", repr(plugin))
            content = f"{dist.project_name}-{dist.version} at {loc}"
            lines.append("  " + content)
    return lines


def testrunner_report_header(config: Config) -> list[str]:
    lines = []
    if config.option.debug or config.option.traceconfig:
        lines.append(f"using: testrunner-{testrunner.__version__}")

        verinfo = getpluginversioninfo(config)
        if verinfo:
            lines.extend(verinfo)

    if config.option.traceconfig:
        lines.append("active plugins:")
        items = config.pluginmanager.list_name_plugin()
        for name, plugin in items:
            if hasattr(plugin, "__file__"):
                r = plugin.__file__
            else:
                r = repr(plugin)
            lines.append(f"    {name:<20}: {r}")
    return lines
