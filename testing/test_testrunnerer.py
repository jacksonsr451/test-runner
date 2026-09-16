# mypy: allow-untyped-defs
from __future__ import annotations

import os
import subprocess
import sys
from types import ModuleType

from _testrunner.config import ExitCode
from _testrunner.config import TestrunnerPluginManager
from _testrunner.monkeypatch import MonkeyPatch
import _testrunner.testrunnerer as testrunnerer_mod
from _testrunner.testrunnerer import HookRecorder
from _testrunner.testrunnerer import LineMatcher
from _testrunner.testrunnerer import SysModulesSnapshot
from _testrunner.testrunnerer import SysPathsSnapshot
from _testrunner.testrunnerer import Testrunnerer
import _testrunner.timing
import testrunner


def test_make_hook_recorder(testrunnerer: Testrunnerer) -> None:
    item = testrunnerer.getitem("def test_func(): pass")
    recorder = testrunnerer.make_hook_recorder(item.config.pluginmanager)
    assert not recorder.getfailures()

    # (The silly condition is to fool mypy that the code below this is reachable)
    if 1 + 1 == 2:
        testrunner.xfail("internal reportrecorder tests need refactoring")

    class rep:
        excinfo = None
        passed = False
        failed = True
        skipped = False
        when = "call"

    recorder.hook.testrunner_runtest_logreport(report=rep)  # type: ignore[attr-defined]
    failures = recorder.getfailures()
    assert failures == [rep]  # type: ignore[comparison-overlap]
    failures = recorder.getfailures()
    assert failures == [rep]  # type: ignore[comparison-overlap]

    class rep2:
        excinfo = None
        passed = False
        failed = False
        skipped = True
        when = "call"

    rep2.passed = False
    rep2.skipped = True
    recorder.hook.testrunner_runtest_logreport(report=rep2)  # type: ignore[attr-defined]

    modcol = testrunnerer.getmodulecol("")
    rep3 = modcol.config.hook.testrunner_make_collect_report(collector=modcol)
    rep3.passed = False
    rep3.failed = True
    rep3.skipped = False
    recorder.hook.testrunner_collectreport(report=rep3)  # type: ignore[attr-defined]

    passed, skipped, failed = recorder.listoutcomes()
    assert not passed and skipped and failed

    numpassed, numskipped, numfailed = recorder.countoutcomes()
    assert numpassed == 0
    assert numskipped == 1
    assert numfailed == 1
    assert len(recorder.getfailedcollections()) == 1

    recorder.unregister()  # type: ignore[attr-defined]
    recorder.clear()
    recorder.hook.testrunner_runtest_logreport(report=rep3)  # type: ignore[attr-defined]
    with testrunner.raises(ValueError):
        recorder.getfailures()


def test_parseconfig(testrunnerer: Testrunnerer) -> None:
    config1 = testrunnerer.parseconfig()
    config2 = testrunnerer.parseconfig()
    assert config2 is not config1


def test_testrunnerer_runs_with_plugin(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        testrunner_plugins = "testrunnerer"
        def test_hello(testrunnerer):
            assert 1
    """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=1)


def test_testrunnerer_with_doctest(testrunnerer: Testrunnerer) -> None:
    """Check that testrunnerer can be used within doctests.

    It used to use `request.function`, which is `None` with doctests."""
    testrunnerer.makepyfile(
        **{
            "sub/t-doctest.py": """
        '''
        >>> import os
        >>> testrunnerer = getfixture("testrunnerer")
        >>> str(testrunnerer.makepyfile("content")).replace(os.sep, '/')
        '.../basetemp/sub.t-doctest0/sub.py'
        '''
    """,
            "sub/__init__.py": "",
        }
    )
    result = testrunnerer.runtestrunner(
        "-p", "testrunnerer", "--doctest-modules", "sub/t-doctest.py"
    )
    assert result.ret == 0


def test_runresult_assertion_on_xfail(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner

        testrunner_plugins = "testrunnerer"

        @testrunner.mark.xfail
        def test_potato():
            assert False
    """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(xfailed=1)
    assert result.ret == 0


def test_runresult_assertion_on_xpassed(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner

        testrunner_plugins = "testrunnerer"

        @testrunner.mark.xfail
        def test_potato():
            assert True
    """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(xpassed=1)
    assert result.ret == 0


def test_xpassed_with_strict_is_considered_a_failure(
    testrunnerer: Testrunnerer,
) -> None:
    testrunnerer.makepyfile(
        """
        import testrunner

        testrunner_plugins = "testrunnerer"

        @testrunner.mark.xfail(strict=True)
        def test_potato():
            assert True
    """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(failed=1)
    assert result.ret != 0


def make_holder():
    class apiclass:
        def testrunner_xyz(self, arg):
            """X"""

        def testrunner_xyz_noarg(self):
            """X"""

    apimod = type(os)("api")

    def testrunner_xyz(arg):
        """X"""

    def testrunner_xyz_noarg():
        """X"""

    apimod.testrunner_xyz = testrunner_xyz  # type: ignore
    apimod.testrunner_xyz_noarg = testrunner_xyz_noarg  # type: ignore
    return apiclass, apimod


@testrunner.mark.parametrize("holder", make_holder())
def test_hookrecorder_basic(holder) -> None:
    pm = TestrunnerPluginManager()
    pm.add_hookspecs(holder)
    rec = HookRecorder(pm, _istestrunner=True)
    pm.hook.testrunner_xyz(arg=123)
    call = rec.popcall("testrunner_xyz")
    assert call.arg == 123
    assert call._name == "testrunner_xyz"
    with testrunner.raises(testrunner.fail.Exception):
        rec.popcall("abc")
    pm.hook.testrunner_xyz_noarg()
    call = rec.popcall("testrunner_xyz_noarg")
    assert call._name == "testrunner_xyz_noarg"


def test_makepyfile_unicode(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(chr(0xFFFD))


def test_makepyfile_utf8(testrunnerer: Testrunnerer) -> None:
    """Ensure makepyfile accepts utf-8 bytes as input (#2738)"""
    utf8_contents = """
        def setup_function(function):
            mixed_encoding = 'São Paulo'
    """.encode()
    p = testrunnerer.makepyfile(utf8_contents)
    assert "mixed_encoding = 'São Paulo'".encode() in p.read_bytes()


class TestInlineRunModulesCleanup:
    def test_inline_run_test_module_not_cleaned_up(
        self, testrunnerer: Testrunnerer
    ) -> None:
        test_mod = testrunnerer.makepyfile("def test_foo(): assert True")
        result = testrunnerer.inline_run(str(test_mod))
        assert result.ret == ExitCode.OK
        # rewrite module, now test should fail if module was re-imported
        test_mod.write_text("def test_foo(): assert False", encoding="utf-8")
        result2 = testrunnerer.inline_run(str(test_mod))
        assert result2.ret == ExitCode.TESTS_FAILED

    def spy_factory(self):
        class SysModulesSnapshotSpy:
            instances: list[SysModulesSnapshotSpy] = []

            def __init__(self, preserve=None) -> None:
                SysModulesSnapshotSpy.instances.append(self)
                self._spy_restore_count = 0
                self._spy_preserve = preserve
                self.__snapshot = SysModulesSnapshot(preserve=preserve)

            def restore(self):
                self._spy_restore_count += 1
                return self.__snapshot.restore()

        return SysModulesSnapshotSpy

    def test_inline_run_taking_and_restoring_a_sys_modules_snapshot(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        spy_factory = self.spy_factory()
        monkeypatch.setattr(testrunnerer_mod, "SysModulesSnapshot", spy_factory)
        testrunnerer.syspathinsert()
        original = dict(sys.modules)
        testrunnerer.makepyfile(import1="# you son of a silly person")
        testrunnerer.makepyfile(import2="# my hovercraft is full of eels")
        test_mod = testrunnerer.makepyfile(
            """
            import import1
            def test_foo(): import import2"""
        )
        testrunnerer.inline_run(str(test_mod))
        assert len(spy_factory.instances) == 1
        spy = spy_factory.instances[0]
        assert spy._spy_restore_count == 1
        assert sys.modules == original
        assert all(sys.modules[x] is original[x] for x in sys.modules)

    def test_inline_run_sys_modules_snapshot_restore_preserving_modules(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        spy_factory = self.spy_factory()
        monkeypatch.setattr(testrunnerer_mod, "SysModulesSnapshot", spy_factory)
        test_mod = testrunnerer.makepyfile("def test_foo(): pass")
        testrunnerer.inline_run(str(test_mod))
        spy = spy_factory.instances[0]
        assert not spy._spy_preserve("black_knight")
        assert spy._spy_preserve("zope")
        assert spy._spy_preserve("zope.interface")
        assert spy._spy_preserve("zopelicious")

    def test_external_test_module_imports_not_cleaned_up(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(imported="data = 'you son of a silly person'")
        import imported

        test_mod = testrunnerer.makepyfile(
            """
            def test_foo():
                import imported
                imported.data = 42"""
        )
        testrunnerer.inline_run(str(test_mod))
        assert imported.data == 42


def test_assert_outcomes_after_testrunner_error(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile("def test_foo(): assert True")

    result = testrunnerer.runtestrunner("--unexpected-argument")
    with testrunner.raises(ValueError) as exc_info:
        result.assert_outcomes(passed=0)

    message = str(exc_info.value)
    assert "Plugins that modify testrunner's terminal output" in message
    assert "TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD=1" in message


class TestSysModulesSnapshot:
    key = "my-test-module"

    def test_remove_added(self) -> None:
        original = dict(sys.modules)
        assert self.key not in sys.modules
        snapshot = SysModulesSnapshot()
        sys.modules[self.key] = ModuleType("something")
        assert self.key in sys.modules
        snapshot.restore()
        assert sys.modules == original

    def test_add_removed(self, monkeypatch: MonkeyPatch) -> None:
        assert self.key not in sys.modules
        monkeypatch.setitem(sys.modules, self.key, ModuleType("something"))
        assert self.key in sys.modules
        original = dict(sys.modules)
        snapshot = SysModulesSnapshot()
        del sys.modules[self.key]
        assert self.key not in sys.modules
        snapshot.restore()
        assert sys.modules == original

    def test_restore_reloaded(self, monkeypatch: MonkeyPatch) -> None:
        assert self.key not in sys.modules
        monkeypatch.setitem(sys.modules, self.key, ModuleType("something"))
        assert self.key in sys.modules
        original = dict(sys.modules)
        snapshot = SysModulesSnapshot()
        sys.modules[self.key] = ModuleType("something else")
        snapshot.restore()
        assert sys.modules == original

    def test_preserve_modules(self, monkeypatch: MonkeyPatch) -> None:
        key = [self.key + str(i) for i in range(3)]
        assert not any(k in sys.modules for k in key)
        for i, k in enumerate(key):
            mod = ModuleType("something" + str(i))
            monkeypatch.setitem(sys.modules, k, mod)
        original = dict(sys.modules)

        def preserve(name):
            return name in (key[0], key[1], "some-other-key")

        snapshot = SysModulesSnapshot(preserve=preserve)
        sys.modules[key[0]] = original[key[0]] = ModuleType("something else0")
        sys.modules[key[1]] = original[key[1]] = ModuleType("something else1")
        sys.modules[key[2]] = ModuleType("something else2")
        snapshot.restore()
        assert sys.modules == original

    def test_preserve_container(self, monkeypatch: MonkeyPatch) -> None:
        original = dict(sys.modules)
        assert self.key not in original
        replacement = dict(sys.modules)
        replacement[self.key] = ModuleType("life of brian")
        snapshot = SysModulesSnapshot()
        monkeypatch.setattr(sys, "modules", replacement)
        snapshot.restore()
        assert sys.modules is replacement
        assert sys.modules == original


@testrunner.mark.parametrize("path_type", ("path", "meta_path"))
class TestSysPathsSnapshot:
    other_path = {"path": "meta_path", "meta_path": "path"}

    @staticmethod
    def path(n: int) -> str:
        return "my-dirty-little-secret-" + str(n)

    def test_restore(self, monkeypatch: MonkeyPatch, path_type) -> None:
        other_path_type = self.other_path[path_type]
        for i in range(10):
            assert self.path(i) not in getattr(sys, path_type)
        sys_path = [self.path(i) for i in range(6)]
        monkeypatch.setattr(sys, path_type, sys_path)
        original = list(sys_path)
        original_other = list(getattr(sys, other_path_type))
        snapshot = SysPathsSnapshot()
        transformation = {"source": (0, 1, 2, 3, 4, 5), "target": (6, 2, 9, 7, 5, 8)}
        assert sys_path == [self.path(x) for x in transformation["source"]]
        sys_path[1] = self.path(6)
        sys_path[3] = self.path(7)
        sys_path.append(self.path(8))
        del sys_path[4]
        sys_path[3:3] = [self.path(9)]
        del sys_path[0]
        assert sys_path == [self.path(x) for x in transformation["target"]]
        snapshot.restore()
        assert getattr(sys, path_type) is sys_path
        assert getattr(sys, path_type) == original
        assert getattr(sys, other_path_type) == original_other

    def test_preserve_container(self, monkeypatch: MonkeyPatch, path_type) -> None:
        other_path_type = self.other_path[path_type]
        original_data = list(getattr(sys, path_type))
        original_other = getattr(sys, other_path_type)
        original_other_data = list(original_other)
        new: list[object] = []
        snapshot = SysPathsSnapshot()
        monkeypatch.setattr(sys, path_type, new)
        snapshot.restore()
        assert getattr(sys, path_type) is new
        assert getattr(sys, path_type) == original_data
        assert getattr(sys, other_path_type) is original_other
        assert getattr(sys, other_path_type) == original_other_data


def test_testrunnerer_subprocess(testrunnerer: Testrunnerer) -> None:
    testfile = testrunnerer.makepyfile("def test_one(): pass")
    assert testrunnerer.runtestrunner_subprocess(testfile).ret == 0


def test_testrunnerer_subprocess_via_runtestrunner_arg(
    testrunnerer: Testrunnerer,
) -> None:
    testfile = testrunnerer.makepyfile(
        """
        def test_testrunnerer_subprocess(testrunnerer):
            import os
            testfile = testrunnerer.makepyfile(
                \"""
                import os
                def test_one():
                    assert {} != os.getpid()
                \""".format(os.getpid())
            )
            assert testrunnerer.runtestrunner(testfile).ret == 0
        """
    )
    result = testrunnerer.runtestrunner_inprocess(
        "-p", "testrunnerer", "--runtestrunner", "subprocess", testfile
    )
    assert result.ret == 0


def test_unicode_args(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("-k", "אבג")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_testrunnerer_run_no_timeout(testrunnerer: Testrunnerer) -> None:
    testfile = testrunnerer.makepyfile("def test_no_timeout(): pass")
    assert testrunnerer.runtestrunner_subprocess(testfile).ret == ExitCode.OK


def test_testrunnerer_run_with_timeout(testrunnerer: Testrunnerer) -> None:
    testfile = testrunnerer.makepyfile("def test_no_timeout(): pass")

    timeout = 120

    instant = _testrunner.timing.Instant()
    result = testrunnerer.runtestrunner_subprocess(testfile, timeout=timeout)
    duration = instant.elapsed()

    assert result.ret == ExitCode.OK
    assert duration.seconds < timeout


def test_testrunnerer_run_timeout_expires(testrunnerer: Testrunnerer) -> None:
    testfile = testrunnerer.makepyfile(
        """
        import time

        def test_timeout():
            time.sleep(10)"""
    )
    with testrunner.raises(testrunnerer.TimeoutExpired):
        testrunnerer.runtestrunner_subprocess(testfile, timeout=1)


def test_linematcher_with_nonlist() -> None:
    """Test LineMatcher with regard to passing in a set (accidentally)."""
    from _testrunner._code.source import Source

    lm = LineMatcher([])
    with testrunner.raises(TypeError, match="invalid type for lines2: set"):
        lm.fnmatch_lines(set())  # type: ignore[arg-type]
    with testrunner.raises(TypeError, match="invalid type for lines2: dict"):
        lm.fnmatch_lines({})  # type: ignore[arg-type]
    with testrunner.raises(TypeError, match="invalid type for lines2: set"):
        lm.re_match_lines(set())  # type: ignore[arg-type]
    with testrunner.raises(TypeError, match="invalid type for lines2: dict"):
        lm.re_match_lines({})  # type: ignore[arg-type]
    with testrunner.raises(TypeError, match="invalid type for lines2: Source"):
        lm.fnmatch_lines(Source())  # type: ignore[arg-type]
    lm.fnmatch_lines([])
    lm.fnmatch_lines(())
    lm.fnmatch_lines("")
    assert lm._getlines({}) == {}  # type: ignore[arg-type,comparison-overlap]
    assert lm._getlines(set()) == set()  # type: ignore[arg-type,comparison-overlap]
    assert lm._getlines(Source()) == []
    assert lm._getlines(Source("pass\npass")) == ["pass", "pass"]


def test_linematcher_match_failure() -> None:
    lm = LineMatcher(["foo", "foo", "bar"])
    with testrunner.raises(testrunner.fail.Exception) as e:
        lm.fnmatch_lines(["foo", "f*", "baz"])
    assert e.value.msg is not None
    assert e.value.msg.splitlines() == [
        "exact match: 'foo'",
        "fnmatch: 'f*'",
        "   with: 'foo'",
        "nomatch: 'baz'",
        "    and: 'bar'",
        "remains unmatched: 'baz'",
    ]

    lm = LineMatcher(["foo", "foo", "bar"])
    with testrunner.raises(testrunner.fail.Exception) as e:
        lm.re_match_lines(["foo", "^f.*", "baz"])
    assert e.value.msg is not None
    assert e.value.msg.splitlines() == [
        "exact match: 'foo'",
        "re.match: '^f.*'",
        "    with: 'foo'",
        " nomatch: 'baz'",
        "     and: 'bar'",
        "remains unmatched: 'baz'",
    ]


def test_linematcher_consecutive() -> None:
    lm = LineMatcher(["1", "", "2"])
    with testrunner.raises(testrunner.fail.Exception) as excinfo:
        lm.fnmatch_lines(["1", "2"], consecutive=True)
    assert str(excinfo.value).splitlines() == [
        "exact match: '1'",
        "no consecutive match: '2'",
        "   with: ''",
    ]

    lm.re_match_lines(["1", r"\d?", "2"], consecutive=True)
    with testrunner.raises(testrunner.fail.Exception) as excinfo:
        lm.re_match_lines(["1", r"\d", "2"], consecutive=True)
    assert str(excinfo.value).splitlines() == [
        "exact match: '1'",
        r"no consecutive match: '\\d'",
        "    with: ''",
    ]


@testrunner.mark.parametrize("function", ["no_fnmatch_line", "no_re_match_line"])
def test_linematcher_no_matching(function: str) -> None:
    if function == "no_fnmatch_line":
        good_pattern = "*.py OK*"
        bad_pattern = "*X.py OK*"
    else:
        assert function == "no_re_match_line"
        good_pattern = r".*py OK"
        bad_pattern = r".*Xpy OK"

    lm = LineMatcher(
        [
            "cachedir: .testrunner_cache",
            "collecting ... collected 1 item",
            "",
            "show_fixtures_per_test.py OK",
            "=== elapsed 1s ===",
        ]
    )

    # check the function twice to ensure we don't accumulate the internal buffer
    for i in range(2):
        with testrunner.raises(testrunner.fail.Exception) as e:
            func = getattr(lm, function)
            func(good_pattern)
        obtained = str(e.value).splitlines()
        if function == "no_fnmatch_line":
            assert obtained == [
                f"nomatch: '{good_pattern}'",
                "    and: 'cachedir: .testrunner_cache'",
                "    and: 'collecting ... collected 1 item'",
                "    and: ''",
                f"fnmatch: '{good_pattern}'",
                "   with: 'show_fixtures_per_test.py OK'",
            ]
        else:
            assert obtained == [
                f" nomatch: '{good_pattern}'",
                "     and: 'cachedir: .testrunner_cache'",
                "     and: 'collecting ... collected 1 item'",
                "     and: ''",
                f"re.match: '{good_pattern}'",
                "    with: 'show_fixtures_per_test.py OK'",
            ]

    func = getattr(lm, function)
    func(bad_pattern)  # bad pattern does not match any line: passes


def test_linematcher_no_matching_after_match() -> None:
    lm = LineMatcher(["1", "2", "3"])
    lm.fnmatch_lines(["1", "3"])
    with testrunner.raises(testrunner.fail.Exception) as e:
        lm.no_fnmatch_line("*")
    assert str(e.value).splitlines() == ["fnmatch: '*'", "   with: '1'"]


def test_linematcher_string_api() -> None:
    lm = LineMatcher(["foo", "bar"])
    assert str(lm) == "foo\nbar"


def test_testrunner_addopts_before_testrunnerer(
    request, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("TESTRUNNER_ADDOPTS", "--orig-unused")
    _: Testrunnerer = request.getfixturevalue("testrunnerer")
    assert "TESTRUNNER_ADDOPTS" not in os.environ


def test_run_stdin(testrunnerer: Testrunnerer) -> None:
    with testrunner.raises(testrunnerer.TimeoutExpired):
        testrunnerer.run(
            sys.executable,
            "-c",
            "import sys, time; time.sleep(1); print(sys.stdin.read())",
            stdin=subprocess.PIPE,
            timeout=0.1,
        )

    with testrunner.raises(testrunnerer.TimeoutExpired):
        result = testrunnerer.run(
            sys.executable,
            "-c",
            "import sys, time; time.sleep(1); print(sys.stdin.read())",
            stdin=b"input\n2ndline",
            timeout=0.1,
        )

    result = testrunnerer.run(
        sys.executable,
        "-c",
        "import sys; print(sys.stdin.read())",
        stdin=b"input\n2ndline",
    )
    assert result.stdout.lines == ["input", "2ndline"]
    assert result.stderr.str() == ""
    assert result.ret == 0


def test_popen_stdin_pipe(testrunnerer: Testrunnerer) -> None:
    proc = testrunnerer.popen(
        [sys.executable, "-c", "import sys; print(sys.stdin.read())"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )
    stdin = b"input\n2ndline"
    stdout, stderr = proc.communicate(input=stdin)
    assert stdout.decode("utf8").splitlines() == ["input", "2ndline"]
    assert stderr == b""
    assert proc.returncode == 0


def test_popen_stdin_bytes(testrunnerer: Testrunnerer) -> None:
    proc = testrunnerer.popen(
        [sys.executable, "-c", "import sys; print(sys.stdin.read())"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=b"input\n2ndline",
    )
    stdout, stderr = proc.communicate()
    assert stdout.decode("utf8").splitlines() == ["input", "2ndline"]
    assert stderr == b""
    assert proc.returncode == 0


def test_popen_default_stdin_stderr_and_stdin_None(testrunnerer: Testrunnerer) -> None:
    # stdout, stderr default to pipes,
    # stdin can be None to not close the pipe, avoiding
    # "ValueError: flush of closed file" with `communicate()`.
    #
    # Wraps the test to make it not hang when run with "-s".
    p1 = testrunnerer.makepyfile(
        '''
        import sys

        def test_inner(testrunnerer):
            p1 = testrunnerer.makepyfile(
                """
                import sys
                print(sys.stdin.read())  # empty
                print('stdout')
                sys.stderr.write('stderr')
                """
            )
            proc = testrunnerer.popen([sys.executable, str(p1)], stdin=None)
            stdout, stderr = proc.communicate(b"ignored")
            assert stdout.splitlines() == [b"", b"stdout"]
            assert stderr.splitlines() == [b"stderr"]
            assert proc.returncode == 0
        '''
    )
    result = testrunnerer.runtestrunner("-p", "testrunnerer", str(p1))
    assert result.ret == 0


def test_spawn_uses_tmphome(testrunnerer: Testrunnerer) -> None:
    tmphome = str(testrunnerer.path)
    assert os.environ.get("HOME") == tmphome

    testrunnerer._monkeypatch.setenv("CUSTOMENV", "42")

    p1 = testrunnerer.makepyfile(
        f"""
        import os

        def test():
            assert os.environ["HOME"] == {tmphome!r}
            assert os.environ["CUSTOMENV"] == "42"
        """
    )
    child = testrunnerer.spawn_testrunner(str(p1))
    out = child.read()
    assert child.wait() == 0, out.decode("utf8")


def test_run_result_repr() -> None:
    outlines = ["some", "normal", "output"]
    errlines = ["some", "nasty", "errors", "happened"]

    # known exit code
    r = testrunnerer_mod.RunResult(1, outlines, errlines, duration=0.5)
    assert repr(r) == (
        f"<RunResult ret={testrunner.ExitCode.TESTS_FAILED!s} len(stdout.lines)=3"
        " len(stderr.lines)=4 duration=0.50s>"
    )

    # unknown exit code: just the number
    r = testrunnerer_mod.RunResult(99, outlines, errlines, duration=0.5)
    assert (
        repr(r) == "<RunResult ret=99 len(stdout.lines)=3"
        " len(stderr.lines)=4 duration=0.50s>"
    )


def test_testrunnerer_outcomes_with_multiple_errors(testrunnerer: Testrunnerer) -> None:
    p1 = testrunnerer.makepyfile(
        """
        import testrunner

        @testrunner.fixture
        def bad_fixture():
            raise Exception("bad")

        def test_error1(bad_fixture):
            pass

        def test_error2(bad_fixture):
            pass
    """
    )
    result = testrunnerer.runtestrunner(str(p1))
    result.assert_outcomes(errors=2)

    assert result.parseoutcomes() == {"errors": 2}


def test_parse_summary_line_always_plural() -> None:
    """Parsing summaries always returns plural nouns (#6505)"""
    lines = [
        "some output 1",
        "some output 2",
        "======= 1 failed, 1 passed, 1 warning, 1 error in 0.13s ====",
        "done.",
    ]
    assert testrunnerer_mod.RunResult.parse_summary_nouns(lines) == {
        "errors": 1,
        "failed": 1,
        "passed": 1,
        "warnings": 1,
    }

    lines = [
        "some output 1",
        "some output 2",
        "======= 1 failed, 1 passed, 2 warnings, 2 errors in 0.13s ====",
        "done.",
    ]
    assert testrunnerer_mod.RunResult.parse_summary_nouns(lines) == {
        "errors": 2,
        "failed": 1,
        "passed": 1,
        "warnings": 2,
    }


def test_makefile_joins_absolute_path(testrunnerer: Testrunnerer) -> None:
    absfile = testrunnerer.path / "absfile"
    p1 = testrunnerer.makepyfile(**{str(absfile): ""})
    assert str(p1) == str(testrunnerer.path / "absfile.py")


def test_testrunnerer_makefile_dot_prefixes_extension_with_warning(
    testrunnerer: Testrunnerer,
) -> None:
    with testrunner.raises(
        ValueError,
        match=r"testrunnerer\.makefile expects a file extension, try \.foo\.bar instead of foo\.bar",
    ):
        testrunnerer.makefile("foo.bar", "")


@testrunner.mark.filterwarnings("default")
def test_testrunnerer_assert_outcomes_warnings(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        import warnings

        def test_with_warning():
            warnings.warn(UserWarning("some custom warning"))
        """
    )
    result = testrunnerer.runtestrunner()
    result.assert_outcomes(passed=1, warnings=1)
    # If warnings is not passed, it is not checked at all.
    result.assert_outcomes(passed=1)


def test_testrunnerer_outcomes_deselected(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile(
        """
        def test_one():
            pass

        def test_two():
            pass
        """
    )
    result = testrunnerer.runtestrunner("-k", "test_one")
    result.assert_outcomes(passed=1, deselected=1)
    # If deselected is not passed, it is not checked at all.
    result.assert_outcomes(passed=1)


def test_testrunnerer_subprocess_with_string_plugins(
    testrunnerer: Testrunnerer,
) -> None:
    """Test that testrunnerer.runtestrunner_subprocess is OK with named (string)
    `.plugins`."""
    testrunnerer.plugins = ["testrunnerer"]

    result = testrunnerer.runtestrunner_subprocess()
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_testrunnerer_subprocess_with_non_string_plugins(
    testrunnerer: Testrunnerer,
) -> None:
    """Test that testrunnerer.runtestrunner_subprocess fails with a proper error given
    non-string `.plugins`."""

    class MyPlugin:
        pass

    testrunnerer.plugins = [MyPlugin()]

    with testrunner.raises(ValueError, match="plugins as objects is not supported"):
        testrunnerer.runtestrunner_subprocess()
