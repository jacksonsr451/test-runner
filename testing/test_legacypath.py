# mypy: allow-untyped-defs
from __future__ import annotations

from pathlib import Path

from _testrunner.compat import LEGACY_PATH
from _testrunner.fixtures import TopRequest
from _testrunner.legacypath import TempdirFactory
from _testrunner.legacypath import Testdir
import testrunner


def test_item_fspath(testrunnerer: testrunner.Testrunnerer) -> None:
    testrunnerer.makepyfile("def test_func(): pass")
    items, _hookrec = testrunnerer.inline_genitems()
    assert len(items) == 1
    (item,) = items
    items2, _hookrec = testrunnerer.inline_genitems(item.nodeid)
    (item2,) = items2
    assert item2.name == item.name
    assert item2.fspath == item.fspath
    assert item2.path == item.path


def test_testdir_testtmproot(testdir: Testdir) -> None:
    """Check test_tmproot is a py.path attribute for backward compatibility."""
    assert testdir.test_tmproot.check(dir=1)


def test_testdir_makefile_dot_prefixes_extension_silently(
    testdir: Testdir,
) -> None:
    """For backwards compat #8192"""
    p1 = testdir.makefile("foo.bar", "")
    assert ".foo.bar" in str(p1)


def test_testdir_makefile_ext_none_raises_type_error(testdir: Testdir) -> None:
    """For backwards compat #8192"""
    with testrunner.raises(TypeError):
        testdir.makefile(None, "")


def test_testdir_makefile_ext_empty_string_makes_file(testdir: Testdir) -> None:
    """For backwards compat #8192"""
    p1 = testdir.makefile("", "")
    assert "test_testdir_makefile" in str(p1)


def attempt_symlink_to(path: str, to_path: str) -> None:
    """Try to make a symlink from "path" to "to_path", skipping in case this platform
    does not support it or we don't have sufficient privileges (common on Windows)."""
    try:
        Path(path).symlink_to(Path(to_path))
    except OSError:
        testrunner.skip("could not create symbolic link")


def test_tmpdir_factory(
    tmpdir_factory: TempdirFactory,
    tmp_path_factory: testrunner.TempPathFactory,
) -> None:
    assert str(tmpdir_factory.getbasetemp()) == str(tmp_path_factory.getbasetemp())
    dir = tmpdir_factory.mktemp("foo")
    assert dir.exists()


def test_tmpdir_equals_tmp_path(tmpdir: LEGACY_PATH, tmp_path: Path) -> None:
    assert Path(tmpdir) == tmp_path


def test_tmpdir_always_is_realpath(testrunnerer: testrunner.Testrunnerer) -> None:
    # See test_tmp_path_always_is_realpath.
    realtemp = testrunnerer.mkdir("myrealtemp")
    linktemp = testrunnerer.path.joinpath("symlinktemp")
    attempt_symlink_to(str(linktemp), str(realtemp))
    p = testrunnerer.makepyfile(
        """
        def test_1(tmpdir):
            import os
            assert os.path.realpath(str(tmpdir)) == str(tmpdir)
    """
    )
    result = testrunnerer.runtestrunner("-s", p, f"--basetemp={linktemp}/bt")
    assert not result.ret


def test_cache_makedir(cache: testrunner.Cache) -> None:
    dir = cache.makedir("foo")  # type: ignore[attr-defined]
    assert dir.exists()
    dir.remove()


def test_fixturerequest_getmodulepath(testrunnerer: testrunner.Testrunnerer) -> None:
    modcol = testrunnerer.getmodulecol("def test_somefunc(): pass")
    (item,) = testrunnerer.genitems([modcol])
    assert isinstance(item, testrunner.Function)
    req = TopRequest(item, _istestrunner=True)
    assert req.path == modcol.path
    assert req.fspath == modcol.fspath  # type: ignore[attr-defined]


class TestFixtureRequestSessionScoped:
    @testrunner.fixture(scope="session")
    @staticmethod
    def session_request(request):
        return request

    def test_session_scoped_unavailable_attributes(self, session_request):
        with testrunner.raises(
            AttributeError,
            match="path not available in session-scoped context",
        ):
            _ = session_request.fspath


@testrunner.mark.parametrize("config_type", ["ini", "toml"])
def test_addini_paths(testrunnerer: testrunner.Testrunnerer, config_type: str) -> None:
    testrunnerer.makeconftest(
        """
        def testrunner_addoption(parser):
            parser.addini("paths", "my new ini value", type="pathlist")
            parser.addini("abc", "abc value")
    """
    )
    if config_type == "ini":
        inipath = testrunnerer.makeini(
            """
            [testrunner]
            paths = hello world/sub.py
            """
        )
    else:
        inipath = testrunnerer.maketoml(
            """
            [testrunner]
            paths = ["hello", "world/sub.py"]
            """
        )
    config = testrunnerer.parseconfig()
    values = config.getini("paths")
    assert len(values) == 2
    assert values[0] == inipath.parent.joinpath("hello")
    assert values[1] == inipath.parent.joinpath("world/sub.py")
    with testrunner.raises(ValueError):
        config.getini("other")


def test_override_ini_paths(testrunnerer: testrunner.Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
        def testrunner_addoption(parser):
            parser.addini("paths", "my new ini value", type="pathlist")"""
    )
    testrunnerer.makeini(
        """
        [testrunner]
        paths=blah.py"""
    )
    testrunnerer.makepyfile(
        r"""
        def test_overridden(testrunnerconfig):
            config_paths = testrunnerconfig.getini("paths")
            print(config_paths)
            for cpf in config_paths:
                print('\nuser_path:%s' % cpf.basename)
        """
    )
    result = testrunnerer.runtestrunner("--override-ini", "paths=foo/bar1.py foo/bar2.py", "-s")
    result.stdout.fnmatch_lines(["user_path:bar1.py", "user_path:bar2.py"])


def test_inifile_from_cmdline_main_hook(testrunnerer: testrunner.Testrunnerer) -> None:
    """Ensure Config.inifile is available during testrunner_cmdline_main (#9396)."""
    p = testrunnerer.makeini(
        """
        [testrunner]
        """
    )
    testrunnerer.makeconftest(
        """
        def testrunner_cmdline_main(config):
            print("testrunner_cmdline_main inifile =", config.inifile)
        """
    )
    result = testrunnerer.runtestrunner_subprocess("-s")
    result.stdout.fnmatch_lines(f"*testrunner_cmdline_main inifile = {p}")
