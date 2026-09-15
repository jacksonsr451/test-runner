# mypy: allow-untyped-defs
from __future__ import annotations

from _testrunner._code import getfslineno
from _testrunner.fixtures import getfixturemarker
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.python import Function
import testrunner


def test_wrapped_getfslineno() -> None:
    def func():
        pass

    def wrap(f):
        func.__wrapped__ = f  # type: ignore
        func.patchings = ["qwe"]  # type: ignore
        return func

    @wrap
    def wrapped_func(x, y, z):
        pass

    _fs, lineno = getfslineno(wrapped_func)
    _fs2, lineno2 = getfslineno(wrap)
    assert lineno > lineno2, "getfslineno does not unwrap correctly"


class TestMockDecoration:
    def test_wrapped_getfuncargnames(self) -> None:
        from _testrunner.compat import getfuncargnames

        def wrap(f):
            def func():
                pass

            func.__wrapped__ = f  # type: ignore
            return func

        @wrap
        def f(x):
            pass

        values = getfuncargnames(f)
        assert values == ("x",)

    def test_getfuncargnames_patching(self):
        from unittest.mock import patch

        from _testrunner.compat import getfuncargnames

        class T:
            def original(self, x, y, z):
                pass

        @patch.object(T, "original")
        def f(x, y, z):
            pass

        values = getfuncargnames(f)
        assert values == ("y", "z")

    def test_unittest_mock(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import unittest.mock
            class T(unittest.TestCase):
                @unittest.mock.patch("os.path.abspath")
                def test_hello(self, abspath):
                    import os
                    os.path.abspath("hello")
                    abspath.assert_any_call("hello")
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_unittest_mock_and_fixture(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import os.path
            import unittest.mock
            import testrunner

            @testrunner.fixture
            def inject_me():
                pass

            @unittest.mock.patch.object(os.path, "abspath",
                                        new=unittest.mock.MagicMock)
            def test_hello(inject_me):
                import os
                os.path.abspath("hello")
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_unittest_mock_and_pypi_mock(self, testrunnerer: Testrunnerer) -> None:
        testrunner.importorskip("mock", "1.0.1")
        testrunnerer.makepyfile(
            """
            import mock
            import unittest.mock
            class TestBoth(object):
                @unittest.mock.patch("os.path.abspath")
                def test_hello(self, abspath):
                    import os
                    os.path.abspath("hello")
                    abspath.assert_any_call("hello")

                @mock.patch("os.path.abspath")
                def test_hello_mock(self, abspath):
                    import os
                    os.path.abspath("hello")
                    abspath.assert_any_call("hello")
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_mock_sentinel_check_against_numpy_like(self, testrunnerer: Testrunnerer) -> None:
        """Ensure our function that detects mock arguments compares against sentinels using
        identity to circumvent objects which can't be compared with equality against others
        in a truth context, like with numpy arrays (#5606).
        """
        testrunnerer.makepyfile(
            dummy="""
            class NumpyLike:
                def __init__(self, value):
                    self.value = value
                def __eq__(self, other):
                    raise ValueError("like numpy, cannot compare against others for truth")
            FOO = NumpyLike(10)
        """
        )
        testrunnerer.makepyfile(
            """
            from unittest.mock import patch
            import dummy
            class Test(object):
                @patch("dummy.FOO", new=dummy.NumpyLike(50))
                def test_hello(self):
                    assert dummy.FOO.value == 50
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_mock(self, testrunnerer: Testrunnerer) -> None:
        testrunner.importorskip("mock", "1.0.1")
        testrunnerer.makepyfile(
            """
            import os
            import unittest
            import mock

            class T(unittest.TestCase):
                @mock.patch("os.path.abspath")
                def test_hello(self, abspath):
                    os.path.abspath("hello")
                    abspath.assert_any_call("hello")
            def mock_basename(path):
                return "mock_basename"
            @mock.patch("os.path.abspath")
            @mock.patch("os.path.normpath")
            @mock.patch("os.path.basename", new=mock_basename)
            def test_something(normpath, abspath, tmp_path):
                abspath.return_value = "this"
                os.path.normpath(os.path.abspath("hello"))
                normpath.assert_any_call("this")
                assert os.path.basename("123") == "mock_basename"
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)
        calls = reprec.getcalls("testrunner_runtest_logreport")
        funcnames = [
            call.report.location[2] for call in calls if call.report.when == "call"
        ]
        assert funcnames == ["T.test_hello", "test_something"]

    def test_mock_sorting(self, testrunnerer: Testrunnerer) -> None:
        testrunner.importorskip("mock", "1.0.1")
        testrunnerer.makepyfile(
            """
            import os
            import mock

            @mock.patch("os.path.abspath")
            def test_one(abspath):
                pass
            @mock.patch("os.path.abspath")
            def test_two(abspath):
                pass
            @mock.patch("os.path.abspath")
            def test_three(abspath):
                pass
        """
        )
        reprec = testrunnerer.inline_run()
        calls = reprec.getreports("testrunner_runtest_logreport")
        calls = [x for x in calls if x.when == "call"]
        names = [x.nodeid.split("::")[-1] for x in calls]
        assert names == ["test_one", "test_two", "test_three"]

    def test_mock_double_patch_issue473(self, testrunnerer: Testrunnerer) -> None:
        testrunner.importorskip("mock", "1.0.1")
        testrunnerer.makepyfile(
            """
            from mock import patch
            from testrunner import mark

            @patch('os.getcwd')
            @patch('os.path')
            @mark.slow
            class TestSimple(object):
                def test_simple_thing(self, mock_path, mock_getcwd):
                    pass
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)


class TestReRunTests:
    def test_rerun(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            from _testrunner.runner import runtestprotocol
            def testrunner_runtest_protocol(item, nextitem):
                runtestprotocol(item, log=False, nextitem=nextitem)
                runtestprotocol(item, log=True, nextitem=nextitem)
        """
        )
        testrunnerer.makepyfile(
            """
            import testrunner
            count = 0
            req = None
            @testrunner.fixture
            def fix(request):
                global count, req
                assert request != req
                req = request
                print("fix count %s" % count)
                count += 1
            def test_fix(fix):
                pass
        """
        )
        result = testrunnerer.runtestrunner("-s")
        result.stdout.fnmatch_lines(
            """
            *fix count 0*
            *fix count 1*
        """
        )
        result.stdout.fnmatch_lines(
            """
            *2 passed*
        """
        )


def test_testrunnerconfig_is_session_scoped() -> None:
    from _testrunner.fixtures import testrunnerconfig

    marker = getfixturemarker(testrunnerconfig)
    assert marker is not None
    assert marker.scope == "session"


class TestNoselikeTestAttribute:
    def test_module_with_global_test(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            __test__ = False
            def test_hello():
                pass
        """
        )
        reprec = testrunnerer.inline_run()
        assert not reprec.getfailedcollections()
        calls = reprec.getreports("testrunner_runtest_logreport")
        assert not calls

    def test_class_and_method(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            __test__ = True
            def test_func():
                pass
            test_func.__test__ = False

            class TestSome(object):
                __test__ = False
                def test_method(self):
                    pass
        """
        )
        reprec = testrunnerer.inline_run()
        assert not reprec.getfailedcollections()
        calls = reprec.getreports("testrunner_runtest_logreport")
        assert not calls

    def test_unittest_class(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import unittest
            class TC(unittest.TestCase):
                def test_1(self):
                    pass
            class TC2(unittest.TestCase):
                __test__ = False
                def test_2(self):
                    pass
        """
        )
        reprec = testrunnerer.inline_run()
        assert not reprec.getfailedcollections()
        call = reprec.getcalls("testrunner_collection_modifyitems")[0]
        assert len(call.items) == 1
        assert call.items[0].cls.__name__ == "TC"

    def test_class_with_nasty_getattr(self, testrunnerer: Testrunnerer) -> None:
        """Make sure we handle classes with a custom nasty __getattr__ right.

        With a custom __getattr__ which e.g. returns a function (like with a
        RPC wrapper), we shouldn't assume this meant "__test__ = True".
        """
        # https://github.com/jacksonsr451/test-runner/issues/1204
        testrunnerer.makepyfile(
            """
            class MetaModel(type):

                def __getattr__(cls, key):
                    return lambda: None


            BaseModel = MetaModel('Model', (), {})


            class Model(BaseModel):

                __metaclass__ = MetaModel

                def test_blah(self):
                    pass
        """
        )
        reprec = testrunnerer.inline_run()
        assert not reprec.getfailedcollections()
        call = reprec.getcalls("testrunner_collection_modifyitems")[0]
        assert not call.items


class TestParameterize:
    """#351"""

    def test_idfn_marker(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            def idfn(param):
                if param == 0:
                    return 'spam'
                elif param == 1:
                    return 'ham'
                else:
                    return None

            @testrunner.mark.parametrize('a,b', [(0, 2), (1, 2)], ids=idfn)
            def test_params(a, b):
                pass
        """
        )
        res = testrunnerer.runtestrunner("--collect-only")
        res.stdout.fnmatch_lines(["*spam-2*", "*ham-2*"])

    def test_idfn_fixture(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            def idfn(param):
                if param == 0:
                    return 'spam'
                elif param == 1:
                    return 'ham'
                else:
                    return None

            @testrunner.fixture(params=[0, 1], ids=idfn)
            def a(request):
                return request.param

            @testrunner.fixture(params=[1, 2], ids=idfn)
            def b(request):
                return request.param

            def test_params(a, b):
                pass
        """
        )
        res = testrunnerer.runtestrunner("--collect-only")
        res.stdout.fnmatch_lines(["*spam-2*", "*ham-2*"])

    def test_param_rejects_usefixtures(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.parametrize("x", [
                testrunner.param(1, marks=[testrunner.mark.usefixtures("foo")]),
            ])
            def test_foo(x):
                pass
        """
        )
        res = testrunnerer.runtestrunner("--collect-only")
        res.stdout.fnmatch_lines(
            ["*test_param_rejects_usefixtures.py:4*", "*testrunner.param(*"]
        )


def test_function_instance(testrunnerer: Testrunnerer) -> None:
    items = testrunnerer.getitems(
        """
        def test_func(): pass

        class TestIt:
            def test_method(self): pass

            @classmethod
            def test_class(cls): pass

            @staticmethod
            def test_static(): pass
        """
    )
    assert len(items) == 4

    assert isinstance(items[0], Function)
    assert items[0].name == "test_func"
    assert items[0].instance is None

    assert isinstance(items[1], Function)
    assert items[1].name == "test_method"
    assert items[1].instance is not None
    assert items[1].instance.__class__.__name__ == "TestIt"

    # Even class and static methods get an instance!
    # This is the instance used for bound fixture methods, which
    # class/staticmethod tests are perfectly able to request.
    assert isinstance(items[2], Function)
    assert items[2].name == "test_class"
    assert items[2].instance is not None

    assert isinstance(items[3], Function)
    assert items[3].name == "test_static"
    assert items[3].instance is not None

    assert items[1].instance is not items[2].instance is not items[3].instance
