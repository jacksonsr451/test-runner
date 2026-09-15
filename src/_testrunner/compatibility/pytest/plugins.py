"""Bridges for pytest protocol hooks used by third-party plugins."""

from __future__ import annotations

from typing import Any

from _testrunner.config import hookimpl


class PytestCompatibilityPlugin:
    """Expose canonical TestRunner reports through pytest hook names."""

    @hookimpl
    def pytest_report_to_serializable(self, config: Any, report: Any) -> Any:
        return config.hook.testrunner_report_to_serializable(
            config=config, report=report
        )

    @hookimpl
    def pytest_report_from_serializable(self, config: Any, data: dict[str, Any]) -> Any:
        return config.hook.testrunner_report_from_serializable(
            config=config, data=data
        )


class XdistCompatibilityPlugin:
    """Select the TestRunner-aware execnet worker bootstrap."""

    @hookimpl(tryfirst=True)
    def pytest_xdist_getremotemodule(self) -> Any:
        from _testrunner.compatibility.pytest import remote

        return remote
