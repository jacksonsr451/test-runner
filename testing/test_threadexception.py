from __future__ import annotations

from _testrunner.testrunnerer import Testrunnerer
import testrunner


@testrunner.mark.filterwarnings(
    "default::testrunner.TestrunnerUnhandledThreadExceptionWarning"
)
def test_unhandled_thread_exception(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_it="""
        import threading

        def test_it():
            def oops():
                raise ValueError("Oops")

            t = threading.Thread(target=oops, name="MyThread")
            t.start()
            t.join()

        def test_2(): pass
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0
    result.assert_outcomes(passed=2, warnings=1)
    result.stdout.fnmatch_lines(
        [
            "*= warnings summary =*",
            "test_it.py::test_it",
            "  * TestrunnerUnhandledThreadExceptionWarning: Exception in thread MyThread",
            "  ",
            "  Traceback (most recent call last):",
            "  ValueError: Oops",
            "  ",
            "    warnings.warn(testrunner.TestrunnerUnhandledThreadExceptionWarning(msg))",
        ]
    )


@testrunner.mark.filterwarnings(
    "default::testrunner.TestrunnerUnhandledThreadExceptionWarning"
)
def test_unhandled_thread_exception_in_setup(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_it="""
        import threading
        import testrunner

        @testrunner.fixture
        def threadexc():
            def oops():
                raise ValueError("Oops")
            t = threading.Thread(target=oops, name="MyThread")
            t.start()
            t.join()

        def test_it(threadexc): pass
        def test_2(): pass
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0
    result.assert_outcomes(passed=2, warnings=1)
    result.stdout.fnmatch_lines(
        [
            "*= warnings summary =*",
            "test_it.py::test_it",
            "  * TestrunnerUnhandledThreadExceptionWarning: Exception in thread MyThread",
            "  ",
            "  Traceback (most recent call last):",
            "  ValueError: Oops",
            "  ",
            "    warnings.warn(testrunner.TestrunnerUnhandledThreadExceptionWarning(msg))",
        ]
    )


@testrunner.mark.filterwarnings(
    "default::testrunner.TestrunnerUnhandledThreadExceptionWarning"
)
def test_unhandled_thread_exception_in_teardown(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_it="""
        import threading
        import testrunner

        @testrunner.fixture
        def threadexc():
            def oops():
                raise ValueError("Oops")
            yield
            t = threading.Thread(target=oops, name="MyThread")
            t.start()
            t.join()

        def test_it(threadexc): pass
        def test_2(): pass
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0
    result.assert_outcomes(passed=2, warnings=1)
    result.stdout.fnmatch_lines(
        [
            "*= warnings summary =*",
            "test_it.py::test_it",
            "  * TestrunnerUnhandledThreadExceptionWarning: Exception in thread MyThread",
            "  ",
            "  Traceback (most recent call last):",
            "  ValueError: Oops",
            "  ",
            "    warnings.warn(testrunner.TestrunnerUnhandledThreadExceptionWarning(msg))",
        ]
    )


@testrunner.mark.filterwarnings(
    "error::testrunner.TestrunnerUnhandledThreadExceptionWarning"
)
def test_unhandled_thread_exception_warning_error(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_it="""
        import threading
        import testrunner

        def test_it():
            def oops():
                raise ValueError("Oops")
            t = threading.Thread(target=oops, name="MyThread")
            t.start()
            t.join()

        def test_2(): pass
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == testrunner.ExitCode.TESTS_FAILED
    result.assert_outcomes(passed=1, failed=1)


@testrunner.mark.filterwarnings(
    "error::testrunner.TestrunnerUnhandledThreadExceptionWarning"
)
def test_threadexception_warning_multiple_errors(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_it="""
        import threading

        def test_it():
            def oops():
                raise ValueError("Oops")

            t = threading.Thread(target=oops, name="MyThread")
            t.start()
            t.join()

            t = threading.Thread(target=oops, name="MyThread2")
            t.start()
            t.join()

        def test_2(): pass
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == testrunner.ExitCode.TESTS_FAILED
    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(
        ["  | *ExceptionGroup: multiple thread exception warnings (2 sub-exceptions)"]
    )


def test_unraisable_collection_failure(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_it="""
        import threading

        class Thread(threading.Thread):
            @property
            def name(self):
                raise RuntimeError("oops!")

        def test_it():
            def oops():
                raise ValueError("Oops")

            t = Thread(target=oops, name="MyThread")
            t.start()
            t.join()

        def test_2(): pass
        """
    )

    result = testrunnerer.runtestrunner()
    assert result.ret == 1
    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(
        ["E               RuntimeError: Failed to process thread exception"]
    )


def test_unhandled_thread_exception_after_teardown(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_it="""
        import threading
        import testrunner

        def thread():
            def oops():
                raise ValueError("Oops")

            t = threading.Thread(target=oops, name="MyThread")
            t.start()
            t.join()

        def test_it(request):
            request.config.add_cleanup(thread)
        """
    )

    result = testrunnerer.runtestrunner("-Werror")

    # TODO: should be a test failure or error
    assert result.ret == testrunner.ExitCode.INTERNAL_ERROR

    result.assert_outcomes(passed=1)
    result.stderr.fnmatch_lines("ValueError: Oops")


@testrunner.mark.filterwarnings(
    "error::testrunner.TestrunnerUnhandledThreadExceptionWarning"
)
def test_possibly_none_excinfo(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_it="""
        import threading
        import types

        def test_it():
            threading.excepthook(
                types.SimpleNamespace(
                    exc_type=RuntimeError,
                    exc_value=None,
                    exc_traceback=None,
                    thread=None,
                )
            )
        """
    )

    result = testrunnerer.runtestrunner()

    # TODO: should be a test failure or error
    assert result.ret == testrunner.ExitCode.TESTS_FAILED

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        [
            "E                   testrunner.TestrunnerUnhandledThreadExceptionWarning:"
            " Exception in thread <unknown>",
            "E                   ",
            "E                   NoneType: None",
        ]
    )
