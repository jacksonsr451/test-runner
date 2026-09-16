# mypy: allow-untyped-defs
from __future__ import annotations

import io
import os
import sys

from _testrunner.testrunnerer import Testrunnerer
import testrunner


def test_enabled(testrunnerer: Testrunnerer) -> None:
    """Test single crashing test displays a traceback."""
    testrunnerer.makepyfile(
        """
    import faulthandler
    def test_crash():
        faulthandler._sigabrt()
    """
    )
    result = testrunnerer.runtestrunner_subprocess()
    result.stderr.fnmatch_lines(["*Fatal Python error*"])
    assert result.ret != 0


def setup_crashing_test(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import faulthandler
        import atexit
        def test_ok():
            atexit.register(faulthandler._sigabrt)
        """
    )


def test_crash_during_shutdown_captured(testrunnerer: Testrunnerer) -> None:
    """
    Re-enable faulthandler if testrunner encountered it enabled during configure.
    We should be able to then see crashes during interpreter shutdown.
    """
    setup_crashing_test(testrunnerer)
    args = (sys.executable, "-Xfaulthandler", "-mtestrunner")
    result = testrunnerer.run(*args)
    result.stderr.fnmatch_lines(["*Fatal Python error*"])
    assert result.ret != 0


def test_crash_during_shutdown_not_captured(testrunnerer: Testrunnerer) -> None:
    """
    Check that testrunner leaves faulthandler disabled if it was not enabled during configure.
    This prevents us from seeing crashes during interpreter shutdown (see #8260).
    """
    setup_crashing_test(testrunnerer)
    args = (sys.executable, "-mtestrunner")
    result = testrunnerer.run(*args)
    result.stderr.no_fnmatch_line("*Fatal Python error*")
    assert result.ret != 0


def test_disabled(testrunnerer: Testrunnerer) -> None:
    """Test option to disable fault handler in the command line."""
    testrunnerer.makepyfile(
        """
    import faulthandler
    def test_disabled():
        assert not faulthandler.is_enabled()
    """
    )
    result = testrunnerer.runtestrunner_subprocess("-p", "no:faulthandler")
    result.stdout.fnmatch_lines(["*1 passed*"])
    assert result.ret == 0


@testrunner.mark.keep_ci_var
@testrunner.mark.parametrize(
    "enabled",
    [
        testrunner.param(
            True,
            marks=testrunner.mark.skipif(
                bool(os.environ.get("CI"))
                and sys.platform == "linux"
                and sys.version_info >= (3, 14),
                reason="sometimes crashes on CI because of truncated outputs (#7022)",
            ),
        ),
        False,
    ],
)
def test_timeout(testrunnerer: Testrunnerer, enabled: bool) -> None:
    """Test option to dump tracebacks after a certain timeout.

    If faulthandler is disabled, no traceback will be dumped.
    """
    testrunnerer.makepyfile(
        """
    import os, time
    def test_timeout():
        time.sleep(1 if "CI" in os.environ else 0.1)
    """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        faulthandler_timeout = 0.01
        """
    )
    args = ["-p", "no:faulthandler"] if not enabled else []

    result = testrunnerer.runtestrunner_subprocess(*args)
    tb_output = "most recent call first"
    if enabled:
        result.stderr.fnmatch_lines([f"*{tb_output}*"])
    else:
        assert tb_output not in result.stderr.str()
    result.stdout.fnmatch_lines(["*1 passed*"])
    assert result.ret == 0


@testrunner.mark.keep_ci_var
@testrunner.mark.skipif(
    "CI" in os.environ and sys.platform == "linux" and sys.version_info >= (3, 14),
    reason="sometimes crashes on CI because of truncated outputs (#7022)",
)
@testrunner.mark.parametrize("exit_on_timeout", [True, False])
def test_timeout_and_exit(testrunnerer: Testrunnerer, exit_on_timeout: bool) -> None:
    """Test option to force exit testrunner process after a certain timeout."""
    testrunnerer.makepyfile(
        """
    import os, time
    def test_long_sleep_and_raise():
        time.sleep(1 if "CI" in os.environ else 0.1)
        raise AssertionError(
            "This test should have been interrupted before reaching this point."
        )
    """
    )
    testrunnerer.makeini(
        f"""
        [testrunner]
        faulthandler_timeout = 0.01
        faulthandler_exit_on_timeout = {"true" if exit_on_timeout else "false"}
        """
    )
    result = testrunnerer.runtestrunner_subprocess()
    tb_output = "most recent call first"
    result.stderr.fnmatch_lines([f"*{tb_output}*"])
    if exit_on_timeout:
        result.stdout.no_fnmatch_line("*1 failed*")
        result.stdout.no_fnmatch_line("*AssertionError*")
    else:
        result.stdout.fnmatch_lines(["*1 failed*"])
        result.stdout.fnmatch_lines(["*AssertionError*"])
    assert result.ret == 1


@testrunner.mark.parametrize(
    "hook_name", ["testrunner_enter_pdb", "testrunner_exception_interact"]
)
def test_cancel_timeout_on_hook(monkeypatch, hook_name) -> None:
    """Make sure that we are cancelling any scheduled traceback dumping due
    to timeout before entering pdb (jacksonsr451/test-runner-faulthandler#12) or any
    other interactive exception (jacksonsr451/test-runner-faulthandler#14)."""
    import faulthandler

    from _testrunner import faulthandler as faulthandler_plugin

    called = []

    monkeypatch.setattr(
        faulthandler, "cancel_dump_traceback_later", lambda: called.append(1)
    )

    # call our hook explicitly, we can trust that testrunner will call the hook
    # for us at the appropriate moment
    hook_func = getattr(faulthandler_plugin, hook_name)
    hook_func()
    assert called == [1]


def test_already_initialized_crash(testrunnerer: Testrunnerer) -> None:
    """Even if faulthandler is already initialized, we still dump tracebacks on crashes (#8258)."""
    testrunnerer.makepyfile(
        """
        def test():
            import faulthandler
            faulthandler._sigabrt()
    """
    )
    result = testrunnerer.run(
        sys.executable,
        "-X",
        "faulthandler",
        "-mtestrunner",
        testrunnerer.path,
    )
    result.stderr.fnmatch_lines(["*Fatal Python error*"])
    assert result.ret != 0


def test_get_stderr_fileno_invalid_fd() -> None:
    """Test for faulthandler being able to handle invalid file descriptors for stderr (#8249)."""
    from _testrunner.faulthandler import get_stderr_fileno

    class StdErrWrapper(io.StringIO):
        """
        Mimic ``twisted.logger.LoggingFile`` to simulate returning an invalid file descriptor.

        https://github.com/twisted/twisted/blob/twisted-20.3.0/src/twisted/logger/_io.py#L132-L139
        """

        def fileno(self):
            return -1

    wrapper = StdErrWrapper()

    with testrunner.MonkeyPatch.context() as mp:
        mp.setattr("sys.stderr", wrapper)

        # Even when the stderr wrapper signals an invalid file descriptor,
        # ``_get_stderr_fileno()`` should return the real one.
        assert get_stderr_fileno() == 2
