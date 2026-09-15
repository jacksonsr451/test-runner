from __future__ import annotations

import dataclasses
import inspect
from types import FunctionType
from typing import Any
from typing import final
from typing import Generic
from typing import TypeVar
import warnings


class TestrunnerWarning(UserWarning):
    """Base class for all warnings emitted by testrunner."""

    __module__ = "testrunner"


@final
class TestrunnerAssertRewriteWarning(TestrunnerWarning):
    """Warning emitted by the testrunner assert rewrite module."""

    __module__ = "testrunner"


@final
class TestrunnerCacheWarning(TestrunnerWarning):
    """Warning emitted by the cache plugin in various situations."""

    __module__ = "testrunner"


@final
class TestrunnerConfigWarning(TestrunnerWarning):
    """Warning emitted for configuration issues."""

    __module__ = "testrunner"


@final
class TestrunnerCollectionWarning(TestrunnerWarning):
    """Warning emitted when testrunner is not able to collect a file or symbol in a module."""

    __module__ = "testrunner"


class TestrunnerDeprecationWarning(TestrunnerWarning, DeprecationWarning):
    """Warning class for features that will be removed in a future version."""

    __module__ = "testrunner"


class TestrunnerRemovedIn10Warning(TestrunnerDeprecationWarning):
    """Warning class for features that will be removed in testrunner 10."""

    __module__ = "testrunner"


@final
class TestrunnerExperimentalApiWarning(TestrunnerWarning, FutureWarning):
    """Warning category used to denote experiments in testrunner.

    Use sparingly as the API might change or even be removed completely in a
    future version.
    """

    __module__ = "testrunner"

    @classmethod
    def simple(cls, apiname: str) -> TestrunnerExperimentalApiWarning:
        return cls(f"{apiname} is an experimental api that may change over time")


@final
class TestrunnerReturnNotNoneWarning(TestrunnerWarning):
    """
    Warning emitted when a test function returns a value other than ``None``.

    See :ref:`return-not-none` for details.
    """

    __module__ = "testrunner"


@final
class TestrunnerUnknownMarkWarning(TestrunnerWarning):
    """Warning emitted on use of unknown markers.

    See :ref:`mark` for details.
    """

    __module__ = "testrunner"


@final
class TestrunnerUnraisableExceptionWarning(TestrunnerWarning):
    """An unraisable exception was reported.

    Unraisable exceptions are exceptions raised in :meth:`__del__ <object.__del__>`
    implementations and similar situations when the exception cannot be raised
    as normal.
    """

    __module__ = "testrunner"


@final
class TestrunnerUnhandledThreadExceptionWarning(TestrunnerWarning):
    """An unhandled exception occurred in a :class:`~threading.Thread`.

    Such exceptions don't propagate normally.
    """

    __module__ = "testrunner"


_W = TypeVar("_W", bound=TestrunnerWarning)


@final
@dataclasses.dataclass
class UnformattedWarning(Generic[_W]):
    """A warning meant to be formatted during runtime.

    This is used to hold warnings that need to format their message at runtime,
    as opposed to a direct message.
    """

    category: type[_W]
    template: str

    def format(self, **kwargs: Any) -> _W:
        """Return an instance of the warning category, formatted with given kwargs."""
        return self.category(self.template.format(**kwargs))


@final
class TestrunnerApproxDecimalToleranceWarning(TestrunnerWarning):
    """Warning emitted when :func:`testrunner.approx` is given a float tolerance
    for a :class:`~decimal.Decimal` comparison."""

    __module__ = "testrunner"


@final
class TestrunnerFDWarning(TestrunnerWarning):
    """When the lsof plugin finds leaked fds."""

    __module__ = "testrunner"


def warn_explicit_for(method: FunctionType, message: TestrunnerWarning) -> None:
    """
    Issue the warning :param:`message` for the definition of the given :param:`method`

    this helps to log warnings for functions defined prior to finding an issue with them
    (like hook wrappers being marked in a legacy mechanism)
    """
    lineno = method.__code__.co_firstlineno
    filename = inspect.getfile(method)
    module = method.__module__
    mod_globals = method.__globals__
    try:
        warnings.warn_explicit(
            message,
            type(message),
            filename=filename,
            module=module,
            registry=mod_globals.setdefault("__warningregistry__", {}),
            lineno=lineno,
        )
    except Warning as w:
        # If warnings are errors (e.g. -Werror), location information gets lost, so we add it to the message.
        raise type(w)(f"{w}\n at {filename}:{lineno}") from None
