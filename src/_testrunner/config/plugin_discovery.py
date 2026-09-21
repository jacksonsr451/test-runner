"""Plugin discovery and import orchestration."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Sequence
import importlib
import os
import sys
import types
from typing import Any

from _testrunner.outcomes import Skipped


class PluginDiscovery:
    """Coordinate plugin discovery without owning the Pluggy registry."""

    def __init__(
        self,
        pluginmanager: Any,
        essential_plugins: Sequence[str],
        builtin_plugins: set[str],
        get_plugin_specs_as_list: Callable[[Any], list[str]],
        is_missing_module: Callable[[ModuleNotFoundError, str], bool],
    ) -> None:
        self._pluginmanager = pluginmanager
        self._essential_plugins = essential_plugins
        self._builtin_plugins = builtin_plugins
        self._get_plugin_specs_as_list = get_plugin_specs_as_list
        self._is_missing_module = is_missing_module

    def consider_preparse(
        self, args: Sequence[str], *, exclude_only: bool = False
    ) -> None:
        i = 0
        n = len(args)
        while i < n:
            opt = args[i]
            i += 1
            if isinstance(opt, str):
                if opt == "-p":
                    try:
                        parg = args[i]
                    except IndexError:
                        return
                    i += 1
                elif opt.startswith("-p"):
                    parg = opt[2:]
                else:
                    continue
                parg = parg.strip()
                if exclude_only and not parg.startswith("no:"):
                    continue
                self._pluginmanager.consider_pluginarg(parg)

    def consider_pluginarg(self, arg: str) -> None:
        from _testrunner.config import UsageError

        if arg.startswith("no:"):
            name = arg[3:]
            if name in self._essential_plugins:
                raise UsageError(f"plugin {name} cannot be disabled")

            if name.endswith("conftest.py"):
                raise UsageError(
                    f"Blocking conftest files using -p is not supported: -p no:{name}\n"
                    "conftest.py files are not plugins and cannot be disabled via -p.\n"
                )

            if name == "cacheprovider":
                self._pluginmanager.set_blocked("stepwise")
                self._pluginmanager.set_blocked("testrunner_stepwise")

            self._pluginmanager.set_blocked(name)
            if not name.startswith("testrunner_"):
                self._pluginmanager.set_blocked("testrunner_" + name)
        else:
            name = arg
            self._pluginmanager.unblock(name)
            if not name.startswith("testrunner_"):
                self._pluginmanager.unblock("testrunner_" + name)
            self._pluginmanager.import_plugin(arg, consider_entry_points=True)

    def consider_conftest(
        self, conftestmodule: types.ModuleType, registration_name: str
    ) -> None:
        self._pluginmanager.register(conftestmodule, name=registration_name)

    def consider_env(self) -> None:
        self._import_plugin_specs(os.environ.get("TESTRUNNER_PLUGINS"))
        self._import_plugin_specs(os.environ.get("PYTEST_PLUGINS"))

    def consider_module(self, mod: types.ModuleType) -> None:
        self._import_plugin_specs(getattr(mod, "testrunner_plugins", []))
        self._import_plugin_specs(getattr(mod, "pytest_plugins", []))

    def _import_plugin_specs(
        self, spec: types.ModuleType | str | Sequence[str] | None
    ) -> None:
        plugins = self._get_plugin_specs_as_list(spec)
        for import_spec in plugins:
            self._pluginmanager.import_plugin(import_spec, consider_entry_points=True)

    def import_plugin(self, modname: str, consider_entry_points: bool = False) -> None:
        from _testrunner.config import PluginImportFailure
        from _testrunner.config import UsageError

        assert isinstance(modname, str), (
            f"module name as text required, got {modname!r}"
        )
        if (
            self._pluginmanager.is_blocked(modname)
            or self._pluginmanager.get_plugin(modname) is not None
        ):
            return

        importspec = (
            "_testrunner." + modname if modname in self._builtin_plugins else modname
        )
        self._pluginmanager.rewrite_hook.mark_rewrite(importspec)

        if consider_entry_points:
            loaded = self._pluginmanager.load_setuptools_entrypoints(
                "testrunner11", name=modname
            )
            loaded += self._pluginmanager.load_setuptools_entrypoints(
                "pytest11", name=modname
            )
            if loaded:
                return

        try:
            if sys.version_info >= (3, 11):
                mod = importlib.import_module(importspec)
            else:
                __import__(importspec)
                mod = sys.modules[importspec]
        except Skipped as e:
            self._pluginmanager.skipped_plugins.append((modname, e.msg or ""))
        except ModuleNotFoundError as e:
            if self._is_missing_module(e, importspec):
                raise UsageError(f'Error importing plugin "{modname}": {e}') from e
            raise PluginImportFailure(modname) from e
        except UsageError:
            raise
        except Exception as e:
            raise PluginImportFailure(modname) from e
        else:
            self._pluginmanager.register(mod, modname)
