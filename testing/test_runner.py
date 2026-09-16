# mypy: allow-untyped-defs
from __future__ import annotations

from functools import partial
import inspect
import os
from pathlib import Path
import sys
import types
from typing import cast

from _testrunner import outcomes
from _testrunner import reports
from _testrunner import runner
from _testrunner._code import ExceptionInfo
from _testrunner._code.code import ExceptionChainRepr
from _testrunner.config import ExitCode
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.outcomes import OutcomeException
from _testrunner.testrunnerer import Testrunnerer
import testrunner


if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup


class TestSetupState:
    def test_setup(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem("def test_func(): pass")
        ss = item.session._setupstate
        values = [1]
        ss.setup(item)
        ss.addfinalizer(values.pop, item)
        assert values
        ss.teardown_exact(None)
        assert not values

    def test_teardown_exact_stack_empty(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem("def test_func(): pass")
        ss = item.session._setupstate
        ss.setup(item)
        ss.teardown_exact(None)
        ss.teardown_exact(None)
        ss.teardown_exact(None)

    def test_setup_fails_and_failure_is_cached(
        self, testrunnerer: Testrunnerer
    ) -> None:
        item = testrunnerer.getitem(
            """
            def setup_module(mod):
                raise ValueError(42)
            def test_func(): pass
        """
        )
        ss = item.session._setupstate
        with testrunner.raises(ValueError):
            ss.setup(item)
        with testrunner.raises(ValueError):
            ss.setup(item)

    def test_teardown_multiple_one_fails(self, testrunnerer: Testrunnerer) -> None:
        r = []

        def fin1():
            r.append("fin1")

        def fin2():
            raise Exception("oops")

        def fin3():
            r.append("fin3")

        item = testrunnerer.getitem("def test_func(): pass")
        ss = item.session._setupstate
        ss.setup(item)
        ss.addfinalizer(fin1, item)
        ss.addfinalizer(fin2, item)
        ss.addfinalizer(fin3, item)
        with testrunner.raises(Exception) as err:
            ss.teardown_exact(None)
        assert err.value.args == ("oops",)
        assert r == ["fin3", "fin1"]

    def test_teardown_multiple_fail(self, testrunnerer: Testrunnerer) -> None:
        def fin1():
            raise Exception("oops1")

        def fin2():
            raise Exception("oops2")

        item = testrunnerer.getitem("def test_func(): pass")
        ss = item.session._setupstate
        ss.setup(item)
        ss.addfinalizer(fin1, item)
        ss.addfinalizer(fin2, item)
        with testrunner.raises(ExceptionGroup) as err:
            ss.teardown_exact(None)

        # Note that finalizers are run LIFO, but because FIFO is more intuitive for
        # users we reverse the order of messages, and see the error from fin1 first.
        err1, err2 = err.value.exceptions
        assert err1.args == ("oops1",)
        assert err2.args == ("oops2",)

    def test_teardown_multiple_scopes_one_fails(
        self, testrunnerer: Testrunnerer
    ) -> None:
        module_teardown = []

        def fin_func():
            raise Exception("oops1")

        def fin_module():
            module_teardown.append("fin_module")

        item = testrunnerer.getitem("def test_func(): pass")
        mod = item.listchain()[-2]
        ss = item.session._setupstate
        ss.setup(item)
        ss.addfinalizer(fin_module, mod)
        ss.addfinalizer(fin_func, item)
        with testrunner.raises(Exception, match="oops1"):
            ss.teardown_exact(None)
        assert module_teardown == ["fin_module"]

    def test_teardown_multiple_scopes_several_fail(self, testrunnerer) -> None:
        def raiser(exc):
            raise exc

        item = testrunnerer.getitem("def test_func(): pass")
        mod = item.listchain()[-2]
        ss = item.session._setupstate
        ss.setup(item)
        ss.addfinalizer(partial(raiser, KeyError("from module scope")), mod)
        ss.addfinalizer(partial(raiser, TypeError("from function scope 1")), item)
        ss.addfinalizer(partial(raiser, ValueError("from function scope 2")), item)

        with testrunner.raises(
            ExceptionGroup, match="errors during test teardown"
        ) as e:
            ss.teardown_exact(None)
        mod, func = e.value.exceptions
        assert isinstance(mod, KeyError)
        assert isinstance(func.exceptions[0], TypeError)
        assert isinstance(func.exceptions[1], ValueError)

    def test_cached_exception_doesnt_get_longer(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Regression test for #12204 (the "BTW" case)."""
        testrunnerer.makepyfile(test="")
        # If the collector.setup() raises, all collected items error with this
        # exception.
        testrunnerer.makeconftest(
            """
            import testrunner

            class MyItem(testrunner.Item):
                def runtest(self) -> None: pass

            class MyBadCollector(testrunner.Collector):
                def collect(self):
                    return [
                        MyItem.from_parent(self, name="one"),
                        MyItem.from_parent(self, name="two"),
                        MyItem.from_parent(self, name="three"),
                    ]

                def setup(self):
                    1 / 0

            def testrunner_collect_file(file_path, parent):
                if file_path.name == "test.py":
                    return MyBadCollector.from_parent(parent, name='bad')
            """
        )

        result = testrunnerer.runtestrunner_inprocess("--tb=native")
        assert result.ret == ExitCode.TESTS_FAILED
        failures = result.reprec.getfailures()  # type: ignore[attr-defined]
        assert len(failures) == 3
        lines1 = failures[1].longrepr.reprtraceback.reprentries[0].lines
        lines2 = failures[2].longrepr.reprtraceback.reprentries[0].lines
        assert len(lines1) == len(lines2)


class BaseFunctionalTests:
    def test_passfunction(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            def test_func():
                pass
        """
        )
        rep = reports[1]
        assert rep.passed
        assert not rep.failed
        assert rep.outcome == "passed"
        assert not rep.longrepr

    def test_failfunction(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            def test_func():
                assert 0
        """
        )
        rep = reports[1]
        assert not rep.passed
        assert not rep.skipped
        assert rep.failed
        assert rep.when == "call"
        assert rep.outcome == "failed"
        # assert isinstance(rep.longrepr, ReprExceptionInfo)

    def test_skipfunction(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            import testrunner
            def test_func():
                testrunner.skip("hello")
        """
        )
        rep = reports[1]
        assert not rep.failed
        assert not rep.passed
        assert rep.skipped
        assert rep.outcome == "skipped"
        # assert rep.skipped.when == "call"
        # assert rep.skipped.when == "call"
        # assert rep.skipped == "%sreason == "hello"
        # assert rep.skipped.location.lineno == 3
        # assert rep.skipped.location.path
        # assert not rep.skipped.failurerepr

    def test_skip_in_setup_function(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            import testrunner
            def setup_function(func):
                testrunner.skip("hello")
            def test_func():
                pass
        """
        )
        print(reports)
        rep = reports[0]
        assert not rep.failed
        assert not rep.passed
        assert rep.skipped
        # assert rep.skipped.reason == "hello"
        # assert rep.skipped.location.lineno == 3
        # assert rep.skipped.location.lineno == 3
        assert len(reports) == 2
        assert reports[1].passed  # teardown

    def test_failure_in_setup_function(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            import testrunner
            def setup_function(func):
                raise ValueError(42)
            def test_func():
                pass
        """
        )
        rep = reports[0]
        assert not rep.skipped
        assert not rep.passed
        assert rep.failed
        assert rep.when == "setup"
        assert len(reports) == 2

    def test_failure_in_teardown_function(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            import testrunner
            def teardown_function(func):
                raise ValueError(42)
            def test_func():
                pass
        """
        )
        print(reports)
        assert len(reports) == 3
        rep = reports[2]
        assert not rep.skipped
        assert not rep.passed
        assert rep.failed
        assert rep.when == "teardown"
        # assert rep.longrepr.reprcrash.lineno == 3
        # assert rep.longrepr.reprtraceback.reprentries

    def test_custom_failure_repr(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            conftest="""
            import testrunner
            class Function(testrunner.Function):
                def repr_failure(self, excinfo):
                    return "hello"
        """
        )
        reports = testrunnerer.runitem(
            """
            import testrunner
            def test_func():
                assert 0
        """
        )
        rep = reports[1]
        assert not rep.skipped
        assert not rep.passed
        assert rep.failed
        # assert rep.outcome.when == "call"
        # assert rep.failed.where.lineno == 3
        # assert rep.failed.where.path.basename == "test_func.py"
        # assert rep.failed.failurerepr == "hello"

    def test_teardown_final_returncode(self, testrunnerer: Testrunnerer) -> None:
        rec = testrunnerer.inline_runsource(
            """
            def test_func():
                pass
            def teardown_function(func):
                raise ValueError(42)
        """
        )
        assert rec.ret == 1

    def test_logstart_logfinish_hooks(self, testrunnerer: Testrunnerer) -> None:
        rec = testrunnerer.inline_runsource(
            """
            import testrunner
            def test_func():
                pass
        """
        )
        reps = rec.getcalls("testrunner_runtest_logstart testrunner_runtest_logfinish")
        assert [x._name for x in reps] == [
            "testrunner_runtest_logstart",
            "testrunner_runtest_logfinish",
        ]
        for rep in reps:
            assert rep.nodeid == "test_logstart_logfinish_hooks.py::test_func"
            assert rep.location == ("test_logstart_logfinish_hooks.py", 1, "test_func")

    def test_exact_teardown_issue90(self, testrunnerer: Testrunnerer) -> None:
        rec = testrunnerer.inline_runsource(
            """
            import testrunner

            class TestClass(object):
                def test_method(self):
                    pass
                def teardown_class(cls):
                    raise Exception()

            def test_func():
                import sys
                # on python2 exc_info is kept till a function exits
                # so we would end up calling test functions while
                # sys.exc_info would return the indexerror
                # from guessing the lastitem
                excinfo = sys.exc_info()
                import traceback
                assert excinfo[0] is None, \
                       traceback.format_exception(*excinfo)
            def teardown_function(func):
                raise ValueError(42)
        """
        )
        reps = rec.getreports("testrunner_runtest_logreport")
        print(reps)
        for i in range(2):
            assert reps[i].nodeid.endswith("test_method")
            assert reps[i].passed
        assert reps[2].when == "teardown"
        assert reps[2].failed
        assert len(reps) == 6
        for i in range(3, 5):
            assert reps[i].nodeid.endswith("test_func")
            assert reps[i].passed
        assert reps[5].when == "teardown"
        assert reps[5].nodeid.endswith("test_func")
        assert reps[5].failed

    def test_exact_teardown_issue1206(self, testrunnerer: Testrunnerer) -> None:
        """Issue shadowing error with wrong number of arguments on teardown_method."""
        rec = testrunnerer.inline_runsource(
            """
            import testrunner

            class TestClass(object):
                def teardown_method(self, x, y, z):
                    pass

                def test_method(self):
                    assert True
        """
        )
        reps = rec.getreports("testrunner_runtest_logreport")
        print(reps)
        assert len(reps) == 3
        #
        assert reps[0].nodeid.endswith("test_method")
        assert reps[0].passed
        assert reps[0].when == "setup"
        #
        assert reps[1].nodeid.endswith("test_method")
        assert reps[1].passed
        assert reps[1].when == "call"
        #
        assert reps[2].nodeid.endswith("test_method")
        assert reps[2].failed
        assert reps[2].when == "teardown"
        longrepr = reps[2].longrepr
        assert isinstance(longrepr, ExceptionChainRepr)
        assert longrepr.reprcrash
        assert longrepr.reprcrash.message in (
            "TypeError: teardown_method() missing 2 required positional arguments: 'y' and 'z'",
            # Python >= 3.10
            "TypeError: TestClass.teardown_method() missing 2 required positional arguments: 'y' and 'z'",
        )

    def test_failure_in_setup_function_ignores_custom_repr(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            conftest="""
            import testrunner
            class Function(testrunner.Function):
                def repr_failure(self, excinfo):
                    assert 0
        """
        )
        reports = testrunnerer.runitem(
            """
            def setup_function(func):
                raise ValueError(42)
            def test_func():
                pass
        """
        )
        assert len(reports) == 2
        rep = reports[0]
        print(rep)
        assert not rep.skipped
        assert not rep.passed
        assert rep.failed
        # assert rep.outcome.when == "setup"
        # assert rep.outcome.where.lineno == 3
        # assert rep.outcome.where.path.basename == "test_func.py"
        # assert isinstance(rep.failed.failurerepr, PythonFailureRepr)

    def test_systemexit_does_not_bail_out(self, testrunnerer: Testrunnerer) -> None:
        try:
            reports = testrunnerer.runitem(
                """
                def test_func():
                    raise SystemExit(42)
            """
            )
        except SystemExit:
            assert False, "runner did not catch SystemExit"
        rep = reports[1]
        assert rep.failed
        assert rep.when == "call"

    def test_exit_propagates(self, testrunnerer: Testrunnerer) -> None:
        try:
            testrunnerer.runitem(
                """
                import testrunner
                def test_func():
                    raise testrunner.exit.Exception()
            """
            )
        except testrunner.exit.Exception:
            pass
        else:
            assert False, "did not raise"


class TestExecutionNonForked(BaseFunctionalTests):
    def getrunner(self):
        def f(item):
            return runner.runtestprotocol(item, log=False)

        return f

    def test_keyboardinterrupt_propagates(self, testrunnerer: Testrunnerer) -> None:
        try:
            testrunnerer.runitem(
                """
                def test_func():
                    raise KeyboardInterrupt("fake")
            """
            )
        except KeyboardInterrupt:
            pass
        else:
            assert False, "did not raise"

    def test_keyboardinterrupt_clears_request_and_funcargs(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Ensure that an item's fixtures are cleared quickly even if exiting
        early due to a keyboard interrupt (#13626)."""
        item = testrunnerer.getitem(
            """
            import testrunner

            @testrunner.fixture
            def resource():
                return object()

            def test_func(resource):
                raise KeyboardInterrupt("fake")
        """
        )
        assert isinstance(item, testrunner.Function)
        assert item._request
        assert item.funcargs == {}

        try:
            runner.runtestprotocol(item, log=False)
        except KeyboardInterrupt:
            pass
        else:
            assert False, "did not raise"

        assert not cast(object, item._request)
        assert not item.funcargs


class TestSessionReports:
    def test_collect_result(self, testrunnerer: Testrunnerer) -> None:
        col = testrunnerer.getmodulecol(
            """
            def test_func1():
                pass
            class TestClass(object):
                pass
        """
        )
        rep = runner.collect_one_node(col)
        assert not rep.failed
        assert not rep.skipped
        assert rep.passed
        locinfo = rep.location
        assert locinfo is not None
        assert locinfo[0] == col.path.name
        assert not locinfo[1]
        assert locinfo[2] == col.path.name
        res = rep.result
        assert len(res) == 2
        assert res[0].name == "test_func1"
        assert res[1].name == "TestClass"


reporttypes: list[type[reports.BaseReport]] = [
    reports.BaseReport,
    reports.TestReport,
    reports.CollectReport,
]


@testrunner.mark.parametrize(
    "reporttype", reporttypes, ids=[x.__name__ for x in reporttypes]
)
def test_report_extra_parameters(reporttype: type[reports.BaseReport]) -> None:
    args = list(inspect.signature(reporttype.__init__).parameters.keys())[1:]
    basekw: dict[str, object] = {arg: [] for arg in args}
    # nodeid must be a real string (unlike the other placeholder args here) --
    # it's parsed into a structured NodeId internally.
    if "nodeid" in basekw:
        basekw["nodeid"] = ""
    report = reporttype(newthing=1, **basekw)
    assert report.newthing == 1


def test_callinfo() -> None:
    ci = runner.CallInfo.from_call(lambda: 0, "collect")
    assert ci.when == "collect"
    assert ci.result == 0
    assert "result" in repr(ci)
    assert repr(ci) == "<CallInfo when='collect' result: 0>"
    assert str(ci) == "<CallInfo when='collect' result: 0>"

    ci2 = runner.CallInfo.from_call(lambda: 0 / 0, "collect")
    assert ci2.when == "collect"
    assert not hasattr(ci2, "result")
    assert repr(ci2) == f"<CallInfo when='collect' excinfo={ci2.excinfo!r}>"
    assert str(ci2) == repr(ci2)
    assert ci2.excinfo

    # Newlines are escaped.
    def raise_assertion():
        assert 0, "assert_msg"

    ci3 = runner.CallInfo.from_call(raise_assertion, "call")
    assert repr(ci3) == f"<CallInfo when='call' excinfo={ci3.excinfo!r}>"
    assert "\n" not in repr(ci3)


# design question: do we want general hooks in python files?
# then something like the following functional tests makes sense


@testrunner.mark.xfail
def test_runtest_in_module_ordering(testrunnerer: Testrunnerer) -> None:
    p1 = testrunnerer.makepyfile(
        """
        import testrunner
        def testrunner_runtest_setup(item): # runs after class-level!
            item.function.mylist.append("module")
        class TestClass(object):
            def testrunner_runtest_setup(self, item):
                assert not hasattr(item.function, 'mylist')
                item.function.mylist = ['class']
            @testrunner.fixture
            def mylist(self, request):
                return request.function.mylist
            @testrunner.hookimpl(wrapper=True)
            def testrunner_runtest_call(self, item):
                try:
                    yield
                except ValueError:
                    pass
            def test_hello1(self, mylist):
                assert mylist == ['class', 'module'], mylist
                raise ValueError()
            def test_hello2(self, mylist):
                assert mylist == ['class', 'module'], mylist
        def testrunner_runtest_teardown(item):
            del item.function.mylist
    """
    )
    result = testrunnerer.runtestrunner(p1)
    result.stdout.fnmatch_lines(["*2 passed*"])


def test_outcomeexception_exceptionattributes() -> None:
    outcome = outcomes.OutcomeException("test")
    assert outcome.args[0] == outcome.msg


def test_outcomeexception_passes_except_Exception() -> None:
    with testrunner.raises(outcomes.OutcomeException):
        try:
            raise outcomes.OutcomeException("test")
        except Exception as e:
            raise NotImplementedError from e


def test_testrunner_exit() -> None:
    with testrunner.raises(testrunner.exit.Exception) as excinfo:
        testrunner.exit("hello")
    assert excinfo.errisinstance(testrunner.exit.Exception)


def test_testrunner_fail() -> None:
    with testrunner.raises(testrunner.fail.Exception) as excinfo:
        testrunner.fail("hello")
    s = excinfo.exconly(tryshort=True)
    assert s.startswith("Failed")


def test_testrunner_exit_msg(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
    import testrunner

    def testrunner_configure(config):
        testrunner.exit('oh noes')
    """
    )
    result = testrunnerer.runtestrunner()
    result.stderr.fnmatch_lines(["Exit: oh noes"])


def _strip_resource_warnings(lines):
    # Assert no output on stderr, except for unreliable ResourceWarnings.
    # (https://github.com/jacksonsr451/test-runner/issues/5088)
    return [
        x
        for x in lines
        if not x.startswith(("Exception ignored in:", "ResourceWarning"))
    ]


def test_testrunner_exit_returncode(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """\
        import testrunner
        def test_foo():
            testrunner.exit("some exit msg", 99)
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*! *Exit: some exit msg !*"])

    assert _strip_resource_warnings(result.stderr.lines) == []
    assert result.ret == 99

    # It prints to stderr also in case of exit during testrunner_sessionstart.
    testrunnerer.makeconftest(
        """\
        import testrunner

        def testrunner_sessionstart():
            testrunner.exit("during_sessionstart", 98)
        """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*! *Exit: during_sessionstart !*"])
    assert _strip_resource_warnings(result.stderr.lines) == [
        "Exit: during_sessionstart"
    ]
    assert result.ret == 98


def test_testrunner_fail_notrace_runtest(testrunnerer: Testrunnerer) -> None:
    """Test testrunner.fail(..., pytrace=False) does not show tracebacks during test run."""
    testrunnerer.makepyfile(
        """
        import testrunner
        def test_hello():
            testrunner.fail("hello", pytrace=False)
        def teardown_function(function):
            testrunner.fail("world", pytrace=False)
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["world", "hello"])
    result.stdout.no_fnmatch_line("*def teardown_function*")


def test_testrunner_fail_notrace_collection(testrunnerer: Testrunnerer) -> None:
    """Test testrunner.fail(..., pytrace=False) does not show tracebacks during collection."""
    testrunnerer.makepyfile(
        """
        import testrunner
        def some_internal_function():
            testrunner.fail("hello", pytrace=False)
        some_internal_function()
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["hello"])
    result.stdout.no_fnmatch_line("*def some_internal_function()*")


def test_testrunner_fail_notrace_non_ascii(testrunnerer: Testrunnerer) -> None:
    """Fix testrunner.fail with pytrace=False with non-ascii characters (#1178).

    This tests with native and unicode strings containing non-ascii chars.
    """
    testrunnerer.makepyfile(
        """\
        import testrunner

        def test_hello():
            testrunner.fail('oh oh: ☺', pytrace=False)
        """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*test_hello*", "oh oh: ☺"])
    result.stdout.no_fnmatch_line("*def test_hello*")


def test_testrunner_no_tests_collected_exit_status(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*collected 0 items*"])
    assert result.ret == ExitCode.NO_TESTS_COLLECTED

    testrunnerer.makepyfile(
        test_foo="""
        def test_foo():
            assert 1
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*collected 1 item*"])
    result.stdout.fnmatch_lines(["*1 passed*"])
    assert result.ret == ExitCode.OK

    result = testrunnerer.runtestrunner("-k nonmatch")
    result.stdout.fnmatch_lines(["*collected 1 item*"])
    result.stdout.fnmatch_lines(["*1 deselected*"])
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_exception_printing_skip() -> None:
    assert testrunner.skip.Exception == testrunner.skip.Exception
    try:
        testrunner.skip("hello")
    except testrunner.skip.Exception:
        excinfo = ExceptionInfo.from_current()
        s = excinfo.exconly(tryshort=True)
        assert s.startswith("Skipped")


def test_importorskip(monkeypatch) -> None:
    importorskip = testrunner.importorskip

    def f():
        importorskip("asdlkj")

    try:
        sysmod = importorskip("sys")
        assert sysmod is sys
        # path = testrunner.importorskip("os.path")
        # assert path == os.path
        excinfo = testrunner.raises(testrunner.skip.Exception, f)
        assert excinfo is not None
        excrepr = excinfo.getrepr()
        assert excrepr is not None
        assert excrepr.reprcrash is not None
        path = Path(excrepr.reprcrash.path)
        # check that importorskip reports the actual call
        # in this test the test_runner.py file
        assert path.stem == "test_runner"
        with testrunner.raises(SyntaxError):
            testrunner.importorskip("x y z")
        with testrunner.raises(SyntaxError):
            testrunner.importorskip("x=y")
        mod = types.ModuleType("hello123")
        mod.__version__ = "1.3"  # type: ignore
        monkeypatch.setitem(sys.modules, "hello123", mod)
        with testrunner.raises(testrunner.skip.Exception):
            testrunner.importorskip("hello123", minversion="1.3.1")
        mod2 = testrunner.importorskip("hello123", minversion="1.3")
        assert mod2 == mod
    except testrunner.skip.Exception:  # pragma: no cover
        assert False, f"spurious skip: {ExceptionInfo.from_current()}"


def test_importorskip_imports_last_module_part() -> None:
    ospath = testrunner.importorskip("os.path")
    assert os.path == ospath


class TestImportOrSkipExcType:
    """Tests for importorskip's exc_type behavior."""

    def test_module_not_found_skips_by_default(self) -> None:
        with testrunner.raises(testrunner.skip.Exception):
            testrunner.importorskip(
                "TestImportOrSkipExcType_test_module_not_found_skips_without_warning"
            )

    def test_import_error_is_propagated_by_default(
        self, testrunnerer: Testrunnerer
    ) -> None:
        fn = testrunnerer.makepyfile("raise ImportError('some specific problem')")
        testrunnerer.syspathinsert()

        with testrunner.raises(ImportError, match="some specific problem"):
            testrunner.importorskip(fn.stem)

    def test_import_error_can_be_captured_explicitly(
        self, testrunnerer: Testrunnerer
    ) -> None:
        fn = testrunnerer.makepyfile("raise ImportError('some specific problem')")
        testrunnerer.syspathinsert()

        with testrunner.raises(testrunner.skip.Exception):
            testrunner.importorskip(fn.stem, exc_type=ImportError)

    def test_import_error_integration(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            def test_foo():
                testrunner.importorskip("warning_integration_module")
            """
        )
        testrunnerer.makepyfile(
            warning_integration_module="""
                raise ImportError("required library foobar not compiled properly")
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            ["*ImportError: required library foobar not compiled properly*"]
        )
        result.assert_outcomes(failed=1)


def test_importorskip_dev_module(monkeypatch) -> None:
    try:
        mod = types.ModuleType("mockmodule")
        mod.__version__ = "0.13.0.dev-43290"  # type: ignore
        monkeypatch.setitem(sys.modules, "mockmodule", mod)
        mod2 = testrunner.importorskip("mockmodule", minversion="0.12.0")
        assert mod2 == mod
        with testrunner.raises(testrunner.skip.Exception):
            testrunner.importorskip("mockmodule1", minversion="0.14.0")
    except testrunner.skip.Exception:  # pragma: no cover
        assert False, f"spurious skip: {ExceptionInfo.from_current()}"


def test_importorskip_module_level(testrunnerer: Testrunnerer) -> None:
    """`importorskip` must be able to skip entire modules when used at module level."""
    testrunnerer.makepyfile(
        """
        import testrunner
        foobarbaz = testrunner.importorskip("foobarbaz")

        def test_foo():
            pass
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*collected 0 items / 1 skipped*"])


def test_importorskip_custom_reason(testrunnerer: Testrunnerer) -> None:
    """Make sure custom reasons are used."""
    testrunnerer.makepyfile(
        """
        import testrunner
        foobarbaz = testrunner.importorskip("foobarbaz2", reason="just because")

        def test_foo():
            pass
    """
    )
    result = testrunnerer.runtestrunner("-ra")
    result.stdout.fnmatch_lines(["*just because*"])
    result.stdout.fnmatch_lines(["*collected 0 items / 1 skipped*"])


def test_testrunner_cmdline_main(testrunnerer: Testrunnerer) -> None:
    p = testrunnerer.makepyfile(
        """
        import testrunner
        def test_hello():
            assert 1
        if __name__ == '__main__':
           testrunner.cmdline.main([__file__])
    """
    )
    import subprocess

    popen = subprocess.Popen([sys.executable, str(p)], stdout=subprocess.PIPE)
    popen.communicate()
    ret = popen.wait()
    assert ret == 0


def test_unicode_in_longrepr(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """\
        import testrunner
        @testrunner.hookimpl(wrapper=True)
        def testrunner_runtest_makereport():
            rep = yield
            if rep.when == "call":
                rep.longrepr = 'ä'
            return rep
        """
    )
    testrunnerer.makepyfile(
        """
        def test_out():
            assert 0
    """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 1
    assert "UnicodeEncodeError" not in result.stderr.str()


def test_failure_in_setup(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        def setup_module():
            0/0
        def test_func():
            pass
    """
    )
    result = testrunnerer.runtestrunner("--tb=line")
    result.stdout.no_fnmatch_line("*def setup_module*")


def test_makereport_getsource(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        def test_foo():
            if False: pass
            else: assert False
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.no_fnmatch_line("*INTERNALERROR*")
    result.stdout.fnmatch_lines(["*else: assert False*"])


def test_makereport_getsource_dynamic_code(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    """Test that exception in dynamically generated code doesn't break getting the source line."""
    import inspect

    original_findsource = inspect.findsource

    def findsource(obj):
        # Can be triggered by dynamically created functions
        if obj.__name__ == "foo":
            raise IndexError()
        return original_findsource(obj)

    monkeypatch.setattr(inspect, "findsource", findsource)

    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture
        def foo(missing):
            pass

        def test_fix(foo):
            assert False
    """
    )
    result = testrunnerer.runtestrunner("-vv")
    result.stdout.no_fnmatch_line("*INTERNALERROR*")
    result.stdout.fnmatch_lines(["*test_fix*", "*fixture*'missing'*not found*"])


def test_store_except_info_on_error() -> None:
    """Test that upon test failure, the exception info is stored on
    sys.last_traceback and friends."""

    # Simulate item that might raise a specific exception, depending on `raise_error` class var
    class ItemMightRaise:
        nodeid = "item_that_raises"
        raise_error = True

        def runtest(self):
            if self.raise_error:
                raise IndexError("TEST")

    try:
        runner.testrunner_runtest_call(ItemMightRaise())  # type: ignore[arg-type]
    except IndexError:
        pass
    # Check that exception info is stored on sys
    assert sys.last_type is IndexError
    assert isinstance(sys.last_value, IndexError)
    if sys.version_info >= (3, 12, 0):
        assert isinstance(sys.last_exc, IndexError)  # type:ignore[attr-defined]

    assert sys.last_value.args[0] == "TEST"
    assert sys.last_traceback

    # The next run should clear the exception info stored by the previous run
    ItemMightRaise.raise_error = False
    runner.testrunner_runtest_call(ItemMightRaise())  # type: ignore[arg-type]
    assert not hasattr(sys, "last_type")
    assert not hasattr(sys, "last_value")
    if sys.version_info >= (3, 12, 0):
        assert not hasattr(sys, "last_exc")
    assert not hasattr(sys, "last_traceback")


def test_current_test_env_var(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    testrunner_current_test_vars: list[tuple[str, str]] = []
    monkeypatch.setattr(
        sys, "testrunner_current_test_vars", testrunner_current_test_vars, raising=False
    )
    testrunnerer.makepyfile(
        """
        import testrunner
        import sys
        import os

        @testrunner.fixture
        def fix():
            sys.testrunner_current_test_vars.append(('setup', os.environ['TESTRUNNER_CURRENT_TEST']))
            yield
            sys.testrunner_current_test_vars.append(('teardown', os.environ['TESTRUNNER_CURRENT_TEST']))

        def test(fix):
            sys.testrunner_current_test_vars.append(('call', os.environ['TESTRUNNER_CURRENT_TEST']))
    """
    )
    result = testrunnerer.runtestrunner_inprocess()
    assert result.ret == 0
    test_id = "test_current_test_env_var.py::test"
    assert testrunner_current_test_vars == [
        ("setup", test_id + " (setup)"),
        ("call", test_id + " (call)"),
        ("teardown", test_id + " (teardown)"),
    ]
    assert "TESTRUNNER_CURRENT_TEST" not in os.environ


class TestReportContents:
    """Test user-level API of ``TestReport`` objects."""

    def getrunner(self):
        return lambda item: runner.runtestprotocol(item, log=False)

    def test_longreprtext_pass(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            def test_func():
                pass
        """
        )
        rep = reports[1]
        assert rep.longreprtext == ""

    def test_longreprtext_skip(self, testrunnerer: Testrunnerer) -> None:
        """TestReport.longreprtext can handle non-str ``longrepr`` attributes (#7559)"""
        reports = testrunnerer.runitem(
            """
            import testrunner
            def test_func():
                testrunner.skip()
            """
        )
        _, call_rep, _ = reports
        assert isinstance(call_rep.longrepr, tuple)
        assert "Skipped" in call_rep.longreprtext

    def test_longreprtext_collect_skip(self, testrunnerer: Testrunnerer) -> None:
        """CollectReport.longreprtext can handle non-str ``longrepr`` attributes (#7559)"""
        testrunnerer.makepyfile(
            """
            import testrunner
            testrunner.skip(allow_module_level=True)
            """
        )
        rec = testrunnerer.inline_run()
        calls = rec.getcalls("testrunner_collectreport")
        _, call, _ = calls
        assert isinstance(call.report.longrepr, tuple)
        assert "Skipped" in call.report.longreprtext

    def test_longreprtext_failure(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            def test_func():
                x = 1
                assert x == 4
        """
        )
        rep = reports[1]
        assert "assert 1 == 4" in rep.longreprtext

    def test_captured_text(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            import testrunner
            import sys

            @testrunner.fixture
            def fix():
                sys.stdout.write('setup: stdout\\n')
                sys.stderr.write('setup: stderr\\n')
                yield
                sys.stdout.write('teardown: stdout\\n')
                sys.stderr.write('teardown: stderr\\n')
                assert 0

            def test_func(fix):
                sys.stdout.write('call: stdout\\n')
                sys.stderr.write('call: stderr\\n')
                assert 0
        """
        )
        setup, call, teardown = reports
        assert setup.capstdout == "setup: stdout\n"
        assert call.capstdout == "setup: stdout\ncall: stdout\n"
        assert teardown.capstdout == "setup: stdout\ncall: stdout\nteardown: stdout\n"

        assert setup.capstderr == "setup: stderr\n"
        assert call.capstderr == "setup: stderr\ncall: stderr\n"
        assert teardown.capstderr == "setup: stderr\ncall: stderr\nteardown: stderr\n"

    def test_no_captured_text(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            def test_func():
                pass
        """
        )
        rep = reports[1]
        assert rep.capstdout == ""
        assert rep.capstderr == ""

    def test_longrepr_type(self, testrunnerer: Testrunnerer) -> None:
        reports = testrunnerer.runitem(
            """
            import testrunner
            def test_func():
                testrunner.fail(pytrace=False)
        """
        )
        rep = reports[1]
        assert isinstance(rep.longrepr, ExceptionChainRepr)


def test_outcome_exception_bad_msg() -> None:
    """Check that OutcomeExceptions validate their input to prevent confusing errors (#5578)"""

    def func() -> None:
        raise NotImplementedError()

    expected = (
        "OutcomeException expected string as 'msg' parameter, got 'function' instead.\n"
        "Perhaps you meant to use a mark?"
    )
    with testrunner.raises(TypeError) as excinfo:
        OutcomeException(func)  # type: ignore
    assert str(excinfo.value) == expected


def test_testrunner_version_env_var(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("TESTRUNNER_VERSION", "old version")
    testrunnerer.makepyfile(
        """
        import testrunner
        import os


        def test():
            assert os.environ.get("TESTRUNNER_VERSION") == testrunner.__version__
    """
    )
    result = testrunnerer.runtestrunner_inprocess()
    assert result.ret == ExitCode.OK
    assert os.environ["TESTRUNNER_VERSION"] == "old version"


def test_teardown_session_failed(testrunnerer: Testrunnerer) -> None:
    """Test that higher-scoped fixture teardowns run in the context of the last
    item after the test session bails early due to --maxfail.

    Regression test for #11706.
    """
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture(scope="module")
        def baz():
            yield
            testrunner.fail("This is a failing teardown")

        def test_foo(baz):
            testrunner.fail("This is a failing test")

        def test_bar(): pass
        """
    )
    result = testrunnerer.runtestrunner("--maxfail=1")
    result.assert_outcomes(failed=1, errors=1)


def test_teardown_session_stopped(testrunnerer: Testrunnerer) -> None:
    """Test that higher-scoped fixture teardowns run in the context of the last
    item after the test session bails early due to --stepwise.

    Regression test for #11706.
    """
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture(scope="module")
        def baz():
            yield
            testrunner.fail("This is a failing teardown")

        def test_foo(baz):
            testrunner.fail("This is a failing test")

        def test_bar(): pass
        """
    )
    result = testrunnerer.runtestrunner("--stepwise")
    result.assert_outcomes(failed=1, errors=1)
