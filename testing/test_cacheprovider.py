from __future__ import annotations

from collections.abc import Generator
from collections.abc import Sequence
from enum import auto
from enum import Enum
import os
from pathlib import Path
import shutil
from typing import Any

from _testrunner.compat import assert_never
from _testrunner.config import ExitCode
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.tmpdir import TempPathFactory
import testrunner


testrunner_plugins = ("testrunnerer",)


class TestNewAPI:
    def test_config_cache_mkdir(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeini("[testrunner]")
        config = testrunnerer.parseconfigure()
        assert config.cache is not None
        with testrunner.raises(ValueError):
            config.cache.mkdir("key/name")

        p = config.cache.mkdir("name")
        assert p.is_dir()

    def test_config_cache_mkdir_escape(self, testrunnerer: Testrunnerer) -> None:
        """`..` is a single path part, so it passes the separator check."""
        testrunnerer.makeini("[testrunner]")
        config = testrunnerer.parseconfigure()
        assert config.cache is not None
        with testrunner.raises(ValueError):
            config.cache.mkdir("..")

    @testrunner.mark.parametrize(
        "key",
        [
            "../escaped",
            "plugin/../../escaped",
            "/absolute/escaped",
            "//absolute/escaped",
        ],
    )
    def test_cache_key_escape(self, testrunnerer: Testrunnerer, key: str) -> None:
        """Keys must not resolve outside the cache's values directory."""
        testrunnerer.makeini("[testrunner]")
        config = testrunnerer.parseconfigure()
        assert config.cache is not None
        with testrunner.raises(ValueError):
            config.cache.set(key, 1)
        with testrunner.raises(ValueError):
            config.cache.get(key, None)

    def test_cache_key_normalized(self, testrunnerer: Testrunnerer) -> None:
        """A `..` that cancels out within the values directory is fine."""
        testrunnerer.makeini("[testrunner]")
        config = testrunnerer.parseconfigure()
        assert config.cache is not None
        config.cache.set("plugin/sub/../value", 42)
        assert config.cache.get("plugin/value", None) == 42

    def test_cache_dir_permissions(self, testrunnerer: Testrunnerer) -> None:
        """The .testrunner_cache directory should have world-readable permissions
        (depending on umask).

        Regression test for #12308.
        """
        testrunnerer.makeini("[testrunner]")
        config = testrunnerer.parseconfigure()
        assert config.cache is not None
        p = config.cache.mkdir("name")
        assert p.is_dir()
        # Instead of messing with umask, make sure .testrunner_cache has the same
        # permissions as the default that `mkdir` gives `p`.
        assert (p.parent.stat().st_mode & 0o777) == (p.stat().st_mode & 0o777)

    def test_config_cache_dataerror(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeini("[testrunner]")
        config = testrunnerer.parseconfigure()
        assert config.cache is not None
        cache = config.cache
        with testrunner.raises(TypeError):
            cache.set("key/name", cache)
        config.cache.set("key/name", 0)
        config.cache._getvaluepath("key/name").write_bytes(b"123invalid")
        val = config.cache.get("key/name", -2)
        assert val == -2

    @testrunner.mark.filterwarnings("ignore:could not create cache path")
    def test_cache_writefail_cachefile_silent(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeini("[testrunner]")
        testrunnerer.path.joinpath(".testrunner_cache").write_text(
            "gone wrong", encoding="utf-8"
        )
        config = testrunnerer.parseconfigure()
        cache = config.cache
        assert cache is not None
        cache.set("test/broken", [])

    @testrunner.fixture
    def unwritable_cache_dir(self, testrunnerer: Testrunnerer) -> Generator[Path]:
        cache_dir = testrunnerer.path.joinpath(".testrunner_cache")
        cache_dir.mkdir()
        mode = cache_dir.stat().st_mode
        cache_dir.chmod(0)
        if os.access(cache_dir, os.W_OK):
            testrunner.skip("Failed to make cache dir unwritable")

        yield cache_dir
        cache_dir.chmod(mode)

    @testrunner.mark.filterwarnings(
        "ignore:could not create cache path:testrunner.TestrunnerWarning"
    )
    def test_cache_writefail_permissions(
        self, unwritable_cache_dir: Path, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makeini("[testrunner]")
        config = testrunnerer.parseconfigure()
        cache = config.cache
        assert cache is not None
        cache.set("test/broken", [])

    @testrunner.mark.filterwarnings("default")
    def test_cache_failure_warns(
        self,
        testrunnerer: Testrunnerer,
        monkeypatch: MonkeyPatch,
        unwritable_cache_dir: Path,
    ) -> None:
        monkeypatch.setenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", "1")

        testrunnerer.makepyfile("def test_error(): raise Exception")
        result = testrunnerer.runtestrunner()
        assert result.ret == 1
        # warnings from nodeids and lastfailed
        result.stdout.fnmatch_lines(
            [
                # Validate location/stacklevel of warning from cacheprovider.
                "*= warnings summary =*",
                "*/cacheprovider.py:*",
                "  */cacheprovider.py:*: TestrunnerCacheWarning: could not create cache path "
                f"{unwritable_cache_dir}/v/cache/nodeids: *",
                '    config.cache.set("cache/nodeids", sorted(str(n) for n in self.cached_nodeids))',
                "*1 failed, 2 warnings in*",
            ]
        )

    def test_config_cache(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_configure(config):
                # see that we get cache information early on
                assert hasattr(config, "cache")
        """
        )
        testrunnerer.makepyfile(
            """
            def test_session(testrunnerconfig):
                assert hasattr(testrunnerconfig, "cache")
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_cachefuncarg(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            def test_cachefuncarg(cache):
                val = cache.get("some/thing", None)
                assert val is None
                cache.set("some/thing", [1])
                with testrunner.raises(TypeError):
                    cache.get("some/thing")
                val = cache.get("some/thing", [])
                assert val == [1]
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_custom_rel_cache_dir(self, testrunnerer: Testrunnerer) -> None:
        rel_cache_dir = os.path.join("custom_cache_dir", "subdir")
        testrunnerer.makeini(
            f"""
            [testrunner]
            cache_dir = {rel_cache_dir}
        """
        )
        testrunnerer.makepyfile(test_errored="def test_error():\n    assert False")
        testrunnerer.runtestrunner()
        assert testrunnerer.path.joinpath(rel_cache_dir).is_dir()

    def test_custom_abs_cache_dir(
        self, testrunnerer: Testrunnerer, tmp_path_factory: TempPathFactory
    ) -> None:
        tmp = tmp_path_factory.mktemp("tmp")
        abs_cache_dir = tmp / "custom_cache_dir"
        testrunnerer.makeini(
            f"""
            [testrunner]
            cache_dir = {abs_cache_dir}
        """
        )
        testrunnerer.makepyfile(test_errored="def test_error():\n    assert False")
        testrunnerer.runtestrunner()
        assert abs_cache_dir.is_dir()

    def test_custom_cache_dir_with_env_var(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setenv("env_var", "custom_cache_dir")
        testrunnerer.makeini(
            """
            [testrunner]
            cache_dir = {cache_dir}
        """.format(cache_dir="$env_var")
        )
        testrunnerer.makepyfile(test_errored="def test_error():\n    assert False")
        testrunnerer.runtestrunner()
        assert testrunnerer.path.joinpath("custom_cache_dir").is_dir()


@testrunner.mark.parametrize("env", ((), ("TOX_ENV_DIR", "mydir/tox-env")))
def test_cache_reportheader(
    env: Sequence[str], testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    testrunnerer.makepyfile("""def test_foo(): pass""")
    if env:
        monkeypatch.setenv(*env)
        expected = os.path.join(env[1], ".testrunner_cache")
    else:
        monkeypatch.delenv("TOX_ENV_DIR", raising=False)
        expected = ".testrunner_cache"
    result = testrunnerer.runtestrunner("-v")
    result.stdout.fnmatch_lines([f"cachedir: {expected}"])


def test_cache_reportheader_external_abspath(
    testrunnerer: Testrunnerer, tmp_path_factory: TempPathFactory
) -> None:
    external_cache = tmp_path_factory.mktemp(
        "test_cache_reportheader_external_abspath_abs"
    )

    testrunnerer.makepyfile("def test_hello(): pass")
    testrunnerer.makeini(
        f"""
    [testrunner]
    cache_dir = {external_cache}
    """
    )
    result = testrunnerer.runtestrunner("-v")
    result.stdout.fnmatch_lines([f"cachedir: {external_cache}"])


def test_cache_show(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("--cache-show")
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*cache is empty*"])
    testrunnerer.makeconftest(
        """
        def testrunner_configure(config):
            config.cache.set("my/name", [1,2,3])
            config.cache.set("my/hello", "world")
            config.cache.set("other/some", {1:2})
            dp = config.cache.mkdir("mydb")
            dp.joinpath("hello").touch()
            dp.joinpath("world").touch()
    """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 5  # no tests executed

    result = testrunnerer.runtestrunner("--cache-show")
    result.stdout.fnmatch_lines(
        [
            "*cachedir:*",
            "*- cache values for '[*]' -*",
            "cache/nodeids contains:",
            "my/name contains:",
            "  [1, 2, 3]",
            "other/some contains:",
            "  {*'1': 2}",
            "*- cache directories for '[*]' -*",
            "*mydb/hello*length 0*",
            "*mydb/world*length 0*",
        ]
    )
    assert result.ret == 0

    result = testrunnerer.runtestrunner("--cache-show", "*/hello")
    result.stdout.fnmatch_lines(
        [
            "*cachedir:*",
            "*- cache values for '[*]/hello' -*",
            "my/hello contains:",
            "  *'world'",
            "*- cache directories for '[*]/hello' -*",
            "d/mydb/hello*length 0*",
        ]
    )
    stdout = result.stdout.str()
    assert "other/some" not in stdout
    assert "d/mydb/world" not in stdout
    assert result.ret == 0


def test_cache_show_escaping_glob(testrunnerer: Testrunnerer) -> None:
    """A glob with `..` must not reach outside the cache directory."""
    testrunnerer.makeconftest(
        """
        def testrunner_configure(config):
            config.cache.set("my/name", [1, 2, 3])
            config.cache.mkdir("mydb").joinpath("hello").touch()
    """
    )
    assert testrunnerer.runtestrunner().ret == 5  # no tests executed
    testrunnerer.path.joinpath("secret.json").write_text(
        '{"token": "s3cr3t"}', encoding="utf-8"
    )

    result = testrunnerer.runtestrunner("--cache-show", "../../../secret.json")
    assert result.ret == 0
    stdout = result.stdout.str()
    # the glob itself is echoed in the section headers, the contents are not.
    assert "s3cr3t" not in stdout
    assert "contains" not in stdout
    assert "is a file of length" not in stdout


class TestLastFailed:
    def test_lastfailed_usecase(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.dont_write_bytecode", True)
        p = testrunnerer.makepyfile(
            """
            def test_1(): assert 0
            def test_2(): assert 0
            def test_3(): assert 1
            """
        )
        result = testrunnerer.runtestrunner(str(p))
        result.stdout.fnmatch_lines(["*2 failed*"])
        p = testrunnerer.makepyfile(
            """
            def test_1(): assert 1
            def test_2(): assert 1
            def test_3(): assert 0
            """
        )
        result = testrunnerer.runtestrunner(str(p), "--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 3 items / 1 deselected / 2 selected",
                "run-last-failure: rerun previous 2 failures",
                "*= 2 passed, 1 deselected in *",
            ]
        )
        result = testrunnerer.runtestrunner(str(p), "--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 3 items",
                "run-last-failure: no previously failed tests, not deselecting items.",
                "*1 failed*2 passed*",
            ]
        )
        testrunnerer.path.joinpath(".testrunner_cache", ".git").mkdir(parents=True)
        result = testrunnerer.runtestrunner(str(p), "--lf", "--cache-clear")
        result.stdout.fnmatch_lines(["*1 failed*2 passed*"])
        assert testrunnerer.path.joinpath(".testrunner_cache", "README.md").is_file()
        assert testrunnerer.path.joinpath(".testrunner_cache", ".git").is_dir()

        # Run this again to make sure clear-cache is robust
        if os.path.isdir(".testrunner_cache"):
            shutil.rmtree(".testrunner_cache")
        result = testrunnerer.runtestrunner("--lf", "--cache-clear")
        result.stdout.fnmatch_lines(["*1 failed*2 passed*"])

    def test_failedfirst_order(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            test_a="def test_always_passes(): pass",
            test_b="def test_always_fails(): assert 0",
        )
        result = testrunnerer.runtestrunner()
        # Test order will be collection order; alphabetical
        result.stdout.fnmatch_lines(["test_a.py*", "test_b.py*"])
        result = testrunnerer.runtestrunner("--ff")
        # Test order will be failing tests first
        result.stdout.fnmatch_lines(
            [
                "collected 2 items",
                "run-last-failure: rerun previous 1 failure first",
                "test_b.py*",
                "test_a.py*",
            ]
        )

    def test_lastfailed_failedfirst_order(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            test_a="def test_always_passes(): assert 1",
            test_b="def test_always_fails(): assert 0",
        )
        result = testrunnerer.runtestrunner()
        # Test order will be collection order; alphabetical
        result.stdout.fnmatch_lines(["test_a.py*", "test_b.py*"])
        result = testrunnerer.runtestrunner("--lf", "--ff")
        # Test order will be failing tests first
        result.stdout.fnmatch_lines(["test_b.py*"])
        result.stdout.no_fnmatch_line("*test_a.py*")

    def test_lastfailed_difference_invocations(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.dont_write_bytecode", True)
        testrunnerer.makepyfile(
            test_a="""
                def test_a1(): assert 0
                def test_a2(): assert 1
            """,
            test_b="def test_b1(): assert 0",
        )
        p = testrunnerer.path.joinpath("test_a.py")
        p2 = testrunnerer.path.joinpath("test_b.py")

        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*2 failed*"])
        result = testrunnerer.runtestrunner("--lf", p2)
        result.stdout.fnmatch_lines(["*1 failed*"])

        testrunnerer.makepyfile(test_b="def test_b1(): assert 1")
        result = testrunnerer.runtestrunner("--lf", p2)
        result.stdout.fnmatch_lines(["*1 passed*"])
        result = testrunnerer.runtestrunner("--lf", p)
        result.stdout.fnmatch_lines(
            [
                "collected 2 items / 1 deselected / 1 selected",
                "run-last-failure: rerun previous 1 failure",
                "*= 1 failed, 1 deselected in *",
            ]
        )

    def test_lastfailed_usecase_splice(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.dont_write_bytecode", True)
        testrunnerer.makepyfile(
            "def test_1(): assert 0", test_something="def test_2(): assert 0"
        )
        p2 = testrunnerer.path.joinpath("test_something.py")
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*2 failed*"])
        result = testrunnerer.runtestrunner("--lf", p2)
        result.stdout.fnmatch_lines(["*1 failed*"])
        result = testrunnerer.runtestrunner("--lf")
        result.stdout.fnmatch_lines(["*2 failed*"])

    def test_lastfailed_xpass(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.inline_runsource(
            """
            import testrunner
            @testrunner.mark.xfail
            def test_hello():
                assert 1
        """
        )
        config = testrunnerer.parseconfigure()
        assert config.cache is not None
        lastfailed = config.cache.get("cache/lastfailed", -1)
        assert lastfailed == -1

    def test_non_serializable_parametrize(self, testrunnerer: Testrunnerer) -> None:
        """Test that failed parametrized tests with unmarshable parameters
        don't break testrunner-cache.
        """
        testrunnerer.makepyfile(
            r"""
            import testrunner

            @testrunner.mark.parametrize('val', [
                b'\xac\x10\x02G',
            ])
            def test_fail(val):
                assert False
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 failed in*"])

    @testrunner.mark.parametrize("parent", ("directory", "package"))
    def test_terminal_report_lastfailed(
        self, testrunnerer: Testrunnerer, parent: str
    ) -> None:
        if parent == "package":
            testrunnerer.makepyfile(
                __init__="",
            )

        test_a = testrunnerer.makepyfile(
            test_a="""
            def test_a1(): pass
            def test_a2(): pass
        """
        )
        test_b = testrunnerer.makepyfile(
            test_b="""
            def test_b1(): assert 0
            def test_b2(): assert 0
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 4 items", "*2 failed, 2 passed in*"])

        result = testrunnerer.runtestrunner("--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 2 items",
                "run-last-failure: rerun previous 2 failures (skipped 1 file)",
                "*2 failed in*",
            ]
        )

        result = testrunnerer.runtestrunner(test_a, "--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 2 items",
                "run-last-failure: 2 known failures not in selected tests",
                "*2 passed in*",
            ]
        )

        result = testrunnerer.runtestrunner(test_b, "--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 2 items",
                "run-last-failure: rerun previous 2 failures",
                "*2 failed in*",
            ]
        )

        result = testrunnerer.runtestrunner("test_b.py::test_b1", "--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 1 item",
                "run-last-failure: rerun previous 1 failure",
                "*1 failed in*",
            ]
        )

    def test_terminal_report_failedfirst(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            test_a="""
            def test_a1(): assert 0
            def test_a2(): pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 2 items", "*1 failed, 1 passed in*"])

        result = testrunnerer.runtestrunner("--ff")
        result.stdout.fnmatch_lines(
            [
                "collected 2 items",
                "run-last-failure: rerun previous 1 failure first",
                "*1 failed, 1 passed in*",
            ]
        )

    def test_lastfailed_collectfailure(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        testrunnerer.makepyfile(
            test_maybe="""
            import os
            env = os.environ
            if '1' == env['FAILIMPORT']:
                raise ImportError('fail')
            def test_hello():
                assert '0' == env['FAILTEST']
        """
        )

        def rlf(fail_import: int, fail_run: int) -> Any:
            monkeypatch.setenv("FAILIMPORT", str(fail_import))
            monkeypatch.setenv("FAILTEST", str(fail_run))

            testrunnerer.runtestrunner("-q")
            config = testrunnerer.parseconfigure()
            assert config.cache is not None
            lastfailed = config.cache.get("cache/lastfailed", -1)
            return lastfailed

        lastfailed = rlf(fail_import=0, fail_run=0)
        assert lastfailed == -1

        lastfailed = rlf(fail_import=1, fail_run=0)
        assert list(lastfailed) == ["test_maybe.py"]

        lastfailed = rlf(fail_import=0, fail_run=1)
        assert list(lastfailed) == ["test_maybe.py::test_hello"]

    def test_lastfailed_failure_subset(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        testrunnerer.makepyfile(
            test_maybe="""
            import os
            env = os.environ
            if '1' == env['FAILIMPORT']:
                raise ImportError('fail')
            def test_hello():
                assert '0' == env['FAILTEST']
        """
        )

        testrunnerer.makepyfile(
            test_maybe2="""
            import os
            env = os.environ
            if '1' == env['FAILIMPORT']:
                raise ImportError('fail')

            def test_hello():
                assert '0' == env['FAILTEST']

            def test_pass():
                pass
        """
        )

        def rlf(
            fail_import: int, fail_run: int, args: Sequence[str] = ()
        ) -> tuple[Any, Any]:
            monkeypatch.setenv("FAILIMPORT", str(fail_import))
            monkeypatch.setenv("FAILTEST", str(fail_run))

            result = testrunnerer.runtestrunner("-q", "--lf", *args)
            config = testrunnerer.parseconfigure()
            assert config.cache is not None
            lastfailed = config.cache.get("cache/lastfailed", -1)
            return result, lastfailed

        result, lastfailed = rlf(fail_import=0, fail_run=0)
        assert lastfailed == -1
        result.stdout.fnmatch_lines(["*3 passed*"])

        result, lastfailed = rlf(fail_import=1, fail_run=0)
        assert sorted(lastfailed) == ["test_maybe.py", "test_maybe2.py"]

        result, lastfailed = rlf(fail_import=0, fail_run=0, args=("test_maybe2.py",))
        assert list(lastfailed) == ["test_maybe.py"]

        # edge case of test selection - even if we remember failures
        # from other tests we still need to run all tests if no test
        # matches the failures
        result, lastfailed = rlf(fail_import=0, fail_run=0, args=("test_maybe2.py",))
        assert list(lastfailed) == ["test_maybe.py"]
        result.stdout.fnmatch_lines(["*2 passed*"])

    def test_lastfailed_creates_cache_when_needed(
        self, testrunnerer: Testrunnerer
    ) -> None:
        # Issue #1342
        testrunnerer.makepyfile(test_empty="")
        testrunnerer.runtestrunner("-q", "--lf")
        assert not os.path.exists(".testrunner_cache/v/cache/lastfailed")

        testrunnerer.makepyfile(test_successful="def test_success():\n    assert True")
        testrunnerer.runtestrunner("-q", "--lf")
        assert not os.path.exists(".testrunner_cache/v/cache/lastfailed")

        testrunnerer.makepyfile(test_errored="def test_error():\n    assert False")
        testrunnerer.runtestrunner("-q", "--lf")
        assert os.path.exists(".testrunner_cache/v/cache/lastfailed")

    def test_xfail_not_considered_failure(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.xfail
            def test(): assert 0
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 xfailed*"])
        assert self.get_cached_last_failed(testrunnerer) == []

    def test_xfail_strict_considered_failure(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            @testrunner.mark.xfail(strict=True)
            def test(): pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*1 failed*"])
        assert self.get_cached_last_failed(testrunnerer) == [
            "test_xfail_strict_considered_failure.py::test"
        ]

    @testrunner.mark.parametrize("mark", ["mark.xfail", "mark.skip"])
    def test_failed_changed_to_xfail_or_skip(
        self, testrunnerer: Testrunnerer, mark: str
    ) -> None:
        testrunnerer.makepyfile(
            """
            import testrunner
            def test(): assert 0
        """
        )
        result = testrunnerer.runtestrunner()
        assert self.get_cached_last_failed(testrunnerer) == [
            "test_failed_changed_to_xfail_or_skip.py::test"
        ]
        assert result.ret == 1

        testrunnerer.makepyfile(
            f"""
            import testrunner
            @testrunner.{mark}
            def test(): assert 0
        """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret == 0
        assert self.get_cached_last_failed(testrunnerer) == []
        assert result.ret == 0

    @testrunner.mark.parametrize("quiet", [True, False])
    @testrunner.mark.parametrize("opt", ["--ff", "--lf"])
    def test_lf_and_ff_prints_no_needless_message(
        self, quiet: bool, opt: str, testrunnerer: Testrunnerer
    ) -> None:
        # Issue 3853
        testrunnerer.makepyfile("def test(): assert 0")
        args = [opt]
        if quiet:
            args.append("-q")
        result = testrunnerer.runtestrunner(*args)
        result.stdout.no_fnmatch_line("*run all*")

        result = testrunnerer.runtestrunner(*args)
        if quiet:
            result.stdout.no_fnmatch_line("*run all*")
        else:
            assert "rerun previous" in result.stdout.str()

    def get_cached_last_failed(self, testrunnerer: Testrunnerer) -> list[str]:
        config = testrunnerer.parseconfigure()
        assert config.cache is not None
        return sorted(config.cache.get("cache/lastfailed", {}))

    def test_cache_cumulative(self, testrunnerer: Testrunnerer) -> None:
        """Test workflow where user fixes errors gradually file by file using --lf."""
        # 1. initial run
        test_bar = testrunnerer.makepyfile(
            test_bar="""
            def test_bar_1(): pass
            def test_bar_2(): assert 0
        """
        )
        test_foo = testrunnerer.makepyfile(
            test_foo="""
            def test_foo_3(): pass
            def test_foo_4(): assert 0
        """
        )
        testrunnerer.runtestrunner()
        assert self.get_cached_last_failed(testrunnerer) == [
            "test_bar.py::test_bar_2",
            "test_foo.py::test_foo_4",
        ]

        # 2. fix test_bar_2, run only test_bar.py
        testrunnerer.makepyfile(
            test_bar="""
            def test_bar_1(): pass
            def test_bar_2(): pass
        """
        )
        result = testrunnerer.runtestrunner(test_bar)
        result.stdout.fnmatch_lines(["*2 passed*"])
        # ensure cache does not forget that test_foo_4 failed once before
        assert self.get_cached_last_failed(testrunnerer) == ["test_foo.py::test_foo_4"]

        result = testrunnerer.runtestrunner("--last-failed")
        result.stdout.fnmatch_lines(
            [
                "collected 1 item",
                "run-last-failure: rerun previous 1 failure (skipped 1 file)",
                "*= 1 failed in *",
            ]
        )
        assert self.get_cached_last_failed(testrunnerer) == ["test_foo.py::test_foo_4"]

        # 3. fix test_foo_4, run only test_foo.py
        test_foo = testrunnerer.makepyfile(
            test_foo="""
            def test_foo_3(): pass
            def test_foo_4(): pass
        """
        )
        result = testrunnerer.runtestrunner(test_foo, "--last-failed")
        result.stdout.fnmatch_lines(
            [
                "collected 2 items / 1 deselected / 1 selected",
                "run-last-failure: rerun previous 1 failure",
                "*= 1 passed, 1 deselected in *",
            ]
        )
        assert self.get_cached_last_failed(testrunnerer) == []

        result = testrunnerer.runtestrunner("--last-failed")
        result.stdout.fnmatch_lines(["*4 passed*"])
        assert self.get_cached_last_failed(testrunnerer) == []

    def test_lastfailed_no_failures_behavior_all_passed(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            def test_1(): pass
            def test_2(): pass
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["*2 passed*"])
        result = testrunnerer.runtestrunner("--lf")
        result.stdout.fnmatch_lines(["*2 passed*"])
        result = testrunnerer.runtestrunner("--lf", "--lfnf", "all")
        result.stdout.fnmatch_lines(["*2 passed*"])

        # Ensure the list passed to testrunner_deselected is a copy,
        # and not a reference which is cleared right after.
        testrunnerer.makeconftest(
            """
            deselected = []

            def testrunner_deselected(items):
                global deselected
                deselected = items

            def testrunner_sessionfinish():
                print("\\ndeselected={}".format(len(deselected)))
        """
        )

        result = testrunnerer.runtestrunner("--lf", "--lfnf", "none")
        result.stdout.fnmatch_lines(
            [
                "collected 2 items / 2 deselected / 0 selected",
                "run-last-failure: no previously failed tests, deselecting all items.",
                "deselected=2",
                "* 2 deselected in *",
            ]
        )
        assert result.ret == ExitCode.NO_TESTS_COLLECTED

    def test_lastfailed_no_failures_behavior_empty_cache(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            """
            def test_1(): pass
            def test_2(): assert 0
        """
        )
        result = testrunnerer.runtestrunner("--lf", "--cache-clear")
        result.stdout.fnmatch_lines(["*1 failed*1 passed*"])
        result = testrunnerer.runtestrunner("--lf", "--cache-clear", "--lfnf", "all")
        result.stdout.fnmatch_lines(["*1 failed*1 passed*"])
        result = testrunnerer.runtestrunner("--lf", "--cache-clear", "--lfnf", "none")
        result.stdout.fnmatch_lines(["*2 desel*"])

    def test_lastfailed_skip_collection(self, testrunnerer: Testrunnerer) -> None:
        """
        Test --lf behavior regarding skipping collection of files that are not marked as
        failed in the cache (#5172).
        """
        testrunnerer.makepyfile(
            **{
                "pkg1/test_1.py": """
                import testrunner

                @testrunner.mark.parametrize('i', range(3))
                def test_1(i): pass
            """,
                "pkg2/test_2.py": """
                import testrunner

                @testrunner.mark.parametrize('i', range(5))
                def test_1(i):
                    assert i not in (1, 3)
            """,
            }
        )
        # first run: collects 8 items (test_1: 3, test_2: 5)
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 8 items", "*2 failed*6 passed*"])
        # second run: collects only 5 items from test_2, because all tests from test_1 have passed
        result = testrunnerer.runtestrunner("--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 2 items",
                "run-last-failure: rerun previous 2 failures (skipped 1 file)",
                "*= 2 failed in *",
            ]
        )

        # add another file and check if message is correct when skipping more than 1 file
        testrunnerer.makepyfile(
            **{
                "pkg1/test_3.py": """
                def test_3(): pass
            """
            }
        )
        result = testrunnerer.runtestrunner("--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 2 items",
                "run-last-failure: rerun previous 2 failures (skipped 2 files)",
                "*= 2 failed in *",
            ]
        )

    def test_lastfailed_skip_collection_with_nesting(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Check that file skipping works even when the file with failures is
        nested at a different level of the collection tree."""
        testrunnerer.makepyfile(
            **{
                "test_1.py": """
                    def test_1(): pass
                """,
                "pkg/__init__.py": "",
                "pkg/test_2.py": """
                    def test_2(): assert False
                """,
            }
        )
        # first run
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 2 items", "*1 failed*1 passed*"])
        # second run - test_1.py is skipped.
        result = testrunnerer.runtestrunner("--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 1 item",
                "run-last-failure: rerun previous 1 failure (skipped 1 file)",
                "*= 1 failed in *",
            ]
        )

    def test_lastfailed_with_known_failures_not_being_selected(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            **{
                "pkg1/test_1.py": """def test_1(): assert 0""",
                "pkg1/test_2.py": """def test_2(): pass""",
            }
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 2 items", "* 1 failed, 1 passed in *"])

        Path("pkg1/test_1.py").unlink()
        result = testrunnerer.runtestrunner("--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 1 item",
                "run-last-failure: 1 known failures not in selected tests",
                "* 1 passed in *",
            ]
        )

        # Recreate file with known failure.
        testrunnerer.makepyfile(**{"pkg1/test_1.py": """def test_1(): assert 0"""})
        result = testrunnerer.runtestrunner("--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 1 item",
                "run-last-failure: rerun previous 1 failure (skipped 1 file)",
                "* 1 failed in *",
            ]
        )

        # Remove/rename test: collects the file again.
        testrunnerer.makepyfile(
            **{"pkg1/test_1.py": """def test_renamed(): assert 0"""}
        )
        result = testrunnerer.runtestrunner("--lf", "-rf")
        result.stdout.fnmatch_lines(
            [
                "collected 2 items",
                "run-last-failure: 1 known failures not in selected tests",
                "pkg1/test_1.py F *",
                "pkg1/test_2.py . *",
                "FAILED pkg1/test_1.py::test_renamed - assert 0",
                "* 1 failed, 1 passed in *",
            ]
        )

        result = testrunnerer.runtestrunner("--lf", "--co")
        result.stdout.fnmatch_lines(
            [
                "collected 1 item",
                "run-last-failure: rerun previous 1 failure (skipped 1 file)",
                "",
                "<Dir *>",
                "  <Dir pkg1>",
                "    <Module test_1.py>",
                "      <Function test_renamed>",
            ]
        )

    def test_lastfailed_args_with_deselected(self, testrunnerer: Testrunnerer) -> None:
        """Test regression with --lf running into NoMatch error.

        This was caused by it not collecting (non-failed) nodes given as
        arguments.
        """
        testrunnerer.makepyfile(
            **{
                "pkg1/test_1.py": """
                    def test_pass(): pass
                    def test_fail(): assert 0
                """,
            }
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 2 items", "* 1 failed, 1 passed in *"])
        assert result.ret == 1

        result = testrunnerer.runtestrunner("pkg1/test_1.py::test_pass", "--lf", "--co")
        assert result.ret == 0
        result.stdout.fnmatch_lines(
            [
                "*collected 1 item",
                "run-last-failure: 1 known failures not in selected tests",
                "",
                "<Dir *>",
                "  <Dir pkg1>",
                "    <Module test_1.py>",
                "      <Function test_pass>",
            ],
            consecutive=True,
        )

        result = testrunnerer.runtestrunner(
            "pkg1/test_1.py::test_pass", "pkg1/test_1.py::test_fail", "--lf", "--co"
        )
        assert result.ret == 0
        result.stdout.fnmatch_lines(
            [
                "collected 2 items / 1 deselected / 1 selected",
                "run-last-failure: rerun previous 1 failure",
                "",
                "<Dir *>",
                "  <Dir pkg1>",
                "    <Module test_1.py>",
                "      <Function test_fail>",
                "*= 1/2 tests collected (1 deselected) in *",
            ],
        )

    def test_lastfailed_with_class_items(self, testrunnerer: Testrunnerer) -> None:
        """Test regression with --lf deselecting whole classes."""
        testrunnerer.makepyfile(
            **{
                "pkg1/test_1.py": """
                    class TestFoo:
                        def test_pass(self): pass
                        def test_fail(self): assert 0

                    def test_other(): assert 0
                """,
            }
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 3 items", "* 2 failed, 1 passed in *"])
        assert result.ret == 1

        result = testrunnerer.runtestrunner("--lf", "--co")
        assert result.ret == 0
        result.stdout.fnmatch_lines(
            [
                "collected 3 items / 1 deselected / 2 selected",
                "run-last-failure: rerun previous 2 failures",
                "",
                "<Dir *>",
                "  <Dir pkg1>",
                "    <Module test_1.py>",
                "      <Class TestFoo>",
                "        <Function test_fail>",
                "      <Function test_other>",
                "",
                "*= 2/3 tests collected (1 deselected) in *",
            ],
            consecutive=True,
        )

    def test_lastfailed_with_all_filtered(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            **{
                "pkg1/test_1.py": """
                    def test_fail(): assert 0
                    def test_pass(): pass
                """,
            }
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 2 items", "* 1 failed, 1 passed in *"])
        assert result.ret == 1

        # Remove known failure.
        testrunnerer.makepyfile(
            **{
                "pkg1/test_1.py": """
                    def test_pass(): pass
                """,
            }
        )
        result = testrunnerer.runtestrunner("--lf", "--co")
        result.stdout.fnmatch_lines(
            [
                "collected 1 item",
                "run-last-failure: 1 known failures not in selected tests",
                "",
                "<Dir *>",
                "  <Dir pkg1>",
                "    <Module test_1.py>",
                "      <Function test_pass>",
                "",
                "*= 1 test collected in*",
            ],
            consecutive=True,
        )
        assert result.ret == 0

    def test_packages(self, testrunnerer: Testrunnerer) -> None:
        """Regression test for #7758.

        The particular issue here was that Package nodes were included in the
        filtering, being themselves Modules for the __init__.py, even if they
        had failed Modules in them.

        The tests includes a test in an __init__.py file just to make sure the
        fix doesn't somehow regress that, it is not critical for the issue.
        """
        testrunnerer.makepyfile(
            **{
                "__init__.py": "",
                "a/__init__.py": "def test_a_init(): assert False",
                "a/test_one.py": "def test_1(): assert False",
                "b/__init__.py": "",
                "b/test_two.py": "def test_2(): assert False",
            },
        )
        testrunnerer.makeini(
            """
            [testrunner]
            python_files = *.py
            """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(failed=3)
        result = testrunnerer.runtestrunner("--lf")
        result.assert_outcomes(failed=3)

    def test_non_python_file_skipped(
        self,
        testrunnerer: Testrunnerer,
        dummy_yaml_custom_test: None,
    ) -> None:
        testrunnerer.makepyfile(
            **{
                "test_bad.py": """def test_bad(): assert False""",
            },
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["collected 2 items", "* 1 failed, 1 passed in *"])

        result = testrunnerer.runtestrunner("--lf")
        result.stdout.fnmatch_lines(
            [
                "collected 1 item",
                "run-last-failure: rerun previous 1 failure (skipped 1 file)",
                "* 1 failed in *",
            ]
        )


class TestNewFirst:
    def test_newfirst_usecase(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            **{
                "test_1/test_1.py": """
                def test_1(): assert 1
            """,
                "test_2/test_2.py": """
                def test_1(): assert 1
            """,
            }
        )

        p1 = testrunnerer.path.joinpath("test_1/test_1.py")
        os.utime(p1, ns=(p1.stat().st_atime_ns, int(1e9)))

        result = testrunnerer.runtestrunner("-v")
        result.stdout.fnmatch_lines(
            ["*test_1/test_1.py::test_1 PASSED*", "*test_2/test_2.py::test_1 PASSED*"]
        )

        result = testrunnerer.runtestrunner("-v", "--nf")
        result.stdout.fnmatch_lines(
            ["*test_2/test_2.py::test_1 PASSED*", "*test_1/test_1.py::test_1 PASSED*"]
        )

        p1.write_text(
            "def test_1(): assert 1\ndef test_2(): assert 1\n", encoding="utf-8"
        )
        os.utime(p1, ns=(p1.stat().st_atime_ns, int(1e9)))

        result = testrunnerer.runtestrunner("--nf", "--collect-only", "-q")
        result.stdout.fnmatch_lines(
            [
                "test_1/test_1.py::test_2",
                "test_2/test_2.py::test_1",
                "test_1/test_1.py::test_1",
            ]
        )

        # Newest first with (plugin) testrunner_collection_modifyitems hook.
        testrunnerer.makepyfile(
            myplugin="""
            def testrunner_collection_modifyitems(items):
                items[:] = sorted(items, key=lambda item: item.nodeid)
                print("new_items:", [x.nodeid for x in items])
            """
        )
        testrunnerer.syspathinsert()
        result = testrunnerer.runtestrunner(
            "--nf", "-p", "myplugin", "--collect-only", "-q"
        )
        result.stdout.fnmatch_lines(
            [
                "new_items: *test_1/test_1.py::test_1*",
                "test_1/test_1.py::test_2",
                "test_2/test_2.py::test_1",
                "test_1/test_1.py::test_1",
            ]
        )

    def test_newfirst_parametrize(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(
            **{
                "test_1/test_1.py": """
                import testrunner
                @testrunner.mark.parametrize('num', [1, 2])
                def test_1(num): assert num
            """,
                "test_2/test_2.py": """
                import testrunner
                @testrunner.mark.parametrize('num', [1, 2])
                def test_1(num): assert num
            """,
            }
        )

        p1 = testrunnerer.path.joinpath("test_1/test_1.py")
        os.utime(p1, ns=(p1.stat().st_atime_ns, int(1e9)))

        result = testrunnerer.runtestrunner("-v")
        result.stdout.fnmatch_lines(
            [
                "*test_1/test_1.py::test_1[1*",
                "*test_1/test_1.py::test_1[2*",
                "*test_2/test_2.py::test_1[1*",
                "*test_2/test_2.py::test_1[2*",
            ]
        )

        result = testrunnerer.runtestrunner("-v", "--nf")
        result.stdout.fnmatch_lines(
            [
                "*test_2/test_2.py::test_1[1*",
                "*test_2/test_2.py::test_1[2*",
                "*test_1/test_1.py::test_1[1*",
                "*test_1/test_1.py::test_1[2*",
            ]
        )

        p1.write_text(
            "import testrunner\n"
            "@testrunner.mark.parametrize('num', [1, 2, 3])\n"
            "def test_1(num): assert num\n",
            encoding="utf-8",
        )
        os.utime(p1, ns=(p1.stat().st_atime_ns, int(1e9)))

        # Running only a subset does not forget about existing ones.
        result = testrunnerer.runtestrunner("-v", "--nf", "test_2/test_2.py")
        result.stdout.fnmatch_lines(
            ["*test_2/test_2.py::test_1[1*", "*test_2/test_2.py::test_1[2*"]
        )

        result = testrunnerer.runtestrunner("-v", "--nf")
        result.stdout.fnmatch_lines(
            [
                "*test_1/test_1.py::test_1[3*",
                "*test_2/test_2.py::test_1[1*",
                "*test_2/test_2.py::test_1[2*",
                "*test_1/test_1.py::test_1[1*",
                "*test_1/test_1.py::test_1[2*",
            ]
        )


class TestReadme:
    def check_readme(self, testrunnerer: Testrunnerer) -> bool:
        config = testrunnerer.parseconfigure()
        assert config.cache is not None
        readme = config.cache._cachedir.joinpath("README.md")
        return readme.is_file()

    def test_readme_passed(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile("def test_always_passes(): pass")
        testrunnerer.runtestrunner()
        assert self.check_readme(testrunnerer) is True

    def test_readme_failed(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile("def test_always_fails(): assert 0")
        testrunnerer.runtestrunner()
        assert self.check_readme(testrunnerer) is True


class Action(Enum):
    """Action to perform on the cache directory."""

    MKDIR = auto()
    SET = auto()


@testrunner.mark.parametrize("action", list(Action))
def test_gitignore(
    testrunnerer: Testrunnerer,
    action: Action,
) -> None:
    """Ensure we automatically create .gitignore file in the testrunner_cache directory (#3286)."""
    from _testrunner.cacheprovider import Cache

    config = testrunnerer.parseconfig()
    cache = Cache.for_config(config, _istestrunner=True)
    if action == Action.MKDIR:
        cache.mkdir("foo")
    elif action == Action.SET:
        cache.set("foo", "bar")
    else:
        assert_never(action)
    msg = "# Created by testrunner automatically.\n*\n"
    gitignore_path = cache._cachedir.joinpath(".gitignore")
    assert gitignore_path.read_text(encoding="UTF-8") == msg

    # Does not overwrite existing/custom one.
    gitignore_path.write_text("custom", encoding="utf-8")
    if action == Action.MKDIR:
        cache.mkdir("something")
    elif action == Action.SET:
        cache.set("something", "else")
    else:
        assert_never(action)
    assert gitignore_path.read_text(encoding="UTF-8") == "custom"


def test_preserve_keys_order(testrunnerer: Testrunnerer) -> None:
    """Ensure keys order is preserved when saving dicts (#9205)."""
    from _testrunner.cacheprovider import Cache

    config = testrunnerer.parseconfig()
    cache = Cache.for_config(config, _istestrunner=True)
    cache.set("foo", {"z": 1, "b": 2, "a": 3, "d": 10})
    read_back = cache.get("foo", None)
    assert list(read_back.items()) == [("z", 1), ("b", 2), ("a", 3), ("d", 10)]


def test_does_not_create_boilerplate_in_existing_dirs(
    testrunnerer: Testrunnerer,
) -> None:
    from _testrunner.cacheprovider import Cache

    testrunnerer.makeini(
        """
        [testrunner]
        cache_dir = .
        """
    )
    config = testrunnerer.parseconfig()
    cache = Cache.for_config(config, _istestrunner=True)
    cache.set("foo", "bar")

    assert os.path.isdir("v")  # cache contents
    assert not os.path.exists(".gitignore")
    assert not os.path.exists("README.md")


def test_cachedir_tag(testrunnerer: Testrunnerer) -> None:
    """Ensure we automatically create CACHEDIR.TAG file in the testrunner_cache directory (#4278)."""
    from _testrunner.cacheprovider import Cache
    from _testrunner.cacheprovider import CACHEDIR_FILES

    config = testrunnerer.parseconfig()
    cache = Cache.for_config(config, _istestrunner=True)
    cache.set("foo", "bar")
    cachedir_tag_path = cache._cachedir.joinpath("CACHEDIR.TAG")
    assert cachedir_tag_path.read_bytes() == CACHEDIR_FILES["CACHEDIR.TAG"]


def test_clioption_with_cacheshow_and_help(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("--cache-show", "--help")
    assert result.ret == 0


def test_make_cachedir_cleans_up_on_base_exception(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Ensure _make_cachedir cleans up the temp directory on BaseException.

    When a BaseException (like KeyboardInterrupt) is raised during cache
    directory creation, the temporary directory should be cleaned up before
    re-raising the exception.
    """
    from _testrunner.cacheprovider import _make_cachedir

    target = tmp_path / ".testrunner_cache"

    def raise_keyboard_interrupt(self: Path, target: Path) -> None:
        raise KeyboardInterrupt("simulated interrupt")

    # Patch Path.rename only for the duration of the _make_cachedir call
    with monkeypatch.context() as m:
        m.setattr(Path, "rename", raise_keyboard_interrupt)

        # Verify the exception is re-raised
        with testrunner.raises(KeyboardInterrupt, match="simulated interrupt"):
            _make_cachedir(target)

    # Verify no temp directories were left behind
    temp_dirs = list(tmp_path.glob("testrunner-cache-files-*"))
    assert temp_dirs == [], f"Temp directories not cleaned up: {temp_dirs}"

    # Verify the target directory was not created
    assert not target.exists()
