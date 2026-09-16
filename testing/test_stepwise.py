# mypy: disallow-untyped-defs
from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path

from _testrunner.cacheprovider import Cache
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.stepwise import STEPWISE_CACHE_DIR
from _testrunner.testrunnerer import Testrunnerer
import testrunner


@testrunner.fixture
def stepwise_testrunnerer(testrunnerer: Testrunnerer) -> Testrunnerer:
    # Rather than having to modify our testfile between tests, we introduce
    # a flag for whether or not the second test should fail.
    testrunnerer.makeconftest(
        """
def testrunner_addoption(parser):
    group = parser.getgroup('general')
    group.addoption('--fail', action='store_true', dest='fail')
    group.addoption('--fail-last', action='store_true', dest='fail_last')
"""
    )

    # Create a simple test suite.
    testrunnerer.makepyfile(
        test_a="""
def test_success_before_fail():
    assert 1

def test_fail_on_flag(request):
    assert not request.config.getvalue('fail')

def test_success_after_fail():
    assert 1

def test_fail_last_on_flag(request):
    assert not request.config.getvalue('fail_last')

def test_success_after_last_fail():
    assert 1
"""
    )

    testrunnerer.makepyfile(
        test_b="""
def test_success():
    assert 1
"""
    )

    # customize cache directory so we don't use the tox's cache directory, which makes tests in this module flaky
    testrunnerer.makeini(
        """
        [testrunner]
        cache_dir = .cache
    """
    )

    return testrunnerer


@testrunner.fixture
def error_testrunnerer(testrunnerer: Testrunnerer) -> Testrunnerer:
    testrunnerer.makepyfile(
        test_a="""
def test_error(nonexisting_fixture):
    assert 1

def test_success_after_fail():
    assert 1
"""
    )

    return testrunnerer


@testrunner.fixture
def broken_testrunnerer(testrunnerer: Testrunnerer) -> Testrunnerer:
    testrunnerer.makepyfile(
        working_testfile="def test_proper(): assert 1", broken_testfile="foobar"
    )
    return testrunnerer


def _strip_resource_warnings(lines: Sequence[str]) -> Sequence[str]:
    # Strip unreliable ResourceWarnings, so no-output assertions on stderr can work.
    # (https://github.com/jacksonsr451/test-runner/issues/5088)
    return [
        x
        for x in lines
        if not x.startswith(("Exception ignored in:", "ResourceWarning"))
    ]


def test_run_without_stepwise(stepwise_testrunnerer: Testrunnerer) -> None:
    result = stepwise_testrunnerer.runtestrunner("-v", "--strict-markers", "--fail")
    result.stdout.fnmatch_lines(["*test_success_before_fail PASSED*"])
    result.stdout.fnmatch_lines(["*test_fail_on_flag FAILED*"])
    result.stdout.fnmatch_lines(["*test_success_after_fail PASSED*"])


def test_stepwise_output_summary(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner
        @testrunner.mark.parametrize("expected", [True, True, True, True, False])
        def test_data(expected):
            assert expected
        """
    )
    result = testrunnerer.runtestrunner("-v", "--stepwise")
    result.stdout.fnmatch_lines(["stepwise: no previously failed tests, not skipping."])
    result = testrunnerer.runtestrunner("-v", "--stepwise")
    result.stdout.fnmatch_lines(
        [
            "stepwise: skipping 4 already passed items (cache from * ago, use --sw-reset to discard).",
            "*1 failed, 4 deselected*",
        ]
    )


def test_fail_and_continue_with_stepwise(stepwise_testrunnerer: Testrunnerer) -> None:
    # Run the tests with a failing second test.
    result = stepwise_testrunnerer.runtestrunner(
        "-v", "--strict-markers", "--stepwise", "--fail"
    )
    assert _strip_resource_warnings(result.stderr.lines) == []

    stdout = result.stdout.str()
    # Make sure we stop after first failing test.
    assert "test_success_before_fail PASSED" in stdout
    assert "test_fail_on_flag FAILED" in stdout
    assert "test_success_after_fail" not in stdout

    # "Fix" the test that failed in the last run and run it again.
    result = stepwise_testrunnerer.runtestrunner("-v", "--strict-markers", "--stepwise")
    assert _strip_resource_warnings(result.stderr.lines) == []

    stdout = result.stdout.str()
    # Make sure the latest failing test runs and then continues.
    assert "test_success_before_fail" not in stdout
    assert "test_fail_on_flag PASSED" in stdout
    assert "test_success_after_fail PASSED" in stdout


@testrunner.mark.parametrize("stepwise_skip", ["--stepwise-skip", "--sw-skip"])
def test_run_with_skip_option(
    stepwise_testrunnerer: Testrunnerer, stepwise_skip: str
) -> None:
    result = stepwise_testrunnerer.runtestrunner(
        "-v",
        "--strict-markers",
        "--stepwise",
        stepwise_skip,
        "--fail",
        "--fail-last",
    )
    assert _strip_resource_warnings(result.stderr.lines) == []

    stdout = result.stdout.str()
    # Make sure first fail is ignore and second fail stops the test run.
    assert "test_fail_on_flag FAILED" in stdout
    assert "test_success_after_fail PASSED" in stdout
    assert "test_fail_last_on_flag FAILED" in stdout
    assert "test_success_after_last_fail" not in stdout


def test_fail_on_errors(error_testrunnerer: Testrunnerer) -> None:
    result = error_testrunnerer.runtestrunner("-v", "--strict-markers", "--stepwise")

    assert _strip_resource_warnings(result.stderr.lines) == []
    stdout = result.stdout.str()

    assert "test_error ERROR" in stdout
    assert "test_success_after_fail" not in stdout


def test_change_testfile(stepwise_testrunnerer: Testrunnerer) -> None:
    result = stepwise_testrunnerer.runtestrunner(
        "-v", "--strict-markers", "--stepwise", "--fail", "test_a.py"
    )
    assert _strip_resource_warnings(result.stderr.lines) == []

    stdout = result.stdout.str()
    assert "test_fail_on_flag FAILED" in stdout

    # Make sure the second test run starts from the beginning, since the
    # test to continue from does not exist in testfile_b.
    result = stepwise_testrunnerer.runtestrunner(
        "-v", "--strict-markers", "--stepwise", "test_b.py"
    )
    assert _strip_resource_warnings(result.stderr.lines) == []

    stdout = result.stdout.str()
    assert "test_success PASSED" in stdout


@testrunner.mark.parametrize("broken_first", [True, False])
def test_stop_on_collection_errors(
    broken_testrunnerer: Testrunnerer, broken_first: bool
) -> None:
    """Stop during collection errors. Broken test first or broken test last
    actually surfaced a bug (#5444), so we test both situations."""
    files = ["working_testfile.py", "broken_testfile.py"]
    if broken_first:
        files.reverse()
    result = broken_testrunnerer.runtestrunner(
        "-v", "--strict-markers", "--stepwise", *files
    )
    result.stdout.fnmatch_lines("*error during collection*")


def test_xfail_handling(testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch) -> None:
    """Ensure normal xfail is ignored, and strict xfail interrupts the session in sw mode

    (#5547)
    """
    monkeypatch.setattr("sys.dont_write_bytecode", True)

    contents = """
        import testrunner
        def test_a(): pass

        @testrunner.mark.xfail(strict={strict})
        def test_b(): assert {assert_value}

        def test_c(): pass
        def test_d(): pass
    """
    testrunnerer.makepyfile(contents.format(assert_value="0", strict="False"))
    result = testrunnerer.runtestrunner("--sw", "-v")
    result.stdout.fnmatch_lines(
        [
            "*::test_a PASSED *",
            "*::test_b XFAIL *",
            "*::test_c PASSED *",
            "*::test_d PASSED *",
            "* 3 passed, 1 xfailed in *",
        ]
    )

    testrunnerer.makepyfile(contents.format(assert_value="1", strict="True"))
    result = testrunnerer.runtestrunner("--sw", "-v")
    result.stdout.fnmatch_lines(
        [
            "*::test_a PASSED *",
            "*::test_b FAILED *",
            "* Interrupted*",
            "* 1 failed, 1 passed in *",
        ]
    )

    testrunnerer.makepyfile(contents.format(assert_value="0", strict="True"))
    result = testrunnerer.runtestrunner("--sw", "-v")
    result.stdout.fnmatch_lines(
        [
            "*::test_b XFAIL *",
            "*::test_c PASSED *",
            "*::test_d PASSED *",
            "* 2 passed, 1 deselected, 1 xfailed in *",
        ]
    )


def test_stepwise_skip_is_independent(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        def test_one():
            assert False

        def test_two():
            assert False

        def test_three():
            assert False

        """
    )
    result = testrunnerer.runtestrunner("--tb", "no", "--stepwise-skip")
    result.assert_outcomes(failed=2)
    result.stdout.fnmatch_lines(
        [
            "FAILED test_stepwise_skip_is_independent.py::test_one - assert False",
            "FAILED test_stepwise_skip_is_independent.py::test_two - assert False",
            "*Interrupted: Test failed, continuing from this test next run.*",
        ]
    )


def test_sw_skip_help(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("-h")
    result.stdout.fnmatch_lines("*Implicitly enables --stepwise.")


def test_stepwise_xdist_dont_store_lastfailed(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makefile(
        ext=".ini",
        testrunner=f"[testrunner]\ncache_dir = {testrunnerer.path}\n",
    )

    testrunnerer.makepyfile(
        conftest="""
import testrunner

@testrunner.hookimpl(tryfirst=True)
def testrunner_configure(config) -> None:
    config.workerinput = True
"""
    )
    testrunnerer.makepyfile(
        test_one="""
def test_one():
    assert False
"""
    )
    result = testrunnerer.runtestrunner("--stepwise")
    assert result.ret == testrunner.ExitCode.INTERRUPTED

    stepwise_cache_file = (
        testrunnerer.path / Cache._CACHE_PREFIX_VALUES / STEPWISE_CACHE_DIR
    )
    assert not Path(stepwise_cache_file).exists()


def test_disabled_stepwise_xdist_dont_clear_cache(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makefile(
        ext=".ini",
        testrunner=f"[testrunner]\ncache_dir = {testrunnerer.path}\n",
    )

    stepwise_cache_file = (
        testrunnerer.path / Cache._CACHE_PREFIX_VALUES / STEPWISE_CACHE_DIR
    )
    stepwise_cache_dir = stepwise_cache_file.parent
    stepwise_cache_dir.mkdir(exist_ok=True, parents=True)

    stepwise_cache_file_relative = f"{Cache._CACHE_PREFIX_VALUES}/{STEPWISE_CACHE_DIR}"

    expected_value = '"test_one.py::test_one"'
    content = {f"{stepwise_cache_file_relative}": expected_value}

    testrunnerer.makefile(ext="", **content)

    testrunnerer.makepyfile(
        conftest="""
import testrunner

@testrunner.hookimpl(tryfirst=True)
def testrunner_configure(config) -> None:
    config.workerinput = True
"""
    )
    testrunnerer.makepyfile(
        test_one="""
def test_one():
    assert True
"""
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0

    assert Path(stepwise_cache_file).exists()
    with stepwise_cache_file.open(encoding="utf-8") as file_handle:
        observed_value = file_handle.readlines()
    assert [expected_value] == observed_value


def test_do_not_reset_cache_if_disabled(testrunnerer: Testrunnerer) -> None:
    """
    If testrunner is run without --stepwise, do not clear the stepwise cache.

    Keeping the cache around is important for this workflow:

    1. Run tests with --stepwise
    2. Stop at the failing test, and iterate over it changing the code and running it in isolation
    (in the IDE for example).
    3. Run tests with --stepwise again - at this point we expect to start from the failing test, which should now pass,
       and continue with the next tests.
    """
    testrunnerer.makepyfile(
        """
        def test_1(): pass
        def test_2(): assert False
        def test_3(): pass
        """
    )
    result = testrunnerer.runtestrunner("--stepwise")
    result.stdout.fnmatch_lines(
        [
            "*::test_2 - assert False*",
            "*failed, continuing from this test next run*",
            "=* 1 failed, 1 passed in *",
        ]
    )

    # Run a specific test without passing `--stepwise`.
    result = testrunnerer.runtestrunner("-k", "test_1")
    result.stdout.fnmatch_lines(["*1 passed*"])

    # Running with `--stepwise` should continue from the last failing test.
    result = testrunnerer.runtestrunner("--stepwise")
    result.stdout.fnmatch_lines(
        [
            "stepwise: skipping 1 already passed items (cache from *, use --sw-reset to discard).",
            "*::test_2 - assert False*",
            "*failed, continuing from this test next run*",
            "=* 1 failed, 1 deselected in *",
        ]
    )


def test_reset(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        def test_1(): pass
        def test_2(): assert False
        def test_3(): pass
        """
    )
    result = testrunnerer.runtestrunner("--stepwise", "-v")
    result.stdout.fnmatch_lines(
        [
            "stepwise: no previously failed tests, not skipping.",
            "*::test_1 *PASSED*",
            "*::test_2 *FAILED*",
            "*failed, continuing from this test next run*",
            "* 1 failed, 1 passed in *",
        ]
    )

    result = testrunnerer.runtestrunner("--stepwise", "-v")
    result.stdout.fnmatch_lines(
        [
            "stepwise: skipping 1 already passed items (cache from *, use --sw-reset to discard).",
            "*::test_2 *FAILED*",
            "*failed, continuing from this test next run*",
            "* 1 failed, 1 deselected in *",
        ]
    )

    # Running with --stepwise-reset restarts the stepwise workflow.
    result = testrunnerer.runtestrunner("-v", "--stepwise-reset")
    result.stdout.fnmatch_lines(
        [
            "stepwise: resetting state, not skipping.",
            "*::test_1 *PASSED*",
            "*::test_2 *FAILED*",
            "*failed, continuing from this test next run*",
            "* 1 failed, 1 passed in *",
        ]
    )


def test_change_test_count(testrunnerer: Testrunnerer) -> None:
    # Run initially with 3 tests.
    testrunnerer.makepyfile(
        """
        def test_1(): pass
        def test_2(): assert False
        def test_3(): pass
        """
    )
    result = testrunnerer.runtestrunner("--stepwise", "-v")
    result.stdout.fnmatch_lines(
        [
            "stepwise: no previously failed tests, not skipping.",
            "*::test_1 *PASSED*",
            "*::test_2 *FAILED*",
            "*failed, continuing from this test next run*",
            "* 1 failed, 1 passed in *",
        ]
    )

    # Change the number of tests, which invalidates the test cache.
    testrunnerer.makepyfile(
        """
        def test_1(): pass
        def test_2(): assert False
        def test_3(): pass
        def test_4(): pass
        """
    )
    result = testrunnerer.runtestrunner("--stepwise", "-v")
    result.stdout.fnmatch_lines(
        [
            "stepwise: test count changed, not skipping (now 4 tests, previously 3).",
            "*::test_1 *PASSED*",
            "*::test_2 *FAILED*",
            "*failed, continuing from this test next run*",
            "* 1 failed, 1 passed in *",
        ]
    )

    # Fix the failing test and run again.
    testrunnerer.makepyfile(
        """
        def test_1(): pass
        def test_2(): pass
        def test_3(): pass
        def test_4(): pass
        """
    )
    result = testrunnerer.runtestrunner("--stepwise", "-v")
    result.stdout.fnmatch_lines(
        [
            "stepwise: skipping 1 already passed items (cache from *, use --sw-reset to discard).",
            "*::test_2 *PASSED*",
            "*::test_3 *PASSED*",
            "*::test_4 *PASSED*",
            "* 3 passed, 1 deselected in *",
        ]
    )


def test_cache_error(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        def test_1(): pass
        """
    )
    # Run stepwise normally to generate the cache information.
    result = testrunnerer.runtestrunner("--stepwise", "-v")
    result.stdout.fnmatch_lines(
        [
            "stepwise: no previously failed tests, not skipping.",
            "*::test_1 *PASSED*",
            "* 1 passed in *",
        ]
    )

    # Corrupt the cache.
    cache_file = testrunnerer.path / f".testrunner_cache/v/{STEPWISE_CACHE_DIR}"
    assert cache_file.is_file()
    cache_file.write_text(json.dumps({"invalid": True}), encoding="UTF-8")

    # Check we run as if the cache did not exist, but also show an error message.
    result = testrunnerer.runtestrunner("--stepwise", "-v")
    result.stdout.fnmatch_lines(
        [
            "stepwise: error reading cache, discarding (KeyError: *",
            "stepwise: no previously failed tests, not skipping.",
            "*::test_1 *PASSED*",
            "* 1 passed in *",
        ]
    )
