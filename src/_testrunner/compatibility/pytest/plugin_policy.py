"""Policy for adapting pytest plugins to the TestRunner hook protocol."""

from __future__ import annotations

from collections.abc import Callable
import inspect
from types import FunctionType
from typing import Any
from typing import cast

from pluggy import HookimplOpts
from pluggy import HookspecOpts

from _testrunner import deprecated
from _testrunner.warning_types import warn_explicit_for


def _get_legacy_hook_marks(
    method: Any,
    hook_type: str,
    opt_names: tuple[str, ...],
) -> dict[str, bool]:
    known_marks: set[str] = {m.name for m in getattr(method, "_testrunner_mark", [])}
    must_warn: list[str] = []
    opts: dict[str, bool] = {}
    for opt_name in opt_names:
        opt_attr = getattr(method, opt_name, AttributeError)
        if opt_attr is not AttributeError:
            must_warn.append(f"{opt_name}={opt_attr}")
            opts[opt_name] = True
        elif opt_name in known_marks:
            must_warn.append(f"{opt_name}=True")
            opts[opt_name] = True
        else:
            opts[opt_name] = False
    if must_warn:
        hook_opts = ", ".join(must_warn)
        message = deprecated.HOOK_LEGACY_MARKING.format(
            type=hook_type,
            fullname=method.__qualname__,
            hook_opts=hook_opts,
        )
        warn_explicit_for(cast(FunctionType, method), message)
    return opts


class PluginCompatibilityPolicy:
    """Decide how pytest-prefixed plugins participate in TestRunner hooks."""

    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def parse_hookimpl_opts(
        self,
        plugin: object,
        name: str,
        parse_default: Callable[[Any, str], HookimplOpts | None],
    ) -> HookimplOpts | None:
        is_testrunner_hook = name.startswith("testrunner_")
        is_pytest_hook = name.startswith("pytest_")
        if not (is_testrunner_hook or is_pytest_hook):
            return None
        if name in {"testrunner_plugins", "pytest_plugins"}:
            return None

        method = getattr(plugin, name)
        if not inspect.isroutine(method):
            return None

        marker = "testrunner_impl" if is_testrunner_hook else "pytest_impl"
        opts = getattr(method, marker, None)
        if opts is None and is_pytest_hook:
            # ``hookimpl`` is the public TestRunner marker and stores its options
            # under ``testrunner_impl`` for pytest-prefixed compatibility hooks.
            opts = getattr(method, "testrunner_impl", None)
        if opts is None and is_testrunner_hook:
            opts = getattr(method, "pytest_impl", None)
        if opts is not None:
            return cast(HookimplOpts, opts)

        # TestRunner hooks are always prefixed with ``testrunner_``, so avoid
        # accessing possibly non-readable attributes for pytest compatibility.
        opts = parse_default(plugin, name) if is_testrunner_hook else None
        if opts is not None:
            return opts

        legacy = _get_legacy_hook_marks(
            method, "impl", ("tryfirst", "trylast", "optionalhook", "hookwrapper")
        )
        return cast(HookimplOpts, legacy)

    def parse_hookspec_opts(
        self,
        module_or_class: object,
        name: str,
        parse_default: Callable[[Any, str], HookspecOpts | None],
    ) -> HookspecOpts | None:
        opts = parse_default(module_or_class, name)
        if opts is None:
            method = getattr(module_or_class, name)
            opts = getattr(method, "pytest_spec", None)
        if opts is None:
            method = getattr(module_or_class, name)
            if name.startswith(("testrunner_", "pytest_")):
                legacy = _get_legacy_hook_marks(
                    method, "spec", ("firstresult", "historic")
                )
                opts = cast(HookspecOpts, legacy)
        return opts

    def add_pytest_hook_aliases(self, plugin: object) -> None:
        """Prepare pytest hooks to participate in the internal hook calls."""
        for name in dir(plugin):
            if not name.startswith("pytest_") or name == "pytest_plugins":
                continue
            testrunner_name = "testrunner_" + name.removeprefix("pytest_")
            if not hasattr(self._manager.hook, testrunner_name) or hasattr(
                plugin, testrunner_name
            ):
                continue
            try:
                setattr(plugin, testrunner_name, getattr(plugin, name))
            except (AttributeError, TypeError):
                continue
