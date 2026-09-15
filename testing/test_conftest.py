# mypy: allow-untyped-defs
from __future__ import annotations

from collections.abc import Generator
from collections.abc import Sequence
import os
from pathlib import Path
import textwrap
from typing import cast

from _testrunner.config import ExitCode
from _testrunner.config import TestrunnerPluginManager
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.pathlib import symlink_or_skip
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.tmpdir import TempPathFactory
import testrunner


def ConftestWithSetinitial(path) -> TestrunnerPluginManager:
    conftest = TestrunnerPluginManager()
    conftest_setinitial(conftest, [path])
    return conftest


def conftest_setinitial(
    conftest: TestrunnerPluginManager,
    args: Sequence[str | Path],
    confcutdir: Path | None = None,
) -> None:
    conftest._set_initial_conftests(
        args=args,
        pyargs=False,
        noconftest=False,
        rootpath=Path(args[0]),
        confcutdir=confcutdir,
        invocation_dir=Path.cwd(),
        importmode="prepend",
        consider_namespace_packages=False,
    )


@testrunner.mark.usefixtures("_sys_snapshot")
class TestConftestValueAccessGlobal:
    @testrunner.fixture(scope="module", params=["global", "inpackage"])
    @staticmethod
    def basedir(request, tmp_path_factory: TempPathFactory) -> Generator[Path]:
        tmp_path = tmp_path_factory.mktemp("basedir", numbered=True)
        tmp_path.joinpath("adir/b").mkdir(parents=True)
        tmp_path.joinpath("adir/conftest.py").write_text(
            "a=1 ; Directory = 3", encoding="utf-8"
        )
        tmp_path.joinpath("adir/b/conftest.py").write_text(
            "b=2 ; a = 1.5", encoding="utf-8"
        )
        if request.param == "inpackage":
            tmp_path.joinpath("adir/__init__.py").touch()
            tmp_path.joinpath("adir/b/__init__.py").touch()

        yield tmp_path

    def test_basic_init(self, basedir: Path) -> None:
        conftest = TestrunnerPluginManager()
        p = basedir / "adir"
        conftest._loadconftestmodules(
            p, importmode="prepend", rootpath=basedir, consider_namespace_packages=False
        )
        assert conftest._rget_with_confmod("a", p)[1] == 1

    def test_immediate_initialization_and_incremental_are_the_same(
        self, basedir: Path
    ) -> None:
        conftest = TestrunnerPluginManager()
        assert not len(conftest._dirpath2confmods)
        conftest._loadconftestmodules(
            basedir,
            importmode="prepend",
            rootpath=basedir,
            consider_namespace_packages=False,
        )
        snap1 = len(conftest._dirpath2confmods)
        assert snap1 == 1
        conftest._loadconftestmodules(
            basedir / "adir",
            importmode="prepend",
            rootpath=basedir,
            consider_namespace_packages=False,
        )
        assert len(conftest._dirpath2confmods) == snap1 + 1
        conftest._loadconftestmodules(
            basedir / "b",
            importmode="prepend",
            rootpath=basedir,
            consider_namespace_packages=False,
        )
        assert len(conftest._dirpath2confmods) == snap1 + 2

    def test_value_access_not_existing(self, basedir: Path) -> None:
        conftest = ConftestWithSetinitial(basedir)
        with testrunner.raises(KeyError):
            conftest._rget_with_confmod("a", basedir)

    def test_value_access_by_path(self, basedir: Path) -> None:
        conftest = ConftestWithSetinitial(basedir)
        adir = basedir / "adir"
        conftest._loadconftestmodules(
            adir,
            importmode="prepend",
            rootpath=basedir,
            consider_namespace_packages=False,
        )
        assert conftest._rget_with_confmod("a", adir)[1] == 1
        conftest._loadconftestmodules(
            adir / "b",
            importmode="prepend",
            rootpath=basedir,
            consider_namespace_packages=False,
        )
        assert conftest._rget_with_confmod("a", adir / "b")[1] == 1.5

    def test_value_access_with_confmod(self, basedir: Path) -> None:
        startdir = basedir / "adir" / "b"
        startdir.joinpath("xx").mkdir()
        conftest = ConftestWithSetinitial(startdir)
        mod, value = conftest._rget_with_confmod("a", startdir)
        assert value == 1.5
        assert mod.__file__ is not None
        path = Path(mod.__file__)
        assert path.parent == basedir / "adir" / "b"
        assert path.stem == "conftest"


def test_conftest_in_nonpkg_with_init(tmp_path: Path, _sys_snapshot) -> None:
    tmp_path.joinpath("adir-1.0/b").mkdir(parents=True)
    tmp_path.joinpath("adir-1.0/conftest.py").write_text(
        "a=1 ; Directory = 3", encoding="utf-8"
    )
    tmp_path.joinpath("adir-1.0/b/conftest.py").write_text(
        "b=2 ; a = 1.5", encoding="utf-8"
    )
    tmp_path.joinpath("adir-1.0/b/__init__.py").touch()
    tmp_path.joinpath("adir-1.0/__init__.py").touch()
    ConftestWithSetinitial(tmp_path.joinpath("adir-1.0", "b"))


def test_doubledash_considered(testrunnerer: Testrunnerer) -> None:
    conf = testrunnerer.mkdir("--option")
    conf.joinpath("conftest.py").touch()
    conftest = TestrunnerPluginManager()
    conftest_setinitial(conftest, [conf.name, conf.name])
    values = conftest._getconftestmodules(conf)
    assert len(values) == 1


def test_issue151_load_all_conftests(testrunnerer: Testrunnerer) -> None:
    names = ["code", "proj", "src"]
    for name in names:
        p = testrunnerer.mkdir(name)
        p.joinpath("conftest.py").touch()

    pm = TestrunnerPluginManager()
    conftest_setinitial(pm, names)
    assert len(set(pm.get_plugins()) - {pm}) == len(names)


def test_conftest_global_import(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest("x=3")
    p = testrunnerer.makepyfile(
        """
        from pathlib import Path
        import testrunner
        from _testrunner.config import TestrunnerPluginManager
        conf = TestrunnerPluginManager()
        mod = conf._importconftest(
            Path("conftest.py"),
            importmode="prepend",
            rootpath=Path.cwd(),
            consider_namespace_packages=False,
        )
        assert mod.x == 3
        import conftest
        assert conftest is mod, (conftest, mod)
        sub = Path("sub")
        sub.mkdir()
        subconf = sub / "conftest.py"
        subconf.write_text("y=4", encoding="utf-8")
        mod2 = conf._importconftest(
            subconf,
            importmode="prepend",
            rootpath=Path.cwd(),
            consider_namespace_packages=False,
        )
        assert mod != mod2
        assert mod2.y == 4
        import conftest
        assert conftest is mod2, (conftest, mod)
    """
    )
    res = testrunnerer.runpython(p)
    assert res.ret == 0


def test_conftestcutdir(testrunnerer: Testrunnerer) -> None:
    conf = testrunnerer.makeconftest("")
    p = testrunnerer.mkdir("x")
    conftest = TestrunnerPluginManager()
    conftest_setinitial(conftest, [testrunnerer.path], confcutdir=p)
    conftest._loadconftestmodules(
        p,
        importmode="prepend",
        rootpath=testrunnerer.path,
        consider_namespace_packages=False,
    )
    values = conftest._getconftestmodules(p)
    assert len(values) == 0
    conftest._loadconftestmodules(
        conf.parent,
        importmode="prepend",
        rootpath=testrunnerer.path,
        consider_namespace_packages=False,
    )
    values = conftest._getconftestmodules(conf.parent)
    assert len(values) == 0
    assert not conftest.has_plugin(str(conf))
    # but we can still import a conftest directly
    conftest._importconftest(
        conf,
        importmode="prepend",
        rootpath=testrunnerer.path,
        consider_namespace_packages=False,
    )
    values = conftest._getconftestmodules(conf.parent)
    assert values[0].__file__ is not None
    assert values[0].__file__.startswith(str(conf))
    # and all sub paths get updated properly
    values = conftest._getconftestmodules(p)
    assert len(values) == 1
    assert values[0].__file__ is not None
    assert values[0].__file__.startswith(str(conf))


def test_conftestcutdir_inplace_considered(testrunnerer: Testrunnerer) -> None:
    conf = testrunnerer.makeconftest("")
    conftest = TestrunnerPluginManager()
    conftest_setinitial(conftest, [conf.parent], confcutdir=conf.parent)
    values = conftest._getconftestmodules(conf.parent)
    assert len(values) == 1
    assert values[0].__file__ is not None
    assert values[0].__file__.startswith(str(conf))


@testrunner.mark.parametrize("name", ["test", "tests", "whatever", ".dotdir"])
def test_setinitial_conftest_subdirs(testrunnerer: Testrunnerer, name: str) -> None:
    sub = testrunnerer.mkdir(name)
    subconftest = sub.joinpath("conftest.py")
    subconftest.touch()
    pm = TestrunnerPluginManager()
    conftest_setinitial(pm, [sub.parent], confcutdir=testrunnerer.path)
    key = subconftest.resolve()
    if name not in ("whatever", ".dotdir"):
        assert pm.has_plugin(str(key))
        assert len(set(pm.get_plugins()) - {pm}) == 1
    else:
        assert not pm.has_plugin(str(key))
        assert len(set(pm.get_plugins()) - {pm}) == 0


def test_conftest_confcutdir(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest("assert 0")
    x = testrunnerer.mkdir("x")
    x.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            def testrunner_addoption(parser):
                parser.addoption("--xyz", action="store_true")
            """
        ),
        encoding="utf-8",
    )
    result = testrunnerer.runtestrunner("-h", f"--confcutdir={x}", x)
    result.stdout.fnmatch_lines(["*--xyz*"])
    result.stdout.no_fnmatch_line("*warning: could not load initial*")


def test_installed_conftest_is_picked_up(testrunnerer: Testrunnerer, tmp_path: Path) -> None:
    """When using `--pyargs` to run tests in an installed packages (located e.g.
    in a site-packages in the PYTHONPATH), conftest files in there are picked
    up.

    Regression test for #9767.
    """
    # testrunnerer dir - the source tree.
    # tmp_path - the simulated site-packages dir (not in source tree).

    testrunnerer.syspathinsert(tmp_path)
    testrunnerer.makepyprojecttoml("[tool.testrunner.ini_options]")
    tmp_path.joinpath("foo").mkdir()
    tmp_path.joinpath("foo", "__init__.py").touch()
    tmp_path.joinpath("foo", "conftest.py").write_text(
        textwrap.dedent(
            """\
            import testrunner
            @testrunner.fixture
            def fix(): return None
            """
        ),
        encoding="utf-8",
    )
    tmp_path.joinpath("foo", "test_it.py").write_text(
        "def test_it(fix): pass", encoding="utf-8"
    )
    result = testrunnerer.runtestrunner("--pyargs", "foo")
    assert result.ret == 0


def test_conftest_symlink(testrunnerer: Testrunnerer) -> None:
    """`conftest.py` discovery follows normal path resolution and does not resolve symlinks."""
    # Structure:
    # /real
    # /real/conftest.py
    # /real/app
    # /real/app/tests
    # /real/app/tests/test_foo.py

    # Links:
    # /symlinktests -> /real/app/tests (running at symlinktests should fail)
    # /symlink -> /real (running at /symlink should work)

    real = testrunnerer.mkdir("real")
    realtests = real.joinpath("app/tests")
    realtests.mkdir(parents=True)
    symlink_or_skip(realtests, testrunnerer.path.joinpath("symlinktests"))
    symlink_or_skip(real, testrunnerer.path.joinpath("symlink"))
    testrunnerer.makepyfile(
        **{
            "real/app/tests/test_foo.py": "def test1(fixture): pass",
            "real/conftest.py": textwrap.dedent(
                """
                import testrunner

                print("conftest_loaded")

                @testrunner.fixture
                def fixture():
                    print("fixture_used")
                """
            ),
        }
    )

    # Should fail because conftest cannot be found from the link structure.
    result = testrunnerer.runtestrunner("-vs", "symlinktests")
    result.stdout.fnmatch_lines(["*fixture 'fixture' not found*"])
    assert result.ret == ExitCode.TESTS_FAILED

    # Should not cause "ValueError: Plugin already registered" (#4174).
    result = testrunnerer.runtestrunner("-vs", "symlink")
    assert result.ret == ExitCode.OK


def test_conftest_symlink_files(testrunnerer: Testrunnerer) -> None:
    """Symlinked conftest.py are found when testrunner is executed in a directory with symlinked
    files."""
    real = testrunnerer.mkdir("real")
    source = {
        "app/test_foo.py": "def test1(fixture): pass",
        "app/__init__.py": "",
        "app/conftest.py": textwrap.dedent(
            """
            import testrunner

            print("conftest_loaded")

            @testrunner.fixture
            def fixture():
                print("fixture_used")
            """
        ),
    }
    testrunnerer.makepyfile(**{f"real/{k}": v for k, v in source.items()})

    # Create a build directory that contains symlinks to actual files
    # but doesn't symlink actual directories.
    build = testrunnerer.mkdir("build")
    build.joinpath("app").mkdir()
    for f in source:
        symlink_or_skip(real.joinpath(f), build.joinpath(f))
    os.chdir(build)
    result = testrunnerer.runtestrunner("-vs", "app/test_foo.py")
    result.stdout.fnmatch_lines(["*conftest_loaded*", "PASSED"])
    assert result.ret == ExitCode.OK


@testrunner.mark.skipif(
    os.path.normcase("x") != os.path.normcase("X"),
    reason="only relevant for case-insensitive file systems",
)
def test_conftest_badcase(testrunnerer: Testrunnerer) -> None:
    """Check conftest.py loading when directory casing is wrong (#5792)."""
    testrunnerer.path.joinpath("JenkinsRoot/test").mkdir(parents=True)
    source = {"setup.py": "", "test/__init__.py": "", "test/conftest.py": ""}
    testrunnerer.makepyfile(**{f"JenkinsRoot/{k}": v for k, v in source.items()})

    os.chdir(testrunnerer.path.joinpath("jenkinsroot/test"))
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_conftest_uppercase(testrunnerer: Testrunnerer) -> None:
    """Check conftest.py whose qualified name contains uppercase characters (#5819)"""
    source = {"__init__.py": "", "Foo/conftest.py": "", "Foo/__init__.py": ""}
    testrunnerer.makepyfile(**source)

    os.chdir(testrunnerer.path)
    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_no_conftest(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest("assert 0")
    result = testrunnerer.runtestrunner("--noconftest")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED

    result = testrunnerer.runtestrunner()
    assert result.ret == ExitCode.USAGE_ERROR


def test_conftest_existing_junitxml(testrunnerer: Testrunnerer) -> None:
    x = testrunnerer.mkdir("tests")
    x.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            def testrunner_addoption(parser):
                parser.addoption("--xyz", action="store_true")
            """
        ),
        encoding="utf-8",
    )
    testrunnerer.makefile(ext=".xml", junit="")  # Writes junit.xml
    result = testrunnerer.runtestrunner("-h", "--junitxml", "junit.xml")
    result.stdout.fnmatch_lines(["*--xyz*"])


def test_conftests_in_invocation_dir_tests_is_initial(testrunnerer: Testrunnerer) -> None:
    """An option registered in a conftest under ``test*`` subdir of the
    invocation dir is loaded as initial when no command-line arguments
    or `testpaths` are given (#14608).
    """
    testrunnerer.makepyfile(
        **{
            "tests/conftest.py": """
                def testrunner_addoption(parser):
                    parser.addoption("--db-url")
            """,
            "test_it.py": """
                def test_it(request):
                    assert request.config.getoption("--db-url") == "scheme://host/db"
            """,
        }
    )
    result = testrunnerer.runtestrunner("--db-url", "scheme://host/db")
    assert result.ret == ExitCode.OK
    result.assert_outcomes(passed=1)


def test_conftest_import_order(testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch) -> None:
    ct1 = testrunnerer.makeconftest("")
    sub = testrunnerer.mkdir("sub")
    ct2 = sub / "conftest.py"
    ct2.write_text("", encoding="utf-8")

    def impct(p, importmode, root, consider_namespace_packages):
        return p

    conftest = TestrunnerPluginManager()
    conftest._confcutdir = testrunnerer.path
    monkeypatch.setattr(conftest, "_importconftest", impct)
    conftest._loadconftestmodules(
        sub,
        importmode="prepend",
        rootpath=testrunnerer.path,
        consider_namespace_packages=False,
    )
    mods = cast(list[Path], conftest._getconftestmodules(sub))
    expected = [ct1, ct2]
    assert mods == expected


def test_fixture_dependency(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest("")
    testrunnerer.path.joinpath("__init__.py").touch()
    sub = testrunnerer.mkdir("sub")
    sub.joinpath("__init__.py").touch()
    sub.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            import testrunner

            @testrunner.fixture
            def not_needed():
                assert False, "Should not be called!"

            @testrunner.fixture
            def foo():
                assert False, "Should not be called!"

            @testrunner.fixture
            def bar(foo):
                return 'bar'
            """
        ),
        encoding="utf-8",
    )
    subsub = sub.joinpath("subsub")
    subsub.mkdir()
    subsub.joinpath("__init__.py").touch()
    subsub.joinpath("test_bar.py").write_text(
        textwrap.dedent(
            """\
            import testrunner

            @testrunner.fixture
            def bar():
                return 'sub bar'

            def test_event_fixture(bar):
                assert bar == 'sub bar'
            """
        ),
        encoding="utf-8",
    )
    result = testrunnerer.runtestrunner("sub")
    result.stdout.fnmatch_lines(["*1 passed*"])


def test_conftest_found_with_double_dash(testrunnerer: Testrunnerer) -> None:
    sub = testrunnerer.mkdir("sub")
    sub.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            def testrunner_addoption(parser):
                parser.addoption("--hello-world", action="store_true")
            """
        ),
        encoding="utf-8",
    )
    p = sub.joinpath("test_hello.py")
    p.write_text("def test_hello(): pass", encoding="utf-8")
    result = testrunnerer.runtestrunner(str(p) + "::test_hello", "-h")
    result.stdout.fnmatch_lines(
        """
        *--hello-world*
    """
    )


class TestConftestVisibility:
    def _setup_tree(self, testrunnerer: Testrunnerer) -> dict[str, Path]:  # for issue616
        # example mostly taken from:
        # https://mail.python.org/pipermail/testrunner-dev/2014-September/002617.html
        runner = testrunnerer.mkdir("empty")
        package = testrunnerer.mkdir("package")

        package.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner
                @testrunner.fixture
                def fxtr():
                    return "from-package"
                """
            ),
            encoding="utf-8",
        )
        package.joinpath("test_pkgroot.py").write_text(
            textwrap.dedent(
                """\
                def test_pkgroot(fxtr):
                    assert fxtr == "from-package"
                """
            ),
            encoding="utf-8",
        )

        swc = package.joinpath("swc")
        swc.mkdir()
        swc.joinpath("__init__.py").touch()
        swc.joinpath("conftest.py").write_text(
            textwrap.dedent(
                """\
                import testrunner
                @testrunner.fixture
                def fxtr():
                    return "from-swc"
                """
            ),
            encoding="utf-8",
        )
        swc.joinpath("test_with_conftest.py").write_text(
            textwrap.dedent(
                """\
                def test_with_conftest(fxtr):
                    assert fxtr == "from-swc"
                """
            ),
            encoding="utf-8",
        )

        snc = package.joinpath("snc")
        snc.mkdir()
        snc.joinpath("__init__.py").touch()
        snc.joinpath("test_no_conftest.py").write_text(
            textwrap.dedent(
                """\
                def test_no_conftest(fxtr):
                    assert fxtr == "from-package"   # No local conftest.py, so should
                                                    # use value from parent dir's
                """
            ),
            encoding="utf-8",
        )
        print("created directory structure:")
        for x in testrunnerer.path.glob("**/"):
            print("   " + str(x.relative_to(testrunnerer.path)))

        return {"runner": runner, "package": package, "swc": swc, "snc": snc}

    # N.B.: "swc" stands for "subdir with conftest.py"
    #       "snc" stands for "subdir no [i.e. without] conftest.py"
    @testrunner.mark.parametrize(
        "chdir,testarg,expect_ntests_passed",
        [
            # Effective target: package/..
            ("runner", "..", 3),
            ("package", "..", 3),
            ("swc", "../..", 3),
            ("snc", "../..", 3),
            # Effective target: package
            ("runner", "../package", 3),
            ("package", ".", 3),
            ("swc", "..", 3),
            ("snc", "..", 3),
            # Effective target: package/swc
            ("runner", "../package/swc", 1),
            ("package", "./swc", 1),
            ("swc", ".", 1),
            ("snc", "../swc", 1),
            # Effective target: package/snc
            ("runner", "../package/snc", 1),
            ("package", "./snc", 1),
            ("swc", "../snc", 1),
            ("snc", ".", 1),
        ],
    )
    def test_parsefactories_relative_node_ids(
        self, testrunnerer: Testrunnerer, chdir: str, testarg: str, expect_ntests_passed: int
    ) -> None:
        """#616"""
        dirs = self._setup_tree(testrunnerer)
        print(f"testrunner run in cwd: {dirs[chdir].relative_to(testrunnerer.path)}")
        print(f"testrunnerarg        : {testarg}")
        print(f"expected pass    : {expect_ntests_passed}")
        os.chdir(dirs[chdir])
        reprec = testrunnerer.inline_run(
            testarg,
            "-q",
            "--traceconfig",
            "--confcutdir",
            testrunnerer.path,
        )
        reprec.assertoutcome(passed=expect_ntests_passed)


@testrunner.mark.parametrize(
    "confcutdir,passed,error", [(".", 2, 0), ("src", 1, 1), (None, 1, 1)]
)
def test_search_conftest_up_to_inifile(
    testrunnerer: Testrunnerer, confcutdir: str, passed: int, error: int
) -> None:
    """Test that conftest files are detected only up to a configuration file, unless
    an explicit --confcutdir option is given.
    """
    root = testrunnerer.path
    src = root.joinpath("src")
    src.mkdir()
    src.joinpath("testrunner.ini").write_text("[testrunner]", encoding="utf-8")
    src.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            import testrunner
            @testrunner.fixture
            def fix1(): pass
            """
        ),
        encoding="utf-8",
    )
    src.joinpath("test_foo.py").write_text(
        textwrap.dedent(
            """\
            def test_1(fix1):
                pass
            def test_2(out_of_reach):
                pass
            """
        ),
        encoding="utf-8",
    )
    root.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            import testrunner
            @testrunner.fixture
            def out_of_reach(): pass
            """
        ),
        encoding="utf-8",
    )

    args = [str(src)]
    if confcutdir:
        args = [f"--confcutdir={root.joinpath(confcutdir)}"]
    result = testrunnerer.runtestrunner(*args)
    match = ""
    if passed:
        match += f"*{passed} passed*"
    if error:
        match += f"*{error} error*"
    result.stdout.fnmatch_lines(match)


def test_issue1073_conftest_special_objects(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """\
        class DontTouchMe(object):
            def __getattr__(self, x):
                raise Exception('cant touch me')

        x = DontTouchMe()
        """
    )
    testrunnerer.makepyfile(
        """\
        def test_some():
            pass
        """
    )
    res = testrunnerer.runtestrunner()
    assert res.ret == 0


def test_conftest_exception_handling(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """\
        raise ValueError()
        """
    )
    testrunnerer.makepyfile(
        """\
        def test_some():
            pass
        """
    )
    res = testrunnerer.runtestrunner()
    assert res.ret == 4
    assert "raise ValueError()" in [line.strip() for line in res.errlines]


def test_hook_proxy(testrunnerer: Testrunnerer) -> None:
    """Session's gethookproxy() would cache conftests incorrectly (#2016).
    It was decided to remove the cache altogether.
    """
    testrunnerer.makepyfile(
        **{
            "root/demo-0/test_foo1.py": "def test1(): pass",
            "root/demo-a/test_foo2.py": "def test1(): pass",
            "root/demo-a/conftest.py": """\
            def testrunner_ignore_collect(collection_path, config):
                return True
            """,
            "root/demo-b/test_foo3.py": "def test1(): pass",
            "root/demo-c/test_foo4.py": "def test1(): pass",
        }
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(
        ["*test_foo1.py*", "*test_foo3.py*", "*test_foo4.py*", "*3 passed*"]
    )


def test_conftest_fixture_scoping_with_testpaths_outside_rootdir(
    testrunnerer: Testrunnerer,
) -> None:
    """Regression test for #14004.

    When testpaths points to a directory outside rootdir, conftest fixtures
    from nested directories should not leak to sibling test directories.

    Layout:
        sdk/
            pyproject.toml      (rootdir, testpaths = ["../tests/sdk"])
        tests/
            sdk/
                conftest.py     (outer fixture)
                test_outer.py
                inner/
                    conftest.py (inner fixture - should NOT be visible in test_outer)
                    test_inner.py
    """
    root = testrunnerer.path
    sdk = root / "sdk"
    sdk.mkdir()
    sdk.joinpath("pyproject.toml").write_text(
        textwrap.dedent("""\
            [tool.testrunner.ini_options]
            testpaths = ["../tests/sdk"]
        """),
        encoding="utf-8",
    )

    tests_sdk = root / "tests" / "sdk"
    tests_sdk.mkdir(parents=True)
    tests_sdk.joinpath("conftest.py").write_text(
        textwrap.dedent("""\
            import testrunner

            @testrunner.fixture(autouse=True)
            def outer_fixture():
                pass
        """),
        encoding="utf-8",
    )
    tests_sdk.joinpath("test_outer.py").write_text(
        textwrap.dedent("""\
            def test_outer(request):
                fixturenames = request.fixturenames
                assert "outer_fixture" in fixturenames
                assert "inner_fixture" not in fixturenames
        """),
        encoding="utf-8",
    )

    inner = tests_sdk / "inner"
    inner.mkdir()
    inner.joinpath("conftest.py").write_text(
        textwrap.dedent("""\
            import testrunner

            @testrunner.fixture(autouse=True)
            def inner_fixture():
                pass
        """),
        encoding="utf-8",
    )
    inner.joinpath("test_inner.py").write_text(
        textwrap.dedent("""\
            def test_inner(request):
                fixturenames = request.fixturenames
                assert "outer_fixture" in fixturenames
                assert "inner_fixture" in fixturenames
        """),
        encoding="utf-8",
    )

    result = testrunnerer.runtestrunner("--rootdir", str(sdk), "-v")
    result.stdout.fnmatch_lines(
        [
            "*test_inner*PASSED*",
            "*test_outer*PASSED*",
            "*2 passed*",
        ]
    )


def test_conftest_fixture_from_ancestor_above_rootdir(
    testrunnerer: Testrunnerer,
) -> None:
    """Conftests from ancestor directories above rootdir that are loaded as
    initial conftests get Session (global) visibility.

    Layout:
        project/
            conftest.py         (defines ancestor_fixture)
            sub/
                pyproject.toml  (rootdir)
                test_it.py      (should see ancestor_fixture)
    """
    root = testrunnerer.path
    root.joinpath("conftest.py").write_text(
        textwrap.dedent("""\
            import testrunner

            @testrunner.fixture
            def ancestor_fixture():
                return "from-ancestor"
        """),
        encoding="utf-8",
    )
    sub = root / "sub"
    sub.mkdir()
    sub.joinpath("pyproject.toml").write_text(
        "[tool.testrunner.ini_options]\n", encoding="utf-8"
    )
    sub.joinpath("test_it.py").write_text(
        textwrap.dedent("""\
            def test_uses_ancestor(ancestor_fixture):
                assert ancestor_fixture == "from-ancestor"
        """),
        encoding="utf-8",
    )

    result = testrunnerer.runtestrunner("--rootdir", str(sub), "--confcutdir", str(root), "-v")
    result.stdout.fnmatch_lines(["*test_uses_ancestor*PASSED*", "*1 passed*"])


def test_rootdir_conftest_visible_outside_rootdir(testrunnerer: Testrunnerer) -> None:
    """A conftest located in the rootdir provides fixtures to items that are
    collected from *outside* the rootdir.

    Before testrunner 9.1 the rootdir conftest got an empty baseid (which matches
    every collected item), so its fixtures were visible session-wide. The
    node-based scoping introduced in #14098 (testrunner 9.1) inadvertently scoped
    it to its own Directory node, making it invisible to items collected from
    a parent/sibling of the rootdir. Regression test for #14683.

    Layout::

        project/                  <- testrunner invoked here
            xclim/                <- collected (``--doctest-modules xclim``)
                testing/           <- rootdir (``--rootdir xclim/testing``)
                    conftest.py    <- defines a fixture
                core/
                    test_it.py     <- collected from outside rootdir
    """
    root = testrunnerer.path
    testing = root / "xclim" / "testing"
    testing.mkdir(parents=True)
    testing.joinpath("conftest.py").write_text(
        textwrap.dedent("""\
            import testrunner

            @testrunner.fixture
            def rootdir_fixture():
                return "from-rootdir"
        """),
        encoding="utf-8",
    )
    core = root / "xclim" / "core"
    core.mkdir()
    core.joinpath("test_it.py").write_text(
        textwrap.dedent("""\
            def test_uses_rootdir(rootdir_fixture):
                assert rootdir_fixture == "from-rootdir"
        """),
        encoding="utf-8",
    )

    result = testrunnerer.runtestrunner(
        "--rootdir", str(testing), "--doctest-modules", "xclim", "-v"
    )
    result.stdout.fnmatch_lines(["*test_uses_rootdir*PASSED*", "*1 passed*"])


def test_fixture_closure_order_independence_with_parametrize(
    testrunnerer: Testrunnerer,
) -> None:
    """Regression test for #14635.

    A test's fixture closure (and thus parametrize validation) should be
    independent of which unrelated paths were collected earlier in the session.

    The scenario: a test uses @testrunner.mark.parametrize("fixture_param", [...])
    where fixture_param is NOT a direct arg of the test but IS an argname of a
    fixture the test depends on transitively. Collecting unrelated directories
    before the test's directory should not cause the fixture_param to drop out
    of the closure.
    """
    root = testrunnerer.path
    tests = root / "tests"
    tests.mkdir()
    tests.joinpath("__init__.py").write_text("", encoding="utf-8")

    # tests/conftest.py - empty (or with some unrelated fixture)
    tests.joinpath("conftest.py").write_text(
        textwrap.dedent("""\
            import testrunner
        """),
        encoding="utf-8",
    )

    # tests/components/ with its conftest
    components = tests / "components"
    components.mkdir()
    components.joinpath("__init__.py").write_text("", encoding="utf-8")
    components.joinpath("conftest.py").write_text(
        textwrap.dedent("""\
            import testrunner

            @testrunner.fixture
            def cache_dir_side_effect():
                return None

            @testrunner.fixture
            def mock_init_cache_dir(cache_dir_side_effect):
                return cache_dir_side_effect

            @testrunner.fixture
            def mock_cache_dir(mock_init_cache_dir):
                return mock_init_cache_dir
        """),
        encoding="utf-8",
    )

    # tests/components/water_heater/ - unrelated test directory
    water_heater = components / "water_heater"
    water_heater.mkdir()
    water_heater.joinpath("__init__.py").write_text("", encoding="utf-8")
    water_heater.joinpath("test_water_heater.py").write_text(
        textwrap.dedent("""\
            def test_water_heater():
                pass
        """),
        encoding="utf-8",
    )

    # tests/components/tts/ - the problematic test directory
    tts = components / "tts"
    tts.mkdir()
    tts.joinpath("__init__.py").write_text("", encoding="utf-8")
    tts.joinpath("conftest.py").write_text(
        textwrap.dedent("""\
            import testrunner

            @testrunner.fixture(autouse=True)
            def mock_cache_dir(mock_cache_dir):
                # Autouse override that requests the parent fixture of same name
                return mock_cache_dir
        """),
        encoding="utf-8",
    )
    tts.joinpath("test_init.py").write_text(
        textwrap.dedent("""\
            import testrunner

            @testrunner.mark.parametrize("cache_dir_side_effect", ["error_value"])
            async def test_setup_no_access(mock_init_cache_dir):
                assert mock_init_cache_dir == "error_value"
        """),
        encoding="utf-8",
    )

    # tests/test_config_entries.py - another unrelated test
    tests.joinpath("test_config_entries.py").write_text(
        textwrap.dedent("""\
            def test_config():
                pass
        """),
        encoding="utf-8",
    )

    # This order triggers the bug: collecting water_heater and config_entries
    # BEFORE tts causes the fixture closure to be wrong.
    result = testrunnerer.runtestrunner(
        "--collect-only",
        str(water_heater),
        str(tests / "test_config_entries.py"),
        str(tts / "test_init.py"),
    )
    result.stdout.fnmatch_lines(["*test_setup_no_access*"])
    assert result.ret == ExitCode.OK


def test_required_option_help(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest("assert 0")
    x = testrunnerer.mkdir("x")
    x.joinpath("conftest.py").write_text(
        textwrap.dedent(
            """\
            def testrunner_addoption(parser):
                parser.addoption("--xyz", action="store_true", required=True)
            """
        ),
        encoding="utf-8",
    )
    result = testrunnerer.runtestrunner("-h", x)
    result.stdout.no_fnmatch_line("*argument --xyz is required*")
    assert "general:" in result.stdout.str()
