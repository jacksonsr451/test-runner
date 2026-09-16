# mypy: allow-untyped-defs
from __future__ import annotations

import importlib.metadata
import json
import types

import execnet

from _testrunner.compatibility.pytest.remote import _replace_once
from _testrunner.config import TestrunnerPluginManager
from _testrunner.reports import TestReport
from _testrunner.testrunnerer import Testrunnerer
import testrunner


@testrunner.fixture
def testrunnerpm() -> TestrunnerPluginManager:
    return TestrunnerPluginManager()


def test_builtin_compatibility_plugins_are_discovered(testrunnerpm) -> None:
    assert testrunnerpm.get_plugin("_testrunner_pytest_compat") is not None


def test_xdist_compatibility_plugin_is_discovered_after_xdist_hookspec(
    testrunnerpm,
) -> None:
    import xdist.newhooks

    testrunnerpm.add_hookspecs(xdist.newhooks)
    assert testrunnerpm.get_plugin("_testrunner_xdist_compat") is not None


def test_compatibility_plugin_is_not_registered_twice(testrunnerpm) -> None:
    plugin = testrunnerpm.get_plugin("_testrunner_pytest_compat")
    assert plugin is not None
    assert testrunnerpm.register(plugin, "another-name") == "_testrunner_pytest_compat"
    assert [p for p in testrunnerpm.get_plugins() if p is plugin] == [plugin]


def test_plugin_found_by_both_entry_point_protocols_is_registered_once(
    testrunnerpm, monkeypatch
) -> None:
    plugin = types.ModuleType("shared_plugin")

    class EntryPoint:
        def __init__(self, group):
            self.group = group
            self.name = "shared-plugin"

        def load(self):
            return plugin

    class Distribution:
        version = "1.0"
        files = ()
        metadata = {"name": "shared-plugin"}
        entry_points = (EntryPoint("testrunner11"), EntryPoint("pytest11"))

    monkeypatch.setattr(importlib.metadata, "distributions", lambda: (Distribution(),))
    testrunnerpm.import_plugin("shared-plugin", consider_entry_points=True)
    assert [p for p in testrunnerpm.get_plugins() if p is plugin] == [plugin]


def test_explicit_pytest_plugin_load_does_not_duplicate(
    testrunnerer: Testrunnerer,
) -> None:
    config = testrunnerer.parseconfigure()
    plugin = config.pluginmanager.get_plugin("_testrunner_pytest_compat")
    assert plugin is not None
    config.pluginmanager.import_plugin("_testrunner.compatibility.pytest")
    assert [p for p in config.pluginmanager.get_plugins() if p is plugin] == [plugin]


def test_explicit_testrunner_plugin_load_does_not_duplicate(
    testrunnerer: Testrunnerer,
) -> None:
    config = testrunnerer.parseconfigure()
    plugin = config.pluginmanager.get_plugin("_testrunner_pytest_compat")
    assert plugin is not None
    config.pluginmanager.import_plugin("_testrunner.compatibility.pytest")
    assert [p for p in config.pluginmanager.get_plugins() if p is plugin] == [plugin]


def test_pytest_logreport_bridges_to_canonical_hook(
    testrunnerer: Testrunnerer, monkeypatch
) -> None:
    config = testrunnerer.parseconfigure()
    seen = []
    report = TestReport(
        "test.py::test_ok", ("test.py", 1, "test_ok"), {}, "passed", None, "call"
    )

    def forward(report):
        seen.append(report)

    monkeypatch.setattr(config.hook, "testrunner_runtest_logreport", forward)
    config.hook.pytest_runtest_logreport(report=report)
    assert seen == [report]


def test_bridge_does_not_recurse(testrunnerer: Testrunnerer, monkeypatch) -> None:
    config = testrunnerer.parseconfigure()
    compatibility = config.pluginmanager.get_plugin("_testrunner_pytest_compat")
    assert compatibility is not None
    calls = []

    def forward(report):
        calls.append(report)

    monkeypatch.setattr(config.hook, "testrunner_runtest_logreport", forward)
    report = TestReport(
        "test.py::test_ok", ("test.py", 1, "test_ok"), {}, "passed", None, "call"
    )
    config.hook.pytest_runtest_logreport(report=report)
    assert len(calls) == 1
    assert not hasattr(compatibility, "testrunner_runtest_logreport")


def test_report_bridge_preserves_firstresult(testrunnerer: Testrunnerer) -> None:
    config = testrunnerer.parseconfigure()
    marker = object()
    called = []

    class First:
        @testrunner.hookimpl(tryfirst=True)
        def testrunner_report_to_serializable(self, config, report):
            return marker

    class Second:
        @testrunner.hookimpl
        def testrunner_report_to_serializable(self, config, report):
            called.append(True)
            return object()

    config.pluginmanager.register(First())
    config.pluginmanager.register(Second())
    assert (
        config.hook.pytest_report_to_serializable(config=config, report=object())
        is marker
    )
    assert called == []


def test_pytest_logreport_is_forwarded(testrunnerer: Testrunnerer, monkeypatch) -> None:
    config = testrunnerer.parseconfigure()
    report = TestReport(
        "test.py::test_ok", ("test.py", 1, "test_ok"), {}, "passed", None, "call"
    )
    seen = []

    def forward(report):
        seen.append(report)

    monkeypatch.setattr(config.hook, "testrunner_runtest_logreport", forward)
    config.hook.pytest_runtest_logreport(report=report)
    assert seen == [report]


def test_report_round_trip_uses_transport_safe_structures(
    testrunnerer: Testrunnerer,
) -> None:
    config = testrunnerer.parseconfigure()
    report = TestReport(
        "tests/test_sample.py::test_ok",
        ("tests/test_sample.py", 11, "test_ok"),
        {"test_ok": 1},
        "passed",
        None,
        "call",
        sections=[("stdout", "hello")],
        duration=0.25,
        user_properties=[("key", "value")],
    )
    data = config.hook.testrunner_report_to_serializable(config=config, report=report)
    assert data is not None
    json.dumps(data)
    execnet.dumps(data)
    restored = config.hook.testrunner_report_from_serializable(config=config, data=data)
    assert isinstance(restored, TestReport)
    assert restored.nodeid == report.nodeid
    assert restored.location == report.location
    assert restored.outcome == report.outcome
    assert restored.when == report.when
    assert restored.sections == report.sections
    assert restored.user_properties == report.user_properties
    assert restored.duration == report.duration


def test_source_transform_fails_if_xdist_shape_changes() -> None:
    with testrunner.raises(RuntimeError, match="expected one"):
        _replace_once("changed", "expected", "replacement")


@testrunner.mark.parametrize("workers", [1, 2])
def test_xdist_workers_execute_tests(testrunnerer: Testrunnerer, workers: int) -> None:
    testrunner.importorskip("xdist")
    testrunnerer.makepyfile(
        """
        import testrunner

        values = [1, 2]

        @testrunner.fixture
        def value():
            return 10

        @testrunner.mark.parametrize("item", values)
        def test_distributed(value, item):
            assert value + item > 0
        """
    )
    result = testrunnerer.runtestrunner(f"-n{workers}", "-pxdist.plugin")
    result.assert_outcomes(passed=2)


def test_xdist_failure_report_and_junit_xml(testrunnerer: Testrunnerer) -> None:
    testrunner.importorskip("xdist")
    testrunnerer.makepyfile(
        """
        def test_failure():
            assert False
        """
    )
    xml = testrunnerer.path / "reports.xml"
    result = testrunnerer.runtestrunner("-n2", "-pxdist.plugin", "--junitxml", str(xml))
    result.assert_outcomes(failed=1)
    assert xml.is_file()


def test_different_plugins_are_not_deduplicated(testrunnerpm) -> None:
    first = types.ModuleType("same_module")
    second = types.ModuleType("same_module")
    assert testrunnerpm.register(first, "same") == "same"
    assert testrunnerpm.register(second, "other") == "other"
    assert testrunnerpm.get_plugin("same") is first
    assert testrunnerpm.get_plugin("other") is second


def test_same_plugin_with_different_names_is_deduplicated(testrunnerpm) -> None:
    plugin = object()
    assert testrunnerpm.register(plugin, "first") == "first"
    assert testrunnerpm.register(plugin, "second") == "first"
