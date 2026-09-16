# mypy: allow-untyped-defs
from __future__ import annotations

import sys

from _testrunner.config import ExitCode
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.testrunnerer import Testrunnerer
import testrunner


def test_simple_unittest(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            def testpassing(self):
                self.assertEqual('foo', 'foo')
            def test_failing(self):
                self.assertEqual('foo', 'bar')
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    assert reprec.matchreport("testpassing").passed
    assert reprec.matchreport("test_failing").failed


def test_runTest_method(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCaseWithRunTest(unittest.TestCase):
            def runTest(self):
                self.assertEqual('foo', 'foo')
        class MyTestCaseWithoutRunTest(unittest.TestCase):
            def runTest(self):
                self.assertEqual('foo', 'foo')
            def test_something(self):
                pass
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.stdout.fnmatch_lines(
        """
        *MyTestCaseWithRunTest::runTest*
        *MyTestCaseWithoutRunTest::test_something*
        *2 passed*
    """
    )


def test_isclasscheck_issue53(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class _E(object):
            def __getattr__(self, tag):
                pass
        E = _E()
    """
    )
    result = testrunnerer.runtestrunner(testpath)
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_setup(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            def setUp(self):
                self.foo = 1
            def setup_method(self, method):
                self.foo2 = 1
            def test_both(self):
                self.assertEqual(1, self.foo)
                assert self.foo2 == 1
            def teardown_method(self, method):
                assert 0, "42"

    """
    )
    reprec = testrunnerer.inline_run("-s", testpath)
    assert reprec.matchreport("test_both", when="call").passed
    rep = reprec.matchreport("test_both", when="teardown")
    assert rep.failed and "42" in str(rep.longrepr)


def test_setUpModule(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        values = []

        def setUpModule():
            values.append(1)

        def tearDownModule():
            del values[0]

        def test_hello():
            assert values == [1]

        def test_world():
            assert values == [1]
        """
    )
    result = testrunnerer.runtestrunner(testpath)
    result.stdout.fnmatch_lines(["*2 passed*"])


def test_setUpModule_failing_no_teardown(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        values = []

        def setUpModule():
            0/0

        def tearDownModule():
            values.append(1)

        def test_hello():
            pass
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    reprec.assertoutcome(passed=0, failed=1)
    call = reprec.getcalls("testrunner_runtest_setup")[0]
    assert not call.item.module.values


def test_new_instances(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            def test_func1(self):
                self.x = 2
            def test_func2(self):
                assert not hasattr(self, 'x')
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    reprec.assertoutcome(passed=2)


def test_function_item_obj_is_instance(testrunnerer: Testrunnerer) -> None:
    """item.obj should be a bound method on unittest.TestCase function items (#5390)."""
    testrunnerer.makeconftest(
        """
        def testrunner_runtest_makereport(item, call):
            if call.when == 'call':
                class_ = item.parent.obj
                assert isinstance(item.obj.__self__, class_)
    """
    )
    testrunnerer.makepyfile(
        """
        import unittest

        class Test(unittest.TestCase):
            def test_foo(self):
                pass
    """
    )
    result = testrunnerer.runtestrunner_inprocess()
    result.stdout.fnmatch_lines(["* 1 passed in*"])


def test_teardown(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            values = []
            def test_one(self):
                pass
            def tearDown(self):
                self.values.append(None)
        class Second(unittest.TestCase):
            def test_check(self):
                self.assertEqual(MyTestCase.values, [None])
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    passed, skipped, failed = reprec.countoutcomes()
    assert failed == 0, failed
    assert passed == 2
    assert passed + skipped + failed == 2


def test_teardown_issue1649(testrunnerer: Testrunnerer) -> None:
    """
    Are TestCase objects cleaned up? Often unittest TestCase objects set
    attributes that are large and expensive during test run or setUp.

    The TestCase will not be cleaned up if the test fails, because it
    would then exist in the stackframe.

    Regression test for #1649 (see also #12367).
    """
    testrunnerer.makepyfile(
        """
        import unittest
        import gc

        class TestCaseObjectsShouldBeCleanedUp(unittest.TestCase):
            def test_expensive(self):
                self.an_expensive_obj = object()

            def test_is_it_still_alive(self):
                gc.collect()
                for obj in gc.get_objects():
                    if type(obj).__name__ == "TestCaseObjectsShouldBeCleanedUp":
                        assert not hasattr(obj, "an_expensive_obj")
                        break
                else:
                    assert False, "Could not find TestCaseObjectsShouldBeCleanedUp instance"
        """
    )

    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.OK


def test_unittest_skip_issue148(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest

        @unittest.skip("hello")
        class MyTestCase(unittest.TestCase):
            @classmethod
            def setUpClass(self):
                xxx
            def test_one(self):
                pass
            @classmethod
            def tearDownClass(self):
                xxx
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    reprec.assertoutcome(skipped=1)


def test_unittest_skip_with_autouse_fixture(testrunnerer: Testrunnerer) -> None:
    """Autouse fixtures inside a @unittest.skipIf class should not run (#13885)."""
    testrunnerer.makepyfile(
        """
        import unittest
        import testrunner

        @unittest.skipIf(True, "skip reason")
        class TestSkipped(unittest.TestCase):
            @testrunner.fixture(autouse=True)
            def my_fixture(self):
                raise RuntimeError("fixture should not run")

            def test_one(self):
                pass
    """
    )
    reprec = testrunnerer.inline_run()
    reprec.assertoutcome(skipped=1)


def test_method_and_teardown_failing_reporting(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import unittest
        class TC(unittest.TestCase):
            def tearDown(self):
                assert 0, "down1"
            def test_method(self):
                assert False, "down2"
    """
    )
    result = testrunnerer.runtestrunner("-s")
    assert result.ret == 1
    result.stdout.fnmatch_lines(
        [
            "*tearDown*",
            "*assert 0*",
            "*test_method*",
            "*assert False*",
            "*1 failed*1 error*",
        ]
    )


def test_setup_failure_is_shown(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import unittest
        import testrunner
        class TC(unittest.TestCase):
            def setUp(self):
                assert 0, "down1"
            def test_method(self):
                print("never42")
                xyz
    """
    )
    result = testrunnerer.runtestrunner("-s")
    assert result.ret == 1
    result.stdout.fnmatch_lines(["*setUp*", "*assert 0*down1*", "*1 failed*"])
    result.stdout.no_fnmatch_line("*never42*")


def test_setup_setUpClass(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        import testrunner
        class MyTestCase(unittest.TestCase):
            x = 0
            @classmethod
            def setUpClass(cls):
                cls.x += 1
            def test_func1(self):
                assert self.x == 1
            def test_func2(self):
                assert self.x == 1
            @classmethod
            def tearDownClass(cls):
                cls.x -= 1
        def test_torn_down():
            assert MyTestCase.x == 0
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    reprec.assertoutcome(passed=3)


def test_fixtures_setup_setUpClass_issue8394(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                pass
            def test_func1(self):
                pass
            @classmethod
            def tearDownClass(cls):
                pass
    """
    )
    result = testrunnerer.runtestrunner("--fixtures")
    assert result.ret == 0
    result.stdout.no_fnmatch_line("*no docstring available*")

    result = testrunnerer.runtestrunner("--fixtures", "-v")
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*no docstring available*"])


def test_setup_class(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        import testrunner
        class MyTestCase(unittest.TestCase):
            x = 0
            def setup_class(cls):
                cls.x += 1
            def test_func1(self):
                assert self.x == 1
            def test_func2(self):
                assert self.x == 1
            def teardown_class(cls):
                cls.x -= 1
        def test_torn_down():
            assert MyTestCase.x == 0
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    reprec.assertoutcome(passed=3)


@testrunner.mark.parametrize("type", ["Error", "Failure"])
def test_testcase_adderrorandfailure_defers(
    testrunnerer: Testrunnerer, type: str
) -> None:
    testrunnerer.makepyfile(
        f"""
        from unittest import TestCase
        import testrunner
        class MyTestCase(TestCase):
            def run(self, result):
                excinfo = testrunner.raises(ZeroDivisionError, lambda: 0/0)
                try:
                    result.add{type}(self, excinfo._excinfo)
                except KeyboardInterrupt:
                    raise
                except:
                    testrunner.fail("add{type} should not raise")
            def test_hello(self):
                pass
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.no_fnmatch_line("*should not raise*")


@testrunner.mark.parametrize("type", ["Error", "Failure"])
def test_testcase_custom_exception_info(testrunnerer: Testrunnerer, type: str) -> None:
    testrunnerer.makepyfile(
        f"""
        from typing import Generic, TypeVar
        from unittest import TestCase
        import testrunner, _testrunner._code

        class MyTestCase(TestCase):
            def run(self, result):
                excinfo = testrunner.raises(ZeroDivisionError, lambda: 0/0)
                # We fake an incompatible exception info.
                class FakeExceptionInfo(Generic[TypeVar("E")]):
                    def __init__(self, *args, **kwargs):
                        mp.undo()
                        raise TypeError()
                    @classmethod
                    def from_current(cls):
                        return cls()
                    @classmethod
                    def from_exc_info(cls, *args, **kwargs):
                        return cls()
                mp = testrunner.MonkeyPatch()
                mp.setattr(_testrunner._code, 'ExceptionInfo', FakeExceptionInfo)
                try:
                    excinfo = excinfo._excinfo
                    result.add{type}(self, excinfo)
                finally:
                    mp.undo()

            def test_hello(self):
                pass
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            "NOTE: Incompatible Exception Representation*",
            "*ZeroDivisionError*",
            "*1 failed*",
        ]
    )


def test_testcase_totally_incompatible_exception_info(
    testrunnerer: Testrunnerer,
) -> None:
    import _testrunner.unittest

    (item,) = testrunnerer.getitems(
        """
        from unittest import TestCase
        class MyTestCase(TestCase):
            def test_hello(self):
                pass
    """
    )
    assert isinstance(item, _testrunner.unittest.TestCaseFunction)
    item.addError(None, 42)  # type: ignore[arg-type]
    excinfo = item._excinfo
    assert excinfo is not None
    assert "ERROR: Unknown Incompatible" in str(excinfo.pop(0).getrepr())


def test_module_level__testrunner_mark(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        import testrunner
        _testrunner_mark = testrunner.mark.xfail
        class MyTestCase(unittest.TestCase):
            def test_func1(self):
                assert 0
    """
    )
    reprec = testrunnerer.inline_run(testpath, "-s")
    reprec.assertoutcome(skipped=1)


class TestTrialUnittest:
    def setup_class(cls):
        cls.ut = testrunner.importorskip("twisted.trial.unittest")
        # on windows trial uses a socket for a reactor and apparently doesn't close it properly
        # https://twistedmatrix.com/trac/ticket/9227
        cls.ignore_unclosed_socket_warning = ("-W", "always")

    def test_trial_testcase_runtest_not_collected(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            from twisted.trial.unittest import TestCase

            class TC(TestCase):
                def test_hello(self):
                    pass
        """
        )
        reprec = testrunnerer.inline_run(*self.ignore_unclosed_socket_warning)
        reprec.assertoutcome(passed=1)
        testrunnerer.makepyfile(
            """
            from twisted.trial.unittest import TestCase

            class TC(TestCase):
                def runTest(self):
                    pass
        """
        )
        reprec = testrunnerer.inline_run(*self.ignore_unclosed_socket_warning)
        reprec.assertoutcome(passed=1)

    def test_trial_exceptions_with_skips(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            from twisted.trial import unittest
            import testrunner
            class TC(unittest.TestCase):
                def test_hello(self):
                    testrunner.skip("skip_in_method")
                @testrunner.mark.skipif("sys.version_info != 1")
                def test_hello2(self):
                    pass
                @testrunner.mark.xfail(reason="iwanto")
                def test_hello3(self):
                    assert 0
                def test_hello4(self):
                    testrunner.xfail("i2wanto")
                def test_trial_skip(self):
                    pass
                test_trial_skip.skip = "trialselfskip"

                def test_trial_todo(self):
                    assert 0
                test_trial_todo.todo = "mytodo"

                def test_trial_todo_success(self):
                    pass
                test_trial_todo_success.todo = "mytodo"

            class TC2(unittest.TestCase):
                def setup_class(cls):
                    testrunner.skip("skip_in_setup_class")
                def test_method(self):
                    pass
        """
        )
        result = testrunnerer.runtestrunner(
            "-rxs", *self.ignore_unclosed_socket_warning
        )
        result.stdout.fnmatch_lines_random(
            [
                "*XFAIL*test_trial_todo*",
                "*trialselfskip*",
                "*skip_in_setup_class*",
                "*iwanto*",
                "*i2wanto*",
                "*sys.version_info*",
                "*skip_in_method*",
                "*1 failed*4 skipped*3 xfailed*",
            ]
        )
        assert result.ret == 1

    def test_trial_error(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            from twisted.trial.unittest import TestCase
            from twisted.internet.defer import Deferred
            from twisted.internet import reactor

            class TC(TestCase):
                def test_one(self):
                    crash

                def test_two(self):
                    def f(_):
                        crash

                    d = Deferred()
                    d.addCallback(f)
                    reactor.callLater(0.3, d.callback, None)
                    return d

                def test_three(self):
                    def f():
                        pass # will never get called
                    reactor.callLater(0.3, f)
                # will crash at teardown

                def test_four(self):
                    def f(_):
                        reactor.callLater(0.3, f)
                        crash

                    d = Deferred()
                    d.addCallback(f)
                    reactor.callLater(0.3, d.callback, None)
                    return d
                # will crash both at test time and at teardown
        """
        )
        result = testrunnerer.runtestrunner(
            "-vv", "-oconsole_output_style=classic", "-W", "ignore::DeprecationWarning"
        )
        result.stdout.fnmatch_lines(
            [
                "test_trial_error.py::TC::test_four FAILED",
                "test_trial_error.py::TC::test_four ERROR",
                "test_trial_error.py::TC::test_one FAILED",
                "test_trial_error.py::TC::test_three FAILED",
                "test_trial_error.py::TC::test_two FAILED",
                "*ERRORS*",
                "*_ ERROR at teardown of TC.test_four _*",
                "*DelayedCalls*",
                "*= FAILURES =*",
                "*_ TC.test_four _*",
                "*NameError*crash*",
                "*_ TC.test_one _*",
                "*NameError*crash*",
                "*_ TC.test_three _*",
                "*DelayedCalls*",
                "*_ TC.test_two _*",
                "*NameError*crash*",
                "*= 4 failed, 1 error in *",
            ]
        )

    def test_trial_pdb(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            from twisted.trial import unittest
            import testrunner
            class TC(unittest.TestCase):
                def test_hello(self):
                    assert 0, "hellopdb"
        """
        )
        child = testrunnerer.spawn_testrunner(str(p))
        child.expect("hellopdb")
        child.sendeof()

    def test_trial_testcase_skip_property(self, testrunnerer: Testrunnerer) -> None:
        testpath = testrunnerer.makepyfile(
            """
            from twisted.trial import unittest
            class MyTestCase(unittest.TestCase):
                skip = 'dont run'
                def test_func(self):
                    pass
            """
        )
        reprec = testrunnerer.inline_run(testpath, "-s")
        reprec.assertoutcome(skipped=1)

    def test_trial_testfunction_skip_property(self, testrunnerer: Testrunnerer) -> None:
        testpath = testrunnerer.makepyfile(
            """
            from twisted.trial import unittest
            class MyTestCase(unittest.TestCase):
                def test_func(self):
                    pass
                test_func.skip = 'dont run'
            """
        )
        reprec = testrunnerer.inline_run(testpath, "-s")
        reprec.assertoutcome(skipped=1)

    def test_trial_testcase_todo_property(self, testrunnerer: Testrunnerer) -> None:
        testpath = testrunnerer.makepyfile(
            """
            from twisted.trial import unittest
            class MyTestCase(unittest.TestCase):
                todo = 'dont run'
                def test_func(self):
                    assert 0
            """
        )
        reprec = testrunnerer.inline_run(testpath, "-s")
        reprec.assertoutcome(skipped=1)

    def test_trial_testfunction_todo_property(self, testrunnerer: Testrunnerer) -> None:
        testpath = testrunnerer.makepyfile(
            """
            from twisted.trial import unittest
            class MyTestCase(unittest.TestCase):
                def test_func(self):
                    assert 0
                test_func.todo = 'dont run'
            """
        )
        reprec = testrunnerer.inline_run(
            testpath, "-s", *self.ignore_unclosed_socket_warning
        )
        reprec.assertoutcome(skipped=1)


def test_djangolike_testcase(testrunnerer: Testrunnerer) -> None:
    # contributed from Morten Breekevold
    testrunnerer.makepyfile(
        """
        from unittest import TestCase, main

        class DjangoLikeTestCase(TestCase):

            def setUp(self):
                print("setUp()")

            def test_presetup_has_been_run(self):
                print("test_thing()")
                self.assertTrue(hasattr(self, 'was_presetup'))

            def tearDown(self):
                print("tearDown()")

            def __call__(self, result=None):
                try:
                    self._pre_setup()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception:
                    import sys
                    result.addError(self, sys.exc_info())
                    return
                super(DjangoLikeTestCase, self).__call__(result)
                try:
                    self._post_teardown()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception:
                    import sys
                    result.addError(self, sys.exc_info())
                    return

            def _pre_setup(self):
                print("_pre_setup()")
                self.was_presetup = True

            def _post_teardown(self):
                print("_post_teardown()")
    """
    )
    result = testrunnerer.runtestrunner("-s")
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        [
            "*_pre_setup()*",
            "*setUp()*",
            "*test_thing()*",
            "*tearDown()*",
            "*_post_teardown()*",
        ]
    )


def test_unittest_not_shown_in_traceback(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import unittest
        class t(unittest.TestCase):
            def test_hello(self):
                x = 3
                self.assertEqual(x, 4)
    """
    )
    res = testrunnerer.runtestrunner()
    res.stdout.no_fnmatch_line("*failUnlessEqual*")


def test_unorderable_types(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import unittest
        class TestJoinEmpty(unittest.TestCase):
            pass

        def make_test():
            class Test(unittest.TestCase):
                pass
            Test.__name__ = "TestFoo"
            return Test
        TestFoo = make_test()
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.no_fnmatch_line("*TypeError*")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_unittest_typerror_traceback(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import unittest
        class TestJoinEmpty(unittest.TestCase):
            def test_hello(self, arg1):
                pass
    """
    )
    result = testrunnerer.runtestrunner()
    assert "TypeError" in result.stdout.str()
    assert result.ret == 1


@testrunner.mark.parametrize("runner", ["testrunner", "unittest"])
def test_unittest_expected_failure_for_failing_test_is_xfail(
    testrunnerer: Testrunnerer, runner
) -> None:
    script = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            @unittest.expectedFailure
            def test_failing_test_is_xfail(self):
                assert False
        if __name__ == '__main__':
            unittest.main()
    """
    )
    if runner == "testrunner":
        result = testrunnerer.runtestrunner("-rxX")
        result.stdout.fnmatch_lines(
            ["*XFAIL*MyTestCase*test_failing_test_is_xfail*", "*1 xfailed*"]
        )
    else:
        result = testrunnerer.runpython(script)
        result.stderr.fnmatch_lines(["*1 test in*", "*OK*(expected failures=1)*"])
    assert result.ret == 0


@testrunner.mark.parametrize("runner", ["testrunner", "unittest"])
def test_unittest_expected_failure_for_passing_test_is_fail(
    testrunnerer: Testrunnerer,
    runner: str,
) -> None:
    script = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            @unittest.expectedFailure
            def test_passing_test_is_fail(self):
                assert True
        if __name__ == '__main__':
            unittest.main()
    """
    )

    if runner == "testrunner":
        result = testrunnerer.runtestrunner("-rxX")
        result.stdout.fnmatch_lines(
            [
                "*MyTestCase*test_passing_test_is_fail*",
                "Unexpected success",
                "*1 failed*",
            ]
        )
    else:
        result = testrunnerer.runpython(script)
        result.stderr.fnmatch_lines(["*1 test in*", "*(unexpected successes=1)*"])

    assert result.ret == 1


@testrunner.mark.parametrize("stmt", ["return", "yield"])
def test_unittest_setup_interaction(testrunnerer: Testrunnerer, stmt: str) -> None:
    testrunnerer.makepyfile(
        f"""
        import unittest
        import testrunner
        class MyTestCase(unittest.TestCase):
            @testrunner.fixture(scope="class", autouse=True)
            @classmethod
            def perclass(cls, request):
                request.cls.hello = "world"
                {stmt}

            @testrunner.fixture(scope="function", autouse=True)
            def perfunction(self, request):
                request.instance.funcname = request.function.__name__
                {stmt}

            def test_method1(self):
                assert self.funcname == "test_method1"
                assert self.hello == "world"

            def test_method2(self):
                assert self.funcname == "test_method2"

            def test_classattr(self):
                assert self.__class__.hello == "world"
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*3 passed*"])


def test_non_unittest_no_setupclass_support(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        class TestFoo(object):
            x = 0

            @classmethod
            def setUpClass(cls):
                cls.x = 1

            def test_method1(self):
                assert self.x == 0

            @classmethod
            def tearDownClass(cls):
                cls.x = 1

        def test_not_torn_down():
            assert TestFoo.x == 0

    """
    )
    reprec = testrunnerer.inline_run(testpath)
    reprec.assertoutcome(passed=2)


def test_no_teardown_if_setupclass_failed(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest

        class MyTestCase(unittest.TestCase):
            x = 0

            @classmethod
            def setUpClass(cls):
                cls.x = 1
                assert False

            def test_func1(self):
                cls.x = 10

            @classmethod
            def tearDownClass(cls):
                cls.x = 100

        def test_notTornDown():
            assert MyTestCase.x == 1
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    reprec.assertoutcome(passed=1, failed=1)


def test_cleanup_functions(testrunnerer: Testrunnerer) -> None:
    """Ensure functions added with addCleanup are always called after each test ends (#6947)"""
    testrunnerer.makepyfile(
        """
        import unittest

        cleanups = []

        class Test(unittest.TestCase):

            def test_func_1(self):
                self.addCleanup(cleanups.append, "test_func_1")

            def test_func_2(self):
                self.addCleanup(cleanups.append, "test_func_2")
                assert 0

            def test_func_3_check_cleanups(self):
                assert cleanups == ["test_func_1", "test_func_2"]
    """
    )
    result = testrunnerer.runtestrunner("-v")
    result.stdout.fnmatch_lines(
        [
            "*::test_func_1 PASSED *",
            "*::test_func_2 FAILED *",
            "*::test_func_3_check_cleanups PASSED *",
        ]
    )


def test_issue333_result_clearing(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
        import testrunner
        @testrunner.hookimpl(wrapper=True)
        def testrunner_runtest_call(item):
            yield
            assert 0
    """
    )
    testrunnerer.makepyfile(
        """
        import unittest
        class TestIt(unittest.TestCase):
            def test_func(self):
                0/0
    """
    )

    reprec = testrunnerer.inline_run()
    reprec.assertoutcome(failed=1)


def test_unittest_raise_skip_issue748(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_foo="""
        import unittest

        class MyTestCase(unittest.TestCase):
            def test_one(self):
                raise unittest.SkipTest('skipping due to reasons')
    """
    )
    result = testrunnerer.runtestrunner("-v", "-rs")
    result.stdout.fnmatch_lines(
        """
        *SKIP*[1]*test_foo.py*skipping due to reasons*
        *1 skipped*
    """
    )


def test_unittest_skip_issue1169(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_foo="""
        import unittest

        class MyTestCase(unittest.TestCase):
            @unittest.skip("skipping due to reasons")
            def test_skip(self):
                 self.fail()
        """
    )
    result = testrunnerer.runtestrunner("-v", "-rs")
    result.stdout.fnmatch_lines(
        """
        *SKIP*[1]*skipping due to reasons*
        *1 skipped*
    """
    )


def test_class_method_containing_test_issue1558(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_foo="""
        import unittest

        class MyTestCase(unittest.TestCase):
            def test_should_run(self):
                pass
            def test_should_not_run(self):
                pass
            test_should_not_run.__test__ = False
    """
    )
    reprec = testrunnerer.inline_run()
    reprec.assertoutcome(passed=1)


@testrunner.mark.parametrize("base", ["builtins.object", "unittest.TestCase"])
def test_usefixtures_marker_on_unittest(base, testrunnerer: Testrunnerer) -> None:
    """#3498"""
    module = base.rsplit(".", 1)[0]
    testrunner.importorskip(module)
    testrunnerer.makepyfile(
        conftest="""
        import testrunner

        @testrunner.fixture(scope='function')
        def fixture1(request, monkeypatch):
            monkeypatch.setattr(request.instance, 'fixture1', True )


        @testrunner.fixture(scope='function')
        def fixture2(request, monkeypatch):
            monkeypatch.setattr(request.instance, 'fixture2', True )

        def node_and_marks(item):
            print(item.nodeid)
            for mark in item.iter_markers():
                print("  ", mark)

        @testrunner.fixture(autouse=True)
        def my_marks(request):
            node_and_marks(request.node)

        def testrunner_collection_modifyitems(items):
            for item in items:
               node_and_marks(item)

        """
    )

    testrunnerer.makepyfile(
        f"""
        import testrunner
        import {module}

        class Tests({base}):
            fixture1 = False
            fixture2 = False

            @testrunner.mark.usefixtures("fixture1")
            def test_one(self):
                assert self.fixture1
                assert not self.fixture2

            @testrunner.mark.usefixtures("fixture1", "fixture2")
            def test_two(self):
                assert self.fixture1
                assert self.fixture2


    """
    )

    result = testrunnerer.runtestrunner("-s")
    result.assert_outcomes(passed=2)


def test_skip_setup_class(testrunnerer: Testrunnerer) -> None:
    """Skipping tests in a class by raising unittest.SkipTest in `setUpClass` (#13985)."""
    testrunnerer.makepyfile(
        """
        import unittest

        class Test(unittest.TestCase):

            @classmethod
            def setUpClass(cls):
                raise unittest.SkipTest('Skipping setupclass')

            def test_foo(self):
                assert False

            def test_bar(self):
                assert False
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(skipped=2)


def test_unittest_skip_function(testrunnerer: Testrunnerer) -> None:
    """
    Ensure raising an explicit unittest.SkipTest skips standard testrunner functions.

    Support for this is debatable -- technically we only support unittest.SkipTest in TestCase subclasses,
    but stating this support here in this test because users currently expect this to work,
    so if we ever break it we at least know we are breaking this use case (#13985).
    """
    testrunnerer.makepyfile(
        """
        import unittest

        def test_foo():
            raise unittest.SkipTest('Skipping test_foo')
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(skipped=1)


def test_testcase_handles_init_exceptions(testrunnerer: Testrunnerer) -> None:
    """
    Regression test to make sure exceptions in the __init__ method are bubbled up correctly.
    See https://github.com/jacksonsr451/test-runner/issues/3788
    """
    testrunnerer.makepyfile(
        """
        from unittest import TestCase
        import testrunner
        class MyTestCase(TestCase):
            def __init__(self, *args, **kwargs):
                raise Exception("should raise this exception")
            def test_hello(self):
                pass
    """
    )
    result = testrunnerer.runtestrunner()
    assert "should raise this exception" in result.stdout.str()
    result.stdout.no_fnmatch_line("*ERROR at teardown of MyTestCase.test_hello*")


def test_error_message_with_parametrized_fixtures(testrunnerer: Testrunnerer) -> None:
    testrunnerer.copy_example("unittest/test_parametrized_fixture_error_message.py")
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            "*test_two does not support fixtures*",
            "*TestSomethingElse::test_two",
            "*Function type: TestCaseFunction",
        ]
    )


@testrunner.mark.parametrize(
    "test_name, expected_outcome",
    [
        ("test_setup_skip.py", "1 skipped"),
        ("test_setup_skip_class.py", "1 skipped"),
        ("test_setup_skip_module.py", "1 error"),
    ],
)
def test_setup_inheritance_skipping(
    testrunnerer: Testrunnerer, test_name, expected_outcome
) -> None:
    """Issue #4700"""
    testrunnerer.copy_example(f"unittest/{test_name}")
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines([f"* {expected_outcome} in *"])


def test_BdbQuit(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_foo="""
        import unittest

        class MyTestCase(unittest.TestCase):
            def test_bdbquit(self):
                import bdb
                raise bdb.BdbQuit()

            def test_should_not_run(self):
                pass
    """
    )
    reprec = testrunnerer.inline_run()
    reprec.assertoutcome(failed=1, passed=1)


def test_exit_outcome(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_foo="""
        import testrunner
        import unittest

        class MyTestCase(unittest.TestCase):
            def test_exit_outcome(self):
                testrunner.exit("testrunner_exit called")

            def test_should_not_run(self):
                pass
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        ["*Exit: testrunner_exit called*", "*= no tests ran in *"]
    )


def test_trace(testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch) -> None:
    calls = []

    def check_call(*args, **kwargs):
        calls.append((args, kwargs))
        assert args == ("runcall",)

        class _pdb:
            def runcall(*args, **kwargs):
                calls.append((args, kwargs))

        return _pdb

    monkeypatch.setattr("_testrunner.debugging.testrunnerPDB._init_pdb", check_call)

    p1 = testrunnerer.makepyfile(
        """
        import unittest

        class MyTestCase(unittest.TestCase):
            def test(self):
                self.assertEqual('foo', 'foo')
    """
    )
    result = testrunnerer.runtestrunner("--trace", str(p1))
    assert len(calls) == 2
    assert result.ret == 0


def test_pdb_teardown_called(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    """Ensure tearDown() is always called when --pdb is given in the command-line.

    We delay the normal tearDown() calls when --pdb is given, so this ensures we are calling
    tearDown() eventually to avoid memory leaks when using --pdb.
    """
    teardowns: list[str] = []
    monkeypatch.setattr(
        testrunner, "test_pdb_teardown_called_teardowns", teardowns, raising=False
    )

    testrunnerer.makepyfile(
        """
        import unittest
        import testrunner

        class MyTestCase(unittest.TestCase):

            def tearDown(self):
                testrunner.test_pdb_teardown_called_teardowns.append(self.id())

            def test_1(self):
                pass
            def test_2(self):
                pass
    """
    )
    result = testrunnerer.runtestrunner_inprocess("--pdb")
    result.stdout.fnmatch_lines("* 2 passed in *")
    assert teardowns == [
        "test_pdb_teardown_called.MyTestCase.test_1",
        "test_pdb_teardown_called.MyTestCase.test_2",
    ]


@testrunner.mark.parametrize("mark", ["@unittest.skip", "@testrunner.mark.skip"])
def test_pdb_teardown_skipped_for_functions(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch, mark: str
) -> None:
    """
    With --pdb, setUp and tearDown should not be called for tests skipped
    via a decorator (#7215).
    """
    tracked: list[str] = []
    monkeypatch.setattr(
        testrunner, "track_pdb_teardown_skipped", tracked, raising=False
    )

    testrunnerer.makepyfile(
        f"""
        import unittest
        import testrunner

        class MyTestCase(unittest.TestCase):

            def setUp(self):
                testrunner.track_pdb_teardown_skipped.append("setUp:" + self.id())

            def tearDown(self):
                testrunner.track_pdb_teardown_skipped.append("tearDown:" + self.id())

            {mark}("skipped for reasons")
            def test_1(self):
                pass

    """
    )
    result = testrunnerer.runtestrunner_inprocess("--pdb")
    result.stdout.fnmatch_lines("* 1 skipped in *")
    assert tracked == []


@testrunner.mark.parametrize("mark", ["@unittest.skip", "@testrunner.mark.skip"])
def test_pdb_teardown_skipped_for_classes(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch, mark: str
) -> None:
    """
    With --pdb, setUp and tearDown should not be called for tests skipped
    via a decorator on the class (#10060).
    """
    tracked: list[str] = []
    monkeypatch.setattr(
        testrunner, "track_pdb_teardown_skipped", tracked, raising=False
    )

    testrunnerer.makepyfile(
        f"""
        import unittest
        import testrunner

        {mark}("skipped for reasons")
        class MyTestCase(unittest.TestCase):

            def setUp(self):
                testrunner.track_pdb_teardown_skipped.append("setUp:" + self.id())

            def tearDown(self):
                testrunner.track_pdb_teardown_skipped.append("tearDown:" + self.id())

            def test_1(self):
                pass

    """
    )
    result = testrunnerer.runtestrunner_inprocess("--pdb")
    result.stdout.fnmatch_lines("* 1 skipped in *")
    assert tracked == []


def test_async_support(testrunnerer: Testrunnerer) -> None:
    testrunner.importorskip("unittest.async_case")

    testrunnerer.copy_example("unittest/test_unittest_asyncio.py")
    reprec = testrunnerer.inline_run()
    reprec.assertoutcome(failed=1, passed=2)


@testrunner.mark.skipif(
    sys.version_info >= (3, 11), reason="asynctest is not compatible with Python 3.11+"
)
def test_asynctest_support(testrunnerer: Testrunnerer) -> None:
    """Check asynctest support (#7110)"""
    testrunner.importorskip("asynctest")
    testrunnerer.copy_example("unittest/test_unittest_asynctest.py")
    reprec = testrunnerer.inline_run()
    reprec.assertoutcome(failed=1, passed=2)


def test_plain_unittest_does_not_support_async(testrunnerer: Testrunnerer) -> None:
    """Async functions in plain unittest.TestCase subclasses are not supported without plugins.

    This test exists here to avoid introducing this support by accident, leading users
    to expect that it works, rather than doing so intentionally as a feature.

    See https://github.com/jacksonsr451/test-runner-asyncio/issues/180 for more context.
    """
    testrunnerer.copy_example("unittest/test_unittest_plain_async.py")
    result = testrunnerer.runtestrunner_subprocess()
    if hasattr(sys, "pypy_version_info"):
        # in PyPy we can't reliable get the warning about the coroutine not being awaited,
        # because it depends on the coroutine being garbage collected; given that
        # we are running in a subprocess, that's difficult to enforce
        expected_lines = ["*1 passed*"]
    else:
        expected_lines = [
            "*RuntimeWarning: coroutine * was never awaited",
            "*1 passed*",
        ]
    result.stdout.fnmatch_lines(expected_lines)


def test_do_class_cleanups_on_success(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            values = []
            @classmethod
            def setUpClass(cls):
                def cleanup():
                    cls.values.append(1)
                cls.addClassCleanup(cleanup)
            def test_one(self):
                pass
            def test_two(self):
                pass
        def test_cleanup_called_exactly_once():
            assert MyTestCase.values == [1]
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    passed, _skipped, failed = reprec.countoutcomes()
    assert failed == 0
    assert passed == 3


def test_do_class_cleanups_on_setupclass_failure(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            values = []
            @classmethod
            def setUpClass(cls):
                def cleanup():
                    cls.values.append(1)
                cls.addClassCleanup(cleanup)
                assert False
            def test_one(self):
                pass
        def test_cleanup_called_exactly_once():
            assert MyTestCase.values == [1]
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    passed, _skipped, failed = reprec.countoutcomes()
    assert failed == 1
    assert passed == 1


def test_do_class_cleanups_on_teardownclass_failure(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            values = []
            @classmethod
            def setUpClass(cls):
                def cleanup():
                    cls.values.append(1)
                cls.addClassCleanup(cleanup)
            @classmethod
            def tearDownClass(cls):
                assert False
            def test_one(self):
                pass
            def test_two(self):
                pass
        def test_cleanup_called_exactly_once():
            assert MyTestCase.values == [1]
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    passed, _skipped, _failed = reprec.countoutcomes()
    assert passed == 3


def test_do_cleanups_on_success(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            values = []
            def setUp(self):
                def cleanup():
                    self.values.append(1)
                self.addCleanup(cleanup)
            def test_one(self):
                pass
            def test_two(self):
                pass
        def test_cleanup_called_the_right_number_of_times():
            assert MyTestCase.values == [1, 1]
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    passed, _skipped, failed = reprec.countoutcomes()
    assert failed == 0
    assert passed == 3


def test_do_cleanups_on_setup_failure(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            values = []
            def setUp(self):
                def cleanup():
                    self.values.append(1)
                self.addCleanup(cleanup)
                assert False
            def test_one(self):
                pass
            def test_two(self):
                pass
        def test_cleanup_called_the_right_number_of_times():
            assert MyTestCase.values == [1, 1]
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    passed, _skipped, failed = reprec.countoutcomes()
    assert failed == 2
    assert passed == 1


def test_do_cleanups_on_teardown_failure(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import unittest
        class MyTestCase(unittest.TestCase):
            values = []
            def setUp(self):
                def cleanup():
                    self.values.append(1)
                self.addCleanup(cleanup)
            def tearDown(self):
                assert False
            def test_one(self):
                pass
            def test_two(self):
                pass
        def test_cleanup_called_the_right_number_of_times():
            assert MyTestCase.values == [1, 1]
    """
    )
    reprec = testrunnerer.inline_run(testpath)
    passed, _skipped, failed = reprec.countoutcomes()
    assert failed == 2
    assert passed == 1


class TestClassCleanupErrors:
    """
    Make sure to show exceptions raised during class cleanup function (those registered
    via addClassCleanup()).

    See #11728.
    """

    def test_class_cleanups_failure_in_setup(self, testrunnerer: Testrunnerer) -> None:
        testpath = testrunnerer.makepyfile(
            """
            import unittest
            class MyTestCase(unittest.TestCase):
                @classmethod
                def setUpClass(cls):
                    def cleanup(n):
                        raise Exception(f"fail {n}")
                    cls.addClassCleanup(cleanup, 2)
                    cls.addClassCleanup(cleanup, 1)
                    raise Exception("fail 0")
                def test(self):
                    pass
        """
        )
        result = testrunnerer.runtestrunner("-s", testpath)
        result.assert_outcomes(passed=0, errors=1)
        result.stdout.fnmatch_lines(
            [
                "*Unittest class cleanup errors *2 sub-exceptions*",
                "*Exception: fail 1",
                "*Exception: fail 2",
            ]
        )
        result.stdout.fnmatch_lines(
            [
                "* ERROR at setup of MyTestCase.test *",
                "*Exception: fail 0",
            ]
        )

    def test_class_cleanups_failure_in_teardown(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testpath = testrunnerer.makepyfile(
            """
            import unittest
            class MyTestCase(unittest.TestCase):
                @classmethod
                def setUpClass(cls):
                    def cleanup(n):
                        raise Exception(f"fail {n}")
                    cls.addClassCleanup(cleanup, 2)
                    cls.addClassCleanup(cleanup, 1)
                def test(self):
                    pass
        """
        )
        result = testrunnerer.runtestrunner("-s", testpath)
        result.assert_outcomes(passed=1, errors=1)
        result.stdout.fnmatch_lines(
            [
                "*Unittest class cleanup errors *2 sub-exceptions*",
                "*Exception: fail 1",
                "*Exception: fail 2",
            ]
        )

    def test_class_cleanup_1_failure_in_teardown(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testpath = testrunnerer.makepyfile(
            """
            import unittest
            class MyTestCase(unittest.TestCase):
                @classmethod
                def setUpClass(cls):
                    def cleanup(n):
                        raise Exception(f"fail {n}")
                    cls.addClassCleanup(cleanup, 1)
                def test(self):
                    pass
        """
        )
        result = testrunnerer.runtestrunner("-s", testpath)
        result.assert_outcomes(passed=1, errors=1)
        result.stdout.fnmatch_lines(
            [
                "*ERROR at teardown of MyTestCase.test*",
                "*Exception: fail 1",
            ]
        )


def test_traceback_pruning(testrunnerer: Testrunnerer) -> None:
    """Regression test for #9610 - doesn't crash during traceback pruning."""
    testrunnerer.makepyfile(
        """
        import unittest

        class MyTestCase(unittest.TestCase):
            def __init__(self, test_method):
                unittest.TestCase.__init__(self, test_method)

        class TestIt(MyTestCase):
            @classmethod
            def tearDownClass(cls) -> None:
                assert False

            def test_it(self):
                pass
        """
    )
    reprec = testrunnerer.inline_run()
    passed, _skipped, failed = reprec.countoutcomes()
    assert passed == 1
    assert failed == 1
    assert reprec.ret == 1


def test_raising_unittest_skiptest_during_collection(
    testrunnerer: Testrunnerer,
) -> None:
    testrunnerer.makepyfile(
        """
        import unittest

        class TestIt(unittest.TestCase):
            def test_it(self): pass
            def test_it2(self): pass

        raise unittest.SkipTest()

        class TestIt2(unittest.TestCase):
            def test_it(self): pass
            def test_it2(self): pass
        """
    )
    reprec = testrunnerer.inline_run()
    passed, skipped, failed = reprec.countoutcomes()
    assert passed == 0
    # Unittest reports one fake test for a skipped module.
    assert skipped == 1
    assert failed == 0
    assert reprec.ret == ExitCode.NO_TESTS_COLLECTED


def test_abstract_testcase_is_not_collected(testrunnerer: Testrunnerer) -> None:
    """Regression test for #12275."""
    testrunnerer.makepyfile(
        """
        import abc
        import unittest

        class TestBase(unittest.TestCase, abc.ABC):
            @abc.abstractmethod
            def abstract1(self): pass

            @abc.abstractmethod
            def abstract2(self): pass

            def test_it(self): pass

        class TestPartial(TestBase):
            def abstract1(self): pass

        class TestConcrete(TestPartial):
            def abstract2(self): pass
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.OK
    result.assert_outcomes(passed=1)
