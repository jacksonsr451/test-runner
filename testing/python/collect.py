# mypy: allow-untyped-defs
from __future__ import annotations

import os
import sys
import textwrap
from typing import Any

import _testrunner._code
from _testrunner.config import ExitCode
from _testrunner.config.exceptions import UsageError
from _testrunner.main import Session
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.nodes import Collector
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.python import Class
from _testrunner.python import Function
import testrunner


class TestModule:
    def test_failing_import(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol("import alksdjalskdjalkjals")
        with testrunner.raises(Collector.CollectError):
            modcol.collect()

    def test_import_duplicate(self, testrunnerer: Testrunnerer) -> None:
        a = testrunnerer.mkdir("a")
        b = testrunnerer.mkdir("b")
        p1 = a.joinpath("test_whatever.py")
        p1.touch()
        p2 = b.joinpath("test_whatever.py")
        p2.touch()
        # ensure we don't have it imported already
        sys.modules.pop(p1.stem, None)

        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "*import*mismatch*",
                "*imported*test_whatever*",
                f"*{p1}*",
                "*not the same*",
                f"*{p2}*",
                "*HINT*",
            ]
        )

    def test_import_prepend_append(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        root1 = testrunnerer.mkdir("root1")
        root2 = testrunnerer.mkdir("root2")
        root1.joinpath("x456.py").touch()
        root2.joinpath("x456.py").touch()
        p = root2.joinpath("test_x456.py")
        monkeypatch.syspath_prepend(str(root1))
        p.write_text(
            textwrap.dedent(
                f"""\
                import x456
                def test():
                    assert x456.__file__.startswith({str(root2)!r})
                """
            ),
            encoding="utf-8",
        )
        with monkeypatch.context() as mp:
            mp.chdir(root2)
            reprec = testrunnerer.inline_run("--import-mode=append")
            reprec.assertoutcome(passed=0, failed=1)
            reprec = testrunnerer.inline_run()
            reprec.assertoutcome(passed=1)

    def test_syntax_error_in_module(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol("this is a syntax error")
        with testrunner.raises(modcol.CollectError):
            modcol.collect()
        with testrunner.raises(modcol.CollectError):
            modcol.collect()

    def test_module_considers_pluginmanager_at_import(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol("testrunner_plugins='xasdlkj',")
        with testrunner.raises(UsageError):
            modcol.obj()

    def test_invalid_test_module_name(self, testrunnerer: Testrunnerer) -> None:
        a = testrunnerer.mkdir("a")
        a.joinpath("test_one.part1.py").touch()
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "ImportError while importing test module*test_one.part1*",
                "Hint: make sure your test modules/packages have valid Python names.",
            ]
        )

    @testrunner.mark.parametrize("verbose", [0, 1, 2])
    def test_show_traceback_import_error(
        self, testrunnerer: Testrunnerer, verbose: int
    ) -> None:
        """Import errors when collecting modules should display the traceback (#1976).

        With low verbosity we omit testrunner and internal modules, otherwise show all traceback entries.
        """
        testrunnerer.makepyfile(
            foo_traceback_import_error="""
               from bar_traceback_import_error import NOT_AVAILABLE
           """,
            bar_traceback_import_error="",
        )
        testrunnerer.makepyfile(
            """
               import foo_traceback_import_error
        """
        )
        args = ("-v",) * verbose
        result = testrunnerer.runtestrunner(*args)
        result.stdout.fnmatch_lines(
            [
                "ImportError while importing test module*",
                "Traceback:",
                "*from bar_traceback_import_error import NOT_AVAILABLE",
                "*cannot import name *NOT_AVAILABLE*",
            ]
        )
        assert result.ret == 2

        stdout = result.stdout.str()
        if verbose == 2:
            assert "_testrunner" in stdout
        else:
            assert "_testrunner" not in stdout

    def test_show_traceback_import_error_unicode(self, testrunnerer: Testrunnerer) -> None:
        """Check test modules collected which raise ImportError with unicode messages
        are handled properly (#2336).
        """
        testrunnerer.makepyfile("raise ImportError('Something bad happened ☺')")
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "ImportError while importing test module*",
                "Traceback:",
                "*raise ImportError*Something bad happened*",
            ]
        )
        assert result.ret == 2


class TestClass:
    def test_class_with_init_warning(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            class TestClass1(object):
                def __init__(self):
                    pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "*cannot collect test class 'TestClass1' because it has "
                "a __init__ constructor (from: test_class_with_init_warning.py)"
            ]
        )

    def test_class_with_new_warning(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            class TestClass1(object):
                def __new__(self):
                    pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "*cannot collect test class 'TestClass1' because it has "
                "a __new__ constructor (from: test_class_with_new_warning.py)"
            ]
        )

    def test_class_subclassobject(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.getmodulecol(
            """
            class test(object):
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*collected 0*"])

    def test_static_method(self, testrunnerer: Testrunnerer) -> None:
        """Support for collecting staticmethod tests (#2528, #2699)"""
        testrunnerer.getmodulecol(
            """
            import testrunner
            class Test(object):
                @staticmethod
                def test_something():
                    pass

                @testrunner.fixture
                def fix(self):
                    return 1

                @staticmethod
                def test_fix(fix):
                    assert fix == 1
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*collected 2 items*", "*2 passed in*"])

    def test_setup_teardown_class_as_classmethod(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            test_mod1="""
            class TestClassMethod(object):
                @classmethod
                def setup_class(cls):
                    pass
                def test_1(self):
                    pass
                @classmethod
                def teardown_class(cls):
                    pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_issue1035_obj_has_getattr(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol(
            """
            class Chameleon(object):
                def __getattr__(self, name):
                    return True
            chameleon = Chameleon()
        """
        )
        colitems = modcol.collect()
        assert len(colitems) == 0

    def test_issue1579_namedtuple(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import collections

            TestCase = collections.namedtuple('TestCase', ['a'])
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            "*cannot collect test class 'TestCase' "
            "because it has a __new__ constructor*"
        )

    def test_issue2234_property(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            class TestCase(object):
                @property
                def prop(self):
                    raise NotImplementedError()
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.NO_TESTS_COLLECTED

    def test_does_not_discover_properties(self, testrunnerer: Testrunnerer) -> None:
        """Regression test for #12446."""
        testrunnerer.makepyfile(
            """\
            class TestCase:
                @property
                def oops(self):
                    raise SystemExit('do not call me!')
            """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.NO_TESTS_COLLECTED

    def test_does_not_discover_instance_descriptors(self, testrunnerer: Testrunnerer) -> None:
        """Regression test for #12446."""
        testrunnerer.makepyfile(
            """\
            # not `@property`, but it acts like one
            # this should cover the case of things like `@cached_property` / etc.
            class MyProperty:
                def __init__(self, func):
                    self._func = func
                def __get__(self, inst, owner):
                    if inst is None:
                        return self
                    else:
                        return self._func.__get__(inst, owner)()

            class TestCase:
                @MyProperty
                def oops(self):
                    raise SystemExit('do not call me!')
            """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.NO_TESTS_COLLECTED

    def test_does_not_eval_properties_when_collecting_tests(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Regression test for #2568.

        Properties on a test class must only be evaluated when a test accesses
        them, not during collection or fixture parsing.
        """
        testrunnerer.makepyfile(
            """\
            calls = []

            class TestCase:
                @property
                def prop(self):
                    calls.append(1)
                    return len(calls)

                def test_prop(self):
                    assert self.prop == 1
            """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=1)

    def test_abstract_class_is_not_collected(self, testrunnerer: Testrunnerer) -> None:
        """Regression test for #12275 (non-unittest version)."""
        testrunnerer.makepyfile(
            """
            import abc

            class TestBase(abc.ABC):
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


class TestFunction:
    def test_getmodulecollector(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem("def test_func(): pass")
        modcol = item.getparent(testrunner.Module)
        assert isinstance(modcol, testrunner.Module)
        assert hasattr(modcol.obj, "test_func")

    @testrunner.mark.filterwarnings("default")
    def test_function_as_object_instance_ignored(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            class A(object):
                def __call__(self, tmp_path):
                    0/0

            test_a = A()
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "collected 0 items",
                "*test_function_as_object_instance_ignored.py:2: "
                "*cannot collect 'test_a' because it is not a function.",
            ]
        )

    @staticmethod
    def make_function(testrunnerer: Testrunnerer, **kwargs: Any) -> Any:
        from _testrunner.fixtures import FixtureManager

        config = testrunnerer.parseconfigure()
        session = Session.from_config(config)
        session._fixturemanager = FixtureManager(session)

        return testrunner.Function.from_parent(parent=session, **kwargs)

    def test_function_equality(self, testrunnerer: Testrunnerer) -> None:
        def func1():
            pass

        def func2():
            pass

        f1 = self.make_function(testrunnerer, name="name", callobj=func1)
        assert f1 == f1
        f2 = self.make_function(
            testrunnerer, name="name", callobj=func2, originalname="foobar"
        )
        assert f1 != f2

    def test_repr_produces_actual_test_id(self, testrunnerer: Testrunnerer) -> None:
        f = self.make_function(
            testrunnerer, name=r"test[\xe5]", callobj=self.test_repr_produces_actual_test_id
        )
        assert repr(f) == r"<Function test[\xe5]>"

    def test_issue197_parametrize_emptyset(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.parametrize('arg', [])
            def test_function(arg):
                pass
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(skipped=1)

    def test_single_tuple_unwraps_values(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.parametrize(('arg',), [(1,)])
            def test_function(arg):
                assert arg == 1
        """
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_issue213_parametrize_value_no_equal(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            class A(object):
                def __eq__(self, other):
                    raise ValueError("not possible")
            @testrunner.mark.parametrize('arg', [A()])
            def test_function(arg):
                assert arg.__class__.__name__ == "A"
        """
        )
        reprec = testrunnerer.inline_run("--fulltrace")
        reprec.assertoutcome(passed=1)

    def test_parametrize_with_non_hashable_values(self, testrunnerer: Testrunnerer) -> None:
        """Test parametrization with non-hashable values."""
        testrunnerer.makepyfile(
            """
            archival_mapping = {
                '1.0': {'tag': '1.0'},
                '1.2.2a1': {'tag': 'release-1.2.2a1'},
            }

            import testrunner
            @testrunner.mark.parametrize('key value'.split(),
                                     archival_mapping.items())
            def test_archival_to_version(key, value):
                assert key in archival_mapping
                assert value == archival_mapping[key]
        """
        )
        rec = testrunnerer.inline_run()
        rec.assertoutcome(passed=2)

    def test_parametrize_with_non_hashable_values_indirect(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test parametrization with non-hashable values with indirect parametrization."""
        testrunnerer.makepyfile(
            """
            archival_mapping = {
                '1.0': {'tag': '1.0'},
                '1.2.2a1': {'tag': 'release-1.2.2a1'},
            }

            import testrunner

            @testrunner.fixture
            def key(request):
                return request.param

            @testrunner.fixture
            def value(request):
                return request.param

            @testrunner.mark.parametrize('key value'.split(),
                                     archival_mapping.items(), indirect=True)
            def test_archival_to_version(key, value):
                assert key in archival_mapping
                assert value == archival_mapping[key]
        """
        )
        rec = testrunnerer.inline_run()
        rec.assertoutcome(passed=2)

    def test_parametrize_overrides_fixture(self, testrunnerer: Testrunnerer) -> None:
        """Test parametrization when parameter overrides existing fixture with same name."""
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture
            def value():
                return 'value'

            @testrunner.mark.parametrize('value',
                                     ['overridden'])
            def test_overridden_via_param(value):
                assert value == 'overridden'

            @testrunner.mark.parametrize('somevalue', ['overridden'])
            def test_not_overridden(value, somevalue):
                assert value == 'value'
                assert somevalue == 'overridden'

            @testrunner.mark.parametrize('other,value', [('foo', 'overridden')])
            def test_overridden_via_multiparam(other, value):
                assert other == 'foo'
                assert value == 'overridden'
        """
        )
        rec = testrunnerer.inline_run()
        rec.assertoutcome(passed=3)

    def test_parametrize_overrides_parametrized_fixture(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test parametrization when parameter overrides existing parametrized fixture with same name."""
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=[1, 2])
            def value(request):
                return request.param

            @testrunner.mark.parametrize('value',
                                     ['overridden'])
            def test_overridden_via_param(value):
                assert value == 'overridden'
        """
        )
        rec = testrunnerer.inline_run()
        rec.assertoutcome(passed=1)

    def test_parametrize_overrides_parametrized_fixture_with_unrelated_indirect(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test parametrization when parameter overrides existing parametrized fixture with same name,
        and there is an unrelated indirect param.

        Regression test for #13974.
        """
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture(params=["a", "b"])
            def target(request):
                return request.param

            @testrunner.fixture
            def val(request):
                return int(request.param)

            @testrunner.mark.parametrize(
                ["val", "target"],
                [
                    ("1", 1),
                    ("2", 2),
                ],
                indirect=["val"],
            )
            def test(val, target):
                assert val == target
            """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == 0
        result.assert_outcomes(passed=2)

    def test_parametrize_overrides_indirect_dependency_fixture(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test parametrization when parameter overrides a fixture that a test indirectly depends on"""
        testrunnerer.makepyfile(
            """
            import testrunner

            fix3_instantiated = False

            @testrunner.fixture
            def fix1(fix2):
               return fix2 + '1'

            @testrunner.fixture
            def fix2(fix3):
               return fix3 + '2'

            @testrunner.fixture
            def fix3():
               global fix3_instantiated
               fix3_instantiated = True
               return '3'

            @testrunner.mark.parametrize('fix2', ['2'])
            def test_it(fix1):
               assert fix1 == '21'
               assert not fix3_instantiated
        """
        )
        rec = testrunnerer.inline_run()
        rec.assertoutcome(passed=1)

    def test_parametrize_with_mark(self, testrunnerer: Testrunnerer) -> None:
        items = testrunnerer.getitems(
            """
            import testrunner
            @testrunner.mark.foo
            @testrunner.mark.parametrize('arg', [
                1,
                testrunner.param(2, marks=[testrunner.mark.baz, testrunner.mark.bar])
            ])
            def test_function(arg):
                pass
        """
        )
        keywords = [item.keywords for item in items]
        assert (
            "foo" in keywords[0]
            and "bar" not in keywords[0]
            and "baz" not in keywords[0]
        )
        assert "foo" in keywords[1] and "bar" in keywords[1] and "baz" in keywords[1]

    def test_parametrize_with_empty_string_arguments(self, testrunnerer: Testrunnerer) -> None:
        items = testrunnerer.getitems(
            """\
            import testrunner

            @testrunner.mark.parametrize('v', ('', ' '))
            @testrunner.mark.parametrize('w', ('', ' '))
            def test(v, w): ...
            """
        )
        names = {item.name for item in items}
        assert names == {"test[-]", "test[ -]", "test[- ]", "test[ - ]"}

    def test_function_equality_with_callspec(self, testrunnerer: Testrunnerer) -> None:
        items = testrunnerer.getitems(
            """
            import testrunner
            @testrunner.mark.parametrize('arg', [1,2])
            def test_function(arg):
                pass
        """
        )
        assert items[0] != items[1]
        assert not (items[0] == items[1])

    def test_pyfunc_call(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem("def test_func(): raise ValueError")
        config = item.config

        class MyPlugin1:
            def testrunner_pyfunc_call(self):
                raise ValueError

        class MyPlugin2:
            def testrunner_pyfunc_call(self):
                return True

        config.pluginmanager.register(MyPlugin1())
        config.pluginmanager.register(MyPlugin2())
        config.hook.testrunner_runtest_setup(item=item)
        config.hook.testrunner_pyfunc_call(pyfuncitem=item)

    def test_multiple_parametrize(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol(
            """
            import testrunner
            @testrunner.mark.parametrize('x', [0, 1])
            @testrunner.mark.parametrize('y', [2, 3])
            def test1(x, y):
                pass
        """
        )
        colitems = modcol.collect()
        assert colitems[0].name == "test1[2-0]"
        assert colitems[1].name == "test1[2-1]"
        assert colitems[2].name == "test1[3-0]"
        assert colitems[3].name == "test1[3-1]"

    def test_issue751_multiple_parametrize_with_ids(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol(
            """
            import testrunner
            @testrunner.mark.parametrize('x', [0], ids=['c'])
            @testrunner.mark.parametrize('y', [0, 1], ids=['a', 'b'])
            class Test(object):
                def test1(self, x, y):
                    pass
                def test2(self, x, y):
                    pass
        """
        )
        colitems = modcol.collect()[0].collect()
        assert colitems[0].name == "test1[a-c]"
        assert colitems[1].name == "test1[b-c]"
        assert colitems[2].name == "test2[a-c]"
        assert colitems[3].name == "test2[b-c]"

    def test_parametrize_skipif(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            m = testrunner.mark.skipif('True')

            @testrunner.mark.parametrize('x', [0, 1, testrunner.param(2, marks=m)])
            def test_skip_if(x):
                assert x < 2
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["* 2 passed, 1 skipped in *"])

    def test_parametrize_skip(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            m = testrunner.mark.skip('')

            @testrunner.mark.parametrize('x', [0, 1, testrunner.param(2, marks=m)])
            def test_skip(x):
                assert x < 2
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["* 2 passed, 1 skipped in *"])

    def test_parametrize_skipif_no_skip(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            m = testrunner.mark.skipif('False')

            @testrunner.mark.parametrize('x', [0, 1, m(2)])
            def test_skipif_no_skip(x):
                assert x < 2
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["* 1 failed, 2 passed in *"])

    def test_parametrize_xfail(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            m = testrunner.mark.xfail('True')

            @testrunner.mark.parametrize('x', [0, 1, testrunner.param(2, marks=m)])
            def test_xfail(x):
                assert x < 2
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["* 2 passed, 1 xfailed in *"])

    def test_parametrize_passed(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            m = testrunner.mark.xfail('True')

            @testrunner.mark.parametrize('x', [0, 1, testrunner.param(2, marks=m)])
            def test_xfail(x):
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["* 2 passed, 1 xpassed in *"])

    def test_parametrize_xfail_passed(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner

            m = testrunner.mark.xfail('False')

            @testrunner.mark.parametrize('x', [0, 1, m(2)])
            def test_passed(x):
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["* 3 passed in *"])

    def test_function_originalname(self, testrunnerer: Testrunnerer) -> None:
        items = testrunnerer.getitems(
            """
            import testrunner

            @testrunner.mark.parametrize('arg', [1,2])
            def test_func(arg):
                pass

            def test_no_param():
                pass
        """
        )
        originalnames = []
        for x in items:
            assert isinstance(x, testrunner.Function)
            originalnames.append(x.originalname)
        assert originalnames == [
            "test_func",
            "test_func",
            "test_no_param",
        ]

    def test_function_with_square_brackets(self, testrunnerer: Testrunnerer) -> None:
        """Check that functions with square brackets don't cause trouble."""
        p1 = testrunnerer.makepyfile(
            """
            locals()["test_foo[name]"] = lambda: None
            """
        )
        result = testrunnerer.runtestrunner("-v", str(p1))
        result.stdout.fnmatch_lines(
            [
                "test_function_with_square_brackets.py::test_foo[[]name[]] PASSED *",
                "*= 1 passed in *",
            ]
        )


class TestSorting:
    def test_check_equality(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol(
            """
            def test_pass(): pass
            def test_fail(): assert 0
        """
        )
        fn1 = testrunnerer.collect_by_name(modcol, "test_pass")
        assert isinstance(fn1, testrunner.Function)
        fn2 = testrunnerer.collect_by_name(modcol, "test_pass")
        assert isinstance(fn2, testrunner.Function)

        assert fn1 == fn2
        assert fn1 != modcol
        assert hash(fn1) == hash(fn2)

        fn3 = testrunnerer.collect_by_name(modcol, "test_fail")
        assert isinstance(fn3, testrunner.Function)
        assert not (fn1 == fn3)
        assert fn1 != fn3

        for fn in fn1, fn2, fn3:
            assert fn != 3  # type: ignore[comparison-overlap]
            assert fn != modcol
            assert fn != [1, 2, 3]  # type: ignore[comparison-overlap]
            assert [1, 2, 3] != fn  # type: ignore[comparison-overlap]
            assert modcol != fn

    def test_allow_sane_sorting_for_decorators(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol(
            """
            def dec(f):
                g = lambda: f(2)
                g.place_as = f
                return g


            def test_b(y):
                pass
            test_b = dec(test_b)

            def test_a(y):
                pass
            test_a = dec(test_a)
        """
        )
        colitems = modcol.collect()
        assert len(colitems) == 2
        assert [item.name for item in colitems] == ["test_b", "test_a"]

    def test_ordered_by_definition_order(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """\
            class Test1:
                def test_foo(self): pass
                def test_bar(self): pass
            class Test2:
                def test_foo(self): pass
                test_bar = Test1.test_bar
            class Test3(Test2):
                def test_baz(self): pass
            """
        )
        result = testrunnerer.runtestrunner("--collect-only")
        result.stdout.fnmatch_lines(
            [
                "*Class Test1*",
                "*Function test_foo*",
                "*Function test_bar*",
                "*Class Test2*",
                # previously the order was flipped due to Test1.test_bar reference
                "*Function test_foo*",
                "*Function test_bar*",
                "*Class Test3*",
                "*Function test_foo*",
                "*Function test_bar*",
                "*Function test_baz*",
            ]
        )


class TestConftestCustomization:
    def test_testrunner_pycollect_module(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            class MyModule(testrunner.Module):
                pass
            def testrunner_pycollect_makemodule(module_path, parent):
                if module_path.name == "test_xyz.py":
                    return MyModule.from_parent(path=module_path, parent=parent)
        """
        )
        testrunnerer.makepyfile("def test_some(): pass")
        testrunnerer.makepyfile(test_xyz="def test_func(): pass")
        result = testrunnerer.runtestrunner("--collect-only")
        result.stdout.fnmatch_lines(["*<Module*test_testrunner*", "*<MyModule*xyz*"])

    def test_customized_pymakemodule_issue205_subdir(self, testrunnerer: Testrunnerer) -> None:
        b = testrunnerer.path.joinpath("a", "b")
        b.mkdir(parents=True)
        b.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner
                @testrunner.hookimpl(wrapper=True)
                def testrunner_pycollect_makemodule():
                    mod = yield
                    mod.obj.hello = "world"
                    return mod
                """
            ),
            encoding="utf-8",
        )
        b.joinpath("test_module.py").write_text(
            textwrap.dedent(
                """\
                def test_hello():
                    assert hello == "world"
                """
            ),
            encoding="utf-8",
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_customized_pymakeitem(self, testrunnerer: Testrunnerer) -> None:
        b = testrunnerer.path.joinpath("a", "b")
        b.mkdir(parents=True)
        b.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner
                @testrunner.hookimpl(wrapper=True)
                def testrunner_pycollect_makeitem():
                    result = yield
                    if result:
                        for func in result:
                            func._some123 = "world"
                    return result
                """
            ),
            encoding="utf-8",
        )
        b.joinpath("test_module.py").write_text(
            textwrap.dedent(
                """\
                import testrunner

                @testrunner.fixture()
                def obj(request):
                    return request.node._some123
                def test_hello(obj):
                    assert obj == "world"
                """
            ),
            encoding="utf-8",
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=1)

    def test_testrunner_pycollect_makeitem(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            class MyFunction(testrunner.Function):
                pass
            def testrunner_pycollect_makeitem(collector, name, obj):
                if name == "some":
                    return MyFunction.from_parent(name=name, parent=collector)
        """
        )
        testrunnerer.makepyfile("def some(): pass")
        result = testrunnerer.runtestrunner("--collect-only")
        result.stdout.fnmatch_lines(["*MyFunction*some*"])

    def test_issue2369_collect_module_fileext(self, testrunnerer: Testrunnerer) -> None:
        """Ensure we can collect files with weird file extensions as Python
        modules (#2369)"""
        # Implement a little meta path finder to import files containing
        # Python source code whose file extension is ".narf".
        testrunnerer.makeconftest(
            """
            import sys
            import os.path
            from importlib.util import spec_from_loader
            from importlib.machinery import SourceFileLoader
            from _testrunner.python import Module

            class MetaPathFinder:
                def find_spec(self, fullname, path, target=None):
                    if os.path.exists(fullname + ".narf"):
                        return spec_from_loader(
                            fullname,
                            SourceFileLoader(fullname, fullname + ".narf"),
                        )
            sys.meta_path.append(MetaPathFinder())

            def testrunner_collect_file(file_path, parent):
                if file_path.suffix == ".narf":
                    return Module.from_parent(path=file_path, parent=parent)
            """
        )
        testrunnerer.makefile(
            ".narf",
            """\
            def test_something():
                assert 1 + 1 == 2""",
        )
        # Use runtestrunner_subprocess, since we're futzing with sys.meta_path.
        result = testrunnerer.runtestrunner_subprocess()
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_early_ignored_attributes(self, testrunnerer: Testrunnerer) -> None:
        """Builtin attributes should be ignored early on, even if
        configuration would otherwise allow them.

        This tests a performance optimization, not correctness, really,
        although it tests TestrunnerCollectionWarning is not raised, while
        it would have been raised otherwise.
        """
        testrunnerer.makeini(
            """
            [testrunner]
            python_classes=*
            python_functions=*
        """
        )
        testrunnerer.makepyfile(
            """
            class TestEmpty:
                pass
            test_empty = TestEmpty()
            def test_real():
                pass
        """
        )
        items, rec = testrunnerer.inline_genitems()
        assert rec.ret == 0
        assert len(items) == 1


def test_setup_only_available_in_subdir(testrunnerer: Testrunnerer) -> None:
    sub1 = testrunnerer.mkpydir("sub1")
    sub2 = testrunnerer.mkpydir("sub2")
    sub1.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            import testrunner
            def testrunner_runtest_setup(item):
                assert item.path.stem == "test_in_sub1"
            def testrunner_runtest_call(item):
                assert item.path.stem == "test_in_sub1"
            def testrunner_runtest_teardown(item):
                assert item.path.stem == "test_in_sub1"
            """
        ),
        encoding="utf-8",
    )
    sub2.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            import testrunner
            def testrunner_runtest_setup(item):
                assert item.path.stem == "test_in_sub2"
            def testrunner_runtest_call(item):
                assert item.path.stem == "test_in_sub2"
            def testrunner_runtest_teardown(item):
                assert item.path.stem == "test_in_sub2"
            """
        ),
        encoding="utf-8",
    )
    sub1.joinpath("test_in_sub1.py").write_text("def test_1(): pass", encoding="utf-8")
    sub2.joinpath("test_in_sub2.py").write_text("def test_2(): pass", encoding="utf-8")
    result = testrunnerer.runtestrunner("-v", "-s")
    result.assert_outcomes(passed=2)


def test_modulecol_roundtrip(testrunnerer: Testrunnerer) -> None:
    modcol = testrunnerer.getmodulecol("pass", withinit=False)
    trail = modcol.nodeid
    newcol = modcol.session.perform_collect([trail], genitems=0)[0]
    assert modcol.name == newcol.name


class TestTracebackCutting:
    def test_skip_simple(self):
        with testrunner.raises(testrunner.skip.Exception) as excinfo:
            testrunner.skip("xxx")
        if sys.version_info >= (3, 11):
            assert excinfo.traceback[-1].frame.code.raw.co_qualname == "_Skip.__call__"
        assert excinfo.traceback[-1].ishidden(excinfo)
        assert excinfo.traceback[-2].frame.code.name == "test_skip_simple"
        assert not excinfo.traceback[-2].ishidden(excinfo)

    def test_traceback_argsetup(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture
            def hello(request):
                raise ValueError("xyz")
        """
        )
        p = testrunnerer.makepyfile("def test(hello): pass")
        result = testrunnerer.runtestrunner(p)
        assert result.ret != 0
        out = result.stdout.str()
        assert "xyz" in out
        assert "conftest.py:5: ValueError" in out
        numentries = out.count("_ _ _")  # separator for traceback entries
        assert numentries == 0

        result = testrunnerer.runtestrunner("--fulltrace", p)
        out = result.stdout.str()
        assert "conftest.py:5: ValueError" in out
        numentries = out.count("_ _ _ _")  # separator for traceback entries
        assert numentries > 3

    def test_traceback_error_during_import(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            x = 1
            x = 2
            x = 17
            asd
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        out = result.stdout.str()
        assert "x = 1" not in out
        assert "x = 2" not in out
        result.stdout.fnmatch_lines([" *asd*", "E*NameError*"])
        result = testrunnerer.runtestrunner("--fulltrace")
        out = result.stdout.str()
        assert "x = 1" in out
        assert "x = 2" in out
        result.stdout.fnmatch_lines([">*asd*", "E*NameError*"])

    def test_traceback_filter_error_during_fixture_collection(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Integration test for issue #995."""
        testrunnerer.makepyfile(
            """
            import testrunner

            def fail_me(func):
                ns = {}
                exec('def w(): raise ValueError("fail me")', ns)
                return ns['w']

            @testrunner.fixture(scope='class')
            @fail_me
            def fail_fixture():
                pass

            def test_failing_fixture(fail_fixture):
               pass
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        out = result.stdout.str()
        assert "INTERNALERROR>" not in out
        result.stdout.fnmatch_lines(["*ValueError: fail me*", "* 1 error in *"])

    def test_filter_traceback_generated_code(self) -> None:
        """Test that filter_traceback() works with the fact that
        _testrunner._code.code.Code.path attribute might return an str object.

        In this case, one of the entries on the traceback was produced by
        dynamically generated code.
        See: https://bitbucket.org/testrunner-dev/py/issues/71
        This fixes #995.
        """
        from _testrunner._code import filter_traceback

        tb = None
        try:
            ns: dict[str, Any] = {}
            exec("def foo(): raise ValueError", ns)
            ns["foo"]()
        except ValueError:
            _, _, tb = sys.exc_info()

        assert tb is not None
        traceback = _testrunner._code.Traceback(tb)
        assert isinstance(traceback[-1].path, str)
        assert not filter_traceback(traceback[-1])

    def test_filter_traceback_path_no_longer_valid(self, testrunnerer: Testrunnerer) -> None:
        """Test that filter_traceback() works with the fact that
        _testrunner._code.code.Code.path attribute might return an str object.

        In this case, one of the files in the traceback no longer exists.
        This fixes #1133.
        """
        from _testrunner._code import filter_traceback

        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(
            filter_traceback_entry_as_str="""
            def foo():
                raise ValueError
        """
        )
        tb = None
        try:
            import filter_traceback_entry_as_str

            filter_traceback_entry_as_str.foo()
        except ValueError:
            _, _, tb = sys.exc_info()

        assert tb is not None
        testrunnerer.path.joinpath("filter_traceback_entry_as_str.py").unlink()
        traceback = _testrunner._code.Traceback(tb)
        assert isinstance(traceback[-1].path, str)
        assert filter_traceback(traceback[-1])


class TestReportInfo:
    def test_itemreport_reportinfo(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            class MyFunction(testrunner.Function):
                def reportinfo(self):
                    return "ABCDE", 42, "custom"
            def testrunner_pycollect_makeitem(collector, name, obj):
                if name == "test_func":
                    return MyFunction.from_parent(name=name, parent=collector)
        """
        )
        item = testrunnerer.getitem("def test_func(): pass")
        item.config.pluginmanager.getplugin("runner")
        assert item.location == ("ABCDE", 42, "custom")

    def test_func_reportinfo(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem("def test_func(): pass")
        path, lineno, modpath = item.reportinfo()
        assert os.fspath(path) == str(item.path)
        assert lineno == 0
        assert modpath == "test_func"

    def test_class_reportinfo(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol(
            """
            # lineno 0
            class TestClass(object):
                def test_hello(self): pass
        """
        )
        classcol = testrunnerer.collect_by_name(modcol, "TestClass")
        assert isinstance(classcol, Class)
        path, lineno, msg = classcol.reportinfo()
        assert os.fspath(path) == str(modcol.path)
        assert lineno == 1
        assert msg == "TestClass"

    @testrunner.mark.filterwarnings(
        "ignore:usage of Generator.Function is deprecated, please use testrunner.Function instead"
    )
    def test_reportinfo_with_nasty_getattr(self, testrunnerer: Testrunnerer) -> None:
        # https://github.com/jacksonsr451/test-runner/issues/1204
        modcol = testrunnerer.getmodulecol(
            """
            # lineno 0
            class TestClass:
                def __getattr__(self, name):
                    return "this is not an int"

                def __class_getattr__(cls, name):
                    return "this is not an int"

                def intest_foo(self):
                    pass

                def test_bar(self):
                    pass
        """
        )
        classcol = testrunnerer.collect_by_name(modcol, "TestClass")
        assert isinstance(classcol, Class)
        _path, _lineno, _msg = classcol.reportinfo()
        func = next(iter(classcol.collect()))
        assert isinstance(func, Function)
        _path, _lineno, _msg = func.reportinfo()


def test_customized_python_discovery(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeini(
        """
        [testrunner]
        python_files=check_*.py
        python_classes=Check
        python_functions=check
    """
    )
    p = testrunnerer.makepyfile(
        """
        def check_simple():
            pass
        class CheckMyApp(object):
            def check_meth(self):
                pass
    """
    )
    p2 = p.with_name(p.name.replace("test", "check"))
    p.rename(p2)
    result = testrunnerer.runtestrunner("--collect-only", "-s")
    result.stdout.fnmatch_lines(
        ["*check_customized*", "*check_simple*", "*CheckMyApp*", "*check_meth*"]
    )

    result = testrunnerer.runtestrunner()
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*2 passed*"])


def test_customized_python_discovery_functions(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeini(
        """
        [testrunner]
        python_functions=_test
    """
    )
    testrunnerer.makepyfile(
        """
        def _test_underscore():
            pass
    """
    )
    result = testrunnerer.runtestrunner("--collect-only", "-s")
    result.stdout.fnmatch_lines(["*_test_underscore*"])

    result = testrunnerer.runtestrunner()
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*1 passed*"])


def test_unorderable_types(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        class TestJoinEmpty(object):
            pass

        def make_test():
            class Test(object):
                pass
            Test.__name__ = "TestFoo"
            return Test
        TestFoo = make_test()
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.no_fnmatch_line("*TypeError*")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


@testrunner.mark.filterwarnings("default::testrunner.TestrunnerCollectionWarning")
def test_dont_collect_non_function_callable(testrunnerer: Testrunnerer) -> None:
    """Test for issue https://github.com/jacksonsr451/test-runner/issues/331

    In this case an INTERNALERROR occurred trying to report the failure of
    a test like this one because testrunner failed to get the source lines.
    """
    testrunnerer.makepyfile(
        """
        class Oh(object):
            def __call__(self):
                pass

        test_a = Oh()

        def test_real():
            pass
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            "*collected 1 item*",
            "*test_dont_collect_non_function_callable.py:2: *cannot collect 'test_a' because it is not a function*",
            "*1 passed, 1 warning in *",
        ]
    )


def test_class_injection_does_not_break_collection(testrunnerer: Testrunnerer) -> None:
    """Tests whether injection during collection time will terminate testing.

    In this case the error should not occur if the TestClass itself
    is modified during collection time, and the original method list
    is still used for collection.
    """
    testrunnerer.makeconftest(
        """
        from test_inject import TestClass
        def testrunner_generate_tests(metafunc):
            TestClass.changed_var = {}
    """
    )
    testrunnerer.makepyfile(
        test_inject='''
         class TestClass(object):
            def test_injection(self):
                """Test being parametrized."""
                pass
    '''
    )
    result = testrunnerer.runtestrunner()
    assert (
        "RuntimeError: dictionary changed size during iteration"
        not in result.stdout.str()
    )
    result.stdout.fnmatch_lines(["*1 passed*"])


def test_syntax_error_with_non_ascii_chars(testrunnerer: Testrunnerer) -> None:
    """Fix decoding issue while formatting SyntaxErrors during collection (#578)."""
    testrunnerer.makepyfile("☃")
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*ERROR collecting*", "*SyntaxError*", "*1 error in*"])


def test_collect_error_with_fulltrace(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile("assert 0")
    result = testrunnerer.runtestrunner("--fulltrace")
    result.stdout.fnmatch_lines(
        [
            "collected 0 items / 1 error",
            "",
            "*= ERRORS =*",
            "*_ ERROR collecting test_collect_error_with_fulltrace.py _*",
            "",
            ">   assert 0",
            "E   assert 0",
            "",
            "test_collect_error_with_fulltrace.py:1: AssertionError",
            "*! Interrupted: 1 error during collection !*",
        ]
    )


def test_skip_duplicates_by_default(testrunnerer: Testrunnerer) -> None:
    """Test for issue https://github.com/jacksonsr451/test-runner/issues/1609 (#1609)

    Ignore duplicate directories.
    """
    a = testrunnerer.mkdir("a")
    fh = a.joinpath("test_a.py")
    fh.write_text(
        textwrap.dedent(
            """\
            import testrunner
            def test_real():
                pass
            """
        ),
        encoding="utf-8",
    )
    result = testrunnerer.runtestrunner(str(a), str(a))
    result.stdout.fnmatch_lines(["*collected 1 item*"])


def test_keep_duplicates(testrunnerer: Testrunnerer) -> None:
    """Test for issue https://github.com/jacksonsr451/test-runner/issues/1609 (#1609)

    Use --keep-duplicates to collect tests from duplicate directories.
    """
    a = testrunnerer.mkdir("a")
    fh = a.joinpath("test_a.py")
    fh.write_text(
        textwrap.dedent(
            """\
            import testrunner
            def test_real():
                pass
            """
        ),
        encoding="utf-8",
    )
    result = testrunnerer.runtestrunner("--keep-duplicates", str(a), str(a))
    result.stdout.fnmatch_lines(["*collected 2 item*"])


def test_package_collection_infinite_recursion(testrunnerer: Testrunnerer) -> None:
    testrunnerer.copy_example("collect/package_infinite_recursion")
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*1 passed*"])


def test_package_collection_init_given_as_argument(testrunnerer: Testrunnerer) -> None:
    """Regression test for #3749, #8976, #9263, #9313.

    Specifying an __init__.py file directly should collect only the __init__.py
    Module, not the entire package.
    """
    p = testrunnerer.copy_example("collect/package_init_given_as_arg")
    items, _hookrecorder = testrunnerer.inline_genitems(p / "pkg" / "__init__.py")
    assert len(items) == 1
    assert items[0].name == "test_init"


def test_package_with_modules(testrunnerer: Testrunnerer) -> None:
    """
    .
    └── root
        ├── __init__.py
        ├── sub1
        │   ├── __init__.py
        │   └── sub1_1
        │       ├── __init__.py
        │       └── test_in_sub1.py
        └── sub2
            └── test
                └── test_in_sub2.py

    """
    root = testrunnerer.mkpydir("root")
    sub1 = root.joinpath("sub1")
    sub1_test = sub1.joinpath("sub1_1")
    sub1_test.mkdir(parents=True)
    for d in (sub1, sub1_test):
        d.joinpath("__init__.py").touch()

    sub2 = root.joinpath("sub2")
    sub2_test = sub2.joinpath("test")
    sub2_test.mkdir(parents=True)

    sub1_test.joinpath("test_in_sub1.py").write_text(
        "def test_1(): pass", encoding="utf-8"
    )
    sub2_test.joinpath("test_in_sub2.py").write_text(
        "def test_2(): pass", encoding="utf-8"
    )

    # Execute from .
    result = testrunnerer.runtestrunner("-v", "-s")
    result.assert_outcomes(passed=2)

    # Execute from . with one argument "root"
    result = testrunnerer.runtestrunner("-v", "-s", "root")
    result.assert_outcomes(passed=2)

    # Chdir into package's root and execute with no args
    os.chdir(root)
    result = testrunnerer.runtestrunner("-v", "-s")
    result.assert_outcomes(passed=2)


def test_package_ordering(testrunnerer: Testrunnerer) -> None:
    """
    .
    └── root
        ├── Test_root.py
        ├── __init__.py
        ├── sub1
        │   ├── Test_sub1.py
        │   └── __init__.py
        └── sub2
            └── test
                └── test_sub2.py

    """
    testrunnerer.makeini(
        """
        [testrunner]
        python_files=*.py
    """
    )
    root = testrunnerer.mkpydir("root")
    sub1 = root.joinpath("sub1")
    sub1.mkdir()
    sub1.joinpath("__init__.py").touch()
    sub2 = root.joinpath("sub2")
    sub2_test = sub2.joinpath("test")
    sub2_test.mkdir(parents=True)

    root.joinpath("Test_root.py").write_text("def test_1(): pass", encoding="utf-8")
    sub1.joinpath("Test_sub1.py").write_text("def test_2(): pass", encoding="utf-8")
    sub2_test.joinpath("test_sub2.py").write_text(
        "def test_3(): pass", encoding="utf-8"
    )

    # Execute from .
    result = testrunnerer.runtestrunner("-v", "-s")
    result.assert_outcomes(passed=3)


def test_collection_hierarchy(testrunnerer: Testrunnerer) -> None:
    """A general test checking that a filesystem hierarchy is collected as
    expected in various scenarios.

    top/
    ├── aaa
    │   ├── pkg
    │   │   ├── __init__.py
    │   │   └── test_pkg.py
    │   └── test_aaa.py
    ├── test_a.py
    ├── test_b
    │   ├── __init__.py
    │   └── test_b.py
    ├── test_c.py
    └── zzz
        ├── dir
        │   └── test_dir.py
        ├── __init__.py
        └── test_zzz.py
    """
    testrunnerer.makepyfile(
        **{
            "top/aaa/test_aaa.py": "def test_it(): pass",
            "top/aaa/pkg/__init__.py": "",
            "top/aaa/pkg/test_pkg.py": "def test_it(): pass",
            "top/test_a.py": "def test_it(): pass",
            "top/test_b/__init__.py": "",
            "top/test_b/test_b.py": "def test_it(): pass",
            "top/test_c.py": "def test_it(): pass",
            "top/zzz/__init__.py": "",
            "top/zzz/test_zzz.py": "def test_it(): pass",
            "top/zzz/dir/test_dir.py": "def test_it(): pass",
        }
    )

    full = [
        "<Dir test_collection_hierarchy*>",
        "  <Dir top>",
        "    <Dir aaa>",
        "      <Package pkg>",
        "        <Module test_pkg.py>",
        "          <Function test_it>",
        "      <Module test_aaa.py>",
        "        <Function test_it>",
        "    <Module test_a.py>",
        "      <Function test_it>",
        "    <Package test_b>",
        "      <Module test_b.py>",
        "        <Function test_it>",
        "    <Module test_c.py>",
        "      <Function test_it>",
        "    <Package zzz>",
        "      <Dir dir>",
        "        <Module test_dir.py>",
        "          <Function test_it>",
        "      <Module test_zzz.py>",
        "        <Function test_it>",
    ]
    result = testrunnerer.runtestrunner("--collect-only")
    result.stdout.fnmatch_lines(full, consecutive=True)
    result = testrunnerer.runtestrunner("top", "--collect-only")
    result.stdout.fnmatch_lines(full, consecutive=True)
    result = testrunnerer.runtestrunner("top", "top", "--collect-only")
    result.stdout.fnmatch_lines(full, consecutive=True)

    result = testrunnerer.runtestrunner(
        "top/aaa", "top/aaa/pkg", "--collect-only", "--keep-duplicates"
    )
    result.stdout.fnmatch_lines(
        [
            "<Dir test_collection_hierarchy*>",
            "  <Dir top>",
            "    <Dir aaa>",
            "      <Package pkg>",
            "        <Module test_pkg.py>",
            "          <Function test_it>",
            "      <Module test_aaa.py>",
            "        <Function test_it>",
            "      <Package pkg>",
            "        <Module test_pkg.py>",
            "          <Function test_it>",
        ],
        consecutive=True,
    )

    result = testrunnerer.runtestrunner(
        "top/aaa/pkg", "top/aaa", "--collect-only", "--keep-duplicates"
    )
    result.stdout.fnmatch_lines(
        [
            "<Dir test_collection_hierarchy*>",
            "  <Dir top>",
            "    <Dir aaa>",
            "      <Package pkg>",
            "        <Module test_pkg.py>",
            "          <Function test_it>",
            "          <Function test_it>",
            "      <Module test_aaa.py>",
            "        <Function test_it>",
        ],
        consecutive=True,
    )
