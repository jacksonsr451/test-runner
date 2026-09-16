# mypy: allow-untyped-defs
from __future__ import annotations

import io
import os
import re
from typing import cast

from _testrunner.capture import CaptureManager
from _testrunner.config import ExitCode
from _testrunner.fixtures import FixtureRequest
from _testrunner.terminal import TerminalReporter
from _testrunner.testrunnerer import Testrunnerer
import testrunner


def test_nothing_logged(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import sys

        def test_foo():
            sys.stdout.write('text going to stdout')
            sys.stderr.write('text going to stderr')
            assert False
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 1
    result.stdout.fnmatch_lines(["*- Captured stdout call -*", "text going to stdout"])
    result.stdout.fnmatch_lines(["*- Captured stderr call -*", "text going to stderr"])
    with testrunner.raises(testrunner.fail.Exception):
        result.stdout.fnmatch_lines(["*- Captured *log call -*"])


def test_messages_logged(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import sys
        import logging

        logger = logging.getLogger(__name__)

        def test_foo():
            sys.stdout.write('text going to stdout')
            sys.stderr.write('text going to stderr')
            logger.info('text going to logger')
            assert False
        """
    )
    result = testrunnerer.runtestrunner("--log-level=INFO")
    assert result.ret == 1
    result.stdout.fnmatch_lines(["*- Captured *log call -*", "*text going to logger*"])
    result.stdout.fnmatch_lines(["*- Captured stdout call -*", "text going to stdout"])
    result.stdout.fnmatch_lines(["*- Captured stderr call -*", "text going to stderr"])


def test_root_logger_affected(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import logging
        logger = logging.getLogger()

        def test_foo():
            logger.info('info text ' + 'going to logger')
            logger.warning('warning text ' + 'going to logger')
            logger.error('error text ' + 'going to logger')

            assert 0
    """
    )
    log_file = str(testrunnerer.path.joinpath("testrunner.log"))
    result = testrunnerer.runtestrunner(
        "--log-level=ERROR", "--log-file=testrunner.log"
    )
    assert result.ret == 1

    # The capture log calls in the stdout section only contain the
    # logger.error msg, because of --log-level=ERROR.
    result.stdout.fnmatch_lines(["*error text going to logger*"])
    stdout = result.stdout.str()
    assert "warning text going to logger" not in stdout
    assert "info text going to logger" not in stdout

    # The log file should only contain the error log messages and
    # not the warning or info ones, because the root logger is set to
    # ERROR using --log-level=ERROR.
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "info text going to logger" not in contents
        assert "warning text going to logger" not in contents
        assert "error text going to logger" in contents


def test_log_cli_level_log_level_interaction(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import logging
        logger = logging.getLogger()

        def test_foo():
            logger.debug('debug text ' + 'going to logger')
            logger.info('info text ' + 'going to logger')
            logger.warning('warning text ' + 'going to logger')
            logger.error('error text ' + 'going to logger')
            assert 0
    """
    )

    result = testrunnerer.runtestrunner("--log-cli-level=INFO", "--log-level=ERROR")
    assert result.ret == 1

    result.stdout.fnmatch_lines(
        [
            "*-- live log call --*",
            "*INFO*info text going to logger",
            "*WARNING*warning text going to logger",
            "*ERROR*error text going to logger",
            "=* 1 failed in *=",
        ]
    )
    result.stdout.no_re_match_line("DEBUG")


def test_setup_logging(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import logging

        logger = logging.getLogger(__name__)

        def setup_function(function):
            logger.info('text going to logger from setup')

        def test_foo():
            logger.info('text going to logger from call')
            assert False
    """
    )
    result = testrunnerer.runtestrunner("--log-level=INFO")
    assert result.ret == 1
    result.stdout.fnmatch_lines(
        [
            "*- Captured *log setup -*",
            "*text going to logger from setup*",
            "*- Captured *log call -*",
            "*text going to logger from call*",
        ]
    )


def test_teardown_logging(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import logging

        logger = logging.getLogger(__name__)

        def test_foo():
            logger.info('text going to logger from call')

        def teardown_function(function):
            logger.info('text going to logger from teardown')
            assert False
        """
    )
    result = testrunnerer.runtestrunner("--log-level=INFO")
    assert result.ret == 1
    result.stdout.fnmatch_lines(
        [
            "*- Captured *log call -*",
            "*text going to logger from call*",
            "*- Captured *log teardown -*",
            "*text going to logger from teardown*",
        ]
    )


@testrunner.mark.parametrize("enabled", [True, False])
def test_log_cli_enabled_disabled(testrunnerer: Testrunnerer, enabled: bool) -> None:
    msg = "critical message logged by test"
    testrunnerer.makepyfile(
        f"""
        import logging
        def test_log_cli():
            logging.critical("{msg}")
    """
    )
    if enabled:
        testrunnerer.makeini(
            """
            [testrunner]
            log_cli=true
        """
        )
    result = testrunnerer.runtestrunner()
    if enabled:
        result.stdout.fnmatch_lines(
            [
                "test_log_cli_enabled_disabled.py::test_log_cli ",
                "*-- live log call --*",
                "CRITICAL *test_log_cli_enabled_disabled.py* critical message logged by test",
                "PASSED*",
            ]
        )
    else:
        assert msg not in result.stdout.str()


def test_log_cli_default_level(testrunnerer: Testrunnerer) -> None:
    # Default log file level
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_cli(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_cli_handler.level == logging.NOTSET
            logging.getLogger('catchlog').info("INFO message won't be shown")
            logging.getLogger('catchlog').warning("WARNING message will be shown")
    """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_cli=true
    """
    )

    result = testrunnerer.runtestrunner()

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(
        [
            "test_log_cli_default_level.py::test_log_cli ",
            "WARNING*test_log_cli_default_level.py* message will be shown*",
        ]
    )
    result.stdout.no_fnmatch_line("*INFO message won't be shown*")
    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0


def test_log_cli_default_level_multiple_tests(
    testrunnerer: Testrunnerer, request: FixtureRequest
) -> None:
    """Ensure we reset the first newline added by the live logger between tests"""
    filename = request.node.name + ".py"
    testrunnerer.makepyfile(
        """
        import logging

        def test_log_1():
            logging.warning("log message from test_log_1")

        def test_log_2():
            logging.warning("log message from test_log_2")
    """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_cli=true
    """
    )

    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            f"{filename}::test_log_1 ",
            "*WARNING*log message from test_log_1*",
            "PASSED *50%*",
            f"{filename}::test_log_2 ",
            "*WARNING*log message from test_log_2*",
            "PASSED *100%*",
            "=* 2 passed in *=",
        ]
    )


def test_log_cli_default_level_sections(
    testrunnerer: Testrunnerer, request: FixtureRequest
) -> None:
    """Check that with live logging enable we are printing the correct headers during
    start/setup/call/teardown/finish."""
    filename = request.node.name + ".py"
    testrunnerer.makeconftest(
        """
        import testrunner
        import logging

        def testrunner_runtest_logstart():
            logging.warning('>>>>> START >>>>>')

        def testrunner_runtest_logfinish():
            logging.warning('<<<<< END <<<<<<<')
    """
    )

    testrunnerer.makepyfile(
        """
        import testrunner
        import logging

        @testrunner.fixture
        def fix(request):
            logging.warning("log message from setup of {}".format(request.node.name))
            yield
            logging.warning("log message from teardown of {}".format(request.node.name))

        def test_log_1(fix):
            logging.warning("log message from test_log_1")

        def test_log_2(fix):
            logging.warning("log message from test_log_2")
    """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_cli=true
    """
    )

    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            f"{filename}::test_log_1 ",
            "*-- live log start --*",
            "*WARNING* >>>>> START >>>>>*",
            "*-- live log setup --*",
            "*WARNING*log message from setup of test_log_1*",
            "*-- live log call --*",
            "*WARNING*log message from test_log_1*",
            "PASSED *50%*",
            "*-- live log teardown --*",
            "*WARNING*log message from teardown of test_log_1*",
            "*-- live log finish --*",
            "*WARNING* <<<<< END <<<<<<<*",
            f"{filename}::test_log_2 ",
            "*-- live log start --*",
            "*WARNING* >>>>> START >>>>>*",
            "*-- live log setup --*",
            "*WARNING*log message from setup of test_log_2*",
            "*-- live log call --*",
            "*WARNING*log message from test_log_2*",
            "PASSED *100%*",
            "*-- live log teardown --*",
            "*WARNING*log message from teardown of test_log_2*",
            "*-- live log finish --*",
            "*WARNING* <<<<< END <<<<<<<*",
            "=* 2 passed in *=",
        ]
    )


def test_live_logs_unknown_sections(
    testrunnerer: Testrunnerer, request: FixtureRequest
) -> None:
    """Check that with live logging enable we are printing the correct headers during
    start/setup/call/teardown/finish."""
    filename = request.node.name + ".py"
    testrunnerer.makeconftest(
        """
        import testrunner
        import logging

        def testrunner_runtest_protocol(item, nextitem):
            logging.warning('Unknown Section!')

        def testrunner_runtest_logstart():
            logging.warning('>>>>> START >>>>>')

        def testrunner_runtest_logfinish():
            logging.warning('<<<<< END <<<<<<<')
    """
    )

    testrunnerer.makepyfile(
        """
        import testrunner
        import logging

        @testrunner.fixture
        def fix(request):
            logging.warning("log message from setup of {}".format(request.node.name))
            yield
            logging.warning("log message from teardown of {}".format(request.node.name))

        def test_log_1(fix):
            logging.warning("log message from test_log_1")

    """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_cli=true
    """
    )

    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            "*WARNING*Unknown Section*",
            f"{filename}::test_log_1 ",
            "*WARNING* >>>>> START >>>>>*",
            "*-- live log setup --*",
            "*WARNING*log message from setup of test_log_1*",
            "*-- live log call --*",
            "*WARNING*log message from test_log_1*",
            "PASSED *100%*",
            "*-- live log teardown --*",
            "*WARNING*log message from teardown of test_log_1*",
            "*WARNING* <<<<< END <<<<<<<*",
            "=* 1 passed in *=",
        ]
    )


def test_sections_single_new_line_after_test_outcome(
    testrunnerer: Testrunnerer, request: FixtureRequest
) -> None:
    """Check that only a single new line is written between log messages during
    teardown/finish."""
    filename = request.node.name + ".py"
    testrunnerer.makeconftest(
        """
        import testrunner
        import logging

        def testrunner_runtest_logstart():
            logging.warning('>>>>> START >>>>>')

        def testrunner_runtest_logfinish():
            logging.warning('<<<<< END <<<<<<<')
            logging.warning('<<<<< END <<<<<<<')
    """
    )

    testrunnerer.makepyfile(
        """
        import testrunner
        import logging

        @testrunner.fixture
        def fix(request):
            logging.warning("log message from setup of {}".format(request.node.name))
            yield
            logging.warning("log message from teardown of {}".format(request.node.name))
            logging.warning("log message from teardown of {}".format(request.node.name))

        def test_log_1(fix):
            logging.warning("log message from test_log_1")
    """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_cli=true
    """
    )

    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            f"{filename}::test_log_1 ",
            "*-- live log start --*",
            "*WARNING* >>>>> START >>>>>*",
            "*-- live log setup --*",
            "*WARNING*log message from setup of test_log_1*",
            "*-- live log call --*",
            "*WARNING*log message from test_log_1*",
            "PASSED *100%*",
            "*-- live log teardown --*",
            "*WARNING*log message from teardown of test_log_1*",
            "*-- live log finish --*",
            "*WARNING* <<<<< END <<<<<<<*",
            "*WARNING* <<<<< END <<<<<<<*",
            "=* 1 passed in *=",
        ]
    )
    assert (
        re.search(
            r"(.+)live log teardown(.+)\nWARNING(.+)\nWARNING(.+)",
            result.stdout.str(),
            re.MULTILINE,
        )
        is not None
    )
    assert (
        re.search(
            r"(.+)live log finish(.+)\nWARNING(.+)\nWARNING(.+)",
            result.stdout.str(),
            re.MULTILINE,
        )
        is not None
    )


def test_log_cli_level(testrunnerer: Testrunnerer) -> None:
    # Default log file level
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_cli(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_cli_handler.level == logging.INFO
            logging.getLogger('catchlog').debug("This log message won't be shown")
            logging.getLogger('catchlog').info("This log message will be shown")
            print('PASSED')
    """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_cli=true
    """
    )

    result = testrunnerer.runtestrunner("-s", "--log-cli-level=INFO")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(
        [
            "*test_log_cli_level.py*This log message will be shown",
            "PASSED",  # 'PASSED' on its own line because the log message prints a new line
        ]
    )
    result.stdout.no_fnmatch_line("*This log message won't be shown*")

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0

    result = testrunnerer.runtestrunner("-s", "--log-level=INFO")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(
        [
            "*test_log_cli_level.py* This log message will be shown",
            "PASSED",  # 'PASSED' on its own line because the log message prints a new line
        ]
    )
    result.stdout.no_fnmatch_line("*This log message won't be shown*")

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0


def test_log_cli_ini_level(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeini(
        """
        [testrunner]
        log_cli=true
        log_cli_level = INFO
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_cli(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_cli_handler.level == logging.INFO
            logging.getLogger('catchlog').debug("This log message won't be shown")
            logging.getLogger('catchlog').info("This log message will be shown")
            print('PASSED')
    """
    )

    result = testrunnerer.runtestrunner("-s")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(
        [
            "*test_log_cli_ini_level.py* This log message will be shown",
            "PASSED",  # 'PASSED' on its own line because the log message prints a new line
        ]
    )
    result.stdout.no_fnmatch_line("*This log message won't be shown*")

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0


@testrunner.mark.parametrize(
    "cli_args",
    ["", "--log-level=WARNING", "--log-file-level=WARNING", "--log-cli-level=WARNING"],
)
def test_log_cli_auto_enable(testrunnerer: Testrunnerer, cli_args: str) -> None:
    """Check that live logs are enabled if --log-level or --log-cli-level is passed on the CLI.

    It should not be auto enabled if the same configs are set on the configuration file.
    """
    testrunnerer.makepyfile(
        """
        import logging

        def test_log_1():
            logging.info("log message from test_log_1 not to be shown")
            logging.warning("log message from test_log_1")

    """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_level=INFO
        log_cli_level=INFO
    """
    )

    result = testrunnerer.runtestrunner(cli_args)
    stdout = result.stdout.str()
    if cli_args == "--log-cli-level=WARNING":
        result.stdout.fnmatch_lines(
            [
                "*::test_log_1 ",
                "*-- live log call --*",
                "*WARNING*log message from test_log_1*",
                "PASSED *100%*",
                "=* 1 passed in *=",
            ]
        )
        assert "INFO" not in stdout
    else:
        result.stdout.fnmatch_lines(
            ["*test_log_cli_auto_enable*100%*", "=* 1 passed in *="]
        )
        assert "INFO" not in stdout
        assert "WARNING" not in stdout


def test_log_file_cli(testrunnerer: Testrunnerer) -> None:
    # Default log file level
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_file(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_file_handler.level == logging.WARNING
            logging.getLogger('catchlog').info("This log message won't be shown")
            logging.getLogger('catchlog').warning("This log message will be shown")
            print('PASSED')
    """
    )

    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    result = testrunnerer.runtestrunner(
        "-s", f"--log-file={log_file}", "--log-file-level=WARNING"
    )

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["test_log_file_cli.py PASSED"])

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "This log message will be shown" in contents
        assert "This log message won't be shown" not in contents


def test_log_file_mode_cli(testrunnerer: Testrunnerer) -> None:
    # Default log file level
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_file(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_file_handler.level == logging.WARNING
            logging.getLogger('catchlog').info("This log message won't be shown")
            logging.getLogger('catchlog').warning("This log message will be shown")
            print('PASSED')
    """
    )

    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    with open(log_file, mode="w", encoding="utf-8") as wfh:
        wfh.write("A custom header\n")

    result = testrunnerer.runtestrunner(
        "-s",
        f"--log-file={log_file}",
        "--log-file-mode=a",
        "--log-file-level=WARNING",
    )

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["test_log_file_mode_cli.py PASSED"])

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "A custom header" in contents
        assert "This log message will be shown" in contents
        assert "This log message won't be shown" not in contents


def test_log_file_mode_cli_invalid(testrunnerer: Testrunnerer) -> None:
    # Default log file level
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_file(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_file_handler.level == logging.WARNING
            logging.getLogger('catchlog').info("This log message won't be shown")
            logging.getLogger('catchlog').warning("This log message will be shown")
    """
    )

    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    result = testrunnerer.runtestrunner(
        "-s",
        f"--log-file={log_file}",
        "--log-file-mode=b",
        "--log-file-level=WARNING",
    )

    # make sure that we get a '4' exit code for the testsuite
    assert result.ret == ExitCode.USAGE_ERROR


def test_log_file_cli_level(testrunnerer: Testrunnerer) -> None:
    # Default log file level
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_file(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_file_handler.level == logging.INFO
            logging.getLogger('catchlog').debug("This log message won't be shown")
            logging.getLogger('catchlog').info("This log message will be shown")
            print('PASSED')
    """
    )

    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    result = testrunnerer.runtestrunner(
        "-s", f"--log-file={log_file}", "--log-file-level=INFO"
    )

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["test_log_file_cli_level.py PASSED"])

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "This log message will be shown" in contents
        assert "This log message won't be shown" not in contents


def test_log_level_not_changed_by_default(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import logging
        def test_log_file():
            assert logging.getLogger().level == logging.WARNING
    """
    )
    result = testrunnerer.runtestrunner("-s")
    result.stdout.fnmatch_lines(["* 1 passed in *"])


def test_log_file_ini(testrunnerer: Testrunnerer) -> None:
    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    testrunnerer.makeini(
        f"""
        [testrunner]
        log_file={log_file}
        log_file_level=WARNING
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_file(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_file_handler.level == logging.WARNING
            logging.getLogger('catchlog').info("This log message won't be shown")
            logging.getLogger('catchlog').warning("This log message will be shown")
            print('PASSED')
    """
    )

    result = testrunnerer.runtestrunner("-s")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["test_log_file_ini.py PASSED"])

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "This log message will be shown" in contents
        assert "This log message won't be shown" not in contents


def test_log_file_mode_ini(testrunnerer: Testrunnerer) -> None:
    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    testrunnerer.makeini(
        f"""
        [testrunner]
        log_file={log_file}
        log_file_mode=a
        log_file_level=WARNING
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_file(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_file_handler.level == logging.WARNING
            logging.getLogger('catchlog').info("This log message won't be shown")
            logging.getLogger('catchlog').warning("This log message will be shown")
            print('PASSED')
    """
    )

    with open(log_file, mode="w", encoding="utf-8") as wfh:
        wfh.write("A custom header\n")

    result = testrunnerer.runtestrunner("-s")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["test_log_file_mode_ini.py PASSED"])

    assert result.ret == ExitCode.OK
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "A custom header" in contents
        assert "This log message will be shown" in contents
        assert "This log message won't be shown" not in contents


def test_log_file_ini_level(testrunnerer: Testrunnerer) -> None:
    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    testrunnerer.makeini(
        f"""
        [testrunner]
        log_file={log_file}
        log_file_level = INFO
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging
        def test_log_file(request):
            plugin = request.config.pluginmanager.getplugin('logging-plugin')
            assert plugin.log_file_handler.level == logging.INFO
            logging.getLogger('catchlog').debug("This log message won't be shown")
            logging.getLogger('catchlog').info("This log message will be shown")
            print('PASSED')
    """
    )

    result = testrunnerer.runtestrunner("-s")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["test_log_file_ini_level.py PASSED"])

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "This log message will be shown" in contents
        assert "This log message won't be shown" not in contents


def test_log_file_unicode(testrunnerer: Testrunnerer) -> None:
    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    testrunnerer.makeini(
        f"""
        [testrunner]
        log_file={log_file}
        log_file_level = INFO
        """
    )
    testrunnerer.makepyfile(
        """\
        import logging

        def test_log_file():
            logging.getLogger('catchlog').info("Normal message")
            logging.getLogger('catchlog').info("├")
            logging.getLogger('catchlog').info("Another normal message")
        """
    )

    result = testrunnerer.runtestrunner()

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "Normal message" in contents
        assert "├" in contents
        assert "Another normal message" in contents


@testrunner.mark.parametrize("has_capture_manager", [True, False])
def test_live_logging_suspends_capture(
    has_capture_manager: bool, request: FixtureRequest
) -> None:
    """Test that capture manager is suspended when we emitting messages for live logging.

    This tests the implementation calls instead of behavior because it is difficult/impossible to do it using
    ``testrunnerer`` facilities because they do their own capturing.

    We parametrize the test to also make sure _LiveLoggingStreamHandler works correctly if no capture manager plugin
    is installed.
    """
    import contextlib
    from functools import partial
    import logging

    from _testrunner.logging import _LiveLoggingStreamHandler

    class MockCaptureManager:
        calls = []

        @contextlib.contextmanager
        def global_and_fixture_disabled(self):
            self.calls.append("enter disabled")
            yield
            self.calls.append("exit disabled")

    class DummyTerminal(io.StringIO):
        def section(self, *args, **kwargs):
            pass

    out_file = cast(TerminalReporter, DummyTerminal())
    capture_manager = (
        cast(CaptureManager, MockCaptureManager()) if has_capture_manager else None
    )
    handler = _LiveLoggingStreamHandler(out_file, capture_manager)
    handler.set_when("call")

    logger = logging.getLogger(__name__ + ".test_live_logging_suspends_capture")
    logger.addHandler(handler)
    request.addfinalizer(partial(logger.removeHandler, handler))

    logger.critical("some message")
    if has_capture_manager:
        assert MockCaptureManager.calls == ["enter disabled", "exit disabled"]
    else:
        assert MockCaptureManager.calls == []
    assert cast(io.StringIO, out_file).getvalue() == "\nsome message\n"


def test_collection_live_logging(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import logging

        logging.getLogger().info("Normal message")
    """
    )

    result = testrunnerer.runtestrunner("--log-cli-level=INFO")
    result.stdout.fnmatch_lines(
        ["*--- live log collection ---*", "*Normal message*", "collected 0 items"]
    )


@testrunner.mark.parametrize("verbose", ["", "-q", "-qq"])
def test_collection_collect_only_live_logging(
    testrunnerer: Testrunnerer, verbose: str
) -> None:
    testrunnerer.makepyfile(
        """
        def test_simple():
            pass
    """
    )

    result = testrunnerer.runtestrunner(
        "--collect-only", "--log-cli-level=INFO", verbose
    )

    expected_lines = []

    if not verbose:
        expected_lines.extend(
            [
                "*collected 1 item*",
                "*<Module test_collection_collect_only_live_logging.py>*",
                "*1 test collected*",
            ]
        )
    elif verbose == "-q":
        result.stdout.no_fnmatch_line("*collected 1 item**")
        expected_lines.extend(
            [
                "*test_collection_collect_only_live_logging.py::test_simple*",
                "1 test collected in [0-9].[0-9][0-9]s",
            ]
        )
    elif verbose == "-qq":
        result.stdout.no_fnmatch_line("*collected 1 item**")
        expected_lines.extend(["*test_collection_collect_only_live_logging.py: 1*"])

    result.stdout.fnmatch_lines(expected_lines)


def test_collection_logging_to_file(testrunnerer: Testrunnerer) -> None:
    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    testrunnerer.makeini(
        f"""
        [testrunner]
        log_file={log_file}
        log_file_level = INFO
        """
    )

    testrunnerer.makepyfile(
        """
        import logging

        logging.getLogger().info("Normal message")

        def test_simple():
            logging.getLogger().debug("debug message in test_simple")
            logging.getLogger().info("info message in test_simple")
    """
    )

    result = testrunnerer.runtestrunner()

    result.stdout.no_fnmatch_line("*--- live log collection ---*")

    assert result.ret == 0
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "Normal message" in contents
        assert "debug message in test_simple" not in contents
        assert "info message in test_simple" in contents


def test_log_in_hooks(testrunnerer: Testrunnerer) -> None:
    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    testrunnerer.makeini(
        f"""
        [testrunner]
        log_file={log_file}
        log_file_level = INFO
        log_cli=true
        """
    )
    testrunnerer.makeconftest(
        """
        import logging

        def testrunner_runtestloop(session):
            logging.info('runtestloop')

        def testrunner_sessionstart(session):
            logging.info('sessionstart')

        def testrunner_sessionfinish(session, exitstatus):
            logging.info('sessionfinish')
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*sessionstart*", "*runtestloop*", "*sessionfinish*"])
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert "sessionstart" in contents
        assert "runtestloop" in contents
        assert "sessionfinish" in contents


def test_log_in_runtest_logreport(testrunnerer: Testrunnerer) -> None:
    log_file = str(testrunnerer.path.joinpath("testrunner.log"))

    testrunnerer.makeini(
        f"""
        [testrunner]
        log_file={log_file}
        log_file_level = INFO
        log_cli=true
        """
    )
    testrunnerer.makeconftest(
        """
        import logging
        logger = logging.getLogger(__name__)

        def testrunner_runtest_logreport(report):
            logger.info("logreport")
    """
    )
    testrunnerer.makepyfile(
        """
            def test_first():
                assert True
        """
    )
    testrunnerer.runtestrunner()
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert contents.count("logreport") == 3


def test_log_set_path(testrunnerer: Testrunnerer) -> None:
    report_dir_base = str(testrunnerer.path)

    testrunnerer.makeini(
        """
        [testrunner]
        log_file_level = DEBUG
        log_cli=true
        """
    )
    testrunnerer.makeconftest(
        f"""
            import os
            import testrunner
            @testrunner.hookimpl(wrapper=True, tryfirst=True)
            def testrunner_runtest_setup(item):
                config = item.config
                logging_plugin = config.pluginmanager.get_plugin("logging-plugin")
                report_file = os.path.join({report_dir_base!r}, item._request.node.name)
                logging_plugin.set_log_path(report_file)
                return (yield)
        """
    )
    testrunnerer.makepyfile(
        """
            import logging
            logger = logging.getLogger("testcase-logger")
            def test_first():
                logger.info("message from test 1")
                assert True

            def test_second():
                logger.debug("message from test 2")
                assert True
        """
    )
    testrunnerer.runtestrunner()
    with open(os.path.join(report_dir_base, "test_first"), encoding="utf-8") as rfh:
        content = rfh.read()
        assert "message from test 1" in content

    with open(os.path.join(report_dir_base, "test_second"), encoding="utf-8") as rfh:
        content = rfh.read()
        assert "message from test 2" in content


def test_log_set_path_with_log_file_mode(testrunnerer: Testrunnerer) -> None:
    report_dir_base = str(testrunnerer.path)

    testrunnerer.makeini(
        """
        [testrunner]
        log_file_level = DEBUG
        log_cli=true
        log_file_mode=a
        """
    )
    testrunnerer.makeconftest(
        f"""
            import os
            import testrunner
            @testrunner.hookimpl(wrapper=True, tryfirst=True)
            def testrunner_runtest_setup(item):
                config = item.config
                logging_plugin = config.pluginmanager.get_plugin("logging-plugin")
                report_file = os.path.join({report_dir_base!r}, item._request.node.name)
                logging_plugin.set_log_path(report_file)
                return (yield)
        """
    )
    testrunnerer.makepyfile(
        """
            import logging
            logger = logging.getLogger("testcase-logger")
            def test_first():
                logger.info("message from test 1")
                assert True

            def test_second():
                logger.debug("message from test 2")
                assert True
        """
    )

    test_first_log_file = os.path.join(report_dir_base, "test_first")
    test_second_log_file = os.path.join(report_dir_base, "test_second")
    with open(test_first_log_file, mode="w", encoding="utf-8") as wfh:
        wfh.write("A custom header for test 1\n")

    with open(test_second_log_file, mode="w", encoding="utf-8") as wfh:
        wfh.write("A custom header for test 2\n")

    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.OK

    with open(test_first_log_file, encoding="utf-8") as rfh:
        content = rfh.read()
        assert "A custom header for test 1" in content
        assert "message from test 1" in content

    with open(test_second_log_file, encoding="utf-8") as rfh:
        content = rfh.read()
        assert "A custom header for test 2" in content
        assert "message from test 2" in content


def test_colored_captured_log(testrunnerer: Testrunnerer) -> None:
    """Test that the level names of captured log messages of a failing test
    are colored."""
    testrunnerer.makepyfile(
        """
        import logging

        logger = logging.getLogger(__name__)

        def test_foo():
            logger.info('text going to logger from call')
            assert False
        """
    )
    result = testrunnerer.runtestrunner("--log-level=INFO", "--color=yes")
    assert result.ret == 1
    result.stdout.fnmatch_lines(
        [
            "*-- Captured log call --*",
            "\x1b[32mINFO    \x1b[0m*text going to logger from call",
        ]
    )


def test_log_propagation_false(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner
        import logging

        logging.getLogger('foo').propagate = False

        def test_log_file():
            logging.getLogger().warning("log goes to root logger")
            logging.getLogger('foo').warning("log goes to initially non-propagating logger")
            logging.getLogger('foo.bar').warning("log goes to initially non-propagating nested logger")
            assert False, "intentionally fail to trigger report logging output"
    """
    )

    reprec = testrunnerer.inline_run()
    reports = reprec.getfailures()
    assert len(reports) == 1
    report = reports[0]
    sections = list(report.get_sections("Captured log call"))
    assert len(sections) == 1
    assert sections[0][1] == "\n".join(
        [
            "WARNING  root:test_log_propagation_false.py:7 log goes to root logger",
            "WARNING  foo:test_log_propagation_false.py:8 log goes to initially non-propagating logger",
            "WARNING  foo.bar:test_log_propagation_false.py:9 log goes to initially non-propagating nested logger",
        ]
    )
    assert not list(report.get_sections("Captured stderr call"))


def test_colored_ansi_esc_caplogtext(testrunnerer: Testrunnerer) -> None:
    """Make sure that caplog.text does not contain ANSI escape sequences."""
    testrunnerer.makepyfile(
        """
        import logging

        logger = logging.getLogger(__name__)

        def test_foo(caplog):
            logger.info('text going to logger from call')
            assert '\x1b' not in caplog.text
        """
    )
    result = testrunnerer.runtestrunner("--log-level=INFO", "--color=yes")
    assert result.ret == 0


def test_logging_emit_error(testrunnerer: Testrunnerer) -> None:
    """An exception raised during emit() should fail the test.

    The default behavior of logging is to print "Logging error"
    to stderr with the call stack and some extra details.

    testrunner overrides this behavior to propagate the exception.
    """
    testrunnerer.makepyfile(
        """
        import logging

        def test_bad_log():
            logging.warning('oops', 'first', 2)
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        [
            "====* FAILURES *====",
            "*not all arguments converted during string formatting*",
        ]
    )


def test_logging_emit_error_supressed(testrunnerer: Testrunnerer) -> None:
    """If logging is configured to silently ignore errors, testrunner
    doesn't propagate errors either."""
    testrunnerer.makepyfile(
        """
        import logging

        def test_bad_log(monkeypatch):
            monkeypatch.setattr(logging, 'raiseExceptions', False)
            logging.warning('oops', 'first', 2)
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=1)


def test_log_file_cli_subdirectories_are_successfully_created(
    testrunnerer: Testrunnerer,
) -> None:
    path = testrunnerer.makepyfile(""" def test_logger(): pass """)
    expected = os.path.join(os.path.dirname(str(path)), "foo", "bar")
    result = testrunnerer.runtestrunner("--log-file=foo/bar/logf.log")
    assert "logf.log" in os.listdir(expected)
    assert result.ret == ExitCode.OK


def test_disable_loggers(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import logging
        import os
        disabled_log = logging.getLogger('disabled')
        test_log = logging.getLogger('test')
        def test_logger_propagation(caplog):
            with caplog.at_level(logging.DEBUG):
                disabled_log.warning("no log; no stderr")
                test_log.debug("Visible text!")
                assert caplog.record_tuples == [('test', 10, 'Visible text!')]
         """
    )
    result = testrunnerer.runtestrunner("--log-disable=disabled", "-s")
    assert result.ret == ExitCode.OK
    assert not result.stderr.lines


def test_disable_loggers_does_not_propagate(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
    import logging
    import os

    parent_logger = logging.getLogger("parent")
    child_logger = parent_logger.getChild("child")

    def test_logger_propagation_to_parent(caplog):
            with caplog.at_level(logging.DEBUG):
                parent_logger.warning("some parent logger message")
                child_logger.warning("some child logger message")
                assert len(caplog.record_tuples) == 1
                assert caplog.record_tuples[0][0] == "parent"
                assert caplog.record_tuples[0][2] == "some parent logger message"
    """
    )

    result = testrunnerer.runtestrunner("--log-disable=parent.child", "-s")
    assert result.ret == ExitCode.OK
    assert not result.stderr.lines


def test_log_disabling_works_with_log_cli(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
    import logging
    disabled_log = logging.getLogger('disabled')
    test_log = logging.getLogger('test')

    def test_log_cli_works(caplog):
        test_log.info("Visible text!")
        disabled_log.warning("This string will be suppressed.")
    """
    )
    result = testrunnerer.runtestrunner(
        "--log-cli-level=DEBUG",
        "--log-disable=disabled",
    )
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(
        "INFO     test:test_log_disabling_works_with_log_cli.py:6 Visible text!"
    )
    result.stdout.no_fnmatch_line(
        "WARNING  disabled:test_log_disabling_works_with_log_cli.py:7 This string will be suppressed."
    )
    assert not result.stderr.lines


def test_without_date_format_log(testrunnerer: Testrunnerer) -> None:
    """Check that date is not printed by default."""
    testrunnerer.makepyfile(
        """
        import logging

        logger = logging.getLogger(__name__)

        def test_foo():
            logger.warning('text')
            assert False
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 1
    result.stdout.fnmatch_lines(
        ["WARNING  test_without_date_format_log:test_without_date_format_log.py:6 text"]
    )


def test_date_format_log(testrunnerer: Testrunnerer) -> None:
    """Check that log_date_format affects output."""
    testrunnerer.makepyfile(
        """
        import logging

        logger = logging.getLogger(__name__)

        def test_foo():
            logger.warning('text')
            assert False
        """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_format=%(asctime)s; %(levelname)s; %(message)s
        log_date_format=%Y-%m-%d %H:%M:%S
    """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 1
    result.stdout.re_match_lines([r"^[0-9-]{10} [0-9:]{8}; WARNING; text"])


def test_date_format_percentf_log(testrunnerer: Testrunnerer) -> None:
    """Make sure that microseconds are printed in log."""
    testrunnerer.makepyfile(
        """
        import logging

        logger = logging.getLogger(__name__)

        def test_foo():
            logger.warning('text')
            assert False
        """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_format=%(asctime)s; %(levelname)s; %(message)s
        log_date_format=%Y-%m-%d %H:%M:%S.%f
    """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 1
    result.stdout.re_match_lines([r"^[0-9-]{10} [0-9:]{8}.[0-9]{6}; WARNING; text"])


def test_date_format_percentf_tz_log(testrunnerer: Testrunnerer) -> None:
    """Make sure that timezone and microseconds are properly formatted together."""
    testrunnerer.makepyfile(
        """
        import logging

        logger = logging.getLogger(__name__)

        def test_foo():
            logger.warning('text')
            assert False
        """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        log_format=%(asctime)s; %(levelname)s; %(message)s
        log_date_format=%Y-%m-%d %H:%M:%S.%f%z
    """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 1
    result.stdout.re_match_lines(
        [r"^[0-9-]{10} [0-9:]{8}.[0-9]{6}[+-][0-9\.]+; WARNING; text"]
    )


def test_log_file_cli_fallback_options(testrunnerer: Testrunnerer) -> None:
    """Make sure that fallback values for log-file formats and level works."""
    testrunnerer.makepyfile(
        """
        import logging
        logger = logging.getLogger()

        def test_foo():
            logger.info('info text going to logger')
            logger.warning('warning text going to logger')
            logger.error('error text going to logger')

            assert 0
    """
    )
    log_file = str(testrunnerer.path.joinpath("testrunner.log"))
    result = testrunnerer.runtestrunner(
        "--log-level=ERROR",
        "--log-format=%(asctime)s %(message)s",
        "--log-date-format=%H:%M",
        "--log-file=testrunner.log",
    )
    assert result.ret == 1

    # The log file should only contain the error log messages
    # not the warning or info ones and the format and date format
    # should match the formats provided using --log-format and --log-date-format
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert re.match(r"[0-9]{2}:[0-9]{2} error text going to logger\s*", contents)
        assert "info text going to logger" not in contents
        assert "warning text going to logger" not in contents
        assert "error text going to logger" in contents

    # Try with a different format and date format to make sure that the formats
    # are being used
    result = testrunnerer.runtestrunner(
        "--log-level=ERROR",
        "--log-format=%(asctime)s : %(message)s",
        "--log-date-format=%H:%M:%S",
        "--log-file=testrunner.log",
    )
    assert result.ret == 1

    # The log file should only contain the error log messages
    # not the warning or info ones and the format and date format
    # should match the formats provided using --log-format and --log-date-format
    assert os.path.isfile(log_file)
    with open(log_file, encoding="utf-8") as rfh:
        contents = rfh.read()
        assert re.match(
            r"[0-9]{2}:[0-9]{2}:[0-9]{2} : error text going to logger\s*", contents
        )
        assert "info text going to logger" not in contents
        assert "warning text going to logger" not in contents
        assert "error text going to logger" in contents
