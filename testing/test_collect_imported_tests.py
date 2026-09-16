"""Tests for the `collect_imported_tests` configuration value."""

from __future__ import annotations

import textwrap

from _testrunner.testrunnerer import Testrunnerer
import testrunner


def setup_files(testrunnerer: Testrunnerer) -> None:
    src_dir = testrunnerer.mkdir("src")
    tests_dir = testrunnerer.mkdir("tests")
    src_file = src_dir / "foo.py"

    src_file.write_text(
        textwrap.dedent("""\
            class Testament:
                def test_collections(self):
                    pass

            def test_testament(): pass
        """),
        encoding="utf-8",
    )

    test_file = tests_dir / "foo_test.py"
    test_file.write_text(
        textwrap.dedent("""\
            from foo import Testament, test_testament

            class TestDomain:
                def test(self):
                    testament = Testament()
                    assert testament
        """),
        encoding="utf-8",
    )

    testrunnerer.syspathinsert(src_dir)


def test_collect_imports_disabled(testrunnerer: Testrunnerer) -> None:
    """
    When collect_imported_tests is disabled, only objects in the
    test modules are collected as tests, so the imported names (`Testament` and `test_testament`)
    are not collected.
    """
    testrunnerer.makeini(
        """
        [testrunner]
        collect_imported_tests = false
        """
    )

    setup_files(testrunnerer)
    result = testrunnerer.runtestrunner("-v", "tests")
    result.stdout.fnmatch_lines(
        [
            "tests/foo_test.py::TestDomain::test PASSED*",
        ]
    )

    # Ensure that the hooks were only called for the collected item.
    reprec = result.reprec  # type:ignore[attr-defined]
    reports = reprec.getreports("testrunner_collectreport")
    [modified] = reprec.getcalls("testrunner_collection_modifyitems")
    [item_collected] = reprec.getcalls("testrunner_itemcollected")

    assert [x.nodeid for x in reports] == [
        "",
        "tests/foo_test.py::TestDomain",
        "tests/foo_test.py",
        "tests",
    ]
    assert [x.nodeid for x in modified.items] == ["tests/foo_test.py::TestDomain::test"]
    assert item_collected.item.nodeid == "tests/foo_test.py::TestDomain::test"


@testrunner.mark.parametrize("configure_ini", [False, True])
def test_collect_imports_enabled(
    testrunnerer: Testrunnerer, configure_ini: bool
) -> None:
    """
    When collect_imported_tests is enabled (the default), all names in the
    test modules are collected as tests.
    """
    if configure_ini:
        testrunnerer.makeini(
            """
            [testrunner]
            collect_imported_tests = true
            """
        )

    setup_files(testrunnerer)
    result = testrunnerer.runtestrunner("-v", "tests")
    result.stdout.fnmatch_lines(
        [
            "tests/foo_test.py::Testament::test_collections PASSED*",
            "tests/foo_test.py::test_testament PASSED*",
            "tests/foo_test.py::TestDomain::test PASSED*",
        ]
    )
