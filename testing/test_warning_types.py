# mypy: allow-untyped-defs
from __future__ import annotations

import inspect

from _testrunner import warning_types
from _testrunner.testrunnerer import Testrunnerer
import testrunner


@testrunner.mark.parametrize(
    "warning_class",
    [
        w
        for n, w in vars(warning_types).items()
        if inspect.isclass(w) and issubclass(w, Warning)
    ],
)
def test_warning_types(warning_class: UserWarning) -> None:
    """Make sure all warnings declared in _testrunner.warning_types are displayed as coming
    from 'testrunner' instead of the internal module (#5452).
    """
    assert warning_class.__module__ == "testrunner"


@testrunner.mark.filterwarnings("error::testrunner.TestrunnerWarning")
def test_testrunner_warnings_repr_integration_test(testrunnerer: Testrunnerer) -> None:
    """Small integration test to ensure our small hack of setting the __module__ attribute
    of our warnings actually works (#5452).
    """
    testrunnerer.makepyfile(
        """
        import testrunner
        import warnings

        def test():
            warnings.warn(testrunner.TestrunnerWarning("some warning"))
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines(["E       testrunner.TestrunnerWarning: some warning"])


@testrunner.mark.filterwarnings("error")
def test_warn_explicit_for_annotates_errors_with_location():
    with testrunner.raises(Warning, match=r"(?m)test\n at .*raises.py:\d+"):
        warning_types.warn_explicit_for(
            testrunner.raises,  # type: ignore[arg-type]
            warning_types.TestrunnerWarning("test"),
        )
