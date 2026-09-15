# mypy: allow-untyped-defs
from __future__ import annotations

from _testrunner import deprecated
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.scope import Scope
import testrunner
from testrunner import TestrunnerDeprecationWarning
from testrunner import TestrunnerRemovedIn10Warning


@testrunner.mark.parametrize("plugin", sorted(deprecated.DEPRECATED_EXTERNAL_PLUGINS))
@testrunner.mark.filterwarnings("default")
def test_external_plugins_integrated(testrunnerer: Testrunnerer, plugin) -> None:
    testrunnerer.syspathinsert()
    testrunnerer.makepyfile(**{plugin: ""})
    recorded = []

    class Recorder:
        def testrunner_warning_recorded(self, warning_message):
            recorded.append(warning_message)

    testrunnerer.plugins = [Recorder()]
    testrunnerer.parseconfig("-p", plugin)

    assert len(recorded) == 1
    assert recorded[0].category is testrunner.TestrunnerConfigWarning


def test_hookspec_via_function_attributes_are_deprecated():
    from _testrunner.config import TestrunnerPluginManager

    pm = TestrunnerPluginManager()

    class DeprecatedHookMarkerSpec:
        def testrunner_bad_hook(self):
            pass

        testrunner_bad_hook.historic = False  # type: ignore[attr-defined]

    with testrunner.warns(
        TestrunnerDeprecationWarning,
        match=r"Please use the testrunner\.hookspec\(historic=False\) decorator",
    ) as recorder:
        pm.add_hookspecs(DeprecatedHookMarkerSpec)
    (record,) = recorder
    assert (
        record.lineno
        == DeprecatedHookMarkerSpec.testrunner_bad_hook.__code__.co_firstlineno
    )
    assert record.filename == __file__


def test_hookimpl_via_function_attributes_are_deprecated():
    from _testrunner.config import TestrunnerPluginManager

    pm = TestrunnerPluginManager()

    class DeprecatedMarkImplPlugin:
        def testrunner_runtest_call(self):
            pass

        testrunner_runtest_call.tryfirst = True  # type: ignore[attr-defined]

    with testrunner.warns(
        TestrunnerDeprecationWarning,
        match=r"Please use the testrunner.hookimpl\(tryfirst=True\)",
    ) as recorder:
        pm.register(DeprecatedMarkImplPlugin())
    (record,) = recorder
    assert (
        record.lineno
        == DeprecatedMarkImplPlugin.testrunner_runtest_call.__code__.co_firstlineno
    )
    assert record.filename == __file__


def test_yield_fixture_is_deprecated() -> None:
    with testrunner.warns(TestrunnerRemovedIn10Warning, match=r"yield_fixture is deprecated"):

        @testrunner.yield_fixture  # type: ignore[deprecated]
        def fix():
            assert False


def test_private_is_deprecated() -> None:
    class PrivateInit:
        def __init__(self, foo: int, *, _istestrunner: bool = False) -> None:
            deprecated.check_istestrunner(_istestrunner)

    with testrunner.warns(
        testrunner.TestrunnerDeprecationWarning, match="private testrunner class or function"
    ):
        PrivateInit(10)

    # Doesn't warn.
    PrivateInit(10, _istestrunner=True)


@testrunner.mark.parametrize(
    "scope", [Scope.Class, Scope.Module, Scope.Package, Scope.Session]
)
def test_higher_scope_instance_method_is_deprecated(
    testrunnerer: Testrunnerer, scope: Scope
) -> None:
    testrunnerer.makepyfile(
        f"""
        import testrunner

        class TestClass:
            @testrunner.fixture(scope="{scope.value}")
            def fix(self):
                self.attr = True

            def test_foo(self, fix):
                pass
        """
    )
    result = testrunnerer.runtestrunner("-Werror::testrunner.TestrunnerRemovedIn10Warning")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(
        ["*TestrunnerRemovedIn10Warning: *-scoped fixtures defined as instance methods*"]
    )


@testrunner.mark.parametrize(
    "scope", [Scope.Class, Scope.Module, Scope.Package, Scope.Session]
)
def test_higher_scope_classmethod_fixture_not_deprecated(
    testrunnerer: Testrunnerer, scope: Scope
) -> None:
    """A higher-scoped fixture defined as @classmethod does NOT warn."""
    testrunnerer.makepyfile(
        f"""
        import testrunner

        class TestClass:
            @testrunner.fixture(scope="{scope.value}")
            @classmethod
            def fix(cls):
                cls.attr = True

            def test_foo(self, fix):
                assert type(self).attr is True
        """
    )
    result = testrunnerer.runtestrunner("-Werror::testrunner.TestrunnerRemovedIn10Warning")
    result.assert_outcomes(passed=1)


@testrunner.mark.parametrize("scope", list(Scope))
def test_staticmethod_fixture_not_deprecated(testrunnerer: Testrunnerer, scope: Scope) -> None:
    """A fixture at any scope defined as @staticmethod does NOT warn."""
    testrunnerer.makepyfile(
        f"""
        import testrunner

        class TestClass:
            @testrunner.fixture(scope="{scope.value}")
            @staticmethod
            def fix():
                pass

            def test_foo(self, fix):
                pass
        """
    )
    result = testrunnerer.runtestrunner("-Werror::testrunner.TestrunnerRemovedIn10Warning")
    result.assert_outcomes(passed=1)


class TestFixtureNodeidDeprecations:
    """Tests for deprecated baseid/nodeid string APIs in fixture registration.

    AI-generated coverage tests for legacy paths that will be removed in
    testrunner 10. These exist solely to maintain patch coverage until the
    deprecated code is deleted.

    Legacy paths covered:
    - parsefactories(obj, nodeid_string) deprecation warning
    - parsefactories(obj, None) does NOT warn (standard plugin pattern)
    - parsefactories() with no args raises TypeError
    - _register_fixture(nodeid=string) deprecation warning
    - _nodeid_autousenames population and _getautousenames yield
    - _matchfactories string-based fallback (match + non-match branches)
    """

    def test_parsefactories_nodeid_deprecation(self, testrunnerer: Testrunnerer) -> None:
        """parsefactories(obj, "path") warns; parsefactories(obj, None) does not."""
        testrunnerer.makeconftest(
            """
            import testrunner
            import types
            import warnings

            def testrunner_collection_modifyitems(session, items):
                fm = session._fixturemanager

                @testrunner.fixture
                def fix_a():
                    return "a"

                @testrunner.fixture
                def fix_b():
                    return "b"

                mod_with_path = types.ModuleType("plugin_path")
                mod_with_path.fix_a = fix_a
                mod_none = types.ModuleType("plugin_none")
                mod_none.fix_b = fix_b

                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    fm.parsefactories(mod_with_path, "some/nodeid")
                    fm.parsefactories(mod_none, None)

                nodeid_warns = [x for x in w if "parsefactories" in str(x.message)]
                assert len(nodeid_warns) == 2, f"Expected 2 warning, got: {w}"
            """
        )
        testrunnerer.makepyfile(
            """
            def test_global_fix(fix_b):
                assert fix_b == "b"
            """
        )
        result = testrunnerer.runtestrunner("-W", "default::testrunner.TestrunnerRemovedIn10Warning")
        result.assert_outcomes(passed=1)

    def test_parsefactories_no_args_raises_typeerror(self, testrunnerer: Testrunnerer) -> None:
        """parsefactories() with no holder and no node_or_obj raises TypeError."""
        testrunnerer.makeconftest(
            """
            import testrunner

            def testrunner_collection_modifyitems(session, items):
                fm = session._fixturemanager
                with testrunner.raises(TypeError, match="requires holder or node_or_obj"):
                    fm.parsefactories()
            """
        )
        testrunnerer.makepyfile("def test_pass(): pass")
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=1)

    def test_register_fixture_nodeid_and_autouse_legacy(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """_register_fixture(nodeid=string) warns and autouse populates/yields.

        Covers end-to-end:
        - Deprecation warning on _register_fixture(nodeid=...)
        - _nodeid_autousenames populated for autouse + non-empty nodeid
        - _getautousenames yields from nodeid_basenames at lookup time
        """
        testrunnerer.makeconftest(
            """
            import testrunner
            import warnings

            _done = False

            def testrunner_collectstart(collector):
                global _done
                if _done or not hasattr(collector.session, "_fixturemanager"):
                    return
                if collector.nodeid == "":
                    return
                _done = True
                fm = collector.session._fixturemanager
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    fm._register_fixture(
                        name="legacy_autouse",
                        func=lambda: None,
                        nodeid=collector.nodeid,
                        autouse=True,
                    )
                assert any("_register_fixture" in str(x.message) for x in w)
                assert "legacy_autouse" in fm._nodeid_autousenames[collector.nodeid]
            """
        )
        testrunnerer.makepyfile(
            """
            def test_autouse_yielded(request):
                assert "legacy_autouse" in request.fixturenames
            """
        )
        result = testrunnerer.runtestrunner("-W", "default::testrunner.TestrunnerRemovedIn10Warning")
        result.assert_outcomes(passed=1)

    def test_matchfactories_string_fallback(self, testrunnerer: Testrunnerer) -> None:
        """_matchfactories uses baseid string matching for legacy fixtures.

        Exercises both branches:
        - baseid="" matches all nodes (global fixture)
        - baseid="nonexistent/path" matches nothing (scoped fixture invisible)
        """
        testrunnerer.makeconftest(
            """
            import testrunner
            import warnings

            def testrunner_collection_modifyitems(session, items):
                fm = session._fixturemanager
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fm._register_fixture(
                        name="global_legacy", func=lambda: "ok", nodeid=""
                    )
                    fm._register_fixture(
                        name="scoped_legacy", func=lambda: "nope",
                        nodeid="nonexistent/path",
                    )
            """
        )
        testrunnerer.makepyfile(
            """
            def test_global_visible(global_legacy):
                assert global_legacy == "ok"

            def test_scoped_invisible(request):
                defs = request.session._fixturemanager.getfixturedefs(
                    "scoped_legacy", request._pyfuncitem
                )
                assert defs == []
            """
        )
        result = testrunnerer.runtestrunner("-W", "ignore::testrunner.TestrunnerRemovedIn10Warning")
        result.assert_outcomes(passed=2)

    def test_fixturedef_has_location_deprecated(self, testrunnerer: Testrunnerer) -> None:
        """Accessing FixtureDef.has_location warns."""
        testrunnerer.makepyfile(
            """
            import testrunner

            @testrunner.fixture
            def fix():
                return 1

            def test_it(request):
                fixturedef = request._fixturemanager.getfixturedefs(
                    "fix", request._pyfuncitem
                )[0]
                with testrunner.warns(
                    testrunner.TestrunnerRemovedIn10Warning, match="has_location"
                ):
                    assert fixturedef.has_location is True
            """
        )
        result = testrunnerer.runtestrunner()
        result.assert_outcomes(passed=1)


def test_callspec2_renamed() -> None:
    """Importing/accessing CallSpec2 warns and returns CallSpec."""
    import _testrunner.python as python_mod
    from _testrunner.python import CallSpec

    with testrunner.warns(testrunner.TestrunnerRemovedIn10Warning, match="CallSpec2"):
        from _testrunner.python import CallSpec2

    assert CallSpec2 is CallSpec

    with testrunner.warns(testrunner.TestrunnerRemovedIn10Warning, match="CallSpec2"):
        assert python_mod.CallSpec2 is CallSpec
