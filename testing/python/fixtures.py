# mypy: allow-untyped-defs
from __future__ import annotations

from itertools import zip_longest
import os
from pathlib import Path
import sys
import textwrap

from _testrunner.compat import getfuncargnames
from _testrunner.config import ExitCode
from _testrunner.fixtures import deduplicate_names
from _testrunner.fixtures import ParamValueKey
from _testrunner.fixtures import TopRequest
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.python import Function
from _testrunner.testrunnerer import get_public_names
from _testrunner.testrunnerer import Testrunnerer
import testrunner


def test_getfuncargnames_functions():
    """Test getfuncargnames for normal functions"""

    def f():
        raise NotImplementedError()

    assert not getfuncargnames(f)

    def g(arg):
        raise NotImplementedError()

    assert getfuncargnames(g) == ("arg",)

    def h(arg1, arg2="hello"):
        raise NotImplementedError()

    assert getfuncargnames(h) == ("arg1",)

    def j(arg1, arg2, arg3="hello"):
        raise NotImplementedError()

    assert getfuncargnames(j) == ("arg1", "arg2")


def test_getfuncargnames_methods():
    """Test getfuncargnames for normal methods"""

    class A:
        def f(self, arg1, arg2="hello"):
            raise NotImplementedError()

        def g(self, /, arg1, arg2="hello"):
            raise NotImplementedError()

        def h(self, *, arg1, arg2="hello"):
            raise NotImplementedError()

        def j(self, arg1, *, arg2, arg3="hello"):
            raise NotImplementedError()

        def k(self, /, arg1, *, arg2, arg3="hello"):
            raise NotImplementedError()

    assert getfuncargnames(A().f) == ("arg1",)
    assert getfuncargnames(A().g) == ("arg1",)
    assert getfuncargnames(A().h) == ("arg1",)
    assert getfuncargnames(A().j) == ("arg1", "arg2")
    assert getfuncargnames(A().k) == ("arg1", "arg2")


def test_getfuncargnames_staticmethod():
    """Test getfuncargnames for staticmethods"""

    class A:
        @staticmethod
        def static(arg1, arg2, x=1):
            raise NotImplementedError()

    assert getfuncargnames(A.static, cls=A) == ("arg1", "arg2")


def test_getfuncargnames_staticmethod_inherited() -> None:
    """Test getfuncargnames for inherited staticmethods (#8061)"""

    class A:
        @staticmethod
        def static(arg1, arg2, x=1):
            raise NotImplementedError()

    class B(A):
        pass

    assert getfuncargnames(B.static, cls=B) == ("arg1", "arg2")


@testrunner.mark.skipif(
    sys.version_info >= (3, 13),
    reason="""\
In python 3.13, this will raise FutureWarning:
functools.partial will be a method descriptor in future Python versions;
wrap it in staticmethod() if you want to preserve the old behavior

But the wrapped 'functools.partial' is tested by 'test_getfuncargnames_staticmethod_partial' below.
""",
)
def test_getfuncargnames_partial():
    """Check getfuncargnames for methods defined with functools.partial (#5701)"""
    import functools

    def check(arg1, arg2, i):
        raise NotImplementedError()

    class T:
        test_ok = functools.partial(check, i=2)

    values = getfuncargnames(T().test_ok, name="test_ok")
    assert values == ("arg1", "arg2")


def test_getfuncargnames_staticmethod_partial():
    """Check getfuncargnames for staticmethods defined with functools.partial (#5701)"""
    import functools

    def check(arg1, arg2, i):
        raise NotImplementedError()

    class T:
        test_ok = staticmethod(functools.partial(check, i=2))

    values = getfuncargnames(T().test_ok, name="test_ok")
    assert values == ("arg1", "arg2")


@testrunner.mark.testrunnerer_example_path("fixtures/fill_fixtures")
class TestFillFixtures:
    def test_funcarg_lookupfails(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.copy_example()
        result = testrunnerer.runtestrunner()  # "--collect-only")
        assert result.ret != 0
        result.stdout.fnmatch_lines(
            """
            *def test_func(some)*
            *fixture*some*not found*
            *xyzsomething*
            """
        )

    def test_fixture_not_found_nodeid_fallback(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test for fallback string nodeid handling in fixture not found error.

        This test can be deleted with FIXTURE_NODEID_DEPRECATED deprecation.
        """
        testrunnerer.makeconftest(
            """
            import testrunner

            def testrunner_collection_finish(session):
                session._fixturemanager._register_fixture(
                    name="does_exist",
                    func=lambda: 0,
                    nodeid="",
                )
            """
        )
        testrunnerer.makepyfile(
            """
            def test_it(does_not_exist): pass
            """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.TESTS_FAILED
        result.stdout.fnmatch_lines(
            [
                "*fixture 'does_not_exist' not found*",
                "*available fixtures: *does_exist*",
            ]
        )

    def test_detect_recursive_dependency_error(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.copy_example()
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            ["*recursive dependency involving fixture 'fix1' detected*"]
        )

    def test_funcarg_basic(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.copy_example()
        item = testrunnerer.getitem(Path("test_funcarg_basic.py"))
        assert isinstance(item, Function)
        # Execute's item's setup, which fills fixtures.
        item.session._setupstate.setup(item)
        del item.funcargs["request"]
        assert len(get_public_names(item.funcargs)) == 2
        assert item.funcargs["some"] == "test_func"
        assert item.funcargs["other"] == 42

    def test_funcarg_lookup_modulelevel(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.copy_example()
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_funcarg_lookup_classlevel(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.copy_example()
        result = testrunnerer.runtestrunner(p)
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_conftest_funcargs_only_available_in_subdir(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.copy_example()
        result = testrunnerer.runtestrunner("-v")
        result.assert_outcomes(passed=2)

    def test_extend_fixture_module_class(self, testrunnerer: Testrunnerer) -> None:
        testfile = testrunnerer.copy_example()
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 passed*"])
        result = testrunnerer.runtestrunner(testfile)
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_extend_fixture_conftest_module(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.copy_example()
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 passed*"])
        result = testrunnerer.runtestrunner(str(next(Path(str(p)).rglob("test_*.py"))))
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_extend_fixture_conftest_conftest(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.copy_example()
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 passed*"])
        result = testrunnerer.runtestrunner(str(next(Path(str(p)).rglob("test_*.py"))))
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_extend_fixture_conftest_plugin(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            testplugin="""
            import testrunner

            @testrunner.fixture
            def foo():
                return 7
        """
        )
        testrunnerer.syspathinsert()
        testrunnerer.makeconftest(
            """
            import testrunner

            testrunner_plugins = 'testplugin'

            @testrunner.fixture
            def foo(foo):
                return foo + 7
        """
        )
        testrunnerer.makepyfile(
            """
            def test_foo(foo):
                assert foo == 14
        """
        )
        result = testrunnerer.runtestrunner("-s")
        assert result.ret == 0

    def test_extend_fixture_plugin_plugin(self, testrunnerer: Testrunnerer) -> None:
        # Two plugins should extend each order in loading order
        testrunnerer.makepyfile(
            testplugin0="""
            import testrunner

            @testrunner.fixture
            def foo():
                return 7
        """
        )
        testrunnerer.makepyfile(
            testplugin1="""
            import testrunner

            @testrunner.fixture
            def foo(foo):
                return foo + 7
        """
        )
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(
            """
            testrunner_plugins = ['testplugin0', 'testplugin1']

            def test_foo(foo):
                assert foo == 14
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == 0

    def test_override_parametrized_fixture_conftest_module(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test override of the parametrized fixture with non-parametrized one on the test module level."""
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(params=[1, 2, 3])
            def spam(request):
                return request.param
        """
        )
        testfile = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture
            def spam():
                return 'spam'

            def test_spam(spam):
                assert spam == 'spam'
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 passed*"])
        result = testrunnerer.runtestrunner(testfile)
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_override_parametrized_fixture_conftest_conftest(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test override of the parametrized fixture with non-parametrized one on the conftest level."""
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(params=[1, 2, 3])
            def spam(request):
                return request.param
        """
        )
        subdir = testrunnerer.mkpydir("subdir")
        subdir.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner

                @testrunner.fixture
                def spam():
                    return 'spam'
                """
            ),
            encoding="utf-8",
        )
        testfile = subdir.joinpath("test_spam.py")
        testfile.write_text(
            textwrap.dedent(
                """\
                def test_spam(spam):
                    assert spam == "spam"
                """
            ),
            encoding="utf-8",
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 passed*"])
        result = testrunnerer.runtestrunner(testfile)
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_override_non_parametrized_fixture_conftest_module(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test override of the non-parametrized fixture with parametrized one on the test module level."""
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture
            def spam():
                return 'spam'
        """
        )
        testfile = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=[1, 2, 3])
            def spam(request):
                return request.param

            params = {'spam': 1}

            def test_spam(spam):
                assert spam == params['spam']
                params['spam'] += 1
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*3 passed*"])
        result = testrunnerer.runtestrunner(testfile)
        result.stdout.fnmatch_lines(["*3 passed*"])

    def test_override_non_parametrized_fixture_conftest_conftest(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test override of the non-parametrized fixture with parametrized one on the conftest level."""
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture
            def spam():
                return 'spam'
        """
        )
        subdir = testrunnerer.mkpydir("subdir")
        subdir.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner

                @testrunner.fixture(params=[1, 2, 3])
                def spam(request):
                    return request.param
                """
            ),
            encoding="utf-8",
        )
        testfile = subdir.joinpath("test_spam.py")
        testfile.write_text(
            textwrap.dedent(
                """\
                params = {'spam': 1}

                def test_spam(spam):
                    assert spam == params['spam']
                    params['spam'] += 1
                """
            ),
            encoding="utf-8",
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*3 passed*"])
        result = testrunnerer.runtestrunner(testfile)
        result.stdout.fnmatch_lines(["*3 passed*"])

    def test_override_autouse_fixture_with_parametrized_fixture_conftest_conftest(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test override of the autouse fixture with parametrized one on the conftest level.
        This test covers the issue explained in issue 1601
        """
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(autouse=True)
            def spam():
                return 'spam'
        """
        )
        subdir = testrunnerer.mkpydir("subdir")
        subdir.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner

                @testrunner.fixture(params=[1, 2, 3])
                def spam(request):
                    return request.param
                """
            ),
            encoding="utf-8",
        )
        testfile = subdir.joinpath("test_spam.py")
        testfile.write_text(
            textwrap.dedent(
                """\
                params = {'spam': 1}

                def test_spam(spam):
                    assert spam == params['spam']
                    params['spam'] += 1
                """
            ),
            encoding="utf-8",
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*3 passed*"])
        result = testrunnerer.runtestrunner(testfile)
        result.stdout.fnmatch_lines(["*3 passed*"])

    def test_override_fixture_reusing_super_fixture_parametrization(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Override a fixture at a lower level, reusing the higher-level fixture that
        is parametrized (#1953).
        """
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(params=[1, 2])
            def foo(request):
                return request.param
            """
        )
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture
            def foo(foo):
                return foo * 2

            def test_spam(foo):
                assert foo in (2, 4)
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*2 passed*"])

    def test_override_parametrize_fixture_and_indirect(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Override a fixture at a lower level, reusing the higher-level fixture that
        is parametrized, while also using indirect parametrization.
        """
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(params=[1, 2])
            def foo(request):
                return request.param
            """
        )
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture
            def foo(foo):
                return foo * 2

            @testrunner.fixture
            def bar(request):
                return request.param * 100

            @testrunner.mark.parametrize("bar", [42], indirect=True)
            def test_spam(bar, foo):
                assert bar == 4200
                assert foo in (2, 4)
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*2 passed*"])

    def test_override_top_level_fixture_reusing_super_fixture_parametrization(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Same as the above test, but with another level of overwriting."""
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(params=['unused', 'unused'])
            def foo(request):
                return request.param
            """
        )
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=[1, 2])
            def foo(request):
                return request.param

            class Test:

                @testrunner.fixture
                def foo(self, foo):
                    return foo * 2

                def test_spam(self, foo):
                    assert foo in (2, 4)
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*2 passed*"])

    def test_override_parametrized_fixture_with_new_parametrized_fixture(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Overriding a parametrized fixture, while also parametrizing the new fixture and
        simultaneously requesting the overwritten fixture as parameter, yields the same value
        as ``request.param``.
        """
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(params=['ignored', 'ignored'])
            def foo(request):
                return request.param
            """
        )
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=[10, 20])
            def foo(foo, request):
                assert request.param == foo
                return foo * 2

            def test_spam(foo):
                assert foo in (20, 40)
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*2 passed*"])

    @testrunner.mark.xfail(reason="not handled currently")
    def test_override_parametrized_fixture_via_transitive_fixture(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that overriding a parametrized fixture works even the super
        fixture is requested only transitively.

        Regression test for #7737.
        """
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=[1, 2])
            def foo(request):
                return request.param

            @testrunner.fixture
            def bar(foo):
                return foo

            class TestIt:
                @testrunner.fixture
                def foo(self, bar):
                    return bar * 2

                def test_it(self, foo):
                    pass
            """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.OK
        result.assert_outcomes(passed=2)

    def test_autouse_fixture_plugin(self, testrunnerer: Testrunnerer) -> None:
        # A fixture from a plugin has no baseid set, which screwed up
        # the autouse fixture handling.
        testrunnerer.makepyfile(
            testplugin="""
            import testrunner

            @testrunner.fixture(autouse=True)
            def foo(request):
                request.function.foo = 7
        """
        )
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(
            """
            testrunner_plugins = 'testplugin'

            def test_foo(request):
                assert request.function.foo == 7
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == 0

    def test_funcarg_lookup_error(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture
            def a_fixture(): pass

            @testrunner.fixture
            def b_fixture(): pass

            @testrunner.fixture
            def c_fixture(): pass

            @testrunner.fixture
            def d_fixture(): pass
        """
        )
        testrunnerer.makepyfile(
            """
            def test_lookup_error(unknown):
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "*ERROR at setup of test_lookup_error*",
                "  def test_lookup_error(unknown):*",
                "E       fixture 'unknown' not found",
                ">       available fixtures:*a_fixture,*b_fixture,*c_fixture,*d_fixture*monkeypatch,*",
                # sorted
                ">       use 'testrunner --fixtures *' for help on them.",
                "*1 error*",
            ]
        )
        result.stdout.no_fnmatch_line("*INTERNAL*")

    def test_fixture_excinfo_leak(self, testrunnerer: Testrunnerer) -> None:
        # on python2 sys.excinfo would leak into fixture executions
        testrunnerer.makepyfile(
            """
            import sys
            import traceback
            import testrunner

            @testrunner.fixture
            def leak():
                if sys.exc_info()[0]:  # python3 bug :)
                    traceback.print_exc()
                #fails
                assert sys.exc_info() == (None, None, None)

            def test_leak(leak):
                if sys.exc_info()[0]:  # python3 bug :)
                    traceback.print_exc()
                assert sys.exc_info() == (None, None, None)
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == 0


class TestRequestBasic:
    def test_request_attributes(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner

            @testrunner.fixture
            def something(request): pass
            def test_func(something): pass
        """
        )
        assert isinstance(item, Function)
        req = TopRequest(item, _istestrunner=True)
        assert req.function == item.obj
        assert req.keywords == item.keywords
        assert hasattr(req.module, "test_func")
        assert req.cls is None
        assert req.function.__name__ == "test_func"
        assert req.config == item.config
        assert repr(req).find(req.function.__name__) != -1

    def test_request_attributes_method(self, testrunnerer: Testrunnerer) -> None:
        (item,) = testrunnerer.getitems(
            """
            import testrunner
            class TestB(object):

                @testrunner.fixture
                def something(self, request):
                    return 1
                def test_func(self, something):
                    pass
        """
        )
        assert isinstance(item, Function)
        req = item._request
        assert req.cls.__name__ == "TestB"
        assert req.instance.__class__ == req.cls

    def test_request_contains_funcarg_arg2fixturedefs(
        self, testrunnerer: Testrunnerer
    ) -> None:
        modcol = testrunnerer.getmodulecol(
            """
            import testrunner
            @testrunner.fixture
            def something(request):
                pass
            class TestClass(object):
                def test_method(self, something):
                    pass
        """
        )
        (item1,) = testrunnerer.genitems([modcol])
        assert isinstance(item1, Function)
        assert item1.name == "test_method"
        arg2fixturedefs = TopRequest(item1, _istestrunner=True)._arg2fixturedefs
        assert len(arg2fixturedefs) == 1
        assert arg2fixturedefs["something"][0].argname == "something"

    @testrunner.mark.skipif(
        hasattr(sys, "pypy_version_info"),
        reason="this method of test doesn't work on pypy",
    )
    def test_request_garbage(self, testrunnerer: Testrunnerer) -> None:
        try:
            import xdist  # noqa: F401
        except ImportError:
            pass
        else:
            testrunner.xfail("this test is flaky when executed with xdist")
        testrunnerer.makepyfile(
            """
            import sys
            import testrunner
            from _testrunner.fixtures import RequestFixtureDef
            import gc

            @testrunner.fixture(autouse=True)
            def something(request):
                original = gc.get_debug()
                gc.set_debug(gc.DEBUG_SAVEALL)
                gc.collect()

                yield

                try:
                    gc.collect()
                    leaked = [x for _ in gc.garbage if isinstance(_, RequestFixtureDef)]
                    assert leaked == []
                finally:
                    gc.set_debug(original)

            def test_func():
                pass
        """
        )
        result = testrunnerer.runtestrunner_subprocess()
        result.stdout.fnmatch_lines(["* 1 passed in *"])

    def test_getfixturevalue_recursive(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture
            def something(request):
                return 1
        """
        )
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture
            def something(request):
                return request.getfixturevalue("something") + 1
            def test_func(something):
                assert something == 2
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_getfixturevalue_teardown(self, testrunnerer: Testrunnerer) -> None:
        """
        Issue #1895

        `test_inner` requests `inner` fixture, which in turn requests `resource`
        using `getfixturevalue`. `test_func` then requests `resource`.

        `resource` is teardown before `inner` because the fixture mechanism won't consider
        `inner` dependent on `resource` when it is used via `getfixturevalue`: `test_func`
        will then cause the `resource`'s finalizer to be called first because of this.
        """
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope='session')
            def resource():
                r = ['value']
                yield r
                r.pop()

            @testrunner.fixture(scope='session')
            def inner(request):
                resource = request.getfixturevalue('resource')
                assert resource == ['value']
                yield
                assert resource == ['value']

            def test_inner(inner):
                pass

            def test_func(resource):
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["* 2 passed in *"])

    def test_getfixturevalue_teardown_previously_requested_does_not_warn(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that requesting a fixture during teardown that was previously
        requested is OK (#12882).

        Note: this is still kinda dubious so don't let this test lock you in to
        allowing this behavior forever...
        """
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture
            def fix(request, tmp_path):
                yield
                assert request.getfixturevalue("tmp_path") == tmp_path

            def test_it(fix):
                pass
        """
        )
        result = testrunnerer.runtestrunner("-Werror")
        result.assert_outcomes(passed=1)

    def test_getfixturevalue_teardown_new_fixture_deprecated(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that requesting a fixture during teardown that was not
        previously requested raises a deprecation warning (#12882).

        Note: this is a case that previously worked but will become a hard
        error after the deprecation is completed.
        """
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope="session")
            def resource():
                return "value"

            @testrunner.fixture
            def fix(request):
                yield
                with testrunner.warns(
                    testrunner.TestrunnerRemovedIn10Warning,
                    match=r'Calling request\\.getfixturevalue\\("resource"\\) during teardown is deprecated',
                ):
                    assert request.getfixturevalue("resource") == "value"

            def test_it(fix):
                pass
            """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=1)

    def test_getfixturevalue_teardown_new_inactive_fixture_errors(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that requesting a fixture during teardown that was not
        previously requested raises an error (#12882)."""
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture
            def fix(request):
                yield
                request.getfixturevalue("tmp_path")

            def test_it(fix):
                pass
            """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=1, errors=1)
        result.stdout.fnmatch_lines(
            [
                (
                    '*The fixture value for "tmp_path" is not available during '
                    "teardown because it was not previously requested.*"
                ),
            ]
        )

    def test_getfixturevalue_teardown_new_inactive_fixture_errors_top_request(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that requesting a fixture during teardown that was not
        previously requested raises an error (tricky case) (#12882)."""
        testrunnerer.makepyfile(
            """
            def test_it(request):
                request.addfinalizer(lambda: request.getfixturevalue("tmp_path"))
            """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=1, errors=1)
        result.stdout.fnmatch_lines(
            [
                (
                    '*The fixture value for "tmp_path" is not available during '
                    "teardown because it was not previously requested.*"
                ),
            ]
        )

    def test_getfixturevalue(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner

            @testrunner.fixture
            def something(request):
                return 1

            values = [2]
            @testrunner.fixture
            def other(request):
                return values.pop()

            def test_func(something): pass
        """
        )
        assert isinstance(item, Function)
        req = item._request

        # Execute item's setup.
        item.session._setupstate.setup(item)

        with testrunner.raises(testrunner.FixtureLookupError):
            req.getfixturevalue("notexists")
        val = req.getfixturevalue("something")
        assert val == 1
        val = req.getfixturevalue("something")
        assert val == 1
        val2 = req.getfixturevalue("other")
        assert val2 == 2
        val2 = req.getfixturevalue("other")  # see about caching
        assert val2 == 2
        assert item.funcargs["something"] == 1
        assert len(get_public_names(item.funcargs)) == 2
        assert "request" in item.funcargs

    def test_request_addfinalizer(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            teardownlist = []
            @testrunner.fixture
            def something(request):
                request.addfinalizer(lambda: teardownlist.append(1))
            def test_func(something): pass
        """
        )
        assert isinstance(item, Function)
        item.session._setupstate.setup(item)
        item._request._fillfixtures()
        # successively check finalization calls
        parent = item.getparent(testrunner.Module)
        assert parent is not None
        teardownlist = parent.obj.teardownlist
        ss = item.session._setupstate
        assert not teardownlist
        ss.teardown_exact(None)
        print(ss.stack)
        assert teardownlist == [1]

    def test_request_addfinalizer_failing_setup(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = [1]
            @testrunner.fixture
            def myfix(request):
                request.addfinalizer(values.pop)
                assert 0
            def test_fix(myfix):
                pass
            def test_finalizer_ran():
                assert not values
        """
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(failed=1, passed=1)

    def test_request_addfinalizer_failing_setup_module(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = [1, 2]
            @testrunner.fixture(scope="module")
            def myfix(request):
                request.addfinalizer(values.pop)
                request.addfinalizer(values.pop)
                assert 0
            def test_fix(myfix):
                pass
        """
        )
        reprec = testrunnerer.inline_run("-s")
        mod = reprec.getcalls("testrunner_runtest_setup")[0].item.module
        assert not mod.values

    def test_request_addfinalizer_partial_setup_failure(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture
            def something(request):
                request.addfinalizer(lambda: values.append(None))
            def test_func(something, missingarg):
                pass
            def test_second():
                assert len(values) == 1
        """
        )
        result = testrunnerer.runtestrunner(p)
        result.stdout.fnmatch_lines(
            ["*1 error*"]  # XXX the whole module collection fails
        )

    def test_request_subrequest_addfinalizer_exceptions(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """
        Ensure exceptions raised during teardown by finalizers are suppressed
        until all finalizers are called, then re-raised together in an
        exception group (#2440)
        """
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            def _excepts(where):
                raise Exception('Error in %s fixture' % where)
            @testrunner.fixture
            def subrequest(request):
                return request
            @testrunner.fixture
            def something(subrequest):
                subrequest.addfinalizer(lambda: values.append(1))
                subrequest.addfinalizer(lambda: values.append(2))
                subrequest.addfinalizer(lambda: _excepts('something'))
            @testrunner.fixture
            def excepts(subrequest):
                subrequest.addfinalizer(lambda: _excepts('excepts'))
                subrequest.addfinalizer(lambda: values.append(3))
            def test_first(something, excepts):
                pass
            def test_second():
                assert values == [3, 2, 1]
        """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=2, errors=1)
        result.stdout.fnmatch_lines(
            [
                '  | *ExceptionGroup: errors while tearing down fixture "subrequest" of <Function test_first> (2 sub-exceptions)',  # noqa: E501
                "  +-+---------------- 1 ----------------",
                "    | Exception: Error in something fixture",
                "    +---------------- 2 ----------------",
                "    | Exception: Error in excepts fixture",
                "    +------------------------------------",
            ],
        )

    def test_request_getmodulepath(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol("def test_somefunc(): pass")
        (item,) = testrunnerer.genitems([modcol])
        assert isinstance(item, Function)
        req = TopRequest(item, _istestrunner=True)
        assert req.path == modcol.path

    def test_request_fixturenames(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            from _testrunner.testrunnerer import get_public_names
            @testrunner.fixture()
            def arg1():
                pass
            @testrunner.fixture()
            def farg(arg1):
                pass
            @testrunner.fixture(autouse=True)
            def sarg(tmp_path):
                pass
            def test_function(request, farg):
                assert set(get_public_names(request.fixturenames)) == \
                       set(["sarg", "arg1", "request", "farg",
                            "tmp_path", "tmp_path_factory"])
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_request_fixturenames_dynamic_fixture(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Regression test for #3057"""
        testrunnerer.copy_example("fixtures/test_getfixturevalue_dynamic.py")
        result = testrunnerer.runtestrunner("-vv")
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_setupdecorator_and_xunit(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            values = []

            @testrunner.fixture(scope='module', autouse=True)
            def setup_module():
                values.append("module")

            @testrunner.fixture(autouse=True)
            def setup_function():
                values.append("function")

            def test_func():
                pass

            class TestClass:
                @testrunner.fixture(scope="class", autouse=True)
                @classmethod
                def setup_class(cls):
                    values.append("class")

                @testrunner.fixture(autouse=True)
                def setup_method(self):
                    values.append("method")

                def test_method(self):
                    pass

            def test_all():
                assert values == [
                    "module",
                    "function",
                    "class",
                    "function",
                    "method",
                    "function",
                ]
        """
        )
        reprec = testrunnerer.inline_run("-v")
        reprec.assertoutcome(passed=3)

    def test_fixtures_sub_subdir_normalize_sep(
        self, testrunnerer: Testrunnerer
    ) -> None:
        # this tests that normalization of nodeids takes place
        b = testrunnerer.path.joinpath("tests", "unit")
        b.mkdir(parents=True)
        b.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner
                @testrunner.fixture
                def arg1():
                    pass
                """
            ),
            encoding="utf-8",
        )
        p = b.joinpath("test_module.py")
        p.write_text("def test_func(arg1): pass", encoding="utf-8")
        result = testrunnerer.runtestrunner(p, "--fixtures")
        assert result.ret == 0
        result.stdout.fnmatch_lines(
            """
            *fixtures defined*conftest*
            *arg1*
        """
        )

    def test_show_fixtures_color_yes(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile("def test_this(): assert 1")
        result = testrunnerer.runtestrunner("--color=yes", "--fixtures")
        assert "\x1b[32mtmp_path" in result.stdout.str()

    def test_newstyle_with_request(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture()
            def arg(request):
                pass
            def test_1(arg):
                pass
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_setupcontext_no_param(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(params=[1,2])
            def arg(request):
                return request.param

            @testrunner.fixture(autouse=True)
            def mysetup(request, arg):
                assert not hasattr(request, "param")
            def test_1(arg):
                assert arg in (1,2)
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)


class TestRequestSessionScoped:
    @testrunner.fixture(scope="session")
    @staticmethod
    def session_request(request):
        return request

    @testrunner.mark.parametrize("name", ["path", "module"])
    def test_session_scoped_unavailable_attributes(self, session_request, name):
        with testrunner.raises(
            AttributeError,
            match=f"{name} not available in session-scoped context",
        ):
            getattr(session_request, name)


class TestRequestMarking:
    def test_applymarker(self, testrunnerer: Testrunnerer) -> None:
        item1, _item2 = testrunnerer.getitems(
            """
            import testrunner

            @testrunner.fixture
            def something(request):
                pass
            class TestClass(object):
                def test_func1(self, something):
                    pass
                def test_func2(self, something):
                    pass
        """
        )
        assert isinstance(item1, Function)
        req1 = TopRequest(item1, _istestrunner=True)
        assert "xfail" not in item1.keywords
        req1.applymarker(testrunner.mark.xfail)
        assert "xfail" in item1.keywords
        assert "skipif" not in item1.keywords
        req1.applymarker(testrunner.mark.skipif)
        assert "skipif" in item1.keywords
        with testrunner.raises(ValueError):
            req1.applymarker(42)  # type: ignore[arg-type]

    def test_accesskeywords(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture()
            def keywords(request):
                return request.keywords
            @testrunner.mark.XYZ
            def test_function(keywords):
                assert keywords["XYZ"]
                assert "abc" not in keywords
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_accessmarker_dynamic(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            @testrunner.fixture()
            def keywords(request):
                return request.keywords

            @testrunner.fixture(scope="class", autouse=True)
            def marking(request):
                request.applymarker(testrunner.mark.XYZ("hello"))
        """
        )
        testrunnerer.makepyfile(
            """
            import testrunner
            def test_fun1(keywords):
                assert keywords["XYZ"] is not None
                assert "abc" not in keywords
            def test_fun2(keywords):
                assert keywords["XYZ"] is not None
                assert "abc" not in keywords
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)


class TestFixtureUsages:
    def test_noargfixturedec(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture
            def arg1():
                return 1

            def test_func(arg1):
                assert arg1 == 1
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_receives_funcargs(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture()
            def arg1():
                return 1

            @testrunner.fixture()
            def arg2(arg1):
                return arg1 + 1

            def test_add(arg2):
                assert arg2 == 2
            def test_all(arg1, arg2):
                assert arg1 == 1
                assert arg2 == 2
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_receives_funcargs_scope_mismatch(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="function")
            def arg1():
                return 1

            @testrunner.fixture(scope="module")
            def arg2(arg1):
                return arg1 + 1

            def test_add(arg2):
                assert arg2 == 2
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "*ScopeMismatch*Requesting fixture stack*",
                "test_receives_funcargs_scope_mismatch.py:6:  def arg2(arg1)",
                "Requested fixture:",
                "test_receives_funcargs_scope_mismatch.py:2:  def arg1()",
                "*1 error*",
            ]
        )

    def test_receives_funcargs_scope_mismatch_issue660(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="function")
            def arg1():
                return 1

            @testrunner.fixture(scope="module")
            def arg2(arg1):
                return arg1 + 1

            def test_add(arg1, arg2):
                assert arg2 == 2
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "*ScopeMismatch*Requesting fixture stack*",
                "* def arg2(arg1)",
                "Requested fixture:",
                "* def arg1()",
                "*1 error*",
            ],
        )

    def test_invalid_scope(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="functions")
            def badscope():
                pass

            def test_nothing(badscope):
                pass
        """
        )
        result = testrunnerer.runtestrunner_inprocess()
        result.stdout.fnmatch_lines(
            "*Fixture 'badscope' from test_invalid_scope.py got an unexpected scope value 'functions'"
        )

    @testrunner.mark.parametrize("scope", ["function", "session"])
    def test_parameters_without_eq_semantics(
        self, scope, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            f"""
            class NoEq1:  # fails on `a == b` statement
                def __eq__(self, _):
                    raise RuntimeError

            class NoEq2:  # fails on `if a == b:` statement
                def __eq__(self, _):
                    class NoBool:
                        def __bool__(self):
                            raise RuntimeError
                    return NoBool()

            import testrunner
            @testrunner.fixture(params=[NoEq1(), NoEq2()], scope={scope!r})
            def no_eq(request):
                return request.param

            def test1(no_eq):
                pass

            def test2(no_eq):
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*4 passed*"])

    def test_funcarg_parametrized_and_used_twice(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(params=[1,2])
            def arg1(request):
                values.append(1)
                return request.param

            @testrunner.fixture()
            def arg2(arg1):
                return arg1 + 1

            def test_add(arg1, arg2):
                assert arg2 == arg1 + 1
                assert len(values) == arg1
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*2 passed*"])

    def test_factory_uses_unknown_funcarg_as_dependency_error(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture()
            def fail(missing):
                return

            @testrunner.fixture()
            def call_fail(fail):
                return

            def test_missing(call_fail):
                pass
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            """
            *testrunner.fixture()*
            *def call_fail(fail)*
            *testrunner.fixture()*
            *def fail*
            *fixture*'missing'*not found*
        """
        )

    def test_factory_setup_as_classes_fails(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            class arg1(object):
                def __init__(self, request):
                    self.x = 1
            arg1 = testrunner.fixture()(arg1)

        """
        )
        reprec = testrunnerer.inline_run()
        values = reprec.getfailedcollections()
        assert len(values) == 1

    def test_usefixtures_marker(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            values = []

            @testrunner.fixture(scope="class")
            def myfix(request):
                request.cls.hello = "world"
                values.append(1)

            class TestClass(object):
                def test_one(self):
                    assert self.hello == "world"
                    assert len(values) == 1
                def test_two(self):
                    assert self.hello == "world"
                    assert len(values) == 1
            testrunner.mark.usefixtures("myfix")(TestClass)
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_empty_usefixtures_marker(self, testrunnerer: Testrunnerer) -> None:
        """Empty usefixtures() marker issues a warning (#12439)."""
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.usefixtures()
            def test_one():
                assert 1 == 1
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            "*TestrunnerWarning: usefixtures() in test_empty_usefixtures_marker.py::test_one"
            " without arguments has no effect"
        )

    def test_usefixtures_ini(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeini(
            """
            [testrunner]
            usefixtures = myfix
        """
        )
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(scope="class")
            def myfix(request):
                request.cls.hello = "world"

        """
        )
        testrunnerer.makepyfile(
            """
            class TestClass(object):
                def test_one(self):
                    assert self.hello == "world"
                def test_two(self):
                    assert self.hello == "world"
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_usefixtures_seen_in_showmarkers(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("--markers")
        result.stdout.fnmatch_lines(
            """
            *usefixtures(fixturename1*mark tests*fixtures*
        """
        )

    def test_request_instance_issue203(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            class TestClass(object):
                @testrunner.fixture
                def setup1(self, request):
                    assert self == request.instance
                    self.arg1 = 1
                def test_hello(self, setup1):
                    assert self.arg1 == 1
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_fixture_parametrized_with_iterator(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            values = []
            def f():
                yield 1
                yield 2
            dec = testrunner.fixture(scope="module", params=f())

            @dec
            def arg(request):
                return request.param
            @dec
            def arg2(request):
                return request.param

            def test_1(arg):
                values.append(arg)
            def test_2(arg2):
                values.append(arg2*10)
        """
        )
        reprec = testrunnerer.inline_run("-v")
        reprec.assertoutcome(passed=4)
        values = reprec.getcalls("testrunner_runtest_call")[0].item.module.values
        assert values == [1, 2, 10, 20]

    def test_setup_functions_as_fixtures(self, testrunnerer: Testrunnerer) -> None:
        """Ensure setup_* methods obey fixture scope rules (#517, #3094)."""
        testrunnerer.makepyfile(
            """
            import testrunner

            DB_INITIALIZED = None

            @testrunner.fixture(scope="session", autouse=True)
            def db():
                global DB_INITIALIZED
                DB_INITIALIZED = True
                yield
                DB_INITIALIZED = False

            def setup_module():
                assert DB_INITIALIZED

            def teardown_module():
                assert DB_INITIALIZED

            class TestClass(object):

                def setup_method(self, method):
                    assert DB_INITIALIZED

                def teardown_method(self, method):
                    assert DB_INITIALIZED

                def test_printer_1(self):
                    pass

                def test_printer_2(self):
                    pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["* 2 passed in *"])

    def test_parameterized_fixture_caching(self, testrunnerer: Testrunnerer) -> None:
        """Regression test for #12600."""
        testrunnerer.makepyfile(
            """
            import testrunner
            from itertools import count

            CACHE_MISSES = count(0)

            def testrunner_generate_tests(metafunc):
                if "my_fixture" in metafunc.fixturenames:
                    # Use unique objects for parametrization (as opposed to small strings
                    # and small integers which are singletons).
                    metafunc.parametrize("my_fixture", [[1], [2]], indirect=True)

            @testrunner.fixture(scope='session')
            def my_fixture(request):
                next(CACHE_MISSES)

            def test1(my_fixture):
                pass

            def test2(my_fixture):
                pass

            def teardown_module():
                assert next(CACHE_MISSES) == 2
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.no_fnmatch_line("* ERROR at teardown *")

    def test_unwrapping_testrunner_fixture(self, testrunnerer: Testrunnerer) -> None:
        """Ensure the unwrap method on `FixtureFunctionDefinition` correctly wraps and unwraps methods and functions"""
        testrunnerer.makepyfile(
            """
            import testrunner
            import inspect

            class FixtureFunctionDefTestClass:
                def __init__(self) -> None:
                    self.i = 10

                @testrunner.fixture
                def fixture_function_def_test_method(self):
                    return self.i


            @testrunner.fixture
            def fixture_function_def_test_func():
                return 9


            def test_get_wrapped_func_returns_method():
                obj = FixtureFunctionDefTestClass()
                wrapped_function_result = (
                    obj.fixture_function_def_test_method._get_wrapped_function()
                )
                assert inspect.ismethod(wrapped_function_result)
                assert wrapped_function_result() == 10


            def test_get_wrapped_func_returns_function():
                assert fixture_function_def_test_func._get_wrapped_function()() == 9
            """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=2)

    def test_fixture_wrapped_looks_liked_wrapped_function(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Ensure that `FixtureFunctionDefinition` behaves like the function it wrapped."""
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture
            def fixture_function_def_test_func():
                return 9
            fixture_function_def_test_func.__doc__ = "documentation"

            def test_fixture_has_same_doc():
                assert fixture_function_def_test_func.__doc__ == "documentation"
            """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=1)

    def test_fixture_function_definition_public_api(self) -> None:
        """FixtureFunctionDefinition is accessible as testrunner.FixtureFunctionDefinition."""
        assert "FixtureFunctionDefinition" in testrunner.__all__

        @testrunner.fixture
        def fixture_func() -> None:
            pass

        assert isinstance(fixture_func, testrunner.FixtureFunctionDefinition)


class TestFixtureManagerParseFactories:
    @testrunner.fixture
    def testrunnerer(self, testrunnerer: Testrunnerer) -> Testrunnerer:
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture
            def hello(request):
                return "conftest"

            @testrunner.fixture
            def fm(request):
                return request._fixturemanager

            @testrunner.fixture
            def item(request):
                return request._pyfuncitem
        """
        )
        return testrunnerer

    def test_parsefactories_evil_objects_issue214(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            class A(object):
                def __call__(self):
                    pass
                def __getattr__(self, name):
                    raise RuntimeError()
            a = A()
            def test_hello():
                pass
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1, failed=0)

    def test_parsefactories_conftest(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            def test_hello(item, fm):
                for name in ("fm", "hello", "item"):
                    faclist = fm.getfixturedefs(name, item)
                    assert len(faclist) == 1
                    fac = faclist[0]
                    assert fac.func.__name__ == name
        """
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(passed=1)

    def test_parsefactories_conftest_and_module_and_class(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """\
            import testrunner

            @testrunner.fixture
            def hello(request):
                return "module"
            class TestClass(object):
                @testrunner.fixture
                def hello(self, request):
                    return "class"
                def test_hello(self, item, fm):
                    faclist = fm.getfixturedefs("hello", item)
                    print(faclist)
                    assert len(faclist) == 3

                    assert faclist[0].func(item._request) == "conftest"
                    assert faclist[1].func(item._request) == "module"
                    assert faclist[2].func(item._request) == "class"
            """
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(passed=1)

    def test_register_fixture_ordered_by_visibility(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """A fixturedef registered for a more specific node takes precedence
        over one registered for a more general (ancestor) node, regardless of
        the order in which they were registered (#14513)."""
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.hookimpl(wrapper=True)
            def testrunner_collection(session):
                result = yield
                item = session.items[0]
                testrunner.register_fixture(name="fix", func=lambda: "session1", node=session)
                # For coverage; can be removed once nodeid= deprecation is over.
                fm = session._fixturemanager
                fm._register_fixture(name="fix", func=lambda: "session-legacy", nodeid="")
                fm._register_fixture(name="fix", func=lambda: "broken-legacy", nodeid="broken")
                testrunner.register_fixture(name="fix", func=lambda fix: f"item1-{fix}", node=item)
                testrunner.register_fixture(name="fix", func=lambda fix: f"item2-{fix}", node=item)
                testrunner.register_fixture(name="fix", func=lambda: "session2", node=session)
                return result
            """
        )
        testrunnerer.makepyfile(
            """
            def test(fix):
                assert fix == "item2-item1-session2"
            """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_parsefactories_relative_node_ids(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        # example mostly taken from:
        # https://mail.python.org/pipermail/testrunner-dev/2014-September/002617.html
        runner = testrunnerer.mkdir("runner")
        package = testrunnerer.mkdir("package")
        package.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
            import testrunner
            @testrunner.fixture
            def one():
                return 1
            """
            ),
            encoding="utf-8",
        )
        package.joinpath("test_x.py").write_text(
            textwrap.dedent(
                """\
                def test_x(one):
                    assert one == 1
                """
            ),
            encoding="utf-8",
        )
        sub = package.joinpath("sub")
        sub.mkdir()
        sub.joinpath("__init__.py").touch()
        sub.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner
                @testrunner.fixture
                def one():
                    return 2
                """
            ),
            encoding="utf-8",
        )
        sub.joinpath("test_y.py").write_text(
            textwrap.dedent(
                """\
                def test_x(one):
                    assert one == 2
                """
            ),
            encoding="utf-8",
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)
        with monkeypatch.context() as mp:
            mp.chdir(runner)
            reprec = testrunnerer.inline_run("..")
            reprec.assertoutcome(passed=2)

    def test_package_xunit_fixture(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            __init__="""\
            values = []
        """
        )
        package = testrunnerer.mkdir("package")
        package.joinpath("__init__.py").write_text(
            textwrap.dedent(
                """\
                from .. import values
                def setup_module():
                    values.append("package")
                def teardown_module():
                    values[:] = []
                """
            ),
            encoding="utf-8",
        )
        package.joinpath("test_x.py").write_text(
            textwrap.dedent(
                """\
                from .. import values
                def test_x():
                    assert values == ["package"]
                """
            ),
            encoding="utf-8",
        )
        package = testrunnerer.mkdir("package2")
        package.joinpath("__init__.py").write_text(
            textwrap.dedent(
                """\
                from .. import values
                def setup_module():
                    values.append("package2")
                def teardown_module():
                    values[:] = []
                """
            ),
            encoding="utf-8",
        )
        package.joinpath("test_x.py").write_text(
            textwrap.dedent(
                """\
                from .. import values
                def test_x():
                    assert values == ["package2"]
                """
            ),
            encoding="utf-8",
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_package_fixture_complex(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            __init__="""\
            values = []
        """
        )
        testrunnerer.syspathinsert(testrunnerer.path.name)
        package = testrunnerer.mkdir("package")
        package.joinpath("__init__.py").write_text("", encoding="utf-8")
        package.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner
                from .. import values
                @testrunner.fixture(scope="package")
                def one():
                    values.append("package")
                    yield values
                    values.pop()
                @testrunner.fixture(scope="package", autouse=True)
                def two():
                    values.append("package-auto")
                    yield values
                    values.pop()
                """
            ),
            encoding="utf-8",
        )
        package.joinpath("test_x.py").write_text(
            textwrap.dedent(
                """\
                from .. import values
                def test_package_autouse():
                    assert values == ["package-auto"]
                def test_package(one):
                    assert values == ["package-auto", "package"]
                """
            ),
            encoding="utf-8",
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_collect_custom_items(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.copy_example("fixtures/custom_item")
        result = testrunnerer.runtestrunner("foo")
        result.stdout.fnmatch_lines(["*passed*"])


class TestAutouseDiscovery:
    @testrunner.fixture
    def testrunnerer(self, testrunnerer: Testrunnerer) -> Testrunnerer:
        testrunnerer.makeconftest(
            """
            import testrunner
            @testrunner.fixture(autouse=True)
            def perfunction(request, tmp_path):
                pass

            @testrunner.fixture()
            def arg1(tmp_path):
                pass
            @testrunner.fixture(autouse=True)
            def perfunction2(arg1):
                pass

            @testrunner.fixture
            def fm(request):
                return request._fixturemanager

            @testrunner.fixture
            def item(request):
                return request._pyfuncitem
        """
        )
        return testrunnerer

    def test_parsefactories_conftest(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            from _testrunner.testrunnerer import get_public_names
            def test_check_setup(item, fm):
                autousenames = list(fm._getautousenames(item))
                assert len(get_public_names(autousenames)) == 2
                assert "perfunction2" in autousenames
                assert "perfunction" in autousenames
        """
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(passed=1)

    def test_two_classes_separated_autouse(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            class TestA(object):
                values = []
                @testrunner.fixture(autouse=True)
                def setup1(self):
                    self.values.append(1)
                def test_setup1(self):
                    assert self.values == [1]
            class TestB(object):
                values = []
                @testrunner.fixture(autouse=True)
                def setup2(self):
                    self.values.append(1)
                def test_setup2(self):
                    assert self.values == [1]
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_setup_at_classlevel(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            class TestClass(object):
                @testrunner.fixture(autouse=True)
                def permethod(self, request):
                    request.instance.funcname = request.function.__name__
                def test_method1(self):
                    assert self.funcname == "test_method1"
                def test_method2(self):
                    assert self.funcname == "test_method2"
        """
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(passed=2)

    @testrunner.mark.xfail(reason="'enabled' feature not implemented")
    def test_setup_enabled_functionnode(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            def enabled(parentnode, markers):
                return "needsdb" in markers

            @testrunner.fixture(params=[1,2])
            def db(request):
                return request.param

            @testrunner.fixture(enabled=enabled, autouse=True)
            def createdb(db):
                pass

            def test_func1(request):
                assert "db" not in request.fixturenames

            @testrunner.mark.needsdb
            def test_func2(request):
                assert "db" in request.fixturenames
        """
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(passed=2)

    def test_callables_nocode(self, testrunnerer: Testrunnerer) -> None:
        """An imported mock.call would break setup/factory discovery due to
        it being callable and __code__ not being a code object."""
        testrunnerer.makepyfile(
            """
           class _call(tuple):
               def __call__(self, *k, **kw):
                   pass
               def __getattr__(self, k):
                   return self

           call = _call()
        """
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(failed=0, passed=0)

    def test_autouse_in_conftests(self, testrunnerer: Testrunnerer) -> None:
        a = testrunnerer.mkdir("a")
        b = testrunnerer.mkdir("a1")
        conftest = testrunnerer.makeconftest(
            """
            import testrunner
            @testrunner.fixture(autouse=True)
            def hello():
                xxx
        """
        )
        conftest.rename(a.joinpath(conftest.name))
        a.joinpath("test_something.py").write_text(
            "def test_func(): pass", encoding="utf-8"
        )
        b.joinpath("test_otherthing.py").write_text(
            "def test_func(): pass", encoding="utf-8"
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            """
            *1 passed*1 error*
        """
        )

    def test_autouse_in_module_and_two_classes(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(autouse=True)
            def append1():
                values.append("module")
            def test_x():
                assert values == ["module"]

            class TestA(object):
                @testrunner.fixture(autouse=True)
                def append2(self):
                    values.append("A")
                def test_hello(self):
                    assert values == ["module", "module", "A"], values
            class TestA2(object):
                def test_world(self):
                    assert values == ["module", "module", "A", "module"], values
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=3)


class TestAutouseManagement:
    def test_autouse_conftest_mid_directory(self, testrunnerer: Testrunnerer) -> None:
        pkgdir = testrunnerer.mkpydir("xyz123")
        pkgdir.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner
                @testrunner.fixture(autouse=True)
                def app():
                    import sys
                    sys._myapp = "hello"
                """
            ),
            encoding="utf-8",
        )
        sub = pkgdir.joinpath("tests")
        sub.mkdir()
        t = sub.joinpath("test_app.py")
        t.touch()
        t.write_text(
            textwrap.dedent(
                """\
                import sys
                def test_app():
                    assert sys._myapp == "hello"
                """
            ),
            encoding="utf-8",
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(passed=1)

    def test_funcarg_and_setup(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(scope="module")
            def arg():
                values.append(1)
                return 0
            @testrunner.fixture(scope="module", autouse=True)
            def something(arg):
                values.append(2)

            def test_hello(arg):
                assert len(values) == 2
                assert values == [1,2]
                assert arg == 0

            def test_hello2(arg):
                assert len(values) == 2
                assert values == [1,2]
                assert arg == 0
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_uses_parametrized_resource(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(params=[1,2])
            def arg(request):
                return request.param

            @testrunner.fixture(autouse=True)
            def something(arg):
                values.append(arg)

            def test_hello():
                if len(values) == 1:
                    assert values == [1]
                elif len(values) == 2:
                    assert values == [1, 2]
                else:
                    0/0

        """
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(passed=2)

    def test_session_parametrized_function(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            values = []

            @testrunner.fixture(scope="session", params=[1,2])
            def arg(request):
               return request.param

            @testrunner.fixture(scope="function", autouse=True)
            def append(request, arg):
                if request.function.__name__ == "test_some":
                    values.append(arg)

            def test_some():
                pass

            def test_result(arg):
                assert len(values) == arg
                assert values[:arg] == [1,2][:arg]
        """
        )
        reprec = testrunnerer.inline_run("-v", "-s")
        reprec.assertoutcome(passed=4)

    def test_class_function_parametrization_finalization(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p = testrunnerer.makeconftest(
            """
            import testrunner
            import pprint

            values = []

            @testrunner.fixture(scope="function", params=[1,2])
            def farg(request):
                return request.param

            @testrunner.fixture(scope="class", params=list("ab"))
            def carg(request):
                return request.param

            @testrunner.fixture(scope="function", autouse=True)
            def append(request, farg, carg):
                def fin():
                    values.append("fin_%s%s" % (carg, farg))
                request.addfinalizer(fin)
        """
        )
        testrunnerer.makepyfile(
            """
            import testrunner

            class TestClass(object):
                def test_1(self):
                    pass
            class TestClass2(object):
                def test_2(self):
                    pass
        """
        )
        reprec = testrunnerer.inline_run("-v", "-s", "--confcutdir", testrunnerer.path)
        reprec.assertoutcome(passed=8)
        config = reprec.getcalls("testrunner_unconfigure")[0].config
        values = config.pluginmanager._getconftestmodules(p)[0].values
        assert values == ["fin_a1", "fin_a2", "fin_b1", "fin_b2"] * 2

    def test_scope_ordering(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(scope="function", autouse=True)
            def fappend2():
                values.append(2)
            @testrunner.fixture(scope="class", autouse=True)
            def classappend3():
                values.append(3)
            @testrunner.fixture(scope="module", autouse=True)
            def mappend():
                values.append(1)

            class TestHallo(object):
                def test_method(self):
                    assert values == [1,3,2]
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_parametrization_setup_teardown_ordering(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            values = []

            def testrunner_generate_tests(metafunc):
                if metafunc.cls is None:
                    assert metafunc.function is test_finish
                if metafunc.cls is not None:
                    metafunc.parametrize("item", [1,2], scope="class")

            class TestClass:
                @testrunner.fixture(scope="class", autouse=True)
                @classmethod
                def setup_teardown(cls, item):
                    values.append("setup-%d" % item)
                    yield
                    values.append("teardown-%d" % item)

                def test_step1(self, item):
                    values.append("step1-%d" % item)

                def test_step2(self, item):
                    values.append("step2-%d" % item)

            def test_finish():
                assert values == [
                    "setup-1",
                    "step1-1",
                    "step2-1",
                    "teardown-1",
                    "setup-2",
                    "step1-2",
                    "step2-2",
                    "teardown-2",
                ]
            """
        )
        result = testrunnerer.inline_run("-vv")
        result.assertoutcome(passed=5)

    def test_ordering_autouse_before_explicit(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            values = []
            @testrunner.fixture(autouse=True)
            def fix1():
                values.append(1)
            @testrunner.fixture()
            def arg1():
                values.append(2)
            def test_hello(arg1):
                assert values == [1,2]
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    @testrunner.mark.parametrize("param1", ["", "params=[1]"], ids=["p00", "p01"])
    @testrunner.mark.parametrize("param2", ["", "params=[1]"], ids=["p10", "p11"])
    def test_ordering_dependencies_torndown_first(
        self, testrunnerer: Testrunnerer, param1, param2
    ) -> None:
        """#226"""
        testrunnerer.makepyfile(
            f"""
            import testrunner
            values = []
            @testrunner.fixture({param1})
            def arg1(request):
                request.addfinalizer(lambda: values.append("fin1"))
                values.append("new1")
            @testrunner.fixture({param2})
            def arg2(request, arg1):
                request.addfinalizer(lambda: values.append("fin2"))
                values.append("new2")

            def test_arg(arg2):
                pass
            def test_check():
                assert values == ["new1", "new2", "fin2", "fin1"]
        """
        )
        reprec = testrunnerer.inline_run("-s")
        reprec.assertoutcome(passed=2)

    def test_reordering_catastrophic_performance(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Check that a certain high-scope parametrization pattern doesn't cause
        a catasrophic slowdown.

        Regression test for #12355.
        """
        testrunnerer.makepyfile("""
            import testrunner

            params = tuple("abcdefghijklmnopqrstuvwxyz")
            @testrunner.mark.parametrize(params, [range(len(params))] * 3, scope="module")
            def test_parametrize(a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z):
                pass
        """)

        result = testrunnerer.runtestrunner()

        result.assert_outcomes(passed=3)


class TestFixtureMarker:
    def test_parametrize(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(params=["a", "b", "c"])
            def arg(request):
                return request.param
            values = []
            def test_param(arg):
                values.append(arg)
            def test_result():
                assert values == list("abc")
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=4)

    def test_multiple_parametrization_issue_736(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=[1,2,3])
            def foo(request):
                return request.param

            @testrunner.mark.parametrize('foobar', [4,5,6])
            def test_issue(foo, foobar):
                assert foo in [1,2,3]
                assert foobar in [4,5,6]
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=9)

    @testrunner.mark.parametrize(
        "param_args",
        ["'fixt, val'", "'fixt,val'", "['fixt', 'val']", "('fixt', 'val')"],
    )
    def test_override_parametrized_fixture_issue_979(
        self, testrunnerer: Testrunnerer, param_args
    ) -> None:
        """Make sure a parametrized argument can override a parametrized fixture.

        This was a regression introduced in the fix for #736.
        """
        testrunnerer.makepyfile(
            f"""
            import testrunner

            @testrunner.fixture(params=[1, 2])
            def fixt(request):
                return request.param

            @testrunner.mark.parametrize({param_args}, [(3, 'x'), (4, 'x')])
            def test_foo(fixt, val):
                pass
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_override_parametrized_fixture_with_indirect(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Make sure a parametrized argument can override a parametrized fixture.

        This was a regression introduced in the fix for #736.
        """
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=["a"])
            def fixt(request):
                return request.param * 2

            def test_fixt(fixt):
                assert fixt == "aa"

            @testrunner.mark.parametrize("fixt", ['b'], indirect=True)
            def test_indirect(fixt):
                assert fixt == "bb"
            """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_scope_session(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(scope="module")
            def arg():
                values.append(1)
                return 1

            def test_1(arg):
                assert arg == 1
            def test_2(arg):
                assert arg == 1
                assert len(values) == 1
            class TestClass(object):
                def test3(self, arg):
                    assert arg == 1
                    assert len(values) == 1
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=3)

    def test_scope_session_exc(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(scope="session")
            def fix():
                values.append(1)
                testrunner.skip('skipping')

            def test_1(fix):
                pass
            def test_2(fix):
                pass
            def test_last():
                assert values == [1]
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(skipped=2, passed=1)

    def test_scope_session_exc_two_fix(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            m = []
            @testrunner.fixture(scope="session")
            def a():
                values.append(1)
                testrunner.skip('skipping')
            @testrunner.fixture(scope="session")
            def b(a):
                m.append(1)

            def test_1(b):
                pass
            def test_2(b):
                pass
            def test_last():
                assert values == [1]
                assert m == []
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(skipped=2, passed=1)

    def test_scope_exc(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            test_foo="""
                def test_foo(fix):
                    pass
            """,
            test_bar="""
                def test_bar(fix):
                    pass
            """,
            conftest="""
                import testrunner
                reqs = []
                @testrunner.fixture(scope="session")
                def fix(request):
                    reqs.append(1)
                    testrunner.skip()
                @testrunner.fixture
                def req_list():
                    return reqs
            """,
            test_real="""
                def test_last(req_list):
                    assert req_list == [1]
            """,
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(skipped=2, passed=1)

    def test_scope_module_uses_session(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(scope="module")
            def arg():
                values.append(1)
                return 1

            def test_1(arg):
                assert arg == 1
            def test_2(arg):
                assert arg == 1
                assert len(values) == 1
            class TestClass(object):
                def test3(self, arg):
                    assert arg == 1
                    assert len(values) == 1
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=3)

    def test_scope_module_and_finalizer(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            finalized_list = []
            created_list = []
            @testrunner.fixture(scope="module")
            def arg(request):
                created_list.append(1)
                assert request.scope == "module"
                request.addfinalizer(lambda: finalized_list.append(1))
            @testrunner.fixture
            def created(request):
                return len(created_list)
            @testrunner.fixture
            def finalized(request):
                return len(finalized_list)
        """
        )
        testrunnerer.makepyfile(
            test_mod1="""
                def test_1(arg, created, finalized):
                    assert created == 1
                    assert finalized == 0
                def test_2(arg, created, finalized):
                    assert created == 1
                    assert finalized == 0""",
            test_mod2="""
                def test_3(arg, created, finalized):
                    assert created == 2
                    assert finalized == 1""",
            test_mode3="""
                def test_4(arg, created, finalized):
                    assert created == 3
                    assert finalized == 2
            """,
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=4)

    def test_scope_mismatch_various(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            finalized = []
            created = []
            @testrunner.fixture(scope="function")
            def arg(request):
                pass
        """
        )
        testrunnerer.makepyfile(
            test_mod1="""
                import testrunner
                @testrunner.fixture(scope="session")
                def arg(request):
                    request.getfixturevalue("arg")
                def test_1(arg):
                    pass
            """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        result.stdout.fnmatch_lines(
            ["*ScopeMismatch*You tried*function*session*request*"]
        )

    def test_scope_mismatch_already_computed_dynamic(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            test_it="""
                import testrunner

                @testrunner.fixture(scope="function")
                def fixfunc(): pass

                @testrunner.fixture(scope="module")
                def fixmod(fixfunc): pass

                def test_it(request, fixfunc):
                    request.getfixturevalue("fixmod")
            """,
        )

        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.TESTS_FAILED
        result.stdout.fnmatch_lines(
            [
                "*ScopeMismatch*Requesting fixture stack*",
                "test_it.py:6:  def fixmod(fixfunc)",
                "Requested fixture:",
                "test_it.py:3:  def fixfunc()",
            ]
        )

    def test_dynamic_scope(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner


            def testrunner_addoption(parser):
                parser.addoption("--extend-scope", action="store_true", default=False)


            def dynamic_scope(fixture_name, config):
                if config.getoption("--extend-scope"):
                    return "session"
                return "function"


            @testrunner.fixture(scope=dynamic_scope)
            def dynamic_fixture(calls=[]):
                calls.append("call")
                return len(calls)

        """
        )

        testrunnerer.makepyfile(
            """
            def test_first(dynamic_fixture):
                assert dynamic_fixture == 1


            def test_second(dynamic_fixture):
                assert dynamic_fixture == 2

        """
        )

        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

        reprec = testrunnerer.inline_run("--extend-scope")
        reprec.assertoutcome(passed=1, failed=1)

    def test_dynamic_scope_bad_return(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            def dynamic_scope(**_):
                return "wrong-scope"

            @testrunner.fixture(scope=dynamic_scope)
            def fixture():
                pass

        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            "Fixture 'fixture' from test_dynamic_scope_bad_return.py "
            "got an unexpected scope value 'wrong-scope'"
        )

    def test_register_only_with_mark(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            @testrunner.fixture()
            def arg():
                return 1
        """
        )
        testrunnerer.makepyfile(
            test_mod1="""
                import testrunner
                @testrunner.fixture()
                def arg(arg):
                    return arg + 1
                def test_1(arg):
                    assert arg == 2
            """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_parametrize_and_scope(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="module", params=["a", "b", "c"])
            def arg(request):
                return request.param
            values = []
            def test_param(arg):
                values.append(arg)
        """
        )
        reprec = testrunnerer.inline_run("-v")
        reprec.assertoutcome(passed=3)
        values = reprec.getcalls("testrunner_runtest_call")[0].item.module.values
        assert len(values) == 3
        assert "a" in values
        assert "b" in values
        assert "c" in values

    def test_scope_mismatch(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            @testrunner.fixture(scope="function")
            def arg(request):
                pass
        """
        )
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="session")
            def arg(arg):
                pass
            def test_mismatch(arg):
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*ScopeMismatch*", "*1 error*"])

    def test_parametrize_separated_order(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope="module", params=[1, 2])
            def arg(request):
                return request.param

            values = []
            def test_1(arg):
                values.append(arg)
            def test_2(arg):
                values.append(arg)
        """
        )
        reprec = testrunnerer.inline_run("-v")
        reprec.assertoutcome(passed=4)
        values = reprec.getcalls("testrunner_runtest_call")[0].item.module.values
        assert values == [1, 1, 2, 2]

    def test_module_parametrized_ordering(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeini(
            """
            [testrunner]
            console_output_style=classic
        """
        )
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(scope="session", params="s1 s2".split())
            def sarg():
                pass
            @testrunner.fixture(scope="module", params="m1 m2".split())
            def marg():
                pass
        """
        )
        testrunnerer.makepyfile(
            test_mod1="""
            def test_func(sarg):
                pass
            def test_func1(marg):
                pass
        """,
            test_mod2="""
            def test_func2(sarg):
                pass
            def test_func3(sarg, marg):
                pass
            def test_func3b(sarg, marg):
                pass
            def test_func4(marg):
                pass
        """,
        )
        result = testrunnerer.runtestrunner("-v")
        result.stdout.fnmatch_lines(
            """
            test_mod1.py::test_func[s1] PASSED
            test_mod2.py::test_func2[s1] PASSED
            test_mod2.py::test_func3[s1-m1] PASSED
            test_mod2.py::test_func3b[s1-m1] PASSED
            test_mod2.py::test_func3[s1-m2] PASSED
            test_mod2.py::test_func3b[s1-m2] PASSED
            test_mod1.py::test_func[s2] PASSED
            test_mod2.py::test_func2[s2] PASSED
            test_mod2.py::test_func3[s2-m1] PASSED
            test_mod2.py::test_func3b[s2-m1] PASSED
            test_mod2.py::test_func4[m1] PASSED
            test_mod2.py::test_func3[s2-m2] PASSED
            test_mod2.py::test_func3b[s2-m2] PASSED
            test_mod2.py::test_func4[m2] PASSED
            test_mod1.py::test_func1[m1] PASSED
            test_mod1.py::test_func1[m2] PASSED
        """
        )

    def test_dynamic_parametrized_ordering(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeini(
            """
            [testrunner]
            console_output_style=classic
        """
        )
        testrunnerer.makeconftest(
            """
            import testrunner

            def testrunner_configure(config):
                class DynamicFixturePlugin(object):
                    @testrunner.fixture(scope='session', params=['flavor1', 'flavor2'])
                    def flavor(self, request):
                        return request.param
                config.pluginmanager.register(DynamicFixturePlugin(), 'flavor-fixture')

            @testrunner.fixture(scope='session', params=['vxlan', 'vlan'])
            def encap(request):
                return request.param

            @testrunner.fixture(scope='session', autouse='True')
            def reprovision(request, flavor, encap):
                pass
        """
        )
        testrunnerer.makepyfile(
            """
            def test(reprovision):
                pass
            def test2(reprovision):
                pass
        """
        )
        result = testrunnerer.runtestrunner("-v")
        result.stdout.fnmatch_lines(
            """
            test_dynamic_parametrized_ordering.py::test[flavor1-vxlan] PASSED
            test_dynamic_parametrized_ordering.py::test2[flavor1-vxlan] PASSED
            test_dynamic_parametrized_ordering.py::test[flavor1-vlan] PASSED
            test_dynamic_parametrized_ordering.py::test2[flavor1-vlan] PASSED
            test_dynamic_parametrized_ordering.py::test[flavor2-vlan] PASSED
            test_dynamic_parametrized_ordering.py::test2[flavor2-vlan] PASSED
            test_dynamic_parametrized_ordering.py::test[flavor2-vxlan] PASSED
            test_dynamic_parametrized_ordering.py::test2[flavor2-vxlan] PASSED
        """
        )

    def test_class_ordering(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeini(
            """
            [testrunner]
            console_output_style=classic
        """
        )
        testrunnerer.makeconftest(
            """
            import testrunner

            values = []

            @testrunner.fixture(scope="function", params=[1,2])
            def farg(request):
                return request.param

            @testrunner.fixture(scope="class", params=list("ab"))
            def carg(request):
                return request.param

            @testrunner.fixture(scope="function", autouse=True)
            def append(request, farg, carg):
                def fin():
                    values.append("fin_%s%s" % (carg, farg))
                request.addfinalizer(fin)
        """
        )
        testrunnerer.makepyfile(
            """
            import testrunner

            class TestClass2(object):
                def test_1(self):
                    pass
                def test_2(self):
                    pass
            class TestClass(object):
                def test_3(self):
                    pass
        """
        )
        result = testrunnerer.runtestrunner("-vs")
        result.stdout.re_match_lines(
            r"""
            test_class_ordering.py::TestClass2::test_1\[a-1\] PASSED
            test_class_ordering.py::TestClass2::test_1\[a-2\] PASSED
            test_class_ordering.py::TestClass2::test_2\[a-1\] PASSED
            test_class_ordering.py::TestClass2::test_2\[a-2\] PASSED
            test_class_ordering.py::TestClass2::test_1\[b-1\] PASSED
            test_class_ordering.py::TestClass2::test_1\[b-2\] PASSED
            test_class_ordering.py::TestClass2::test_2\[b-1\] PASSED
            test_class_ordering.py::TestClass2::test_2\[b-2\] PASSED
            test_class_ordering.py::TestClass::test_3\[a-1\] PASSED
            test_class_ordering.py::TestClass::test_3\[a-2\] PASSED
            test_class_ordering.py::TestClass::test_3\[b-1\] PASSED
            test_class_ordering.py::TestClass::test_3\[b-2\] PASSED
        """
        )

    def test_parametrize_separated_order_higher_scope_first(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope="function", params=[1, 2])
            def arg(request):
                param = request.param
                request.addfinalizer(lambda: values.append("fin:%s" % param))
                values.append("create:%s" % param)
                return request.param

            @testrunner.fixture(scope="module", params=["mod1", "mod2"])
            def modarg(request):
                param = request.param
                request.addfinalizer(lambda: values.append("fin:%s" % param))
                values.append("create:%s" % param)
                return request.param

            values = []
            def test_1(arg):
                values.append("test1")
            def test_2(modarg):
                values.append("test2")
            def test_3(arg, modarg):
                values.append("test3")
            def test_4(modarg, arg):
                values.append("test4")
        """
        )
        reprec = testrunnerer.inline_run("-v")
        reprec.assertoutcome(passed=12)
        values = reprec.getcalls("testrunner_runtest_call")[0].item.module.values
        expected = [
            "create:1",
            "test1",
            "fin:1",
            "create:2",
            "test1",
            "fin:2",
            "create:mod1",
            "test2",
            "create:1",
            "test3",
            "fin:1",
            "create:2",
            "test3",
            "fin:2",
            "create:1",
            "test4",
            "fin:1",
            "create:2",
            "test4",
            "fin:2",
            "fin:mod1",
            "create:mod2",
            "test2",
            "create:1",
            "test3",
            "fin:1",
            "create:2",
            "test3",
            "fin:2",
            "create:1",
            "test4",
            "fin:1",
            "create:2",
            "test4",
            "fin:2",
            "fin:mod2",
        ]
        import pprint

        pprint.pprint(list(zip_longest(values, expected)))
        assert values == expected

    def test_parametrized_fixture_teardown_order(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(params=[1,2], scope="class")
            def param1(request):
                return request.param

            values = []

            class TestClass(object):
                @testrunner.fixture(scope="class", autouse=True)
                @classmethod
                def setup1(cls, request, param1):
                    values.append(1)
                    request.addfinalizer(cls.teardown1)

                @classmethod
                def teardown1(self):
                    assert values.pop() == 1

                @testrunner.fixture(scope="class", autouse=True)
                @classmethod
                def setup2(cls, request, param1):
                    values.append(2)
                    request.addfinalizer(cls.teardown2)

                @classmethod
                def teardown2(cls):
                    assert values.pop() == 2

                def test(self):
                    pass

            def test_finish():
                assert not values
        """
        )
        result = testrunnerer.runtestrunner("-v")
        result.stdout.fnmatch_lines(
            """
            *3 passed*
        """
        )
        assert result.ret == 0

    def test_fixture_finalizer(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            import sys

            @testrunner.fixture
            def browser(request):

                def finalize():
                    sys.stdout.write_text('Finalized', encoding='utf-8')
                request.addfinalizer(finalize)
                return {}
        """
        )
        b = testrunnerer.mkdir("subdir")
        b.joinpath("test_overridden_fixture_finalizer.py").write_text(
            textwrap.dedent(
                """\
                import testrunner
                @testrunner.fixture
                def browser(browser):
                    browser['visited'] = True
                    return browser

                def test_browser(browser):
                    assert browser['visited'] is True
                """
            ),
            encoding="utf-8",
        )
        reprec = testrunnerer.runtestrunner("-s")
        for test in ["test_browser"]:
            reprec.stdout.fnmatch_lines(["*Finalized*"])

    def test_class_scope_with_normal_tests(self, testrunnerer: Testrunnerer) -> None:
        testpath = testrunnerer.makepyfile(
            """
            import testrunner

            class Box(object):
                value = 0

            @testrunner.fixture(scope='class')
            def a(request):
                Box.value += 1
                return Box.value

            def test_a(a):
                assert a == 1

            class Test1(object):
                def test_b(self, a):
                    assert a == 2

            class Test2(object):
                def test_c(self, a):
                    assert a == 3"""
        )
        reprec = testrunnerer.inline_run(testpath)
        for test in ["test_a", "test_b", "test_c"]:
            assert reprec.matchreport(test).passed

    def test_request_is_clean(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(params=[1, 2])
            def fix(request):
                request.addfinalizer(lambda: values.append(request.param))
            def test_fix(fix):
                pass
        """
        )
        reprec = testrunnerer.inline_run("-s")
        values = reprec.getcalls("testrunner_runtest_call")[0].item.module.values
        assert values == [1, 2]

    def test_parametrize_separated_lifecycle(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            values = []
            @testrunner.fixture(scope="module", params=[1, 2])
            def arg(request):
                x = request.param
                request.addfinalizer(lambda: values.append("fin%s" % x))
                return request.param
            def test_1(arg):
                values.append(arg)
            def test_2(arg):
                values.append(arg)
        """
        )
        reprec = testrunnerer.inline_run("-vs")
        reprec.assertoutcome(passed=4)
        values = reprec.getcalls("testrunner_runtest_call")[0].item.module.values
        import pprint

        pprint.pprint(values)
        # assert len(values) == 6
        assert values[0] == values[1] == 1
        assert values[2] == "fin1"
        assert values[3] == values[4] == 2
        assert values[5] == "fin2"

    def test_parametrize_function_scoped_finalizers_called(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope="function", params=[1, 2])
            def arg(request):
                x = request.param
                request.addfinalizer(lambda: values.append("fin%s" % x))
                return request.param

            values = []
            def test_1(arg):
                values.append(arg)
            def test_2(arg):
                values.append(arg)
            def test_3():
                assert len(values) == 8
                assert values == [1, "fin1", 2, "fin2", 1, "fin1", 2, "fin2"]
        """
        )
        reprec = testrunnerer.inline_run("-v")
        reprec.assertoutcome(passed=5)

    @testrunner.mark.parametrize("scope", ["session", "function", "module"])
    def test_finalizer_order_on_parametrization(
        self, scope, testrunnerer: Testrunnerer
    ) -> None:
        """#246"""
        testrunnerer.makepyfile(
            f"""
            import testrunner
            values = []

            @testrunner.fixture(scope={scope!r}, params=["1"])
            def fix1(request):
                return request.param

            @testrunner.fixture(scope={scope!r})
            def fix2(request, base):
                def cleanup_fix2():
                    assert not values, "base should not have been finalized"
                request.addfinalizer(cleanup_fix2)

            @testrunner.fixture(scope={scope!r})
            def base(request, fix1):
                def cleanup_base():
                    values.append("fin_base")
                    print("finalizing base")
                request.addfinalizer(cleanup_base)

            def test_begin():
                pass
            def test_baz(base, fix2):
                pass
            def test_other():
                pass
        """
        )
        reprec = testrunnerer.inline_run("-lvs")
        reprec.assertoutcome(passed=3)

    def test_class_scope_parametrization_ordering(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """#396"""
        testrunnerer.makepyfile(
            """
            import testrunner
            values = []
            @testrunner.fixture(params=["John", "Doe"], scope="class")
            def human(request):
                request.addfinalizer(lambda: values.append("fin %s" % request.param))
                return request.param

            class TestGreetings(object):
                def test_hello(self, human):
                    values.append("test_hello")

            class TestMetrics(object):
                def test_name(self, human):
                    values.append("test_name")

                def test_population(self, human):
                    values.append("test_population")
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=6)
        values = reprec.getcalls("testrunner_runtest_call")[0].item.module.values
        assert values == [
            "test_hello",
            "fin John",
            "test_hello",
            "fin Doe",
            "test_name",
            "test_population",
            "fin John",
            "test_name",
            "test_population",
            "fin Doe",
        ]

    def test_parametrize_setup_function(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope="module", params=[1, 2])
            def arg(request):
                return request.param

            @testrunner.fixture(scope="module", autouse=True)
            def mysetup(request, arg):
                request.addfinalizer(lambda: values.append("fin%s" % arg))
                values.append("setup%s" % arg)

            values = []
            def test_1(arg):
                values.append(arg)
            def test_2(arg):
                values.append(arg)
            def test_3():
                import pprint
                pprint.pprint(values)
                if arg == 1:
                    assert values == ["setup1", 1, 1, ]
                elif arg == 2:
                    assert values == ["setup1", 1, 1, "fin1",
                                 "setup2", 2, 2, ]

        """
        )
        reprec = testrunnerer.inline_run("-v")
        reprec.assertoutcome(passed=6)

    def test_fixture_marked_function_not_collected_as_test(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture
            def test_app():
                return 1

            def test_something(test_app):
                assert test_app == 1
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_params_and_ids(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=[object(), object()],
                            ids=['alpha', 'beta'])
            def fix(request):
                return request.param

            def test_foo(fix):
                assert 1
        """
        )
        res = testrunnerer.runtestrunner("-v")
        res.stdout.fnmatch_lines(["*test_foo*alpha*", "*test_foo*beta*"])

    def test_params_and_ids_yieldfixture(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=[object(), object()], ids=['alpha', 'beta'])
            def fix(request):
                 yield request.param

            def test_foo(fix):
                assert 1
        """
        )
        res = testrunnerer.runtestrunner("-v")
        res.stdout.fnmatch_lines(["*test_foo*alpha*", "*test_foo*beta*"])

    def test_deterministic_fixture_collection(
        self, testrunnerer: Testrunnerer, monkeypatch
    ) -> None:
        """#920"""
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope="module",
                            params=["A",
                                    "B",
                                    "C"])
            def A(request):
                return request.param

            @testrunner.fixture(scope="module",
                            params=["DDDDDDDDD", "EEEEEEEEEEEE", "FFFFFFFFFFF", "banansda"])
            def B(request, A):
                return request.param

            def test_foo(B):
                # Something funky is going on here.
                # Despite specified seeds, on what is collected,
                # sometimes we get unexpected passes. hashing B seems
                # to help?
                assert hash(B) or True
            """
        )
        monkeypatch.setenv("PYTHONHASHSEED", "1")
        out1 = testrunnerer.runtestrunner_subprocess("-v")
        monkeypatch.setenv("PYTHONHASHSEED", "2")
        out2 = testrunnerer.runtestrunner_subprocess("-v")
        output1 = [
            line
            for line in out1.outlines
            if line.startswith("test_deterministic_fixture_collection.py::test_foo")
        ]
        output2 = [
            line
            for line in out2.outlines
            if line.startswith("test_deterministic_fixture_collection.py::test_foo")
        ]
        assert len(output1) == 12
        assert output1 == output2


class TestRequestScopeAccess:
    _testrunner_mark = testrunner.mark.parametrize(
        ("scope", "ok", "error"),
        [
            ["session", "", "path class function module"],
            ["module", "module path", "cls function"],
            ["class", "module path cls", "function"],
            ["function", "module path cls function", ""],
        ],
    )

    def test_setup(self, testrunnerer: Testrunnerer, scope, ok, error) -> None:
        testrunnerer.makepyfile(
            f"""
            import testrunner
            @testrunner.fixture(scope={scope!r}, autouse=True)
            def myscoped(request):
                for x in {ok.split()}:
                    assert hasattr(request, x)
                for x in {error.split()}:
                    with testrunner.raises(AttributeError):
                        getattr(request, x)
                assert request.session
                assert request.config
            def test_func():
                pass
        """
        )
        reprec = testrunnerer.inline_run("-l")
        reprec.assertoutcome(passed=1)

    def test_funcarg(self, testrunnerer: Testrunnerer, scope, ok, error) -> None:
        testrunnerer.makepyfile(
            f"""
            import testrunner
            @testrunner.fixture(scope={scope!r})
            def arg(request):
                for x in {ok.split()!r}:
                    assert hasattr(request, x)
                for x in {error.split()!r}:
                    with testrunner.raises(AttributeError):
                        getattr(request, x)
                assert request.session
                assert request.config
            def test_func(arg):
                pass
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)


class TestErrors:
    def test_subfactory_missing_funcarg(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture()
            def gen(qwe123):
                return 1
            def test_something(gen):
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        result.stdout.fnmatch_lines(
            ["*def gen(qwe123):*", "*fixture*qwe123*not found*", "*1 error*"]
        )

    def test_issue498_fixture_finalizer_failing(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture
            def fix1(request):
                def f():
                    raise KeyError
                request.addfinalizer(f)
                return object()

            values = []
            def test_1(fix1):
                values.append(fix1)
            def test_2(fix1):
                values.append(fix1)
            def test_3():
                assert values[0] != values[1]
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            """
            *ERROR*teardown*test_1*
            *KeyError*
            *ERROR*teardown*test_2*
            *KeyError*
            *3 pass*2 errors*
        """
        )

    def test_setupfunc_missing_funcarg(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(autouse=True)
            def gen(qwe123):
                return 1
            def test_something():
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        result.stdout.fnmatch_lines(
            ["*def gen(qwe123):*", "*fixture*qwe123*not found*", "*1 error*"]
        )

    def test_cached_exception_doesnt_get_longer(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Regression test for #12204."""
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="session")
            def bad(): 1 / 0

            def test_1(bad): pass
            def test_2(bad): pass
            def test_3(bad): pass
            """
        )

        result = testrunnerer.runtestrunner_inprocess("--tb=native")
        assert result.ret == ExitCode.TESTS_FAILED
        failures = result.reprec.getfailures()  # type: ignore[attr-defined]
        assert len(failures) == 3
        lines1 = failures[1].longrepr.reprtraceback.reprentries[0].lines
        lines2 = failures[2].longrepr.reprtraceback.reprentries[0].lines
        assert len(lines1) == len(lines2)


class TestShowFixtures:
    def test_funcarg_compat(self, testrunnerer: Testrunnerer) -> None:
        config = testrunnerer.parseconfigure("--funcargs")
        assert config.option.showfixtures

    def test_show_help(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("--fixtures", "--help")
        assert not result.ret

    def test_show_fixtures(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("--fixtures")
        result.stdout.fnmatch_lines(
            [
                "tmp_path_factory [[]session scope[]] -- .../_testrunner/tmpdir.py:*",
                "*for the test session*",
                "tmp_path -- .../_testrunner/tmpdir.py:*",
                "*temporary directory*",
            ]
        )

    def test_show_fixtures_verbose(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("--fixtures", "-v")
        result.stdout.fnmatch_lines(
            [
                "tmp_path_factory [[]session scope[]] -- .../_testrunner/tmpdir.py:*",
                "*for the test session*",
                "tmp_path -- .../_testrunner/tmpdir.py:*",
                "*temporary directory*",
            ]
        )

    def test_show_fixtures_testmodule(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            '''
            import testrunner
            @testrunner.fixture
            def _arg0():
                """ hidden """
            @testrunner.fixture
            def arg1():
                """  hello world """
        '''
        )
        result = testrunnerer.runtestrunner("--fixtures", p)
        result.stdout.fnmatch_lines(
            """
            *tmp_path -- *
            *fixtures defined from*
            *arg1 -- test_show_fixtures_testmodule.py:6*
            *hello world*
        """
        )
        result.stdout.no_fnmatch_line("*arg0*")

    @testrunner.mark.parametrize("testmod", [True, False])
    def test_show_fixtures_conftest(self, testrunnerer: Testrunnerer, testmod) -> None:
        testrunnerer.makeconftest(
            '''
            import testrunner
            @testrunner.fixture
            def arg1():
                """  hello world """
        '''
        )
        if testmod:
            testrunnerer.makepyfile(
                """
                def test_hello():
                    pass
            """
            )
        result = testrunnerer.runtestrunner("--fixtures")
        result.stdout.fnmatch_lines(
            """
            *tmp_path*
            *fixtures defined from*conftest*
            *arg1*
            *hello world*
        """
        )

    def test_show_fixtures_trimmed_doc(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            textwrap.dedent(
                '''\
                import testrunner
                @testrunner.fixture
                def arg1():
                    """
                    line1
                    line2

                    """
                @testrunner.fixture
                def arg2():
                    """
                    line1
                    line2

                    """
                '''
            )
        )
        result = testrunnerer.runtestrunner("--fixtures", p)
        result.stdout.fnmatch_lines(
            textwrap.dedent(
                """\
                * fixtures defined from test_show_fixtures_trimmed_doc *
                arg2 -- test_show_fixtures_trimmed_doc.py:10
                    line1
                    line2
                arg1 -- test_show_fixtures_trimmed_doc.py:3
                    line1
                    line2
                """
            )
        )

    def test_show_fixtures_indented_doc(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            textwrap.dedent(
                '''\
                import testrunner
                @testrunner.fixture
                def fixture1():
                    """
                    line1
                        indented line
                    """
                '''
            )
        )
        result = testrunnerer.runtestrunner("--fixtures", p)
        result.stdout.fnmatch_lines(
            textwrap.dedent(
                """\
                * fixtures defined from test_show_fixtures_indented_doc *
                fixture1 -- test_show_fixtures_indented_doc.py:3
                    line1
                        indented line
                """
            )
        )

    def test_show_fixtures_indented_doc_first_line_unindented(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p = testrunnerer.makepyfile(
            textwrap.dedent(
                '''\
                import testrunner
                @testrunner.fixture
                def fixture1():
                    """line1
                    line2
                        indented line
                    """
                '''
            )
        )
        result = testrunnerer.runtestrunner("--fixtures", p)
        result.stdout.fnmatch_lines(
            textwrap.dedent(
                """\
                * fixtures defined from test_show_fixtures_indented_doc_first_line_unindented *
                fixture1 -- test_show_fixtures_indented_doc_first_line_unindented.py:3
                    line1
                    line2
                        indented line
                """
            )
        )

    def test_show_fixtures_indented_in_class(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            textwrap.dedent(
                '''\
                import testrunner
                class TestClass(object):
                    @testrunner.fixture
                    def fixture1(self):
                        """line1
                        line2
                            indented line
                        """
                '''
            )
        )
        result = testrunnerer.runtestrunner("--fixtures", p)
        result.stdout.fnmatch_lines(
            textwrap.dedent(
                """\
                * fixtures defined from test_show_fixtures_indented_in_class *
                fixture1 -- test_show_fixtures_indented_in_class.py:4
                    line1
                    line2
                        indented line
                """
            )
        )

    def test_show_fixtures_different_files(self, testrunnerer: Testrunnerer) -> None:
        """`--fixtures` only shows fixtures from first file (#833)."""
        testrunnerer.makepyfile(
            test_a='''
            import testrunner

            @testrunner.fixture
            def fix_a():
                """Fixture A"""
                pass

            def test_a(fix_a):
                pass
        '''
        )
        testrunnerer.makepyfile(
            test_b='''
            import testrunner

            @testrunner.fixture
            def fix_b():
                """Fixture B"""
                pass

            def test_b(fix_b):
                pass
        '''
        )
        result = testrunnerer.runtestrunner("--fixtures")
        result.stdout.fnmatch_lines(
            """
            * fixtures defined from test_a *
            fix_a -- test_a.py:4
                Fixture A

            * fixtures defined from test_b *
            fix_b -- test_b.py:4
                Fixture B
        """
        )

    def test_show_fixtures_with_same_name(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            '''
            import testrunner
            @testrunner.fixture
            def arg1():
                """Hello World in conftest.py"""
                return "Hello World"
        '''
        )
        testrunnerer.makepyfile(
            """
            def test_foo(arg1):
                assert arg1 == "Hello World"
        """
        )
        testrunnerer.makepyfile(
            '''
            import testrunner
            @testrunner.fixture
            def arg1():
                """Hi from test module"""
                return "Hi"
            def test_bar(arg1):
                assert arg1 == "Hi"
        '''
        )
        result = testrunnerer.runtestrunner("--fixtures")
        result.stdout.fnmatch_lines(
            """
            * fixtures defined from conftest *
            arg1 -- conftest.py:3
                Hello World in conftest.py

            * fixtures defined from test_show_fixtures_with_same_name *
            arg1 -- test_show_fixtures_with_same_name.py:3
                Hi from test module
        """
        )

    def test_fixture_disallow_twice(self):
        """Test that applying @testrunner.fixture twice generates an error (#2334)."""
        with testrunner.raises(ValueError):

            @testrunner.fixture
            @testrunner.fixture
            def foo():
                raise NotImplementedError()

    def test_show_fixtures_deprecated_nodeid_fixture(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test for fallback string nodeid handling in showfixtures.

        This test can be deleted with FIXTURE_NODEID_DEPRECATED deprecation.
        """
        testrunnerer.makeconftest(
            """
            import testrunner

            def testrunner_collection_finish(session):
                session._fixturemanager._register_fixture(
                    name="does_exist",
                    func=lambda: 0,
                    nodeid="",
                )
            """
        )

        result = testrunnerer.runtestrunner("--fixtures")
        result.stdout.fnmatch_lines(
            [
                "*does_exist -- conftest.py:*",
            ]
        )


class TestContextManagerFixtureFuncs:
    def test_simple(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture
            def arg1():
                print("setup")
                yield 1
                print("teardown")
            def test_1(arg1):
                print("test1", arg1)
            def test_2(arg1):
                print("test2", arg1)
                assert 0
        """
        )
        result = testrunnerer.runtestrunner("-s")
        result.stdout.fnmatch_lines(
            """
            *setup*
            *test1 1*
            *teardown*
            *setup*
            *test2 1*
            *teardown*
        """
        )

    def test_scoped(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="module")
            def arg1():
                print("setup")
                yield 1
                print("teardown")
            def test_1(arg1):
                print("test1", arg1)
            def test_2(arg1):
                print("test2", arg1)
        """
        )
        result = testrunnerer.runtestrunner("-s")
        result.stdout.fnmatch_lines(
            """
            *setup*
            *test1 1*
            *test2 1*
            *teardown*
        """
        )

    def test_setup_exception(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="module")
            def arg1():
                testrunner.fail("setup")
                yield 1
            def test_1(arg1):
                pass
        """
        )
        result = testrunnerer.runtestrunner("-s")
        result.stdout.fnmatch_lines(
            """
            *testrunner.fail*setup*
            *1 error*
        """
        )

    def test_teardown_exception(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="module")
            def arg1():
                yield 1
                testrunner.fail("teardown")
            def test_1(arg1):
                pass
        """
        )
        result = testrunnerer.runtestrunner("-s")
        result.stdout.fnmatch_lines(
            """
            *testrunner.fail*teardown*
            *1 passed*1 error*
        """
        )

    def test_yields_more_than_one(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(scope="module")
            def arg1():
                yield 1
                yield 2
            def test_1(arg1):
                pass
        """
        )
        result = testrunnerer.runtestrunner("-s")
        result.stdout.fnmatch_lines(
            """
            *fixture function*
            *test_yields*:2*
        """
        )

    def test_custom_name(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture(name='meow')
            def arg1():
                return 'mew'
            def test_1(meow):
                print(meow)
        """
        )
        result = testrunnerer.runtestrunner("-s")
        result.stdout.fnmatch_lines(["*mew*"])


class TestParameterizedSubRequest:
    def test_call_from_fixture(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            test_call_from_fixture="""
            import testrunner

            @testrunner.fixture(params=[0, 1, 2])
            def fix_with_param(request):
                return request.param

            @testrunner.fixture
            def get_named_fixture(request):
                return request.getfixturevalue('fix_with_param')

            def test_foo(request, get_named_fixture):
                pass
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "The requested fixture has no parameter defined for test:",
                "    test_call_from_fixture.py::test_foo",
                "Requested fixture 'fix_with_param' defined in:",
                "test_call_from_fixture.py:4",
                "Requested here:",
                "test_call_from_fixture.py:9",
                "*1 error in*",
            ]
        )

    def test_call_from_test(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            test_call_from_test="""
            import testrunner

            @testrunner.fixture(params=[0, 1, 2])
            def fix_with_param(request):
                return request.param

            def test_foo(request):
                request.getfixturevalue('fix_with_param')
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "The requested fixture has no parameter defined for test:",
                "    test_call_from_test.py::test_foo",
                "Requested fixture 'fix_with_param' defined in:",
                "test_call_from_test.py:4",
                "Requested here:",
                "test_call_from_test.py:8",
                "*1 failed*",
            ]
        )

    def test_external_fixture(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(params=[0, 1, 2])
            def fix_with_param(request):
                return request.param
            """
        )

        testrunnerer.makepyfile(
            test_external_fixture="""
            def test_foo(request):
                request.getfixturevalue('fix_with_param')
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "The requested fixture has no parameter defined for test:",
                "    test_external_fixture.py::test_foo",
                "",
                "Requested fixture 'fix_with_param' defined in:",
                "conftest.py:4",
                "Requested here:",
                "test_external_fixture.py:2",
                "*1 failed*",
            ]
        )

    def test_non_relative_path(self, testrunnerer: Testrunnerer) -> None:
        tests_dir = testrunnerer.mkdir("tests")
        fixdir = testrunnerer.mkdir("fixtures")
        fixfile = fixdir.joinpath("fix.py")
        fixfile.write_text(
            textwrap.dedent(
                """\
                import testrunner

                @testrunner.fixture(params=[0, 1, 2])
                def fix_with_param(request):
                    return request.param
                """
            ),
            encoding="utf-8",
        )

        testfile = tests_dir.joinpath("test_foos.py")
        testfile.write_text(
            textwrap.dedent(
                """\
                from fix import fix_with_param

                def test_foo(request):
                    request.getfixturevalue('fix_with_param')
                """
            ),
            encoding="utf-8",
        )

        os.chdir(tests_dir)
        testrunnerer.syspathinsert(fixdir)
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "The requested fixture has no parameter defined for test:",
                "    test_foos.py::test_foo",
                "",
                "Requested fixture 'fix_with_param' defined in:",
                f"{fixfile}:4",
                "Requested here:",
                "test_foos.py:4",
                "*1 failed*",
            ]
        )

        # With non-overlapping rootdir, passing tests_dir.
        rootdir = testrunnerer.mkdir("rootdir")
        os.chdir(rootdir)
        result = testrunnerer.runtestrunner("--rootdir", rootdir, tests_dir)
        result.stdout.fnmatch_lines(
            [
                "The requested fixture has no parameter defined for test:",
                "    test_foos.py::test_foo",
                "",
                "Requested fixture 'fix_with_param' defined in:",
                f"{fixfile}:4",
                "Requested here:",
                f"{testfile}:4",
                "*1 failed*",
            ]
        )


def test_testrunner_fixture_setup_and_post_finalizer_hook(
    testrunnerer: Testrunnerer,
) -> None:
    testrunnerer.makeconftest(
        """
        def testrunner_fixture_setup(fixturedef, request):
            print('ROOT setup hook called for {0} from {1}'.format(fixturedef.argname, request.node.name))
        def testrunner_fixture_post_finalizer(fixturedef, request):
            print('ROOT finalizer hook called for {0} from {1}'.format(fixturedef.argname, request.node.name))
    """
    )
    testrunnerer.makepyfile(
        **{
            "tests/conftest.py": """
            def testrunner_fixture_setup(fixturedef, request):
                print('TESTS setup hook called for {0} from {1}'.format(fixturedef.argname, request.node.name))
            def testrunner_fixture_post_finalizer(fixturedef, request):
                print('TESTS finalizer hook called for {0} from {1}'.format(fixturedef.argname, request.node.name))
        """,
            "tests/test_hooks.py": """
            import testrunner

            @testrunner.fixture()
            def my_fixture():
                return 'some'

            def test_func(my_fixture):
                print('TEST test_func')
                assert my_fixture == 'some'
        """,
        }
    )
    result = testrunnerer.runtestrunner("-s")
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        [
            "*TESTS setup hook called for my_fixture from test_func*",
            "*ROOT setup hook called for my_fixture from test_func*",
            "*TEST test_func*",
            "*TESTS finalizer hook called for my_fixture from test_func*",
            "*ROOT finalizer hook called for my_fixture from test_func*",
        ]
    )


def test_fixture_post_finalizer_called_once(testrunnerer: Testrunnerer) -> None:
    """Test that testrunner_fixture_post_finalizer is called only once per fixture teardown.

    When a fixture depends on multiple parametrized fixtures and all their parameters
    change at the same time, the dependent fixture should be torn down only once,
    and testrunner_fixture_post_finalizer should be called only once for it.
    """
    testrunnerer.makeconftest(
        """
        import testrunner

        finalizer_calls = []

        def testrunner_fixture_post_finalizer(fixturedef, request):
            finalizer_calls.append(fixturedef.argname)

        @testrunner.fixture(autouse=True)
        def check_finalizer_calls(request):
            yield
            # After each test, verify no duplicate finalizer calls.
            if finalizer_calls:
                assert len(finalizer_calls) == len(set(finalizer_calls)), (
                    f"Duplicate finalizer calls detected: {finalizer_calls}"
                )
                finalizer_calls.clear()
        """
    )
    testrunnerer.makepyfile(
        test_fixtures="""
        import testrunner

        @testrunner.fixture(scope="session")
        def foo(request):
            return request.param

        @testrunner.fixture(scope="session")
        def bar(request):
            return request.param

        @testrunner.fixture(scope="session")
        def baz(foo, bar):
            return f"{foo}-{bar}"

        @testrunner.mark.parametrize("foo,bar", [(1, 1)], indirect=True)
        def test_first(foo, bar, baz):
            assert foo == 1
            assert bar == 1
            assert baz == "1-1"

        @testrunner.mark.parametrize("foo,bar", [(2, 2)], indirect=True)
        def test_second(foo, bar, baz):
            assert foo == 2
            assert bar == 2
            assert baz == "2-2"
        """
    )
    result = testrunnerer.runtestrunner("-v")
    # The test passes, which means no duplicate finalizer calls were detected
    # by the check_finalizer_calls autouse fixture.
    result.assert_outcomes(passed=2)


def test_fixture_post_finalizer_hook_exception(testrunnerer: Testrunnerer) -> None:
    """Test that exceptions in testrunner_fixture_post_finalizer hook are caught.

    Also verifies that the fixture cache is properly reset even when the
    post_finalizer hook raises an exception, so the fixture can be rebuilt
    in subsequent tests.
    """
    testrunnerer.makeconftest(
        """
        import testrunner

        def testrunner_fixture_post_finalizer(fixturedef, request):
            if "test_first" in request.node.nodeid:
                raise RuntimeError("Error in post finalizer hook")

        @testrunner.fixture
        def my_fixture(request):
            yield request.node.nodeid
        """
    )
    testrunnerer.makepyfile(
        test_fixtures="""
        def test_first(my_fixture):
            assert "test_first" in my_fixture

        def test_second(my_fixture):
            assert "test_second" in my_fixture
        """
    )
    result = testrunnerer.runtestrunner("-v", "--setup-show")
    result.assert_outcomes(passed=2, errors=1)
    result.stdout.fnmatch_lines(
        [
            "*test_first*PASSED",
            "*test_first*ERROR",
            "*RuntimeError: Error in post finalizer hook*",
        ]
    )
    # Verify fixture is setup twice (rebuilt for test_second despite error).
    result.stdout.fnmatch_lines(
        [
            "test_fixtures.py::test_first ",
            "        SETUP    F my_fixture",
            "        test_fixtures.py::test_first (fixtures used: my_fixture, request) PASSED",
            "test_fixtures.py::test_first ERROR",
            "test_fixtures.py::test_second ",
            "        SETUP    F my_fixture",
            "        test_fixtures.py::test_second (fixtures used: my_fixture, request) PASSED",
            "        TEARDOWN F my_fixture",
        ],
        consecutive=True,
    )


class TestParamValueKey:
    """Unit tests for the equivalence key used by `reorder_items` (#8914)."""

    def test_equal_hashable_values(self) -> None:
        # Build equal-but-not-identical values to exercise the ``==`` path
        # rather than the identity shortcut.
        v1, v2 = tuple([1, 2]), tuple([1, 2])  # noqa: C409
        assert v1 is not v2
        k1, k2 = ParamValueKey(v1, 0), ParamValueKey(v2, 1)
        assert k1 == k2
        assert hash(k1) == hash(k2)

    def test_identical_value(self) -> None:
        value = object()
        assert ParamValueKey(value, 0) == ParamValueKey(value, 1)

    def test_unequal_hashable_values(self) -> None:
        assert ParamValueKey("a", 0) != ParamValueKey("b", 0)

    def test_equal_values_of_different_type(self) -> None:
        # 1 == True == 1.0 in Python, but grouping them could change which
        # value an adjacent test's fixture is set up with, so the key keeps
        # them apart.
        assert ParamValueKey(1, 0) != ParamValueKey(True, 0)
        assert ParamValueKey(1, 0) != ParamValueKey(1.0, 0)

    def test_value_key_never_equals_index_key(self) -> None:
        # hash(0) == hash(ParamValueKey({}, 0)._key) here, so these could
        # collide in a dict bucket; they must still compare unequal.
        assert ParamValueKey(0, 0) != ParamValueKey({}, 0)
        assert ParamValueKey({}, 0) != ParamValueKey(0, 0)

    def test_unhashable_values_compare_by_index(self) -> None:
        assert ParamValueKey({"a": 1}, 0) == ParamValueKey({"b": 2}, 0)
        assert ParamValueKey({"a": 1}, 0) != ParamValueKey({"a": 1}, 1)

    def test_exotic_eq(self) -> None:
        class Exotic:
            def __eq__(self, other: object) -> bool:
                raise ValueError("cannot compare")

            def __hash__(self) -> int:
                return 0

        assert ParamValueKey(Exotic(), 0) != ParamValueKey(Exotic(), 0)

    def test_other_types(self) -> None:
        assert ParamValueKey("a", 0) != "a"
        assert ParamValueKey("a", 0).__eq__("a") is NotImplemented

    def test_repr(self) -> None:
        assert repr(ParamValueKey("a", 0)) == "ParamValueKey(value='a')"
        assert repr(ParamValueKey({}, 3)) == "ParamValueKey(index=3)"


class TestScopeOrdering:
    """Class of tests that ensure fixtures are ordered based on their scopes (#2405)"""

    @testrunner.mark.parametrize("variant", ["mark", "autouse"])
    def test_func_closure_module_auto(
        self, testrunnerer: Testrunnerer, variant, monkeypatch
    ) -> None:
        """Semantically identical to the example posted in #2405 when ``use_mark=True``"""
        monkeypatch.setenv("FIXTURE_ACTIVATION_VARIANT", variant)
        testrunnerer.makepyfile(
            """
            import warnings
            import os
            import testrunner
            VAR = 'FIXTURE_ACTIVATION_VARIANT'
            VALID_VARS = ('autouse', 'mark')

            VARIANT = os.environ.get(VAR)
            if VARIANT is None or VARIANT not in VALID_VARS:
                warnings.warn("{!r} is not  in {}, assuming autouse".format(VARIANT, VALID_VARS) )
                variant = 'mark'

            @testrunner.fixture(scope='module', autouse=VARIANT == 'autouse')
            def m1(): pass

            if VARIANT=='mark':
                _testrunner_mark = testrunner.mark.usefixtures('m1')

            @testrunner.fixture(scope='function', autouse=True)
            def f1(): pass

            def test_func(m1):
                pass
        """
        )
        items, _ = testrunnerer.inline_genitems()
        assert isinstance(items[0], Function)
        request = TopRequest(items[0], _istestrunner=True)
        assert request.fixturenames == ["m1", "f1"]

    def test_func_closure_with_native_fixtures(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Sanity check that verifies the order returned by the closures and the
        actual fixture execution order: the execution order may differ because
        of fixture inter-dependencies."""
        testrunnerer.makepyfile(
            """
            import testrunner

            fixture_order = []

            @testrunner.fixture(scope="session")
            def s1():
                fixture_order.append("s1")

            @testrunner.fixture(scope="package")
            def p1():
                fixture_order.append("p1")

            @testrunner.fixture(scope="module")
            def m1():
                fixture_order.append("m1")

            @testrunner.fixture(scope="session")
            def my_tmp_path_factory():
                fixture_order.append("my_tmp_path_factory")

            @testrunner.fixture
            def my_tmp_path(my_tmp_path_factory):
                fixture_order.append("my_tmp_path")

            @testrunner.fixture
            def f1(my_tmp_path):
                fixture_order.append("f1")

            @testrunner.fixture
            def f2():
                fixture_order.append("f2")

            def test_foo(f1, p1, m1, f2, s1):
                # Actual fixture execution differs from static order: dependent
                # fixtures must be created first ("my_tmp_path").
                assert fixture_order == [
                    "my_tmp_path_factory",
                    "s1",
                    "p1",
                    "m1",
                    "my_tmp_path",
                    "f1",
                    "f2",
                ]
        """
        )
        items, _ = testrunnerer.inline_genitems()
        assert isinstance(items[0], Function)
        request = TopRequest(items[0], _istestrunner=True)
        # Static order of fixtures based on their scope and position in the
        # parameter list.
        assert request.fixturenames == [
            "my_tmp_path_factory",
            "s1",
            "p1",
            "m1",
            "f1",
            "my_tmp_path",
            "f2",
        ]
        result = testrunnerer.runtestrunner("-vv")
        result.assert_outcomes(passed=1)

    def test_func_closure_module(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope='module')
            def m1(): pass

            @testrunner.fixture(scope='function')
            def f1(): pass

            def test_func(f1, m1):
                pass
        """
        )
        items, _ = testrunnerer.inline_genitems()
        assert isinstance(items[0], Function)
        request = TopRequest(items[0], _istestrunner=True)
        assert request.fixturenames == ["m1", "f1"]

    def test_func_closure_scopes_reordered(self, testrunnerer: Testrunnerer) -> None:
        """Test ensures that fixtures are ordered by scope regardless of the order of the parameters, although
        fixtures of same scope keep the declared order
        """
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope='session')
            def s1(): pass

            @testrunner.fixture(scope='module')
            def m1(): pass

            @testrunner.fixture(scope='function')
            def f1(): pass

            @testrunner.fixture(scope='function')
            def f2(): pass

            class Test:

                @testrunner.fixture(scope='class')
                def c1(cls): pass

                def test_func(self, f2, f1, c1, m1, s1):
                    pass
        """
        )
        items, _ = testrunnerer.inline_genitems()
        assert isinstance(items[0], Function)
        request = TopRequest(items[0], _istestrunner=True)
        assert request.fixturenames == ["s1", "m1", "c1", "f2", "f1"]

    def test_func_closure_same_scope_closer_root_first(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Auto-use fixtures of same scope are ordered by closer-to-root first"""
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(scope='module', autouse=True)
            def m_conf(): pass
        """
        )
        testrunnerer.makepyfile(
            **{
                "sub/conftest.py": """
                import testrunner

                @testrunner.fixture(scope='package', autouse=True)
                def p_sub(): pass

                @testrunner.fixture(scope='module', autouse=True)
                def m_sub(): pass
            """,
                "sub/__init__.py": "",
                "sub/test_func.py": """
                import testrunner

                @testrunner.fixture(scope='module', autouse=True)
                def m_test(): pass

                @testrunner.fixture(scope='function')
                def f1(): pass

                def test_func(m_test, f1):
                    pass
        """,
            }
        )
        items, _ = testrunnerer.inline_genitems()
        assert isinstance(items[0], Function)
        request = TopRequest(items[0], _istestrunner=True)
        assert request.fixturenames == ["p_sub", "m_conf", "m_sub", "m_test", "f1"]

    def test_func_closure_all_scopes_complex(self, testrunnerer: Testrunnerer) -> None:
        """Complex test involving all scopes and mixing autouse with normal fixtures"""
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(scope='session')
            def s1(): pass

            @testrunner.fixture(scope='package', autouse=True)
            def p1(): pass
        """
        )
        testrunnerer.makepyfile(**{"__init__.py": ""})
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(scope='module', autouse=True)
            def m1(): pass

            @testrunner.fixture(scope='module')
            def m2(s1): pass

            @testrunner.fixture(scope='function')
            def f1(): pass

            @testrunner.fixture(scope='function')
            def f2(): pass

            class Test:

                @testrunner.fixture(scope='class', autouse=True)
                def c1(self):
                    pass

                def test_func(self, f2, f1, m2):
                    pass
        """
        )
        items, _ = testrunnerer.inline_genitems()
        assert isinstance(items[0], Function)
        request = TopRequest(items[0], _istestrunner=True)
        assert request.fixturenames == ["s1", "p1", "m1", "m2", "c1", "f2", "f1"]

    def test_parametrized_package_scope_reordering(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """A parameterized package-scoped fixture correctly reorders items to
        minimize setups & teardowns.

        Regression test for #12328.
        """
        testrunnerer.makepyfile(
            __init__="",
            conftest="""
                import testrunner
                @testrunner.fixture(scope="package", params=["a", "b"])
                def fix(request):
                    return request.param
            """,
            test_1="def test1(fix): pass",
            test_2="def test2(fix): pass",
        )

        result = testrunnerer.runtestrunner("--setup-plan")
        assert result.ret == ExitCode.OK
        result.stdout.fnmatch_lines(
            [
                "  SETUP    P fix['a']",
                "        test_1.py::test1[a] (fixtures used: fix, request)",
                "        test_2.py::test2[a] (fixtures used: fix, request)",
                "  TEARDOWN P fix['a']",
                "  SETUP    P fix['b']",
                "        test_1.py::test1[b] (fixtures used: fix, request)",
                "        test_2.py::test2[b] (fixtures used: fix, request)",
                "  TEARDOWN P fix['b']",
            ],
        )

    def test_reorder_by_param_value_across_parametrize_calls(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Items parametrized by separate parametrize() calls are grouped by
        the *value* of higher-scoped parameters, so that equal values share a
        single fixture setup.

        Regression test for #8914.
        """
        testrunnerer.makepyfile(
            test_8914="""
                import testrunner

                @testrunner.fixture(scope="session")
                def prepare(request):
                    return request.param

                @testrunner.mark.parametrize("prepare", ["dina"], indirect=True, scope="session")
                def test_1(prepare): pass

                @testrunner.mark.parametrize("prepare", ["more"], indirect=True, scope="session")
                def test_2(prepare): pass

                @testrunner.mark.parametrize("prepare", ["dina"], indirect=True, scope="session")
                def test_3(prepare): pass
            """
        )
        result = testrunnerer.runtestrunner("--setup-plan")
        assert result.ret == ExitCode.OK
        result.stdout.fnmatch_lines(
            [
                "SETUP    S prepare['dina']",
                "        test_8914.py::test_1[dina] (fixtures used: prepare, request)",
                "        test_8914.py::test_3[dina] (fixtures used: prepare, request)",
                "TEARDOWN S prepare['dina']",
                "SETUP    S prepare['more']",
                "        test_8914.py::test_2[more] (fixtures used: prepare, request)",
                "TEARDOWN S prepare['more']",
            ],
        )

    def test_reorder_unhashable_params_fall_back_to_index(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Unhashable parameter values are grouped by their index within their
        parametrize() call, as they were before #8914 was fixed.
        """
        testrunnerer.makepyfile(
            test_unhashable="""
                import testrunner

                @testrunner.fixture(scope="module")
                def fix(request):
                    return request.param

                @testrunner.mark.parametrize("fix", [{"a": 1}, {"b": 2}], indirect=True, scope="module")
                def test_1(fix): pass

                @testrunner.mark.parametrize("fix", [{"a": 1}, {"b": 2}], indirect=True, scope="module")
                def test_2(fix): pass
            """
        )
        result = testrunnerer.runtestrunner("--setup-plan")
        assert result.ret == ExitCode.OK
        result.stdout.fnmatch_lines(
            [
                "    SETUP    M fix[{'a': 1}]",
                "        test_unhashable.py::test_1[fix0] (fixtures used: fix, request)",
                "        test_unhashable.py::test_2[fix0] (fixtures used: fix, request)",
                "    TEARDOWN M fix[{'a': 1}]",
                "    SETUP    M fix[{'b': 2}]",
                "        test_unhashable.py::test_1[fix1] (fixtures used: fix, request)",
                "        test_unhashable.py::test_2[fix1] (fixtures used: fix, request)",
                "    TEARDOWN M fix[{'b': 2}]",
            ],
        )

    def test_reorder_mixed_hashable_unhashable_params(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Hashable and unhashable values parametrizing the same fixture only
        group with their own kind: values with values, unhashables by index.
        """
        testrunnerer.makepyfile(
            test_mixed="""
                import testrunner

                @testrunner.fixture(scope="module")
                def fix(request):
                    return request.param

                @testrunner.mark.parametrize("fix", [{"a": 1}], indirect=True, scope="module")
                def test_1(fix): pass

                @testrunner.mark.parametrize("fix", ["x"], indirect=True, scope="module")
                def test_2(fix): pass

                @testrunner.mark.parametrize("fix", ["x"], indirect=True, scope="module")
                def test_3(fix): pass
            """
        )
        result = testrunnerer.runtestrunner("--setup-plan")
        assert result.ret == ExitCode.OK
        result.stdout.fnmatch_lines(
            [
                "    SETUP    M fix[{'a': 1}]",
                "        test_mixed.py::test_1[fix0] (fixtures used: fix, request)",
                "    TEARDOWN M fix[{'a': 1}]",
                "    SETUP    M fix['x']",
                "        test_mixed.py::test_2[x] (fixtures used: fix, request)",
                "        test_mixed.py::test_3[x] (fixtures used: fix, request)",
                "    TEARDOWN M fix['x']",
            ],
        )

    def test_reorder_params_with_exotic_eq(self, testrunnerer: Testrunnerer) -> None:
        """Parameter values whose ``__eq__`` raises or returns non-booleans
        (e.g. numpy arrays) do not break collection or reordering (#6497).
        """
        testrunnerer.makepyfile(
            """
            import testrunner

            class Exotic:
                def __init__(self, value):
                    self.value = value
                def __eq__(self, other):
                    raise ValueError("cannot compare")
                def __hash__(self):
                    return 0

            @testrunner.fixture(scope="module")
            def fix(request):
                return request.param

            @testrunner.mark.parametrize("fix", [Exotic(1)], indirect=True, scope="module")
            def test_1(fix): pass

            @testrunner.mark.parametrize("fix", [Exotic(2)], indirect=True, scope="module")
            def test_2(fix): pass
            """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.OK
        result.assert_outcomes(passed=2)

    def test_multiple_packages(self, testrunnerer: Testrunnerer) -> None:
        """Complex test involving multiple package fixtures. Make sure teardowns
        are executed in order.
        .
        └── root
            ├── __init__.py
            ├── sub1
            │   ├── __init__.py
            │   ├── conftest.py
            │   └── test_1.py
            └── sub2
                ├── __init__.py
                ├── conftest.py
                └── test_2.py
        """
        root = testrunnerer.mkdir("root")
        root.joinpath("__init__.py").write_text("values = []", encoding="utf-8")
        sub1 = root.joinpath("sub1")
        sub1.mkdir()
        sub1.joinpath("__init__.py").touch()
        sub1.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
            import testrunner
            from .. import values
            @testrunner.fixture(scope="package")
            def fix():
                values.append("pre-sub1")
                yield values
                assert values.pop() == "pre-sub1"
        """
            ),
            encoding="utf-8",
        )
        sub1.joinpath("test_1.py").write_text(
            textwrap.dedent(
                """\
            from .. import values
            def test_1(fix):
                assert values == ["pre-sub1"]
        """
            ),
            encoding="utf-8",
        )
        sub2 = root.joinpath("sub2")
        sub2.mkdir()
        sub2.joinpath("__init__.py").touch()
        sub2.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
            import testrunner
            from .. import values
            @testrunner.fixture(scope="package")
            def fix():
                values.append("pre-sub2")
                yield values
                assert values.pop() == "pre-sub2"
        """
            ),
            encoding="utf-8",
        )
        sub2.joinpath("test_2.py").write_text(
            textwrap.dedent(
                """\
            from .. import values
            def test_2(fix):
                assert values == ["pre-sub2"]
        """
            ),
            encoding="utf-8",
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=2)

    def test_class_fixture_self_instance(self, testrunnerer: Testrunnerer) -> None:
        """Check that plugin classes which implement fixtures receive the plugin instance
        as self (see #2270).
        """
        testrunnerer.makeconftest(
            """
            import testrunner

            def testrunner_configure(config):
                config.pluginmanager.register(MyPlugin())

            class MyPlugin():
                def __init__(self):
                    self.arg = 1

                @testrunner.fixture(scope='function')
                def myfix(self):
                    assert isinstance(self, MyPlugin)
                    return self.arg
        """
        )

        testrunnerer.makepyfile(
            """
            class TestClass(object):
                def test_1(self, myfix):
                    assert myfix == 1
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)


def test_call_fixture_function_error():
    """Check if an error is raised if a fixture function is called directly (#4545)"""

    @testrunner.fixture
    def fix():
        raise NotImplementedError()

    with testrunner.raises(testrunner.fail.Exception):
        assert fix() == 1


def test_fixture_double_decorator(testrunnerer: Testrunnerer) -> None:
    """Check if an error is raised when using @testrunner.fixture twice."""
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture
        @testrunner.fixture
        def fixt():
            pass
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(
        [
            "E * ValueError: @testrunner.fixture is being applied more than once to the same function 'fixt'"
        ]
    )


def test_fixture_class(testrunnerer: Testrunnerer) -> None:
    """Check if an error is raised when using @testrunner.fixture on a class."""
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture
        class A:
            pass
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(errors=1)


def test_fixture_param_shadowing(testrunnerer: Testrunnerer) -> None:
    """Parametrized arguments would be shadowed if a fixture with the same name also exists (#5036)"""
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture(params=['a', 'b'])
        def argroot(request):
            return request.param

        @testrunner.fixture
        def arg(argroot):
            return argroot

        # This should only be parametrized directly
        @testrunner.mark.parametrize("arg", [1])
        def test_direct(arg):
            assert arg == 1

        # This should be parametrized based on the fixtures
        def test_normal_fixture(arg):
            assert isinstance(arg, str)

        # Indirect should still work:

        @testrunner.fixture
        def arg2(request):
            return 2*request.param

        @testrunner.mark.parametrize("arg2", [1], indirect=True)
        def test_indirect(arg2):
            assert arg2 == 2
    """
    )
    # Only one test should have run
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=4)
    result.stdout.fnmatch_lines(["*::test_direct[[]1[]]*"])
    result.stdout.fnmatch_lines(["*::test_normal_fixture[[]a[]]*"])
    result.stdout.fnmatch_lines(["*::test_normal_fixture[[]b[]]*"])
    result.stdout.fnmatch_lines(["*::test_indirect[[]1[]]*"])


def test_fixture_named_request(testrunnerer: Testrunnerer) -> None:
    testrunnerer.copy_example("fixtures/test_fixture_named_request.py")
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            "*'request' is a reserved word for fixtures, use another name:",
            "  *test_fixture_named_request.py:8",
        ]
    )


def test_indirect_fixture_does_not_break_scope(testrunnerer: Testrunnerer) -> None:
    """Ensure that fixture scope is respected when using indirect fixtures (#570)"""
    testrunnerer.makepyfile(
        """
        import testrunner
        instantiated  = []

        @testrunner.fixture(scope="session")
        def fixture_1(request):
            instantiated.append(("fixture_1", request.param))


        @testrunner.fixture(scope="session")
        def fixture_2(request):
            instantiated.append(("fixture_2", request.param))


        scenarios = [
            ("A", "a1"),
            ("A", "a2"),
            ("B", "b1"),
            ("B", "b2"),
            ("C", "c1"),
            ("C", "c2"),
        ]

        @testrunner.mark.parametrize(
            "fixture_1,fixture_2", scenarios, indirect=["fixture_1", "fixture_2"]
        )
        def test_create_fixtures(fixture_1, fixture_2):
            pass


        def test_check_fixture_instantiations():
            assert instantiated == [
                ('fixture_1', 'A'),
                ('fixture_2', 'a1'),
                ('fixture_2', 'a2'),
                ('fixture_1', 'B'),
                ('fixture_2', 'b1'),
                ('fixture_2', 'b2'),
                ('fixture_1', 'C'),
                ('fixture_2', 'c1'),
                ('fixture_2', 'c2'),
            ]
    """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=7)


def test_fixture_parametrization_nparray(testrunnerer: Testrunnerer) -> None:
    testrunner.importorskip("numpy")

    testrunnerer.makepyfile(
        """
        from numpy import linspace
        from testrunner import fixture

        @fixture(params=linspace(1, 10, 10))
        def value(request):
            return request.param

        def test_bug(value):
            assert value == value
    """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=10)


def test_fixture_arg_ordering(testrunnerer: Testrunnerer) -> None:
    """
    This test describes how fixtures in the same scope but without explicit dependencies
    between them are created. While users should make dependencies explicit, often
    they rely on this order, so this test exists to catch regressions in this regard.
    See #6540 and #6492.
    """
    p1 = testrunnerer.makepyfile(
        """
        import testrunner

        suffixes = []

        @testrunner.fixture
        def fix_1(): suffixes.append("fix_1")
        @testrunner.fixture
        def fix_2(): suffixes.append("fix_2")
        @testrunner.fixture
        def fix_3(): suffixes.append("fix_3")
        @testrunner.fixture
        def fix_4(): suffixes.append("fix_4")
        @testrunner.fixture
        def fix_5(): suffixes.append("fix_5")

        @testrunner.fixture
        def fix_combined(fix_1, fix_2, fix_3, fix_4, fix_5): pass

        def test_suffix(fix_combined):
            assert suffixes == ["fix_1", "fix_2", "fix_3", "fix_4", "fix_5"]
        """
    )
    result = testrunnerer.runtestrunner("-vv", str(p1))
    assert result.ret == 0


def test_yield_fixture_with_no_value(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner
        @testrunner.fixture(name='custom')
        def empty_yield():
            if False:
                yield

        def test_fixt(custom):
            pass
        """
    )
    expected = "E               ValueError: custom did not yield a value"
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines([expected])
    assert result.ret == ExitCode.TESTS_FAILED


def test_deduplicate_names() -> None:
    items = deduplicate_names("abacd")
    assert items == ("a", "b", "c", "d")
    items = deduplicate_names((*items, "g", "f", "g", "e", "b"))
    assert items == ("a", "b", "c", "d", "g", "f", "e")


def test_staticmethod_classmethod_fixture_instance(testrunnerer: Testrunnerer) -> None:
    """Ensure that static and class methods get and have access to a fresh
    instance.

    This also ensures `setup_method` works well with static and class methods.

    Regression test for #12065.
    """
    testrunnerer.makepyfile(
        """
        import testrunner

        class Test:
            ran_setup_method = False
            ran_fixture = False

            def setup_method(self):
                assert not self.ran_setup_method
                self.ran_setup_method = True

            @testrunner.fixture(autouse=True)
            def fixture(self):
                assert not self.ran_fixture
                self.ran_fixture = True

            def test_method(self):
                assert self.ran_setup_method
                assert self.ran_fixture

            @staticmethod
            def test_1(request):
                assert request.instance.ran_setup_method
                assert request.instance.ran_fixture

            @classmethod
            def test_2(cls, request):
                assert request.instance.ran_setup_method
                assert request.instance.ran_fixture
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.OK
    result.assert_outcomes(passed=3)


def test_scoped_fixture_caching(testrunnerer: Testrunnerer) -> None:
    """Make sure setup and finalization is only run once when using scoped fixture
    multiple times."""
    testrunnerer.makepyfile(
        """
        from __future__ import annotations

        from typing import Generator

        import testrunner
        executed: list[str] = []
        @testrunner.fixture(scope="class")
        def fixture_1() -> Generator[None, None, None]:
            executed.append("fix setup")
            yield
            executed.append("fix teardown")


        class TestFixtureCaching:
            def test_1(self, fixture_1: None) -> None:
                assert executed == ["fix setup"]

            def test_2(self, fixture_1: None) -> None:
                assert executed == ["fix setup"]


        def test_expected_setup_and_teardown() -> None:
            assert executed == ["fix setup", "fix teardown"]
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0


def test_scoped_fixture_caching_exception(testrunnerer: Testrunnerer) -> None:
    """Make sure setup & finalization is only run once for scoped fixture, with a cached exception."""
    testrunnerer.makepyfile(
        """
        from __future__ import annotations

        import testrunner
        executed_crash: list[str] = []


        @testrunner.fixture(scope="class")
        def fixture_crash(request: testrunner.FixtureRequest) -> None:
            executed_crash.append("fix_crash setup")

            def my_finalizer() -> None:
                executed_crash.append("fix_crash teardown")

            request.addfinalizer(my_finalizer)

            raise Exception("foo")


        class TestFixtureCachingException:
            @testrunner.mark.xfail
            def test_crash_1(self, fixture_crash: None) -> None:
                ...

            @testrunner.mark.xfail
            def test_crash_2(self, fixture_crash: None) -> None:
                ...


        def test_crash_expected_setup_and_teardown() -> None:
            assert executed_crash == ["fix_crash setup", "fix_crash teardown"]
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0


def test_scoped_fixture_teardown_order(testrunnerer: Testrunnerer) -> None:
    """
    Make sure teardowns happen in reverse order of setup with scoped fixtures, when
    a later test only depends on a subset of scoped fixtures.

    Regression test for https://github.com/jacksonsr451/test-runner/issues/1489
    """
    testrunnerer.makepyfile(
        """
        from typing import Generator

        import testrunner


        last_executed = ""


        @testrunner.fixture(scope="module")
        def fixture_1() -> Generator[None, None, None]:
            global last_executed
            assert last_executed == ""
            last_executed = "fixture_1_setup"
            yield
            assert last_executed == "fixture_2_teardown"
            last_executed = "fixture_1_teardown"


        @testrunner.fixture(scope="module")
        def fixture_2() -> Generator[None, None, None]:
            global last_executed
            assert last_executed == "fixture_1_setup"
            last_executed = "fixture_2_setup"
            yield
            assert last_executed == "run_test"
            last_executed = "fixture_2_teardown"


        def test_fixture_teardown_order(fixture_1: None, fixture_2: None) -> None:
            global last_executed
            assert last_executed == "fixture_2_setup"
            last_executed = "run_test"


        def test_2(fixture_1: None) -> None:
            # This would previously queue an additional teardown of fixture_1,
            # despite fixture_1's value being cached, which caused fixture_1 to be
            # torn down before fixture_2 - violating the rule that teardowns should
            # happen in reverse order of setup.
            pass
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0


def test_subfixture_teardown_order(testrunnerer: Testrunnerer) -> None:
    """
    Make sure fixtures don't re-register their finalization in parent fixtures multiple
    times, causing ordering failure in their teardowns.

    Regression test for #12135
    """
    testrunnerer.makepyfile(
        """
        import testrunner

        execution_order = []

        @testrunner.fixture(scope="class")
        def fixture_1():
            ...

        @testrunner.fixture(scope="class")
        def fixture_2(fixture_1):
            execution_order.append("setup 2")
            yield
            execution_order.append("teardown 2")

        @testrunner.fixture(scope="class")
        def fixture_3(fixture_1):
            execution_order.append("setup 3")
            yield
            execution_order.append("teardown 3")

        class TestFoo:
            def test_initialize_fixtures(self, fixture_2, fixture_3):
                ...

            # This would previously reschedule fixture_2's finalizer in the parent fixture,
            # causing it to be torn down before fixture 3.
            def test_reschedule_fixture_2(self, fixture_2):
                ...

            # Force finalization directly on fixture_1
            # Otherwise the cleanup would sequence 3&2 before 1 as normal.
            @testrunner.mark.parametrize("fixture_1", [None], indirect=["fixture_1"])
            def test_finalize_fixture_1(self, fixture_1):
                ...

        def test_result():
            assert execution_order == ["setup 2", "setup 3", "teardown 3", "teardown 2"]
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0


def test_parametrized_fixture_scope_allowed(testrunnerer: Testrunnerer) -> None:
    """
    Make sure scope from parametrize does not affect fixture's ability to be
    depended upon.

    Regression test for #13248
    """
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture(scope="session")
        def my_fixture(request):
            return getattr(request, "param", None)

        @testrunner.fixture(scope="session")
        def another_fixture(my_fixture):
            return my_fixture

        @testrunner.mark.parametrize("my_fixture", ["a value"], indirect=True, scope="function")
        def test_foo(another_fixture):
            assert another_fixture == "a value"
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=1)


def test_collect_positional_only(testrunnerer: Testrunnerer) -> None:
    """Support the collection of tests with positional-only arguments (#13376)."""
    testrunnerer.makepyfile(
        """
        import testrunner

        class Test:
            @testrunner.fixture
            def fix(self):
                return 1

            def test_method(self, /, fix):
                assert fix == 1
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=1)


def test_parametrization_dependency_pruning(testrunnerer: Testrunnerer) -> None:
    """Test that when a fixture is dynamically shadowed by parameterization, it
    is properly pruned and not executed."""
    testrunnerer.makepyfile(
        """
        import testrunner


        # This fixture should never run because shadowed_fixture is parametrized.
        @testrunner.fixture
        def boom():
            raise RuntimeError("BOOM!")


        # This fixture is shadowed by metafunc.parametrize in testrunner_generate_tests.
        @testrunner.fixture
        def shadowed_fixture(boom):
            return "fixture_value"


        # Dynamically parametrize shadowed_fixture, replacing the fixture with direct values.
        def testrunner_generate_tests(metafunc):
            if "shadowed_fixture" in metafunc.fixturenames:
                metafunc.parametrize("shadowed_fixture", ["param1", "param2"])


        # This test should receive shadowed_fixture as a parametrized value, and
        # boom should not explode.
        def test_shadowed(shadowed_fixture):
            assert shadowed_fixture in ["param1", "param2"]
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=2)


def test_fixture_closure_with_overrides(testrunnerer: Testrunnerer) -> None:
    """Test that an item's static fixture closure properly includes transitive
    dependencies through overridden fixtures (#13773)."""
    testrunnerer.makeconftest(
        """
        import testrunner

        @testrunner.fixture
        def db(): pass

        @testrunner.fixture
        def app(db): pass
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner

        # Overrides conftest-level `app` and requests it.
        @testrunner.fixture
        def app(app): pass

        class TestClass:
            # Overrides module-level `app` and requests it.
            @testrunner.fixture
            def app(self, app): pass

            def test_something(self, request, app):
                # Both dynamic and static fixture closures should include 'db'.
                assert 'db' in request.fixturenames
                assert 'db' in request.node.fixturenames
                # No dynamic dependencies, should be equal.
                assert set(request.fixturenames) == set(request.node.fixturenames)
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=1)


def test_fixture_closure_with_overrides_and_intermediary(
    testrunnerer: Testrunnerer,
) -> None:
    """Test that an item's static fixture closure properly includes transitive
    dependencies through overridden fixtures (#13773).

    A more complicated case than test_fixture_closure_with_overrides, adds an
    intermediary so the override chain is not direct.
    """
    testrunnerer.makeconftest(
        """
        import testrunner

        @testrunner.fixture
        def db(): pass

        @testrunner.fixture
        def app(db): pass

        @testrunner.fixture
        def intermediate(app): pass
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner

        # Overrides conftest-level `app` and requests it.
        @testrunner.fixture
        def app(intermediate): pass

        class TestClass:
            # Overrides module-level `app` and requests it.
            @testrunner.fixture
            def app(self, app): pass

            def test_something(self, request, app):
                # Both dynamic and static fixture closures should include 'db'.
                assert 'db' in request.fixturenames
                assert 'db' in request.node.fixturenames
                # No dynamic dependencies, should be equal.
                assert set(request.fixturenames) == set(request.node.fixturenames)
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=1)


def test_fixture_closure_with_overrides_and_parametrization(
    testrunnerer: Testrunnerer,
) -> None:
    """Test that an item's static fixture closure properly includes transitive
    dependencies through overridden fixtures (#13773) when also including
    parametrization (#14248)."""
    testrunnerer.makeconftest(
        """
        import testrunner

        @testrunner.fixture
        def db(): pass

        @testrunner.fixture
        def app(db): pass
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner

        # Overrides conftest-level `app` and requests it.
        @testrunner.fixture
        def app(app): pass

        class TestClass:
            # Overrides module-level `app` and requests it.
            @testrunner.fixture
            def app(self, app): pass

            @testrunner.mark.parametrize("a", [1])
            def test_something(self, request, app, a):
                # Both dynamic and static fixture closures should include 'db'.
                assert 'db' in request.fixturenames
                assert 'db' in request.node.fixturenames
                # No dynamic dependencies, should be equal.
                assert set(request.fixturenames) == set(request.node.fixturenames)
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=1)


def test_fixture_closure_with_broken_override_chain(testrunnerer: Testrunnerer) -> None:
    """Test that an item's static fixture closure properly includes transitive
    dependencies through overridden fixtures (#13773).

    A more complicated case than test_fixture_closure_with_overrides, one of the
    fixtures in the chain doesn't call its super, so it shouldn't be included.
    """
    testrunnerer.makeconftest(
        """
        import testrunner

        @testrunner.fixture
        def db(): pass

        @testrunner.fixture
        def app(db): pass
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner

        # Overrides conftest-level `app` and *doesn't* request it.
        @testrunner.fixture
        def app(): pass

        class TestClass:
            # Overrides module-level `app` and requests it.
            @testrunner.fixture
            def app(self, app): pass

            def test_something(self, request, app):
                # Both dynamic and static fixture closures should include 'db'.
                assert 'db' not in request.fixturenames
                assert 'db' not in request.node.fixturenames
                # No dynamic dependencies, should be equal.
                assert set(request.fixturenames) == set(request.node.fixturenames)
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=1)


def test_fixture_closure_handles_circular_dependencies(
    testrunnerer: Testrunnerer,
) -> None:
    """Test that getfixtureclosure properly handles circular dependencies.

    The test will error in the runtest phase due to the fixture loop,
    but the closure computation still completes.
    """
    testrunnerer.makepyfile(
        """
        import testrunner

        # Direct circular dependency.
        @testrunner.fixture
        def fix_a(fix_b): pass

        @testrunner.fixture
        def fix_b(fix_a): pass

        # Indirect circular dependency through multiple fixtures.
        @testrunner.fixture
        def fix_x(fix_y): pass

        @testrunner.fixture
        def fix_y(fix_z): pass

        @testrunner.fixture
        def fix_z(fix_x): pass

        def test_circular_deps(fix_a, fix_x):
            pass
        """
    )
    items, _hookrec = testrunnerer.inline_genitems()
    assert isinstance(items[0], Function)
    assert items[0].fixturenames == ["fix_a", "fix_b", "fix_x", "fix_y", "fix_z"]


def test_fixture_closure_handles_diamond_dependencies(
    testrunnerer: Testrunnerer,
) -> None:
    """Test that getfixtureclosure properly handles diamond dependencies."""
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture
        def db(): pass

        @testrunner.fixture
        def user(db): pass

        @testrunner.fixture
        def session(db): pass

        @testrunner.fixture
        def app(user, session): pass

        def test_diamond_deps(request, app):
            assert request.node.fixturenames == ["request", "app", "user", "db", "session"]
            assert request.fixturenames == ["request", "app", "user", "db", "session"]
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=1)


def test_fixture_closure_with_complex_override_and_shared_deps(
    testrunnerer: Testrunnerer,
) -> None:
    """Test that shared dependencies in override chains are processed only once."""
    testrunnerer.makeconftest(
        """
        import testrunner

        @testrunner.fixture
        def db(): pass

        @testrunner.fixture
        def cache(): pass

        @testrunner.fixture
        def settings(): pass

        @testrunner.fixture
        def app(db, cache, settings): pass
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner

        # Override app, but also directly use cache and settings.
        # This creates multiple paths to the same fixtures.
        @testrunner.fixture
        def app(app, cache, settings): pass

        class TestClass:
            # Another override that uses both app and cache.
            @testrunner.fixture
            def app(self, app, cache): pass

            def test_shared_deps(self, request, app):
                assert request.node.fixturenames == ["request", "app", "db", "cache", "settings"]
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=1)


def test_fixture_closure_with_parametrize_ignore(testrunnerer: Testrunnerer) -> None:
    """Test that getfixtureclosure properly handles parametrization argnames
    which override a fixture."""
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture
        def fix1(fix2): pass

        @testrunner.fixture
        def fix2(fix3): pass

        @testrunner.fixture
        def fix3(): pass

        @testrunner.mark.parametrize('fix2', ['2'])
        def test_it(request, fix1):
            assert request.node.fixturenames == ["request", "fix1", "fix2"]
            assert request.fixturenames == ["request", "fix1", "fix2"]
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=1)


def test_overridden_fixture_depends_on_parametrized(testrunnerer: Testrunnerer) -> None:
    """#11075"""
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture(params=["foo"])
        def fixture_foo(request):
            yield request.param

        @testrunner.fixture
        def fixture_bar(fixture_foo):
            yield fixture_foo

        class TestFoobar:
            @testrunner.fixture
            def fixture_bar(self, fixture_bar):
                yield fixture_bar

            def test_foobar(self, fixture_bar):
                assert fixture_bar == "foo"
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=1)


@testrunner.mark.filterwarnings(
    "default:cannot discover fixture *:testrunner.TestrunnerWarning"
)
def test_custom_decorated_fixture_warning(testrunnerer: Testrunnerer) -> None:
    """Fixtures wrapped by custom decorators using functools.wraps warn."""
    testrunnerer.makepyfile(
        """
        import testrunner
        import functools

        def custom_deco(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        class TestClass:
            @custom_deco
            @testrunner.fixture
            def my_fixture(self):
                return "fixture_value"

            def test_fixture_usage(self, my_fixture):
                assert my_fixture == "fixture_value"
        """
    )
    result = testrunnerer.runtestrunner_inprocess(
        "-v", "-rw", "-W", "default::testrunner.TestrunnerWarning"
    )

    result.stdout.fnmatch_lines(
        [
            "*test_custom_decorated_fixture_warning.py:*: "
            "TestrunnerWarning: cannot discover fixture 'my_fixture' "
            "due to being wrapped in decorators*"
        ]
    )

    result.stdout.fnmatch_lines(["*fixture 'my_fixture' not found*"])
    result.assert_outcomes(errors=1)


@testrunner.mark.filterwarnings(
    "default:cannot discover fixture *:testrunner.TestrunnerWarning"
)
def test_custom_decorated_fixture_above_classmethod_warning(
    testrunnerer: Testrunnerer,
) -> None:
    """Warn when wraps hides a fixture that itself wraps @classmethod.

    The fixture definition stores the classmethod descriptor; warning emission
    peels it to reach the underlying function for warn_explicit_for.
    """
    testrunnerer.makepyfile(
        """
        import testrunner
        import functools

        def custom_deco(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        class TestClass:
            @custom_deco
            @testrunner.fixture(scope="class")
            @classmethod
            def my_fixture(cls):
                return "fixture_value"

            def test_fixture_usage(self, my_fixture):
                assert my_fixture == "fixture_value"
        """
    )
    result = testrunnerer.runtestrunner_inprocess(
        "-v", "-rw", "-W", "default::testrunner.TestrunnerWarning"
    )

    result.stdout.fnmatch_lines(
        [
            "*TestrunnerWarning: cannot discover fixture 'my_fixture' "
            "due to being wrapped in decorators*"
        ]
    )
    result.stdout.fnmatch_lines(["*fixture 'my_fixture' not found*"])
    result.assert_outcomes(errors=1)


@testrunner.mark.filterwarnings(
    "default:cannot discover fixture *:testrunner.TestrunnerWarning"
)
def test_classmethod_above_fixture_warning(testrunnerer: Testrunnerer) -> None:
    """@classmethod above @testrunner.fixture hides the fixture (#13507)."""
    testrunnerer.makepyfile(
        """
        import testrunner

        class TestFixture:
            @classmethod
            @testrunner.fixture(scope="class")
            def fixt(cls):
                return 1

            def test_fixt(self, fixt):
                assert fixt == 1
        """
    )
    result = testrunnerer.runtestrunner_inprocess(
        "-v", "-rw", "-W", "default::testrunner.TestrunnerWarning"
    )

    result.stdout.fnmatch_lines(
        [
            "*test_classmethod_above_fixture_warning.py:*: "
            "TestrunnerWarning: cannot discover fixture 'fixt' because it is "
            "wrapped by @classmethod; place @testrunner.fixture above @classmethod*"
        ]
    )
    result.stdout.fnmatch_lines(["*fixture 'fixt' not found*"])
    result.assert_outcomes(errors=1)


@testrunner.mark.filterwarnings(
    "default:fixture * is wrapped by @staticmethod*:testrunner.TestrunnerWarning"
)
def test_staticmethod_above_fixture_warning(testrunnerer: Testrunnerer) -> None:
    """@staticmethod above @testrunner.fixture always warns.

    Unlike ``classmethod``, discovery still finds the fixture via
    ``staticmethod.__get__``, so the test can pass; a leading ``self``/``cls``
    already fails as a missing fixture without special-casing here.
    """
    testrunnerer.makepyfile(
        """
        import testrunner

        class TestFixture:
            @staticmethod
            @testrunner.fixture
            def fixt():
                return 1

            def test_fixt(self, fixt):
                assert fixt == 1
        """
    )
    result = testrunnerer.runtestrunner_inprocess(
        "-v", "-rw", "-W", "default::testrunner.TestrunnerWarning"
    )

    result.stdout.fnmatch_lines(
        [
            "*test_staticmethod_above_fixture_warning.py:*: "
            "TestrunnerWarning: fixture 'fixt' is wrapped by @staticmethod above "
            "@testrunner.fixture; place @testrunner.fixture above @staticmethod*"
        ]
    )
    result.assert_outcomes(passed=1)


def test_fixture_above_classmethod_still_works(testrunnerer: Testrunnerer) -> None:
    """Documented order @testrunner.fixture above @classmethod remains discoverable."""
    testrunnerer.makepyfile(
        """
        import testrunner

        class TestFixture:
            @testrunner.fixture(scope="class")
            @classmethod
            def fixt(cls):
                return 1

            def test_fixt(self, fixt):
                assert fixt == 1
        """
    )
    result = testrunnerer.runtestrunner("-v")
    result.assert_outcomes(passed=1)


def test_fixture_above_staticmethod_still_works(testrunnerer: Testrunnerer) -> None:
    """@testrunner.fixture above @staticmethod remains discoverable without warning."""
    testrunnerer.makepyfile(
        """
        import testrunner

        class TestFixture:
            @testrunner.fixture
            @staticmethod
            def fixt():
                return 1

            def test_fixt(self, fixt):
                assert fixt == 1
        """
    )
    result = testrunnerer.runtestrunner(
        "-W", "error::testrunner.TestrunnerWarning", "-v"
    )
    result.assert_outcomes(passed=1)


@testrunner.mark.filterwarnings(
    "default:cannot discover fixture *:testrunner.TestrunnerWarning"
)
def test_classmethod_above_fixture_warning_inherited(
    testrunnerer: Testrunnerer,
) -> None:
    """MRO ``__dict__`` lookup finds @classmethod wrappers on a base class."""
    testrunnerer.makepyfile(
        """
        import testrunner

        class Base:
            @classmethod
            @testrunner.fixture(scope="class")
            def fixt(cls):
                return 1

        class TestFixture(Base):
            def test_fixt(self, fixt):
                assert fixt == 1
        """
    )
    result = testrunnerer.runtestrunner_inprocess(
        "-v", "-rw", "-W", "default::testrunner.TestrunnerWarning"
    )

    result.stdout.fnmatch_lines(
        [
            "*TestrunnerWarning: cannot discover fixture 'fixt' because it is "
            "wrapped by @classmethod; place @testrunner.fixture above @classmethod*"
        ]
    )
    result.stdout.fnmatch_lines(["*fixture 'fixt' not found*"])
    result.assert_outcomes(errors=1)
