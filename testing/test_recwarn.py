# mypy: allow-untyped-defs
from __future__ import annotations

import re
import sys
import warnings

import testrunner
from testrunner import ExitCode
from testrunner import Testrunnerer
from testrunner import WarningsRecorder


def test_recwarn_stacklevel(recwarn: WarningsRecorder) -> None:
    warnings.warn("hello")
    warn = recwarn.pop()
    assert warn.filename == __file__


def test_recwarn_functional(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import warnings
        def test_method(recwarn):
            warnings.warn("hello")
            warn = recwarn.pop()
            assert isinstance(warn.message, UserWarning)
    """
    )
    reprec = testrunnerer.inline_run()
    reprec.assertoutcome(passed=1)


@testrunner.mark.filterwarnings("")
def test_recwarn_captures_deprecation_warning(recwarn: WarningsRecorder) -> None:
    """
    Check that recwarn can capture DeprecationWarning by default
    without custom filterwarnings (see #8666).
    """
    warnings.warn(DeprecationWarning("some deprecation"))
    assert len(recwarn) == 1
    assert recwarn.pop(DeprecationWarning)


class TestSubclassWarningPop:
    class ParentWarning(Warning):
        pass

    class ChildWarning(ParentWarning):
        pass

    class ChildOfChildWarning(ChildWarning):
        pass

    @staticmethod
    def raise_warnings_from_list(_warnings: list[type[Warning]]):
        for warn in _warnings:
            warnings.warn(f"Warning {warn().__repr__()}", warn)

    def test_pop_finds_exact_match(self):
        with testrunner.warns((self.ParentWarning, self.ChildWarning)) as record:
            self.raise_warnings_from_list(
                [self.ChildWarning, self.ParentWarning, self.ChildOfChildWarning]
            )

        assert len(record) == 3
        _warn = record.pop(self.ParentWarning)
        assert _warn.category is self.ParentWarning

    def test_pop_raises_if_no_match(self):
        with testrunner.raises(AssertionError):
            with testrunner.warns(self.ParentWarning) as record:
                self.raise_warnings_from_list([self.ParentWarning])
            record.pop(self.ChildOfChildWarning)

    def test_pop_finds_best_inexact_match(self):
        with testrunner.warns(self.ParentWarning) as record:
            self.raise_warnings_from_list(
                [self.ChildOfChildWarning, self.ChildWarning, self.ChildOfChildWarning]
            )

        _warn = record.pop(self.ParentWarning)
        assert _warn.category is self.ChildWarning


class TestWarningsRecorderChecker:
    def test_recording(self) -> None:
        rec = WarningsRecorder(_istestrunner=True)
        with rec:
            assert not rec.list
            warnings.warn_explicit("hello", UserWarning, "xyz", 13)
            assert len(rec.list) == 1
            warnings.warn(DeprecationWarning("hello"))
            assert len(rec.list) == 2
            warn = rec.pop()
            assert str(warn.message) == "hello"
            values = rec.list
            rec.clear()
            assert len(rec.list) == 0
            assert values is rec.list
            with testrunner.raises(AssertionError):
                rec.pop()

    def test_warn_stacklevel(self) -> None:
        """#4243"""
        rec = WarningsRecorder(_istestrunner=True)
        with rec:
            warnings.warn("test", DeprecationWarning, 2)

    def test_typechecking(self) -> None:
        from _testrunner.recwarn import WarningsChecker

        with testrunner.raises(TypeError):
            WarningsChecker(5, _istestrunner=True)  # type: ignore[arg-type]
        with testrunner.raises(TypeError):
            WarningsChecker(("hi", RuntimeWarning), _istestrunner=True)  # type: ignore[arg-type]
        with testrunner.raises(TypeError):
            WarningsChecker([DeprecationWarning, RuntimeWarning], _istestrunner=True)  # type: ignore[arg-type]

    def test_invalid_enter_exit(self) -> None:
        # wrap this test in WarningsRecorder to ensure warning state gets reset
        with WarningsRecorder(_istestrunner=True):
            with testrunner.raises(RuntimeError):
                rec = WarningsRecorder(_istestrunner=True)
                rec.__exit__(None, None, None)  # can't exit before entering

            with testrunner.raises(RuntimeError):
                rec = WarningsRecorder(_istestrunner=True)
                with rec:
                    with rec:
                        pass  # can't enter twice


class TestDeprecatedCall:
    """test testrunner.deprecated_call()"""

    def dep(self, i: int, j: int | None = None) -> int:
        if i == 0:
            warnings.warn("is deprecated", DeprecationWarning, stacklevel=1)
        return 42

    def dep_explicit(self, i: int) -> None:
        if i == 0:
            warnings.warn_explicit(
                "dep_explicit", category=DeprecationWarning, filename="hello", lineno=3
            )

    def test_deprecated_call_raises(self) -> None:
        with testrunner.raises(testrunner.fail.Exception, match="No warnings of type"):
            with testrunner.deprecated_call():
                self.dep(3, 5)

    def test_deprecated_call(self) -> None:
        with testrunner.deprecated_call():
            self.dep(0, 5)

    def test_deprecated_call_ret(self) -> None:
        ret = testrunner.deprecated_call(self.dep, 0)
        assert ret == 42

    def test_deprecated_call_preserves(self) -> None:
        # Type ignored because `onceregistry` and `filters` are not
        # documented API.
        onceregistry = warnings.onceregistry.copy()  # type: ignore
        filters = warnings.filters[:]
        warn = warnings.warn
        warn_explicit = warnings.warn_explicit
        self.test_deprecated_call_raises()
        self.test_deprecated_call()
        assert onceregistry == warnings.onceregistry  # type: ignore
        assert filters == warnings.filters
        assert warn is warnings.warn
        assert warn_explicit is warnings.warn_explicit

    def test_deprecated_explicit_call_raises(self) -> None:
        with testrunner.raises(testrunner.fail.Exception):
            with testrunner.deprecated_call():
                self.dep_explicit(3)

    def test_deprecated_explicit_call(self) -> None:
        with testrunner.deprecated_call():
            self.dep_explicit(0)
        with testrunner.deprecated_call():
            self.dep_explicit(0)

    @testrunner.mark.parametrize("mode", ["context_manager", "call"])
    def test_deprecated_call_no_warning(self, mode) -> None:
        """Ensure deprecated_call() raises the expected failure when its block/function does
        not raise a deprecation warning.
        """

        def f():
            pass

        msg = "No warnings of type (.*DeprecationWarning.*, .*PendingDeprecationWarning.*)"
        with testrunner.raises(testrunner.fail.Exception, match=msg):
            if mode == "call":
                testrunner.deprecated_call(f)
            else:
                with testrunner.deprecated_call():
                    f()

    @testrunner.mark.parametrize(
        "warning_type", [PendingDeprecationWarning, DeprecationWarning, FutureWarning]
    )
    @testrunner.mark.parametrize("mode", ["context_manager", "call"])
    @testrunner.mark.parametrize("call_f_first", [True, False])
    @testrunner.mark.filterwarnings("ignore:hi")
    def test_deprecated_call_modes(self, warning_type, mode, call_f_first) -> None:
        """Ensure deprecated_call() captures a deprecation warning as expected inside its
        block/function.
        """

        def f():
            warnings.warn(warning_type("hi"))
            return 10

        # ensure deprecated_call() can capture the warning even if it has already been triggered
        if call_f_first:
            assert f() == 10
        if mode == "call":
            assert testrunner.deprecated_call(f) == 10
        else:
            with testrunner.deprecated_call():
                assert f() == 10

    def test_deprecated_call_specificity(self) -> None:
        other_warnings = [
            Warning,
            UserWarning,
            SyntaxWarning,
            RuntimeWarning,
            ImportWarning,
            UnicodeWarning,
        ]
        for warning in other_warnings:

            def f():
                warnings.warn(warning("hi"))  # noqa: B023

            with testrunner.warns(warning):
                with testrunner.raises(testrunner.fail.Exception):
                    testrunner.deprecated_call(f)
                with testrunner.raises(testrunner.fail.Exception):
                    with testrunner.deprecated_call():
                        f()

    def test_deprecated_call_supports_match(self) -> None:
        with testrunner.deprecated_call(match=r"must be \d+$"):
            warnings.warn("value must be 42", DeprecationWarning)

        with testrunner.deprecated_call():
            with testrunner.raises(
                testrunner.fail.Exception, match="Regex pattern did not match"
            ):
                with testrunner.deprecated_call(match=r"must be \d+$"):
                    warnings.warn("this is not here", DeprecationWarning)


class TestWarns:
    def test_check_callable(self) -> None:
        source = "warnings.warn('w1', RuntimeWarning)"
        with testrunner.raises(TypeError, match=r".* must be callable"):
            testrunner.warns(RuntimeWarning, source)  # type: ignore

    def test_several_messages(self) -> None:
        # different messages, b/c Python suppresses multiple identical warnings
        with testrunner.warns(RuntimeWarning):
            warnings.warn("w1", RuntimeWarning)
        with testrunner.warns(RuntimeWarning):
            with testrunner.raises(testrunner.fail.Exception):
                with testrunner.warns(UserWarning):
                    warnings.warn("w2", RuntimeWarning)
        with testrunner.warns(RuntimeWarning):
            warnings.warn("w3", RuntimeWarning)

    def test_function(self) -> None:
        testrunner.warns(
            SyntaxWarning, lambda msg: warnings.warn(msg, SyntaxWarning), "syntax"
        )

    def test_warning_tuple(self) -> None:
        with testrunner.warns((RuntimeWarning, SyntaxWarning)):
            warnings.warn("w1", RuntimeWarning)
        with testrunner.warns((RuntimeWarning, SyntaxWarning)):
            warnings.warn("w2", SyntaxWarning)
        with testrunner.warns(UserWarning, match="^w3$"):
            with testrunner.raises(testrunner.fail.Exception):
                with testrunner.warns((RuntimeWarning, SyntaxWarning)):
                    warnings.warn("w3", UserWarning)

    def test_as_contextmanager(self) -> None:
        with testrunner.warns(RuntimeWarning):
            warnings.warn("runtime", RuntimeWarning)

        with testrunner.warns(UserWarning):
            warnings.warn("user", UserWarning)

        with testrunner.warns():
            with testrunner.raises(testrunner.fail.Exception) as excinfo:
                with testrunner.warns(RuntimeWarning):
                    warnings.warn("user", UserWarning)
        excinfo.match(
            r"DID NOT WARN. No warnings of type \(.+RuntimeWarning.+,\) were emitted.\n"
            r" Emitted warnings: \[UserWarning\('user',?\)\]."
        )

        with testrunner.warns():
            with testrunner.raises(testrunner.fail.Exception) as excinfo:
                with testrunner.warns(UserWarning):
                    warnings.warn("runtime", RuntimeWarning)
        excinfo.match(
            r"DID NOT WARN. No warnings of type \(.+UserWarning.+,\) were emitted.\n"
            r" Emitted warnings: \[RuntimeWarning\('runtime',?\)]."
        )

        with testrunner.raises(testrunner.fail.Exception) as excinfo:
            with testrunner.warns(UserWarning):
                pass
        excinfo.match(
            r"DID NOT WARN. No warnings of type \(.+UserWarning.+,\) were emitted.\n"
            r" Emitted warnings: \[\]."
        )

        warning_classes = (UserWarning, FutureWarning)
        with testrunner.warns():
            with testrunner.raises(testrunner.fail.Exception) as excinfo:
                with testrunner.warns(warning_classes) as warninfo:
                    warnings.warn("runtime", RuntimeWarning)
                    warnings.warn("import", ImportWarning)

        messages = [each.message for each in warninfo]
        expected_str = (
            f"DID NOT WARN. No warnings of type {warning_classes} were emitted.\n"
            f" Emitted warnings: {messages}."
        )

        assert str(excinfo.value) == expected_str

    def test_record(self) -> None:
        with testrunner.warns(UserWarning) as record:
            warnings.warn("user", UserWarning)

        assert len(record) == 1
        assert str(record[0].message) == "user"

    def test_record_only(self) -> None:
        with testrunner.warns() as record:
            warnings.warn("user", UserWarning)
            warnings.warn("runtime", RuntimeWarning)

        assert len(record) == 2
        assert str(record[0].message) == "user"
        assert str(record[1].message) == "runtime"

    def test_record_only_none_type_error(self) -> None:
        with testrunner.raises(TypeError):
            testrunner.warns(None)  # type: ignore[call-overload]

    def test_record_by_subclass(self) -> None:
        with testrunner.warns(Warning) as record:
            warnings.warn("user", UserWarning)
            warnings.warn("runtime", RuntimeWarning)

        assert len(record) == 2
        assert str(record[0].message) == "user"
        assert str(record[1].message) == "runtime"

        class MyUserWarning(UserWarning):
            pass

        class MyRuntimeWarning(RuntimeWarning):
            pass

        with testrunner.warns((UserWarning, RuntimeWarning)) as record:
            warnings.warn("user", MyUserWarning)
            warnings.warn("runtime", MyRuntimeWarning)

        assert len(record) == 2
        assert str(record[0].message) == "user"
        assert str(record[1].message) == "runtime"

    def test_double_test(self, testrunnerer: Testrunnerer) -> None:
        """If a test is run again, the warning should still be raised"""
        testrunnerer.makepyfile(
            """
            import testrunner
            import warnings

            @testrunner.mark.parametrize('run', [1, 2])
            def test(run):
                with testrunner.warns(RuntimeWarning):
                    warnings.warn("runtime", RuntimeWarning)
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*2 passed in*"])

    def test_match_regex(self) -> None:
        with testrunner.warns(UserWarning, match=r"must be \d+$"):
            warnings.warn("value must be 42", UserWarning)

        with testrunner.warns():
            with testrunner.raises(testrunner.fail.Exception):
                with testrunner.warns(UserWarning, match=r"must be \d+$"):
                    warnings.warn("this is not here", UserWarning)

        with testrunner.warns():
            with testrunner.raises(testrunner.fail.Exception):
                with testrunner.warns(FutureWarning, match=r"must be \d+$"):
                    warnings.warn("value must be 42", UserWarning)

    def test_one_from_multiple_warns(self) -> None:
        with testrunner.warns():
            with testrunner.raises(
                testrunner.fail.Exception, match="Regex pattern did not match"
            ):
                with testrunner.warns(UserWarning, match=r"aaa"):
                    with testrunner.warns(UserWarning, match=r"aaa"):
                        warnings.warn("cccccccccc", UserWarning)
                        warnings.warn("bbbbbbbbbb", UserWarning)
                        warnings.warn("aaaaaaaaaa", UserWarning)

    def test_none_of_multiple_warns(self) -> None:
        with testrunner.warns():
            with testrunner.raises(
                testrunner.fail.Exception, match="Regex pattern did not match"
            ):
                with testrunner.warns(UserWarning, match=r"aaa"):
                    warnings.warn("bbbbbbbbbb", UserWarning)
                    warnings.warn("cccccccccc", UserWarning)

    def test_warns_match_failure_message_detail(self) -> None:
        with testrunner.warns():
            with testrunner.raises(testrunner.fail.Exception) as excinfo:
                with testrunner.warns(UserWarning, match=r"must be \d+$"):
                    warnings.warn("this is not here", UserWarning)
        msg = str(excinfo.value)
        assert "Regex pattern did not match" in msg
        assert "this is not here" in msg
        assert "DID NOT WARN" not in msg

    def test_warns_match_re_escape_hint(self) -> None:
        with testrunner.warns():
            with testrunner.raises(testrunner.fail.Exception) as excinfo:
                with testrunner.warns(UserWarning, match="foo (bar)"):
                    warnings.warn("foo (bar)", UserWarning)
        assert "re.escape()" in str(excinfo.value)

    def test_warns_match_re_escape_hint_no_false_positive(self) -> None:
        with testrunner.warns():
            with testrunner.raises(testrunner.fail.Exception) as excinfo:
                with testrunner.warns(DeprecationWarning, match="foo (bar)"):
                    warnings.warn("some deprecation msg", DeprecationWarning)
                    warnings.warn("foo (bar)", UserWarning)
        assert "re.escape()" not in str(excinfo.value)

    @testrunner.mark.filterwarnings("ignore")
    def test_can_capture_previously_warned(self) -> None:
        def f() -> int:
            warnings.warn(UserWarning("ohai"))
            return 10

        assert f() == 10
        assert testrunner.warns(UserWarning, f) == 10
        assert testrunner.warns(UserWarning, f) == 10
        assert testrunner.warns(UserWarning, f) != "10"  # type: ignore[comparison-overlap]

    def test_warns_context_manager_with_kwargs(self) -> None:
        with testrunner.raises(TypeError) as excinfo:
            with testrunner.warns(UserWarning, foo="bar"):  # type: ignore
                pass
        assert "Unexpected keyword arguments" in str(excinfo.value)

    def test_re_emit_single(self) -> None:
        with testrunner.warns(DeprecationWarning):
            with testrunner.warns(UserWarning):
                warnings.warn("user warning", UserWarning)
                warnings.warn("some deprecation warning", DeprecationWarning)

    def test_re_emit_multiple(self) -> None:
        with testrunner.warns(UserWarning):
            warnings.warn("first warning", UserWarning)
            warnings.warn("second warning", UserWarning)

    def test_re_emit_match_single(self) -> None:
        with testrunner.warns(DeprecationWarning):
            with testrunner.warns(UserWarning, match="user warning"):
                warnings.warn("user warning", UserWarning)
                warnings.warn("some deprecation warning", DeprecationWarning)

    def test_re_emit_match_multiple(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # if anything is re-emitted
            with testrunner.warns(UserWarning, match="user warning"):
                warnings.warn("first user warning", UserWarning)
                warnings.warn("second user warning", UserWarning)

    def test_re_emit_non_match_single(self) -> None:
        with testrunner.warns(UserWarning, match="v2 warning"):
            with testrunner.warns(UserWarning, match="v1 warning"):
                warnings.warn("v1 warning", UserWarning)
                warnings.warn("non-matching v2 warning", UserWarning)

    def test_re_emit_filename_derived_module(self) -> None:
        """Regression test for #11933.

        Re-emitted warnings were attributed to the ``warnings`` module rather
        than the location the warning was originally emitted from, so
        ``module``-based warning filters were applied to the wrong warnings.
        """
        # When no `module` is passed to `warn_explicit`, it derives one from
        # the filename by stripping the ".py" suffix.
        derived_module = re.escape(
            sys._getframe().f_code.co_filename.removesuffix(".py")
        )
        with warnings.catch_warnings():
            # Must not match the re-emitted warning below; before the fix it
            # did, because the warning was attributed to the `warnings` module.
            warnings.filterwarnings("ignore", module="warnings")
            # Must match the re-emitted warning.
            warnings.filterwarnings(
                "error", category=DeprecationWarning, module=derived_module
            )
            with testrunner.raises(DeprecationWarning, match="unmatched"):
                with testrunner.warns(UserWarning, match="user warning"):
                    warnings.warn("user warning", UserWarning)
                    warnings.warn("unmatched", DeprecationWarning)

    def test_catch_warning_within_raise(self) -> None:
        # warns-in-raises works since https://github.com/jacksonsr451/test-runner/pull/11129
        with testrunner.raises(ValueError, match="some exception"):
            with testrunner.warns(FutureWarning, match="some warning"):
                warnings.warn("some warning", category=FutureWarning)
                raise ValueError("some exception")
        # and raises-in-warns has always worked but we'll check for symmetry.
        with testrunner.warns(FutureWarning, match="some warning"):
            with testrunner.raises(ValueError, match="some exception"):
                warnings.warn("some warning", category=FutureWarning)
                raise ValueError("some exception")

    def test_skip_within_warns(self, testrunnerer: Testrunnerer) -> None:
        """Regression test for #11907."""
        testrunnerer.makepyfile(
            """
            import testrunner

            def test_it():
                with testrunner.warns(Warning):
                    testrunner.skip("this is OK")
            """,
        )

        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.OK
        result.assert_outcomes(skipped=1)

    def test_fail_within_warns(self, testrunnerer: Testrunnerer) -> None:
        """Regression test for #11907."""
        testrunnerer.makepyfile(
            """
            import testrunner

            def test_it():
                with testrunner.warns(Warning):
                    testrunner.fail("BOOM")
            """,
        )

        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.TESTS_FAILED
        result.assert_outcomes(failed=1)
        assert "DID NOT WARN" not in str(result.stdout)

    def test_exit_within_warns(self, testrunnerer: Testrunnerer) -> None:
        """Regression test for #11907."""
        testrunnerer.makepyfile(
            """
            import testrunner

            def test_it():
                with testrunner.warns(Warning):
                    testrunner.exit()
            """,
        )

        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.INTERRUPTED
        result.assert_outcomes()

    def test_keyboard_interrupt_within_warns(self, testrunnerer: Testrunnerer) -> None:
        """Regression test for #11907."""
        testrunnerer.makepyfile(
            """
            import testrunner

            def test_it():
                with testrunner.warns(Warning):
                    raise KeyboardInterrupt()
            """,
        )

        result = testrunnerer.runtestrunner_subprocess()
        assert result.ret == ExitCode.INTERRUPTED
        result.assert_outcomes()


def test_raise_type_error_on_invalid_warning() -> None:
    """Check testrunner.warns validates warning messages are strings (#10865) or
    Warning instances (#11959)."""
    with testrunner.raises(TypeError, match="Warning must be str or Warning"):
        with testrunner.warns(UserWarning):
            warnings.warn(1)  # type: ignore


@testrunner.mark.parametrize(
    "message",
    [
        testrunner.param("Warning", id="str"),
        testrunner.param(UserWarning(), id="UserWarning"),
        testrunner.param(Warning(), id="Warning"),
    ],
)
def test_no_raise_type_error_on_valid_warning(message: str | Warning) -> None:
    """Check testrunner.warns validates warning messages are strings (#10865) or
    Warning instances (#11959)."""
    with testrunner.warns(Warning):
        warnings.warn(message)


@testrunner.mark.skipif(
    hasattr(sys, "pypy_version_info"),
    reason="Not for pypy",
)
def test_raise_type_error_on_invalid_warning_message_cpython() -> None:
    # Check that we get the same behavior with the stdlib, at least if filtering
    # (see https://github.com/python/cpython/issues/103577 for details)
    with testrunner.raises(TypeError):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "test")
            warnings.warn(1)  # type: ignore


def test_multiple_arg_custom_warning() -> None:
    """Test for issue #11906."""

    class CustomWarning(UserWarning):
        def __init__(self, a, b):
            pass

    with testrunner.warns(CustomWarning):
        with testrunner.raises(
            testrunner.fail.Exception, match="Regex pattern did not match"
        ):
            with testrunner.warns(CustomWarning, match="not gonna match"):
                a, b = 1, 2
                warnings.warn(CustomWarning(a, b))
