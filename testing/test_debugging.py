# mypy: allow-untyped-defs
from __future__ import annotations

import sys

import _testrunner._code
from _testrunner.debugging import _validate_usepdb_cls
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.testrunnerer import Testrunnerer
import testrunner


@testrunner.fixture(autouse=True)
def pdb_env(request):
    if "testrunnerer" in request.fixturenames:
        # Disable pdb++ with inner tests.
        testrunnerer = request.getfixturevalue("testrunnerer")
        testrunnerer._monkeypatch.setenv("PDBPP_HIJACK_PDB", "0")
        # Python 3.15+ defaults pdb to PyREPL, which injects ANSI colors and
        # bracketed-paste sequences into pexpect output and breaks exact
        # matching in these selftests. Force the classic REPL instead.
        # https://docs.python.org/3.15/whatsnew/3.15.html#pdb
        testrunnerer._monkeypatch.setenv("PYTHON_BASIC_REPL", "1")


def runpdb(testrunnerer: Testrunnerer, source: str):
    p = testrunnerer.makepyfile(source)
    return testrunnerer.runtestrunner_inprocess("--pdb", p)


def runpdb_and_get_stdout(testrunnerer: Testrunnerer, source: str):
    result = runpdb(testrunnerer, source)
    return result.stdout.str()


def runpdb_and_get_report(testrunnerer: Testrunnerer, source: str):
    result = runpdb(testrunnerer, source)
    reports = result.reprec.getreports("testrunner_runtest_logreport")
    assert len(reports) == 3, reports  # setup/call/teardown
    return reports[1]


@testrunner.fixture
def custom_pdb_calls() -> list[str]:
    called = []

    # install dummy debugger class and track which methods were called on it
    class _CustomPdb:
        quitting = False

        def __init__(self, *args, **kwargs):
            called.append("init")

        def reset(self):
            called.append("reset")

        def interaction(self, *args):
            called.append("interaction")

        # Methods which we copy docstrings to.
        def do_debug(self, *args):  # pragma: no cover
            pass

        def do_continue(self, *args):  # pragma: no cover
            pass

        def do_quit(self, *args):  # pragma: no cover
            pass

    _testrunner._CustomPdb = _CustomPdb  # type: ignore
    return called


@testrunner.fixture
def custom_debugger_hook():
    called = []

    # install dummy debugger class and track which methods were called on it
    class _CustomDebugger:
        def __init__(self, *args, **kwargs):
            called.append("init")

        def reset(self):
            called.append("reset")

        def interaction(self, *args):
            called.append("interaction")

        def set_trace(self, frame):
            print("**CustomDebugger**")
            called.append("set_trace")

        # Methods which we copy docstrings to.
        def do_debug(self, *args):  # pragma: no cover
            pass

        def do_continue(self, *args):  # pragma: no cover
            pass

        def do_quit(self, *args):  # pragma: no cover
            pass

    _testrunner._CustomDebugger = _CustomDebugger  # type: ignore
    yield called
    del _testrunner._CustomDebugger  # type: ignore


class TestPDB:
    @testrunner.fixture
    def pdblist(self, request):
        monkeypatch = request.getfixturevalue("monkeypatch")
        pdblist = []

        def mypdb(*args):
            pdblist.append(args)

        plugin = request.config.pluginmanager.getplugin("debugging")
        monkeypatch.setattr(plugin, "post_mortem", mypdb)
        return pdblist

    def test_pdb_on_fail(self, testrunnerer: Testrunnerer, pdblist) -> None:
        rep = runpdb_and_get_report(
            testrunnerer,
            """
            def test_func():
                assert 0
        """,
        )
        assert rep.failed
        assert len(pdblist) == 1
        if sys.version_info < (3, 13):
            tb = _testrunner._code.Traceback(pdblist[0][0])
        else:
            tb = _testrunner._code.Traceback(pdblist[0][0].__traceback__)
        assert tb[-1].name == "test_func"

    def test_pdb_on_xfail(self, testrunnerer: Testrunnerer, pdblist) -> None:
        rep = runpdb_and_get_report(
            testrunnerer,
            """
            import testrunner
            @testrunner.mark.xfail
            def test_func():
                assert 0
        """,
        )
        assert "xfail" in rep.keywords
        assert not pdblist

    def test_pdb_on_skip(self, testrunnerer, pdblist) -> None:
        rep = runpdb_and_get_report(
            testrunnerer,
            """
            import testrunner
            def test_func():
                testrunner.skip("hello")
        """,
        )
        assert rep.skipped
        assert len(pdblist) == 0

    def test_pdb_on_top_level_raise_skiptest(self, testrunnerer, pdblist) -> None:
        stdout = runpdb_and_get_stdout(
            testrunnerer,
            """
            import unittest
            raise unittest.SkipTest("This is a common way to skip an entire file.")
        """,
        )
        assert "entering PDB" not in stdout, stdout

    def test_pdb_on_BdbQuit(self, testrunnerer, pdblist) -> None:
        rep = runpdb_and_get_report(
            testrunnerer,
            """
            import bdb
            def test_func():
                raise bdb.BdbQuit
        """,
        )
        assert rep.failed
        assert len(pdblist) == 0

    def test_pdb_on_KeyboardInterrupt(self, testrunnerer, pdblist) -> None:
        rep = runpdb_and_get_report(
            testrunnerer,
            """
            def test_func():
                raise KeyboardInterrupt
        """,
        )
        assert rep.failed
        assert len(pdblist) == 1

    @staticmethod
    def flush(child):
        if child.isalive():
            # Read if the test has not (e.g. test_pdb_unittest_skip).
            child.read()
            child.wait()
        assert not child.isalive()

    def test_pdb_unittest_postmortem(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import unittest
            class Blub(unittest.TestCase):
                def tearDown(self):
                    self.filename = None
                def test_false(self):
                    self.filename = 'debug' + '.me'
                    assert 0
        """
        )
        child = testrunnerer.spawn_testrunner(f"--pdb {p1}")
        child.expect("Pdb")
        child.sendline("p self.filename")
        child.sendeof()
        rest = child.read().decode("utf8")
        assert "debug.me" in rest
        self.flush(child)

    def test_pdb_unittest_skip(self, testrunnerer: Testrunnerer) -> None:
        """Test for issue #2137"""
        p1 = testrunnerer.makepyfile(
            """
            import unittest
            @unittest.skipIf(True, 'Skipping also with pdb active')
            class MyTestCase(unittest.TestCase):
                def test_one(self):
                    assert 0
        """
        )
        child = testrunnerer.spawn_testrunner(f"-rs --pdb {p1}")
        child.expect("Skipping also with pdb active")
        child.expect_exact("= 1 skipped in")
        child.sendeof()
        self.flush(child)

    def test_pdb_print_captured_stdout_and_stderr(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def test_1():
                import sys
                sys.stderr.write("get\\x20rekt")
                print("get\\x20rekt")
                assert False

            def test_not_called_due_to_quit():
                pass
        """
        )
        child = testrunnerer.spawn_testrunner(f"--pdb {p1}")
        child.expect("captured stdout")
        child.expect("get rekt")
        child.expect("captured stderr")
        child.expect("get rekt")
        child.expect("traceback")
        child.expect("def test_1")
        child.expect("Pdb")
        child.sendeof()
        rest = child.read().decode("utf8")
        assert "Exit: Quitting debugger" in rest
        assert "= 1 failed in" in rest
        assert "def test_1" not in rest
        assert "get rekt" not in rest
        self.flush(child)

    def test_pdb_dont_print_empty_captured_stdout_and_stderr(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def test_1():
                assert False
        """
        )
        child = testrunnerer.spawn_testrunner(f"--pdb {p1}")
        child.expect("Pdb")
        output = child.before.decode("utf8")
        child.sendeof()
        assert "captured stdout" not in output
        assert "captured stderr" not in output
        self.flush(child)

    @testrunner.mark.parametrize("showcapture", ["all", "no", "log"])
    def test_pdb_print_captured_logs(self, testrunnerer, showcapture: str) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def test_1():
                import logging
                logging.warning("get " + "rekt")
                assert False
        """
        )
        child = testrunnerer.spawn_testrunner(
            f"--show-capture={showcapture} --pdb {p1}"
        )
        if showcapture in ("all", "log"):
            child.expect("captured log")
            child.expect("get rekt")
        child.expect("Pdb")
        child.sendeof()
        rest = child.read().decode("utf8")
        assert "1 failed" in rest
        self.flush(child)

    def test_pdb_print_captured_logs_nologging(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def test_1():
                import logging
                logging.warning("get " + "rekt")
                assert False
        """
        )
        child = testrunnerer.spawn_testrunner(
            f"--show-capture=all --pdb -p no:logging {p1}"
        )
        child.expect("get rekt")
        output = child.before.decode("utf8")
        assert "captured log" not in output
        child.expect("Pdb")
        child.sendeof()
        rest = child.read().decode("utf8")
        assert "1 failed" in rest
        self.flush(child)

    def test_pdb_interaction_exception(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            def globalfunc():
                pass
            def test_1():
                with testrunner.raises(ValueError):
                    globalfunc()
        """
        )
        child = testrunnerer.spawn_testrunner(f"--pdb {p1}")
        child.expect(".*def test_1")
        child.expect(r"with testrunner.raises\(ValueError\)")
        child.expect("Pdb")
        child.sendline("globalfunc")
        child.expect(".*function")
        child.sendeof()
        child.expect("1 failed")
        self.flush(child)

    def test_pdb_interaction_on_collection_issue181(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            xxx
        """
        )
        child = testrunnerer.spawn_testrunner(f"--pdb {p1}")
        # child.expect(".*import testrunner.*")
        child.expect("Pdb")
        child.sendline("c")
        child.expect("1 error")
        self.flush(child)

    def test_pdb_interaction_on_internal_error(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_runtest_protocol():
                0/0
        """
        )
        p1 = testrunnerer.makepyfile("def test_func(): pass")
        child = testrunnerer.spawn_testrunner(f"--pdb {p1}")
        child.expect("Pdb")

        # INTERNALERROR is only displayed once via terminal reporter.
        assert (
            len(
                [
                    x
                    for x in child.before.decode().splitlines()
                    if x.startswith("INTERNALERROR> Traceback")
                ]
            )
            == 1
        )

        child.sendeof()
        self.flush(child)

    def test_pdb_prevent_ConftestImportFailure_hiding_exception(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile("def test_func(): pass")
        sub_dir = testrunnerer.path.joinpath("ns")
        sub_dir.mkdir()
        sub_dir.joinpath("conftest").with_suffix(".py").write_text(
            "import unknown", "utf-8"
        )
        sub_dir.joinpath("test_file").with_suffix(".py").write_text(
            "def test_func(): pass", "utf-8"
        )

        result = testrunnerer.runtestrunner_subprocess("--pdb", ".")
        result.stdout.fnmatch_lines(["-> import unknown"])

    @testrunner.mark.xfail(reason="#10042", strict=False)
    def test_pdb_interaction_capturing_simple(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            def test_1():
                i = 0
                print("hello17")
                testrunner.set_trace()
                i == 1
                assert 0
        """
        )
        child = testrunnerer.spawn_testrunner(str(p1))
        child.expect(r"test_1\(\)")
        child.expect("i == 1")
        child.expect("Pdb")
        child.sendline("c")
        rest = child.read().decode("utf-8")
        assert "AssertionError" in rest
        assert "1 failed" in rest
        assert "def test_1" in rest
        assert "hello17" in rest  # out is captured
        self.flush(child)

    def test_pdb_set_trace_kwargs(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            def test_1():
                i = 0
                print("hello17")
                testrunner.set_trace(header="== my_header ==")
                x = 3
                assert 0
        """
        )
        child = testrunnerer.spawn_testrunner(str(p1))
        child.expect("== my_header ==")
        assert "PDB set_trace" not in child.before.decode()
        child.expect("Pdb")
        child.sendline("c")
        rest = child.read().decode("utf-8")
        assert "1 failed" in rest
        assert "def test_1" in rest
        assert "hello17" in rest  # out is captured
        self.flush(child)

    def test_pdb_set_trace_interception(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import pdb
            def test_1():
                pdb.set_trace()
        """
        )
        child = testrunnerer.spawn_testrunner(str(p1))
        child.expect("test_1")
        child.expect("Pdb")
        child.sendline("q")
        rest = child.read().decode("utf8")
        assert "no tests ran" in rest
        assert "reading from stdin while output" not in rest
        assert "BdbQuit" not in rest
        self.flush(child)

    def test_pdb_and_capsys(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            def test_1(capsys):
                print("hello1")
                testrunner.set_trace()
        """
        )
        child = testrunnerer.spawn_testrunner(str(p1))
        child.expect("test_1")
        child.send("capsys.readouterr()\n")
        child.expect("hello1")
        child.sendeof()
        child.read()
        self.flush(child)

    def test_pdb_with_caplog_on_pdb_invocation(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def test_1(capsys, caplog):
                import logging
                logging.getLogger(__name__).warning("some_warning")
                assert 0
        """
        )
        child = testrunnerer.spawn_testrunner(f"--pdb {p1!s}")
        child.send("caplog.record_tuples\n")
        child.expect_exact(
            "[('test_pdb_with_caplog_on_pdb_invocation', 30, 'some_warning')]"
        )
        child.sendeof()
        child.read()
        self.flush(child)

    def test_set_trace_capturing_afterwards(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import pdb
            def test_1():
                pdb.set_trace()
            def test_2():
                print("hello")
                assert 0
        """
        )
        child = testrunnerer.spawn_testrunner(str(p1))
        child.expect("test_1")
        child.send("c\n")
        child.expect("test_2")
        child.expect("Captured")
        child.expect("hello")
        child.sendeof()
        child.read()
        self.flush(child)

    def test_pdb_interaction_doctest(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def function_1():
                '''
                >>> i = 0
                >>> assert i == 1
                '''
        """
        )
        child = testrunnerer.spawn_testrunner(f"--doctest-modules --pdb {p1}")
        child.expect("Pdb")

        assert "UNEXPECTED EXCEPTION: AssertionError()" in child.before.decode("utf8")

        child.sendline("'i=%i.' % i")
        child.expect("Pdb")
        assert "\r\n'i=0.'\r\n" in child.before.decode("utf8")

        child.sendeof()
        rest = child.read().decode("utf8")
        assert "! _testrunner.outcomes.Exit: Quitting debugger !" in rest
        assert "BdbQuit" not in rest
        assert "1 failed" in rest
        self.flush(child)

    def test_doctest_set_trace_quit(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def function_1():
                '''
                >>> __import__('pdb').set_trace()
                '''
        """
        )
        # NOTE: does not use testrunner.set_trace, but Python's patched pdb,
        #       therefore "-s" is required.
        child = testrunnerer.spawn_testrunner(f"--doctest-modules --pdb -s {p1}")
        child.expect("Pdb")
        child.sendline("q")
        rest = child.read().decode("utf8")

        assert "! _testrunner.outcomes.Exit: Quitting debugger !" in rest
        assert "= no tests ran in" in rest
        assert "BdbQuit" not in rest
        assert "UNEXPECTED EXCEPTION" not in rest

    @testrunner.mark.xfail(reason="#10042", strict=False)
    def test_pdb_interaction_capturing_twice(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            def test_1():
                i = 0
                print("hello17")
                testrunner.set_trace()
                x = 3
                print("hello18")
                testrunner.set_trace()
                x = 4
                assert 0
        """
        )
        child = testrunnerer.spawn_testrunner(str(p1))
        child.expect(r"PDB set_trace \(IO-capturing turned off\)")
        child.expect("test_1")
        child.expect("x = 3")
        child.expect("Pdb")
        child.sendline("c")
        child.expect(r"PDB continue \(IO-capturing resumed\)")
        child.expect(r"PDB set_trace \(IO-capturing turned off\)")
        child.expect("x = 4")
        child.expect("Pdb")
        child.sendline("c")
        child.expect("_ test_1 _")
        child.expect("def test_1")
        rest = child.read().decode("utf8")
        assert "Captured stdout call" in rest
        assert "hello17" in rest  # out is captured
        assert "hello18" in rest  # out is captured
        assert "1 failed" in rest
        self.flush(child)

    @testrunner.mark.xfail(reason="#10042", strict=False)
    def test_pdb_with_injected_do_debug(self, testrunnerer: Testrunnerer) -> None:
        """Simulates pdbpp, which injects Pdb into do_debug, and uses
        self.__class__ in do_continue.
        """
        p1 = testrunnerer.makepyfile(
            mytest="""
            import pdb
            import testrunner

            count_continue = 0

            class CustomPdb(pdb.Pdb, object):
                def do_debug(self, arg):
                    import sys
                    import types

                    do_debug_func = pdb.Pdb.do_debug

                    newglobals = do_debug_func.__globals__.copy()
                    newglobals['Pdb'] = self.__class__
                    orig_do_debug = types.FunctionType(
                        do_debug_func.__code__, newglobals,
                        do_debug_func.__name__, do_debug_func.__defaults__,
                    )
                    return orig_do_debug(self, arg)
                do_debug.__doc__ = pdb.Pdb.do_debug.__doc__

                def do_continue(self, *args, **kwargs):
                    global count_continue
                    count_continue += 1
                    return super(CustomPdb, self).do_continue(*args, **kwargs)

            def foo():
                print("print_from_foo")

            def test_1():
                i = 0
                print("hello17")
                testrunner.set_trace()
                x = 3
                print("hello18")

                assert count_continue == 2, "unexpected_failure: %d != 2" % count_continue
                testrunner.fail("expected_failure")
        """
        )
        child = testrunnerer.spawn_testrunner(f"--pdbcls=mytest:CustomPdb {p1!s}")
        child.expect(r"PDB set_trace \(IO-capturing turned off\)")
        child.expect(r"\n\(Pdb")
        child.sendline("debug foo()")
        child.expect("ENTERING RECURSIVE DEBUGGER")
        child.expect(r"\n\(\(Pdb")
        child.sendline("c")
        child.expect("LEAVING RECURSIVE DEBUGGER")
        assert b"PDB continue" not in child.before
        # No extra newline.
        assert child.before.endswith(b"c\r\nprint_from_foo\r\n")

        # set_debug should not raise outcomes. Exit, if used recursively.
        child.sendline("debug 42")
        child.sendline("q")
        child.expect("LEAVING RECURSIVE DEBUGGER")
        assert b"ENTERING RECURSIVE DEBUGGER" in child.before
        assert b"Quitting debugger" not in child.before

        child.sendline("c")
        child.expect(r"PDB continue \(IO-capturing resumed\)")
        rest = child.read().decode("utf8")
        assert "hello17" in rest  # out is captured
        assert "hello18" in rest  # out is captured
        assert "1 failed" in rest
        assert "Failed: expected_failure" in rest
        assert "AssertionError: unexpected_failure" not in rest
        self.flush(child)

    def test_pdb_without_capture(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            def test_1():
                testrunner.set_trace()
        """
        )
        child = testrunnerer.spawn_testrunner(f"-s {p1}")
        child.expect(r">>> PDB set_trace >>>")
        child.expect("Pdb")
        child.sendline("c")
        child.expect(r">>> PDB continue >>>")
        child.expect("1 passed")
        self.flush(child)

    @testrunner.mark.parametrize("capture_arg", ("", "-s", "-p no:capture"))
    def test_pdb_continue_with_recursive_debug(
        self, capture_arg, testrunnerer: Testrunnerer
    ) -> None:
        """Full coverage for do_debug without capturing.

        This is very similar to test_pdb_interaction_continue_recursive in general,
        but mocks out ``pdb.set_trace`` for providing more coverage.
        """
        p1 = testrunnerer.makepyfile(
            """
            try:
                input = raw_input
            except NameError:
                pass

            def set_trace():
                __import__('pdb').set_trace()

            def test_1(monkeypatch):
                import _testrunner.debugging

                class testrunnerPDBTest(_testrunner.debugging.testrunnerPDB):
                    @classmethod
                    def set_trace(cls, *args, **kwargs):
                        # Init TestrunnerPdbWrapper to handle capturing.
                        _pdb = cls._init_pdb("set_trace", *args, **kwargs)

                        # Mock out pdb.Pdb.do_continue.
                        import pdb
                        pdb.Pdb.do_continue = lambda self, arg: None

                        print("===" + " SET_TRACE ===")
                        assert input() == "debug set_trace()"

                        # Simulate TestrunnerPdbWrapper.do_debug
                        cls._recursive_debug += 1
                        print("ENTERING RECURSIVE DEBUGGER")
                        print("===" + " SET_TRACE_2 ===")

                        assert input() == "c"
                        _pdb.do_continue("")
                        print("===" + " SET_TRACE_3 ===")

                        # Simulate TestrunnerPdbWrapper.do_debug
                        print("LEAVING RECURSIVE DEBUGGER")
                        cls._recursive_debug -= 1

                        print("===" + " SET_TRACE_4 ===")
                        assert input() == "c"
                        _pdb.do_continue("")

                    def do_continue(self, arg):
                        print("=== do_continue")

                monkeypatch.setattr(_testrunner.debugging, "testrunnerPDB", testrunnerPDBTest)

                import pdb
                monkeypatch.setattr(pdb, "set_trace", testrunnerPDBTest.set_trace)

                set_trace()
        """
        )
        child = testrunnerer.spawn_testrunner(f"--tb=short {p1} {capture_arg}")
        child.expect("=== SET_TRACE ===")
        before = child.before.decode("utf8")
        if not capture_arg:
            assert ">>> PDB set_trace (IO-capturing turned off) >>>" in before
        else:
            assert ">>> PDB set_trace >>>" in before
        child.sendline("debug set_trace()")
        child.expect("=== SET_TRACE_2 ===")
        before = child.before.decode("utf8")
        assert "\r\nENTERING RECURSIVE DEBUGGER\r\n" in before
        child.sendline("c")
        child.expect("=== SET_TRACE_3 ===")

        # No continue message with recursive debugging.
        before = child.before.decode("utf8")
        assert ">>> PDB continue " not in before

        child.sendline("c")
        child.expect("=== SET_TRACE_4 ===")
        before = child.before.decode("utf8")
        assert "\r\nLEAVING RECURSIVE DEBUGGER\r\n" in before
        child.sendline("c")
        rest = child.read().decode("utf8")
        if not capture_arg:
            assert "> PDB continue (IO-capturing resumed) >" in rest
        else:
            assert "> PDB continue >" in rest
        assert "= 1 passed in" in rest

    def test_pdb_used_outside_test(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            testrunner.set_trace()
            x = 5
        """
        )
        if sys.version_info[:2] >= (3, 13):
            break_line = "testrunner.set_trace()"
        else:
            break_line = "x = 5"
        child = testrunnerer.spawn(f"{sys.executable} {p1}")
        child.expect_exact(break_line)
        child.expect_exact("Pdb")
        child.sendeof()
        self.flush(child)

    def test_pdb_used_in_generate_tests(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            def testrunner_generate_tests(metafunc):
                testrunner.set_trace()
                x = 5
            def test_foo(a):
                pass
        """
        )
        if sys.version_info[:2] >= (3, 13):
            break_line = "testrunner.set_trace()"
        else:
            break_line = "x = 5"
        child = testrunnerer.spawn_testrunner(str(p1))
        child.expect_exact(break_line)
        child.expect_exact("Pdb")
        child.sendeof()
        self.flush(child)

    def test_pdb_collection_failure_is_shown(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile("xxx")
        result = testrunnerer.runtestrunner_subprocess("--pdb", p1)
        result.stdout.fnmatch_lines(
            ["E   NameError: *xxx*", "*! *Exit: Quitting debugger !*"]  # due to EOF
        )

    @testrunner.mark.parametrize("post_mortem", (False, True))
    def test_enter_leave_pdb_hooks_are_called(
        self, post_mortem, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makeconftest(
            """
            mypdb = None

            def testrunner_configure(config):
                config.testing_verification = 'configured'

            def testrunner_enter_pdb(config, pdb):
                assert config.testing_verification == 'configured'
                print('enter_pdb_hook')

                global mypdb
                mypdb = pdb
                mypdb.set_attribute = "bar"

            def testrunner_leave_pdb(config, pdb):
                assert config.testing_verification == 'configured'
                print('leave_pdb_hook')

                global mypdb
                assert mypdb is pdb
                assert mypdb.set_attribute == "bar"
        """
        )
        p1 = testrunnerer.makepyfile(
            """
            import testrunner

            def test_set_trace():
                testrunner.set_trace()
                assert 0

            def test_post_mortem():
                assert 0
        """
        )
        if post_mortem:
            child = testrunnerer.spawn_testrunner(
                str(p1) + " --pdb -s -k test_post_mortem"
            )
        else:
            child = testrunnerer.spawn_testrunner(str(p1) + " -k test_set_trace")
        child.expect("enter_pdb_hook")
        child.sendline("c")
        if post_mortem:
            child.expect(r"PDB continue")
        else:
            child.expect(r"PDB continue \(IO-capturing resumed\)")
            child.expect("Captured stdout call")
        rest = child.read().decode("utf8")
        assert "leave_pdb_hook" in rest
        assert "1 failed" in rest
        self.flush(child)

    def test_pdb_custom_cls(
        self, testrunnerer: Testrunnerer, custom_pdb_calls: list[str]
    ) -> None:
        p1 = testrunnerer.makepyfile("""xxx """)
        result = testrunnerer.runtestrunner_inprocess(
            "--pdb", "--pdbcls=_testrunner:_CustomPdb", p1
        )
        result.stdout.fnmatch_lines(["*NameError*xxx*", "*1 error*"])
        assert custom_pdb_calls == ["init", "reset", "interaction"]

    def test_pdb_custom_cls_invalid(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner_inprocess("--pdbcls=invalid")
        result.stderr.fnmatch_lines(
            [
                "*: error: argument --pdbcls: 'invalid' is not in the format 'modname:classname'"
            ]
        )

    def test_pdb_validate_usepdb_cls(self):
        assert _validate_usepdb_cls("os.path:dirname.__name__") == (
            "os.path",
            "dirname.__name__",
        )

        assert _validate_usepdb_cls("pdb:DoesNotExist") == ("pdb", "DoesNotExist")

    def test_pdb_custom_cls_without_pdb(
        self, testrunnerer: Testrunnerer, custom_pdb_calls: list[str]
    ) -> None:
        p1 = testrunnerer.makepyfile("""xxx """)
        result = testrunnerer.runtestrunner_inprocess(
            "--pdbcls=_testrunner:_CustomPdb", p1
        )
        result.stdout.fnmatch_lines(["*NameError*xxx*", "*1 error*"])
        assert custom_pdb_calls == []

    def test_pdb_custom_cls_with_set_trace(
        self,
        testrunnerer: Testrunnerer,
        monkeypatch: MonkeyPatch,
    ) -> None:
        testrunnerer.makepyfile(
            custom_pdb="""
            class CustomPdb(object):
                def __init__(self, *args, **kwargs):
                    skip = kwargs.pop("skip")
                    assert skip == ["foo.*"]
                    print("__init__")
                    super(CustomPdb, self).__init__(*args, **kwargs)

                def set_trace(*args, **kwargs):
                    print('custom set_trace>')
         """
        )
        p1 = testrunnerer.makepyfile(
            """
            import testrunner

            def test_foo():
                testrunner.set_trace(skip=['foo.*'])
        """
        )
        monkeypatch.setenv("PYTHONPATH", str(testrunnerer.path))
        child = testrunnerer.spawn_testrunner(f"--pdbcls=custom_pdb:CustomPdb {p1!s}")

        child.expect("__init__")
        child.expect("custom set_trace>")
        self.flush(child)

    @testrunner.mark.skipif(
        sys.version_info < (3, 13),
        reason="Navigating exception chains was introduced in 3.13",
    )
    def test_pdb_exception_chain_navigation(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def inner_raise():
                is_inner = True
                raise RuntimeError("Woops")

            def outer_raise():
                is_inner = False
                try:
                    inner_raise()
                except RuntimeError:
                    raise RuntimeError("Woopsie")

            def test_1():
                outer_raise()
                assert True
        """
        )
        child = testrunnerer.spawn_testrunner(f"--pdb {p1}")
        child.expect("Pdb")
        child.sendline("is_inner")
        child.expect_exact("False")
        child.sendline("exceptions 0")
        child.sendline("is_inner")
        child.expect_exact("True")
        child.sendeof()
        self.flush(child)

    def test_pdb_wrapped_commands_docstrings(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def test_1():
                assert False
            """
        )

        child = testrunnerer.spawn_testrunner(f"--pdb {p1}")
        child.expect("Pdb")

        # Verify no undocumented commands
        child.sendline("help")
        child.expect("Documented commands")
        assert "Undocumented commands" not in child.before.decode()

        child.sendline("help continue")
        child.expect("Continue execution")
        child.expect("Pdb")

        child.sendline("help debug")
        child.expect("Enter a recursive debugger")
        child.expect("Pdb")

        child.sendline("c")
        child.sendeof()
        self.flush(child)


class TestDebuggingBreakpoints:
    @testrunner.mark.parametrize("arg", ["--pdb", ""])
    def test_sys_breakpointhook_configure_and_unconfigure(
        self, testrunnerer: Testrunnerer, arg: str
    ) -> None:
        """
        Test that sys.breakpointhook is set to the custom Pdb class once configured, test that
        hook is reset to system value once testrunner has been unconfigured
        """
        testrunnerer.makeconftest(
            """
            import sys
            from testrunner import hookimpl
            from _testrunner.debugging import testrunnerPDB

            def testrunner_configure(config):
                config.add_cleanup(check_restored)

            def check_restored():
                assert sys.breakpointhook == sys.__breakpointhook__

            def test_check():
                assert sys.breakpointhook == testrunnerPDB.set_trace
        """
        )
        testrunnerer.makepyfile(
            """
            def test_nothing(): pass
        """
        )
        args = (arg,) if arg else ()
        result = testrunnerer.runtestrunner_subprocess(*args)
        result.stdout.fnmatch_lines(["*1 passed in *"])

    def test_pdb_custom_cls(
        self, testrunnerer: Testrunnerer, custom_debugger_hook, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PYTHONBREAKPOINT", raising=False)
        p1 = testrunnerer.makepyfile(
            """
            def test_nothing():
                breakpoint()
        """
        )
        result = testrunnerer.runtestrunner_inprocess(
            "--pdb", "--pdbcls=_testrunner:_CustomDebugger", p1
        )
        result.stdout.fnmatch_lines(["*CustomDebugger*", "*1 passed*"])
        assert custom_debugger_hook == ["init", "set_trace"]

    @testrunner.mark.parametrize("arg", ["--pdb", ""])
    def test_environ_custom_class(
        self, testrunnerer: Testrunnerer, custom_debugger_hook, arg: str
    ) -> None:
        testrunnerer.makeconftest(
            """
            import os
            import sys

            os.environ['PYTHONBREAKPOINT'] = '_testrunner._CustomDebugger.set_trace'

            def testrunner_configure(config):
                config.add_cleanup(check_restored)

            def check_restored():
                assert sys.breakpointhook == sys.__breakpointhook__

            def test_check():
                import _testrunner
                assert sys.breakpointhook is _testrunner._CustomDebugger.set_trace
        """
        )
        testrunnerer.makepyfile(
            """
            def test_nothing(): pass
        """
        )
        args = (arg,) if arg else ()
        result = testrunnerer.runtestrunner_subprocess(*args)
        result.stdout.fnmatch_lines(["*1 passed in *"])

    def test_sys_breakpoint_interception(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PYTHONBREAKPOINT", raising=False)
        p1 = testrunnerer.makepyfile(
            """
            def test_1():
                breakpoint()
        """
        )
        child = testrunnerer.spawn_testrunner(str(p1))
        child.expect("test_1")
        child.expect("Pdb")
        child.sendline("quit")
        rest = child.read().decode("utf8")
        assert "Quitting debugger" in rest
        assert "reading from stdin while output" not in rest
        TestPDB.flush(child)

    @testrunner.mark.xfail(reason="#10042", strict=False)
    def test_pdb_not_altered(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import pdb
            def test_1():
                pdb.set_trace()
                assert 0
        """
        )
        child = testrunnerer.spawn_testrunner(str(p1))
        child.expect("test_1")
        child.expect("Pdb")
        child.sendline("c")
        rest = child.read().decode("utf8")
        assert "1 failed" in rest
        assert "reading from stdin while output" not in rest
        TestPDB.flush(child)


class TestTraceOption:
    def test_trace_sets_breakpoint(self, testrunnerer: Testrunnerer) -> None:
        p1 = testrunnerer.makepyfile(
            """
            def test_1():
                assert True

            def test_2():
                pass

            def test_3():
                pass
            """
        )
        child = testrunnerer.spawn_testrunner("--trace " + str(p1))
        child.expect("test_1")
        child.expect("Pdb")
        child.sendline("c")
        child.expect("test_2")
        child.expect("Pdb")
        child.sendline("c")
        child.expect("test_3")
        child.expect("Pdb")
        child.sendline("q")
        child.expect_exact("Exit: Quitting debugger")
        rest = child.read().decode("utf8")
        assert "= 2 passed in" in rest
        assert "reading from stdin while output" not in rest
        # Only printed once - not on stderr.
        assert "Exit: Quitting debugger" not in child.before.decode("utf8")
        TestPDB.flush(child)

    def test_trace_with_parametrize_handles_shared_fixtureinfo(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p1 = testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.parametrize('myparam', [1,2])
            def test_1(myparam, request):
                assert myparam in (1, 2)
                assert request.function.__name__ == "test_1"
            @testrunner.mark.parametrize('func', [1,2])
            def test_func(func, request):
                assert func in (1, 2)
                assert request.function.__name__ == "test_func"
            @testrunner.mark.parametrize('myparam', [1,2])
            def test_func_kw(myparam, request, func="func_kw"):
                assert myparam in (1, 2)
                assert func == "func_kw"
                assert request.function.__name__ == "test_func_kw"
            """
        )
        child = testrunnerer.spawn_testrunner("--trace " + str(p1))
        for func, argname in [
            ("test_1", "myparam"),
            ("test_func", "func"),
            ("test_func_kw", "myparam"),
        ]:
            child.expect_exact("> PDB runcall (IO-capturing turned off) >")
            child.expect_exact(func)
            child.expect_exact("Pdb")
            child.sendline("args")
            child.expect_exact(f"{argname} = 1\r\n")
            child.expect_exact("Pdb")
            child.sendline("c")
            child.expect_exact("Pdb")
            child.sendline("args")
            child.expect_exact(f"{argname} = 2\r\n")
            child.expect_exact("Pdb")
            child.sendline("c")
            child.expect_exact("> PDB continue (IO-capturing resumed) >")
        rest = child.read().decode("utf8")
        assert "= 6 passed in" in rest
        assert "reading from stdin while output" not in rest
        # Only printed once - not on stderr.
        assert "Exit: Quitting debugger" not in child.before.decode("utf8")
        TestPDB.flush(child)


def test_trace_after_runtestrunner(testrunnerer: Testrunnerer) -> None:
    """Test that debugging's testrunner_configure is reentrant."""
    p1 = testrunnerer.makepyfile(
        """
        from _testrunner.debugging import testrunnerPDB

        def test_outer(testrunnerer) -> None:
            assert len(testrunnerPDB._saved) == 1

            testrunnerer.makepyfile(
                \"""
                from _testrunner.debugging import testrunnerPDB

                def test_inner():
                    assert len(testrunnerPDB._saved) == 2
                    print()
                    print("test_inner_" + "end")
                \"""
            )

            result = testrunnerer.runtestrunner("-s", "-k", "test_inner")
            assert result.ret == 0

            assert len(testrunnerPDB._saved) == 1
    """
    )
    result = testrunnerer.runtestrunner_subprocess("-s", "-p", "testrunnerer", str(p1))
    result.stdout.fnmatch_lines(["test_inner_end"])
    assert result.ret == 0


def test_quit_with_swallowed_SystemExit(testrunnerer: Testrunnerer) -> None:
    """Test that debugging's testrunner_configure is reentrant."""
    p1 = testrunnerer.makepyfile(
        """
        def call_pdb_set_trace():
            __import__('pdb').set_trace()


        def test_1():
            try:
                call_pdb_set_trace()
            except SystemExit:
                pass


        def test_2():
            pass
    """
    )
    child = testrunnerer.spawn_testrunner(str(p1))
    child.expect("Pdb")
    child.sendline("q")
    child.expect_exact("Exit: Quitting debugger")
    rest = child.read().decode("utf8")
    assert "no tests ran" in rest
    TestPDB.flush(child)


@testrunner.mark.parametrize("fixture", ("capfd", "capsys"))
@testrunner.mark.xfail(reason="#10042", strict=False)
def test_pdb_suspends_fixture_capturing(
    testrunnerer: Testrunnerer, fixture: str
) -> None:
    """Using "-s" with testrunner should suspend/resume fixture capturing."""
    p1 = testrunnerer.makepyfile(
        f"""
        def test_inner({fixture}):
            import sys

            print("out_inner_before")
            sys.stderr.write("err_inner_before\\n")

            __import__("pdb").set_trace()

            print("out_inner_after")
            sys.stderr.write("err_inner_after\\n")

            out, err = {fixture}.readouterr()
            assert out =="out_inner_before\\nout_inner_after\\n"
            assert err =="err_inner_before\\nerr_inner_after\\n"
        """
    )

    child = testrunnerer.spawn_testrunner(str(p1) + " -s")

    child.expect("Pdb")
    before = child.before.decode("utf8")
    assert (
        f"> PDB set_trace (IO-capturing turned off for fixture {fixture}) >" in before
    )

    # Test that capturing is really suspended.
    child.sendline("p 40 + 2")
    child.expect("Pdb")
    assert "\r\n42\r\n" in child.before.decode("utf8")

    child.sendline("c")
    rest = child.read().decode("utf8")
    assert "out_inner" not in rest
    assert "err_inner" not in rest

    TestPDB.flush(child)
    assert child.exitstatus == 0
    assert "= 1 passed in" in rest
    assert f"> PDB continue (IO-capturing resumed for fixture {fixture}) >" in rest


def test_pdbcls_via_local_module(testrunnerer: Testrunnerer) -> None:
    """It should be imported in testrunner_configure or later only."""
    p1 = testrunnerer.makepyfile(
        """
        def test():
            print("before_set_trace")
            __import__("pdb").set_trace()
        """,
        mypdb="""
        class Wrapped:
            class MyPdb:
                def set_trace(self, *args):
                    print("set_trace_called", args)

                def runcall(self, *args, **kwds):
                    print("runcall_called", args, kwds)

                # Methods which we copy the docstring over.
                def do_debug(self, *args):
                    pass

                def do_continue(self, *args):
                    pass

                def do_quit(self, *args):
                    pass
        """,
    )
    result = testrunnerer.runtestrunner(
        str(p1), "--pdbcls=really.invalid:Value", syspathinsert=True
    )
    result.stdout.fnmatch_lines(
        [
            "*= FAILURES =*",
            "E * --pdbcls: could not import 'really.invalid:Value': No module named *really*",
        ]
    )
    assert result.ret == 1

    result = testrunnerer.runtestrunner(
        str(p1), "--pdbcls=mypdb:Wrapped.MyPdb", syspathinsert=True
    )
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*set_trace_called*", "* 1 passed in *"])

    # Ensure that it also works with --trace.
    result = testrunnerer.runtestrunner(
        str(p1), "--pdbcls=mypdb:Wrapped.MyPdb", "--trace", syspathinsert=True
    )
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*runcall_called*", "* 1 passed in *"])


@testrunner.mark.xfail(
    sys.version_info >= (3, 14),
    reason="C-D now quits the test session, rather than failing the test. See https://github.com/python/cpython/issues/124703",
)
def test_raises_bdbquit_with_eoferror(testrunnerer: Testrunnerer) -> None:
    """It is not guaranteed that DontReadFromInput's read is called."""
    p1 = testrunnerer.makepyfile(
        """
        def input_without_read(*args, **kwargs):
            raise EOFError()

        def test(monkeypatch):
            import builtins
            monkeypatch.setattr(builtins, "input", input_without_read)
            __import__('pdb').set_trace()
        """
    )
    result = testrunnerer.runtestrunner(str(p1))
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["E *BdbQuit", "*= 1 failed in*"])
    assert result.ret == 1


def test_pdb_wrapper_class_is_reused(testrunnerer: Testrunnerer) -> None:
    p1 = testrunnerer.makepyfile(
        """
        def test():
            __import__("pdb").set_trace()
            __import__("pdb").set_trace()

            import mypdb
            instances = mypdb.instances
            assert len(instances) == 2
            assert instances[0].__class__ is instances[1].__class__
        """,
        mypdb="""
        instances = []

        class MyPdb:
            def __init__(self, *args, **kwargs):
                instances.append(self)

            def set_trace(self, *args):
                print("set_trace_called", args)

            # Methods which we copy the docstring over.
            def do_debug(self, *args):
                pass

            def do_continue(self, *args):
                pass

            def do_quit(self, *args):
                pass
        """,
    )
    result = testrunnerer.runtestrunner(
        str(p1), "--pdbcls=mypdb:MyPdb", syspathinsert=True
    )
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        ["*set_trace_called*", "*set_trace_called*", "* 1 passed in *"]
    )
