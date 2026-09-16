"""Bridges for pytest protocol hooks used by third-party plugins."""

from __future__ import annotations

from typing import Any

from _testrunner.config import hookimpl


class PytestCompatibilityPlugin:
    """Expose canonical TestRunner reports through pytest hook names."""

    config: Any | None = None

    @hookimpl(optionalhook=True)
    def pytest_report_to_serializable(self, config: Any, report: Any) -> Any:
        return config.hook.testrunner_report_to_serializable(
            config=config, report=report
        )

    @hookimpl(optionalhook=True)
    def pytest_report_from_serializable(self, config: Any, data: dict[str, Any]) -> Any:
        return config.hook.testrunner_report_from_serializable(config=config, data=data)

    @hookimpl(trylast=True)
    def pytest_runtest_makereport(self, item: Any, call: Any) -> Any:
        config = self.config
        if config is None:
            return None
        return config.hook.testrunner_runtest_makereport(item=item, call=call)

    @hookimpl
    def pytest_runtest_logstart(self, nodeid: str, location: Any) -> None:
        config = self.config
        if config is None:
            return
        config.hook.testrunner_runtest_logstart(nodeid=nodeid, location=location)

    @hookimpl
    def pytest_runtest_logreport(self, report: Any) -> None:
        config = self.config
        if config is None:
            return
        config.hook.testrunner_runtest_logreport(report=report)

    @hookimpl
    def pytest_runtest_logfinish(self, nodeid: str, location: Any) -> None:
        config = self.config
        if config is None:
            return
        config.hook.testrunner_runtest_logfinish(nodeid=nodeid, location=location)


class XdistCompatibilityPlugin:
    """Select the TestRunner-aware execnet worker bootstrap."""

    @hookimpl(tryfirst=True)
    def pytest_xdist_getremotemodule(self) -> Any:
        from _testrunner.compatibility.pytest import remote

        return remote
