# mypy: allow-untyped-defs
from __future__ import annotations

import textwrap

from _testrunner._code import ExceptionInfo
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.runner import runtestprotocol
from _testrunner.skipping import evaluate_skip_marks
from _testrunner.skipping import evaluate_xfail_marks
from _testrunner.skipping import testrunner_runtest_setup
import testrunner


class TestEvaluation:
    def test_no_marker(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem("def test_func(): pass")
        skipped = evaluate_skip_marks(item)
        assert not skipped

    def test_marked_xfail_no_args(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.xfail
            def test_func():
                pass
        """
        )
        xfailed = evaluate_xfail_marks(item)
        assert xfailed
        assert xfailed.reason == ""
        assert xfailed.run

    def test_marked_skipif_no_args(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.skipif
            def test_func():
                pass
        """
        )
        skipped = evaluate_skip_marks(item)
        assert skipped
        assert skipped.reason == ""

    def test_marked_one_arg(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.skipif("hasattr(os, 'sep')")
            def test_func():
                pass
        """
        )
        skipped = evaluate_skip_marks(item)
        assert skipped
        assert skipped.reason == "condition: hasattr(os, 'sep')"

    def test_marked_one_arg_with_reason(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.skipif("hasattr(os, 'sep')", attr=2, reason="hello world")
            def test_func():
                pass
        """
        )
        skipped = evaluate_skip_marks(item)
        assert skipped
        assert skipped.reason == "hello world"

    def test_marked_one_arg_twice(self, testrunnerer: Testrunnerer) -> None:
        lines = [
            """@testrunner.mark.skipif("not hasattr(os, 'murks')")""",
            """@testrunner.mark.skipif(condition="hasattr(os, 'murks')")""",
        ]
        for i in range(2):
            item = testrunnerer.getitem(
                f"""
                import testrunner
                {lines[i]}
                {lines[(i + 1) % 2]}
                def test_func():
                    pass
            """
            )
            skipped = evaluate_skip_marks(item)
            assert skipped
            assert skipped.reason == "condition: not hasattr(os, 'murks')"

    def test_marked_one_arg_twice2(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.skipif("hasattr(os, 'murks')")
            @testrunner.mark.skipif("not hasattr(os, 'murks')")
            def test_func():
                pass
        """
        )
        skipped = evaluate_skip_marks(item)
        assert skipped
        assert skipped.reason == "condition: not hasattr(os, 'murks')"

    def test_marked_skipif_with_boolean_without_reason(
        self, testrunnerer: Testrunnerer
    ) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.skipif(False)
            def test_func():
                pass
        """
        )
        with testrunner.raises(testrunner.fail.Exception) as excinfo:
            evaluate_skip_marks(item)
        assert excinfo.value.msg is not None
        assert (
            """Error evaluating 'skipif': you need to specify reason=STRING when using booleans as conditions."""
            in excinfo.value.msg
        )

    def test_marked_skipif_with_invalid_boolean(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner

            class InvalidBool:
                def __bool__(self):
                    raise TypeError("INVALID")

            @testrunner.mark.skipif(InvalidBool(), reason="xxx")
            def test_func():
                pass
        """
        )
        with testrunner.raises(testrunner.fail.Exception) as excinfo:
            evaluate_skip_marks(item)
        assert excinfo.value.msg is not None
        assert "Error evaluating 'skipif' condition as a boolean" in excinfo.value.msg
        assert "INVALID" in excinfo.value.msg

    def test_skipif_class(self, testrunnerer: Testrunnerer) -> None:
        (item,) = testrunnerer.getitems(
            """
            import testrunner
            class TestClass(object):
                _testrunner_mark = testrunner.mark.skipif("config._hackxyz")
                def test_func(self):
                    pass
        """
        )
        item.config._hackxyz = 3  # type: ignore[attr-defined]
        skipped = evaluate_skip_marks(item)
        assert skipped
        assert skipped.reason == "condition: config._hackxyz"

    def test_skipif_markeval_namespace(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner

            def testrunner_markeval_namespace():
                return {"color": "green"}
            """
        )
        p = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.skipif("color == 'green'")
            def test_1():
                assert True

            @testrunner.mark.skipif("color == 'red'")
            def test_2():
                assert True
        """
        )
        res = testrunnerer.runtestrunner(p)
        assert res.ret == 0
        res.stdout.fnmatch_lines(["*1 skipped*"])
        res.stdout.fnmatch_lines(["*1 passed*"])

    def test_skipif_markeval_namespace_multiple(self, testrunnerer: Testrunnerer) -> None:
        """Keys defined by ``testrunner_markeval_namespace()`` in nested plugins override top-level ones."""
        root = testrunnerer.mkdir("root")
        root.joinpath("__init__.py").touch()
        root.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
            import testrunner

            def testrunner_markeval_namespace():
                return {"arg": "root"}
            """
            ),
            encoding="utf-8",
        )
        root.joinpath("test_root.py").write_text(
            textwrap.dedent(
                """\
            import testrunner

            @testrunner.mark.skipif("arg == 'root'")
            def test_root():
                assert False
            """
            ),
            encoding="utf-8",
        )
        foo = root.joinpath("foo")
        foo.mkdir()
        foo.joinpath("__init__.py").touch()
        foo.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
            import testrunner

            def testrunner_markeval_namespace():
                return {"arg": "foo"}
            """
            ),
            encoding="utf-8",
        )
        foo.joinpath("test_foo.py").write_text(
            textwrap.dedent(
                """\
            import testrunner

            @testrunner.mark.skipif("arg == 'foo'")
            def test_foo():
                assert False
            """
            ),
            encoding="utf-8",
        )
        bar = root.joinpath("bar")
        bar.mkdir()
        bar.joinpath("__init__.py").touch()
        bar.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
            import testrunner

            def testrunner_markeval_namespace():
                return {"arg": "bar"}
            """
            ),
            encoding="utf-8",
        )
        bar.joinpath("test_bar.py").write_text(
            textwrap.dedent(
                """\
            import testrunner

            @testrunner.mark.skipif("arg == 'bar'")
            def test_bar():
                assert False
            """
            ),
            encoding="utf-8",
        )

        reprec = testrunnerer.inline_run("-vs", "--capture=no")
        reprec.assertoutcome(skipped=3)

    def test_skipif_markeval_namespace_ValueError(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner

            def testrunner_markeval_namespace():
                return True
            """
        )
        p = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.skipif("color == 'green'")
            def test_1():
                assert True
        """
        )
        res = testrunnerer.runtestrunner(p)
        assert res.ret == 1
        res.stdout.fnmatch_lines(
            [
                "*ValueError: testrunner_markeval_namespace() needs to return a dict, got True*"
            ]
        )


class TestXFail:
    @testrunner.mark.parametrize("strict", [True, False])
    def test_xfail_simple(self, testrunnerer: Testrunnerer, strict: bool) -> None:
        item = testrunnerer.getitem(
            f"""
            import testrunner
            @testrunner.mark.xfail(strict={strict})
            def test_func():
                assert 0
        """
        )
        reports = runtestprotocol(item, log=False)
        assert len(reports) == 3
        callreport = reports[1]
        assert callreport.skipped
        assert callreport.wasxfail == ""

    def test_xfail_xpassed(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.xfail(reason="this is an xfail")
            def test_func():
                assert 1
        """
        )
        reports = runtestprotocol(item, log=False)
        assert len(reports) == 3
        callreport = reports[1]
        assert callreport.passed
        assert callreport.wasxfail == "this is an xfail"

    def test_xfail_using_platform(self, testrunnerer: Testrunnerer) -> None:
        """Verify that platform can be used with xfail statements."""
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.xfail("platform.platform() == platform.platform()")
            def test_func():
                assert 0
        """
        )
        reports = runtestprotocol(item, log=False)
        assert len(reports) == 3
        callreport = reports[1]
        assert callreport.wasxfail

    def test_xfail_xpassed_strict(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.xfail(strict=True, reason="nope")
            def test_func():
                assert 1
        """
        )
        reports = runtestprotocol(item, log=False)
        assert len(reports) == 3
        callreport = reports[1]
        assert callreport.failed
        assert str(callreport.longrepr) == "[XPASS(strict)] nope"
        assert not hasattr(callreport, "wasxfail")

    def test_xfail_run_anyway(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.xfail
            def test_func():
                assert 0
            def test_func2():
                testrunner.xfail("hello")
        """
        )
        result = testrunnerer.runtestrunner("--runxfail")
        result.stdout.fnmatch_lines(
            ["*def test_func():*", "*assert 0*", "*1 failed*1 pass*"]
        )

    @testrunner.mark.parametrize(
        "test_input,expected",
        [
            (
                ["-rs"],
                ["SKIPPED [1] test_sample.py:2: unconditional skip", "*1 skipped*"],
            ),
            (
                ["-rs", "--runxfail"],
                ["SKIPPED [1] test_sample.py:2: unconditional skip", "*1 skipped*"],
            ),
        ],
    )
    def test_xfail_run_with_skip_mark(
        self, testrunnerer: Testrunnerer, test_input, expected
    ) -> None:
        testrunnerer.makepyfile(
            test_sample="""
            import testrunner
            @testrunner.mark.skip
            def test_skip_location() -> None:
                assert 0
        """
        )
        result = testrunnerer.runtestrunner(*test_input)
        result.stdout.fnmatch_lines(expected)

    def test_xfail_evalfalse_but_fails(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.xfail('False')
            def test_func():
                assert 0
        """
        )
        reports = runtestprotocol(item, log=False)
        callreport = reports[1]
        assert callreport.failed
        assert not hasattr(callreport, "wasxfail")
        assert "xfail" in callreport.keywords

    def test_xfail_not_report_default(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            test_one="""
            import testrunner
            @testrunner.mark.xfail
            def test_this():
                assert 0
        """
        )
        testrunnerer.runtestrunner(p, "-v")
        # result.stdout.fnmatch_lines([
        #    "*HINT*use*-r*"
        # ])

    def test_xfail_not_run_xfail_reporting(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            test_one="""
            import testrunner
            @testrunner.mark.xfail(run=False, reason="noway")
            def test_this():
                assert 0
            @testrunner.mark.xfail("True", run=False)
            def test_this_true():
                assert 0
            @testrunner.mark.xfail("False", run=False, reason="huh")
            def test_this_false():
                assert 1
        """
        )
        result = testrunnerer.runtestrunner(p, "-rx")
        result.stdout.fnmatch_lines(
            [
                "*test_one*test_this - *NOTRUN* noway",
                "*test_one*test_this_true - *NOTRUN* condition: True",
                "*1 passed*",
            ]
        )

    def test_xfail_not_run_does_not_format_traceback(
        self, testrunnerer: Testrunnerer, monkeypatch: testrunner.MonkeyPatch
    ) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner

            @testrunner.mark.xfail(run=False, reason="noway")
            def test_func():
                assert 0
            """
        )
        getrepr = ExceptionInfo.getrepr
        styles = []

        def spy_getrepr(self, *args, **kwargs):
            styles.append(kwargs["style"])
            return getrepr(self, *args, **kwargs)

        monkeypatch.setattr(ExceptionInfo, "getrepr", spy_getrepr)

        reports = runtestprotocol(item, log=False)

        assert reports[0].skipped
        assert styles == ["value"]

    def test_xfail_not_run_no_setup_run(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            test_one="""
            import testrunner
            @testrunner.mark.xfail(run=False, reason="hello")
            def test_this():
                assert 0
            def setup_module(mod):
                raise ValueError(42)
        """
        )
        result = testrunnerer.runtestrunner(p, "-rx")
        result.stdout.fnmatch_lines(["*test_one*test_this*NOTRUN*hello", "*1 xfailed*"])

    def test_xfail_xpass(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            test_one="""
            import testrunner
            @testrunner.mark.xfail
            def test_that():
                assert 1
        """
        )
        result = testrunnerer.runtestrunner(p, "-rX")
        result.stdout.fnmatch_lines(["*XPASS*test_that*", "*1 xpassed*"])
        assert result.ret == 0

    def test_xfail_imperative(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner
            def test_this():
                testrunner.xfail("hello")
        """
        )
        result = testrunnerer.runtestrunner(p)
        result.stdout.fnmatch_lines(["*1 xfailed*"])
        result = testrunnerer.runtestrunner(p, "-rx")
        result.stdout.fnmatch_lines(["*XFAIL*test_this*hello*"])
        result = testrunnerer.runtestrunner(p, "--runxfail")
        result.stdout.fnmatch_lines(["*1 pass*"])

    def test_xfail_imperative_in_setup_function(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner
            def setup_function(function):
                testrunner.xfail("hello")

            def test_this():
                assert 0
        """
        )
        result = testrunnerer.runtestrunner(p)
        result.stdout.fnmatch_lines(["*1 xfailed*"])
        result = testrunnerer.runtestrunner(p, "-rx")
        result.stdout.fnmatch_lines(["*XFAIL*test_this*hello*"])
        result = testrunnerer.runtestrunner(p, "--runxfail")
        result.stdout.fnmatch_lines(
            """
            *def test_this*
            *1 fail*
        """
        )

    def xtest_dynamic_xfail_set_during_setup(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner
            def setup_function(function):
                testrunner.mark.xfail(function)
            def test_this():
                assert 0
            def test_that():
                assert 1
        """
        )
        result = testrunnerer.runtestrunner(p, "-rxX")
        result.stdout.fnmatch_lines(["*XFAIL*test_this*", "*XPASS*test_that*"])

    def test_dynamic_xfail_no_run(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture
            def arg(request):
                request.applymarker(testrunner.mark.xfail(run=False))
            def test_this(arg):
                assert 0
        """
        )
        result = testrunnerer.runtestrunner(p, "-rxX")
        result.stdout.fnmatch_lines(["*XFAIL*test_this*NOTRUN*"])

    def test_dynamic_xfail_set_during_funcarg_setup(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.fixture
            def arg(request):
                request.applymarker(testrunner.mark.xfail)
            def test_this2(arg):
                assert 0
        """
        )
        result = testrunnerer.runtestrunner(p)
        result.stdout.fnmatch_lines(["*1 xfailed*"])

    def test_dynamic_xfail_set_during_runtest_failed(self, testrunnerer: Testrunnerer) -> None:
        # Issue #7486.
        p = testrunnerer.makepyfile(
            """
            import testrunner
            def test_this(request):
                request.node.add_marker(testrunner.mark.xfail(reason="xfail"))
                assert 0
        """
        )
        result = testrunnerer.runtestrunner(p)
        result.assert_outcomes(xfailed=1)

    def test_dynamic_xfail_set_during_runtest_passed_strict(
        self, testrunnerer: Testrunnerer
    ) -> None:
        # Issue #7486.
        p = testrunnerer.makepyfile(
            """
            import testrunner
            def test_this(request):
                request.node.add_marker(testrunner.mark.xfail(reason="xfail", strict=True))
        """
        )
        result = testrunnerer.runtestrunner(p)
        result.assert_outcomes(failed=1)

    @testrunner.mark.parametrize(
        "expected, actual, matchline",
        [
            ("TypeError", "TypeError", "*1 xfailed*"),
            ("(AttributeError, TypeError)", "TypeError", "*1 xfailed*"),
            ("TypeError", "IndexError", "*1 failed*"),
            ("(AttributeError, TypeError)", "IndexError", "*1 failed*"),
        ],
    )
    def test_xfail_raises(
        self, expected, actual, matchline, testrunnerer: Testrunnerer
    ) -> None:
        p = testrunnerer.makepyfile(
            f"""
            import testrunner
            @testrunner.mark.xfail(raises={expected})
            def test_raises():
                raise {actual}()
        """
        )
        result = testrunnerer.runtestrunner(p)
        result.stdout.fnmatch_lines([matchline])

    def test_strict_sanity(self, testrunnerer: Testrunnerer) -> None:
        """Sanity check for xfail(strict=True): a failing test should behave
        exactly like a normal xfail."""
        p = testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.xfail(reason='unsupported feature', strict=True)
            def test_foo():
                assert 0
        """
        )
        result = testrunnerer.runtestrunner(p, "-rxX")
        result.stdout.fnmatch_lines(["*XFAIL*unsupported feature*"])
        assert result.ret == 0

    @testrunner.mark.parametrize("strict", [True, False])
    def test_strict_xfail(self, testrunnerer: Testrunnerer, strict: bool) -> None:
        p = testrunnerer.makepyfile(
            f"""
            import testrunner

            @testrunner.mark.xfail(reason='unsupported feature', strict={strict})
            def test_foo():
                with open('foo_executed', 'w', encoding='utf-8'):
                    pass  # make sure test executes
        """
        )
        result = testrunnerer.runtestrunner(p, "-rxX")
        if strict:
            result.stdout.fnmatch_lines(
                ["*test_foo*", "*XPASS(strict)*unsupported feature*"]
            )
        else:
            result.stdout.fnmatch_lines(
                [
                    "*test_strict_xfail*",
                    "XPASS test_strict_xfail.py::test_foo - unsupported feature",
                ]
            )
        assert result.ret == (1 if strict else 0)
        assert testrunnerer.path.joinpath("foo_executed").exists()

    @testrunner.mark.parametrize("strict", [True, False])
    def test_strict_xfail_condition(self, testrunnerer: Testrunnerer, strict: bool) -> None:
        p = testrunnerer.makepyfile(
            f"""
            import testrunner

            @testrunner.mark.xfail(False, reason='unsupported feature', strict={strict})
            def test_foo():
                pass
        """
        )
        result = testrunnerer.runtestrunner(p, "-rxX")
        result.stdout.fnmatch_lines(["*1 passed*"])
        assert result.ret == 0

    @testrunner.mark.parametrize("strict", [True, False])
    def test_xfail_condition_keyword(self, testrunnerer: Testrunnerer, strict: bool) -> None:
        p = testrunnerer.makepyfile(
            f"""
            import testrunner

            @testrunner.mark.xfail(condition=False, reason='unsupported feature', strict={strict})
            def test_foo():
                pass
        """
        )
        result = testrunnerer.runtestrunner(p, "-rxX")
        result.stdout.fnmatch_lines(["*1 passed*"])
        assert result.ret == 0

    @testrunner.mark.parametrize("strict_val", ["true", "false"])
    @testrunner.mark.parametrize("option_name", ["strict_xfail", "strict"])
    def test_strict_xfail_default_from_file(
        self, testrunnerer: Testrunnerer, strict_val: str, option_name: str
    ) -> None:
        testrunnerer.makeini(
            f"""
            [testrunner]
            {option_name} = {strict_val}
        """
        )
        p = testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.xfail(reason='unsupported feature')
            def test_foo():
                pass
        """
        )
        result = testrunnerer.runtestrunner(p, "-rxX")
        strict = strict_val == "true"
        result.stdout.fnmatch_lines(["*1 failed*" if strict else "*1 xpassed*"])
        assert result.ret == (1 if strict else 0)

    def test_xfail_markeval_namespace(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner

            def testrunner_markeval_namespace():
                return {"color": "green"}
            """
        )
        p = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.xfail("color == 'green'")
            def test_1():
                assert False

            @testrunner.mark.xfail("color == 'red'")
            def test_2():
                assert False
        """
        )
        res = testrunnerer.runtestrunner(p)
        assert res.ret == 1
        res.stdout.fnmatch_lines(["*1 failed*"])
        res.stdout.fnmatch_lines(["*1 xfailed*"])


class TestXFailwithSetupTeardown:
    def test_failing_setup_issue9(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            def setup_function(func):
                assert 0

            @testrunner.mark.xfail
            def test_func():
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 xfail*"])

    def test_failing_teardown_issue9(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            def teardown_function(func):
                assert 0

            @testrunner.mark.xfail
            def test_func():
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 xfail*"])

    def test_xfail_call_and_teardown_reports_show_phase(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            test_case="""
            import testrunner

            @testrunner.fixture
            def my_fix():
                yield
                raise Exception("teardown")

            @testrunner.mark.xfail(reason="Some reason")
            def test_func(my_fix):
                raise Exception("call")
            """
        )

        result = testrunnerer.runtestrunner("-rx")

        result.stdout.fnmatch_lines(
            [
                "*XFAIL*test_case.py::test_func*",
                "*XFAIL at teardown of*test_case.py::test_func*",
            ]
        )

    def test_xfail_setup_report_shows_phase(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            test_case="""
            import testrunner

            @testrunner.fixture
            def my_fix():
                raise Exception("setup")

            @testrunner.mark.xfail(reason="Some reason")
            def test_func(my_fix):
                pass
            """
        )

        result = testrunnerer.runtestrunner("-rx")

        result.stdout.fnmatch_lines(
            [
                "*XFAIL at setup of*test_case.py::test_func*",
            ]
        )


class TestSkip:
    def test_skip_class(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skip
            class TestSomething(object):
                def test_foo(self):
                    pass
                def test_bar(self):
                    pass

            def test_baz():
                pass
        """
        )
        rec = testrunnerer.inline_run()
        rec.assertoutcome(skipped=2, passed=1)

    def test_skips_on_false_string(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skip('False')
            def test_foo():
                pass
        """
        )
        rec = testrunnerer.inline_run()
        rec.assertoutcome(skipped=1)

    def test_arg_as_reason(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skip('testing stuff')
            def test_bar():
                pass
        """
        )
        result = testrunnerer.runtestrunner("-rs")
        result.stdout.fnmatch_lines(["*testing stuff*", "*1 skipped*"])

    def test_skip_no_reason(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skip
            def test_foo():
                pass
        """
        )
        result = testrunnerer.runtestrunner("-rs")
        result.stdout.fnmatch_lines(["*unconditional skip*", "*1 skipped*"])

    def test_skip_with_reason(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skip(reason="for lolz")
            def test_bar():
                pass
        """
        )
        result = testrunnerer.runtestrunner("-rs")
        result.stdout.fnmatch_lines(["*for lolz*", "*1 skipped*"])

    def test_only_skips_marked_test(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skip
            def test_foo():
                pass
            @testrunner.mark.skip(reason="nothing in particular")
            def test_bar():
                pass
            def test_baz():
                assert True
        """
        )
        result = testrunnerer.runtestrunner("-rs")
        result.stdout.fnmatch_lines(["*nothing in particular*", "*1 passed*2 skipped*"])

    def test_strict_and_skip(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skip
            def test_hello():
                pass
        """
        )
        result = testrunnerer.runtestrunner("-rs", "--strict-markers")
        result.stdout.fnmatch_lines(["*unconditional skip*", "*1 skipped*"])

    def test_wrong_skip_usage(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skip(False, reason="I thought this was skipif")
            def test_hello():
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "*TypeError: *__init__() got multiple values for argument 'reason'"
                " - maybe you meant testrunner.mark.skipif?"
            ]
        )


class TestSkipif:
    def test_skipif_conditional(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.skipif("hasattr(os, 'sep')")
            def test_func():
                pass
        """
        )
        x = testrunner.raises(testrunner.skip.Exception, lambda: testrunner_runtest_setup(item))
        assert x.value.msg == "condition: hasattr(os, 'sep')"

    @testrunner.mark.parametrize(
        "params", ["\"hasattr(sys, 'platform')\"", 'True, reason="invalid platform"']
    )
    def test_skipif_reporting(self, testrunnerer: Testrunnerer, params) -> None:
        p = testrunnerer.makepyfile(
            test_foo=f"""
            import testrunner
            @testrunner.mark.skipif({params})
            def test_that():
                assert 0
        """
        )
        result = testrunnerer.runtestrunner(p, "-s", "-rs")
        result.stdout.fnmatch_lines(["*SKIP*1*test_foo.py*platform*", "*1 skipped*"])
        assert result.ret == 0

    def test_skipif_using_platform(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            @testrunner.mark.skipif("platform.platform() == platform.platform()")
            def test_func():
                pass
        """
        )
        with testrunner.raises(testrunner.skip.Exception):
            testrunner_runtest_setup(item)

    @testrunner.mark.parametrize(
        "marker, msg1, msg2",
        [("skipif", "SKIP", "skipped"), ("xfail", "XPASS", "xpassed")],
    )
    def test_skipif_reporting_multiple(
        self, testrunnerer: Testrunnerer, marker, msg1, msg2
    ) -> None:
        testrunnerer.makepyfile(
            test_foo=f"""
            import testrunner
            @testrunner.mark.{marker}(False, reason='first_condition')
            @testrunner.mark.{marker}(True, reason='second_condition')
            def test_foobar():
                assert 1
        """
        )
        result = testrunnerer.runtestrunner("-s", "-rsxX")
        result.stdout.fnmatch_lines(
            [f"*{msg1}*test_foo.py*second_condition*", f"*1 {msg2}*"]
        )
        assert result.ret == 0


def test_skip_not_report_default(testrunnerer: Testrunnerer) -> None:
    p = testrunnerer.makepyfile(
        test_one="""
        import testrunner
        def test_this():
            testrunner.skip("hello")
    """
    )
    result = testrunnerer.runtestrunner(p, "-v")
    result.stdout.fnmatch_lines(
        [
            # "*HINT*use*-r*",
            "*1 skipped*"
        ]
    )


def test_skipif_class(testrunnerer: Testrunnerer) -> None:
    p = testrunnerer.makepyfile(
        """
        import testrunner

        class TestClass(object):
            _testrunner_mark = testrunner.mark.skipif("True")
            def test_that(self):
                assert 0
            def test_though(self):
                assert 0
    """
    )
    result = testrunnerer.runtestrunner(p)
    result.stdout.fnmatch_lines(["*2 skipped*"])


def test_skipped_reasons_functional(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_one="""
            import testrunner
            from helpers import doskip

            def setup_function(func):  # LINE 4
                doskip("setup function")

            def test_func():
                pass

            class TestClass:
                def test_method(self):
                    doskip("test method")

                @testrunner.mark.skip("via_decorator")  # LINE 14
                def test_deco(self):
                    assert 0
        """,
        helpers="""
            import testrunner, sys
            def doskip(reason):
                assert sys._getframe().f_lineno == 3
                testrunner.skip(reason)  # LINE 4
        """,
    )
    result = testrunnerer.runtestrunner("-rs")
    result.stdout.fnmatch_lines_random(
        [
            "SKIPPED [[]1[]] test_one.py:7: setup function",
            "SKIPPED [[]1[]] helpers.py:4: test method",
            "SKIPPED [[]1[]] test_one.py:14: via_decorator",
        ]
    )
    assert result.ret == 0


def test_skipped_folding(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_one="""
            import testrunner
            _testrunner_mark = testrunner.mark.skip("Folding")
            def setup_function(func):
                pass
            def test_func():
                pass
            class TestClass(object):
                def test_method(self):
                    pass
       """
    )
    result = testrunnerer.runtestrunner("-rs")
    result.stdout.fnmatch_lines(["*SKIP*2*test_one.py: Folding"])
    assert result.ret == 0


def test_reportchars(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner
        def test_1():
            assert 0
        @testrunner.mark.xfail
        def test_2():
            assert 0
        @testrunner.mark.xfail
        def test_3():
            pass
        def test_4():
            testrunner.skip("four")
    """
    )
    result = testrunnerer.runtestrunner("-rfxXs")
    result.stdout.fnmatch_lines(
        ["FAIL*test_1*", "XFAIL*test_2*", "XPASS*test_3*", "SKIP*four*"]
    )


def test_reportchars_error(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        conftest="""
        def testrunner_runtest_teardown():
            assert 0
        """,
        test_simple="""
        def test_foo():
            pass
        """,
    )
    result = testrunnerer.runtestrunner("-rE")
    result.stdout.fnmatch_lines(["ERROR*test_foo*"])


def test_reportchars_all(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner
        def test_1():
            assert 0
        @testrunner.mark.xfail
        def test_2():
            assert 0
        @testrunner.mark.xfail
        def test_3():
            pass
        def test_4():
            testrunner.skip("four")
        @testrunner.fixture
        def fail():
            assert 0
        def test_5(fail):
            pass
    """
    )
    result = testrunnerer.runtestrunner("-ra")
    result.stdout.fnmatch_lines(
        [
            "SKIP*four*",
            "XFAIL*test_2*",
            "XPASS*test_3*",
            "ERROR*test_5*",
            "FAIL*test_1*",
        ]
    )


def test_reportchars_all_error(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        conftest="""
        def testrunner_runtest_teardown():
            assert 0
        """,
        test_simple="""
        def test_foo():
            pass
        """,
    )
    result = testrunnerer.runtestrunner("-ra")
    result.stdout.fnmatch_lines(["ERROR*test_foo*"])


def test_errors_in_xfail_skip_expressions(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner
        @testrunner.mark.skipif("asd")
        def test_nameerror():
            pass
        @testrunner.mark.xfail("syntax error")
        def test_syntax():
            pass

        def test_func():
            pass
    """
    )
    result = testrunnerer.runtestrunner()

    expected = [
        "*ERROR*test_nameerror*",
        "*asd*",
        "",
        "During handling of the above exception, another exception occurred:",
    ]

    expected += [
        "*evaluating*skipif*condition*",
        "*asd*",
        "*ERROR*test_syntax*",
        "*evaluating*xfail*condition*",
        "    syntax error",
        "            ^",
        "SyntaxError: invalid syntax",
        "*1 pass*2 errors*",
    ]
    result.stdout.fnmatch_lines(expected)


def test_xfail_skipif_with_globals(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner
        x = 3
        @testrunner.mark.skipif("x == 3")
        def test_skip1():
            pass
        @testrunner.mark.xfail("x == 3")
        def test_boolean():
            assert 0
    """
    )
    result = testrunnerer.runtestrunner("-rsx")
    result.stdout.fnmatch_lines(["*SKIP*x == 3*", "*XFAIL*test_boolean*x == 3*"])


def test_default_markers(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("--markers")
    result.stdout.fnmatch_lines(
        [
            "*skipif(condition, ..., [*], reason=...)*skip*",
            "*xfail(condition, ..., [*], reason=..., run=True, raises=None, strict=strict_xfail)*expected failure*",
        ]
    )


def test_xfail_test_setup_exception(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
            def testrunner_runtest_setup():
                0 / 0
        """
    )
    p = testrunnerer.makepyfile(
        """
            import testrunner
            @testrunner.mark.xfail
            def test_func():
                assert 0
        """
    )
    result = testrunnerer.runtestrunner(p)
    assert result.ret == 0
    assert "xfailed" in result.stdout.str()
    result.stdout.no_fnmatch_line("*xpassed*")


def test_imperativeskip_on_xfail_test(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner
        @testrunner.mark.xfail
        def test_that_fails():
            assert 0

        @testrunner.mark.skipif("True")
        def test_hello():
            pass
    """
    )
    testrunnerer.makeconftest(
        """
        import testrunner
        def testrunner_runtest_setup(item):
            testrunner.skip("abc")
    """
    )
    result = testrunnerer.runtestrunner("-rsxX")
    result.stdout.fnmatch_lines_random(
        """
        *SKIP*abc*
        *SKIP*condition: True*
        *2 skipped*
    """
    )


class TestBooleanCondition:
    def test_skipif(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skipif(True, reason="True123")
            def test_func1():
                pass
            @testrunner.mark.skipif(False, reason="True123")
            def test_func2():
                pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            """
            *1 passed*1 skipped*
        """
        )

    def test_skipif_noreason(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.skipif(True)
            def test_func():
                pass
        """
        )
        result = testrunnerer.runtestrunner("-rs")
        result.stdout.fnmatch_lines(
            """
            *1 error*
        """
        )

    def test_xfail(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.xfail(True, reason="True123")
            def test_func():
                assert 0
        """
        )
        result = testrunnerer.runtestrunner("-rxs")
        result.stdout.fnmatch_lines(
            """
            *XFAIL*True123*
            *1 xfail*
        """
        )


def test_xfail_item(testrunnerer: Testrunnerer) -> None:
    # Ensure testrunner.xfail works with non-Python Item
    testrunnerer.makeconftest(
        """
        import testrunner

        class MyItem(testrunner.Item):
            nodeid = 'foo'
            def runtest(self):
                testrunner.xfail("Expected Failure")

        def testrunner_collect_file(file_path, parent):
            return MyItem.from_parent(name="foo", parent=parent)
    """
    )
    result = testrunnerer.inline_run()
    _passed, skipped, failed = result.listoutcomes()
    assert not failed
    xfailed = [r for r in skipped if hasattr(r, "wasxfail")]
    assert xfailed


def test_module_level_skip_error(testrunnerer: Testrunnerer) -> None:
    """Verify that using testrunner.skip at module level causes a collection error."""
    testrunnerer.makepyfile(
        """
        import testrunner
        testrunner.skip("skip_module_level")

        def test_func():
            assert True
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        ["*Using testrunner.skip outside of a test will skip the entire module*"]
    )


def test_module_level_skip_with_allow_module_level(testrunnerer: Testrunnerer) -> None:
    """Verify that using testrunner.skip(allow_module_level=True) is allowed."""
    testrunnerer.makepyfile(
        """
        import testrunner
        testrunner.skip("skip_module_level", allow_module_level=True)

        def test_func():
            assert 0
    """
    )
    result = testrunnerer.runtestrunner("-rxs")
    result.stdout.fnmatch_lines(["*SKIP*skip_module_level"])


def test_invalid_skip_keyword_parameter(testrunnerer: Testrunnerer) -> None:
    """Verify that using testrunner.skip() with unknown parameter raises an error."""
    testrunnerer.makepyfile(
        """
        import testrunner
        testrunner.skip("skip_module_level", unknown=1)

        def test_func():
            assert 0
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*TypeError:*['unknown']*"])


def test_mark_xfail_item(testrunnerer: Testrunnerer) -> None:
    # Ensure testrunner.mark.xfail works with non-Python Item
    testrunnerer.makeconftest(
        """
        import testrunner

        class MyItem(testrunner.Item):
            nodeid = 'foo'
            def setup(self):
                marker = testrunner.mark.xfail("1 == 2", reason="Expected failure - false")
                self.add_marker(marker)
                marker = testrunner.mark.xfail(True, reason="Expected failure - true")
                self.add_marker(marker)
            def runtest(self):
                assert False

        def testrunner_collect_file(file_path, parent):
            return MyItem.from_parent(name="foo", parent=parent)
    """
    )
    result = testrunnerer.inline_run()
    _passed, skipped, failed = result.listoutcomes()
    assert not failed
    xfailed = [r for r in skipped if hasattr(r, "wasxfail")]
    assert xfailed


def test_summary_list_after_errors(testrunnerer: Testrunnerer) -> None:
    """Ensure the list of errors/fails/xfails/skips appears after tracebacks in terminal reporting."""
    testrunnerer.makepyfile(
        """
        import testrunner
        def test_fail():
            assert 0
    """
    )
    result = testrunnerer.runtestrunner("-ra")
    result.stdout.fnmatch_lines(
        [
            "=* FAILURES *=",
            "*= short test summary info =*",
            "FAILED test_summary_list_after_errors.py::test_fail - assert 0",
        ]
    )


def test_importorskip() -> None:
    with testrunner.raises(
        testrunner.skip.Exception,
        match=r"^could not import 'doesnotexist': No module named .*",
    ):
        testrunner.importorskip("doesnotexist")


def test_relpath_rootdir(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        **{
            "tests/test_1.py": """
        import testrunner
        @testrunner.mark.skip()
        def test_pass():
            pass
            """,
        }
    )
    result = testrunnerer.runtestrunner("-rs", "tests/test_1.py", "--rootdir=tests")
    result.stdout.fnmatch_lines(
        ["SKIPPED [[]1[]] tests/test_1.py:2: unconditional skip"]
    )


def test_skip_from_fixture(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        **{
            "tests/test_1.py": """
        import testrunner
        def test_pass(arg):
            pass
        @testrunner.fixture
        def arg():
            condition = True
            if condition:
                testrunner.skip("Fixture conditional skip")
            """,
        }
    )
    result = testrunnerer.runtestrunner("-rs", "tests/test_1.py", "--rootdir=tests")
    result.stdout.fnmatch_lines(
        ["SKIPPED [[]1[]] tests/test_1.py:2: Fixture conditional skip"]
    )


def test_skip_using_reason_works_ok(testrunnerer: Testrunnerer) -> None:
    p = testrunnerer.makepyfile(
        """
        import testrunner

        def test_skipping_reason():
            testrunner.skip(reason="skippedreason")
        """
    )
    result = testrunnerer.runtestrunner(p)
    result.stdout.no_fnmatch_line("*TestrunnerDeprecationWarning*")
    result.assert_outcomes(skipped=1)


def test_fail_using_reason_works_ok(testrunnerer: Testrunnerer) -> None:
    p = testrunnerer.makepyfile(
        """
        import testrunner

        def test_failing_reason():
            testrunner.fail(reason="failedreason")
        """
    )
    result = testrunnerer.runtestrunner(p)
    result.stdout.no_fnmatch_line("*TestrunnerDeprecationWarning*")
    result.assert_outcomes(failed=1)


def test_exit_with_reason_works_ok(testrunnerer: Testrunnerer) -> None:
    p = testrunnerer.makepyfile(
        """
        import testrunner

        def test_exit_reason_only():
            testrunner.exit(reason="foo")
        """
    )
    result = testrunnerer.runtestrunner(p)
    result.stdout.fnmatch_lines("*_testrunner.outcomes.Exit: foo*")
