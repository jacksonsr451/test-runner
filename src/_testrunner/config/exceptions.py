from __future__ import annotations

from typing import final


@final
class UsageError(Exception):
    """Error in testrunner usage or invocation."""

    __module__ = "testrunner"


class PrintHelp(Exception):
    """Raised when testrunner should print its help to skip the rest of the
    argument parsing and validation."""
