# mypy: allow-untyped-defs
from __future__ import annotations

from collections.abc import Sequence
import dataclasses
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import types

import setuptools

from _testrunner.config import ExitCode
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.pathlib import symlink_or_skip
from _testrunner.testrunnerer import Testrunnerer
import testrunner


def prepend_pythonpath(*dirs) -> str:
    cur = os.getenv("PYTHONPATH")
    if cur:
        dirs += (cur,)
    return os.pathsep.join(str(p) for p in dirs)


class TestGeneralUsage:
    def test_config_error(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.copy_example("conftest_usageerror/conftest.py")
        result = testrunnerer.runtestrunner(testrunnerer.path)
        assert result.ret == ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(["*ERROR: hello"])
        result.stdout.fnmatch_lines(["*testrunner_unconfigure_called"])

    def test_root_conftest_syntax_error(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(conftest="raise SyntaxError\n")
        result = testrunnerer.runtestrunner()
        result.stderr.fnmatch_lines(["*raise SyntaxError*"])
        assert result.ret != 0

    def test_early_hook_error_issue38_1(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_sessionstart():
                0 / 0
        """
        )
        result = testrunnerer.runtestrunner(testrunnerer.path)
        assert result.ret != 0
        # tracestyle is native by default for hook failures
        result.stdout.fnmatch_lines(
            ["*INTERNALERROR*File*conftest.py*line 2*", "*0 / 0*"]
        )
        result = testrunnerer.runtestrunner(testrunnerer.path, "--fulltrace")
        assert result.ret != 0
        # tracestyle is native by default for hook failures
        result.stdout.fnmatch_lines(
            ["*INTERNALERROR*def testrunner_sessionstart():*", "*INTERNALERROR*0 / 0*"]
        )

    def test_early_hook_configure_error_issue38(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_configure():
                0 / 0
        """
        )
        result = testrunnerer.runtestrunner(testrunnerer.path)
        assert result.ret != 0
        # here we get it on stderr
        result.stderr.fnmatch_lines(
            ["*INTERNALERROR*File*conftest.py*line 2*", "*0 / 0*"]
        )

    def test_file_not_found(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("asd")
        assert result.ret != 0
        result.stderr.fnmatch_lines(["ERROR: file or directory not found: asd"])

    def test_file_not_found_unconfigure_issue143(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_configure():
                print("---configure")
            def testrunner_unconfigure():
                print("---unconfigure")
        """
        )
        result = testrunnerer.runtestrunner("-s", "asd")
        assert result.ret == ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(["ERROR: file or directory not found: asd"])
        result.stdout.fnmatch_lines(["*---configure", "*---unconfigure"])

    def test_config_preparse_plugin_option(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            testrunner_xyz="""
            def testrunner_addoption(parser):
                parser.addoption("--xyz", dest="xyz", action="store")
        """
        )
        testrunnerer.makepyfile(
            test_one="""
            def test_option(testrunnerconfig):
                assert testrunnerconfig.option.xyz == "123"
        """
        )
        result = testrunnerer.runtestrunner("-p", "testrunner_xyz", "--xyz=123", syspathinsert=True)
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*1 passed*"])

    @testrunner.mark.parametrize("load_cov_early", [True, False])
    def test_early_load_setuptools_name(
        self, testrunnerer: Testrunnerer, monkeypatch, load_cov_early
    ) -> None:
        monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD")

        testrunnerer.makepyfile(mytestplugin1_module="")
        testrunnerer.makepyfile(mytestplugin2_module="")
        testrunnerer.makepyfile(mycov_module="")
        testrunnerer.syspathinsert()

        loaded = []

        @dataclasses.dataclass
        class DummyEntryPoint:
            name: str
            module: str
            group: str = "testrunner11"

            def load(self):
                mod = importlib.import_module(self.module)
                loaded.append(self.name)
                return mod

        entry_points = [
            DummyEntryPoint("myplugin1", "mytestplugin1_module"),
            DummyEntryPoint("myplugin2", "mytestplugin2_module"),
            DummyEntryPoint("mycov", "mycov_module"),
        ]

        @dataclasses.dataclass
        class DummyDist:
            entry_points: object
            files: object = ()

        def my_dists():
            return (DummyDist(entry_points),)

        monkeypatch.setattr(importlib.metadata, "distributions", my_dists)
        params = ("-p", "mycov") if load_cov_early else ()
        testrunnerer.runtestrunner_inprocess(*params)
        if load_cov_early:
            assert loaded == ["mycov", "myplugin1", "myplugin2"]
        else:
            assert loaded == ["myplugin1", "myplugin2", "mycov"]

    @testrunner.mark.parametrize("import_mode", ["prepend", "append", "importlib"])
    def test_assertion_rewrite(self, testrunnerer: Testrunnerer, import_mode) -> None:
        p = testrunnerer.makepyfile(
            """
            def test_this():
                x = 0
                assert x
        """
        )
        result = testrunnerer.runtestrunner(p, f"--import-mode={import_mode}")
        result.stdout.fnmatch_lines([">       assert x", "E       assert 0"])
        assert result.ret == 1

    def test_nested_import_error(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
                import import_fails
                def test_this():
                    assert import_fails.a == 1
        """
        )
        testrunnerer.makepyfile(import_fails="import does_not_work")
        result = testrunnerer.runtestrunner(p)
        result.stdout.fnmatch_lines(
            [
                "ImportError while importing test module*",
                "*No module named *does_not_work*",
            ]
        )
        assert result.ret == 2

    def test_not_collectable_arguments(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile("")
        p2 = testrunnerer.makefile(".pyc", "123")
        result = testrunnerer.runtestrunner(p1, p2)
        assert result.ret == ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(
            [
                f"ERROR: not found: {p2}",
                "(no match in any of *)",
                "",
            ]
        )

    @testrunner.mark.filterwarnings("default")
    def test_better_reporting_on_conftest_load_failure(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Show a user-friendly traceback on conftest import failures (#486, #3332)"""
        testrunnerer.makepyfile("")
        conftest = testrunnerer.makeconftest(
            """
            def foo():
                import qwerty
            foo()
        """
        )
        result = testrunnerer.runtestrunner("--help")
        result.stdout.fnmatch_lines(
            """
            *--version*
            *warning*conftest.py*
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.stdout.lines == []
        assert result.stderr.lines == [
            f"ImportError while loading conftest '{conftest}'.",
            "conftest.py:3: in <module>",
            "    foo()",
            "conftest.py:2: in foo",
            "    import qwerty",
            "E   ModuleNotFoundError: No module named 'qwerty'",
        ]

    def test_early_skip(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.mkdir("xyz")
        testrunnerer.makeconftest(
            """
            import testrunner
            def testrunner_collect_file():
                testrunner.skip("early")
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
        result.stdout.fnmatch_lines(["*1 skip*"])

    def test_issue88_initial_file_multinodes(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.copy_example("issue88_initial_file_multinodes")
        p = testrunnerer.makepyfile("def test_hello(): pass")
        result = testrunnerer.runtestrunner(p, "--collect-only")
        result.stdout.fnmatch_lines(["*MyFile*test_issue88*", "*Module*test_issue88*"])

    def test_issue93_initialnode_importing_capturing(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import sys
            print("should not be seen")
            sys.stderr.write("stder42\\n")
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
        result.stdout.no_fnmatch_line("*should not be seen*")
        assert "stderr42" not in result.stderr.str()

    def test_conftest_printing_shows_if_error(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            print("should be seen")
            assert 0
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        assert "should be seen" in result.stdout.str()

    def test_issue109_sibling_conftests_not_loaded(self, testrunnerer: Testrunnerer) -> None:
        sub1 = testrunnerer.mkdir("sub1")
        sub2 = testrunnerer.mkdir("sub2")
        sub1.joinpath("conftest.py").write_text("assert 0", encoding="utf-8")
        result = testrunnerer.runtestrunner(sub2)
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
        sub2.joinpath("__init__.py").touch()
        p = sub2.joinpath("test_hello.py")
        p.touch()
        result = testrunnerer.runtestrunner(p)
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
        result = testrunnerer.runtestrunner(sub1)
        assert result.ret == ExitCode.USAGE_ERROR

    def test_directory_skipped(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            def testrunner_ignore_collect():
                testrunner.skip("intentional")
        """
        )
        testrunnerer.makepyfile("def test_hello(): pass")
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
        result.stdout.fnmatch_lines(["*1 skipped*"])

    def test_multiple_items_per_collector_byid(self, testrunnerer: Testrunnerer) -> None:
        c = testrunnerer.makeconftest(
            """
            import testrunner
            class MyItem(testrunner.Item):
                def runtest(self):
                    pass
            class MyCollector(testrunner.File):
                def collect(self):
                    return [MyItem.from_parent(name="xyz", parent=self)]
            def testrunner_collect_file(file_path, parent):
                if file_path.name.startswith("conftest"):
                    return MyCollector.from_parent(path=file_path, parent=parent)
        """
        )
        result = testrunnerer.runtestrunner(c.name + "::" + "xyz")
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*1 pass*"])

    def test_skip_on_generated_funcarg_id(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            def testrunner_generate_tests(metafunc):
                metafunc.parametrize('x', [3], ids=['hello-123'])
            def testrunner_runtest_setup(item):
                print(item.keywords)
                if 'hello-123' in item.keywords:
                    testrunner.skip("hello")
                assert 0
        """
        )
        p = testrunnerer.makepyfile("""def test_func(x): pass""")
        res = testrunnerer.runtestrunner(p)
        assert res.ret == 0
        res.stdout.fnmatch_lines(["*1 skipped*"])

    def test_direct_addressing_selects(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            def testrunner_generate_tests(metafunc):
                metafunc.parametrize('i', [1, 2], ids=["1", "2"])
            def test_func(i):
                pass
        """
        )
        res = testrunnerer.runtestrunner(p.name + "::" + "test_func[1]")
        assert res.ret == 0
        res.stdout.fnmatch_lines(["*1 passed*"])

    def test_direct_addressing_selects_duplicates(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.parametrize("a", [1, 2, 10, 11, 2, 1, 12, 11])
            def test_func(a):
                pass
            """
        )
        result = testrunnerer.runtestrunner(p)
        result.assert_outcomes(failed=0, passed=8)

    def test_direct_addressing_selects_duplicates_1(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.parametrize("a", [1, 2, 10, 11, 2, 1, 12, 1_1,2_1])
            def test_func(a):
                pass
            """
        )
        result = testrunnerer.runtestrunner(p)
        result.assert_outcomes(failed=0, passed=9)

    def test_direct_addressing_selects_duplicates_2(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.parametrize("a", ["a","b","c","a","a1"])
            def test_func(a):
                pass
            """
        )
        result = testrunnerer.runtestrunner(p)
        result.assert_outcomes(failed=0, passed=5)

    def test_direct_addressing_notfound(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            def test_func():
                pass
        """
        )
        res = testrunnerer.runtestrunner(p.name + "::" + "test_notfound")
        assert res.ret
        res.stderr.fnmatch_lines(["*ERROR*not found*"])

    def test_docstring_on_hookspec(self) -> None:
        from _testrunner import hookspec

        for name, value in vars(hookspec).items():
            if name.startswith("testrunner_"):
                assert value.__doc__, f"no docstring for {name}"

    def test_initialization_error_issue49(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_configure():
                x
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == 3  # internal error
        result.stderr.fnmatch_lines(["INTERNAL*testrunner_configure*", "INTERNAL*x*"])
        assert "sessionstarttime" not in result.stderr.str()

    @testrunner.mark.parametrize("lookfor", ["test_fun.py::test_a"])
    def test_issue134_report_error_when_collecting_member(
        self, testrunnerer: Testrunnerer, lookfor
    ) -> None:
        testrunnerer.makepyfile(
            test_fun="""
            def test_a():
                pass
            def"""
        )
        result = testrunnerer.runtestrunner(lookfor)
        result.stdout.fnmatch_lines(["*SyntaxError*"])
        if "::" in lookfor:
            result.stderr.fnmatch_lines(["*ERROR*"])
            assert result.ret == 4  # usage error only if item not found

    def test_report_all_failed_collections_initargs(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            from _testrunner.config import ExitCode

            def testrunner_sessionfinish(exitstatus):
                assert exitstatus == ExitCode.USAGE_ERROR
                print("testrunner_sessionfinish_called")
            """
        )
        testrunnerer.makepyfile(test_a="def", test_b="def")
        result = testrunnerer.runtestrunner("test_a.py::a", "test_b.py::b")
        result.stderr.fnmatch_lines(["*ERROR*test_a.py::a*", "*ERROR*test_b.py::b*"])
        result.stdout.fnmatch_lines(["testrunner_sessionfinish_called"])
        assert result.ret == ExitCode.USAGE_ERROR

    def test_namespace_import_doesnt_confuse_import_hook(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Ref #383.

        Python 3.3's namespace package messed with our import hooks.
        Importing a module that didn't exist, even if the ImportError was
        gracefully handled, would make our test crash.
        """
        testrunnerer.mkdir("not_a_package")
        p = testrunnerer.makepyfile(
            """
            try:
                from not_a_package import doesnt_exist
            except ImportError:
                # We handle the import error gracefully here
                pass

            def test_whatever():
                pass
        """
        )
        res = testrunnerer.runtestrunner(p.name)
        assert res.ret == 0

    def test_unknown_option(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("--qwlkej")
        result.stderr.fnmatch_lines(
            """
            *unrecognized*
        """
        )

    def test_getsourcelines_error_issue553(
        self, testrunnerer: Testrunnerer, monkeypatch
    ) -> None:
        monkeypatch.setattr("inspect.getsourcelines", None)
        p = testrunnerer.makepyfile(
            """
            def raise_error(obj):
                raise OSError('source code not available')

            import inspect
            inspect.getsourcelines = raise_error

            def test_foo(invalid_fixture):
                pass
        """
        )
        res = testrunnerer.runtestrunner(p)
        res.stdout.fnmatch_lines(
            ["*source code not available*", "E*fixture 'invalid_fixture' not found"]
        )

    def test_plugins_given_as_strings(
        self, testrunnerer: Testrunnerer, monkeypatch, _sys_snapshot
    ) -> None:
        """Test that str values passed to main() as `plugins` arg are
        interpreted as module names to be imported and registered (#855)."""
        # A plugin which cannot be found is a usage error, reported through the
        # return value rather than raised out of testrunner.main() (#993).
        ret = testrunner.main([str(testrunnerer.path)], plugins=["invalid.module"])
        assert ret == ExitCode.USAGE_ERROR

        p = testrunnerer.path.joinpath("test_test_plugins_given_as_strings.py")
        p.write_text("def test_foo(): pass", encoding="utf-8")
        mod = types.ModuleType("myplugin")
        monkeypatch.setitem(sys.modules, "myplugin", mod)
        assert testrunner.main(args=[str(testrunnerer.path)], plugins=["myplugin"]) == 0

    def test_parametrized_with_bytes_regex(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import re
            import testrunner
            @testrunner.mark.parametrize('r', [re.compile(b'foo')])
            def test_stuff(r):
                pass
        """
        )
        res = testrunnerer.runtestrunner(p)
        res.stdout.fnmatch_lines(["*1 passed*"])

    def test_parametrized_with_null_bytes(self, testrunnerer: Testrunnerer) -> None:
        """Test parametrization with values that contain null bytes and unicode characters (#2644, #2957)"""
        p = testrunnerer.makepyfile(
            """\
            import testrunner

            @testrunner.mark.parametrize("data", [b"\\x00", "\\x00", 'ação'])
            def test_foo(data):
                assert data
            """
        )
        res = testrunnerer.runtestrunner(p)
        res.assert_outcomes(passed=3)

    # Warning ignore because of:
    # https://github.com/python/cpython/issues/85308
    # Can be removed once Python<3.12 support is dropped.
    @testrunner.mark.filterwarnings("ignore:'encoding' argument not specified")
    def test_command_line_args_from_file(
        self, testrunnerer: Testrunnerer, tmp_path: Path
    ) -> None:
        testrunnerer.makepyfile(
            test_file="""
            import testrunner

            class TestClass:
                @testrunner.mark.parametrize("a", ["x","y"])
                def test_func(self, a):
                    pass
            """
        )
        tests = [
            "test_file.py::TestClass::test_func[x]",
            "test_file.py::TestClass::test_func[y]",
            "-q",
        ]
        args_file = testrunnerer.maketxtfile(tests="\n".join(tests))
        result = testrunnerer.runtestrunner(f"@{args_file}")
        result.assert_outcomes(failed=0, passed=2)


class TestInvocationVariants:
    def test_earlyinit(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner
            assert hasattr(testrunner, 'mark')
        """
        )
        result = testrunnerer.runpython(p)
        assert result.ret == 0

    def test_pydoc(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runpython_c("import testrunner;help(testrunner)")
        assert result.ret == 0
        s = result.stdout.str()
        assert "MarkGenerator" in s

    def test_import_star_testrunner(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            from testrunner import *
            #Item
            #File
            main
            skip
            xfail
        """
        )
        result = testrunnerer.runpython(p)
        assert result.ret == 0

    def test_double_testrunnercmdline(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            run="""
            import testrunner
            testrunner.main()
            testrunner.main()
        """
        )
        testrunnerer.makepyfile(
            """
            def test_hello():
                pass
        """
        )
        result = testrunnerer.runpython(p)
        result.stdout.fnmatch_lines(["*1 passed*", "*1 passed*"])

    def test_python_minus_m_invocation_ok(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile("def test_hello(): pass")
        res = testrunnerer.run(sys.executable, "-m", "testrunner", str(p1))
        assert res.ret == 0

    def test_python_minus_m_invocation_fail(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile("def test_fail(): 0/0")
        res = testrunnerer.run(sys.executable, "-m", "testrunner", str(p1))
        assert res.ret == 1

    def test_python_testrunner_package(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile("def test_pass(): pass")
        res = testrunnerer.run(sys.executable, "-m", "testrunner", str(p1))
        assert res.ret == 0
        res.stdout.fnmatch_lines(["*1 passed*"])

    def test_invoke_with_invalid_type(self) -> None:
        with testrunner.raises(
            TypeError, match="expected to be a list of strings, got: '-h'"
        ):
            testrunner.main("-h")  # type: ignore[arg-type]

    def test_invoke_with_path(self, testrunnerer: Testrunnerer) -> None:
        retcode = testrunner.main([str(testrunnerer.path)])
        assert retcode == ExitCode.NO_TESTS_COLLECTED

    def test_invoke_plugin_api(self, capsys) -> None:
        class MyPlugin:
            def testrunner_addoption(self, parser):
                parser.addoption("--myopt")

        testrunner.main(["-h"], plugins=[MyPlugin()])
        out, _err = capsys.readouterr()
        assert "--myopt" in out

    def test_pyargs_importerror(self, testrunnerer: Testrunnerer, monkeypatch) -> None:
        monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", False)
        path = testrunnerer.mkpydir("tpkg")
        path.joinpath("test_hello.py").write_text("raise ImportError", encoding="utf-8")

        result = testrunnerer.runtestrunner("--pyargs", "tpkg.test_hello", syspathinsert=True)
        assert result.ret != 0

        result.stdout.fnmatch_lines(["collected*0*items*/*1*error"])

    def test_pyargs_only_imported_once(self, testrunnerer: Testrunnerer) -> None:
        pkg = testrunnerer.mkpydir("foo")
        pkg.joinpath("test_foo.py").write_text(
            "print('hello from test_foo')\ndef test(): pass", encoding="utf-8"
        )
        pkg.joinpath("conftest.py").write_text(
            "def testrunner_configure(config): print('configuring')", encoding="utf-8"
        )

        result = testrunnerer.runtestrunner(
            "--pyargs", "foo.test_foo", "-s", syspathinsert=True
        )
        # should only import once
        assert result.outlines.count("hello from test_foo") == 1
        # should only configure once
        assert result.outlines.count("configuring") == 1

    def test_pyargs_filename_looks_like_module(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.path.joinpath("conftest.py").touch()
        testrunnerer.path.joinpath("t.py").write_text("def test(): pass", encoding="utf-8")
        result = testrunnerer.runtestrunner("--pyargs", "t.py")
        assert result.ret == ExitCode.OK

    def test_cmdline_python_package(self, testrunnerer: Testrunnerer, monkeypatch) -> None:
        import warnings

        monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", False)
        path = testrunnerer.mkpydir("tpkg")
        path.joinpath("test_hello.py").write_text(
            "def test_hello(): pass", encoding="utf-8"
        )
        path.joinpath("test_world.py").write_text(
            "def test_world(): pass", encoding="utf-8"
        )
        result = testrunnerer.runtestrunner("--pyargs", "tpkg")
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*2 passed*"])
        result = testrunnerer.runtestrunner("--pyargs", "tpkg.test_hello", syspathinsert=True)
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*1 passed*"])

        empty_package = testrunnerer.mkpydir("empty_package")
        monkeypatch.setenv("PYTHONPATH", str(empty_package), prepend=os.pathsep)
        # the path which is not a package raises a warning on pypy;
        # no idea why only pypy and not normal python warn about it here
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ImportWarning)
            result = testrunnerer.runtestrunner("--pyargs", ".")
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*2 passed*"])

        monkeypatch.setenv("PYTHONPATH", str(testrunnerer), prepend=os.pathsep)
        result = testrunnerer.runtestrunner("--pyargs", "tpkg.test_missing", syspathinsert=True)
        assert result.ret != 0
        result.stderr.fnmatch_lines(["*not*found*test_missing*"])

    @testrunner.mark.skipif(
        int(setuptools.__version__.split(".")[0]) >= 80,
        reason="modern setuptools removing pkg_resources",
    )
    def test_cmdline_python_legacy_namespace_package(
        self, testrunnerer: Testrunnerer, monkeypatch
    ) -> None:
        """Test --pyargs option with legacy namespace packages (#1567).

        Ref: https://packaging.python.org/guides/packaging-namespace-packages/
        """
        monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)

        search_path = []
        for dirname in "hello", "world":
            d = testrunnerer.mkdir(dirname)
            search_path.append(d)
            ns = d.joinpath("ns_pkg")
            ns.mkdir()
            ns.joinpath("__init__.py").write_text(
                "__import__('pkg_resources').declare_namespace(__name__)",
                encoding="utf-8",
            )
            lib = ns.joinpath(dirname)
            lib.mkdir()
            lib.joinpath("__init__.py").touch()
            lib.joinpath(f"test_{dirname}.py").write_text(
                f"def test_{dirname}(): pass\ndef test_other():pass",
                encoding="utf-8",
            )

        # The structure of the test directory is now:
        # .
        # ├── hello
        # │   └── ns_pkg
        # │       ├── __init__.py
        # │       └── hello
        # │           ├── __init__.py
        # │           └── test_hello.py
        # └── world
        #     └── ns_pkg
        #         ├── __init__.py
        #         └── world
        #             ├── __init__.py
        #             └── test_world.py

        # NOTE: the different/reversed ordering is intentional here.
        monkeypatch.setenv("PYTHONPATH", prepend_pythonpath(*search_path))
        for p in search_path:
            monkeypatch.syspath_prepend(p)

        # mixed module and filenames:
        monkeypatch.chdir("world")

        # pgk_resources.declare_namespace has been deprecated in favor of implicit namespace packages.
        # pgk_resources has been deprecated entirely.
        # While we could change the test to use implicit namespace packages, seems better
        # to still ensure the old declaration via declare_namespace still works.
        ignore_w = (
            r"-Wignore:Deprecated call to `pkg_resources.declare_namespace",
            r"-Wignore:pkg_resources is deprecated",
        )
        result = testrunnerer.runtestrunner(
            "--pyargs", "-v", "ns_pkg.hello", "ns_pkg/world", *ignore_w
        )
        assert result.ret == 0
        result.stdout.fnmatch_lines(
            [
                "test_hello.py::test_hello*PASSED*",
                "test_hello.py::test_other*PASSED*",
                "ns_pkg/world/test_world.py::test_world*PASSED*",
                "ns_pkg/world/test_world.py::test_other*PASSED*",
                "*4 passed in*",
            ]
        )

        # specify tests within a module
        testrunnerer.chdir()
        result = testrunnerer.runtestrunner(
            "--pyargs", "-v", "ns_pkg.world.test_world::test_other"
        )
        assert result.ret == 0
        result.stdout.fnmatch_lines(
            ["*test_world.py::test_other*PASSED*", "*1 passed*"]
        )

    def test_invoke_test_and_doctestmodules(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            def test():
                pass
        """
        )
        result = testrunnerer.runtestrunner(str(p) + "::test", "--doctest-modules")
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_cmdline_python_package_symlink(
        self, testrunnerer: Testrunnerer, monkeypatch
    ) -> None:
        """
        --pyargs with packages with path containing symlink can have conftest.py in
        their package (#2985)
        """
        monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)

        dirname = "lib"
        d = testrunnerer.mkdir(dirname)
        foo = d.joinpath("foo")
        foo.mkdir()
        foo.joinpath("__init__.py").touch()
        lib = foo.joinpath("bar")
        lib.mkdir()
        lib.joinpath("__init__.py").touch()
        lib.joinpath("test_bar.py").write_text(
            "def test_bar(): pass\ndef test_other(a_fixture):pass", encoding="utf-8"
        )
        lib.joinpath("conftest.py").write_text(
            "import testrunner\n@testrunner.fixture\ndef a_fixture():pass", encoding="utf-8"
        )

        d_local = testrunnerer.mkdir("symlink_root")
        symlink_location = d_local / "lib"
        symlink_or_skip(d, symlink_location, target_is_directory=True)

        # The structure of the test directory is now:
        # .
        # ├── symlink_root
        # │   └── lib -> ../lib
        # └── lib
        #     └── foo
        #         ├── __init__.py
        #         └── bar
        #             ├── __init__.py
        #             ├── conftest.py
        #             └── test_bar.py

        # NOTE: the different/reversed ordering is intentional here.
        search_path = ["lib", os.path.join("symlink_root", "lib")]
        monkeypatch.setenv("PYTHONPATH", prepend_pythonpath(*search_path))
        for p in search_path:
            monkeypatch.syspath_prepend(p)

        # module picked up in symlink-ed directory:
        # It picks up symlink_root/lib/foo/bar (symlink) via sys.path.
        result = testrunnerer.runtestrunner("--pyargs", "-v", "foo.bar")
        testrunnerer.chdir()
        assert result.ret == 0
        result.stdout.fnmatch_lines(
            [
                "symlink_root/lib/foo/bar/test_bar.py::test_bar PASSED*",
                "symlink_root/lib/foo/bar/test_bar.py::test_other PASSED*",
                "*2 passed*",
            ]
        )

    def test_cmdline_python_package_not_exists(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("--pyargs", "tpkgwhatv")
        assert result.ret
        result.stderr.fnmatch_lines(["ERROR*module*or*package*not*found*"])

    @testrunner.mark.xfail(reason="decide: feature or bug")
    def test_noclass_discovery_if_not_testcase(self, testrunnerer: Testrunnerer) -> None:
        testpath = testrunnerer.makepyfile(
            """
            import unittest
            class TestHello(object):
                def test_hello(self):
                    assert self.attr

            class RealTest(unittest.TestCase, TestHello):
                attr = 42
        """
        )
        reprec = testrunnerer.inline_run(testpath)
        reprec.assertoutcome(passed=1)

    def test_doctest_id(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makefile(
            ".txt",
            """
            >>> x=3
            >>> x
            4
        """,
        )
        testid = "test_doctest_id.txt::test_doctest_id.txt"
        expected_lines = [
            "*= FAILURES =*",
            "*_ ?doctest? test_doctest_id.txt _*",
            "FAILED test_doctest_id.txt::test_doctest_id.txt",
            "*= 1 failed in*",
        ]
        result = testrunnerer.runtestrunner(testid, "-rf", "--tb=short")
        result.stdout.fnmatch_lines(expected_lines)

        # Ensure that re-running it will still handle it as
        # doctest.DocTestFailure, which was not the case before when
        # re-importing doctest, but not creating a new RUNNER_CLASS.
        result = testrunnerer.runtestrunner(testid, "-rf", "--tb=short")
        result.stdout.fnmatch_lines(expected_lines)

    def test_core_backward_compatibility(self) -> None:
        """Test backward compatibility for get_plugin_manager function. See #787."""
        import _testrunner.config

        assert (
            type(_testrunner.config.get_plugin_manager())
            is _testrunner.config.TestrunnerPluginManager
        )

    def test_has_plugin(self, request) -> None:
        """Test hasplugin function of the plugin manager (#932)."""
        assert request.config.pluginmanager.hasplugin("python")


class TestDurations:
    source = """
        from _testrunner import timing
        def test_something():
            pass
        def test_2():
            timing.sleep(0.010)
        def test_1():
            timing.sleep(0.002)
        def test_3():
            timing.sleep(0.020)
    """

    def test_calls(self, testrunnerer: Testrunnerer, mock_timing) -> None:
        testrunnerer.makepyfile(self.source)
        result = testrunnerer.runtestrunner_inprocess("--durations=10")
        assert result.ret == 0

        result.stdout.fnmatch_lines_random(
            ["*durations*", "*call*test_3*", "*call*test_2*"]
        )

        result.stdout.fnmatch_lines(
            ["(8 durations < 0.005s hidden.  Use -vv to show these durations.)"]
        )

    def test_calls_show_2(self, testrunnerer: Testrunnerer, mock_timing) -> None:
        testrunnerer.makepyfile(self.source)
        result = testrunnerer.runtestrunner_inprocess("--durations=2")
        assert result.ret == 0

        lines = result.stdout.get_lines_after("*slowest*durations*")
        assert "4 passed" in lines[2]

    def test_calls_showall(self, testrunnerer: Testrunnerer, mock_timing) -> None:
        testrunnerer.makepyfile(self.source)
        result = testrunnerer.runtestrunner_inprocess("--durations=0")
        assert result.ret == 0
        TestDurations.check_tests_in_output(result.stdout.lines, 2, 3)

    def test_calls_showall_verbose(self, testrunnerer: Testrunnerer, mock_timing) -> None:
        testrunnerer.makepyfile(self.source)
        result = testrunnerer.runtestrunner_inprocess("--durations=0", "-vv")
        assert result.ret == 0
        TestDurations.check_tests_in_output(result.stdout.lines, 1, 2, 3)

    def test_calls_showall_durationsmin(self, testrunnerer: Testrunnerer, mock_timing) -> None:
        testrunnerer.makepyfile(self.source)
        result = testrunnerer.runtestrunner_inprocess("--durations=0", "--durations-min=0.015")
        assert result.ret == 0
        TestDurations.check_tests_in_output(result.stdout.lines, 3)

    def test_calls_showall_durationsmin_verbose(
        self, testrunnerer: Testrunnerer, mock_timing
    ) -> None:
        testrunnerer.makepyfile(self.source)
        result = testrunnerer.runtestrunner_inprocess(
            "--durations=0", "--durations-min=0.015", "-vv"
        )
        assert result.ret == 0
        TestDurations.check_tests_in_output(result.stdout.lines, 3)

    @staticmethod
    def check_tests_in_output(
        lines: Sequence[str], *expected_test_numbers: int, number_of_tests: int = 3
    ) -> None:
        found_test_numbers = {
            test_number
            for test_number in range(1, number_of_tests + 1)
            if any(
                line.endswith(f"test_{test_number}") and " call " in line
                for line in lines
            )
        }
        assert found_test_numbers == set(expected_test_numbers)

    def test_with_deselected(self, testrunnerer: Testrunnerer, mock_timing) -> None:
        testrunnerer.makepyfile(self.source)
        result = testrunnerer.runtestrunner_inprocess("--durations=2", "-k test_3")
        assert result.ret == 0

        result.stdout.fnmatch_lines(["*durations*", "*call*test_3*"])

    def test_with_failing_collection(self, testrunnerer: Testrunnerer, mock_timing) -> None:
        testrunnerer.makepyfile(self.source)
        testrunnerer.makepyfile(test_collecterror="""xyz""")
        result = testrunnerer.runtestrunner_inprocess("--durations=2", "-k test_1")
        assert result.ret == 2

        result.stdout.fnmatch_lines(["*Interrupted: 1 error during collection*"])
        # Collection errors abort test execution, therefore no duration is
        # output
        result.stdout.no_fnmatch_line("*duration*")

    def test_with_not(self, testrunnerer: Testrunnerer, mock_timing) -> None:
        testrunnerer.makepyfile(self.source)
        result = testrunnerer.runtestrunner_inprocess("-k not 1")
        assert result.ret == 0


class TestDurationsWithFixture:
    source = """
        import testrunner
        from _testrunner import timing

        @testrunner.fixture
        def setup_fixt():
            timing.sleep(2)

        def test_1(setup_fixt):
            timing.sleep(5)
    """

    def test_setup_function(self, testrunnerer: Testrunnerer, mock_timing) -> None:
        testrunnerer.makepyfile(self.source)
        result = testrunnerer.runtestrunner_inprocess("--durations=10")
        assert result.ret == 0

        result.stdout.fnmatch_lines_random(
            """
            *durations*
            5.00s call *test_1*
            2.00s setup *test_1*
        """
        )


def test_zipimport_hook(testrunnerer: Testrunnerer) -> None:
    """Test package loader is being used correctly (see #1837)."""
    zipapp = testrunner.importorskip("zipapp")
    testrunnerer.path.joinpath("app").mkdir()
    testrunnerer.makepyfile(
        **{
            "app/foo.py": """
            import testrunner
            def main():
                testrunner.main(['--pyargs', 'foo'])
        """
        }
    )
    target = testrunnerer.path.joinpath("foo.zip")
    zipapp.create_archive(
        str(testrunnerer.path.joinpath("app")), str(target), main="foo:main"
    )
    result = testrunnerer.runpython(target)
    assert result.ret == 0
    result.stderr.fnmatch_lines(["*not found*foo*"])
    result.stdout.no_fnmatch_line("*INTERNALERROR>*")


class TestStartupPluginImportErrors:
    """Exit codes for plugins which fail to load at startup (#993).

    A plugin which cannot be found means testrunner was pointed at something which
    is not there, which is a usage error; a plugin which is found but blows up
    while importing is a defect in the plugin, reported as an internal error.
    """

    @testrunner.fixture
    def broken_plugin(self, testrunnerer: Testrunnerer) -> Testrunnerer:
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(myplugin="raise ValueError('plugin is broken')")
        testrunnerer.makepyfile("def test_foo(): pass")
        return testrunnerer

    @testrunner.fixture
    def missing_plugin(self, testrunnerer: Testrunnerer) -> Testrunnerer:
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile("def test_foo(): pass")
        return testrunnerer

    def test_missing_via_cmdline(self, missing_plugin: Testrunnerer) -> None:
        result = missing_plugin.runtestrunner("-p", "nosuchplugin")
        assert result.ret == ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(['*Error importing plugin "nosuchplugin"*'])

    def test_missing_via_conftest(self, missing_plugin: Testrunnerer) -> None:
        missing_plugin.makeconftest("testrunner_plugins = ['nosuchplugin']")
        result = missing_plugin.runtestrunner()
        assert result.ret == ExitCode.USAGE_ERROR

    def test_missing_via_env(
        self, missing_plugin: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "nosuchplugin")
        result = missing_plugin.runtestrunner()
        assert result.ret == ExitCode.USAGE_ERROR

    def test_broken_via_cmdline(self, broken_plugin: Testrunnerer) -> None:
        result = broken_plugin.runtestrunner("-p", "myplugin")
        assert result.ret == ExitCode.INTERNAL_ERROR
        result.stderr.fnmatch_lines(
            [
                'Error while loading plugin "myplugin".',
                "*myplugin.py:1: in <module>*",
                "E*ValueError: plugin is broken",
            ]
        )

    def test_broken_via_conftest(self, broken_plugin: Testrunnerer) -> None:
        broken_plugin.makeconftest("testrunner_plugins = ['myplugin']")
        result = broken_plugin.runtestrunner()
        assert result.ret == ExitCode.INTERNAL_ERROR

    def test_broken_via_env(
        self, broken_plugin: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "myplugin")
        result = broken_plugin.runtestrunner()
        assert result.ret == ExitCode.INTERNAL_ERROR

    def test_usage_error_passes_through(self, testrunnerer: Testrunnerer) -> None:
        """A plugin raising UsageError at import keeps its usage-error semantics."""
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(
            myplugin="import testrunner\nraise testrunner.UsageError('config trouble')"
        )
        result = testrunnerer.runtestrunner("-p", "myplugin")
        assert result.ret == ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(["ERROR: config trouble*"])

    def test_broken_via_entry_point(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", raising=False)

        class DummyEntryPoint:
            name = "myplugin"
            group = "testrunner11"

            def load(self):
                raise ValueError("plugin is broken")

        class Distribution:
            version = "1.0"
            files = ("foo.txt",)
            metadata = {"name": "foo"}
            entry_points = (DummyEntryPoint(),)

        monkeypatch.setattr(
            importlib.metadata, "distributions", lambda: (Distribution(),)
        )
        testrunnerer.makepyfile("def test_foo(): pass")
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.INTERNAL_ERROR

    def test_import_error_without_args(self, testrunnerer: Testrunnerer) -> None:
        """A bare ``raise ImportError`` used to crash with an IndexError (#993)."""
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(myplugin="raise ImportError")
        testrunnerer.makepyfile("def test_foo(): pass")
        result = testrunnerer.runtestrunner("-p", "myplugin")
        assert result.ret == ExitCode.INTERNAL_ERROR
        result.stderr.no_fnmatch_line("*IndexError*")
        result.stderr.fnmatch_lines(['Error while loading plugin "myplugin".'])

    def test_missing_dependency_is_not_a_usage_error(self, testrunnerer: Testrunnerer) -> None:
        """The plugin was found; one of *its* imports is unsatisfied (#993)."""
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(myplugin="import nosuchdependency")
        testrunnerer.makepyfile("def test_foo(): pass")
        result = testrunnerer.runtestrunner("-p", "myplugin")
        assert result.ret == ExitCode.INTERNAL_ERROR

    def test_missing_submodule_of_existing_package(self, testrunnerer: Testrunnerer) -> None:
        """The package exists but the requested plugin module within it does not."""
        testrunnerer.syspathinsert()
        testrunnerer.mkpydir("mypkg")
        testrunnerer.makepyfile("def test_foo(): pass")
        result = testrunnerer.runtestrunner("-p", "mypkg.nosuchmodule")
        assert result.ret == ExitCode.USAGE_ERROR

    def test_conftest_import_failure_stays_a_usage_error(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """conftest.py is not a plugin; it keeps reporting a usage error (#993)."""
        testrunnerer.makeconftest("raise ValueError('conftest is broken')")
        testrunnerer.makepyfile("def test_foo(): pass")
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.USAGE_ERROR


def test_import_plugin_unicode_name(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(myplugin="")
    testrunnerer.makepyfile("def test(): pass")
    testrunnerer.makeconftest("testrunner_plugins = ['myplugin']")
    r = testrunnerer.runtestrunner()
    assert r.ret == 0


def test_testrunner_plugins_as_module(testrunnerer: Testrunnerer) -> None:
    """Do not raise an error if testrunner_plugins attribute is a module (#3899)"""
    testrunnerer.makepyfile(
        **{
            "__init__.py": "",
            "testrunner_plugins.py": "",
            "conftest.py": "from . import testrunner_plugins",
            "test_foo.py": "def test(): pass",
        }
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["* 1 passed in *"])


def test_deferred_hook_checking(testrunnerer: Testrunnerer) -> None:
    """Check hooks as late as possible (#1821)."""
    testrunnerer.syspathinsert()
    testrunnerer.makepyfile(
        **{
            "plugin.py": """
        class Hooks(object):
            def testrunner_my_hook(self, config):
                pass

        def testrunner_configure(config):
            config.pluginmanager.add_hookspecs(Hooks)
        """,
            "conftest.py": """
            testrunner_plugins = ['plugin']
            def testrunner_my_hook(config):
                return 40
        """,
            "test_foo.py": """
            def test(request):
                assert request.config.hook.testrunner_my_hook(config=request.config) == [40]
        """,
        }
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["* 1 passed *"])


def test_fixture_values_leak(testrunnerer: Testrunnerer) -> None:
    """Ensure that fixture objects are properly destroyed by the garbage collector at the end of their expected
    life-times (#2981).
    """
    testrunnerer.makepyfile(
        """
        import dataclasses
        import gc
        import testrunner
        import weakref

        @dataclasses.dataclass
        class SomeObj:
            name: str

        fix_of_test1_ref = None
        session_ref = None

        @testrunner.fixture(scope='session')
        def session_fix():
            global session_ref
            obj = SomeObj(name='session-fixture')
            session_ref = weakref.ref(obj)
            return obj

        @testrunner.fixture
        def fix(session_fix):
            global fix_of_test1_ref
            obj = SomeObj(name='local-fixture')
            fix_of_test1_ref = weakref.ref(obj)
            return obj

        def test1(fix):
            assert fix_of_test1_ref() is fix

        def test2():
            gc.collect()
            # fixture "fix" created during test1 must have been destroyed by now
            assert fix_of_test1_ref() is None
    """
    )
    # Running on subprocess does not activate the HookRecorder
    # which holds itself a reference to objects in case of the
    # testrunner_assert_reprcompare hook
    result = testrunnerer.runtestrunner_subprocess()
    result.stdout.fnmatch_lines(["* 2 passed *"])


def test_fixture_order_respects_scope(testrunnerer: Testrunnerer) -> None:
    """Ensure that fixtures are created according to scope order (#2405)."""
    testrunnerer.makepyfile(
        """
        import testrunner

        data = {}

        @testrunner.fixture(scope='module')
        def clean_data():
            data.clear()

        @testrunner.fixture(autouse=True)
        def add_data():
            data.update(value=True)

        @testrunner.mark.usefixtures('clean_data')
        def test_value():
            assert data.get('value')
    """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0


def test_frame_leak_on_failing_test(testrunnerer: Testrunnerer) -> None:
    """Testrunner would leak garbage referencing the frames of tests that failed
    that could never be reclaimed (#2798).

    Unfortunately it was not possible to remove the actual circles because most of them
    are made of traceback objects which cannot be weakly referenced. Those objects at least
    can be eventually claimed by the garbage collector.
    """
    testrunnerer.makepyfile(
        """
        import gc
        import weakref

        class Obj:
            pass

        ref = None

        def test1():
            obj = Obj()
            global ref
            ref = weakref.ref(obj)
            assert 0

        def test2():
            gc.collect()
            assert ref() is None
    """
    )
    result = testrunnerer.runtestrunner_subprocess()
    result.stdout.fnmatch_lines(["*1 failed, 1 passed in*"])


def test_fixture_mock_integration(testrunnerer: Testrunnerer) -> None:
    """Test that decorators applied to fixture are left working (#3774)"""
    p = testrunnerer.copy_example("acceptance/fixture_mock_integration.py")
    result = testrunnerer.runtestrunner(p)
    result.stdout.fnmatch_lines(["*1 passed*"])


def test_usage_error_code(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("-unknown-option-")
    assert result.ret == ExitCode.USAGE_ERROR


def test_error_on_async_function(testrunnerer: Testrunnerer) -> None:
    # In the below we .close() the coroutine only to avoid
    # "RuntimeWarning: coroutine 'test_2' was never awaited"
    # which messes with other tests.
    testrunnerer.makepyfile(
        test_async="""
        async def test_1():
            pass
        async def test_2():
            pass
        def test_3():
            coro = test_2()
            coro.close()
            return coro
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            "*async def functions are not natively supported*",
            "*test_async.py::test_1*",
            "*test_async.py::test_2*",
            "*test_async.py::test_3*",
        ]
    )
    result.assert_outcomes(failed=3)


def test_error_on_async_gen_function(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_async="""
        async def test_1():
            yield
        async def test_2():
            yield
        def test_3():
            return test_2()
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        [
            "*async def functions are not natively supported*",
            "*test_async.py::test_1*",
            "*test_async.py::test_2*",
            "*test_async.py::test_3*",
        ]
    )
    result.assert_outcomes(failed=3)


def test_error_on_sync_test_async_fixture(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_sync="""
            import testrunner

            @testrunner.fixture
            async def async_fixture():
                ...

            def test_foo(async_fixture):
                # suppress unawaited coroutine warning
                try:
                    async_fixture.send(None)
                except StopIteration:
                    pass
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(
        [
            "'test_foo' requested an async fixture 'async_fixture', with no plugin or hook that handled it. "
            "This is an error, as testrunner does not natively support it."
        ]
    )


def test_error_on_sync_test_async_fixture_gen(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_sync="""
            import testrunner

            @testrunner.fixture
            async def async_fixture():
                yield

            def test_foo(async_fixture):
                # async gens don't emit unawaited-coroutine
                ...
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(
        [
            "'test_foo' requested an async fixture 'async_fixture', with no plugin or hook that handled it. "
            "This is an error, as testrunner does not natively support it."
        ]
    )


def test_error_on_sync_test_async_autouse_fixture(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_sync="""
            import testrunner

            @testrunner.fixture(autouse=True)
            async def async_fixture():
                ...

            # We explicitly request the fixture to be able to
            # suppress the RuntimeWarning for unawaited coroutine.
            def test_foo(async_fixture):
                try:
                    async_fixture.send(None)
                except StopIteration:
                    pass
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(
        [
            "'test_foo' requested an async fixture 'async_fixture' with autouse=True, "
            "with no plugin or hook that handled it. "
            "This is an error, as testrunner does not natively support it."
        ]
    )


def test_pdb_can_be_rewritten(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        **{
            "conftest.py": """
                import testrunner
                testrunner.register_assert_rewrite("pdb")
                """,
            "__init__.py": "",
            "pdb.py": """
                def check():
                    assert 1 == 2
                """,
            "test_pdb.py": """
                def test():
                    import pdb
                    assert pdb.check()
                """,
        }
    )
    # Disable debugging plugin itself to avoid:
    # > INTERNALERROR> AttributeError: module 'pdb' has no attribute 'set_trace'
    result = testrunnerer.runtestrunner_subprocess("-p", "no:debugging", "-vv")
    result.stdout.fnmatch_lines(
        [
            "    def check():",
            ">       assert 1 == 2",
            "E       assert 1 == 2",
            "",
            "pdb.py:2: AssertionError",
            "*= 1 failed in *",
        ]
    )
    assert result.ret == 1


def test_tee_stdio_captures_and_live_prints(testrunnerer: Testrunnerer) -> None:
    testpath = testrunnerer.makepyfile(
        """
        import sys
        def test_simple():
            print ("@this is stdout@")
            print ("@this is stderr@", file=sys.stderr)
    """
    )
    result = testrunnerer.runtestrunner_subprocess(
        testpath,
        "--capture=tee-sys",
        "--junitxml=output.xml",
        "-o",
        "junit_logging=all",
    )

    # ensure stdout/stderr were 'live printed'
    result.stdout.fnmatch_lines(["*@this is stdout@*"])
    result.stderr.fnmatch_lines(["*@this is stderr@*"])

    # now ensure the output is in the junitxml
    fullXml = testrunnerer.path.joinpath("output.xml").read_text(encoding="utf-8")
    assert "@this is stdout@\n" in fullXml
    assert "@this is stderr@\n" in fullXml


@testrunner.mark.skipif(
    sys.platform == "win32",
    reason="Windows raises `OSError: [Errno 22] Invalid argument` instead",
)
def test_no_brokenpipeerror_message(testrunnerer: Testrunnerer) -> None:
    """Ensure that the broken pipe error message is suppressed.

    In some Python versions, it reaches sys.unraisablehook, in others
    a BrokenPipeError exception is propagated, but either way it prints
    to stderr on shutdown, so checking nothing is printed is enough.
    """
    popen = testrunnerer.popen((*testrunnerer._gettestrunnerargs(), "--help"))
    popen.stdout.close()
    ret = popen.wait()
    assert popen.stderr.read() == b""
    assert ret == 1

    # Cleanup.
    popen.stderr.close()


@testrunner.mark.filterwarnings("default")
def test_function_return_non_none_warning(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        def test_stuff():
            return "something"
    """
    )
    res = testrunnerer.runtestrunner()
    res.stdout.fnmatch_lines(["*Did you mean to use `assert` instead of `return`?*"])


def test_doctest_and_normal_imports_with_importlib(testrunnerer: Testrunnerer) -> None:
    """
    Regression test for #10811: previously import_path with ImportMode.importlib would
    not return a module if already in sys.modules, resulting in modules being imported
    multiple times, which causes problems with modules that have import side effects.
    """
    # Uses the exact reproducer form #10811, given it is very minimal
    # and illustrates the problem well.
    testrunnerer.makepyfile(
        **{
            "pmxbot/commands.py": "from . import logging",
            "pmxbot/logging.py": "",
            "tests/__init__.py": "",
            "tests/test_commands.py": """
                import importlib
                from pmxbot import logging

                class TestCommands:
                    def test_boo(self):
                        assert importlib.import_module('pmxbot.logging') is logging
                """,
        }
    )
    testrunnerer.makeini(
        """
        [testrunner]
        addopts=
            --doctest-modules
            --import-mode importlib
        """
    )
    result = testrunnerer.runtestrunner_subprocess()
    result.stdout.fnmatch_lines("*1 passed*")


@testrunner.mark.skip(reason="Test is not isolated")
def test_issue_9765(testrunnerer: Testrunnerer) -> None:
    """Reproducer for issue #9765 on Windows

    https://github.com/jacksonsr451/test-runner/issues/9765
    """
    testrunnerer.makepyprojecttoml(
        """
        [tool.testrunner.ini_options]
        addopts = "-p my_package.plugin.my_plugin"
        """
    )
    testrunnerer.makepyfile(
        **{
            "setup.py": (
                """
                from setuptools import setup

                if __name__ == '__main__':
                    setup(name='my_package', packages=['my_package', 'my_package.plugin'])
                """
            ),
            "my_package/__init__.py": "",
            "my_package/conftest.py": "",
            "my_package/test_foo.py": "def test(): pass",
            "my_package/plugin/__init__.py": "",
            "my_package/plugin/my_plugin.py": (
                """
                import testrunner

                def testrunner_configure(config):

                    class SimplePlugin:
                        @testrunner.fixture(params=[1, 2, 3])
                        def my_fixture(self, request):
                            yield request.param

                    config.pluginmanager.register(SimplePlugin())
                """
            ),
        }
    )

    subprocess.run(
        [sys.executable, "-Im", "pip", "install", "-e", "."],
        check=True,
    )
    try:
        # We are using subprocess.run rather than testrunnerer.run on purpose.
        # testrunnerer.run is adding the current directory to PYTHONPATH which avoids
        # the bug. We also use testrunner rather than python -m testrunner for the same
        # PYTHONPATH reason.
        subprocess.run(
            ["testrunner", "my_package"],
            capture_output=True,
            check=True,
            encoding="utf-8",
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            f"testrunner command failed:\n{exc.stdout=!s}\n{exc.stderr=!s}"
        ) from exc


def test_no_terminal_plugin(testrunnerer: Testrunnerer) -> None:
    """Smoke test to ensure testrunner can execute without the terminal plugin (#9422)."""
    testrunnerer.makepyfile("def test(): assert 1 == 2")
    result = testrunnerer.runtestrunner("-pno:terminal", "-s")
    assert result.ret == ExitCode.TESTS_FAILED


def test_stop_iteration_from_collect(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(test_it="raise StopIteration('hello')")
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.INTERRUPTED
    result.assert_outcomes(failed=0, passed=0, errors=1)
    result.stdout.fnmatch_lines(
        [
            "=* short test summary info =*",
            "ERROR test_it.py - StopIteration: hello",
            "!* Interrupted: 1 error during collection !*",
            "=* 1 error in * =*",
        ]
    )


def test_stop_iteration_runtest_protocol(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_it="""
        import testrunner
        @testrunner.fixture
        def fail_setup():
            raise StopIteration(1)
        def test_fail_setup(fail_setup):
            pass
        def test_fail_teardown(request):
            def stop_iteration():
                raise StopIteration(2)
            request.addfinalizer(stop_iteration)
        def test_fail_call():
            raise StopIteration(3)
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.TESTS_FAILED
    result.assert_outcomes(failed=1, passed=1, errors=2)
    result.stdout.fnmatch_lines(
        [
            "=* short test summary info =*",
            "FAILED test_it.py::test_fail_call - StopIteration: 3",
            "ERROR test_it.py::test_fail_setup - StopIteration: 1",
            "ERROR test_it.py::test_fail_teardown - StopIteration: 2",
            "=* 1 failed, 1 passed, 2 errors in * =*",
        ]
    )
