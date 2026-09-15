# mypy: allow-untyped-defs
from __future__ import annotations

from collections.abc import Sequence

from _testrunner._code.code import ExceptionChainRepr
from _testrunner._code.code import ExceptionRepr
from _testrunner.approx import approx
from _testrunner.config import Config
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.reports import CollectReport
from _testrunner.reports import TestReport
import testrunner


class TestReportSerialization:
    def test_xdist_longrepr_to_str_issue_241(self, testrunnerer: Testrunnerer) -> None:
        """Regarding issue testrunner-xdist#241.

        This test came originally from test_remote.py in xdist (ca03269).
        """
        testrunnerer.makepyfile(
            """
            def test_a(): assert False
            def test_b(): pass
        """
        )
        reprec = testrunnerer.inline_run()
        reports = reprec.getreports("testrunner_runtest_logreport")
        assert len(reports) == 6
        test_a_call = reports[1]
        assert test_a_call.when == "call"
        assert test_a_call.outcome == "failed"
        assert test_a_call._to_json()["longrepr"]["reprtraceback"]["style"] == "long"
        test_b_call = reports[4]
        assert test_b_call.when == "call"
        assert test_b_call.outcome == "passed"
        assert test_b_call._to_json()["longrepr"] is None

    def test_xdist_report_longrepr_reprcrash_130(self, testrunnerer: Testrunnerer) -> None:
        """Regarding issue testrunner-xdist#130

        This test came originally from test_remote.py in xdist (ca03269).
        """
        reprec = testrunnerer.inline_runsource(
            """
                    def test_fail():
                        assert False, 'Expected Message'
                """
        )
        reports = reprec.getreports("testrunner_runtest_logreport")
        assert len(reports) == 3
        rep = reports[1]
        added_section = ("Failure Metadata", "metadata metadata", "*")
        assert isinstance(rep.longrepr, ExceptionRepr)
        rep.longrepr.sections.append(added_section)
        d = rep._to_json()
        a = TestReport._from_json(d)
        assert isinstance(a.longrepr, ExceptionRepr)
        # Check assembled == rep
        assert a.__dict__.keys() == rep.__dict__.keys()
        for key in rep.__dict__:
            if key == "longrepr":
                continue
            if key == "_id":
                # _from_json() reconstructs a NodeId via NodeId.parse() from
                # the plain nodeid string on the wire; compare by string form
                # to be independent of any cached state on the instance.
                assert str(a._id) == str(rep._id)
                continue
            assert getattr(a, key) == getattr(rep, key)
        assert rep.longrepr.reprcrash is not None
        assert a.longrepr.reprcrash is not None
        assert rep.longrepr.reprcrash.lineno == a.longrepr.reprcrash.lineno
        assert rep.longrepr.reprcrash.message == a.longrepr.reprcrash.message
        assert rep.longrepr.reprcrash.path == a.longrepr.reprcrash.path
        assert rep.longrepr.reprtraceback.entrysep == a.longrepr.reprtraceback.entrysep
        assert (
            rep.longrepr.reprtraceback.extraline == a.longrepr.reprtraceback.extraline
        )
        assert rep.longrepr.reprtraceback.style == a.longrepr.reprtraceback.style
        assert rep.longrepr.sections == a.longrepr.sections
        # Missing section attribute PR171
        assert added_section in a.longrepr.sections

    def test_to_json_nodeid_wire_shape(self, testrunnerer: Testrunnerer) -> None:
        """The JSON wire payload must keep a plain top-level string "nodeid"
        key (never an internal NodeId object / "_id" key) -- testrunner-xdist
        depends on this exact shape to serialize reports across processes.
        """
        reprec = testrunnerer.inline_runsource("def test_a(): pass")
        reports = reprec.getreports("testrunner_runtest_logreport")
        rep = reports[1]
        assert rep.when == "call"
        d = rep._to_json()
        assert d["nodeid"] == "test_to_json_nodeid_wire_shape.py::test_a"
        assert d["nodeid"] == rep.nodeid
        assert "_id" not in d

    def test_reprentries_serialization_170(self, testrunnerer: Testrunnerer) -> None:
        """Regarding issue testrunner-xdist#170

        This test came originally from test_remote.py in xdist (ca03269).
        """
        from _testrunner._code.code import ReprEntry

        reprec = testrunnerer.inline_runsource(
            """
                            def test_repr_entry():
                                x = 0
                                assert x
                        """,
            "--showlocals",
        )
        reports = reprec.getreports("testrunner_runtest_logreport")
        assert len(reports) == 3
        rep = reports[1]
        assert isinstance(rep.longrepr, ExceptionRepr)
        d = rep._to_json()
        a = TestReport._from_json(d)
        assert isinstance(a.longrepr, ExceptionRepr)

        rep_entries = rep.longrepr.reprtraceback.reprentries
        a_entries = a.longrepr.reprtraceback.reprentries
        for a_entry, rep_entry in zip(a_entries, rep_entries, strict=True):
            assert isinstance(rep_entry, ReprEntry)
            assert rep_entry.reprfileloc is not None
            assert rep_entry.reprfuncargs is not None
            assert rep_entry.reprlocals is not None

            assert isinstance(a_entry, ReprEntry)
            assert a_entry.reprfileloc is not None
            assert a_entry.reprfuncargs is not None
            assert a_entry.reprlocals is not None

            assert rep_entry.lines == a_entry.lines
            assert rep_entry.reprfileloc.lineno == a_entry.reprfileloc.lineno
            assert rep_entry.reprfileloc.message == a_entry.reprfileloc.message
            assert rep_entry.reprfileloc.path == a_entry.reprfileloc.path
            assert rep_entry.reprfuncargs.args == a_entry.reprfuncargs.args
            assert rep_entry.reprlocals.lines == a_entry.reprlocals.lines
            assert rep_entry.style == a_entry.style

    def test_reprentries_serialization_196(self, testrunnerer: Testrunnerer) -> None:
        """Regarding issue testrunner-xdist#196

        This test came originally from test_remote.py in xdist (ca03269).
        """
        from _testrunner._code.code import ReprEntryNative

        reprec = testrunnerer.inline_runsource(
            """
                            def test_repr_entry_native():
                                x = 0
                                assert x
                        """,
            "--tb=native",
        )
        reports = reprec.getreports("testrunner_runtest_logreport")
        assert len(reports) == 3
        rep = reports[1]
        assert isinstance(rep.longrepr, ExceptionRepr)
        d = rep._to_json()
        a = TestReport._from_json(d)
        assert isinstance(a.longrepr, ExceptionRepr)

        rep_entries = rep.longrepr.reprtraceback.reprentries
        a_entries = a.longrepr.reprtraceback.reprentries
        for rep_entry, a_entry in zip(rep_entries, a_entries, strict=True):
            assert isinstance(rep_entry, ReprEntryNative)
            assert rep_entry.lines == a_entry.lines

    def test_itemreport_outcomes(self, testrunnerer: Testrunnerer) -> None:
        # This test came originally from test_remote.py in xdist (ca03269).
        reprec = testrunnerer.inline_runsource(
            """
            import testrunner
            def test_pass(): pass
            def test_fail(): 0/0
            @testrunner.mark.skipif("True")
            def test_skip(): pass
            def test_skip_imperative():
                testrunner.skip("hello")
            @testrunner.mark.xfail("True")
            def test_xfail(): 0/0
            def test_xfail_imperative():
                testrunner.xfail("hello")
        """
        )
        reports = reprec.getreports("testrunner_runtest_logreport")
        assert len(reports) == 17  # with setup/teardown "passed" reports
        for rep in reports:
            d = rep._to_json()
            newrep = TestReport._from_json(d)
            assert newrep.passed == rep.passed
            assert newrep.failed == rep.failed
            assert newrep.skipped == rep.skipped
            if newrep.skipped and not hasattr(newrep, "wasxfail"):
                assert isinstance(newrep.longrepr, tuple)
                assert len(newrep.longrepr) == 3
            assert newrep.outcome == rep.outcome
            assert newrep.when == rep.when
            assert newrep.keywords == rep.keywords
            if rep.failed:
                assert newrep.longreprtext == rep.longreprtext

    def test_collectreport_passed(self, testrunnerer: Testrunnerer) -> None:
        """This test came originally from test_remote.py in xdist (ca03269)."""
        reprec = testrunnerer.inline_runsource("def test_func(): pass")
        reports = reprec.getreports("testrunner_collectreport")
        for rep in reports:
            d = rep._to_json()
            newrep = CollectReport._from_json(d)
            assert newrep.passed == rep.passed
            assert newrep.failed == rep.failed
            assert newrep.skipped == rep.skipped

    def test_collectreport_fail(self, testrunnerer: Testrunnerer) -> None:
        """This test came originally from test_remote.py in xdist (ca03269)."""
        reprec = testrunnerer.inline_runsource("qwe abc")
        reports = reprec.getreports("testrunner_collectreport")
        assert reports
        for rep in reports:
            d = rep._to_json()
            newrep = CollectReport._from_json(d)
            assert newrep.passed == rep.passed
            assert newrep.failed == rep.failed
            assert newrep.skipped == rep.skipped
            if rep.failed:
                assert newrep.longrepr == str(rep.longrepr)

    def test_extended_report_deserialization(self, testrunnerer: Testrunnerer) -> None:
        """This test came originally from test_remote.py in xdist (ca03269)."""
        reprec = testrunnerer.inline_runsource("qwe abc")
        reports = reprec.getreports("testrunner_collectreport")
        assert reports
        for rep in reports:
            rep.extra = True  # type: ignore[attr-defined]
            d = rep._to_json()
            newrep = CollectReport._from_json(d)
            assert newrep.extra
            assert newrep.passed == rep.passed
            assert newrep.failed == rep.failed
            assert newrep.skipped == rep.skipped
            if rep.failed:
                assert newrep.longrepr == str(rep.longrepr)

    def test_paths_support(self, testrunnerer: Testrunnerer) -> None:
        """Report attributes which are path-like should become strings."""
        testrunnerer.makepyfile(
            """
            def test_a():
                assert False
        """
        )

        class MyPathLike:
            def __init__(self, path: str) -> None:
                self.path = path

            def __fspath__(self) -> str:
                return self.path

        reprec = testrunnerer.inline_run()
        reports = reprec.getreports("testrunner_runtest_logreport")
        assert len(reports) == 3
        test_a_call = reports[1]
        test_a_call.path1 = MyPathLike(str(testrunnerer.path))  # type: ignore[attr-defined]
        test_a_call.path2 = testrunnerer.path  # type: ignore[attr-defined]
        data = test_a_call._to_json()
        assert data["path1"] == str(testrunnerer.path)
        assert data["path2"] == str(testrunnerer.path)

    def test_deserialization_failure(self, testrunnerer: Testrunnerer) -> None:
        """Check handling of failure during deserialization of report types."""
        testrunnerer.makepyfile(
            """
            def test_a():
                assert False
        """
        )
        reprec = testrunnerer.inline_run()
        reports = reprec.getreports("testrunner_runtest_logreport")
        assert len(reports) == 3
        test_a_call = reports[1]
        data = test_a_call._to_json()
        entry = data["longrepr"]["reprtraceback"]["reprentries"][0]
        assert entry["type"] == "ReprEntry"

        entry["type"] = "Unknown"
        with testrunner.raises(
            RuntimeError, match="INTERNALERROR: Unknown entry type returned: Unknown"
        ):
            TestReport._from_json(data)

    @testrunner.mark.parametrize("report_class", [TestReport, CollectReport])
    def test_chained_exceptions(
        self, testrunnerer: Testrunnerer, tw_mock, report_class
    ) -> None:
        """Check serialization/deserialization of report objects containing chained exceptions (#5786)"""
        testrunnerer.makepyfile(
            f"""
            def foo():
                raise ValueError('value error')
            def test_a():
                try:
                    foo()
                except ValueError as e:
                    raise RuntimeError('runtime error') from e
            if {report_class is CollectReport}:
                test_a()
        """
        )

        reprec = testrunnerer.inline_run()
        if report_class is TestReport:
            reports: Sequence[TestReport] | Sequence[CollectReport] = reprec.getreports(
                "testrunner_runtest_logreport"
            )
            # we have 3 reports: setup/call/teardown
            assert len(reports) == 3
            # get the call report
            report = reports[1]
        else:
            assert report_class is CollectReport
            # three collection reports: session, test file, directory
            reports = reprec.getreports("testrunner_collectreport")
            assert len(reports) == 3
            report = reports[1]

        def check_longrepr(longrepr: ExceptionChainRepr) -> None:
            """Check the attributes of the given longrepr object according to the test file.

            We can get away with testing both CollectReport and TestReport with this function because
            the longrepr objects are very similar.
            """
            assert isinstance(longrepr, ExceptionChainRepr)
            assert longrepr.sections == [("title", "contents", "=")]
            assert len(longrepr.chain) == 2
            entry1, entry2 = longrepr.chain
            tb1, _fileloc1, desc1 = entry1
            tb2, _fileloc2, desc2 = entry2

            assert "ValueError('value error')" in str(tb1)
            assert "RuntimeError('runtime error')" in str(tb2)

            assert (
                desc1
                == "The above exception was the direct cause of the following exception:"
            )
            assert desc2 is None

        assert report.failed
        assert len(report.sections) == 0
        assert isinstance(report.longrepr, ExceptionChainRepr)
        report.longrepr.addsection("title", "contents", "=")
        check_longrepr(report.longrepr)

        data = report._to_json()
        loaded_report = report_class._from_json(data)

        assert loaded_report.failed
        check_longrepr(loaded_report.longrepr)

        # make sure we don't blow up on ``toterminal`` call; we don't test the actual output because it is very
        # brittle and hard to maintain, but we can assume it is correct because ``toterminal`` is already tested
        # elsewhere and we do check the contents of the longrepr object after loading it.
        loaded_report.longrepr.toterminal(tw_mock)

    def test_chained_exceptions_no_reprcrash(self, testrunnerer: Testrunnerer, tw_mock) -> None:
        """Regression test for tracebacks without a reprcrash (#5971)

        This happens notably on exceptions raised by multiprocess.pool: the exception transfer
        from subprocess to main process creates an artificial exception, which ExceptionInfo
        can't obtain the ReprFileLocation from.
        """
        testrunnerer.makepyfile(
            """
            from concurrent.futures import ProcessPoolExecutor

            def func():
                raise ValueError('value error')

            def test_a():
                with ProcessPoolExecutor() as p:
                    p.submit(func).result()
        """
        )

        testrunnerer.syspathinsert()
        reprec = testrunnerer.inline_run()

        reports = reprec.getreports("testrunner_runtest_logreport")

        def check_longrepr(longrepr: object) -> None:
            assert isinstance(longrepr, ExceptionChainRepr)
            assert len(longrepr.chain) == 2
            entry1, entry2 = longrepr.chain
            tb1, fileloc1, _desc1 = entry1
            tb2, fileloc2, _desc2 = entry2

            assert "RemoteTraceback" in str(tb1)
            assert "ValueError: value error" in str(tb2)

            assert fileloc1 is None
            assert fileloc2 is not None
            assert fileloc2.message == "ValueError: value error"

        # 3 reports: setup/call/teardown: get the call report
        assert len(reports) == 3
        report = reports[1]

        assert report.failed
        check_longrepr(report.longrepr)

        data = report._to_json()
        loaded_report = TestReport._from_json(data)

        assert loaded_report.failed
        check_longrepr(loaded_report.longrepr)

        # for same reasons as previous test, ensure we don't blow up here
        assert loaded_report.longrepr is not None
        assert isinstance(loaded_report.longrepr, ExceptionChainRepr)
        loaded_report.longrepr.toterminal(tw_mock)

    def test_report_prevent_ConftestImportFailure_hiding_exception(
        self, testrunnerer: Testrunnerer
    ) -> None:
        sub_dir = testrunnerer.path.joinpath("ns")
        sub_dir.mkdir()
        sub_dir.joinpath("conftest.py").write_text("import unknown", encoding="utf-8")

        result = testrunnerer.runtestrunner_subprocess(".")
        result.stdout.fnmatch_lines(["E   *Error: No module named 'unknown'"])
        result.stdout.no_fnmatch_line("ERROR  - *ConftestImportFailure*")

    def test_report_timestamps_match_duration(self, testrunnerer: Testrunnerer, mock_timing):
        reprec = testrunnerer.inline_runsource(
            """
            import testrunner
            from _testrunner import timing
            @testrunner.fixture
            def fixture_():
                timing.sleep(5)
                yield
                timing.sleep(5)
            def test_1(fixture_): timing.sleep(10)
        """
        )
        reports = reprec.getreports("testrunner_runtest_logreport")
        assert len(reports) == 3
        for report in reports:
            data = report._to_json()
            loaded_report = TestReport._from_json(data)
            assert loaded_report.stop - loaded_report.start == approx(report.duration)

    @testrunner.mark.parametrize(
        "first_skip_reason, second_skip_reason, skip_reason_output",
        [("A", "B", "(A; B)"), ("A", "A", "(A)")],
    )
    def test_exception_group_with_only_skips(
        self,
        testrunnerer: Testrunnerer,
        first_skip_reason: str,
        second_skip_reason: str,
        skip_reason_output: str,
    ):
        """
        Test that when an ExceptionGroup with only Skipped exceptions is raised in teardown,
        it is reported as a single skipped test, not as an error.
        This is a regression test for issue #13537.
        """
        testrunnerer.makepyfile(
            test_it=f"""
            import testrunner
            @testrunner.fixture
            def fixA():
                yield
                testrunner.skip(reason="{first_skip_reason}")
            @testrunner.fixture
            def fixB():
                yield
                testrunner.skip(reason="{second_skip_reason}")
            def test_skip(fixA, fixB):
                assert True
            """
        )
        result = testrunnerer.runtestrunner("-v")
        result.assert_outcomes(passed=1, skipped=1)
        out = result.stdout.str()
        assert skip_reason_output in out
        assert "ERROR at teardown" not in out

    @testrunner.mark.parametrize(
        "use_item_location, skip_file_location",
        [(True, "test_it.py"), (False, "runner.py")],
    )
    def test_exception_group_skips_use_item_location(
        self, testrunnerer: Testrunnerer, use_item_location: bool, skip_file_location: str
    ):
        """
        Regression for #13537:
        If any skip inside an ExceptionGroup has _use_item_location=True,
        the report location should point to the test item, not the fixture teardown.
        """
        testrunnerer.makepyfile(
            test_it=f"""
            import testrunner
            @testrunner.fixture
            def fix_item1():
                yield
                exc = testrunner.skip.Exception("A")
                exc._use_item_location = True
                raise exc
            @testrunner.fixture
            def fix_item2():
                yield
                exc = testrunner.skip.Exception("B")
                exc._use_item_location = {use_item_location}
                raise exc
            def test_both(fix_item1, fix_item2):
                assert True
            """
        )
        result = testrunnerer.runtestrunner("-rs")
        result.assert_outcomes(passed=1, skipped=1)

        out = result.stdout.str()
        # Both reasons should appear
        assert "A" and "B" in out
        # Crucially, the skip should be attributed to the test item, not teardown
        assert skip_file_location in out


class TestHooks:
    """Test that the hooks are working correctly for plugins"""

    def test_test_report(self, testrunnerer: Testrunnerer, testrunnerconfig: Config) -> None:
        testrunnerer.makepyfile(
            """
            def test_a(): assert False
            def test_b(): pass
        """
        )
        reprec = testrunnerer.inline_run()
        reports = reprec.getreports("testrunner_runtest_logreport")
        assert len(reports) == 6
        for rep in reports:
            data = testrunnerconfig.hook.testrunner_report_to_serializable(
                config=testrunnerconfig, report=rep
            )
            assert data["$report_type"] == "TestReport"
            new_rep = testrunnerconfig.hook.testrunner_report_from_serializable(
                config=testrunnerconfig, data=data
            )
            assert new_rep.nodeid == rep.nodeid
            assert new_rep.when == rep.when
            assert new_rep.outcome == rep.outcome

    def test_collect_report(self, testrunnerer: Testrunnerer, testrunnerconfig: Config) -> None:
        testrunnerer.makepyfile(
            """
            def test_a(): assert False
            def test_b(): pass
        """
        )
        reprec = testrunnerer.inline_run()
        reports = reprec.getreports("testrunner_collectreport")
        assert len(reports) == 3
        for rep in reports:
            data = testrunnerconfig.hook.testrunner_report_to_serializable(
                config=testrunnerconfig, report=rep
            )
            assert data["$report_type"] == "CollectReport"
            new_rep = testrunnerconfig.hook.testrunner_report_from_serializable(
                config=testrunnerconfig, data=data
            )
            assert new_rep.nodeid == rep.nodeid
            assert new_rep.when == "collect"
            assert new_rep.outcome == rep.outcome

    @testrunner.mark.parametrize(
        "hook_name", ["testrunner_runtest_logreport", "testrunner_collectreport"]
    )
    def test_invalid_report_types(
        self, testrunnerer: Testrunnerer, testrunnerconfig: Config, hook_name: str
    ) -> None:
        testrunnerer.makepyfile(
            """
            def test_a(): pass
            """
        )
        reprec = testrunnerer.inline_run()
        reports = reprec.getreports(hook_name)
        assert reports
        rep = reports[0]
        data = testrunnerconfig.hook.testrunner_report_to_serializable(
            config=testrunnerconfig, report=rep
        )
        data["$report_type"] = "Unknown"
        with testrunner.raises(AssertionError):
            _ = testrunnerconfig.hook.testrunner_report_from_serializable(
                config=testrunnerconfig, data=data
            )
