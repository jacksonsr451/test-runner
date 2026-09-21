"""Conftest discovery and loading for a TestRunner plugin manager."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
import pathlib
import sys
import types
from typing import Any
from typing import cast

from _testrunner.nodeid import NodeId
from _testrunner.outcomes import fail
from _testrunner.pathlib import absolutepath
from _testrunner.pathlib import import_path
from _testrunner.pathlib import ImportMode
from _testrunner.pathlib import resolve_package_path
from _testrunner.pathlib import safe_exists


def _get_directory(path: pathlib.Path) -> pathlib.Path:
    """Get the directory of a path, using the path itself if it is a directory."""
    if path.is_file():
        return path.parent
    return path


class ConftestManager:
    """Own conftest discovery state for one plugin manager."""

    def __init__(self, pluginmanager: Any) -> None:
        self._pluginmanager = pluginmanager
        self._conftest_plugins: set[types.ModuleType] = set()
        self._dirpath2confmods: dict[pathlib.Path, list[types.ModuleType]] = {}
        self._confcutdir: pathlib.Path | None = None
        self._noconftest = False
        self._using_pyargs = False
        self._get_directory = lru_cache(256)(_get_directory)

    def set_initial_conftests(
        self,
        args: Sequence[str | pathlib.Path],
        pyargs: bool,
        noconftest: bool,
        rootpath: pathlib.Path,
        confcutdir: pathlib.Path | None,
        invocation_dir: pathlib.Path,
        importmode: ImportMode | str,
        *,
        consider_namespace_packages: bool,
    ) -> None:
        """Load initial conftest files given a preparsed namespace."""
        self._confcutdir = (
            absolutepath(invocation_dir / confcutdir) if confcutdir else None
        )
        self._noconftest = noconftest
        self._using_pyargs = pyargs

        anchors = []
        for initial_path in args:
            path = NodeId.parse(str(initial_path)).path
            anchor = absolutepath(invocation_dir / path)
            if not safe_exists(anchor):
                continue

            anchors.append(anchor)
            if anchor.is_dir():
                anchors.extend(x for x in anchor.glob("test*") if x.is_dir())
        if not anchors:
            anchors.append(invocation_dir)
            anchors.extend(x for x in invocation_dir.glob("test*") if x.is_dir())

        for anchor in anchors:
            self._pluginmanager._loadconftestmodules(
                anchor,
                importmode,
                rootpath,
                consider_namespace_packages=consider_namespace_packages,
            )

    def is_in_confcutdir(self, path: pathlib.Path) -> bool:
        """Whether to consider the given path to load conftests from."""
        if self._confcutdir is None:
            return True
        return path not in self._confcutdir.parents

    def load_conftest_modules(
        self,
        path: pathlib.Path,
        importmode: str | ImportMode,
        rootpath: pathlib.Path,
        *,
        consider_namespace_packages: bool,
    ) -> None:
        if self._noconftest:
            return

        directory = self._get_directory(path)
        if directory in self._dirpath2confmods:
            return

        clist = []
        for parent in reversed((directory, *directory.parents)):
            if self._pluginmanager._is_in_confcutdir(parent):
                conftestpath = parent / "conftest.py"
                if conftestpath.is_file():
                    mod = self._pluginmanager._importconftest(
                        conftestpath,
                        importmode,
                        rootpath,
                        consider_namespace_packages=consider_namespace_packages,
                    )
                    clist.append(mod)
        self._dirpath2confmods[directory] = clist

    def get_conftest_modules(self, path: pathlib.Path) -> Sequence[types.ModuleType]:
        directory = self._get_directory(path)
        return self._dirpath2confmods.get(directory, ())

    def rget_with_confmod(
        self,
        name: str,
        path: pathlib.Path,
    ) -> tuple[types.ModuleType, Any]:
        modules = self.get_conftest_modules(path)
        for mod in reversed(modules):
            try:
                return mod, getattr(mod, name)
            except AttributeError:
                continue
        raise KeyError(name)

    def import_conftest(
        self,
        conftestpath: pathlib.Path,
        importmode: str | ImportMode,
        rootpath: pathlib.Path,
        *,
        consider_namespace_packages: bool,
    ) -> types.ModuleType:
        conftestpath_plugin_name = str(conftestpath)
        existing = self._pluginmanager.get_plugin(conftestpath_plugin_name)
        if existing is not None:
            return cast(types.ModuleType, existing)

        pkgpath = resolve_package_path(conftestpath)
        if pkgpath is None:
            try:
                del sys.modules[conftestpath.stem]
            except KeyError:
                pass

        try:
            mod = import_path(
                conftestpath,
                mode=importmode,
                root=rootpath,
                consider_namespace_packages=consider_namespace_packages,
            )
        except Exception as e:
            from _testrunner.config import ConftestImportFailure

            assert e.__traceback__ is not None
            raise ConftestImportFailure(conftestpath, cause=e) from e

        self._pluginmanager._check_non_top_testrunner_plugins(mod, conftestpath)

        self._conftest_plugins.add(mod)
        dirpath = conftestpath.parent
        if dirpath in self._dirpath2confmods:
            for path, mods in self._dirpath2confmods.items():
                if dirpath in path.parents or path == dirpath:
                    if mod in mods:
                        raise AssertionError(
                            f"While trying to load conftest path {conftestpath!s}, "
                            f"found that the module {mod} is already loaded with path {mod.__file__}. "
                            "This is not supposed to happen. Please report this issue to testrunner."
                        )
                    mods.append(mod)
        self._pluginmanager.trace(f"loading conftestmodule {mod!r}")
        self._pluginmanager.consider_conftest(
            mod, registration_name=conftestpath_plugin_name
        )
        return mod

    def check_non_top_testrunner_plugins(
        self,
        mod: types.ModuleType,
        conftestpath: pathlib.Path,
    ) -> None:
        plugin_spec_name = (
            "testrunner_plugins"
            if hasattr(mod, "testrunner_plugins")
            else "pytest_plugins"
        )
        if (
            (hasattr(mod, "testrunner_plugins") or hasattr(mod, "pytest_plugins"))
            and self._pluginmanager._configured
            and not self._using_pyargs
        ):
            msg = (
                f"Defining '{plugin_spec_name}' in a non-top-level conftest is no longer supported:\n"
                "It affects the entire test suite instead of just below the conftest as expected.\n"
                "  {}\n"
                "Please move it to a top level conftest file at the rootdir:\n"
                "  {}\n"
                "For more information, visit:\n"
                "  https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#testrunner-plugins-in-non-top-level-conftest-files"
            )
            fail(msg.format(conftestpath, self._confcutdir), pytrace=False)
