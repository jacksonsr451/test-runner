# mypy: allow-untyped-defs
from __future__ import annotations

import importlib.metadata
import os
import shutil
import sys
import types

from _testrunner._code import ExceptionInfo
from _testrunner.config import _is_missing_module
from _testrunner.config import Config
from _testrunner.config import ExitCode
from _testrunner.config import PluginImportFailure
from _testrunner.config import TestrunnerPluginManager
from _testrunner.config.exceptions import UsageError
from _testrunner.main import Session
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.pathlib import import_path
from _testrunner.testrunnerer import Testrunnerer
import testrunner


@testrunner.fixture
def testrunnerpm() -> TestrunnerPluginManager:
    return TestrunnerPluginManager()


class TestTestrunnerPluginInteractions:
    def test_addhooks_conftestplugin(
        self, testrunnerer: Testrunnerer, _config_for_test: Config
    ) -> None:
        testrunnerer.makepyfile(
            newhooks="""
            def testrunner_myhook(xyz):
                "new hook"
        """
        )
        conf = testrunnerer.makeconftest(
            """
            import newhooks
            def testrunner_addhooks(pluginmanager):
                pluginmanager.add_hookspecs(newhooks)
            def testrunner_myhook(xyz):
                return xyz + 1
        """
        )
        config = _config_for_test
        pm = config.pluginmanager
        pm.hook.testrunner_addhooks.call_historic(
            kwargs=dict(pluginmanager=config.pluginmanager)
        )
        config.pluginmanager._importconftest(
            conf,
            importmode="prepend",
            rootpath=testrunnerer.path,
            consider_namespace_packages=False,
        )
        # print(config.pluginmanager.get_plugins())
        res = config.hook.testrunner_myhook(xyz=10)
        assert res == [11]

    def test_addhooks_nohooks(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            import sys
            def testrunner_addhooks(pluginmanager):
                pluginmanager.add_hookspecs(sys)
        """
        )
        res = testrunnerer.runtestrunner()
        assert res.ret != 0
        res.stderr.fnmatch_lines(["*did not find*sys*"])

    def test_do_option_postinitialize(self, testrunnerer: Testrunnerer) -> None:
        config = testrunnerer.parseconfigure()
        assert not hasattr(config.option, "test123")
        p = testrunnerer.makepyfile(
            """
            def testrunner_addoption(parser):
                parser.addoption('--test123', action="store_true",
                    default=True)
        """
        )
        config.pluginmanager._importconftest(
            p,
            importmode="prepend",
            rootpath=testrunnerer.path,
            consider_namespace_packages=False,
        )
        assert config.option.test123

    def test_configure(self, testrunnerer: Testrunnerer) -> None:
        config = testrunnerer.parseconfig()
        values = []

        class A:
            def testrunner_configure(self):
                values.append(self)

        config.pluginmanager.register(A())
        assert len(values) == 0
        config._do_configure()
        assert len(values) == 1
        config.pluginmanager.register(A())  # leads to a configured() plugin
        assert len(values) == 2
        assert values[0] != values[1]

        config._ensure_unconfigure()
        config.pluginmanager.register(A())
        assert len(values) == 2

    @testrunner.mark.skipif(
        not sys.platform.startswith("win"),
        reason="requires a case-insensitive file system",
    )
    def test_conftestpath_case_sensitivity(self, testrunnerer: Testrunnerer) -> None:
        """Unit test for issue #9765."""
        config = testrunnerer.parseconfig()
        testrunnerer.makepyfile(**{"tests/conftest.py": ""})

        conftest = testrunnerer.path.joinpath("tests/conftest.py")
        conftest_upper_case = testrunnerer.path.joinpath("TESTS/conftest.py")

        mod = config.pluginmanager._importconftest(
            conftest,
            importmode="prepend",
            rootpath=testrunnerer.path,
            consider_namespace_packages=False,
        )
        plugin = config.pluginmanager.get_plugin(str(conftest))
        assert plugin is mod

        mod_uppercase = config.pluginmanager._importconftest(
            conftest_upper_case,
            importmode="prepend",
            rootpath=testrunnerer.path,
            consider_namespace_packages=False,
        )
        plugin_uppercase = config.pluginmanager.get_plugin(str(conftest_upper_case))
        assert plugin_uppercase is mod_uppercase

        # No str(conftestpath) normalization so conftest should be imported
        # twice and modules should be different objects
        assert mod is not mod_uppercase

    def test_hook_tracing(self, _config_for_test: Config) -> None:
        testrunnerpm = _config_for_test.pluginmanager  # fully initialized with plugins
        saveindent = []

        class api1:
            def testrunner_plugin_registered(self):
                saveindent.append(testrunnerpm.trace.root.indent)

        class api2:
            def testrunner_plugin_registered(self):
                saveindent.append(testrunnerpm.trace.root.indent)
                raise ValueError()

        values: list[str] = []
        testrunnerpm.trace.root.setwriter(values.append)
        undo = testrunnerpm.enable_tracing()
        try:
            indent = testrunnerpm.trace.root.indent
            p = api1()
            testrunnerpm.register(p)
            assert testrunnerpm.trace.root.indent == indent
            assert len(values) >= 2
            assert "testrunner_plugin_registered" in values[0]
            assert "finish" in values[1]

            values[:] = []
            with testrunner.raises(ValueError):
                testrunnerpm.register(api2())
            assert testrunnerpm.trace.root.indent == indent
            assert saveindent[0] > indent
        finally:
            undo()

    def test_hook_proxy(self, testrunnerer: Testrunnerer) -> None:
        """Test the gethookproxy function(#2016)"""
        config = testrunnerer.parseconfig()
        session = Session.from_config(config)
        testrunnerer.makepyfile(**{"tests/conftest.py": "", "tests/subdir/conftest.py": ""})

        conftest1 = testrunnerer.path.joinpath("tests/conftest.py")
        conftest2 = testrunnerer.path.joinpath("tests/subdir/conftest.py")

        config.pluginmanager._importconftest(
            conftest1,
            importmode="prepend",
            rootpath=testrunnerer.path,
            consider_namespace_packages=False,
        )
        ihook_a = session.gethookproxy(testrunnerer.path / "tests")
        assert ihook_a is not None
        config.pluginmanager._importconftest(
            conftest2,
            importmode="prepend",
            rootpath=testrunnerer.path,
            consider_namespace_packages=False,
        )
        ihook_b = session.gethookproxy(testrunnerer.path / "tests")
        assert ihook_a is not ihook_b

    def test_hook_with_addoption(self, testrunnerer: Testrunnerer) -> None:
        """Test that hooks can be used in a call to testrunner_addoption"""
        testrunnerer.makepyfile(
            newhooks="""
            import testrunner
            @testrunner.hookspec(firstresult=True)
            def testrunner_default_value():
                pass
        """
        )
        testrunnerer.makepyfile(
            myplugin="""
            import newhooks
            def testrunner_addhooks(pluginmanager):
                pluginmanager.add_hookspecs(newhooks)
            def testrunner_addoption(parser, pluginmanager):
                default_value = pluginmanager.hook.testrunner_default_value()
                parser.addoption("--config", help="Config, defaults to %(default)s", default=default_value)
        """
        )
        testrunnerer.makeconftest(
            """
            testrunner_plugins=("myplugin",)
            def testrunner_default_value():
                return "default_value"
        """
        )
        res = testrunnerer.runtestrunner("--help")
        res.stdout.fnmatch_lines(["*--config=CONFIG*default_value*"])


def test_default_markers(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("--markers")
    result.stdout.fnmatch_lines(["*tryfirst*first*", "*trylast*last*"])


def test_importplugin_error_message(
    testrunnerer: Testrunnerer, testrunnerpm: TestrunnerPluginManager
) -> None:
    """Don't hide import errors when importing plugins and provide
    an easy to debug message.

    See #375 and #1998.
    """
    testrunnerer.syspathinsert(testrunnerer.path)
    testrunnerer.makepyfile(
        qwe="""\
        def test_traceback():
            raise ImportError('Not possible to import: ☺')
        test_traceback()
        """
    )
    with testrunner.raises(PluginImportFailure) as excinfo:
        testrunnerpm.import_plugin("qwe")

    assert excinfo.value.args == ("qwe",)
    # The original error and traceback must stay reachable through the cause,
    # otherwise there is no way to tell where in the plugin things went wrong.
    assert excinfo.value.__cause__ is not None
    assert str(excinfo.value.__cause__) == "Not possible to import: ☺"
    cause = ExceptionInfo.from_exception(excinfo.value.__cause__)
    assert "in test_traceback" in str(cause.traceback[-1])


def test_is_missing_module_without_name() -> None:
    """A ModuleNotFoundError raised without a module name cannot be attributed
    to the requested plugin, so it counts as a defect in the plugin."""
    assert not _is_missing_module(ModuleNotFoundError("boom"), "myplugin")


class TestTestrunnerPluginManager:
    def test_register_imported_modules(self) -> None:
        pm = TestrunnerPluginManager()
        mod = types.ModuleType("x.y.testrunner_hello")
        pm.register(mod)
        assert pm.is_registered(mod)
        values = pm.get_plugins()
        assert mod in values
        with testrunner.raises(ValueError):
            pm.register(mod)
        with testrunner.raises(ValueError):
            pm.register(mod)
        # assert not pm.is_registered(mod2)
        assert pm.get_plugins() == values

    def test_canonical_import(self, monkeypatch):
        mod = types.ModuleType("testrunner_xyz")
        monkeypatch.setitem(sys.modules, "testrunner_xyz", mod)
        pm = TestrunnerPluginManager()
        pm.import_plugin("testrunner_xyz")
        assert pm.get_plugin("testrunner_xyz") == mod
        assert pm.is_registered(mod)

    def test_consider_module(
        self, testrunnerer: Testrunnerer, testrunnerpm: TestrunnerPluginManager
    ) -> None:
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(testrunner_p1="#")
        testrunnerer.makepyfile(testrunner_p2="#")
        mod = types.ModuleType("temp")
        mod.__dict__["testrunner_plugins"] = ["testrunner_p1", "testrunner_p2"]
        testrunnerpm.consider_module(mod)
        p1 = testrunnerpm.get_plugin("testrunner_p1")
        assert p1 is not None
        assert p1.__name__ == "testrunner_p1"
        p2 = testrunnerpm.get_plugin("testrunner_p2")
        assert p2 is not None
        assert p2.__name__ == "testrunner_p2"

    def test_consider_module_import_module(
        self, testrunnerer: Testrunnerer, _config_for_test: Config
    ) -> None:
        testrunnerpm = _config_for_test.pluginmanager
        mod = types.ModuleType("x")
        mod.__dict__["testrunner_plugins"] = "testrunner_a"
        aplugin = testrunnerer.makepyfile(testrunner_a="#")
        reprec = testrunnerer.make_hook_recorder(testrunnerpm)
        testrunnerer.syspathinsert(aplugin.parent)
        testrunnerpm.consider_module(mod)
        call = reprec.getcall(testrunnerpm.hook.testrunner_plugin_registered.name)
        assert call.plugin.__name__ == "testrunner_a"

        # check that it is not registered twice
        testrunnerpm.consider_module(mod)
        values = reprec.getcalls("testrunner_plugin_registered")
        assert len(values) == 1

    def test_consider_env_fails_to_import(
        self, monkeypatch: MonkeyPatch, testrunnerpm: TestrunnerPluginManager
    ) -> None:
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "nonexisting", prepend=",")
        with testrunner.raises(UsageError):
            testrunnerpm.consider_env()

    def test_consider_env_entry_point_name(
        self, monkeypatch: MonkeyPatch, testrunnerpm: TestrunnerPluginManager
    ) -> None:
        """TESTRUNNER_PLUGINS accepts entry point names of installed plugins,
        in addition to importable module names (#12624)."""
        plugin = types.ModuleType("mytestplugin_module")

        class DummyEntryPoint:
            name = "mytestplugin"
            group = "testrunner11"

            def load(self):
                return plugin

        class DummyDist:
            version = "1.0"
            files = ()
            metadata = {"name": "mytestplugin"}
            entry_points = (DummyEntryPoint(),)

        monkeypatch.setattr(importlib.metadata, "distributions", lambda: (DummyDist(),))
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "mytestplugin")
        testrunnerpm.consider_env()
        assert testrunnerpm.get_plugin("mytestplugin") is plugin

    def test_consider_module_entry_point_name(
        self, monkeypatch: MonkeyPatch, testrunnerpm: TestrunnerPluginManager
    ) -> None:
        """testrunner_plugins accepts entry point names of installed plugins,
        in addition to importable module names (#12624)."""
        plugin = types.ModuleType("mytestplugin_module")

        class DummyEntryPoint:
            name = "mytestplugin"
            group = "testrunner11"

            def load(self):
                return plugin

        class DummyDist:
            version = "1.0"
            files = ()
            metadata = {"name": "mytestplugin"}
            entry_points = (DummyEntryPoint(),)

        monkeypatch.setattr(importlib.metadata, "distributions", lambda: (DummyDist(),))
        mod = types.ModuleType("temp")
        mod.__dict__["testrunner_plugins"] = ["mytestplugin"]
        testrunnerpm.consider_module(mod)
        assert testrunnerpm.get_plugin("mytestplugin") is plugin

    def test_consider_env_entry_point_reported_in_header(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        """Plugins loaded by entry point name via TESTRUNNER_PLUGINS are shown in
        the terminal header, like with -p (#12615)."""
        plugin = types.ModuleType("mytestplugin_module")

        class DummyEntryPoint:
            name = "mytestplugin"
            group = "testrunner11"

            def load(self):
                return plugin

        class DummyDist:
            version = "1.2.3"
            files = ()
            metadata = {"name": "mytestplugin"}
            entry_points = (DummyEntryPoint(),)

        monkeypatch.setattr(importlib.metadata, "distributions", lambda: (DummyDist(),))
        monkeypatch.setenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", "1")
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "mytestplugin")
        testrunnerer.makepyfile("def test_ok(): pass")
        result = testrunnerer.runtestrunner_inprocess()
        assert result.ret == ExitCode.OK
        result.stdout.fnmatch_lines(["plugins: *mytestplugin-1.2.3*"])

    @testrunner.mark.filterwarnings("always")
    def test_plugin_skip(self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch) -> None:
        p = testrunnerer.makepyfile(
            skipping1="""
            import testrunner
            testrunner.skip("hello", allow_module_level=True)
        """
        )
        shutil.copy(p, p.with_name("skipping2.py"))
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "skipping2")
        result = testrunnerer.runtestrunner("-p", "skipping1", syspathinsert=True)
        assert result.ret == ExitCode.NO_TESTS_COLLECTED
        result.stdout.fnmatch_lines(
            ["*skipped plugin*skipping1*hello*", "*skipped plugin*skipping2*hello*"]
        )

    def test_consider_env_plugin_instantiation(
        self,
        testrunnerer: Testrunnerer,
        monkeypatch: MonkeyPatch,
        testrunnerpm: TestrunnerPluginManager,
    ) -> None:
        testrunnerer.syspathinsert()
        testrunnerer.makepyfile(xy123="#")
        monkeypatch.setitem(os.environ, "TESTRUNNER_PLUGINS", "xy123")
        l1 = len(testrunnerpm.get_plugins())
        testrunnerpm.consider_env()
        l2 = len(testrunnerpm.get_plugins())
        assert l2 == l1 + 1
        assert testrunnerpm.get_plugin("xy123")
        testrunnerpm.consider_env()
        l3 = len(testrunnerpm.get_plugins())
        assert l2 == l3

    def test_pluginmanager_ENV_startup(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        testrunnerer.makepyfile(testrunner_x500="#")
        p = testrunnerer.makepyfile(
            """
            import testrunner
            def test_hello(testrunnerconfig):
                plugin = testrunnerconfig.pluginmanager.get_plugin('testrunner_x500')
                assert plugin is not None
        """
        )
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "testrunner_x500", prepend=",")
        result = testrunnerer.runtestrunner(p, syspathinsert=True)
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*1 passed*"])

    def test_import_plugin_importname(
        self, testrunnerer: Testrunnerer, testrunnerpm: TestrunnerPluginManager
    ) -> None:
        with testrunner.raises(UsageError):
            testrunnerpm.import_plugin("qweqwex.y")
        with testrunner.raises(UsageError):
            testrunnerpm.import_plugin("testrunner_qweqwx.y")

        testrunnerer.syspathinsert()
        pluginname = "testrunner_hello"
        testrunnerer.makepyfile(**{pluginname: ""})
        testrunnerpm.import_plugin("testrunner_hello")
        len1 = len(testrunnerpm.get_plugins())
        testrunnerpm.import_plugin("testrunner_hello")
        len2 = len(testrunnerpm.get_plugins())
        assert len1 == len2
        plugin1 = testrunnerpm.get_plugin("testrunner_hello")
        assert plugin1 is not None
        assert plugin1.__name__.endswith("testrunner_hello")
        plugin2 = testrunnerpm.get_plugin("testrunner_hello")
        assert plugin2 is plugin1

    def test_import_plugin_dotted_name(
        self, testrunnerer: Testrunnerer, testrunnerpm: TestrunnerPluginManager
    ) -> None:
        with testrunner.raises(UsageError):
            testrunnerpm.import_plugin("qweqwex.y")
        with testrunner.raises(UsageError):
            testrunnerpm.import_plugin("testrunner_qweqwex.y")

        testrunnerer.syspathinsert()
        testrunnerer.mkpydir("pkg").joinpath("plug.py").write_text("x=3", encoding="utf-8")
        pluginname = "pkg.plug"
        testrunnerpm.import_plugin(pluginname)
        mod = testrunnerpm.get_plugin("pkg.plug")
        assert mod is not None
        assert mod.x == 3

    def test_consider_conftest_deps(
        self,
        testrunnerer: Testrunnerer,
        testrunnerpm: TestrunnerPluginManager,
    ) -> None:
        mod = import_path(
            testrunnerer.makepyfile("testrunner_plugins='xyz'"),
            root=testrunnerer.path,
            consider_namespace_packages=False,
        )
        with testrunner.raises(UsageError):
            testrunnerpm.consider_conftest(mod, registration_name="unused")


class TestTestrunnerPluginManagerBootstrapping:
    def test_preparse_args(self, testrunnerpm: TestrunnerPluginManager) -> None:
        with testrunner.raises(UsageError):
            testrunnerpm.consider_preparse(["xyz", "-p", "hello123"])

        # Handles -p without space (#3532).
        with testrunner.raises(UsageError) as excinfo:
            testrunnerpm.consider_preparse(["-phello123"])
        assert '"hello123"' in excinfo.value.args[0]
        testrunnerpm.consider_preparse(["-pno:hello123"])

        # Handles -p without following arg (when used without argparse).
        testrunnerpm.consider_preparse(["-p"])

        with testrunner.raises(UsageError, match=r"^plugin main cannot be disabled$"):
            testrunnerpm.consider_preparse(["-p", "no:main"])

    def test_plugin_prevent_register(self, testrunnerpm: TestrunnerPluginManager) -> None:
        testrunnerpm.consider_preparse(["xyz", "-p", "no:abc"])
        l1 = testrunnerpm.get_plugins()
        testrunnerpm.register(42, name="abc")
        l2 = testrunnerpm.get_plugins()
        assert len(l2) == len(l1)
        assert 42 not in l2

    def test_plugin_prevent_register_unregistered_already_registered(
        self, testrunnerpm: TestrunnerPluginManager
    ) -> None:
        testrunnerpm.register(42, name="abc")
        l1 = testrunnerpm.get_plugins()
        assert 42 in l1
        testrunnerpm.consider_preparse(["xyz", "-p", "no:abc"])
        l2 = testrunnerpm.get_plugins()
        assert 42 not in l2

    def test_plugin_prevent_register_stepwise_on_cacheprovider_unregister(
        self, testrunnerpm: TestrunnerPluginManager
    ) -> None:
        """From PR #4304: The only way to unregister a module is documented at
        the end of https://github.com/jacksonsr451/test-runner/tree/main/doc/en/how-to/plugins.html.

        When unregister cacheprovider, then unregister stepwise too.
        """
        testrunnerpm.register(42, name="cacheprovider")
        testrunnerpm.register(43, name="stepwise")
        l1 = testrunnerpm.get_plugins()
        assert 42 in l1
        assert 43 in l1
        testrunnerpm.consider_preparse(["xyz", "-p", "no:cacheprovider"])
        l2 = testrunnerpm.get_plugins()
        assert 42 not in l2
        assert 43 not in l2

    def test_blocked_plugin_can_be_used(self, testrunnerpm: TestrunnerPluginManager) -> None:
        testrunnerpm.consider_preparse(["xyz", "-p", "no:abc", "-p", "abc"])

        assert testrunnerpm.has_plugin("abc")
        assert not testrunnerpm.is_blocked("abc")
        assert not testrunnerpm.is_blocked("testrunner_abc")
