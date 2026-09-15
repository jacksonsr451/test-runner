# mypy: allow-untyped-defs
from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path
from pathlib import PurePath
import pprint
import shutil
import sys
import tempfile
import textwrap

from _testrunner.compat import running_on_ci
from _testrunner.config import ExitCode
from _testrunner.fixtures import FixtureRequest
from _testrunner.main import _in_venv
from _testrunner.main import Session
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.nodes import Item
from _testrunner.pathlib import symlink_or_skip
from _testrunner.testrunnerer import HookRecorder
from _testrunner.testrunnerer import Testrunnerer
import testrunner


def ensure_file(file_path: Path) -> Path:
    """Ensure that file exists"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.touch(exist_ok=True)
    return file_path


class TestCollector:
    def test_collect_versus_item(self) -> None:
        from testrunner import Collector
        from testrunner import Item

        assert not issubclass(Collector, Item)
        assert not issubclass(Item, Collector)

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
            assert isinstance(fn, testrunner.Function)
            assert fn != 3  # type: ignore[comparison-overlap]
            assert fn != modcol
            assert fn != [1, 2, 3]  # type: ignore[comparison-overlap]
            assert [1, 2, 3] != fn  # type: ignore[comparison-overlap]
            assert modcol != fn

        assert testrunnerer.collect_by_name(modcol, "doesnotexist") is None

    def test_getparent_and_accessors(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol(
            """
            class TestClass:
                 def test_foo(self):
                     pass
        """
        )
        cls = testrunnerer.collect_by_name(modcol, "TestClass")
        assert isinstance(cls, testrunner.Class)
        fn = testrunnerer.collect_by_name(cls, "test_foo")
        assert isinstance(fn, testrunner.Function)

        assert fn.getparent(testrunner.Module) is modcol
        assert modcol is not None
        assert modcol.module is not None
        assert modcol.cls is None
        assert modcol.instance is None

        assert fn.getparent(testrunner.Class) is cls
        assert cls.module is not None
        assert cls.cls is not None
        assert cls.instance is None

        assert fn.getparent(testrunner.Function) is fn
        assert fn.module is not None
        assert fn.cls is not None
        assert fn.instance is not None
        assert fn.function is not None

    def test_getcustomfile_roundtrip(self, testrunnerer: Testrunnerer) -> None:
        hello = testrunnerer.makefile(".xxx", hello="world")
        testrunnerer.makepyfile(
            conftest="""
            import testrunner
            class CustomFile(testrunner.File):
                def collect(self):
                    return []
            def testrunner_collect_file(file_path, parent):
                if file_path.suffix == ".xxx":
                    return CustomFile.from_parent(path=file_path, parent=parent)
        """
        )
        node = testrunnerer.getpathnode(hello)
        assert isinstance(node, testrunner.File)
        assert node.name == "hello.xxx"
        nodes = node.session.perform_collect([node.nodeid], genitems=False)
        assert len(nodes) == 1
        assert isinstance(nodes[0], testrunner.File)

    def test_can_skip_class_with_test_attr(self, testrunnerer: Testrunnerer) -> None:
        """Assure test class is skipped when using `__test__=False` (See #2007)."""
        testrunnerer.makepyfile(
            """
            class TestFoo(object):
                __test__ = False
                def __init__(self):
                    pass
                def test_foo():
                    assert True
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 0 items", "*no tests ran in*"])


class TestCollectFS:
    def test_ignored_certain_directories(self, testrunnerer: Testrunnerer) -> None:
        tmp_path = testrunnerer.path
        ensure_file(tmp_path / "build" / "test_notfound.py")
        ensure_file(tmp_path / "dist" / "test_notfound.py")
        ensure_file(tmp_path / "_darcs" / "test_notfound.py")
        ensure_file(tmp_path / "CVS" / "test_notfound.py")
        ensure_file(tmp_path / "{arch}" / "test_notfound.py")
        ensure_file(tmp_path / ".whatever" / "test_notfound.py")
        ensure_file(tmp_path / ".bzr" / "test_notfound.py")
        ensure_file(tmp_path / "normal" / "test_found.py")
        for x in tmp_path.rglob("test_*.py"):
            x.write_text("def test_hello(): pass", encoding="utf-8")

        result = testrunnerer.runtestrunner("--collect-only")
        s = result.stdout.str()
        assert "test_notfound" not in s
        assert "test_found" in s

    known_environment_types = testrunner.mark.parametrize(
        "env_path",
        [
            testrunner.param(PurePath("pyvenv.cfg"), id="venv"),
            testrunner.param(PurePath("conda-meta", "history"), id="conda"),
        ],
    )

    @known_environment_types
    def test_ignored_virtualenvs(self, testrunnerer: Testrunnerer, env_path: PurePath) -> None:
        ensure_file(testrunnerer.path / "virtual" / env_path)
        testfile = ensure_file(testrunnerer.path / "virtual" / "test_invenv.py")
        testfile.write_text("def test_hello(): pass", encoding="utf-8")

        # by default, ignore tests inside a virtualenv
        result = testrunnerer.runtestrunner()
        result.stdout.no_fnmatch_line("*test_invenv*")
        # allow test collection if user insists
        result = testrunnerer.runtestrunner("--collect-in-virtualenv")
        assert "test_invenv" in result.stdout.str()
        # allow test collection if user directly passes in the directory
        result = testrunnerer.runtestrunner("virtual")
        assert "test_invenv" in result.stdout.str()

    @known_environment_types
    def test_ignored_virtualenvs_norecursedirs_precedence(
        self, testrunnerer: Testrunnerer, env_path
    ) -> None:
        # norecursedirs takes priority
        ensure_file(testrunnerer.path / ".virtual" / env_path)
        testfile = ensure_file(testrunnerer.path / ".virtual" / "test_invenv.py")
        testfile.write_text("def test_hello(): pass", encoding="utf-8")
        result = testrunnerer.runtestrunner("--collect-in-virtualenv")
        result.stdout.no_fnmatch_line("*test_invenv*")
        # ...unless the virtualenv is explicitly given on the CLI
        result = testrunnerer.runtestrunner("--collect-in-virtualenv", ".virtual")
        assert "test_invenv" in result.stdout.str()

    @known_environment_types
    def test__in_venv(self, testrunnerer: Testrunnerer, env_path: PurePath) -> None:
        """Directly test the virtual env detection function"""
        # no env path, not a env
        base_path = testrunnerer.mkdir("venv")
        assert _in_venv(base_path) is False
        # with env path, totally a env
        ensure_file(base_path.joinpath(env_path))
        assert _in_venv(base_path) is True

    def test_custom_norecursedirs(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeini(
            """
            [testrunner]
            norecursedirs = mydir xyz*
        """
        )
        tmp_path = testrunnerer.path
        ensure_file(tmp_path / "mydir" / "test_hello.py").write_text(
            "def test_1(): pass", encoding="utf-8"
        )
        ensure_file(tmp_path / "xyz123" / "test_2.py").write_text(
            "def test_2(): 0/0", encoding="utf-8"
        )
        ensure_file(tmp_path / "xy" / "test_ok.py").write_text(
            "def test_3(): pass", encoding="utf-8"
        )
        rec = testrunnerer.inline_run()
        rec.assertoutcome(passed=1)
        rec = testrunnerer.inline_run("xyz123/test_2.py")
        rec.assertoutcome(failed=1)

    def test_testpaths_ini(self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch) -> None:
        testrunnerer.makeini(
            """
            [testrunner]
            testpaths = */tests
        """
        )
        tmp_path = testrunnerer.path
        ensure_file(tmp_path / "a" / "test_1.py").write_text(
            "def test_a(): pass", encoding="utf-8"
        )
        ensure_file(tmp_path / "b" / "tests" / "test_2.py").write_text(
            "def test_b(): pass", encoding="utf-8"
        )
        ensure_file(tmp_path / "c" / "tests" / "test_3.py").write_text(
            "def test_c(): pass", encoding="utf-8"
        )

        # executing from rootdir only tests from `testpaths` directories
        # are collected
        items, _reprec = testrunnerer.inline_genitems("-v")
        assert [x.name for x in items] == ["test_b", "test_c"]

        # check that explicitly passing directories in the command-line
        # collects the tests
        for dirname in ("a", "b", "c"):
            items, _reprec = testrunnerer.inline_genitems(tmp_path.joinpath(dirname))
            assert [x.name for x in items] == [f"test_{dirname}"]

        # changing cwd to each subdirectory and running testrunner without
        # arguments collects the tests in that directory normally
        for dirname in ("a", "b", "c"):
            monkeypatch.chdir(testrunnerer.path.joinpath(dirname))
            items, _reprec = testrunnerer.inline_genitems()
            assert [x.name for x in items] == [f"test_{dirname}"]

    def test_missing_permissions_on_unselected_directory_doesnt_crash(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Regression test for #12120."""
        test = testrunnerer.makepyfile(test="def test(): pass")
        bad = testrunnerer.mkdir("bad")
        try:
            bad.chmod(0)

            result = testrunnerer.runtestrunner(test)
        finally:
            bad.chmod(750)
            bad.rmdir()

        assert result.ret == ExitCode.OK
        result.assert_outcomes(passed=1)


class TestCollectPluginHookRelay:
    def test_testrunner_collect_file(self, testrunnerer: Testrunnerer) -> None:
        wascalled = []

        class Plugin:
            def testrunner_collect_file(self, file_path: Path) -> None:
                if not file_path.name.startswith("."):
                    # Ignore hidden files, e.g. .testmondata.
                    wascalled.append(file_path)

        testrunnerer.makefile(".abc", "xyz")
        testrunner.main(testrunnerer.path, plugins=[Plugin()])
        assert len(wascalled) == 1
        assert wascalled[0].suffix == ".abc"


class TestPrunetraceback:
    def test_custom_repr_failure(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import not_exists
        """
        )
        testrunnerer.makeconftest(
            """
            import testrunner
            def testrunner_collect_file(file_path, parent):
                return MyFile.from_parent(path=file_path, parent=parent)
            class MyError(Exception):
                pass
            class MyFile(testrunner.File):
                def collect(self):
                    raise MyError()
                def repr_failure(self, excinfo):
                    if isinstance(excinfo.value, MyError):
                        return "hello world"
                    return testrunner.File.repr_failure(self, excinfo)
        """
        )

        result = testrunnerer.runtestrunner(p)
        result.stdout.fnmatch_lines(["*ERROR collecting*", "*hello world*"])

    @testrunner.mark.xfail(reason="other mechanism for adding to reporting needed")
    def test_collect_report_postprocessing(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import not_exists
        """
        )
        testrunnerer.makeconftest(
            """
            import testrunner
            @testrunner.hookimpl(wrapper=True)
            def testrunner_make_collect_report():
                rep = yield
                rep.headerlines += ["header1"]
                return rep
        """
        )
        result = testrunnerer.runtestrunner(p)
        result.stdout.fnmatch_lines(["*ERROR collecting*", "*header1*"])

    def test_collection_error_traceback_is_clean(self, testrunnerer: Testrunnerer) -> None:
        """When a collection error occurs, the report traceback doesn't contain
        internal testrunner stack entries.

        Issue #11710.
        """
        testrunnerer.makepyfile(
            """
            raise Exception("LOUSY")
            """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(
            [
                "*ERROR collecting*",
                "test_*.py:1: in <module>",
                '    raise Exception("LOUSY")',
                "E   Exception: LOUSY",
                "*= short test summary info =*",
            ],
            consecutive=True,
        )


class TestCustomConftests:
    def test_ignore_collect_path(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_ignore_collect(collection_path, config):
                return collection_path.name.startswith("x") or collection_path.name == "test_one.py"
        """
        )
        sub = testrunnerer.mkdir("xy123")
        ensure_file(sub / "test_hello.py").write_text("syntax error", encoding="utf-8")
        sub.joinpath("conftest.py").write_text("syntax error", encoding="utf-8")
        testrunnerer.makepyfile("def test_hello(): pass")
        testrunnerer.makepyfile(test_one="syntax error")
        result = testrunnerer.runtestrunner("--fulltrace")
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_ignore_collect_not_called_on_argument(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_ignore_collect(collection_path, config):
                return True
        """
        )
        p = testrunnerer.makepyfile("def test_hello(): pass")
        result = testrunnerer.runtestrunner(p)
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*1 passed*"])
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
        result.stdout.fnmatch_lines(["*collected 0 items*"])

    def test_collectignore_exclude_on_option(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            from pathlib import Path

            class MyPathLike:
                def __init__(self, path):
                    self.path = path
                def __fspath__(self):
                    return "path"

            collect_ignore = [MyPathLike('hello'), 'test_world.py', Path('bye')]

            def testrunner_addoption(parser):
                parser.addoption("--XX", action="store_true", default=False)

            def testrunner_configure(config):
                if config.getvalue("XX"):
                    collect_ignore[:] = []
        """
        )
        testrunnerer.mkdir("hello")
        testrunnerer.makepyfile(test_world="def test_hello(): pass")
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
        result.stdout.no_fnmatch_line("*passed*")
        result = testrunnerer.runtestrunner("--XX")
        assert result.ret == 0
        assert "passed" in result.stdout.str()

    def test_collectignoreglob_exclude_on_option(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            collect_ignore_glob = ['*w*l[dt]*']
            def testrunner_addoption(parser):
                parser.addoption("--XX", action="store_true", default=False)
            def testrunner_configure(config):
                if config.getvalue("XX"):
                    collect_ignore_glob[:] = []
        """
        )
        testrunnerer.makepyfile(test_world="def test_hello(): pass")
        testrunnerer.makepyfile(test_welt="def test_hallo(): pass")
        result = testrunnerer.runtestrunner()
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
        result.stdout.fnmatch_lines(["*collected 0 items*"])
        result = testrunnerer.runtestrunner("--XX")
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*2 passed*"])

    def test_testrunner_fs_collect_hooks_are_seen(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import testrunner
            class MyModule(testrunner.Module):
                pass
            def testrunner_collect_file(file_path, parent):
                if file_path.suffix == ".py":
                    return MyModule.from_parent(path=file_path, parent=parent)
        """
        )
        testrunnerer.mkdir("sub")
        testrunnerer.makepyfile("def test_x(): pass")
        result = testrunnerer.runtestrunner("--co")
        result.stdout.fnmatch_lines(["*MyModule*", "*test_x*"])

    def test_testrunner_collect_file_from_sister_dir(self, testrunnerer: Testrunnerer) -> None:
        sub1 = testrunnerer.mkpydir("sub1")
        sub2 = testrunnerer.mkpydir("sub2")
        conf1 = testrunnerer.makeconftest(
            """
            import testrunner
            class MyModule1(testrunner.Module):
                pass
            def testrunner_collect_file(file_path, parent):
                if file_path.suffix == ".py":
                    return MyModule1.from_parent(path=file_path, parent=parent)
        """
        )
        conf1.replace(sub1.joinpath(conf1.name))
        conf2 = testrunnerer.makeconftest(
            """
            import testrunner
            class MyModule2(testrunner.Module):
                pass
            def testrunner_collect_file(file_path, parent):
                if file_path.suffix == ".py":
                    return MyModule2.from_parent(path=file_path, parent=parent)
        """
        )
        conf2.replace(sub2.joinpath(conf2.name))
        p = testrunnerer.makepyfile("def test_x(): pass")
        shutil.copy(p, sub1.joinpath(p.name))
        shutil.copy(p, sub2.joinpath(p.name))
        result = testrunnerer.runtestrunner("--co")
        result.stdout.fnmatch_lines(["*MyModule1*", "*MyModule2*", "*test_x*"])


class TestSession:
    def test_collect_topdir(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile("def test_func(): pass")
        id = "::".join([p.name, "test_func"])
        # XXX migrate to collectonly? (see below)
        config = testrunnerer.parseconfig(id)
        topdir = testrunnerer.path
        rcol = Session.from_config(config)
        assert topdir == rcol.path
        # rootid = rcol.nodeid
        # root2 = rcol.perform_collect([rcol.nodeid], genitems=False)[0]
        # assert root2 == rcol, rootid
        colitems = rcol.perform_collect([rcol.nodeid], genitems=False)
        assert len(colitems) == 1
        assert colitems[0].path == topdir

    def get_reported_items(self, hookrec: HookRecorder) -> list[Item]:
        """Return testrunner.Item instances reported by the testrunner_collectreport hook"""
        calls = hookrec.getcalls("testrunner_collectreport")
        return [
            x
            for call in calls
            for x in call.report.result
            if isinstance(x, testrunner.Item)
        ]

    def test_collect_protocol_single_function(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile("def test_func(): pass")
        id = "::".join([p.name, "test_func"])
        items, hookrec = testrunnerer.inline_genitems(id)
        (item,) = items
        assert item.name == "test_func"
        newid = item.nodeid
        assert newid == id
        pprint.pprint(hookrec.calls)
        topdir = testrunnerer.path  # noqa: F841
        hookrec.assert_contains(
            [
                ("testrunner_collectstart", "collector.path == topdir"),
                ("testrunner_make_collect_report", "collector.path == topdir"),
                ("testrunner_collectstart", "collector.path == p"),
                ("testrunner_make_collect_report", "collector.path == p"),
                ("testrunner_pycollect_makeitem", "name == 'test_func'"),
                ("testrunner_collectreport", "report.result[0].name == 'test_func'"),
            ]
        )
        # ensure we are reporting the collection of the single test item (#2464)
        assert [x.name for x in self.get_reported_items(hookrec)] == ["test_func"]

    def test_collect_protocol_method(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            class TestClass(object):
                def test_method(self):
                    pass
        """
        )
        normid = p.name + "::TestClass::test_method"
        for id in [p.name, p.name + "::TestClass", normid]:
            items, hookrec = testrunnerer.inline_genitems(id)
            assert len(items) == 1
            assert items[0].name == "test_method"
            newid = items[0].nodeid
            assert newid == normid
            # ensure we are reporting the collection of the single test item (#2464)
            assert [x.name for x in self.get_reported_items(hookrec)] == ["test_method"]

    def test_collect_custom_nodes_multi_id(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile("def test_func(): pass")
        testrunnerer.makeconftest(
            f"""
            import testrunner
            class SpecialItem(testrunner.Item):
                def runtest(self):
                    return # ok
            class SpecialFile(testrunner.File):
                def collect(self):
                    return [SpecialItem.from_parent(name="check", parent=self)]
            def testrunner_collect_file(file_path, parent):
                if file_path.name == {p.name!r}:
                    return SpecialFile.from_parent(path=file_path, parent=parent)
        """
        )
        id = p.name

        items, hookrec = testrunnerer.inline_genitems(id)
        pprint.pprint(hookrec.calls)
        assert len(items) == 2
        hookrec.assert_contains(
            [
                ("testrunner_collectstart", "collector.path == collector.session.path"),
                (
                    "testrunner_collectstart",
                    "collector.__class__.__name__ == 'SpecialFile'",
                ),
                ("testrunner_collectstart", "collector.__class__.__name__ == 'Module'"),
                ("testrunner_pycollect_makeitem", "name == 'test_func'"),
                ("testrunner_collectreport", "report.nodeid.startswith(p.name)"),
            ]
        )
        assert len(self.get_reported_items(hookrec)) == 2

    def test_collect_subdir_event_ordering(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile("def test_func(): pass")
        aaa = testrunnerer.mkpydir("aaa")
        test_aaa = aaa.joinpath("test_aaa.py")
        p.replace(test_aaa)

        items, hookrec = testrunnerer.inline_genitems()
        assert len(items) == 1
        pprint.pprint(hookrec.calls)
        hookrec.assert_contains(
            [
                ("testrunner_collectstart", "collector.path == test_aaa"),
                ("testrunner_pycollect_makeitem", "name == 'test_func'"),
                ("testrunner_collectreport", "report.nodeid.startswith('aaa/test_aaa.py')"),
            ]
        )

    def test_collect_two_commandline_args(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile("def test_func(): pass")
        aaa = testrunnerer.mkpydir("aaa")
        bbb = testrunnerer.mkpydir("bbb")
        test_aaa = aaa.joinpath("test_aaa.py")
        shutil.copy(p, test_aaa)
        test_bbb = bbb.joinpath("test_bbb.py")
        p.replace(test_bbb)

        id = "."

        items, hookrec = testrunnerer.inline_genitems(id)
        assert len(items) == 2
        pprint.pprint(hookrec.calls)
        hookrec.assert_contains(
            [
                ("testrunner_collectstart", "collector.path == test_aaa"),
                ("testrunner_pycollect_makeitem", "name == 'test_func'"),
                ("testrunner_collectreport", "report.nodeid == 'aaa/test_aaa.py'"),
                ("testrunner_collectstart", "collector.path == test_bbb"),
                ("testrunner_pycollect_makeitem", "name == 'test_func'"),
                ("testrunner_collectreport", "report.nodeid == 'bbb/test_bbb.py'"),
            ]
        )

    def test_serialization_byid(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile("def test_func(): pass")
        items, _hookrec = testrunnerer.inline_genitems()
        assert len(items) == 1
        (item,) = items
        items2, _hookrec = testrunnerer.inline_genitems(item.nodeid)
        (item2,) = items2
        assert item2.name == item.name
        assert item2.path == item.path

    def test_find_byid_without_instance_parents(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            class TestClass(object):
                def test_method(self):
                    pass
        """
        )
        arg = p.name + "::TestClass::test_method"
        items, hookrec = testrunnerer.inline_genitems(arg)
        assert len(items) == 1
        (item,) = items
        assert item.nodeid.endswith("TestClass::test_method")
        # ensure we are reporting the collection of the single test item (#2464)
        assert [x.name for x in self.get_reported_items(hookrec)] == ["test_method"]

    def test_collect_parametrized_order(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.mark.parametrize('i', [0, 1, 2])
            def test_param(i): ...
            """
        )
        items, _hookrec = testrunnerer.inline_genitems(f"{p}::test_param")
        assert len(items) == 3
        assert [item.nodeid for item in items] == [
            "test_collect_parametrized_order.py::test_param[0]",
            "test_collect_parametrized_order.py::test_param[1]",
            "test_collect_parametrized_order.py::test_param[2]",
        ]


class Test_getinitialnodes:
    def test_global_file(self, testrunnerer: Testrunnerer) -> None:
        tmp_path = testrunnerer.path
        x = ensure_file(tmp_path / "x.py")
        config = testrunnerer.parseconfigure(x)
        col = testrunnerer.getnode(config, x)
        assert isinstance(col, testrunner.Module)
        assert col.name == "x.py"
        assert col.parent is not None
        assert col.parent.parent is not None
        assert col.parent.parent.parent is None
        for parent in col.listchain():
            assert parent.config is config

    def test_pkgfile(self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch) -> None:
        """Verify nesting when a module is within a package.
        The parent chain should match: Module<x.py> -> Package<subdir> -> Session.
            Session's parent should always be None.
        """
        tmp_path = testrunnerer.path
        subdir = tmp_path.joinpath("subdir")
        x = ensure_file(subdir / "x.py")
        ensure_file(subdir / "__init__.py")
        with monkeypatch.context() as mp:
            mp.chdir(subdir)
            config = testrunnerer.parseconfigure(x)
        col = testrunnerer.getnode(config, x)
        assert col is not None
        assert col.name == "x.py"
        assert isinstance(col, testrunner.Module)
        assert isinstance(col.parent, testrunner.Package)
        assert isinstance(col.parent.parent, testrunner.Session)
        # session is batman (has no parents)
        assert col.parent.parent.parent is None
        for parent in col.listchain():
            assert parent.config is config


class Test_genitems:
    def test_check_collect_hashes(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            def test_1():
                pass

            def test_2():
                pass
        """
        )
        shutil.copy(p, p.parent / (p.stem + "2" + ".py"))
        items, _reprec = testrunnerer.inline_genitems(p.parent)
        assert len(items) == 4
        for numi, i in enumerate(items):
            for numj, j in enumerate(items):
                if numj != numi:
                    assert hash(i) != hash(j)
                    assert i != j

    def test_example_items1(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner

            def testone():
                pass

            class TestX(object):
                def testmethod_one(self):
                    pass

            class TestY(TestX):
                @testrunner.mark.parametrize("arg0", [".["])
                def testmethod_two(self, arg0):
                    pass
        """
        )
        items, _reprec = testrunnerer.inline_genitems(p)
        assert len(items) == 4
        assert items[0].name == "testone"
        assert items[1].name == "testmethod_one"
        assert items[2].name == "testmethod_one"
        assert items[3].name == "testmethod_two[.[]"

        # let's also test getmodpath here
        assert items[0].getmodpath() == "testone"  # type: ignore[attr-defined]
        assert items[1].getmodpath() == "TestX.testmethod_one"  # type: ignore[attr-defined]
        assert items[2].getmodpath() == "TestY.testmethod_one"  # type: ignore[attr-defined]
        # PR #6202: Fix incorrect result of getmodpath method. (Resolves issue #6189)
        assert items[3].getmodpath() == "TestY.testmethod_two[.[]"  # type: ignore[attr-defined]

        s = items[0].getmodpath(stopatmodule=False)  # type: ignore[attr-defined]
        assert s.endswith("test_example_items1.testone")
        print(s)

    def test_classmethod_is_discovered(self, testrunnerer: Testrunnerer) -> None:
        """Test that classmethods are discovered"""
        p = testrunnerer.makepyfile(
            """
            class TestCase:
                @classmethod
                def test_classmethod(cls) -> None:
                    pass
            """
        )
        items, _reprec = testrunnerer.inline_genitems(p)
        ids = [x.getmodpath() for x in items]  # type: ignore[attr-defined]
        assert ids == ["TestCase.test_classmethod"]

    def test_class_and_functions_discovery_using_glob(self, testrunnerer: Testrunnerer) -> None:
        """Test that Python_classes and Python_functions config options work
        as prefixes and glob-like patterns (#600)."""
        testrunnerer.makeini(
            """
            [testrunner]
            python_classes = *Suite Test
            python_functions = *_test test
        """
        )
        p = testrunnerer.makepyfile(
            """
            class MyTestSuite(object):
                def x_test(self):
                    pass

            class TestCase(object):
                def test_y(self):
                    pass
        """
        )
        items, _reprec = testrunnerer.inline_genitems(p)
        ids = [x.getmodpath() for x in items]  # type: ignore[attr-defined]
        assert ids == ["MyTestSuite.x_test", "TestCase.test_y"]


def test_matchnodes_two_collections_same_file(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
        import testrunner
        def testrunner_configure(config):
            config.pluginmanager.register(Plugin2())

        class Plugin2(object):
            def testrunner_collect_file(self, file_path, parent):
                if file_path.suffix == ".abc":
                    return MyFile2.from_parent(path=file_path, parent=parent)

        def testrunner_collect_file(file_path, parent):
            if file_path.suffix == ".abc":
                return MyFile1.from_parent(path=file_path, parent=parent)

        class MyFile1(testrunner.File):
            def collect(self):
                yield Item1.from_parent(name="item1", parent=self)

        class MyFile2(testrunner.File):
            def collect(self):
                yield Item2.from_parent(name="item2", parent=self)

        class Item1(testrunner.Item):
            def runtest(self):
                pass

        class Item2(testrunner.Item):
            def runtest(self):
                pass
    """
    )
    p = testrunnerer.makefile(".abc", "")
    result = testrunnerer.runtestrunner()
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*2 passed*"])
    res = testrunnerer.runtestrunner(f"{p.name}::item2")
    res.stdout.fnmatch_lines(["*1 passed*"])


class TestNodeKeywords:
    def test_no_under(self, testrunnerer: Testrunnerer) -> None:
        modcol = testrunnerer.getmodulecol(
            """
            def test_pass(): pass
            def test_fail(): assert 0
        """
        )
        values = list(modcol.keywords)
        assert modcol.name in values
        for x in values:
            assert not x.startswith("_")
        assert modcol.name in repr(modcol.keywords)

    def test_issue345(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            def test_should_not_be_selected():
                assert False, 'I should not have been selected to run'

            def test___repr__():
                pass
        """
        )
        reprec = testrunnerer.inline_run("-k repr")
        reprec.assertoutcome(passed=1, failed=0)

    def test_keyword_matching_is_case_insensitive_by_default(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Check that selection via -k EXPRESSION is case-insensitive.

        Since markers are also added to the node keywords, they too can
        be matched without having to think about case sensitivity.

        """
        testrunnerer.makepyfile(
            """
            import testrunner

            def test_sPeCiFiCToPiC_1():
                assert True

            class TestSpecificTopic_2:
                def test(self):
                    assert True

            @testrunner.mark.sPeCiFiCToPic_3
            def test():
                assert True

            @testrunner.mark.sPeCiFiCToPic_4
            class Test:
                def test(self):
                    assert True

            def test_failing_5():
                assert False, "This should not match"

        """
        )
        num_matching_tests = 4
        for expression in ("specifictopic", "SPECIFICTOPIC", "SpecificTopic"):
            reprec = testrunnerer.inline_run("-k " + expression)
            reprec.assertoutcome(passed=num_matching_tests, failed=0)

    def test_duplicates_handled_correctly(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            _testrunner_mark = testrunner.mark.kw
            class TestClass:
                _testrunner_mark = testrunner.mark.kw
                def test_method(self): pass
                test_method.kw = 'method'
        """,
            "test_method",
        )
        assert item.parent is not None and item.parent.parent is not None
        item.parent.parent.keywords["kw"] = "class"

        assert item.keywords["kw"] == "method"
        assert len(item.keywords) == len(set(item.keywords))

    def test_unpacked_marks_added_to_keywords(self, testrunnerer: Testrunnerer) -> None:
        item = testrunnerer.getitem(
            """
            import testrunner
            _testrunner_mark = testrunner.mark.foo
            class TestClass:
                _testrunner_mark = testrunner.mark.bar
                def test_method(self): pass
                test_method._testrunner_mark = testrunner.mark.baz
        """,
            "test_method",
        )
        assert isinstance(item, testrunner.Function)
        cls = item.getparent(testrunner.Class)
        assert cls is not None
        mod = item.getparent(testrunner.Module)
        assert mod is not None

        assert item.keywords["foo"] == testrunner.mark.foo.mark
        assert item.keywords["bar"] == testrunner.mark.bar.mark
        assert item.keywords["baz"] == testrunner.mark.baz.mark

        assert cls.keywords["foo"] == testrunner.mark.foo.mark
        assert cls.keywords["bar"] == testrunner.mark.bar.mark
        assert "baz" not in cls.keywords

        assert mod.keywords["foo"] == testrunner.mark.foo.mark
        assert "bar" not in mod.keywords
        assert "baz" not in mod.keywords


class TestCollectDirectoryHook:
    def test_custom_directory_example(self, testrunnerer: Testrunnerer) -> None:
        """Verify the example from the customdirectory.rst doc."""
        testrunnerer.copy_example("customdirectory")

        reprec = testrunnerer.inline_run()

        reprec.assertoutcome(passed=2, failed=0)
        calls = reprec.getcalls("testrunner_collect_directory")
        assert len(calls) == 2
        assert calls[0].path == testrunnerer.path
        assert isinstance(calls[0].parent, testrunner.Session)
        assert calls[1].path == testrunnerer.path / "tests"
        assert isinstance(calls[1].parent, testrunner.Dir)

    def test_directory_ignored_if_none(self, testrunnerer: Testrunnerer) -> None:
        """If the (entire) hook returns None, it's OK, the directory is ignored."""
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.hookimpl(wrapper=True)
            def testrunner_collect_directory():
                yield
                return None
            """,
        )
        testrunnerer.makepyfile(
            **{
                "tests/test_it.py": """
                    import testrunner

                    def test_it(): pass
                """,
            },
        )
        reprec = testrunnerer.inline_run()
        reprec.assertoutcome(passed=0, failed=0)


COLLECTION_ERROR_PY_FILES = dict(
    test_01_failure="""
        def test_1():
            assert False
        """,
    test_02_import_error="""
        import asdfasdfasdf
        def test_2():
            assert True
        """,
    test_03_import_error="""
        import asdfasdfasdf
        def test_3():
            assert True
    """,
    test_04_success="""
        def test_4():
            assert True
    """,
)


def test_exit_on_collection_error(testrunnerer: Testrunnerer) -> None:
    """Verify that all collection errors are collected and no tests executed"""
    testrunnerer.makepyfile(**COLLECTION_ERROR_PY_FILES)

    res = testrunnerer.runtestrunner()
    assert res.ret == 2

    res.stdout.fnmatch_lines(
        [
            "collected 2 items / 2 errors",
            "*ERROR collecting test_02_import_error.py*",
            "*No module named *asdfa*",
            "*ERROR collecting test_03_import_error.py*",
            "*No module named *asdfa*",
        ]
    )


def test_exit_on_collection_with_maxfail_smaller_than_n_errors(
    testrunnerer: Testrunnerer,
) -> None:
    """
    Verify collection is aborted once maxfail errors are encountered ignoring
    further modules which would cause more collection errors.
    """
    testrunnerer.makepyfile(**COLLECTION_ERROR_PY_FILES)

    res = testrunnerer.runtestrunner("--maxfail=1")
    assert res.ret == 1
    res.stdout.fnmatch_lines(
        [
            "collected 1 item / 1 error",
            "*ERROR collecting test_02_import_error.py*",
            "*No module named *asdfa*",
            "*! stopping after 1 failures !*",
            "*= 1 error in *",
        ]
    )
    res.stdout.no_fnmatch_line("*test_03*")


def test_exit_on_collection_with_maxfail_bigger_than_n_errors(
    testrunnerer: Testrunnerer,
) -> None:
    """
    Verify the test run aborts due to collection errors even if maxfail count of
    errors was not reached.
    """
    testrunnerer.makepyfile(**COLLECTION_ERROR_PY_FILES)

    res = testrunnerer.runtestrunner("--maxfail=4")
    assert res.ret == 2
    res.stdout.fnmatch_lines(
        [
            "collected 2 items / 2 errors",
            "*ERROR collecting test_02_import_error.py*",
            "*No module named *asdfa*",
            "*ERROR collecting test_03_import_error.py*",
            "*No module named *asdfa*",
            "*! Interrupted: 2 errors during collection !*",
            "*= 2 errors in *",
        ]
    )


def test_continue_on_collection_errors(testrunnerer: Testrunnerer) -> None:
    """
    Verify tests are executed even when collection errors occur when the
    --continue-on-collection-errors flag is set
    """
    testrunnerer.makepyfile(**COLLECTION_ERROR_PY_FILES)

    res = testrunnerer.runtestrunner("--continue-on-collection-errors")
    assert res.ret == 1

    res.stdout.fnmatch_lines(
        ["collected 2 items / 2 errors", "*1 failed, 1 passed, 2 errors*"]
    )


def test_continue_on_collection_errors_maxfail(testrunnerer: Testrunnerer) -> None:
    """
    Verify tests are executed even when collection errors occur and that maxfail
    is honoured (including the collection error count).
    4 tests: 2 collection errors + 1 failure + 1 success
    test_4 is never executed because the test run is with --maxfail=3 which
    means it is interrupted after the 2 collection errors + 1 failure.
    """
    testrunnerer.makepyfile(**COLLECTION_ERROR_PY_FILES)

    res = testrunnerer.runtestrunner("--continue-on-collection-errors", "--maxfail=3")
    assert res.ret == 1

    res.stdout.fnmatch_lines(["collected 2 items / 2 errors", "*1 failed, 2 errors*"])


def test_fixture_scope_sibling_conftests(testrunnerer: Testrunnerer) -> None:
    """Regression test case for https://github.com/jacksonsr451/test-runner/issues/2836"""
    foo_path = testrunnerer.mkdir("foo")
    foo_path.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            import testrunner
            @testrunner.fixture
            def fix():
                return 1
            """
        ),
        encoding="utf-8",
    )
    foo_path.joinpath("test_foo.py").write_text(
        "def test_foo(fix): assert fix == 1", encoding="utf-8"
    )

    # Tests in `food/` should not see the conftest fixture from `foo/`
    food_path = testrunnerer.mkpydir("food")
    food_path.joinpath("test_food.py").write_text(
        "def test_food(fix): assert fix == 1", encoding="utf-8"
    )

    res = testrunnerer.runtestrunner()
    assert res.ret == 1

    res.stdout.fnmatch_lines(
        [
            "*ERROR at setup of test_food*",
            "E*fixture 'fix' not found",
            "*1 passed, 1 error*",
        ]
    )


def test_collect_init_tests(testrunnerer: Testrunnerer) -> None:
    """Check that we collect files from __init__.py files when they patch the 'python_files' (#3773)"""
    p = testrunnerer.copy_example("collect/collect_init_tests")
    result = testrunnerer.runtestrunner(p, "--collect-only")
    result.stdout.fnmatch_lines(
        [
            "collected 2 items",
            "<Dir *>",
            "  <Package tests>",
            "    <Module __init__.py>",
            "      <Function test_init>",
            "    <Module test_foo.py>",
            "      <Function test_foo>",
        ]
    )
    result = testrunnerer.runtestrunner("./tests", "--collect-only")
    result.stdout.fnmatch_lines(
        [
            "collected 2 items",
            "<Dir *>",
            "  <Package tests>",
            "    <Module __init__.py>",
            "      <Function test_init>",
            "    <Module test_foo.py>",
            "      <Function test_foo>",
        ]
    )
    # Ignores duplicates with "." and pkginit (#4310).
    result = testrunnerer.runtestrunner("./tests", ".", "--collect-only")
    result.stdout.fnmatch_lines(
        [
            "collected 2 items",
            "<Dir *>",
            "  <Package tests>",
            "    <Module __init__.py>",
            "      <Function test_init>",
            "    <Module test_foo.py>",
            "      <Function test_foo>",
        ]
    )
    # Same as before, but different order.
    result = testrunnerer.runtestrunner(".", "tests", "--collect-only")
    result.stdout.fnmatch_lines(
        [
            "collected 2 items",
            "<Dir *>",
            "  <Package tests>",
            "    <Module __init__.py>",
            "      <Function test_init>",
            "    <Module test_foo.py>",
            "      <Function test_foo>",
        ]
    )
    result = testrunnerer.runtestrunner("./tests/test_foo.py", "--collect-only")
    result.stdout.fnmatch_lines(
        [
            "<Dir *>",
            "  <Package tests>",
            "    <Module test_foo.py>",
            "      <Function test_foo>",
        ]
    )
    result.stdout.no_fnmatch_line("*test_init*")
    result = testrunnerer.runtestrunner("./tests/__init__.py", "--collect-only")
    result.stdout.fnmatch_lines(
        [
            "<Dir *>",
            "  <Package tests>",
            "    <Module __init__.py>",
            "      <Function test_init>",
        ]
    )
    result.stdout.no_fnmatch_line("*test_foo*")


def test_collect_invalid_signature_message(testrunnerer: Testrunnerer) -> None:
    """Check that we issue a proper message when we can't determine the signature of a test
    function (#4026).
    """
    testrunnerer.makepyfile(
        """
        import testrunner

        class TestCase:
            @testrunner.fixture
            def fix():
                pass
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        ["Could not determine arguments of *.fix *: invalid method signature"]
    )


def test_collect_handles_raising_on_dunder_class(testrunnerer: Testrunnerer) -> None:
    """Handle proxy classes like Django's LazySettings that might raise on
    ``isinstance`` (#4266).
    """
    testrunnerer.makepyfile(
        """
        class ImproperlyConfigured(Exception):
            pass

        class RaisesOnGetAttr(object):
            def raises(self):
                raise ImproperlyConfigured

            __class__ = property(raises)

        raises = RaisesOnGetAttr()


        def test_1():
            pass
    """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_collect_with_chdir_during_import(testrunnerer: Testrunnerer) -> None:
    subdir = testrunnerer.mkdir("sub")
    testrunnerer.path.joinpath("conftest.py").write_text(
        textwrap.dedent(
            f"""
            import os
            os.chdir({str(subdir)!r})
            """
        ),
        encoding="utf-8",
    )
    testrunnerer.makepyfile(
        f"""
        def test_1():
            import os
            assert os.getcwd() == {str(subdir)!r}
        """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["*1 passed in*"])
    assert result.ret == 0

    # Handles relative testpaths.
    testrunnerer.makeini(
        """
        [testrunner]
        testpaths = .
    """
    )
    result = testrunnerer.runtestrunner("--collect-only")
    result.stdout.fnmatch_lines(["collected 1 item"])


def test_collect_pyargs_with_testpaths(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    testmod = testrunnerer.mkdir("testmod")
    # NOTE: __init__.py is not collected since it does not match python_files.
    testmod.joinpath("__init__.py").write_text(
        "def test_func(): pass", encoding="utf-8"
    )
    testmod.joinpath("test_file.py").write_text(
        "def test_func(): pass", encoding="utf-8"
    )

    root = testrunnerer.mkdir("root")
    root.joinpath("testrunner.ini").write_text(
        textwrap.dedent(
            """
        [testrunner]
        addopts = --pyargs
        testpaths = testmod
    """
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(testrunnerer.path), prepend=os.pathsep)
    with monkeypatch.context() as mp:
        mp.chdir(root)
        result = testrunnerer.runtestrunner_subprocess()
    result.assert_outcomes(passed=1)


def test_initial_conftests_with_testpaths(testrunnerer: Testrunnerer) -> None:
    """The testpaths config option should load conftests in those paths as 'initial' (#10987)."""
    p = testrunnerer.mkdir("some_path")
    p.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """
            def testrunner_sessionstart(session):
                raise Exception("testrunner_sessionstart hook successfully run")
            """
        ),
        encoding="utf-8",
    )
    testrunnerer.makeini(
        """
        [testrunner]
        testpaths = some_path
        """
    )

    # No command line args - falls back to testpaths.
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.INTERNAL_ERROR
    result.stdout.fnmatch_lines(
        "INTERNALERROR* Exception: testrunner_sessionstart hook successfully run"
    )

    # No fallback.
    result = testrunnerer.runtestrunner(".")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_large_option_breaks_initial_conftests(testrunnerer: Testrunnerer) -> None:
    """Long option values do not break initial conftests handling (#10169)."""
    option_value = "x" * 1024 * 1000
    testrunnerer.makeconftest(
        """
        def testrunner_addoption(parser):
            parser.addoption("--xx", default=None)
        """
    )
    testrunnerer.makepyfile(
        f"""
        def test_foo(request):
            assert request.config.getoption("xx") == {option_value!r}
        """
    )
    result = testrunnerer.runtestrunner(f"--xx={option_value}")
    assert result.ret == 0


def test_collect_symlink_file_arg(testrunnerer: Testrunnerer) -> None:
    """Collect a direct symlink works even if it does not match python_files (#4325)."""
    real = testrunnerer.makepyfile(
        real="""
        def test_nodeid(request):
            assert request.node.nodeid == "symlink.py::test_nodeid"
        """
    )
    symlink = testrunnerer.path.joinpath("symlink.py")
    symlink_or_skip(real, symlink)
    result = testrunnerer.runtestrunner("-v", symlink)
    result.stdout.fnmatch_lines(["symlink.py::test_nodeid PASSED*", "*1 passed in*"])
    assert result.ret == 0


def test_collect_symlink_out_of_tree(testrunnerer: Testrunnerer) -> None:
    """Test collection of symlink via out-of-tree rootdir."""
    sub = testrunnerer.mkdir("sub")
    real = sub.joinpath("test_real.py")
    real.write_text(
        textwrap.dedent(
            """
        def test_nodeid(request):
            # Should not contain sub/ prefix.
            assert request.node.nodeid == "test_real.py::test_nodeid"
        """
        ),
        encoding="utf-8",
    )

    out_of_tree = testrunnerer.mkdir("out_of_tree")
    symlink_to_sub = out_of_tree.joinpath("symlink_to_sub")
    symlink_or_skip(sub, symlink_to_sub)
    os.chdir(sub)
    result = testrunnerer.runtestrunner("-vs", f"--rootdir={sub}", symlink_to_sub)
    result.stdout.fnmatch_lines(
        [
            # Should not contain "sub/"!
            "test_real.py::test_nodeid PASSED"
        ]
    )
    assert result.ret == 0


def test_collect_symlink_dir(testrunnerer: Testrunnerer) -> None:
    """A symlinked directory is collected."""
    dir = testrunnerer.mkdir("dir")
    dir.joinpath("test_it.py").write_text("def test_it(): pass", "utf-8")
    symlink_or_skip(testrunnerer.path.joinpath("symlink_dir"), dir)
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=2)


def test_collectignore_via_conftest(testrunnerer: Testrunnerer) -> None:
    """collect_ignore in parent conftest skips importing child (issue #4592)."""
    tests = testrunnerer.mkpydir("tests")
    tests.joinpath("conftest.py").write_text(
        "collect_ignore = ['ignore_me']", encoding="utf-8"
    )

    ignore_me = tests.joinpath("ignore_me")
    ignore_me.mkdir()
    ignore_me.joinpath("__init__.py").touch()
    ignore_me.joinpath("conftest.py").write_text(
        "assert 0, 'should_not_be_called'", encoding="utf-8"
    )

    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_collect_pkg_init_and_file_in_args(testrunnerer: Testrunnerer) -> None:
    subdir = testrunnerer.mkdir("sub")
    init = subdir.joinpath("__init__.py")
    init.write_text("def test_init(): pass", encoding="utf-8")
    p = subdir.joinpath("test_file.py")
    p.write_text("def test_file(): pass", encoding="utf-8")

    # Just the package directory, the __init__.py module is filtered out.
    result = testrunnerer.runtestrunner("-v", subdir)
    result.stdout.fnmatch_lines(
        [
            "sub/test_file.py::test_file PASSED*",
            "*1 passed in*",
        ]
    )

    # But it's included if specified directly.
    result = testrunnerer.runtestrunner("-v", init, p)
    result.stdout.fnmatch_lines(
        [
            "sub/__init__.py::test_init PASSED*",
            "sub/test_file.py::test_file PASSED*",
            "*2 passed in*",
        ]
    )

    # Or if the pattern allows it.
    result = testrunnerer.runtestrunner("-v", "-o", "python_files=*.py", subdir)
    result.stdout.fnmatch_lines(
        [
            "sub/__init__.py::test_init PASSED*",
            "sub/test_file.py::test_file PASSED*",
            "*2 passed in*",
        ]
    )


def test_collect_pkg_init_only(testrunnerer: Testrunnerer) -> None:
    subdir = testrunnerer.mkdir("sub")
    init = subdir.joinpath("__init__.py")
    init.write_text("def test_init(): pass", encoding="utf-8")

    result = testrunnerer.runtestrunner(subdir)
    result.stdout.fnmatch_lines(["*no tests ran in*"])

    result = testrunnerer.runtestrunner("-v", init)
    result.stdout.fnmatch_lines(["sub/__init__.py::test_init PASSED*", "*1 passed in*"])

    result = testrunnerer.runtestrunner("-v", "-o", "python_files=*.py", subdir)
    result.stdout.fnmatch_lines(["sub/__init__.py::test_init PASSED*", "*1 passed in*"])


@testrunner.mark.parametrize("use_pkg", (True, False))
def test_collect_sub_with_symlinks(use_pkg: bool, testrunnerer: Testrunnerer) -> None:
    """Collection works with symlinked files and broken symlinks"""
    sub = testrunnerer.mkdir("sub")
    if use_pkg:
        sub.joinpath("__init__.py").touch()
    sub.joinpath("test_file.py").write_text("def test_file(): pass", encoding="utf-8")

    # Create a broken symlink.
    symlink_or_skip("test_doesnotexist.py", sub.joinpath("test_broken.py"))

    # Symlink that gets collected.
    symlink_or_skip("test_file.py", sub.joinpath("test_symlink.py"))

    result = testrunnerer.runtestrunner("-v", str(sub))
    result.stdout.fnmatch_lines(
        [
            "sub/test_file.py::test_file PASSED*",
            "sub/test_symlink.py::test_file PASSED*",
            "*2 passed in*",
        ]
    )


def test_collector_respects_tbstyle(testrunnerer: Testrunnerer) -> None:
    p1 = testrunnerer.makepyfile("assert 0")
    result = testrunnerer.runtestrunner(p1, "--tb=native")
    assert result.ret == ExitCode.INTERRUPTED
    result.stdout.fnmatch_lines(
        [
            "*_ ERROR collecting test_collector_respects_tbstyle.py _*",
            "Traceback (most recent call last):",
            '  File "*/test_collector_respects_tbstyle.py", line 1, in <module>',
            "    assert 0",
            "AssertionError: assert 0",
            "*! Interrupted: 1 error during collection !*",
            "*= 1 error in *",
        ]
    )


def test_does_not_eagerly_collect_packages(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile("def test(): pass")
    pydir = testrunnerer.mkpydir("foopkg")
    pydir.joinpath("__init__.py").write_text("assert False", encoding="utf-8")
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.OK


def test_does_not_put_src_on_path(testrunnerer: Testrunnerer) -> None:
    # `src` is not on sys.path so it should not be importable
    ensure_file(testrunnerer.path / "src/nope/__init__.py")
    testrunnerer.makepyfile(
        "import testrunner\n"
        "def test():\n"
        "    with testrunner.raises(ImportError):\n"
        "        import nope\n"
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.OK


def test_fscollector_from_parent(testrunnerer: Testrunnerer, request: FixtureRequest) -> None:
    """Ensure File.from_parent can forward custom arguments to the constructor.

    Context: https://github.com/jacksonsr451/test-runner-cpp/pull/47
    """

    class MyCollector(testrunner.File):
        def __init__(self, *k, x, **kw):
            super().__init__(*k, **kw)
            self.x = x

        def collect(self):
            raise NotImplementedError()

    collector = MyCollector.from_parent(
        parent=request.session, path=testrunnerer.path / "foo", x=10
    )
    assert collector.x == 10


def test_class_from_parent(request: FixtureRequest) -> None:
    """Ensure Class.from_parent can forward custom arguments to the constructor."""

    class MyCollector(testrunner.Class):
        def __init__(self, name, parent, x):
            super().__init__(name, parent)
            self.x = x

        @classmethod
        def from_parent(cls, parent, *, name, x):  # type: ignore[override]
            return super().from_parent(parent=parent, name=name, x=x)

    collector = MyCollector.from_parent(parent=request.session, name="foo", x=10)
    assert collector.x == 10


class TestImportModeImportlib:
    def test_collect_duplicate_names(self, testrunnerer: Testrunnerer) -> None:
        """--import-mode=importlib can import modules with same names that are not in packages."""
        testrunnerer.makepyfile(
            **{
                "tests_a/test_foo.py": "def test_foo1(): pass",
                "tests_b/test_foo.py": "def test_foo2(): pass",
            }
        )
        result = testrunnerer.runtestrunner("-v", "--import-mode=importlib")
        result.stdout.fnmatch_lines(
            [
                "tests_a/test_foo.py::test_foo1 *",
                "tests_b/test_foo.py::test_foo2 *",
                "* 2 passed in *",
            ]
        )

    def test_conftest(self, testrunnerer: Testrunnerer) -> None:
        """Directory containing conftest modules are not put in sys.path as a side-effect of
        importing them."""
        tests_dir = testrunnerer.path.joinpath("tests")
        testrunnerer.makepyfile(
            **{
                "tests/conftest.py": "",
                "tests/test_foo.py": f"""
                import sys
                def test_check():
                    assert r"{tests_dir}" not in sys.path
                """,
            }
        )
        result = testrunnerer.runtestrunner("-v", "--import-mode=importlib")
        result.stdout.fnmatch_lines(["* 1 passed in *"])

    def setup_conftest_and_foo(self, testrunnerer: Testrunnerer) -> None:
        """Setup a tests directory to be used to test if modules in that directory can be imported
        due to side-effects of --import-mode or not."""
        testrunnerer.makepyfile(
            **{
                "tests/conftest.py": "",
                "tests/foo.py": """
                    def foo(): return 42
                """,
                "tests/test_foo.py": """
                    def test_check():
                        from foo import foo
                        assert foo() == 42
                """,
            }
        )

    def test_modules_importable_as_side_effect(self, testrunnerer: Testrunnerer) -> None:
        """In import-modes `prepend` and `append`, we are able to import modules from directories
        containing conftest.py files due to the side effect of changing sys.path."""
        self.setup_conftest_and_foo(testrunnerer)
        result = testrunnerer.runtestrunner("-v", "--import-mode=prepend")
        result.stdout.fnmatch_lines(["* 1 passed in *"])

    def test_modules_not_importable_as_side_effect(self, testrunnerer: Testrunnerer) -> None:
        """In import-mode `importlib`, modules in directories containing conftest.py are not
        importable, as don't change sys.path or sys.modules as side effect of importing
        the conftest.py file.
        """
        self.setup_conftest_and_foo(testrunnerer)
        result = testrunnerer.runtestrunner("-v", "--import-mode=importlib")
        result.stdout.fnmatch_lines(
            [
                "*ModuleNotFoundError: No module named 'foo'",
                "tests?test_foo.py:2: ModuleNotFoundError",
                "* 1 failed in *",
            ]
        )

    def test_using_python_path(self, testrunnerer: Testrunnerer) -> None:
        """
        Dummy modules created by insert_missing_modules should not get in
        the way of modules that could be imported via python path (#9645).
        """
        testrunnerer.makeini(
            """
            [testrunner]
            pythonpath = .
            addopts = --import-mode importlib
            """
        )
        testrunnerer.makepyfile(
            **{
                "tests/__init__.py": "",
                "tests/conftest.py": "",
                "tests/subpath/__init__.py": "",
                "tests/subpath/helper.py": "",
                "tests/subpath/test_something.py": """
                import tests.subpath.helper

                def test_something():
                    assert True
                """,
            }
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines("*1 passed in*")


def test_does_not_crash_on_error_from_decorated_function(testrunnerer: Testrunnerer) -> None:
    """Regression test for an issue around bad exception formatting due to
    assertion rewriting mangling lineno's (#4984)."""
    testrunnerer.makepyfile(
        """
        @testrunner.fixture
        def a(): return 4
        """
    )
    result = testrunnerer.runtestrunner()
    # Not INTERNAL_ERROR
    assert result.ret == ExitCode.INTERRUPTED


def test_does_not_crash_on_recursive_symlink(testrunnerer: Testrunnerer) -> None:
    """Regression test for an issue around recursive symlinks (#7951)."""
    symlink_or_skip("recursive", testrunnerer.path.joinpath("recursive"))
    testrunnerer.makepyfile(
        """
        def test_foo(): assert True
        """
    )
    result = testrunnerer.runtestrunner()

    assert result.ret == ExitCode.OK
    assert result.parseoutcomes() == {"passed": 1}


@testrunner.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
def test_collect_short_file_windows(testrunnerer: Testrunnerer) -> None:
    """Reproducer for #11895: short paths not collected on Windows."""
    short_path = tempfile.mkdtemp()
    if "~" not in short_path:  # pragma: no cover
        if running_on_ci():
            # On CI, we are expecting that under the current GitHub actions configuration,
            # tempfile.mkdtemp() is producing short paths, so we want to fail to prevent
            # this from silently changing without us noticing.
            testrunner.fail(
                f"tempfile.mkdtemp() failed to produce a short path on CI: {short_path}"
            )
        else:
            # We want to skip failing this test locally in this situation because
            # depending on the local configuration tempfile.mkdtemp() might not produce a short path:
            # For example, user might have configured %TEMP% exactly to avoid generating short paths.
            testrunner.skip(
                f"tempfile.mkdtemp() failed to produce a short path: {short_path}, skipping"
            )

    test_file = Path(short_path).joinpath("test_collect_short_file_windows.py")
    test_file.write_text("def test(): pass", encoding="UTF-8")
    result = testrunnerer.runtestrunner(short_path)
    assert result.parseoutcomes() == {"passed": 1}


def test_collect_short_file_windows_multi_level_symlink(
    testrunnerer: Testrunnerer,
    request: FixtureRequest,
) -> None:
    """Regression test for multi-level Windows short-path comparison with
    symlinks.

    Previously, when matching collection arguments against collected nodes on
    Windows, the short path fallback resolved symlinks. With a chain a -> b ->
    target, comparing 'a' against 'b' would incorrectly succeed because both
    resolved to 'target', which could cause incorrect matching or duplicate
    collection.
    """
    # Prepare target directory with a test file.
    short_path = Path(tempfile.mkdtemp())
    request.addfinalizer(lambda: shutil.rmtree(short_path, ignore_errors=True))
    target = short_path / "target"
    target.mkdir()
    (target / "test_chain.py").write_text("def test_chain(): pass", encoding="UTF-8")

    # Create multi-level symlink chain: a -> b -> target.
    b = short_path / "b"
    a = short_path / "a"
    symlink_or_skip(target, b, target_is_directory=True)
    symlink_or_skip(b, a, target_is_directory=True)

    # Collect via the first symlink; should find exactly one test.
    result = testrunnerer.runtestrunner(a)
    result.assert_outcomes(passed=1)

    # Collect via the intermediate symlink; also exactly one test.
    result = testrunnerer.runtestrunner(b)
    result.assert_outcomes(passed=1)


def test_pyargs_collection_tree(testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch) -> None:
    """When using `--pyargs`, the collection tree of a pyargs collection
    argument should only include parents in the import path, not up to confcutdir.

    Regression test for #11904.
    """
    site_packages = testrunnerer.path / "venv/lib/site-packages"
    site_packages.mkdir(parents=True)
    monkeypatch.syspath_prepend(site_packages)
    testrunnerer.makepyfile(
        **{
            "venv/lib/site-packages/pkg/__init__.py": "",
            "venv/lib/site-packages/pkg/sub/__init__.py": "",
            "venv/lib/site-packages/pkg/sub/test_it.py": "def test(): pass",
        }
    )

    result = testrunnerer.runtestrunner("--pyargs", "--collect-only", "pkg.sub.test_it")
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(
        [
            "<Package venv/lib/site-packages/pkg>",
            "  <Package sub>",
            "    <Module test_it.py>",
            "      <Function test>",
        ],
        consecutive=True,
    )

    # Now with an unrelated rootdir with unrelated files.
    monkeypatch.chdir(tempfile.gettempdir())

    result = testrunnerer.runtestrunner("--pyargs", "--collect-only", "pkg.sub.test_it")
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(
        [
            "<Package *pkg>",
            "  <Package sub>",
            "    <Module test_it.py>",
            "      <Function test>",
        ],
        consecutive=True,
    )


def test_do_not_collect_symlink_siblings(
    testrunnerer: Testrunnerer, tmp_path: Path, request: testrunner.FixtureRequest
) -> None:
    """
    Regression test for #12039: Do not collect from directories that are symlinks to other directories in the same path.

    The check for short paths under Windows via os.path.samefile, introduced in #11936, also finds the symlinked
    directory created by tmp_path/tmpdir.
    """
    # Use tmp_path because it creates a symlink with the name "current" next to the directory it creates.
    symlink_path = tmp_path.parent / (tmp_path.name[:-1] + "current")
    if not symlink_path.is_symlink():  # pragma: no cover
        testrunner.skip("Symlinks not supported in this environment")

    # Create test file.
    tmp_path.joinpath("test_foo.py").write_text("def test(): pass", encoding="UTF-8")

    # Ensure we collect it only once if we pass the tmp_path.
    result = testrunnerer.runtestrunner(tmp_path, "-sv")
    result.assert_outcomes(passed=1)

    # Ensure we collect it only once if we pass the symlinked directory.
    result = testrunnerer.runtestrunner(symlink_path, "-sv")
    result.assert_outcomes(passed=1)


@testrunner.mark.parametrize(
    "exception_class, msg",
    [
        (KeyboardInterrupt, "*!!! KeyboardInterrupt !!!*"),
        (SystemExit, "INTERNALERROR> SystemExit"),
    ],
)
def test_respect_system_exceptions(
    testrunnerer: Testrunnerer,
    exception_class: type[BaseException],
    msg: str,
):
    head = "Before exception"
    tail = "After exception"
    ensure_file(testrunnerer.path / "test_eggs.py").write_text(
        f"print('{head}')", encoding="UTF-8"
    )
    ensure_file(testrunnerer.path / "test_ham.py").write_text(
        f"raise {exception_class.__name__}()", encoding="UTF-8"
    )
    ensure_file(testrunnerer.path / "test_spam.py").write_text(
        f"print('{tail}')", encoding="UTF-8"
    )

    result = testrunnerer.runtestrunner_subprocess("-s")
    result.stdout.fnmatch_lines([f"*{head}*"])
    result.stdout.fnmatch_lines([msg])
    result.stdout.no_fnmatch_line(f"*{tail}*")


def test_yield_disallowed_in_tests(testrunnerer: Testrunnerer):
    """Ensure generator test functions with 'yield' fail collection (#12960)."""
    testrunnerer.makepyfile(
        """
        def test_with_yield():
            yield 1
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 2
    result.stdout.fnmatch_lines(
        ["*'yield' keyword is allowed in fixtures, but not in tests (test_with_yield)*"]
    )
    # Assert that no tests were collected
    result.stdout.fnmatch_lines(["*collected 0 items*"])


def test_annotations_deferred_future(testrunnerer: Testrunnerer):
    """Ensure stringified annotations don't raise any errors."""
    testrunnerer.makepyfile(
        """
        from __future__ import annotations
        import testrunner

        @testrunner.fixture
        def func() -> X: ...  # X is undefined

        def test_func():
            assert True
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*1 passed*"])


@testrunner.mark.skipif(
    sys.version_info < (3, 14), reason="Annotations are only skipped on 3.14+"
)
def test_annotations_deferred_314(testrunnerer: Testrunnerer):
    """Ensure annotation eval is deferred."""
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture
        def func() -> X: ...  # X is undefined

        def test_func():
            assert True
        """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*1 passed*"])


@testrunner.mark.parametrize("import_mode", ["prepend", "importlib", "append"])
def test_namespace_packages(testrunnerer: Testrunnerer, import_mode: str):
    testrunnerer.makeini(
        f"""
        [testrunner]
        consider_namespace_packages = true
        pythonpath = .
        python_files = *.py
        addopts = --import-mode {import_mode}
    """
    )
    testrunnerer.makepyfile(
        **{
            "pkg/module1.py": "def test_module1(): pass",
            "pkg/subpkg_namespace/module2.py": "def test_module1(): pass",
            "pkg/subpkg_regular/__init__.py": "",
            "pkg/subpkg_regular/module3": "def test_module3(): pass",
        }
    )

    # should collect when called with top-level package correctly
    result = testrunnerer.runtestrunner("--collect-only", "--pyargs", "pkg")
    result.stdout.fnmatch_lines(
        [
            "collected 3 items",
            "<Dir pkg>",
            "  <Module module1.py>",
            "    <Function test_module1>",
            "  <Dir subpkg_namespace>",
            "    <Module module2.py>",
            "      <Function test_module1>",
            "  <Package subpkg_regular>",
            "    <Module module3.py>",
            "      <Function test_module3>",
        ]
    )

    # should also work when called against a more specific subpackage/module
    result = testrunnerer.runtestrunner("--collect-only", "--pyargs", "pkg.subpkg_namespace")
    result.stdout.fnmatch_lines(
        [
            "collected 1 item",
            "<Dir pkg>",
            "  <Dir subpkg_namespace>",
            "    <Module module2.py>",
            "      <Function test_module1>",
        ]
    )

    result = testrunnerer.runtestrunner("--collect-only", "--pyargs", "pkg.subpkg_regular")
    result.stdout.fnmatch_lines(
        [
            "collected 1 item",
            "<Dir pkg>",
            "  <Package subpkg_regular>",
            "    <Module module3.py>",
            "      <Function test_module3>",
        ]
    )


class TestOverlappingCollectionArguments:
    """Test that overlapping collection arguments (e.g. `testrunner a/b a
    a/c::TestIt) are handled correctly (#12083)."""

    @testrunner.mark.parametrize("args", [("a", "a/b"), ("a/b", "a")])
    def test_parent_child(self, testrunnerer: Testrunnerer, args: tuple[str, ...]) -> None:
        """Test that 'testrunner a a/b' and `testrunner a/b a` collects all tests from 'a'."""
        testrunnerer.makepyfile(
            **{
                "a/test_a.py": """
                    def test_a1(): pass
                    def test_a2(): pass
                """,
                "a/b/test_b.py": """
                    def test_b1(): pass
                    def test_b2(): pass
                """,
            }
        )

        result = testrunnerer.runtestrunner("--collect-only", *args)

        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Dir a>",
                "    <Dir b>",
                "      <Module test_b.py>",
                "        <Function test_b1>",
                "        <Function test_b2>",
                "    <Module test_a.py>",
                "      <Function test_a1>",
                "      <Function test_a2>",
                "",
            ],
            consecutive=True,
        )

    def test_multiple_nested_paths(self, testrunnerer: Testrunnerer) -> None:
        """Test that 'testrunner a/b a a/b/c' collects all tests from 'a'."""
        testrunnerer.makepyfile(
            **{
                "a/test_a.py": """
                    def test_a(): pass
                """,
                "a/b/test_b.py": """
                    def test_b(): pass
                """,
                "a/b/c/test_c.py": """
                    def test_c(): pass
                """,
            }
        )

        result = testrunnerer.runtestrunner("--collect-only", "a/b", "a", "a/b/c")

        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Dir a>",
                "    <Dir b>",
                "      <Dir c>",
                "        <Module test_c.py>",
                "          <Function test_c>",
                "      <Module test_b.py>",
                "        <Function test_b>",
                "    <Module test_a.py>",
                "      <Function test_a>",
                "",
            ],
            consecutive=True,
        )

    def test_same_path_twice(self, testrunnerer: Testrunnerer) -> None:
        """Test that 'testrunner a a' doesn't duplicate tests."""
        testrunnerer.makepyfile(
            **{
                "a/test_a.py": """
                    def test_a(): pass
                """,
            }
        )

        result = testrunnerer.runtestrunner("--collect-only", "a", "a")

        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Dir a>",
                "    <Module test_a.py>",
                "      <Function test_a>",
                "",
            ],
            consecutive=True,
        )

    def test_keep_duplicates_flag(self, testrunnerer: Testrunnerer) -> None:
        """Test that --keep-duplicates allows duplication."""
        testrunnerer.makepyfile(
            **{
                "a/test_a.py": """
                    def test_a(): pass
                """,
                "a/b/test_b.py": """
                    def test_b(): pass
                """,
            }
        )

        result = testrunnerer.runtestrunner("--collect-only", "--keep-duplicates", "a", "a/b")

        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Dir a>",
                "    <Dir b>",
                "      <Module test_b.py>",
                "        <Function test_b>",
                "    <Module test_a.py>",
                "      <Function test_a>",
                "    <Dir b>",
                "      <Module test_b.py>",
                "        <Function test_b>",
                "",
            ],
            consecutive=True,
        )

    def test_specific_file_then_parent_dir(self, testrunnerer: Testrunnerer) -> None:
        """Test that 'testrunner a/test_a.py a' collects all tests from 'a'."""
        testrunnerer.makepyfile(
            **{
                "a/test_a.py": """
                    def test_a(): pass
                """,
                "a/test_other.py": """
                    def test_other(): pass
                """,
            }
        )

        result = testrunnerer.runtestrunner("--collect-only", "a/test_a.py", "a")

        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Dir a>",
                "    <Module test_a.py>",
                "      <Function test_a>",
                "    <Module test_other.py>",
                "      <Function test_other>",
                "",
            ],
            consecutive=True,
        )

    def test_package_scope_fixture_with_overlapping_paths(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that package-scoped fixtures work correctly with overlapping paths."""
        testrunnerer.makepyfile(
            **{
                "pkg/__init__.py": "",
                "pkg/test_pkg.py": """
                    import testrunner

                    counter = {"value": 0}

                    @testrunner.fixture(scope="package")
                    def pkg_fixture():
                        counter["value"] += 1
                        return counter["value"]

                    def test_pkg1(pkg_fixture):
                        assert pkg_fixture == 1

                    def test_pkg2(pkg_fixture):
                        assert pkg_fixture == 1
                """,
                "pkg/sub/__init__.py": "",
                "pkg/sub/test_sub.py": """
                    def test_sub(): pass
                """,
            }
        )

        # Package fixture should run only once even with overlapping paths.
        result = testrunnerer.runtestrunner("pkg", "pkg/sub", "pkg", "-v")
        result.assert_outcomes(passed=3)

    def test_execution_order_preserved(self, testrunnerer: Testrunnerer) -> None:
        """Test that test execution order follows argument order."""
        testrunnerer.makepyfile(
            **{
                "a/test_a.py": """
                    def test_a(): pass
                """,
                "b/test_b.py": """
                    def test_b(): pass
                """,
            }
        )

        result = testrunnerer.runtestrunner("--collect-only", "b", "a", "b/test_b.py::test_b")

        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Dir b>",
                "    <Module test_b.py>",
                "      <Function test_b>",
                "  <Dir a>",
                "    <Module test_a.py>",
                "      <Function test_a>",
                "",
            ],
            consecutive=True,
        )

    def test_overlapping_node_ids_class_and_method(self, testrunnerer: Testrunnerer) -> None:
        """Test that overlapping node IDs are handled correctly."""
        testrunnerer.makepyfile(
            test_nodeids="""
                class TestClass:
                    def test_method1(self): pass
                    def test_method2(self): pass
                    def test_method3(self): pass

                def test_function(): pass
            """
        )

        # Class then specific method.
        result = testrunnerer.runtestrunner(
            "--collect-only",
            "test_nodeids.py::TestClass",
            "test_nodeids.py::TestClass::test_method2",
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Module test_nodeids.py>",
                "    <Class TestClass>",
                "      <Function test_method1>",
                "      <Function test_method2>",
                "      <Function test_method3>",
                "",
            ],
            consecutive=True,
        )

        # Specific method then class.
        result = testrunnerer.runtestrunner(
            "--collect-only",
            "test_nodeids.py::TestClass::test_method3",
            "test_nodeids.py::TestClass",
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Module test_nodeids.py>",
                "    <Class TestClass>",
                "      <Function test_method1>",
                "      <Function test_method2>",
                "      <Function test_method3>",
                "",
            ],
            consecutive=True,
        )

    def test_overlapping_node_ids_file_and_class(self, testrunnerer: Testrunnerer) -> None:
        """Test that file-level and class-level selections work correctly."""
        testrunnerer.makepyfile(
            test_file="""
                class TestClass:
                    def test_method(self): pass

                class TestOther:
                    def test_other(self): pass

                def test_function(): pass
            """
        )

        # File then class.
        result = testrunnerer.runtestrunner(
            "--collect-only", "test_file.py", "test_file.py::TestClass"
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Module test_file.py>",
                "    <Class TestClass>",
                "      <Function test_method>",
                "    <Class TestOther>",
                "      <Function test_other>",
                "    <Function test_function>",
                "",
            ],
            consecutive=True,
        )

        # Class then file.
        result = testrunnerer.runtestrunner(
            "--collect-only", "test_file.py::TestClass", "test_file.py"
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Module test_file.py>",
                "    <Class TestClass>",
                "      <Function test_method>",
                "    <Class TestOther>",
                "      <Function test_other>",
                "    <Function test_function>",
                "",
            ],
            consecutive=True,
        )

    def test_same_node_id_twice(self, testrunnerer: Testrunnerer) -> None:
        """Test that the same node ID specified twice is collected only once."""
        testrunnerer.makepyfile(
            test_dup="""
                def test_one(): pass
                def test_two(): pass
            """
        )

        result = testrunnerer.runtestrunner(
            "--collect-only",
            "test_dup.py::test_one",
            "test_dup.py::test_one",
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Module test_dup.py>",
                "    <Function test_one>",
                "",
            ],
            consecutive=True,
        )

    def test_overlapping_with_parametrization(self, testrunnerer: Testrunnerer) -> None:
        """Test overlapping with parametrized tests."""
        testrunnerer.makepyfile(
            test_param="""
                import testrunner

                @testrunner.mark.parametrize("n", [1, 2])
                def test_param(n): pass

                class TestClass:
                    @testrunner.mark.parametrize("x", ["a", "b"])
                    def test_method(self, x): pass
            """
        )

        result = testrunnerer.runtestrunner(
            "--collect-only",
            "test_param.py::test_param[2]",
            "test_param.py::TestClass::test_method[a]",
            "test_param.py",
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Module test_param.py>",
                "    <Function test_param[1]>",
                "    <Function test_param[2]>",
                "    <Class TestClass>",
                "      <Function test_method[a]>",
                "      <Function test_method[b]>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner(
            "--collect-only",
            "test_param.py::test_param[2]",
            "test_param.py::test_param",
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Module test_param.py>",
                "    <Function test_param[1]>",
                "    <Function test_param[2]>",
                "",
            ],
            consecutive=True,
        )

    @testrunner.mark.parametrize("order", [(".", "a"), ("a", ".")])
    def test_root_and_subdir(self, testrunnerer: Testrunnerer, order: tuple[str, ...]) -> None:
        """Test that '. a' and 'a .' both collect all tests."""
        testrunnerer.makepyfile(
            test_root="""
                def test_root(): pass
            """,
            **{
                "a/test_a.py": """
                    def test_a(): pass
                """,
            },
        )

        result = testrunnerer.runtestrunner("--collect-only", *order)

        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Dir a>",
                "    <Module test_a.py>",
                "      <Function test_a>",
                "  <Module test_root.py>",
                "    <Function test_root>",
                "",
            ],
            consecutive=True,
        )

    def test_complex_combined_handling(self, testrunnerer: Testrunnerer) -> None:
        """Test some scenarios in a complex hierarchy."""
        testrunnerer.makepyfile(
            **{
                "top1/__init__.py": "",
                "top1/test_1.py": (
                    """
                    def test_1(): pass

                    class TestIt:
                        def test_2(): pass

                    def test_3(): pass
                    """
                ),
                "top1/test_2.py": (
                    """
                    def test_1(): pass
                    """
                ),
                "top2/__init__.py": "",
                "top2/test_1.py": (
                    """
                    def test_1(): pass
                    """
                ),
            },
        )

        result = testrunnerer.runtestrunner_inprocess("--collect-only", ".")
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top1>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                "      <Class TestIt>",
                "        <Function test_2>",
                "      <Function test_3>",
                "    <Module test_2.py>",
                "      <Function test_1>",
                "  <Package top2>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess("--collect-only", "top2", "top1")
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top2>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                "  <Package top1>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                "      <Class TestIt>",
                "        <Function test_2>",
                "      <Function test_3>",
                "    <Module test_2.py>",
                "      <Function test_1>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess(
            "--collect-only", "top1", "top1/test_2.py"
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top1>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                "      <Class TestIt>",
                "        <Function test_2>",
                "      <Function test_3>",
                "    <Module test_2.py>",
                "      <Function test_1>",
                # NOTE: Also sensible arguably even without --keep-duplicates.
                # "    <Module test_2.py>",
                # "      <Function test_1>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess(
            "--collect-only", "top1/test_2.py", "top1"
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top1>",
                # NOTE: Ideally test_2 would come before test_1 here.
                "    <Module test_1.py>",
                "      <Function test_1>",
                "      <Class TestIt>",
                "        <Function test_2>",
                "      <Function test_3>",
                "    <Module test_2.py>",
                "      <Function test_1>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess(
            "--collect-only", "--keep-duplicates", "top1/test_2.py", "top1"
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top1>",
                "    <Module test_2.py>",
                "      <Function test_1>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                "      <Class TestIt>",
                "        <Function test_2>",
                "      <Function test_3>",
                "    <Module test_2.py>",
                "      <Function test_1>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess(
            "--collect-only", "top1/test_2.py", "top1/test_2.py"
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top1>",
                "    <Module test_2.py>",
                "      <Function test_1>",
                # NOTE: Also sensible arguably even without --keep-duplicates.
                # "    <Module test_2.py>",
                # "      <Function test_1>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess("--collect-only", "top2/", "top2/")
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top2>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                # NOTE: Also sensible arguably even without --keep-duplicates.
                # "  <Package top2>",
                # "    <Module test_1.py>",
                # "      <Function test_1>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess(
            "--collect-only", "top2/", "top2/", "top2/test_1.py"
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top2>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                # NOTE: Also sensible arguably even without --keep-duplicates.
                # "  <Package top2>",
                # "    <Module test_1.py>",
                # "      <Function test_1>",
                # "    <Module test_1.py>",
                # "      <Function test_1>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess(
            "--collect-only", "top1/test_1.py", "top1/test_1.py::test_3"
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top1>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                "      <Class TestIt>",
                "        <Function test_2>",
                "      <Function test_3>",
                # NOTE: Also sensible arguably even without --keep-duplicates.
                # "      <Function test_3>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess(
            "--collect-only", "top1/test_1.py::test_3", "top1/test_1.py"
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top1>",
                "    <Module test_1.py>",
                # NOTE: Ideally test_3 would come before the others here.
                "      <Function test_1>",
                "      <Class TestIt>",
                "        <Function test_2>",
                "      <Function test_3>",
                "",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner_inprocess(
            "--collect-only",
            "--keep-duplicates",
            "top1/test_1.py::test_3",
            "top1/test_1.py",
        )
        result.stdout.fnmatch_lines(
            [
                "<Dir *>",
                "  <Package top1>",
                # NOTE: That <Module test_1.py> is duplicated here is not great.
                "    <Module test_1.py>",
                "      <Function test_3>",
                "    <Module test_1.py>",
                "      <Function test_1>",
                "      <Class TestIt>",
                "        <Function test_2>",
                "      <Function test_3>",
                "",
            ],
            consecutive=True,
        )


@testrunner.mark.parametrize(
    ["x_y", "expected_duplicates"],
    [
        (
            [(1, 1), (1, 1)],
            ["1-1"],
        ),
        (
            [(1, 1), (1, 2), (1, 1)],
            ["1-1"],
        ),
        (
            [(1, 1), (2, 2), (1, 1)],
            ["1-1"],
        ),
        (
            [(1, 1), (2, 2), (1, 2), (2, 1), (1, 1), (2, 1)],
            ["1-1", "2-1"],
        ),
    ],
)
@testrunner.mark.parametrize("option_name", ["strict_parametrization_ids", "strict"])
def test_strict_parametrization_ids(
    testrunnerer: Testrunnerer,
    x_y: Sequence[tuple[int, int]],
    expected_duplicates: Sequence[str],
    option_name: str,
) -> None:
    testrunnerer.makeini(
        f"""
        [testrunner]
        {option_name} = true
        """
    )
    testrunnerer.makepyfile(
        f"""
        import testrunner

        @testrunner.mark.parametrize(["x", "y"], {x_y})
        def test1(x, y):
            pass
        """
    )

    result = testrunnerer.runtestrunner()

    assert result.ret == ExitCode.INTERRUPTED
    expected_parametersets = ", ".join(str(list(p)) for p in x_y)
    expected_ids = ", ".join(f"{x}-{y}" for x, y in x_y)
    result.stdout.fnmatch_lines(
        [
            "Duplicate parametrization IDs detected*",
            "",
            "Test name:      *::test1",
            "Parameters:     x, y",
            f"Parameter sets: {expected_parametersets}",
            f"IDs:            {expected_ids}",
            f"Duplicates:     {', '.join(expected_duplicates)}",
            "",
            "You can fix this problem using *",
        ]
    )


def test_strict_parametrization_ids_with_hidden_param(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeini(
        """
        [testrunner]
        strict_parametrization_ids = true
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.mark.parametrize(["x"], ["a", testrunner.param("a", id=testrunner.HIDDEN_PARAM), "a"])
        def test1(x):
            pass
        """
    )

    result = testrunnerer.runtestrunner()

    assert result.ret == ExitCode.INTERRUPTED
    result.stdout.fnmatch_lines(
        [
            "Duplicate parametrization IDs detected*",
            "IDs:            a, <hidden>, a",
            "Duplicates:     a",
        ]
    )
