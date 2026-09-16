# mypy: allow-untyped-defs
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re

from _testrunner.config import ExitCode
from _testrunner.config import UsageError
from _testrunner.main import CollectionArgument
from _testrunner.main import resolve_collection_argument
from _testrunner.main import validate_basetemp
from _testrunner.testrunnerer import Testrunnerer
import testrunner


@testrunner.mark.parametrize(
    "ret_exc",
    (
        testrunner.param((None, ValueError)),
        testrunner.param((42, SystemExit)),
        testrunner.param((False, SystemExit)),
    ),
)
def test_wrap_session_notify_exception(ret_exc, testrunnerer: Testrunnerer) -> None:
    returncode, exc = ret_exc
    c1 = testrunnerer.makeconftest(
        f"""
        import testrunner

        def testrunner_sessionstart():
            raise {exc.__name__}("boom")

        def testrunner_internalerror(excrepr, excinfo):
            returncode = {returncode!r}
            if returncode is not False:
                testrunner.exit("exiting after %s..." % excinfo.typename, returncode={returncode!r})
    """
    )
    result = testrunnerer.runtestrunner()
    if returncode:
        assert result.ret == returncode
    else:
        assert result.ret == ExitCode.INTERNAL_ERROR
    assert result.stdout.lines[0] == "INTERNALERROR> Traceback (most recent call last):"

    end_lines = result.stdout.lines[-3:]

    if exc == SystemExit:
        assert end_lines == [
            f'INTERNALERROR>   File "{c1}", line 4, in testrunner_sessionstart',
            'INTERNALERROR>     raise SystemExit("boom")',
            "INTERNALERROR> SystemExit: boom",
        ]
    else:
        assert end_lines == [
            f'INTERNALERROR>   File "{c1}", line 4, in testrunner_sessionstart',
            'INTERNALERROR>     raise ValueError("boom")',
            "INTERNALERROR> ValueError: boom",
        ]
    if returncode is False:
        assert result.stderr.lines == ["mainloop: caught unexpected SystemExit!"]
    else:
        assert result.stderr.lines == [f"Exit: exiting after {exc.__name__}..."]


@testrunner.mark.parametrize("returncode", (None, 42))
def test_wrap_session_exit_sessionfinish(
    returncode: int | None, testrunnerer: Testrunnerer
) -> None:
    testrunnerer.makeconftest(
        f"""
        import testrunner
        def testrunner_sessionfinish():
            testrunner.exit(reason="exit_testrunner_sessionfinish", returncode={returncode})
    """
    )
    result = testrunnerer.runtestrunner()
    if returncode:
        assert result.ret == returncode
    else:
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
    assert result.stdout.lines[-1] == "collected 0 items"
    assert result.stderr.lines == ["Exit: exit_testrunner_sessionfinish"]


@testrunner.mark.parametrize("basetemp", ["foo", "foo/bar"])
def test_validate_basetemp_ok(tmp_path, basetemp, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    validate_basetemp(tmp_path / basetemp)


@testrunner.mark.parametrize("basetemp", ["", ".", ".."])
def test_validate_basetemp_fails(tmp_path, basetemp, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    msg = "basetemp must not be empty, the current working directory or any parent directory of it"
    with testrunner.raises(argparse.ArgumentTypeError, match=msg):
        if basetemp:
            basetemp = tmp_path / basetemp
        validate_basetemp(basetemp)


def test_validate_basetemp_integration(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("--basetemp=.")
    result.stderr.fnmatch_lines("*basetemp must not be*")


class TestResolveCollectionArgument:
    @testrunner.fixture
    def invocation_path(self, testrunnerer: Testrunnerer) -> Path:
        testrunnerer.syspathinsert(testrunnerer.path / "src")
        testrunnerer.chdir()

        pkg = testrunnerer.path.joinpath("src/pkg")
        pkg.mkdir(parents=True)
        pkg.joinpath("__init__.py").touch()
        pkg.joinpath("test.py").touch()
        return testrunnerer.path

    def test_file(self, invocation_path: Path) -> None:
        """File and parts."""
        assert resolve_collection_argument(
            invocation_path, "src/pkg/test.py", 0
        ) == CollectionArgument(
            path=invocation_path / "src/pkg/test.py",
            parts=[],
            parametrization=None,
            module_name=None,
            original_index=0,
        )
        assert resolve_collection_argument(
            invocation_path, "src/pkg/test.py::", 10
        ) == CollectionArgument(
            path=invocation_path / "src/pkg/test.py",
            parts=[""],
            parametrization=None,
            module_name=None,
            original_index=10,
        )
        assert resolve_collection_argument(
            invocation_path, "src/pkg/test.py::foo::bar", 20
        ) == CollectionArgument(
            path=invocation_path / "src/pkg/test.py",
            parts=["foo", "bar"],
            parametrization=None,
            module_name=None,
            original_index=20,
        )
        assert resolve_collection_argument(
            invocation_path, "src/pkg/test.py::foo::bar::", 30
        ) == CollectionArgument(
            path=invocation_path / "src/pkg/test.py",
            parts=["foo", "bar", ""],
            parametrization=None,
            module_name=None,
            original_index=30,
        )
        assert resolve_collection_argument(
            invocation_path, "src/pkg/test.py::foo::bar[a,b,c]", 40
        ) == CollectionArgument(
            path=invocation_path / "src/pkg/test.py",
            parts=["foo", "bar"],
            parametrization="[a,b,c]",
            module_name=None,
            original_index=40,
        )

    def test_dir(self, invocation_path: Path) -> None:
        """Directory and parts."""
        assert resolve_collection_argument(
            invocation_path, "src/pkg", 0
        ) == CollectionArgument(
            path=invocation_path / "src/pkg",
            parts=[],
            parametrization=None,
            module_name=None,
            original_index=0,
        )

        with testrunner.raises(
            UsageError, match=r"directory argument cannot contain :: selection parts"
        ):
            resolve_collection_argument(invocation_path, "src/pkg::", 0)

        with testrunner.raises(
            UsageError, match=r"directory argument cannot contain :: selection parts"
        ):
            resolve_collection_argument(invocation_path, "src/pkg::foo::bar", 0)

    @testrunner.mark.parametrize("namespace_package", [False, True])
    def test_pypath(self, namespace_package: bool, invocation_path: Path) -> None:
        """Dotted name and parts."""
        if namespace_package:
            # Namespace package doesn't have to contain __init__py
            (invocation_path / "src/pkg/__init__.py").unlink()

        assert resolve_collection_argument(
            invocation_path, "pkg.test", 0, as_pypath=True
        ) == CollectionArgument(
            path=invocation_path / "src/pkg/test.py",
            parts=[],
            parametrization=None,
            module_name="pkg.test",
            original_index=0,
        )
        assert resolve_collection_argument(
            invocation_path, "pkg.test::foo::bar", 0, as_pypath=True
        ) == CollectionArgument(
            path=invocation_path / "src/pkg/test.py",
            parts=["foo", "bar"],
            parametrization=None,
            module_name="pkg.test",
            original_index=0,
        )
        assert resolve_collection_argument(
            invocation_path,
            "pkg",
            0,
            as_pypath=True,
            consider_namespace_packages=namespace_package,
        ) == CollectionArgument(
            path=invocation_path / "src/pkg",
            parts=[],
            parametrization=None,
            module_name="pkg",
            original_index=0,
        )

        with testrunner.raises(
            UsageError, match=r"package argument cannot contain :: selection parts"
        ):
            resolve_collection_argument(
                invocation_path,
                "pkg::foo::bar",
                0,
                as_pypath=True,
                consider_namespace_packages=namespace_package,
            )

    def test_parametrized_name_with_colons(self, invocation_path: Path) -> None:
        assert resolve_collection_argument(
            invocation_path, "src/pkg/test.py::test[a::b]", 0
        ) == CollectionArgument(
            path=invocation_path / "src/pkg/test.py",
            parts=["test"],
            parametrization="[a::b]",
            module_name=None,
            original_index=0,
        )

    @testrunner.mark.parametrize(
        "arg", ["x.py[a]", "x.py[a]::foo", "x/y.py[a]::foo::bar", "x.py[a]::foo[b]"]
    )
    def test_path_parametrization_not_allowed(
        self, invocation_path: Path, arg: str
    ) -> None:
        with testrunner.raises(
            UsageError, match=r"path cannot contain \[\] parametrization"
        ):
            resolve_collection_argument(invocation_path, arg, 0)

    def test_does_not_exist(self, invocation_path: Path) -> None:
        """Given a file/module that does not exist raises UsageError."""
        with testrunner.raises(
            UsageError, match=re.escape("file or directory not found: foobar")
        ):
            resolve_collection_argument(invocation_path, "foobar", 0)

        with testrunner.raises(
            UsageError,
            match=re.escape(
                "module or package not found: foobar (missing __init__.py?)"
            ),
        ):
            resolve_collection_argument(invocation_path, "foobar", 0, as_pypath=True)

    def test_absolute_paths_are_resolved_correctly(self, invocation_path: Path) -> None:
        """Absolute paths resolve back to absolute paths."""
        full_path = str(invocation_path / "src")
        assert resolve_collection_argument(
            invocation_path, full_path, 0
        ) == CollectionArgument(
            path=Path(os.path.abspath("src")),
            parts=[],
            parametrization=None,
            module_name=None,
            original_index=0,
        )

        # ensure full paths given in the command-line without the drive letter resolve
        # to the full path correctly (#7628)
        _drive, full_path_without_drive = os.path.splitdrive(full_path)
        assert resolve_collection_argument(
            invocation_path, full_path_without_drive, 0
        ) == CollectionArgument(
            path=Path(os.path.abspath("src")),
            parts=[],
            parametrization=None,
            module_name=None,
            original_index=0,
        )


def test_module_full_path_without_drive(testrunnerer: Testrunnerer) -> None:
    """Collect and run test using full path except for the drive letter (#7628).

    Passing a full path without a drive letter would trigger a bug in legacy_path
    where it would keep the full path without the drive letter around, instead of resolving
    to the full path, resulting in fixtures node ids not matching against test node ids correctly.
    """
    testrunnerer.makepyfile(
        **{
            "project/conftest.py": """
                import testrunner
                @testrunner.fixture
                def fix(): return 1
            """,
        }
    )

    testrunnerer.makepyfile(
        **{
            "project/tests/dummy_test.py": """
                def test(fix):
                    assert fix == 1
            """
        }
    )
    fn = testrunnerer.path.joinpath("project/tests/dummy_test.py")
    assert fn.is_file()

    _drive, path = os.path.splitdrive(str(fn))

    result = testrunnerer.runtestrunner(path, "-v")
    result.stdout.fnmatch_lines(
        [
            os.path.join("project", "tests", "dummy_test.py") + "::test PASSED *",
            "* 1 passed in *",
        ]
    )


def test_very_long_cmdline_arg(testrunnerer: Testrunnerer) -> None:
    """
    Regression test for #11394.

    Note: we could not manage to actually reproduce the error with this code, we suspect
    GitHub runners are configured to support very long paths, however decided to leave
    the test in place in case this ever regresses in the future.
    """
    testrunnerer.makeconftest(
        """
        import testrunner

        def testrunner_addoption(parser):
            parser.addoption("--long-list", dest="long_list", action="store", default="all", help="List of things")

        @testrunner.fixture(scope="module")
        def specified_feeds(request):
            list_string = request.config.getoption("--long-list")
            return list_string.split(',')
        """
    )
    testrunnerer.makepyfile(
        """
        def test_foo(specified_feeds):
            assert len(specified_feeds) == 100_000
        """
    )
    result = testrunnerer.runtestrunner(
        "--long-list", ",".join(["helloworld"] * 100_000)
    )
    result.stdout.fnmatch_lines("* 1 passed *")
