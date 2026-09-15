# mypy: allow-untyped-defs
from __future__ import annotations

import os
import sys
import warnings

from _testrunner.config import ExitCode
from _testrunner.fixtures import FixtureRequest
from _testrunner.testrunnerer import Testrunnerer
import testrunner


WARNINGS_SUMMARY_HEADER = "warnings summary"


@testrunner.fixture
def pyfile_with_warnings(testrunnerer: Testrunnerer, request: FixtureRequest) -> str:
    """Create a test file which calls a function in a module which generates warnings."""
    testrunnerer.syspathinsert()
    module_name = request.function.__name__[len("test_") :] + "_module"
    test_file = testrunnerer.makepyfile(
        f"""
        import {module_name}
        def test_func():
            assert {module_name}.foo() == 1
        """,
        **{
            module_name: """
            import warnings
            def foo():
                warnings.warn(UserWarning("user warning"))
                warnings.warn(RuntimeWarning("runtime warning"))
                return 1
            """,
        },
    )
    return str(test_file)


@testrunner.mark.filterwarnings("default::UserWarning", "default::RuntimeWarning")
def test_normal_flow(testrunnerer: Testrunnerer, pyfile_with_warnings) -> None:
    """Check that the warnings section is displayed."""
    result = testrunnerer.runtestrunner(pyfile_with_warnings)
    result.stdout.fnmatch_lines(
        [
            f"*== {WARNINGS_SUMMARY_HEADER} ==*",
            "test_normal_flow.py::test_func",
            "*normal_flow_module.py:3: UserWarning: user warning",
            '*  warnings.warn(UserWarning("user warning"))',
            "*normal_flow_module.py:4: RuntimeWarning: runtime warning",
            '*  warnings.warn(RuntimeWarning("runtime warning"))',
            "* 1 passed, 2 warnings*",
        ]
    )


@testrunner.mark.filterwarnings("always::UserWarning")
def test_setup_teardown_warnings(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import warnings
        import testrunner

        @testrunner.fixture
        def fix():
            warnings.warn(UserWarning("warning during setup"))
            yield
            warnings.warn(UserWarning("warning during teardown"))

        def test_func(fix):
            pass
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            f"*== {WARNINGS_SUMMARY_HEADER} ==*",
            "*test_setup_teardown_warnings.py:6: UserWarning: warning during setup",
            '*warnings.warn(UserWarning("warning during setup"))',
            "*test_setup_teardown_warnings.py:8: UserWarning: warning during teardown",
            '*warnings.warn(UserWarning("warning during teardown"))',
            "* 1 passed, 2 warnings*",
        ]
    )


@testrunner.mark.parametrize("method", ["cmdline", "ini"])
def test_as_errors(testrunnerer: Testrunnerer, pyfile_with_warnings, method) -> None:
    args = ("-W", "error") if method == "cmdline" else ()
    if method == "ini":
        testrunnerer.makeini(
            """
            [testrunner]
            filterwarnings=error
            """
        )
    # Use a subprocess, since changing logging level affects other threads
    # (xdist).
    result = testrunnerer.runtestrunner_subprocess(*args, pyfile_with_warnings)
    result.stdout.fnmatch_lines(
        [
            "E       UserWarning: user warning",
            "as_errors_module.py:3: UserWarning",
            "* 1 failed in *",
        ]
    )


@testrunner.mark.parametrize("method", ["cmdline", "ini"])
def test_ignore(testrunnerer: Testrunnerer, pyfile_with_warnings, method) -> None:
    args = ("-W", "ignore") if method == "cmdline" else ()
    if method == "ini":
        testrunnerer.makeini(
            """
        [testrunner]
        filterwarnings= ignore
        """
        )

    result = testrunnerer.runtestrunner(*args, pyfile_with_warnings)
    result.stdout.fnmatch_lines(["* 1 passed in *"])
    assert WARNINGS_SUMMARY_HEADER not in result.stdout.str()


@testrunner.mark.filterwarnings("always::UserWarning")
def test_unicode(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import warnings
        import testrunner


        @testrunner.fixture
        def fix():
            warnings.warn("测试")
            yield

        def test_func(fix):
            pass
        """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            f"*== {WARNINGS_SUMMARY_HEADER} ==*",
            "*test_unicode.py:7: UserWarning: \u6d4b\u8bd5*",
            "* 1 passed, 1 warning*",
        ]
    )


@testrunner.mark.skip("issue #13485")
def test_works_with_filterwarnings(testrunnerer: Testrunnerer) -> None:
    """Ensure our warnings capture does not mess with pre-installed filters (#2430)."""
    testrunnerer.makepyfile(
        """
        import warnings

        class MyWarning(Warning):
            pass

        warnings.filterwarnings("error", category=MyWarning)

        class TestWarnings(object):
            def test_my_warning(self):
                try:
                    warnings.warn(MyWarning("warn!"))
                    assert False
                except MyWarning:
                    assert True
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*== 1 passed in *"])


@testrunner.mark.parametrize("default_config", ["ini", "cmdline"])
def test_filterwarnings_mark(testrunnerer: Testrunnerer, default_config) -> None:
    """Test ``filterwarnings`` mark works and takes precedence over command
    line and ini options."""
    if default_config == "ini":
        testrunnerer.makeini(
            """
            [testrunner]
            filterwarnings = always::RuntimeWarning
        """
        )
    testrunnerer.makepyfile(
        """
        import warnings
        import testrunner

        @testrunner.mark.filterwarnings('ignore::RuntimeWarning')
        def test_ignore_runtime_warning():
            warnings.warn(RuntimeWarning())

        @testrunner.mark.filterwarnings('error')
        def test_warning_error():
            warnings.warn(RuntimeWarning())

        def test_show_warning():
            warnings.warn(RuntimeWarning())
    """
    )
    result = testrunnerer.runtestrunner(
        "-W always::RuntimeWarning" if default_config == "cmdline" else ""
    )
    result.stdout.fnmatch_lines(["*= 1 failed, 2 passed, 1 warning in *"])


def test_non_string_warning_argument(testrunnerer: Testrunnerer) -> None:
    """Non-str argument passed to warning breaks testrunner (#2956)"""
    testrunnerer.makepyfile(
        """\
        import warnings
        import testrunner

        def test():
            warnings.warn(UserWarning(1, 'foo'))
        """
    )
    result = testrunnerer.runtestrunner("-W", "always::UserWarning")
    result.stdout.fnmatch_lines(["*= 1 passed, 1 warning in *"])


def test_filterwarnings_mark_registration(testrunnerer: Testrunnerer) -> None:
    """Ensure filterwarnings mark is registered"""
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.mark.filterwarnings('error')
        def test_func():
            pass
    """
    )
    result = testrunnerer.runtestrunner("--strict-markers")
    assert result.ret == 0


@testrunner.mark.filterwarnings("always::UserWarning")
def test_warning_recorded_hook(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
        def testrunner_configure(config):
            config.issue_config_time_warning(UserWarning("config warning"), stacklevel=2)
    """
    )
    testrunnerer.makepyfile(
        """
        import testrunner, warnings

        warnings.warn(UserWarning("collect warning"))

        @testrunner.fixture
        def fix():
            warnings.warn(UserWarning("setup warning"))
            yield 1
            warnings.warn(UserWarning("teardown warning"))

        def test_func(fix):
            warnings.warn(UserWarning("call warning"))
            assert fix == 1
        """
    )

    collected = []

    class WarningCollector:
        def testrunner_warning_recorded(self, warning_message, when, nodeid, location):
            collected.append((str(warning_message.message), when, nodeid, location))

    result = testrunnerer.runtestrunner(plugins=[WarningCollector()])
    result.stdout.fnmatch_lines(["*1 passed*"])

    expected = [
        ("config warning", "config", ""),
        ("collect warning", "collect", ""),
        ("setup warning", "runtest", "test_warning_recorded_hook.py::test_func"),
        ("call warning", "runtest", "test_warning_recorded_hook.py::test_func"),
        ("teardown warning", "runtest", "test_warning_recorded_hook.py::test_func"),
    ]
    for collected_result, expected_result in zip(collected, expected, strict=True):
        assert collected_result[0] == expected_result[0], str(collected)
        assert collected_result[1] == expected_result[1], str(collected)
        assert collected_result[2] == expected_result[2], str(collected)

        # NOTE: collected_result[3] is location, which differs based on the platform you are on
        #       thus, the best we can do here is assert the types of the parameters match what we expect
        #       and not try and preload it in the expected array
        if collected_result[3] is not None:
            assert type(collected_result[3][0]) is str, str(collected)
            assert type(collected_result[3][1]) is int, str(collected)
            assert type(collected_result[3][2]) is str, str(collected)
        else:
            assert collected_result[3] is None, str(collected)


@testrunner.mark.filterwarnings("always::UserWarning")
def test_collection_warnings(testrunnerer: Testrunnerer) -> None:
    """Check that we also capture warnings issued during test collection (#3251)."""
    testrunnerer.makepyfile(
        """
        import warnings

        warnings.warn(UserWarning("collection warning"))

        def test_foo():
            pass
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            f"*== {WARNINGS_SUMMARY_HEADER} ==*",
            "  *collection_warnings.py:3: UserWarning: collection warning",
            '    warnings.warn(UserWarning("collection warning"))',
            "* 1 passed, 1 warning*",
        ]
    )


@testrunner.mark.filterwarnings("always::UserWarning")
def test_mark_regex_escape(testrunnerer: Testrunnerer) -> None:
    """@testrunner.mark.filterwarnings should not try to escape regex characters (#3936)"""
    testrunnerer.makepyfile(
        r"""
        import testrunner, warnings

        @testrunner.mark.filterwarnings(r"ignore:some \(warning\)")
        def test_foo():
            warnings.warn(UserWarning("some (warning)"))
    """
    )
    result = testrunnerer.runtestrunner()
    assert WARNINGS_SUMMARY_HEADER not in result.stdout.str()


@testrunner.mark.filterwarnings("default::testrunner.TestrunnerWarning")
@testrunner.mark.parametrize("ignore_testrunner_warnings", ["no", "ini", "cmdline"])
def test_hide_testrunner_internal_warnings(
    testrunnerer: Testrunnerer, ignore_testrunner_warnings
) -> None:
    """Make sure we can ignore internal testrunner warnings using a warnings filter."""
    testrunnerer.makepyfile(
        """
        import testrunner
        import warnings

        warnings.warn(testrunner.TestrunnerWarning("some internal warning"))

        def test_bar():
            pass
    """
    )
    if ignore_testrunner_warnings == "ini":
        testrunnerer.makeini(
            """
            [testrunner]
            filterwarnings = ignore::testrunner.TestrunnerWarning
        """
        )
    args = (
        ["-W", "ignore::testrunner.TestrunnerWarning"]
        if ignore_testrunner_warnings == "cmdline"
        else []
    )
    result = testrunnerer.runtestrunner(*args)
    if ignore_testrunner_warnings != "no":
        assert WARNINGS_SUMMARY_HEADER not in result.stdout.str()
    else:
        result.stdout.fnmatch_lines(
            [
                f"*== {WARNINGS_SUMMARY_HEADER} ==*",
                "*test_hide_testrunner_internal_warnings.py:4: TestrunnerWarning: some internal warning",
                "* 1 passed, 1 warning *",
            ]
        )


@testrunner.mark.parametrize("ignore_on_cmdline", [True, False])
def test_option_precedence_cmdline_over_ini(
    testrunnerer: Testrunnerer, ignore_on_cmdline
) -> None:
    """Filters defined in the command-line should take precedence over filters in config files (#3946)."""
    testrunnerer.makeini(
        """
        [testrunner]
        filterwarnings = error::UserWarning
    """
    )
    testrunnerer.makepyfile(
        """
        import warnings
        def test():
            warnings.warn(UserWarning('hello'))
    """
    )
    args = ["-W", "ignore"] if ignore_on_cmdline else []
    result = testrunnerer.runtestrunner(*args)
    if ignore_on_cmdline:
        result.stdout.fnmatch_lines(["* 1 passed in*"])
    else:
        result.stdout.fnmatch_lines(["* 1 failed in*"])


def test_option_precedence_mark(testrunnerer: Testrunnerer) -> None:
    """Filters defined by marks should always take precedence (#3946)."""
    testrunnerer.makeini(
        """
        [testrunner]
        filterwarnings = ignore
    """
    )
    testrunnerer.makepyfile(
        """
        import testrunner, warnings
        @testrunner.mark.filterwarnings('error')
        def test():
            warnings.warn(UserWarning('hello'))
    """
    )
    result = testrunnerer.runtestrunner("-W", "ignore")
    result.stdout.fnmatch_lines(["* 1 failed in*"])


def test_accept_unknown_category(testrunnerer: Testrunnerer) -> None:
    """Category types that can't be imported don't cause failure (#13732)."""
    testrunnerer.makeini(
        """
        [testrunner]
        filterwarnings =
            always:Failed to import filter module.*:testrunner.TestrunnerConfigWarning
            ignore::foobar.Foobar
    """
    )
    testrunnerer.makepyfile(
        """
        def test():
            pass
    """
    )
    result = testrunnerer.runtestrunner_subprocess("-W", "ignore::bizbaz.Bizbaz")
    result.stdout.fnmatch_lines(
        [
            f"*== {WARNINGS_SUMMARY_HEADER} ==*",
            "*TestrunnerConfigWarning: Failed to import filter module 'foobar': ignore::foobar.Foobar",
            "*TestrunnerConfigWarning: Failed to import filter module 'bizbaz': ignore::bizbaz.Bizbaz",
            "* 1 passed, * warning*",
        ]
    )


class TestDeprecationWarningsByDefault:
    """
    Note: all testrunner runs are executed in a subprocess so we don't inherit warning filters
    from testrunner's own test suite
    """

    def create_file(self, testrunnerer: Testrunnerer, mark="") -> None:
        testrunnerer.makepyfile(
            f"""
            import testrunner, warnings

            warnings.warn(DeprecationWarning("collection"))

            {mark}
            def test_foo():
                warnings.warn(PendingDeprecationWarning("test run"))
        """
        )

    @testrunner.mark.parametrize("customize_filters", [True, False])
    def test_shown_by_default(self, testrunnerer: Testrunnerer, customize_filters) -> None:
        """Show deprecation warnings by default, even if user has customized the warnings filters (#4013)."""
        self.create_file(testrunnerer)
        if customize_filters:
            testrunnerer.makeini(
                """
                [testrunner]
                filterwarnings =
                    once::UserWarning
            """
            )
        result = testrunnerer.runtestrunner_subprocess()
        result.stdout.fnmatch_lines(
            [
                f"*== {WARNINGS_SUMMARY_HEADER} ==*",
                "*test_shown_by_default.py:3: DeprecationWarning: collection",
                "*test_shown_by_default.py:7: PendingDeprecationWarning: test run",
                "* 1 passed, 2 warnings*",
            ]
        )

    def test_hidden_by_ini(self, testrunnerer: Testrunnerer) -> None:
        self.create_file(testrunnerer)
        testrunnerer.makeini(
            """
            [testrunner]
            filterwarnings =
                ignore::DeprecationWarning
                ignore::PendingDeprecationWarning
        """
        )
        result = testrunnerer.runtestrunner_subprocess()
        assert WARNINGS_SUMMARY_HEADER not in result.stdout.str()

    def test_hidden_by_mark(self, testrunnerer: Testrunnerer) -> None:
        """Should hide the deprecation warning from the function, but the warning during collection should
        be displayed normally.
        """
        self.create_file(
            testrunnerer,
            mark='@testrunner.mark.filterwarnings("ignore::PendingDeprecationWarning")',
        )
        result = testrunnerer.runtestrunner_subprocess()
        result.stdout.fnmatch_lines(
            [
                f"*== {WARNINGS_SUMMARY_HEADER} ==*",
                "*test_hidden_by_mark.py:3: DeprecationWarning: collection",
                "* 1 passed, 1 warning*",
            ]
        )

    def test_hidden_by_cmdline(self, testrunnerer: Testrunnerer) -> None:
        self.create_file(testrunnerer)
        result = testrunnerer.runtestrunner_subprocess(
            "-W",
            "ignore::DeprecationWarning",
            "-W",
            "ignore::PendingDeprecationWarning",
        )
        assert WARNINGS_SUMMARY_HEADER not in result.stdout.str()

    def test_hidden_by_system(self, testrunnerer: Testrunnerer, monkeypatch) -> None:
        self.create_file(testrunnerer)
        monkeypatch.setenv("PYTHONWARNINGS", "once::UserWarning")
        result = testrunnerer.runtestrunner_subprocess()
        assert WARNINGS_SUMMARY_HEADER not in result.stdout.str()

    def test_invalid_regex_in_filterwarning(self, testrunnerer: Testrunnerer) -> None:
        self.create_file(testrunnerer)
        testrunnerer.makeini(
            """
                [testrunner]
                filterwarnings =
                    ignore::DeprecationWarning:*
            """
        )
        result = testrunnerer.runtestrunner_subprocess()
        assert result.ret == testrunner.ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(
            [
                "ERROR: while parsing the following warning configuration:",
                "",
                "  ignore::DeprecationWarning:[*]",
                "",
                "This error occurred:",
                "",
                "Invalid regex '[*]': nothing to repeat at position 0",
            ]
        )


@testrunner.mark.skip("not relevant until testrunner 10.0")
@testrunner.mark.parametrize("change_default", [None, "ini", "cmdline"])
def test_removed_in_x_warning_as_error(testrunnerer: Testrunnerer, change_default) -> None:
    """This ensures that TestrunnerRemovedInXWarnings raised by testrunner are turned into errors.

    This test should be enabled as part of each major release, and skipped again afterwards
    to ensure our deprecations are turning into warnings as expected.
    """
    testrunnerer.makepyfile(
        """
        import warnings, testrunner
        def test():
            warnings.warn(testrunner.TestrunnerRemovedIn10Warning("some warning"))
    """
    )
    if change_default == "ini":
        testrunnerer.makeini(
            """
            [testrunner]
            filterwarnings =
                ignore::testrunner.TestrunnerRemovedIn10Warning
        """
        )

    args = (
        ("-Wignore::testrunner.TestrunnerRemovedIn10Warning",)
        if change_default == "cmdline"
        else ()
    )
    result = testrunnerer.runtestrunner(*args)
    if change_default is None:
        result.stdout.fnmatch_lines(["* 1 failed in *"])
    else:
        assert change_default in ("ini", "cmdline")
        result.stdout.fnmatch_lines(["* 1 passed in *"])


class TestAssertionWarnings:
    @staticmethod
    def assert_result_warns(result, msg) -> None:
        result.stdout.fnmatch_lines([f"*TestrunnerAssertRewriteWarning: {msg}*"])

    def test_tuple_warning(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """\
            def test_foo():
                assert (1,2)
            """
        )
        result = testrunnerer.runtestrunner()
        self.assert_result_warns(
            result, "assertion is always true, perhaps remove parentheses?"
        )


def test_warnings_checker_twice() -> None:
    """Issue #4617"""
    expectation = testrunner.warns(UserWarning)
    with expectation:
        warnings.warn("Message A", UserWarning)
    with expectation:
        warnings.warn("Message B", UserWarning)


@testrunner.mark.filterwarnings("always::UserWarning")
def test_group_warnings_by_message(testrunnerer: Testrunnerer) -> None:
    testrunnerer.copy_example("warnings/test_group_warnings_by_message.py")
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            f"*== {WARNINGS_SUMMARY_HEADER} ==*",
            "test_group_warnings_by_message.py::test_foo[[]0[]]",
            "test_group_warnings_by_message.py::test_foo[[]1[]]",
            "test_group_warnings_by_message.py::test_foo[[]2[]]",
            "test_group_warnings_by_message.py::test_foo[[]3[]]",
            "test_group_warnings_by_message.py::test_foo[[]4[]]",
            "test_group_warnings_by_message.py::test_foo_1",
            "  */test_group_warnings_by_message.py:*: UserWarning: foo",
            "    warnings.warn(UserWarning(msg))",
            "",
            "test_group_warnings_by_message.py::test_bar[[]0[]]",
            "test_group_warnings_by_message.py::test_bar[[]1[]]",
            "test_group_warnings_by_message.py::test_bar[[]2[]]",
            "test_group_warnings_by_message.py::test_bar[[]3[]]",
            "test_group_warnings_by_message.py::test_bar[[]4[]]",
            "  */test_group_warnings_by_message.py:*: UserWarning: bar",
            "    warnings.warn(UserWarning(msg))",
            "",
            "-- Docs: *",
            "*= 11 passed, 11 warnings *",
        ],
        consecutive=True,
    )


@testrunner.mark.filterwarnings("always::UserWarning")
def test_group_warnings_by_message_summary(testrunnerer: Testrunnerer) -> None:
    testrunnerer.copy_example("warnings/test_group_warnings_by_message_summary")
    testrunnerer.syspathinsert()
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            f"*== {WARNINGS_SUMMARY_HEADER} ==*",
            "test_1.py: 21 warnings",
            "test_2.py: 1 warning",
            "  */test_1.py:10: UserWarning: foo",
            "    warnings.warn(UserWarning(msg))",
            "",
            "test_1.py: 20 warnings",
            "  */test_1.py:10: UserWarning: bar",
            "    warnings.warn(UserWarning(msg))",
            "",
            "-- Docs: *",
            "*= 42 passed, 42 warnings *",
        ],
        consecutive=True,
    )


def test_testrunner_configure_warning(testrunnerer: Testrunnerer, recwarn) -> None:
    """Issue 5115."""
    testrunnerer.makeconftest(
        """
        def testrunner_configure():
            import warnings

            warnings.warn("from testrunner_configure")
        """
    )

    result = testrunnerer.runtestrunner()
    assert result.ret == 5
    assert "INTERNALERROR" not in result.stderr.str()
    warning = recwarn.pop()
    assert str(warning.message) == "from testrunner_configure"


@testrunner.mark.parametrize("tryfirst", [True, False])
def test_testrunner_configure_warning_filter(testrunnerer: Testrunnerer, tryfirst: bool) -> None:
    """Issue 10128.

    Parametrize over ``tryfirst`` to guard against hooks that run early
    from avoiding the filterwarnings configuration.
    """
    testrunnerer.makeini(
        """
        [testrunner]
        filterwarnings =
            ignore::UserWarning
        """
    )
    testrunnerer.makeconftest(
        f"""
        import warnings
        import testrunner

        @testrunner.hookimpl(tryfirst={tryfirst})
        def testrunner_configure():
            warnings.warn("from testrunner_configure", UserWarning)
        """
    )
    testrunnerer.makepyfile("def test_it(): pass")

    result = testrunnerer.runtestrunner_subprocess()

    result.assert_outcomes(passed=1)
    result.stdout.no_fnmatch_line("*from testrunner_configure*")
    result.stderr.no_fnmatch_line("*from testrunner_configure*")


class TestPluginImportWarning:
    """filterwarnings apply to warnings emitted whilst importing plugins.

    Issue #12697.
    """

    @staticmethod
    def _make_plugin_with_import_warning(testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            warning_plugin="""
                import warnings
                warnings.warn("from plugin import", DeprecationWarning)
            """,
            test_it="def test_it(): pass",
        )

    def test_plugin_import_warning(self, testrunnerer: Testrunnerer) -> None:
        self._make_plugin_with_import_warning(testrunnerer)
        testrunnerer.plugins = ["warning_plugin"]

        result = testrunnerer.runtestrunner_subprocess()

        result.assert_outcomes(passed=1, warnings=1)
        result.stdout.fnmatch_lines("*DeprecationWarning: from plugin import")

    def test_plugin_import_warning_without_warnings_plugin(
        self,
        testrunnerer: Testrunnerer,
    ) -> None:
        testrunnerer.makeini(
            """
            [testrunner]
            filterwarnings =
                error::DeprecationWarning
            """
        )
        self._make_plugin_with_import_warning(testrunnerer)
        testrunnerer.plugins = ["warning_plugin"]

        result = testrunnerer.runtestrunner_subprocess("-p", "no:warnings")

        result.assert_outcomes(passed=1)
        result.stdout.no_fnmatch_line("*from plugin import*")
        result.stderr.no_fnmatch_line("*from plugin import*")

    def test_plugin_import_warning_with_warnings_plugin_reenabled(
        self,
        testrunnerer: Testrunnerer,
    ) -> None:
        self._make_plugin_with_import_warning(testrunnerer)
        testrunnerer.syspathinsert()

        result = testrunnerer.runtestrunner(
            "-p", "warning_plugin", "-p", "no:warnings", "-p", "warnings"
        )

        result.assert_outcomes(passed=1)
        result.stdout.fnmatch_lines("*DeprecationWarning: from plugin import")

    def test_plugin_import_warning_from_testrunner_plugins(
        self,
        testrunnerer: Testrunnerer,
        monkeypatch: testrunner.MonkeyPatch,
    ) -> None:
        self._make_plugin_with_import_warning(testrunnerer)
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "warning_plugin")

        result = testrunnerer.runtestrunner_subprocess()

        result.assert_outcomes(passed=1, warnings=1)
        result.stdout.fnmatch_lines("*DeprecationWarning: from plugin import")


class TestStackLevel:
    @testrunner.fixture
    def capwarn(self, testrunnerer: Testrunnerer):
        class CapturedWarnings:
            captured: list[
                tuple[warnings.WarningMessage, tuple[str, int, str] | None]
            ] = []

            @classmethod
            def testrunner_warning_recorded(cls, warning_message, when, nodeid, location):
                cls.captured.append((warning_message, location))

        testrunnerer.plugins = [CapturedWarnings()]

        return CapturedWarnings

    def test_issue4445_rewrite(self, testrunnerer: Testrunnerer, capwarn) -> None:
        """#4445: Make sure the warning points to a reasonable location
        See origin of _issue_warning_captured at: _testrunner.assertion.rewrite.py:241
        """
        testrunnerer.makepyfile(some_mod="")
        conftest = testrunnerer.makeconftest(
            """
                import some_mod
                import testrunner

                testrunner.register_assert_rewrite("some_mod")
            """
        )
        testrunnerer.parseconfig()

        # with stacklevel=5 the warning originates from register_assert_rewrite
        # function in the created conftest.py
        assert len(capwarn.captured) == 1
        warning, location = capwarn.captured.pop()
        file, lineno, func = location

        assert "Module already imported" in str(warning.message)
        assert file == str(conftest)
        assert func == "<module>"  # the above conftest.py
        assert lineno == 4

    def test_issue4445_initial_conftest(self, testrunnerer: Testrunnerer, capwarn) -> None:
        """#4445: Make sure the warning points to a reasonable location."""
        testrunnerer.makeconftest(
            """
            import nothing
            """
        )
        testrunnerer.parseconfig("--help")

        # with stacklevel=2 the warning should originate from config._preparse and is
        # thrown by an erroneous conftest.py
        assert len(capwarn.captured) == 1
        warning, location = capwarn.captured.pop()
        file, _, func = location

        assert "could not load initial conftests" in str(warning.message)
        assert f"config{os.sep}__init__.py" in file
        assert func == "parse"

    @testrunner.mark.filterwarnings("default")
    def test_conftest_warning_captured(self, testrunnerer: Testrunnerer) -> None:
        """Warnings raised during importing of conftest.py files is captured (#2891)."""
        testrunnerer.makeconftest(
            """
            import warnings
            warnings.warn(UserWarning("my custom warning"))
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            ["conftest.py:2", "*UserWarning: my custom warning*"]
        )

    def test_issue4445_import_plugin(self, testrunnerer: Testrunnerer, capwarn) -> None:
        """#4445: Make sure the warning points to a reasonable location"""
        testrunnerer.makepyfile(
            some_plugin="""
            import testrunner
            testrunner.skip("thing", allow_module_level=True)
            """
        )
        testrunnerer.syspathinsert()
        testrunnerer.parseconfig("-p", "some_plugin")

        # with stacklevel=2 the warning should originate from
        # config.TestrunnerPluginManager.import_plugin is thrown by a skipped plugin

        assert len(capwarn.captured) == 1
        warning, location = capwarn.captured.pop()
        file, _, func = location

        assert "skipped plugin 'some_plugin': thing" in str(warning.message)
        assert f"config{os.sep}__init__.py" in file
        assert func == "_warn_about_skipped_plugins"

    def test_issue4445_issue5928_mark_generator(self, testrunnerer: Testrunnerer) -> None:
        """#4445 and #5928: Make sure the warning from an unknown mark points to
        the test file where this mark is used.
        """
        testfile = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.unknown
            def test_it():
                pass
            """
        )
        result = testrunnerer.runtestrunner_subprocess()
        # with stacklevel=2 the warning should originate from the above created test file
        result.stdout.fnmatch_lines_random(
            [
                f"*{testfile}:3*",
                "*Unknown testrunner.mark.unknown*",
            ]
        )


def test_warning_on_testpaths_not_found(testrunnerer: Testrunnerer) -> None:
    # Check for warning when testpaths set, but not found by glob
    testrunnerer.makeini(
        """
        [testrunner]
        testpaths = absent
        """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        ["*ConfigWarning: No files were found in testpaths*", "*1 warning*"]
    )


def test_resource_warning(testrunnerer: Testrunnerer, monkeypatch: testrunner.MonkeyPatch) -> None:
    # Some platforms (notably PyPy) don't have tracemalloc.
    # We choose to explicitly not skip this in case tracemalloc is not
    # available, using `importorskip("tracemalloc")` for example,
    # because we want to ensure the same code path does not break in those platforms.
    try:
        import tracemalloc  # noqa: F401

        has_tracemalloc = True
    except ImportError:
        has_tracemalloc = False

    # Explicitly disable PYTHONTRACEMALLOC in case testrunner's test suite is running
    # with it enabled.
    monkeypatch.delenv("PYTHONTRACEMALLOC", raising=False)

    testrunnerer.makepyfile(
        """
        def open_file(p):
            f = p.open("r", encoding="utf-8")
            assert p.read_text() == "hello"

        def test_resource_warning(tmp_path):
            p = tmp_path.joinpath("foo.txt")
            p.write_text("hello", encoding="utf-8")
            open_file(p)
        """
    )
    result = testrunnerer.run(sys.executable, "-Xdev", "-m", "testrunner")
    expected_extra = (
        [
            "*ResourceWarning* unclosed file*",
            "*Enable tracemalloc to get traceback where the object was allocated*",
            "*See https* for more info.",
        ]
        if has_tracemalloc
        else []
    )
    result.stdout.fnmatch_lines([*expected_extra, "*1 passed*"])

    monkeypatch.setenv("PYTHONTRACEMALLOC", "20")

    result = testrunnerer.run(sys.executable, "-Xdev", "-m", "testrunner")
    expected_extra = (
        [
            "*ResourceWarning* unclosed file*",
            "*Object allocated at*",
        ]
        if has_tracemalloc
        else []
    )
    result.stdout.fnmatch_lines([*expected_extra, "*1 passed*"])


class TestMaxWarnings:
    """Tests for the --max-warnings feature."""

    PYFILE = """
        import warnings
        def test_one():
            warnings.warn(UserWarning("warning one"))
        def test_two():
            warnings.warn(UserWarning("warning two"))
    """

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_not_set(self, testrunnerer: Testrunnerer) -> None:
        """Without --max-warnings, warnings don't affect exit code."""
        testrunnerer.makepyfile(self.PYFILE)
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=2, warnings=2)
        assert result.ret == ExitCode.OK

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_not_exceeded(self, testrunnerer: Testrunnerer) -> None:
        """When warning count is below the threshold, exit code is OK."""
        testrunnerer.makepyfile(self.PYFILE)
        result = testrunnerer.runtestrunner("--max-warnings", "10")
        result.assert_outcomes(passed=2, warnings=2)
        assert result.ret == ExitCode.OK

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_exceeded(self, testrunnerer: Testrunnerer) -> None:
        """When warning count exceeds threshold, exit code is MAX_WARNINGS_ERROR."""
        testrunnerer.makepyfile(self.PYFILE)
        result = testrunnerer.runtestrunner("--max-warnings", "1")
        assert result.ret == ExitCode.MAX_WARNINGS_ERROR

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_equal_to_count(self, testrunnerer: Testrunnerer) -> None:
        """When warning count equals threshold exactly, exit code is OK."""
        testrunnerer.makepyfile(self.PYFILE)
        result = testrunnerer.runtestrunner("--max-warnings", "2")
        result.assert_outcomes(passed=2, warnings=2)
        assert result.ret == ExitCode.OK

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_zero(self, testrunnerer: Testrunnerer) -> None:
        """--max-warnings 0 means no warnings are allowed."""
        testrunnerer.makepyfile(self.PYFILE)
        result = testrunnerer.runtestrunner("--max-warnings", "0")
        assert result.ret == ExitCode.MAX_WARNINGS_ERROR

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_exceeded_message(self, testrunnerer: Testrunnerer) -> None:
        """Verify the output message when max warnings is exceeded."""
        testrunnerer.makepyfile(self.PYFILE)
        result = testrunnerer.runtestrunner("--max-warnings", "1")
        result.stdout.fnmatch_lines(
            ["*Tests pass, but maximum allowed warnings exceeded: 2 > 1*"]
        )

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_ini_option(self, testrunnerer: Testrunnerer) -> None:
        """max_warnings can be set via INI configuration."""
        testrunnerer.makeini(
            """
            [testrunner]
            max_warnings = 1
            """
        )
        testrunnerer.makepyfile(self.PYFILE)
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.MAX_WARNINGS_ERROR

    @testrunner.mark.filterwarnings("default::UserWarning")
    @testrunner.mark.parametrize("value", ["1", '"1"'])
    def test_max_warnings_toml_option(self, testrunnerer: Testrunnerer, value: str) -> None:
        """max_warnings can be set via TOML configuration.

        Supports both int and str (for backward compat).
        """
        testrunnerer.maketoml(
            f"""
            [testrunner]
            max_warnings = {value}
            """
        )
        testrunnerer.makepyfile(self.PYFILE)
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.MAX_WARNINGS_ERROR

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_with_test_failure(self, testrunnerer: Testrunnerer) -> None:
        """When tests fail AND warnings exceed max, TESTS_FAILED takes priority."""
        testrunnerer.makepyfile(
            """
            import warnings
            def test_fail():
                warnings.warn(UserWarning("a warning"))
                assert False
            """
        )
        result = testrunnerer.runtestrunner("--max-warnings", "0")
        assert result.ret == ExitCode.TESTS_FAILED

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_with_filterwarnings_ignore(self, testrunnerer: Testrunnerer) -> None:
        """Filtered (ignored) warnings don't count toward max_warnings."""
        testrunnerer.makepyfile(
            """
            import warnings
            def test_one():
                warnings.warn(UserWarning("counted"))
                warnings.warn(RuntimeWarning("ignored"))
            """
        )
        result = testrunnerer.runtestrunner(
            "--max-warnings",
            "1",
            "-W",
            "ignore::RuntimeWarning",
        )
        result.assert_outcomes(passed=1, warnings=1)
        assert result.ret == ExitCode.OK

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_with_filterwarnings_error(self, testrunnerer: Testrunnerer) -> None:
        """Warnings turned into errors via filterwarnings don't count as warnings."""
        testrunnerer.makepyfile(
            """
            import warnings
            def test_one():
                warnings.warn(UserWarning("still a warning"))
            def test_two():
                warnings.warn(RuntimeWarning("becomes an error"))
            """
        )
        result = testrunnerer.runtestrunner(
            "--max-warnings",
            "0",
            "-W",
            "error::RuntimeWarning",
        )
        # The RuntimeWarning becomes a test error, so TESTS_FAILED takes priority.
        assert result.ret == ExitCode.TESTS_FAILED

    @testrunner.mark.filterwarnings("default::UserWarning")
    def test_max_warnings_with_filterwarnings_ini_ignore(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Warnings ignored via ini filterwarnings don't count toward max_warnings."""
        testrunnerer.makeini(
            """
            [testrunner]
            filterwarnings =
                ignore::RuntimeWarning
            max_warnings = 1
            """
        )
        testrunnerer.makepyfile(
            """
            import warnings
            def test_one():
                warnings.warn(UserWarning("counted"))
                warnings.warn(RuntimeWarning("ignored by ini"))
            """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=1, warnings=1)
        assert result.ret == ExitCode.OK


def test_pythonwarnings_not_duplicated(testrunnerer: Testrunnerer) -> None:
    """Regression test for #13484: -W values should not be duplicated in
    known_args_namespace due to the arg parser being called multiple times."""
    config = testrunnerer.parseconfig("-W", "error")
    warnings_list = config.known_args_namespace.pythonwarnings
    assert warnings_list is not None
    assert warnings_list == ["error"]
