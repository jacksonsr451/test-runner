# mypy: allow-untyped-defs
from __future__ import annotations

from _testrunner.config import ExitCode
from _testrunner.config.exceptions import UsageError
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.testrunnerer import Testrunnerer
import testrunner


class SessionTests:
    def test_basic_testitem_events(self, testrunnerer: Testrunnerer) -> None:
        tfile = testrunnerer.makepyfile(
            """
            def test_one():
                pass
            def test_one_one():
                assert 0
            def test_other():
                raise ValueError(23)
            class TestClass(object):
                def test_two(self, someargs):
                    pass
        """
        )
        reprec = testrunnerer.inline_run(tfile)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(skipped) == 0
        assert len(passed) == 1
        assert len(failed) == 3

        def end(x):
            return x.nodeid.split("::")[-1]

        assert end(failed[0]) == "test_one_one"
        assert end(failed[1]) == "test_other"
        itemstarted = reprec.getcalls("testrunner_itemcollected")
        assert len(itemstarted) == 4
        # XXX check for failing funcarg setup
        # colreports = reprec.getcalls("testrunner_collectreport")
        # assert len(colreports) == 4
        # assert colreports[1].report.failed

    def test_nested_import_error(self, testrunnerer: Testrunnerer) -> None:
        tfile = testrunnerer.makepyfile(
            """
            import import_fails
            def test_this():
                assert import_fails.a == 1
        """,
            import_fails="""
            import does_not_work
            a = 1
        """,
        )
        reprec = testrunnerer.inline_run(tfile)
        values = reprec.getfailedcollections()
        assert len(values) == 1
        out = str(values[0].longrepr)
        assert out.find("does_not_work") != -1

    def test_raises_output(self, testrunnerer: Testrunnerer) -> None:
        reprec = testrunnerer.inline_runsource(
            """
            import testrunner
            def test_raises_doesnt():
                with testrunner.raises(ValueError):
                    int("3")
        """
        )
        _passed, _skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message  # type: ignore[union-attr]
        assert "DID NOT RAISE" in out

    def test_syntax_error_module(self, testrunnerer: Testrunnerer) -> None:
        reprec = testrunnerer.inline_runsource("this is really not python")
        values = reprec.getfailedcollections()
        assert len(values) == 1
        out = str(values[0].longrepr)
        assert out.find("not python") != -1

    def test_exit_first_problem(self, testrunnerer: Testrunnerer) -> None:
        reprec = testrunnerer.inline_runsource(
            """
            def test_one(): assert 0
            def test_two(): assert 0
        """,
            "--exitfirst",
        )
        passed, skipped, failed = reprec.countoutcomes()
        assert failed == 1
        assert passed == skipped == 0

    def test_maxfail(self, testrunnerer: Testrunnerer) -> None:
        reprec = testrunnerer.inline_runsource(
            """
            def test_one(): assert 0
            def test_two(): assert 0
            def test_three(): assert 0
        """,
            "--maxfail=2",
        )
        passed, skipped, failed = reprec.countoutcomes()
        assert failed == 2
        assert passed == skipped == 0

    def test_broken_repr(self, testrunnerer: Testrunnerer) -> None:
        p = testrunnerer.makepyfile(
            """
            import testrunner

            class reprexc(BaseException):
                def __str__(self):
                    return "Ha Ha fooled you, I'm a broken repr()."

            class BrokenRepr1(object):
                foo=0
                def __repr__(self):
                    raise reprexc

            class TestBrokenClass(object):
                def test_explicit_bad_repr(self):
                    t = BrokenRepr1()
                    with testrunner.raises(BaseException, match="broken repr"):
                        repr(t)

                def test_implicit_bad_repr1(self):
                    t = BrokenRepr1()
                    assert t.foo == 1

        """
        )
        reprec = testrunnerer.inline_run(p)
        passed, skipped, failed = reprec.listoutcomes()
        assert (len(passed), len(skipped), len(failed)) == (1, 0, 1)
        out = failed[0].longrepr.reprcrash.message  # type: ignore[union-attr]
        assert out.find("<[reprexc() raised in repr()] BrokenRepr1") != -1

    def test_broken_repr_with_showlocals_verbose(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p = testrunnerer.makepyfile(
            """
            class ObjWithErrorInRepr:
                def __repr__(self):
                    raise NotImplementedError

            def test_repr_error():
                x = ObjWithErrorInRepr()
                assert x == "value"
        """
        )
        reprec = testrunnerer.inline_run("--showlocals", "-vv", p)
        passed, skipped, failed = reprec.listoutcomes()
        assert (len(passed), len(skipped), len(failed)) == (0, 0, 1)
        entries = failed[0].longrepr.reprtraceback.reprentries  # type: ignore[union-attr]
        assert len(entries) == 1
        repr_locals = entries[0].reprlocals
        assert repr_locals.lines
        assert len(repr_locals.lines) == 1
        assert repr_locals.lines[0].startswith(
            "x          = <[NotImplementedError() raised in repr()] ObjWithErrorInRepr"
        )

    def test_skip_file_by_conftest(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            conftest="""
            import testrunner
            def testrunner_collect_file():
                testrunner.skip("intentional")
        """,
            test_file="""
            def test_one(): pass
        """,
        )
        try:
            reprec = testrunnerer.inline_run(testrunnerer.path)
        except testrunner.skip.Exception:  # pragma: no cover
            testrunner.fail("wrong skipped caught")
        reports = reprec.getreports("testrunner_collectreport")
        # Session, Dir
        assert len(reports) == 2
        assert reports[1].skipped


class TestNewSession(SessionTests):
    def test_order_of_execution(self, testrunnerer: Testrunnerer) -> None:
        reprec = testrunnerer.inline_runsource(
            """
            values = []
            def test_1():
                values.append(1)
            def test_2():
                values.append(2)
            def test_3():
                assert values == [1,2]
            class Testmygroup(object):
                reslist = values
                def test_1(self):
                    self.reslist.append(1)
                def test_2(self):
                    self.reslist.append(2)
                def test_3(self):
                    self.reslist.append(3)
                def test_4(self):
                    assert self.reslist == [1,2,1,2,3]
        """
        )
        passed, skipped, failed = reprec.countoutcomes()
        assert failed == skipped == 0
        assert passed == 7

    def test_collect_only_with_various_situations(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p = testrunnerer.makepyfile(
            test_one="""
                def test_one():
                    raise ValueError()

                class TestX(object):
                    def test_method_one(self):
                        pass

                class TestY(TestX):
                    pass
            """,
            test_three="xxxdsadsadsadsa",
            __init__="",
        )
        reprec = testrunnerer.inline_run("--collect-only", p.parent)

        itemstarted = reprec.getcalls("testrunner_itemcollected")
        assert len(itemstarted) == 3
        assert not reprec.getreports("testrunner_runtest_logreport")
        started = reprec.getcalls("testrunner_collectstart")
        finished = reprec.getreports("testrunner_collectreport")
        assert len(started) == len(finished)
        assert len(started) == 6
        colfail = [x for x in finished if x.failed]
        assert len(colfail) == 1

    def test_minus_x_import_error(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(__init__="")
        testrunnerer.makepyfile(test_one="xxxx", test_two="yyyy")
        reprec = testrunnerer.inline_run("-x", testrunnerer.path)
        finished = reprec.getreports("testrunner_collectreport")
        colfail = [x for x in finished if x.failed]
        assert len(colfail) == 1

    def test_minus_x_overridden_by_maxfail(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(__init__="")
        testrunnerer.makepyfile(test_one="xxxx", test_two="yyyy", test_third="zzz")
        reprec = testrunnerer.inline_run("-x", "--maxfail=2", testrunnerer.path)
        finished = reprec.getreports("testrunner_collectreport")
        colfail = [x for x in finished if x.failed]
        assert len(colfail) == 2


def test_plugin_specify(testrunnerer: Testrunnerer) -> None:
    with testrunner.raises(UsageError):
        testrunnerer.parseconfig("-p", "nqweotexistent")
    # testrunner.raises(ImportError,
    #    "config.do_configure(config)"
    # )


def test_plugin_already_exists(testrunnerer: Testrunnerer) -> None:
    config = testrunnerer.parseconfig("-p", "terminal")
    assert config.option.plugins == ["terminal"]
    config._do_configure()
    config._ensure_unconfigure()


def test_exclude(testrunnerer: Testrunnerer) -> None:
    hellodir = testrunnerer.mkdir("hello")
    hellodir.joinpath("test_hello.py").write_text("x y syntaxerror", encoding="utf-8")
    hello2dir = testrunnerer.mkdir("hello2")
    hello2dir.joinpath("test_hello2.py").write_text("x y syntaxerror", encoding="utf-8")
    testrunnerer.makepyfile(test_ok="def test_pass(): pass")
    result = testrunnerer.runtestrunner("--ignore=hello", "--ignore=hello2")
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*1 passed*"])


def test_exclude_glob(testrunnerer: Testrunnerer) -> None:
    hellodir = testrunnerer.mkdir("hello")
    hellodir.joinpath("test_hello.py").write_text("x y syntaxerror", encoding="utf-8")
    hello2dir = testrunnerer.mkdir("hello2")
    hello2dir.joinpath("test_hello2.py").write_text("x y syntaxerror", encoding="utf-8")
    hello3dir = testrunnerer.mkdir("hallo3")
    hello3dir.joinpath("test_hello3.py").write_text("x y syntaxerror", encoding="utf-8")
    subdir = testrunnerer.mkdir("sub")
    subdir.joinpath("test_hello4.py").write_text("x y syntaxerror", encoding="utf-8")
    testrunnerer.makepyfile(test_ok="def test_pass(): pass")
    result = testrunnerer.runtestrunner("--ignore-glob=*h[ea]llo*")
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*1 passed*"])


def test_deselect(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        test_a="""
        import testrunner

        def test_a1(): pass

        @testrunner.mark.parametrize('b', range(3))
        def test_a2(b): pass

        class TestClass:
            def test_c1(self): pass

            def test_c2(self): pass
    """
    )
    result = testrunnerer.runtestrunner(
        "-v",
        "--deselect=test_a.py::test_a2[1]",
        "--deselect=test_a.py::test_a2[2]",
        "--deselect=test_a.py::TestClass::test_c1",
    )
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*3 passed, 3 deselected*"])
    for line in result.stdout.lines:
        assert not line.startswith(("test_a.py::test_a2[1]", "test_a.py::test_a2[2]"))


def test_sessionfinish_with_start(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
        import os
        values = []
        def testrunner_sessionstart():
            values.append(os.getcwd())
            os.chdir("..")

        def testrunner_sessionfinish():
            assert values[0] == os.getcwd()

    """
    )
    res = testrunnerer.runtestrunner("--collect-only")
    assert res.ret == ExitCode.NO_TESTS_COLLECTED


def test_collection_args_do_not_duplicate_modules(testrunnerer: Testrunnerer) -> None:
    """Test that when multiple collection args are specified on the command line
    for the same module, only a single Module collector is created.

    Regression test for #723, #3358.
    """
    testrunnerer.makepyfile(
        **{
            "d/test_it": """
                def test_1(): pass
                def test_2(): pass
                """
        }
    )

    result = testrunnerer.runtestrunner(
        "--collect-only",
        "d/test_it.py::test_1",
        "d/test_it.py::test_2",
    )
    result.stdout.fnmatch_lines(
        [
            "  <Dir d>",
            "    <Module test_it.py>",
            "      <Function test_1>",
            "      <Function test_2>",
        ],
        consecutive=True,
    )

    # Different, but related case.
    result = testrunnerer.runtestrunner(
        "--collect-only",
        "--keep-duplicates",
        "d",
        "d",
    )
    result.stdout.fnmatch_lines(
        [
            "  <Dir d>",
            "    <Module test_it.py>",
            "      <Function test_1>",
            "      <Function test_2>",
            "      <Function test_1>",
            "      <Function test_2>",
        ],
        consecutive=True,
    )


@testrunner.mark.parametrize("path", ["root", "{relative}/root", "{environment}/root"])
def test_rootdir_option_arg(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch, path: str
) -> None:
    monkeypatch.setenv("PY_ROOTDIR_PATH", str(testrunnerer.path))
    path = path.format(relative=str(testrunnerer.path), environment="$PY_ROOTDIR_PATH")

    rootdir = testrunnerer.path / "root" / "tests"
    rootdir.mkdir(parents=True)
    testrunnerer.makepyfile(
        """
        import os
        def test_one():
            assert 1
    """
    )

    result = testrunnerer.runtestrunner(f"--rootdir={path}")
    result.stdout.fnmatch_lines(
        [
            f"*rootdir: {testrunnerer.path}/root",
            "root/test_rootdir_option_arg.py *",
            "*1 passed*",
        ]
    )


def test_rootdir_wrong_option_arg(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("--rootdir=wrong_dir")
    result.stderr.fnmatch_lines(
        ["*Directory *wrong_dir* not found. Check your '--rootdir' option.*"]
    )


def test_shouldfail_is_sticky(testrunnerer: Testrunnerer) -> None:
    """Test that session.shouldfail cannot be reset to False after being set.

    Issue #11706.
    """
    testrunnerer.makeconftest(
        """
        def testrunner_sessionfinish(session):
            assert session.shouldfail
            session.shouldfail = False
            assert session.shouldfail
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner

        def test_foo():
            testrunner.fail("This is a failing test")

        def test_bar(): pass
        """
    )

    result = testrunnerer.runtestrunner("--maxfail=1", "-Wall")

    result.assert_outcomes(failed=1, warnings=1)
    result.stdout.fnmatch_lines("*session.shouldfail cannot be unset*")


def test_shouldstop_is_sticky(testrunnerer: Testrunnerer) -> None:
    """Test that session.shouldstop cannot be reset to False after being set.

    Issue #11706.
    """
    testrunnerer.makeconftest(
        """
        def testrunner_sessionfinish(session):
            assert session.shouldstop
            session.shouldstop = False
            assert session.shouldstop
        """
    )
    testrunnerer.makepyfile(
        """
        import testrunner

        def test_foo():
            testrunner.fail("This is a failing test")

        def test_bar(): pass
        """
    )

    result = testrunnerer.runtestrunner("--stepwise", "-Wall")

    result.assert_outcomes(failed=1, warnings=1)
    result.stdout.fnmatch_lines("*session.shouldstop cannot be unset*")
