# mypy: allow-untyped-defs
from __future__ import annotations

from collections.abc import Sequence
import dataclasses
import importlib.metadata
import os
from pathlib import Path
import re
import sys
import textwrap
from typing import Any
from typing import Literal

import _testrunner._code
from _testrunner.config import _get_plugin_specs_as_list
from _testrunner.config import _get_prog_name
from _testrunner.config import _iter_rewritable_modules
from _testrunner.config import _strtobool
from _testrunner.config import Config
from _testrunner.config import ConftestImportFailure
from _testrunner.config import console_main
from _testrunner.config import ExitCode
from _testrunner.config import parse_warning_filter
from _testrunner.config import PluginImportFailure
from _testrunner.config.argparsing import get_ini_default_for_type
from _testrunner.config.argparsing import Parser
from _testrunner.config.exceptions import UsageError
from _testrunner.config.findpaths import ConfigValue
from _testrunner.config.findpaths import determine_setup
from _testrunner.config.findpaths import get_common_ancestor
from _testrunner.config.findpaths import locate_config
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.pathlib import absolutepath
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.warning_types import TestrunnerDeprecationWarning
import testrunner


class TestParseIni:
    @testrunner.mark.parametrize(
        "section, filename",
        [("testrunner", "testrunner.ini"), ("tool:testrunner", "setup.cfg")],
    )
    def test_getcfg_and_config(
        self,
        testrunnerer: Testrunnerer,
        tmp_path: Path,
        section: str,
        filename: str,
        monkeypatch: MonkeyPatch,
    ) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        monkeypatch.chdir(sub)
        (tmp_path / filename).write_text(
            textwrap.dedent(
                f"""\
                [{section}]
                name = value
                """
            ),
            encoding="utf-8",
        )
        _, _, cfg, _ = locate_config(Path.cwd(), [sub])
        assert cfg["name"] == ConfigValue("value", origin="file", mode="ini")
        config = testrunnerer.parseconfigure(str(sub))
        assert config._inicfg["name"] == ConfigValue("value", origin="file", mode="ini")

    def test_setupcfg_uses_tooltestrunner_with_testrunner(
        self, testrunnerer: Testrunnerer
    ) -> None:
        p1 = testrunnerer.makepyfile("def test(): pass")
        testrunnerer.makefile(
            ".cfg",
            setup=f"""
                [tool:testrunner]
                testpaths={p1.name}
                [testrunner]
                testpaths=ignored
        """,
        )
        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(["configfile: setup.cfg", "* 1 passed in *"])
        assert result.ret == 0

    def test_append_parse_args(
        self, testrunnerer: Testrunnerer, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TESTRUNNER_ADDOPTS", '--color no -rs --tb="short"')
        tmp_path.joinpath("testrunner.ini").write_text(
            textwrap.dedent(
                """\
                [testrunner]
                addopts = --verbose
                """
            ),
            encoding="utf-8",
        )
        config = testrunnerer.parseconfig(tmp_path)
        assert config.option.color == "no"
        assert config.option.reportchars == "s"
        assert config.option.tbstyle == "short"
        assert config.option.verbose

    @testrunner.mark.parametrize("flag", ("-r", "--report-chars="))
    @testrunner.mark.parametrize("value", ("fE", "A", "fs"))
    def test_report_chars_option(
        self,
        testrunnerer: Testrunnerer,
        tmp_path: Path,
        monkeypatch: MonkeyPatch,
        flag: str,
        value: str,
    ) -> None:
        """Test that -r/--report-chars is parsed correctly."""
        monkeypatch.setenv("TESTRUNNER_ADDOPTS", flag + value)
        config = testrunnerer.parseconfig(tmp_path)
        assert config.option.reportchars == value

    def test_tox_ini_wrong_version(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makefile(
            ".ini",
            tox="""
            [testrunner]
            minversion=999.0
        """,
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        result.stderr.fnmatch_lines(
            ["*tox.ini: 'minversion' requires testrunner-999.0, actual testrunner-*"]
        )

    @testrunner.mark.parametrize(
        "section, name",
        [
            ("tool:testrunner", "setup.cfg"),
            ("testrunner", "tox.ini"),
            ("testrunner", "testrunner.ini"),
            ("testrunner", ".testrunner.ini"),
        ],
    )
    def test_ini_names(self, testrunnerer: Testrunnerer, name, section) -> None:
        testrunnerer.path.joinpath(name).write_text(
            textwrap.dedent(
                f"""
            [{section}]
            minversion = 0.1.0.dev0
        """
            ),
            encoding="utf-8",
        )
        config = testrunnerer.parseconfig()
        assert config.getini("minversion") == "0.1.0.dev0"

    @testrunner.mark.parametrize("name", ["testrunner.toml", ".testrunner.toml"])
    def test_toml_config_names(self, testrunnerer: Testrunnerer, name: str) -> None:
        testrunnerer.path.joinpath(name).write_text(
            textwrap.dedent(
                """
            [testrunner]
            minversion = "0.1.0.dev0"
        """
            ),
            encoding="utf-8",
        )
        config = testrunnerer.parseconfig()
        assert config.getini("minversion") == "0.1.0.dev0"

    @testrunner.mark.parametrize("name", ["testrunner.toml", ".testrunner.toml"])
    def test_toml_config_names_without_section_errors(
        self, testrunnerer: Testrunnerer, name: str
    ) -> None:
        config_path = testrunnerer.path.joinpath(name)
        config_path.write_text(
            textwrap.dedent(
                """
            minversion = "0.1.0.dev0"
            addopts = ["-v"]
        """
            ),
            encoding="utf-8",
        )
        with testrunner.raises(UsageError) as excinfo:
            testrunnerer.parseconfig()
        assert str(excinfo.value) == (
            f"{config_path}: "
            "testrunner configuration must be under a [testrunner] table "
            "(found top-level options: minversion, addopts)"
        )

    def test_pyproject_toml(self, testrunnerer: Testrunnerer) -> None:
        pyproject_toml = testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner.ini_options]
            minversion = "0.1.0.dev0"
        """
        )
        config = testrunnerer.parseconfig()
        assert config.inipath == pyproject_toml
        assert config.getini("minversion") == "0.1.0.dev0"

    def test_empty_pyproject_toml(self, testrunnerer: Testrunnerer) -> None:
        """An empty pyproject.toml is considered as config if no other option is found."""
        pyproject_toml = testrunnerer.makepyprojecttoml("")
        config = testrunnerer.parseconfig()
        assert config.inipath == pyproject_toml

    def test_empty_pyproject_toml_found_many(self, testrunnerer: Testrunnerer) -> None:
        """
        In case we find multiple pyproject.toml files in our search, without a [tool.testrunner]
        table and without finding other candidates, the closest to where we started wins.
        """
        testrunnerer.makefile(
            ".toml",
            **{
                "pyproject": "",
                "foo/pyproject": "",
                "foo/bar/pyproject": "",
            },
        )
        config = testrunnerer.parseconfig(testrunnerer.path / "foo/bar")
        assert config.inipath == testrunnerer.path / "foo/bar/pyproject.toml"

    def test_testrunner_toml(self, testrunnerer: Testrunnerer) -> None:
        testrunner_toml = testrunnerer.path.joinpath("testrunner.toml")
        testrunner_toml = testrunnerer.maketoml(
            """
            [testrunner]
            minversion = "0.1.0.dev0"
            """
        )
        config = testrunnerer.parseconfig()
        assert config.inipath == testrunner_toml
        assert config.getini("minversion") == "0.1.0.dev0"

    @testrunner.mark.parametrize("name", ["testrunner.toml", ".testrunner.toml"])
    def test_empty_testrunner_toml(self, testrunnerer: Testrunnerer, name: str) -> None:
        """An empty testrunner.toml is considered as config if no other option is found."""
        testrunner_toml = testrunnerer.path / name
        testrunner_toml.write_text("", encoding="utf-8")
        config = testrunnerer.parseconfig()
        assert config.inipath == testrunner_toml

    def test_testrunner_toml_trumps_pyproject_toml(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """A testrunner.toml always takes precedence over a pyproject.toml file."""
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner]
            minversion = "0.1.0.dev0"
            """
        )
        testrunner_toml = testrunnerer.maketoml(
            """
            [testrunner]
            minversion = "0.1.0.dev0"
            """
        )
        config = testrunnerer.parseconfig()
        assert config.inipath == testrunner_toml
        assert config.getini("minversion") == "0.1.0.dev0"

    def test_testrunner_toml_trumps_testrunner_ini(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """A testrunner.toml always takes precedence over a testrunner.ini file."""
        testrunnerer.makeini(
            """
            [testrunner]
            minversion = 0.1.0.dev0
            """,
        )
        testrunner_toml = testrunnerer.maketoml(
            """
            [testrunner]
            minversion = "0.1.0.dev0"
            """,
        )
        config = testrunnerer.parseconfig()
        assert config.inipath == testrunner_toml
        assert config.getini("minversion") == "0.1.0.dev0"

    def test_dot_testrunner_toml_trumps_testrunner_ini(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """A .testrunner.toml always takes precedence over a testrunner.ini file."""
        testrunnerer.makeini(
            """
            [testrunner]
            minversion = 0.1.0.dev0
            """,
        )
        testrunner_toml = testrunnerer.maketoml(
            """
            [testrunner]
            minversion = "0.1.0.dev0"
            """
        )
        config = testrunnerer.parseconfig()
        assert config.inipath == testrunner_toml
        assert config.getini("minversion") == "0.1.0.dev0"

    def test_testrunner_ini_trumps_pyproject_toml(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """A testrunner.ini always take precedence over a pyproject.toml file."""
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner]
            minversion = "0.1.0.dev0"
            """
        )
        testrunner_ini = testrunnerer.makefile(".ini", testrunner="")
        config = testrunnerer.parseconfig()
        assert config.inipath == testrunner_ini

    def test_toxini_before_lower_testrunnerini(
        self, testrunnerer: Testrunnerer
    ) -> None:
        sub = testrunnerer.mkdir("sub")
        sub.joinpath("tox.ini").write_text(
            textwrap.dedent(
                """
            [testrunner]
            minversion = 0.1.0.dev0
        """
            ),
            encoding="utf-8",
        )
        testrunnerer.path.joinpath("testrunner.ini").write_text(
            textwrap.dedent(
                """
            [testrunner]
            minversion = 0.1.0.dev0
        """
            ),
            encoding="utf-8",
        )
        config = testrunnerer.parseconfigure(sub)
        assert config.getini("minversion") == "0.1.0.dev0"

    def test_ini_parse_error(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.path.joinpath("testrunner.ini").write_text(
            "addopts = -x", encoding="utf-8"
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        result.stderr.fnmatch_lines(
            "ERROR: *testrunner.ini:1: no section header defined"
        )

    def test_toml_parse_error(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyprojecttoml(
            """
            \\"
            """
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        result.stderr.fnmatch_lines("ERROR: *pyproject.toml: Invalid statement*")

    def test_testrunner_toml_parse_error(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.path.joinpath("testrunner.toml").write_text(
            """
            \\"
            """,
            encoding="utf-8",
        )
        result = testrunnerer.runtestrunner()
        assert result.ret != 0
        result.stderr.fnmatch_lines("ERROR: *testrunner.toml: Invalid statement*")

    def test_confcutdir_default_without_configfile(
        self, testrunnerer: Testrunnerer
    ) -> None:
        # If --confcutdir is not specified, and there is no configfile, default
        # to the rootpath.
        sub = testrunnerer.mkdir("sub")
        os.chdir(sub)
        config = testrunnerer.parseconfigure()
        assert config.pluginmanager._confcutdir == sub

    def test_confcutdir_default_with_configfile(
        self, testrunnerer: Testrunnerer
    ) -> None:
        # If --confcutdir is not specified, and there is a configfile, default
        # to the configfile's directory.
        testrunnerer.makeini("[testrunner]")
        sub = testrunnerer.mkdir("sub")
        os.chdir(sub)
        config = testrunnerer.parseconfigure()
        assert config.pluginmanager._confcutdir == testrunnerer.path

    @testrunner.mark.xfail(reason="probably not needed")
    def test_confcutdir(self, testrunnerer: Testrunnerer) -> None:
        sub = testrunnerer.mkdir("sub")
        os.chdir(sub)
        testrunnerer.makeini(
            """
            [testrunner]
            addopts = --qwe
        """
        )
        result = testrunnerer.inline_run("--confcutdir=.")
        assert result.ret == 0

    @testrunner.mark.parametrize(
        "ini_file_text, invalid_keys, warning_output, exception_text",
        [
            testrunner.param(
                """
                [testrunner]
                unknown_ini = value1
                another_unknown_ini = value2
                """,
                ["unknown_ini", "another_unknown_ini"],
                [
                    "=*= warnings summary =*=",
                    "*TestrunnerConfigWarning:*Unknown config option: another_unknown_ini",
                    "*TestrunnerConfigWarning:*Unknown config option: unknown_ini",
                ],
                "Unknown config option: another_unknown_ini",
                id="2-unknowns",
            ),
            testrunner.param(
                """
                [testrunner]
                unknown_ini = value1
                minversion = 0.1.0.dev0
                """,
                ["unknown_ini"],
                [
                    "=*= warnings summary =*=",
                    "*TestrunnerConfigWarning:*Unknown config option: unknown_ini",
                ],
                "Unknown config option: unknown_ini",
                id="1-unknown",
            ),
            testrunner.param(
                """
                [some_other_header]
                unknown_ini = value1
                [testrunner]
                minversion = 0.1.0.dev0
                """,
                [],
                [],
                "",
                id="unknown-in-other-header",
            ),
            testrunner.param(
                """
                [testrunner]
                minversion = 0.1.0.dev0
                """,
                [],
                [],
                "",
                id="no-unknowns",
            ),
            testrunner.param(
                """
                [testrunner]
                conftest_ini_key = 1
                """,
                [],
                [],
                "",
                id="1-known",
            ),
        ],
    )
    @testrunner.mark.filterwarnings("default")
    def test_invalid_config_options(
        self,
        testrunnerer: Testrunnerer,
        ini_file_text,
        invalid_keys,
        warning_output,
        exception_text,
    ) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("conftest_ini_key", "")
            """
        )
        testrunnerer.makepyfile("def test(): pass")
        testrunnerer.makeini(ini_file_text)

        config = testrunnerer.parseconfig()
        assert sorted(config._get_unknown_ini_keys()) == sorted(invalid_keys)

        result = testrunnerer.runtestrunner()
        result.stdout.fnmatch_lines(warning_output)

        result = testrunnerer.runtestrunner("--strict-config")
        if exception_text:
            result.stderr.fnmatch_lines("ERROR: " + exception_text)
            assert result.ret == testrunner.ExitCode.USAGE_ERROR
        else:
            result.stderr.no_fnmatch_line(exception_text)
            assert result.ret == testrunner.ExitCode.OK

    @testrunner.mark.filterwarnings("default")
    def test_silence_unknown_key_warning(self, testrunnerer: Testrunnerer) -> None:
        """Unknown config key warnings can be silenced using filterwarnings (#7620)"""
        testrunnerer.makeini(
            """
            [testrunner]
            filterwarnings =
                ignore:Unknown config option:testrunner.TestrunnerConfigWarning
            foobar=1
        """
        )
        result = testrunnerer.runtestrunner()
        result.stdout.no_fnmatch_line("*TestrunnerConfigWarning*")

    @testrunner.mark.parametrize(
        "option",
        [
            "strict_config = true",
            "strict = true",
            "addopts = --strict-config",
        ],
    )
    def test_strict_config_ini_option(
        self, testrunnerer: Testrunnerer, option: str
    ) -> None:
        """Test that strict_config and strict ini options enable strict config checking."""
        testrunnerer.makeini(
            f"""
            [testrunner]
            unknown_option = 1
            {option}
            """
        )
        result = testrunnerer.runtestrunner()
        result.stderr.fnmatch_lines("ERROR: Unknown config option: unknown_option")
        assert result.ret == testrunner.ExitCode.USAGE_ERROR

    @testrunner.mark.filterwarnings("default::testrunner.TestrunnerConfigWarning")
    def test_disable_warnings_plugin_disables_config_warnings(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Disabling 'warnings' plugin also disables config time warnings"""
        testrunnerer.makeconftest(
            """
            import testrunner
            def testrunner_configure(config):
                config.issue_config_time_warning(
                    testrunner.TestrunnerConfigWarning("custom config warning"),
                    stacklevel=2,
                )
        """
        )
        result = testrunnerer.runtestrunner("-pno:warnings")
        result.stdout.no_fnmatch_line("*TestrunnerConfigWarning*")

    @testrunner.mark.parametrize(
        "ini_file_text, plugin_version, exception_text",
        [
            testrunner.param(
                """
                [testrunner]
                required_plugins = a z
                """,
                "1.5",
                "Missing required plugins: a, z",
                id="2-missing",
            ),
            testrunner.param(
                """
                [testrunner]
                required_plugins = a z myplugin
                """,
                "1.5",
                "Missing required plugins: a, z",
                id="2-missing-1-ok",
            ),
            testrunner.param(
                """
                [testrunner]
                required_plugins = myplugin
                """,
                "1.5",
                None,
                id="1-ok",
            ),
            testrunner.param(
                """
                [testrunner]
                required_plugins = myplugin==1.5
                """,
                "1.5",
                None,
                id="1-ok-pin-exact",
            ),
            testrunner.param(
                """
                [testrunner]
                required_plugins = myplugin>1.0,<2.0
                """,
                "1.5",
                None,
                id="1-ok-pin-loose",
            ),
            testrunner.param(
                """
                [testrunner]
                required_plugins = myplugin
                """,
                "1.5a1",
                None,
                id="1-ok-prerelease",
            ),
            testrunner.param(
                """
                [testrunner]
                required_plugins = myplugin==1.6
                """,
                "1.5",
                "Missing required plugins: myplugin==1.6",
                id="missing-version",
            ),
            testrunner.param(
                """
                [testrunner]
                required_plugins = myplugin==1.6 other==1.0
                """,
                "1.5",
                "Missing required plugins: myplugin==1.6, other==1.0",
                id="missing-versions",
            ),
            testrunner.param(
                """
                [some_other_header]
                required_plugins = won't be triggered
                [testrunner]
                """,
                "1.5",
                None,
                id="invalid-header",
            ),
        ],
    )
    def test_missing_required_plugins(
        self,
        testrunnerer: Testrunnerer,
        monkeypatch: MonkeyPatch,
        ini_file_text: str,
        plugin_version: str,
        exception_text: str,
    ) -> None:
        """Check 'required_plugins' option with various settings.

        This test installs a mock "myplugin-1.5" which is used in the parametrized test cases.
        """

        @dataclasses.dataclass
        class DummyEntryPoint:
            name: str
            module: str
            group: str = "testrunner11"

            def load(self):
                return importlib.import_module(self.module)

        entry_points = [
            DummyEntryPoint("myplugin1", "myplugin1_module"),
        ]

        @dataclasses.dataclass
        class DummyDist:
            entry_points: object
            files: object = ()
            version: str = plugin_version

            @property
            def metadata(self):
                return {"name": "myplugin"}

        def my_dists():
            return [DummyDist(entry_points)]

        testrunnerer.makepyfile(myplugin1_module="# my plugin module")
        testrunnerer.syspathinsert()

        monkeypatch.setattr(importlib.metadata, "distributions", my_dists)
        monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", raising=False)

        testrunnerer.makeini(ini_file_text)

        if exception_text:
            with testrunner.raises(testrunner.UsageError, match=exception_text):
                testrunnerer.parseconfig()
        else:
            testrunnerer.parseconfig()

    def test_early_config_cmdline(
        self, testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
    ) -> None:
        """early_config contains options registered by third-party plugins.

        This is a regression involving testrunner-cov (and possibly others) introduced in #7700.
        """
        testrunnerer.makepyfile(
            myplugin="""
            def testrunner_addoption(parser):
                parser.addoption('--foo', default=None, dest='foo')

            def testrunner_load_initial_conftests(early_config, parser, args):
                assert early_config.known_args_namespace.foo == "1"
            """
        )
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "myplugin")
        testrunnerer.syspathinsert()
        result = testrunnerer.runtestrunner("--foo=1")
        result.stdout.fnmatch_lines("* no tests ran in *")

    def test_args_source_args(self, testrunnerer: Testrunnerer):
        config = testrunnerer.parseconfig("--", "test_filename.py")
        assert config.args_source == Config.ArgsSource.ARGS

    def test_args_source_invocation_dir(self, testrunnerer: Testrunnerer):
        config = testrunnerer.parseconfig()
        assert config.args_source == Config.ArgsSource.INVOCATION_DIR

    def test_args_source_testpaths(self, testrunnerer: Testrunnerer):
        testrunnerer.makeini(
            """
            [testrunner]
            testpaths=*
        """
        )
        config = testrunnerer.parseconfig()
        assert config.args_source == Config.ArgsSource.TESTPATHS


class TestConfigCmdlineParsing:
    def test_parsing_again_fails(self, testrunnerer: Testrunnerer) -> None:
        config = testrunnerer.parseconfig()
        with testrunner.raises(AssertionError):
            config.parse([])

    def test_explicitly_specified_config_file_is_loaded(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("custom", "")
        """
        )
        testrunnerer.makeini(
            """
            [testrunner]
            custom = 0
        """
        )
        testrunnerer.makefile(
            ".ini",
            custom="""
            [testrunner]
            custom = 1
        """,
        )
        config = testrunnerer.parseconfig("-c", "custom.ini")
        assert config.getini("custom") == "1"
        config = testrunnerer.parseconfig("--config-file", "custom.ini")
        assert config.getini("custom") == "1"

        testrunnerer.makefile(
            ".cfg",
            custom_tool_testrunner_section="""
            [tool:testrunner]
            custom = 1
        """,
        )
        config = testrunnerer.parseconfig("-c", "custom_tool_testrunner_section.cfg")
        assert config.getini("custom") == "1"
        config = testrunnerer.parseconfig(
            "--config-file", "custom_tool_testrunner_section.cfg"
        )
        assert config.getini("custom") == "1"

        testrunnerer.makefile(
            ".toml",
            custom="""
                [tool.testrunner.ini_options]
                custom = 1
                value = [
                ]  # this is here on purpose, as it makes this an invalid '.ini' file
            """,
        )
        config = testrunnerer.parseconfig("-c", "custom.toml")
        assert config.getini("custom") == "1"
        config = testrunnerer.parseconfig("--config-file", "custom.toml")
        assert config.getini("custom") == "1"

        # A custom TOML file also reads [testrunner], the table testrunner's own
        # configuration files use (#14705).
        testrunnerer.makefile(
            ".toml",
            custom_testrunner_table="""
                [testrunner]
                custom = "1"
                value = [
                ]  # this is here on purpose, as it makes this an invalid '.ini' file
            """,
        )
        config = testrunnerer.parseconfig("-c", "custom_testrunner_table.toml")
        assert config.getini("custom") == "1"
        config = testrunnerer.parseconfig(
            "--config-file", "custom_testrunner_table.toml"
        )
        assert config.getini("custom") == "1"

    @testrunner.mark.parametrize(
        "name", ["missing.ini", "missing.in", "missing.toml", "missing"]
    )
    def test_explicitly_specified_config_file_missing(
        self, testrunnerer: Testrunnerer, name: str
    ) -> None:
        """A nonexistent -c path is a UsageError, whatever its extension (#14716).

        Previously this either silently proceeded with an empty configuration
        (unrecognized extension) or crashed with a raw FileNotFoundError
        traceback (recognized extension).
        """
        with testrunner.raises(UsageError, match=r"Config file .* not found"):
            testrunnerer.parseconfig("-c", name)

    def test_explicitly_specified_config_file_unsupported_format(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """An existing -c path with an unsupported extension is a UsageError (#14716)."""
        testrunnerer.makefile(".in", config="[testrunner]\naddopts = -v\n")
        with testrunner.raises(UsageError, match="unsupported format"):
            testrunnerer.parseconfig("-c", "config.in")

    def test_explicitly_specified_config_file_is_a_directory(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """A directory passed to -c is a UsageError rather than a confusing no-op."""
        testrunnerer.mkdir("somedir")
        with testrunner.raises(UsageError, match="is a directory"):
            testrunnerer.parseconfig("-c", "somedir")

    @testrunner.mark.skipif(
        sys.platform.startswith("win32"), reason="requires a POSIX null device"
    )
    def test_explicitly_specified_config_file_not_a_regular_file(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """``--config-file=/dev/null`` loads no config and does not set rootdir to /dev.

        Deriving the rootdir from a character device made the cache plugin try to
        write to ``/dev/.testrunner_cache`` (#11502).
        """
        testrunnerer.makepyfile(test_it="def test(): pass")
        config = testrunnerer.parseconfig(
            "--config-file", os.devnull, str(testrunnerer.path)
        )
        assert config.rootpath == testrunnerer.path
        assert config.inipath == Path(os.devnull)

    def test_absolute_win32_path(self, testrunnerer: Testrunnerer) -> None:
        temp_ini_file = testrunnerer.makeini("[testrunner]")
        from os.path import normpath

        temp_ini_file_norm = normpath(str(temp_ini_file))
        ret = testrunner.main(["-c", temp_ini_file_norm])
        assert ret == ExitCode.NO_TESTS_COLLECTED
        ret = testrunner.main(["--config-file", temp_ini_file_norm])
        assert ret == ExitCode.NO_TESTS_COLLECTED


class TestConfigAPI:
    def test_config_trace(self, testrunnerer: Testrunnerer) -> None:
        config = testrunnerer.parseconfig()
        values: list[str] = []
        config.trace.root.setwriter(values.append)
        config.trace("hello")
        assert len(values) == 1
        assert values[0] == "hello [config]\n"

    def test_config_getoption_declared_option_name(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addoption("--hello", "-X", dest="hello")
        """
        )
        config = testrunnerer.parseconfig("--hello=this")
        for x in ("hello", "--hello", "-X"):
            assert config.getoption(x) == "this"
        with testrunner.raises(ValueError):
            config.getoption("qweqwe")

        config_novalue = testrunnerer.parseconfig()
        assert config_novalue.getoption("hello") is None
        assert config_novalue.getoption("hello", default=1) is None
        assert config_novalue.getoption("hello", default=1, skip=True) == 1

    def test_config_getoption_undeclared_option_name(
        self, testrunnerer: Testrunnerer
    ) -> None:
        config = testrunnerer.parseconfig()
        with testrunner.raises(ValueError):
            config.getoption("x")
        assert config.getoption("x", default=1) == 1
        assert config.getoption("x", default=1, skip=True) == 1

    def test_config_getoption_unicode(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addoption('--hello', type=str)
        """
        )
        config = testrunnerer.parseconfig("--hello=this")
        assert config.getoption("hello") == "this"

    def test_config_getvalueorskip(self, testrunnerer: Testrunnerer) -> None:
        config = testrunnerer.parseconfig()
        with testrunner.raises(testrunner.skip.Exception):
            config.getvalueorskip("hello")
        verbose = config.getvalueorskip("verbose")
        assert verbose == config.option.verbose

    def test_config_getvalueorskip_None(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addoption("--hello")
        """
        )
        config = testrunnerer.parseconfig()
        with testrunner.raises(testrunner.skip.Exception):
            config.getvalueorskip("hello")

    def test_getconftest_pathlist(
        self, testrunnerer: Testrunnerer, tmp_path: Path
    ) -> None:
        somepath = tmp_path.joinpath("x", "y", "z")
        p = tmp_path.joinpath("conftest.py")
        p.write_text(f"mylist = {['.', str(somepath)]}", encoding="utf-8")
        config = testrunnerer.parseconfigure(p)
        assert config._getconftest_pathlist("notexist", path=tmp_path) is None
        assert config._getconftest_pathlist("mylist", path=tmp_path) == [
            tmp_path,
            somepath,
        ]

    @testrunner.mark.parametrize("maybe_type", ["not passed", "None", '"string"'])
    def test_addini(self, testrunnerer: Testrunnerer, maybe_type: str) -> None:
        if maybe_type == "not passed":
            type_string = ""
        else:
            type_string = f", {maybe_type}"

        testrunnerer.makeconftest(
            f"""
            def testrunner_addoption(parser):
                parser.addini("myname", "my new ini value"{type_string})
        """
        )
        testrunnerer.makeini(
            """
            [testrunner]
            myname=hello
        """
        )
        config = testrunnerer.parseconfig()
        val = config.getini("myname")
        assert val == "hello"
        with testrunner.raises(ValueError):
            config.getini("other")

    @testrunner.mark.parametrize("config_type", ["ini", "pyproject"])
    def test_addini_paths(self, testrunnerer: Testrunnerer, config_type: str) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("paths", "my new ini value", type="paths")
                parser.addini("abc", "abc value")
        """
        )
        if config_type == "ini":
            inipath = testrunnerer.makeini(
                """
                [testrunner]
                paths=hello world/sub.py
            """
            )
        elif config_type == "pyproject":
            inipath = testrunnerer.makepyprojecttoml(
                """
                [tool.testrunner.ini_options]
                paths=["hello", "world/sub.py"]
            """
            )
        config = testrunnerer.parseconfig()
        values = config.getini("paths")
        assert len(values) == 2
        assert values[0] == inipath.parent.joinpath("hello")
        assert values[1] == inipath.parent.joinpath("world/sub.py")
        with testrunner.raises(ValueError):
            config.getini("other")

    def make_conftest_for_args(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("args", "new args", type="args")
                parser.addini("a2", "", "args", default="1 2 3".split())
        """
        )

    def test_addini_args_ini_files(self, testrunnerer: Testrunnerer) -> None:
        self.make_conftest_for_args(testrunnerer)
        testrunnerer.makeini(
            """
            [testrunner]
            args=123 "123 hello" "this"
            """
        )
        self.check_config_args(testrunnerer)

    def test_addini_args_pyproject_toml(self, testrunnerer: Testrunnerer) -> None:
        self.make_conftest_for_args(testrunnerer)
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner.ini_options]
            args = ["123", "123 hello", "this"]
            """
        )
        self.check_config_args(testrunnerer)

    def check_config_args(self, testrunnerer: Testrunnerer) -> None:
        config = testrunnerer.parseconfig()
        values = config.getini("args")
        assert values == ["123", "123 hello", "this"]
        values = config.getini("a2")
        assert values == list("123")

    def make_conftest_for_linelist(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("xy", "", type="linelist")
                parser.addini("a2", "", "linelist")
        """
        )

    def test_addini_linelist_ini_files(self, testrunnerer: Testrunnerer) -> None:
        self.make_conftest_for_linelist(testrunnerer)
        testrunnerer.makeini(
            """
            [testrunner]
            xy= 123 345
                second line
        """
        )
        self.check_config_linelist(testrunnerer)

    def test_addini_linelist_pprojecttoml(self, testrunnerer: Testrunnerer) -> None:
        self.make_conftest_for_linelist(testrunnerer)
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner.ini_options]
            xy = ["123 345", "second line"]
        """
        )
        self.check_config_linelist(testrunnerer)

    def check_config_linelist(self, testrunnerer: Testrunnerer) -> None:
        config = testrunnerer.parseconfig()
        values = config.getini("xy")
        assert len(values) == 2
        assert values == ["123 345", "second line"]
        values = config.getini("a2")
        assert values == []

    @testrunner.mark.parametrize(
        "str_val, bool_val", [("True", True), ("no", False), ("no-ini", True)]
    )
    def test_addini_bool(
        self, testrunnerer: Testrunnerer, str_val: str, bool_val: bool
    ) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("strip", "", type="bool", default=True)
        """
        )
        if str_val != "no-ini":
            testrunnerer.makeini(
                f"""
                [testrunner]
                strip={str_val}
            """
            )
        config = testrunnerer.parseconfig()
        assert config.getini("strip") is bool_val

    @testrunner.mark.parametrize("str_val, int_val", [("10", 10), ("no-ini", 2)])
    def test_addini_int(
        self, testrunnerer: Testrunnerer, str_val: str, int_val: bool
    ) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("ini_param", "", type="int", default=2)
        """
        )
        if str_val != "no-ini":
            testrunnerer.makeini(
                f"""
                [testrunner]
                ini_param={str_val}
            """
            )
        config = testrunnerer.parseconfig()
        assert config.getini("ini_param") == int_val

    def test_addini_int_invalid(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("ini_param", "", type="int", default=2)
        """
        )
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner.ini_options]
            ini_param=["foo"]
            """
        )
        config = testrunnerer.parseconfig()
        with testrunner.raises(
            UsageError, match="Expected an int string for option ini_param"
        ):
            _ = config.getini("ini_param")

    @testrunner.mark.parametrize(
        "str_val, float_val", [("10.5", 10.5), ("no-ini", 2.2)]
    )
    def test_addini_float(
        self, testrunnerer: Testrunnerer, str_val: str, float_val: bool
    ) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("ini_param", "", type="float", default=2.2)
        """
        )
        if str_val != "no-ini":
            testrunnerer.makeini(
                f"""
                [testrunner]
                ini_param={str_val}
            """
            )
        config = testrunnerer.parseconfig()
        assert config.getini("ini_param") == float_val

    def test_addini_float_invalid(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("ini_param", "", type="float", default=2.2)
        """
        )
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner.ini_options]
            ini_param=["foo"]
            """
        )
        config = testrunnerer.parseconfig()
        with testrunner.raises(
            UsageError, match="Expected a float string for option ini_param"
        ):
            _ = config.getini("ini_param")

    def test_addini_string_non_str_deprecated(self, testrunnerer: Testrunnerer) -> None:
        """Passing a non-string value to a 'string'-typed ini option emits a
        deprecation warning. The value is still returned as-is for now, but will
        raise TypeError in testrunner 10."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("myname", "", type="string")
        """
        )
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner.ini_options]
            myname = ["value1", "value2"]
            """
        )
        config = testrunnerer.parseconfig()
        with testrunner.warns(
            testrunner.TestrunnerRemovedIn10Warning,
            match="Passing a value that is not a string to a 'string'-typed ini option",
        ):
            result = config.getini("myname")
        assert result == ["value1", "value2"]

    UNION_CONFTEST = """
        def testrunner_addoption(parser):
            parser.addini("ini_param", "", type=int | str, default=None)
    """

    LITERAL_CONFTEST = """
        from typing import Literal

        def testrunner_addoption(parser):
            parser.addini(
                "ini_param", "", type=Literal["auto", "long"], default="auto"
            )
    """

    @testrunner.mark.parametrize(
        "section, value, expected",
        [
            # Native TOML: int and str are both accepted; the first union
            # member that matches wins (int before str).
            ("[tool.testrunner]", '"7"', "7"),
            ("[tool.testrunner]", "7", 7),
            # ini_options mode stringifies, then coerces to the first member.
            ("[tool.testrunner.ini_options]", '"7"', 7),
            ("[tool.testrunner.ini_options]", "7", 7),
        ],
        ids=["native-str", "native-int", "ini-options-str", "ini-options-int"],
    )
    def test_addini_union_type(
        self, testrunnerer: Testrunnerer, section: str, value: str, expected: object
    ) -> None:
        testrunnerer.makeconftest(self.UNION_CONFTEST)
        testrunnerer.makepyprojecttoml(
            f"""
            {section}
            ini_param = {value}
            """
        )
        config = testrunnerer.parseconfig()
        result = config.getini("ini_param")
        assert result == expected
        assert type(result) is type(expected)

    def test_addini_union_type_invalid_value(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(self.UNION_CONFTEST)
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner]
            ini_param = [1, 2]
            """
        )
        config = testrunnerer.parseconfig()
        with testrunner.raises(
            UsageError, match=r"config option 'ini_param' expects one of int \| string"
        ):
            _ = config.getini("ini_param")

    def test_addini_plain_type(self, testrunnerer: Testrunnerer) -> None:
        """A plain Python type is accepted as an alias of its string tag."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("ini_param", "", type=int)
        """
        )
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner]
            ini_param = 7
            """
        )
        config = testrunnerer.parseconfig()
        assert config.getini("ini_param") == 7

    @testrunner.mark.parametrize("bad_type", ["integer", dict, int | dict])
    def test_addini_invalid_type(self, bad_type: object) -> None:
        parser = Parser(_istestrunner=True)
        with testrunner.raises(
            ValueError, match="invalid type for ini option 'ini_param'"
        ):
            parser.addini("ini_param", "", type=bad_type)  # type: ignore[arg-type]

    def test_addini_union_type_requires_default(self) -> None:
        parser = Parser(_istestrunner=True)
        with testrunner.raises(
            ValueError, match="union type, which has no implicit default"
        ):
            parser.addini("ini_param", "", type=int | str)

    @testrunner.mark.parametrize(
        "value, expected",
        [('"long"', "long"), (None, "auto")],
        ids=["value", "default"],
    )
    def test_addini_literal_type(
        self, testrunnerer: Testrunnerer, value: str | None, expected: str
    ) -> None:
        """A Literal of strings restricts the value to the given choices."""
        testrunnerer.makeconftest(self.LITERAL_CONFTEST)
        if value is not None:
            testrunnerer.makepyprojecttoml(f"[tool.testrunner]\nini_param = {value}")
        config = testrunnerer.parseconfig()
        assert config.getini("ini_param") == expected

    def test_addini_literal_type_ini_and_override(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makeconftest(self.LITERAL_CONFTEST)
        testrunnerer.makeini(
            """
            [testrunner]
            ini_param = long
        """
        )
        assert testrunnerer.parseconfig().getini("ini_param") == "long"
        assert (
            testrunnerer.parseconfig("-o", "ini_param=auto").getini("ini_param")
            == "auto"
        )

    @testrunner.mark.parametrize(
        "value, match",
        [
            ('"short"', r"expects one of 'auto' \| 'long', got 'short'"),
            ("5", r"expects a string, got int: 5"),
        ],
        ids=["bad-choice", "bad-type"],
    )
    def test_addini_literal_type_invalid_value(
        self, testrunnerer: Testrunnerer, value: str, match: str
    ) -> None:
        testrunnerer.makeconftest(self.LITERAL_CONFTEST)
        testrunnerer.makepyprojecttoml(f"[tool.testrunner]\nini_param = {value}")
        config = testrunnerer.parseconfig()
        with testrunner.raises(UsageError, match=f"config option 'ini_param' {match}"):
            _ = config.getini("ini_param")

    UNION_LITERAL_CONFTEST = """
        from typing import Literal

        def testrunner_addoption(parser):
            parser.addini(
                "ini_param", "", type=int | Literal["auto"], default="auto"
            )
    """

    @testrunner.mark.parametrize(
        "value, expected",
        [("3", 3), ('"auto"', "auto"), (None, "auto")],
        ids=["int", "literal", "default"],
    )
    def test_addini_union_with_literal_toml(
        self, testrunnerer: Testrunnerer, value: str | None, expected: object
    ) -> None:
        """A Literal of strings may be a union member, e.g. int | Literal["auto"]."""
        testrunnerer.makeconftest(self.UNION_LITERAL_CONFTEST)
        if value is not None:
            testrunnerer.makepyprojecttoml(f"[tool.testrunner]\nini_param = {value}")
        assert testrunnerer.parseconfig().getini("ini_param") == expected

    def test_addini_union_with_literal_ini_and_override(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makeconftest(self.UNION_LITERAL_CONFTEST)
        testrunnerer.makeini(
            """
            [testrunner]
            ini_param = 3
        """
        )
        assert testrunnerer.parseconfig().getini("ini_param") == 3
        assert (
            testrunnerer.parseconfig("-o", "ini_param=auto").getini("ini_param")
            == "auto"
        )

    def test_addini_union_with_literal_invalid_value(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makeconftest(self.UNION_LITERAL_CONFTEST)
        testrunnerer.makepyprojecttoml('[tool.testrunner]\nini_param = "3"')
        config = testrunnerer.parseconfig()
        with testrunner.raises(
            UsageError,
            match=r"config option 'ini_param' expects one of int \| 'auto', "
            r"got str: '3'",
        ):
            _ = config.getini("ini_param")

    def test_addini_union_with_literal_non_str_choice(self) -> None:
        parser = Parser(_istestrunner=True)
        with testrunner.raises(ValueError, match="Literal choices must be strings"):
            parser.addini("ini_param", "", type=str | Literal[1], default="")

    def test_addini_literal_type_requires_default(self) -> None:
        parser = Parser(_istestrunner=True)
        with testrunner.raises(
            ValueError, match="Literal type, which has no implicit default"
        ):
            parser.addini("ini_param", "", type=Literal["auto", "long"])

    def test_addini_literal_type_non_str_choice(self) -> None:
        parser = Parser(_istestrunner=True)
        with testrunner.raises(ValueError, match="Literal choices must be strings"):
            parser.addini("ini_param", "", type=Literal["auto", 1], default="auto")

    def test_addinivalue_line_existing(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("xy", "", type="linelist")
        """
        )
        testrunnerer.makeini(
            """
            [testrunner]
            xy= 123
        """
        )
        config = testrunnerer.parseconfig()
        values = config.getini("xy")
        assert len(values) == 1
        assert values == ["123"]
        config.addinivalue_line("xy", "456")
        values = config.getini("xy")
        assert len(values) == 2
        assert values == ["123", "456"]

    def test_addinivalue_line_new(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("xy", "", type="linelist")
        """
        )
        config = testrunnerer.parseconfig()
        assert not config.getini("xy")
        config.addinivalue_line("xy", "456")
        values = config.getini("xy")
        assert len(values) == 1
        assert values == ["456"]
        config.addinivalue_line("xy", "123")
        values = config.getini("xy")
        assert len(values) == 2
        assert values == ["456", "123"]

    def test_addini_default_values(self, testrunnerer: Testrunnerer) -> None:
        """Tests the default values for configuration based on
        config type
        """
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("linelist1", "", type="linelist")
                parser.addini("paths1", "", type="paths")
                parser.addini("pathlist1", "", type="pathlist")
                parser.addini("args1", "", type="args")
                parser.addini("bool1", "", type="bool")
                parser.addini("string1", "", type="string")
                parser.addini("none_1", "", type="linelist", default=None)
                parser.addini("none_2", "", default=None)
                parser.addini("no_type", "")
        """
        )

        config = testrunnerer.parseconfig()
        # default for linelist, paths, pathlist and args is []
        value = config.getini("linelist1")
        assert value == []
        value = config.getini("paths1")
        assert value == []
        value = config.getini("pathlist1")
        assert value == []
        value = config.getini("args1")
        assert value == []
        # default for bool is False
        value = config.getini("bool1")
        assert value is False
        # default for string is ""
        value = config.getini("string1")
        assert value == ""
        # should return None if None is explicitly set as default value
        # irrespective of the type argument
        value = config.getini("none_1")
        assert value is None
        value = config.getini("none_2")
        assert value is None
        # in case no type is provided and no default set
        # treat it as string and default value will be ""
        value = config.getini("no_type")
        assert value == ""

    def test_addini_with_aliases(self, testrunnerer: Testrunnerer) -> None:
        """Test that ini options can have aliases."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("new_name", "my option", aliases=["old_name"])
            """
        )
        testrunnerer.makeini(
            """
            [testrunner]
            old_name = hello
            """
        )
        config = testrunnerer.parseconfig()
        # Should be able to access via canonical name.
        assert config.getini("new_name") == "hello"
        # Should also be able to access via alias.
        assert config.getini("old_name") == "hello"

    def test_addini_aliases_with_canonical_in_file(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that canonical name takes precedence over alias in configuration file."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("new_name", "my option", aliases=["old_name"])
            """
        )
        testrunnerer.makeini(
            """
            [testrunner]
            old_name = from_alias
            new_name = from_canonical
            """
        )
        config = testrunnerer.parseconfig()
        # Canonical name should take precedence.
        assert config.getini("new_name") == "from_canonical"
        assert config.getini("old_name") == "from_canonical"

    def test_addini_aliases_multiple(self, testrunnerer: Testrunnerer) -> None:
        """Test that ini option can have multiple aliases."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("current_name", "my option", aliases=["old_name", "legacy_name"])
            """
        )
        testrunnerer.makeini(
            """
            [testrunner]
            old_name = value1
            """
        )
        config = testrunnerer.parseconfig()
        assert config.getini("current_name") == "value1"
        assert config.getini("old_name") == "value1"
        assert config.getini("legacy_name") == "value1"

    def test_addini_aliases_with_override_of_old(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that aliases work with --override-ini -- ini sets old."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("new_name", "my option", aliases=["old_name"])
            """
        )
        testrunnerer.makeini(
            """
            [testrunner]
            old_name = from_file
            """
        )
        # Override using alias.
        config = testrunnerer.parseconfig("-o", "old_name=overridden")
        assert config.getini("new_name") == "overridden"
        assert config.getini("old_name") == "overridden"

        # Override using canonical name.
        config = testrunnerer.parseconfig("-o", "new_name=overridden2")
        assert config.getini("new_name") == "overridden2"

    def test_addini_aliases_with_override_of_new(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that aliases work with --override-ini -- ini sets new."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("new_name", "my option", aliases=["old_name"])
            """
        )
        testrunnerer.makeini(
            """
            [testrunner]
            new_name = from_file
            """
        )
        # Override using alias.
        config = testrunnerer.parseconfig("-o", "old_name=overridden")
        assert config.getini("new_name") == "overridden"
        assert config.getini("old_name") == "overridden"

        # Override using canonical name.
        config = testrunnerer.parseconfig("-o", "new_name=overridden2")
        assert config.getini("new_name") == "overridden2"

    def test_addini_aliases_with_types(self, testrunnerer: Testrunnerer) -> None:
        """Test that aliases work with different types."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("mylist", "list option", type="linelist", aliases=["oldlist"])
                parser.addini("mybool", "bool option", type="bool", aliases=["oldbool"])
            """
        )
        testrunnerer.makeini(
            """
            [testrunner]
            oldlist = line1
                line2
            oldbool = true
        """
        )
        config = testrunnerer.parseconfig()
        assert config.getini("mylist") == ["line1", "line2"]
        assert config.getini("oldlist") == ["line1", "line2"]
        assert config.getini("mybool") is True
        assert config.getini("oldbool") is True

    def test_addini_aliases_conflict_error(self, testrunnerer: Testrunnerer) -> None:
        """Test that registering an alias that conflicts with an existing option raises an error."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("existing", "first option")

                try:
                    parser.addini("new_option", "second option", aliases=["existing"])
                except ValueError as e:
                    assert "alias 'existing' conflicts with existing configuration option" in str(e)
                else:
                    assert False, "Should have raised ValueError"
            """
        )
        testrunnerer.parseconfig()

    def test_addini_aliases_duplicate_error(self, testrunnerer: Testrunnerer) -> None:
        """Test that registering the same alias twice raises an error."""
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("option1", "first option", aliases=["shared_alias"])
                try:
                    parser.addini("option2", "second option", aliases=["shared_alias"])
                    raise AssertionError("Should have raised ValueError")
                except ValueError as e:
                    assert "'shared_alias' is already an alias of 'option1'" in str(e)
            """
        )
        testrunnerer.parseconfig()

    @testrunner.mark.parametrize(
        "type, expected",
        [
            testrunner.param(None, "", id="None"),
            testrunner.param("string", "", id="string"),
            testrunner.param("paths", [], id="paths"),
            testrunner.param("pathlist", [], id="pathlist"),
            testrunner.param("args", [], id="args"),
            testrunner.param("linelist", [], id="linelist"),
            testrunner.param("bool", False, id="bool"),
        ],
    )
    def test_get_ini_default_for_type(self, type: Any, expected: Any) -> None:
        assert get_ini_default_for_type(type) == expected

    def test_confcutdir_check_isdir(self, testrunnerer: Testrunnerer) -> None:
        """Give an error if --confcutdir is not a valid directory (#2078)"""
        exp_match = r"^--confcutdir must be a directory, given: "
        with testrunner.raises(testrunner.UsageError, match=exp_match):
            testrunnerer.parseconfig("--confcutdir", testrunnerer.path.joinpath("file"))
        with testrunner.raises(testrunner.UsageError, match=exp_match):
            testrunnerer.parseconfig(
                "--confcutdir", testrunnerer.path.joinpath("nonexistent")
            )

        p = testrunnerer.mkdir("dir")
        config = testrunnerer.parseconfig("--confcutdir", p)
        assert config.getoption("confcutdir") == str(p)

    @testrunner.mark.parametrize(
        "names, expected",
        [
            # dist-info based distributions root are files as will be put in PYTHONPATH
            (["bar.py"], ["bar"]),
            (["foo/bar.py"], ["bar"]),
            (["foo/bar.pyc"], []),
            (["foo/__init__.py"], ["foo"]),
            (["bar/__init__.py", "xz.py"], ["bar", "xz"]),
            (["setup.py"], []),
            # egg based distributions root contain the files from the dist root
            (["src/bar/__init__.py"], ["bar"]),
            (["src/bar/__init__.py", "setup.py"], ["bar"]),
            (["source/python/bar/__init__.py", "setup.py"], ["bar"]),
            # editable installation finder modules
            (["__editable___xyz_finder.py"], []),
            (["bar/__init__.py", "__editable___xyz_finder.py"], ["bar"]),
        ],
    )
    def test_iter_rewritable_modules(self, names, expected) -> None:
        assert list(_iter_rewritable_modules(names)) == expected

    def test_add_cleanup(self, testrunnerer: Testrunnerer) -> None:
        config = Config.fromdictargs({}, [])
        config._do_configure()
        report = []

        class MyError(BaseException):
            pass

        @config.add_cleanup
        def cleanup_last():
            report.append("cleanup_last")

        @config.add_cleanup
        def raise_2():
            report.append("raise_2")
            raise MyError("raise_2")

        @config.add_cleanup
        def raise_1():
            report.append("raise_1")
            raise MyError("raise_1")

        @config.add_cleanup
        def cleanup_first():
            report.append("cleanup_first")

        with testrunner.raises(MyError, match=r"raise_2"):
            config._ensure_unconfigure()

        assert report == ["cleanup_first", "raise_1", "raise_2", "cleanup_last"]


class TestConfigFromdictargs:
    def test_basic_behavior(self, _sys_snapshot) -> None:
        option_dict = {"verbose": 444, "foo": "bar", "capture": "no"}
        args = ["a", "b"]

        config = Config.fromdictargs(option_dict, args)
        with testrunner.raises(AssertionError):
            config.parse(["should refuse to parse again"])
        assert config.option.verbose == 444
        assert config.option.foo == "bar"
        assert config.option.capture == "no"
        assert config.args == args

    def test_invocation_params_args(self, _sys_snapshot) -> None:
        """Show that fromdictargs can handle args in their "orig" format"""
        option_dict: dict[str, object] = {}
        args = ["-vvvv", "-s", "a", "b"]

        config = Config.fromdictargs(option_dict, args)
        assert config.args == ["a", "b"]
        assert config.invocation_params.args == tuple(args)
        assert config.option.verbose == 4
        assert config.option.capture == "no"

    def test_inifilename(self, tmp_path: Path) -> None:
        d1 = tmp_path.joinpath("foo")
        d1.mkdir()
        p1 = d1.joinpath("bar.ini")
        p1.touch()
        p1.write_text(
            textwrap.dedent(
                """\
                [testrunner]
                name = value
                """
            ),
            encoding="utf-8",
        )

        inifilename = "../../foo/bar.ini"
        option_dict = {"inifilename": inifilename, "capture": "no"}

        cwd = tmp_path.joinpath("a/b")
        cwd.mkdir(parents=True)
        p2 = cwd.joinpath("testrunner.ini")
        p2.touch()
        p2.write_text(
            textwrap.dedent(
                """\
                [testrunner]
                name = wrong-value
                should_not_be_set = true
                """
            ),
            encoding="utf-8",
        )
        with MonkeyPatch.context() as mp:
            mp.chdir(cwd)
            config = Config.fromdictargs(option_dict, [])
            inipath = absolutepath(inifilename)

        assert config.args == [str(cwd)]
        assert config.option.inifilename == inifilename
        assert config.option.capture == "no"

        # this indicates this is the file used for getting configuration values
        assert config.inipath == inipath
        assert config._inicfg.get("name") == ConfigValue(
            "value", origin="file", mode="ini"
        )
        assert config._inicfg.get("should_not_be_set") is None


def test_options_on_small_file_do_not_blow_up(testrunnerer: Testrunnerer) -> None:
    def runfiletest(opts: Sequence[str]) -> None:
        reprec = testrunnerer.inline_run(*opts)
        passed, skipped, failed = reprec.countoutcomes()
        assert failed == 2
        assert skipped == passed == 0

    path = str(
        testrunnerer.makepyfile(
            """
        def test_f1(): assert 0
        def test_f2(): assert 0
    """
        )
    )

    runfiletest([path])
    runfiletest(["-l", path])
    runfiletest(["-s", path])
    runfiletest(["--tb=no", path])
    runfiletest(["--tb=short", path])
    runfiletest(["--tb=long", path])
    runfiletest(["--fulltrace", path])
    runfiletest(["--traceconfig", path])
    runfiletest(["-v", path])
    runfiletest(["-v", "-v", path])


def test_preparse_ordering_with_setuptools(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", raising=False)

    class EntryPoint:
        name = "mytestplugin"
        group = "testrunner11"

        def load(self):
            class PseudoPlugin:
                x = 42

            return PseudoPlugin()

    class Dist:
        files = ()
        metadata = {"name": "foo"}
        entry_points = (EntryPoint(),)

    def my_dists():
        return (Dist,)

    monkeypatch.setattr(importlib.metadata, "distributions", my_dists)
    testrunnerer.makeconftest(
        """
        testrunner_plugins = "mytestplugin",
    """
    )
    monkeypatch.setenv("TESTRUNNER_PLUGINS", "mytestplugin")
    config = testrunnerer.parseconfig()
    plugin = config.pluginmanager.getplugin("mytestplugin")
    assert plugin.x == 42


def test_setuptools_importerror_issue1479(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", raising=False)

    class DummyEntryPoint:
        name = "mytestplugin"
        group = "testrunner11"

        def load(self):
            raise ImportError("Don't hide me!")

    class Distribution:
        version = "1.0"
        files = ("foo.txt",)
        metadata = {"name": "foo"}
        entry_points = (DummyEntryPoint(),)

    def distributions():
        return (Distribution(),)

    monkeypatch.setattr(importlib.metadata, "distributions", distributions)
    with testrunner.raises(PluginImportFailure) as excinfo:
        testrunnerer.parseconfig()
    assert "Don't hide me!" in str(excinfo.value.__cause__)


def test_setuptools_usage_error_passes_through(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    """A UsageError from an entry-point plugin is not reclassified (#993)."""
    monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", raising=False)

    class DummyEntryPoint:
        name = "mytestplugin"
        group = "testrunner11"

        def load(self):
            raise UsageError("bad usage")

    class Distribution:
        version = "1.0"
        files = ("foo.txt",)
        metadata = {"name": "foo"}
        entry_points = (DummyEntryPoint(),)

    def distributions():
        return (Distribution(),)

    monkeypatch.setattr(importlib.metadata, "distributions", distributions)
    with testrunner.raises(UsageError, match="bad usage"):
        testrunnerer.parseconfig()


def test_importlib_metadata_broken_distribution(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch
) -> None:
    """Integration test for broken distributions with 'files' metadata being None (#5389)"""
    monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", raising=False)

    class DummyEntryPoint:
        name = "mytestplugin"
        group = "testrunner11"

        def load(self):
            return object()

    class Distribution:
        version = "1.0"
        files = None
        metadata = {"name": "foo"}
        entry_points = (DummyEntryPoint(),)

    def distributions():
        return (Distribution(),)

    monkeypatch.setattr(importlib.metadata, "distributions", distributions)
    testrunnerer.parseconfig()


@testrunner.mark.parametrize("block_it", [True, False])
def test_plugin_preparse_prevents_setuptools_loading(
    testrunnerer: Testrunnerer, monkeypatch: MonkeyPatch, block_it: bool
) -> None:
    monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", raising=False)

    plugin_module_placeholder = object()

    class DummyEntryPoint:
        name = "mytestplugin"
        group = "testrunner11"

        def load(self):
            return plugin_module_placeholder

    class Distribution:
        version = "1.0"
        files = ("foo.txt",)
        metadata = {"name": "foo"}
        entry_points = (DummyEntryPoint(),)

    def distributions():
        return (Distribution(),)

    monkeypatch.setattr(importlib.metadata, "distributions", distributions)
    args = ("-p", "no:mytestplugin") if block_it else ()
    config = testrunnerer.parseconfig(*args)
    config.pluginmanager.import_plugin("mytestplugin")
    if block_it:
        assert "mytestplugin" not in sys.modules
        assert config.pluginmanager.get_plugin("mytestplugin") is None
    else:
        assert (
            config.pluginmanager.get_plugin("mytestplugin") is plugin_module_placeholder
        )


@testrunner.mark.parametrize("disable_plugin_method", ["env_var", "flag", ""])
@testrunner.mark.parametrize("enable_plugin_method", ["env_var", "flag", ""])
def test_disable_plugin_autoload(
    testrunnerer: Testrunnerer,
    monkeypatch: MonkeyPatch,
    enable_plugin_method: str,
    disable_plugin_method: str,
) -> None:
    class DummyEntryPoint:
        project_name = name = "mytestplugin"
        group = "testrunner11"
        version = "1.0"

        def load(self):
            return sys.modules[self.name]

    class Distribution:
        metadata = {"name": "foo"}
        entry_points = (DummyEntryPoint(),)
        files = ()

    class PseudoPlugin:
        x = 42

        attrs_used = []

        def __getattr__(self, name):
            assert name in ("__loader__", "__spec__")
            self.attrs_used.append(name)
            return object()

    def distributions():
        return (Distribution(),)

    parse_args: list[str] = []

    if disable_plugin_method == "env_var":
        monkeypatch.setenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD", "1")
    elif disable_plugin_method == "flag":
        monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD")
        parse_args.append("--disable-plugin-autoload")
    else:
        assert disable_plugin_method == ""
        monkeypatch.delenv("TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD")

    if enable_plugin_method == "env_var":
        monkeypatch.setenv("TESTRUNNER_PLUGINS", "mytestplugin")
    elif enable_plugin_method == "flag":
        parse_args.extend(["-p", "mytestplugin"])
    else:
        assert enable_plugin_method == ""

    monkeypatch.setattr(importlib.metadata, "distributions", distributions)
    monkeypatch.setitem(sys.modules, "mytestplugin", PseudoPlugin())
    config = testrunnerer.parseconfig(*parse_args)

    has_loaded = config.pluginmanager.get_plugin("mytestplugin") is not None
    # it should load if it's enabled, or we haven't disabled autoloading
    assert has_loaded == (bool(enable_plugin_method) or not disable_plugin_method)

    # The reason for the discrepancy between 'has_loaded' and __loader__ being accessed
    # appears to be the monkeypatching of importlib.metadata.distributions; where
    # files being empty means that _mark_plugins_for_rewrite doesn't find the plugin.
    # But enable_method==flag ends up in mark_rewrite being called and __loader__
    # being accessed.
    assert ("__loader__" in PseudoPlugin.attrs_used) == (
        has_loaded
        and not (enable_plugin_method in ("env_var", "") and not disable_plugin_method)
    )

    # __spec__ is accessed in AssertionRewritingHook.exec_module, which is never
    # reached here: since TESTRUNNER_PLUGINS also considers entry points (#12624),
    # the plugin is loaded through its entry point (like with -p) instead of
    # being imported through the rewrite hook.
    assert "__spec__" not in PseudoPlugin.attrs_used


def test_plugin_loading_order(testrunnerer: Testrunnerer) -> None:
    """Test order of plugin loading with `-p`."""
    p1 = testrunnerer.makepyfile(
        """
        def test_terminal_plugin(request):
            import myplugin
            assert myplugin.terminal_plugin == [False, True]
        """,
        myplugin="""
            terminal_plugin = []

            def testrunner_configure(config):
                terminal_plugin.append(bool(config.pluginmanager.get_plugin("terminalreporter")))

            def testrunner_sessionstart(session):
                config = session.config
                terminal_plugin.append(bool(config.pluginmanager.get_plugin("terminalreporter")))
            """,
    )
    testrunnerer.syspathinsert()
    result = testrunnerer.runtestrunner("-p", "myplugin", str(p1))
    assert result.ret == 0


def test_invalid_options_show_extra_information(testrunnerer: Testrunnerer) -> None:
    """Display extra information when testrunner exits due to unrecognized
    options in the command-line."""
    testrunnerer.makeini(
        """
        [testrunner]
        addopts = --invalid-option
    """
    )
    result = testrunnerer.runtestrunner()
    result.stderr.fnmatch_lines(
        [
            "*error: unrecognized arguments: --invalid-option*",
            "*  inifile: {}*".format(testrunnerer.path.joinpath("tox.ini")),
            f"*  rootdir: {testrunnerer.path}*",
        ]
    )


@testrunner.mark.parametrize(
    "args",
    [
        ["dir1", "dir2", "-v"],
        ["dir1", "-v", "dir2"],
        ["dir2", "-v", "dir1"],
        ["-v", "dir2", "dir1"],
    ],
)
def test_consider_args_after_options_for_rootdir(
    testrunnerer: Testrunnerer, args: list[str]
) -> None:
    """
    Consider all arguments in the command-line for rootdir
    discovery, even if they happen to occur after an option. #949
    """
    # replace "dir1" and "dir2" from "args" into their real directory
    root = testrunnerer.mkdir("myroot")
    d1 = root.joinpath("dir1")
    d1.mkdir()
    d2 = root.joinpath("dir2")
    d2.mkdir()
    for i, arg in enumerate(args):
        if arg == "dir1":
            args[i] = str(d1)
        elif arg == "dir2":
            args[i] = str(d2)
    with MonkeyPatch.context() as mp:
        mp.chdir(root)
        result = testrunnerer.runtestrunner(*args)
    result.stdout.fnmatch_lines(["*rootdir: *myroot"])


def test_toolongargs_issue224(testrunnerer: Testrunnerer) -> None:
    result = testrunnerer.runtestrunner("-m", "hello" * 500)
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_config_in_subdirectory_colon_command_line_issue2148(
    testrunnerer: Testrunnerer,
) -> None:
    conftest_source = """
        def testrunner_addoption(parser):
            parser.addini('foo', 'foo')
    """

    testrunnerer.makefile(
        ".ini",
        **{
            "testrunner": "[testrunner]\nfoo = root",
            "subdir/testrunner": "[testrunner]\nfoo = subdir",
        },
    )

    testrunnerer.makepyfile(
        **{
            "conftest": conftest_source,
            "subdir/conftest": conftest_source,
            "subdir/test_foo": """\
            def test_foo(testrunnerconfig):
                assert testrunnerconfig.getini('foo') == 'subdir'
            """,
        }
    )

    result = testrunnerer.runtestrunner("subdir/test_foo.py::test_foo")
    assert result.ret == 0


def test_notify_exception(testrunnerer: Testrunnerer, capfd) -> None:
    config = testrunnerer.parseconfig()
    with testrunner.raises(ValueError) as excinfo:
        raise ValueError(1)
    config.notify_exception(excinfo, config.option)
    _, err = capfd.readouterr()
    assert "ValueError" in err

    class A:
        def testrunner_internalerror(self):
            return True

    config.pluginmanager.register(A())
    config.notify_exception(excinfo, config.option)
    _, err = capfd.readouterr()
    assert not err

    config = testrunnerer.parseconfig("-p", "no:terminal")
    with testrunner.raises(ValueError) as excinfo:
        raise ValueError(1)
    config.notify_exception(excinfo, config.option)
    _, err = capfd.readouterr()
    assert "ValueError" in err


def test_no_terminal_discovery_error(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makepyfile("raise TypeError('oops!')")
    result = testrunnerer.runtestrunner("-p", "no:terminal", "--collect-only")
    assert result.ret == ExitCode.INTERRUPTED


def test_load_initial_conftest_last_ordering(_config_for_test):
    pm = _config_for_test.pluginmanager

    class My:
        def testrunner_load_initial_conftests(self):
            pass

    m = My()
    pm.register(m)
    hc = pm.hook.testrunner_load_initial_conftests
    hookimpls = [
        (
            hookimpl.function.__module__,
            "wrapper" if (hookimpl.wrapper or hookimpl.hookwrapper) else "nonwrapper",
        )
        for hookimpl in hc.get_hookimpls()
    ]
    assert hookimpls == [
        ("_testrunner.config", "nonwrapper"),
        (m.__module__, "nonwrapper"),
        ("_testrunner.legacypath", "nonwrapper"),
        ("_testrunner.capture", "wrapper"),
        ("_testrunner.warnings", "wrapper"),
    ]


def test_get_plugin_specs_as_list() -> None:
    def exp_match(val: object) -> str:
        return (
            f"Plugins may be specified as a sequence or a ','-separated string "
            f"of plugin names. Got: {re.escape(repr(val))}"
        )

    with testrunner.raises(testrunner.UsageError, match=exp_match({"foo"})):
        _get_plugin_specs_as_list({"foo"})  # type: ignore[arg-type]
    with testrunner.raises(testrunner.UsageError, match=exp_match({})):
        _get_plugin_specs_as_list(dict())  # type: ignore[arg-type]

    assert _get_plugin_specs_as_list(None) == []
    assert _get_plugin_specs_as_list("") == []
    assert _get_plugin_specs_as_list("foo") == ["foo"]
    assert _get_plugin_specs_as_list("foo,bar") == ["foo", "bar"]
    assert _get_plugin_specs_as_list(["foo", "bar"]) == ["foo", "bar"]
    assert _get_plugin_specs_as_list(("foo", "bar")) == ["foo", "bar"]


def test_collect_testrunner_prefix_bug_integration(testrunnerer: Testrunnerer) -> None:
    """Integration test for issue #3775"""
    p = testrunnerer.copy_example("config/collect_testrunner_prefix")
    result = testrunnerer.runtestrunner(p)
    result.stdout.fnmatch_lines(["* 1 passed *"])


def test_collect_testrunner_prefix_bug(testrunnerconfig):
    """Ensure we collect only actual functions from conftest files (#3775)"""

    class Dummy:
        class testrunner_something:
            pass

    pm = testrunnerconfig.pluginmanager
    assert pm.parse_hookimpl_opts(Dummy(), "testrunner_something") is None


class TestRootdir:
    def test_simple_noini(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        assert get_common_ancestor(Path.cwd(), [tmp_path]) == tmp_path
        a = tmp_path / "a"
        a.mkdir()
        assert get_common_ancestor(Path.cwd(), [a, tmp_path]) == tmp_path
        assert get_common_ancestor(Path.cwd(), [tmp_path, a]) == tmp_path
        monkeypatch.chdir(tmp_path)
        assert get_common_ancestor(Path.cwd(), []) == tmp_path
        no_path = tmp_path / "does-not-exist"
        assert get_common_ancestor(Path.cwd(), [no_path]) == tmp_path
        assert get_common_ancestor(Path.cwd(), [no_path / "a"]) == tmp_path

    @testrunner.mark.parametrize(
        "name, contents",
        [
            testrunner.param(
                "testrunner.ini", "[testrunner]\nx=10", id="testrunner.ini"
            ),
            testrunner.param(
                "pyproject.toml",
                "[tool.testrunner.ini_options]\nx=10",
                id="pyproject.toml",
            ),
            testrunner.param("tox.ini", "[testrunner]\nx=10", id="tox.ini"),
            testrunner.param("setup.cfg", "[tool:testrunner]\nx=10", id="setup.cfg"),
        ],
    )
    def test_with_ini(self, tmp_path: Path, name: str, contents: str) -> None:
        inipath = tmp_path / name
        inipath.write_text(contents, encoding="utf-8")

        a = tmp_path / "a"
        a.mkdir()
        b = a / "b"
        b.mkdir()
        for args in ([str(tmp_path)], [str(a)], [str(b)]):
            rootpath, parsed_inipath, *_ = determine_setup(
                inifile=None,
                override_ini=None,
                args=args,
                rootdir_cmd_arg=None,
                invocation_dir=Path.cwd(),
            )
            assert rootpath == tmp_path
            assert parsed_inipath == inipath
        rootpath, parsed_inipath, ini_config, _ = determine_setup(
            inifile=None,
            override_ini=None,
            args=[str(b), str(a)],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert parsed_inipath == inipath
        assert ini_config["x"] == ConfigValue("10", origin="file", mode="ini")

    @testrunner.mark.parametrize(
        "testrunner_ini", ["testrunner.ini", ".testrunner.ini"]
    )
    @testrunner.mark.parametrize("other", ["setup.cfg", "tox.ini"])
    def test_testrunnerini_overrides_empty_other(
        self, tmp_path: Path, testrunner_ini: str, other: str
    ) -> None:
        inipath = tmp_path / testrunner_ini
        inipath.touch()
        a = tmp_path / "a"
        a.mkdir()
        (a / other).touch()
        rootpath, parsed_inipath, *_ = determine_setup(
            inifile=None,
            override_ini=None,
            args=[str(a)],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert parsed_inipath == inipath

    def test_setuppy_fallback(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        a.mkdir()
        (a / "setup.cfg").touch()
        (tmp_path / "setup.py").touch()
        rootpath, inipath, inicfg, _ = determine_setup(
            inifile=None,
            override_ini=None,
            args=[str(a)],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert inipath is None
        assert inicfg == {}

    def test_nothing(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        rootpath, inipath, inicfg, _ = determine_setup(
            inifile=None,
            override_ini=None,
            args=[str(tmp_path)],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert inipath is None
        assert inicfg == {}

    @testrunner.mark.parametrize(
        "name, contents",
        [
            # testrunner.param("testrunner.ini", "[testrunner]\nx=10", id="testrunner.ini"),
            testrunner.param(
                "pyproject.toml",
                "[tool.testrunner.ini_options]\nx=10",
                id="pyproject.toml",
            ),
            # testrunner.param("tox.ini", "[testrunner]\nx=10", id="tox.ini"),
            # testrunner.param("setup.cfg", "[tool:testrunner]\nx=10", id="setup.cfg"),
        ],
    )
    def test_with_specific_inifile(
        self, tmp_path: Path, name: str, contents: str
    ) -> None:
        p = tmp_path / name
        p.touch()
        p.write_text(contents, encoding="utf-8")
        rootpath, inipath, ini_config, _ = determine_setup(
            inifile=str(p),
            override_ini=None,
            args=[str(tmp_path)],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert inipath == p
        assert ini_config["x"] == ConfigValue("10", origin="file", mode="ini")

    def test_explicit_config_file_sets_rootdir(
        self, tmp_path: Path, monkeypatch: testrunner.MonkeyPatch
    ) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        monkeypatch.chdir(tmp_path)

        # No config file is explicitly given: rootdir is determined to be cwd.
        rootpath, found_inipath, *_ = determine_setup(
            inifile=None,
            override_ini=None,
            args=[str(tests_dir)],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert found_inipath is None

        # Config file is explicitly given: rootdir is determined to be inifile's directory.
        inipath = tmp_path / "testrunner.ini"
        inipath.touch()
        rootpath, found_inipath, *_ = determine_setup(
            inifile=str(inipath),
            override_ini=None,
            args=[str(tests_dir)],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert found_inipath == inipath

    @testrunner.mark.skipif(
        sys.platform.startswith("win32"), reason="requires a POSIX null device"
    )
    def test_non_regular_config_file_with_unrelated_args(self, tmp_path: Path) -> None:
        """A non-regular config file plus rootless args falls back to the invocation dir."""
        rootpath, *_ = determine_setup(
            inifile=os.devnull,
            override_ini=None,
            args=[tmp_path.anchor],
            rootdir_cmd_arg=None,
            invocation_dir=tmp_path,
        )
        assert rootpath == tmp_path

    @testrunner.mark.skipif(
        sys.platform.startswith("win32"), reason="requires a POSIX null device"
    )
    def test_non_regular_config_file_honours_explicit_rootdir(
        self, tmp_path: Path
    ) -> None:
        """``--rootdir`` still wins when the config file is not a regular file."""
        explicit = tmp_path / "explicit"
        explicit.mkdir()

        rootpath, *_ = determine_setup(
            inifile=os.devnull,
            override_ini=None,
            args=[str(tmp_path)],
            rootdir_cmd_arg=str(explicit),
            invocation_dir=tmp_path,
        )
        assert rootpath == explicit

    def test_with_arg_outside_cwd_without_inifile(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        a = tmp_path / "a"
        a.mkdir()
        b = tmp_path / "b"
        b.mkdir()
        rootpath, inifile, *_ = determine_setup(
            inifile=None,
            override_ini=None,
            args=[str(a), str(b)],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert inifile is None

    def test_with_arg_outside_cwd_with_inifile(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        a.mkdir()
        b = tmp_path / "b"
        b.mkdir()
        inipath = a / "testrunner.ini"
        inipath.touch()
        rootpath, parsed_inipath, *_ = determine_setup(
            inifile=None,
            override_ini=None,
            args=[str(a), str(b)],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == a
        assert inipath == parsed_inipath

    @testrunner.mark.parametrize("dirs", ([], ["does-not-exist"], ["a/does-not-exist"]))
    def test_with_non_dir_arg(
        self, dirs: Sequence[str], tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        rootpath, inipath, *_ = determine_setup(
            inifile=None,
            override_ini=None,
            args=dirs,
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert inipath is None

    def test_with_existing_file_in_subdir(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        a = tmp_path / "a"
        a.mkdir()
        (a / "exists").touch()
        monkeypatch.chdir(tmp_path)
        rootpath, inipath, *_ = determine_setup(
            inifile=None,
            override_ini=None,
            args=["a/exist"],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )
        assert rootpath == tmp_path
        assert inipath is None

    def test_with_config_also_in_parent_directory(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Regression test for #7807."""
        (tmp_path / "setup.cfg").write_text("[tool:testrunner]\n", "utf-8")
        (tmp_path / "myproject").mkdir()
        (tmp_path / "myproject" / "setup.cfg").write_text(
            "[tool:testrunner]\n", "utf-8"
        )
        (tmp_path / "myproject" / "tests").mkdir()
        monkeypatch.chdir(tmp_path / "myproject")

        rootpath, inipath, *_ = determine_setup(
            inifile=None,
            override_ini=None,
            args=["tests/"],
            rootdir_cmd_arg=None,
            invocation_dir=Path.cwd(),
        )

        assert rootpath == tmp_path / "myproject"
        assert inipath == tmp_path / "myproject" / "setup.cfg"


class TestOverrideIniArgs:
    @testrunner.mark.parametrize("name", ["setup.cfg", "tox.ini", "testrunner.ini"])
    def test_override_ini_names(self, testrunnerer: Testrunnerer, name: str) -> None:
        section = "[testrunner]" if name != "setup.cfg" else "[tool:testrunner]"
        testrunnerer.path.joinpath(name).write_text(
            textwrap.dedent(
                f"""
            {section}
            custom = 1.0"""
            ),
            encoding="utf-8",
        )
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("custom", "")"""
        )
        testrunnerer.makepyfile(
            """
            def test_pass(testrunnerconfig):
                ini_val = testrunnerconfig.getini("custom")
                print('\\ncustom_option:%s\\n' % ini_val)"""
        )

        result = testrunnerer.runtestrunner("--override-ini", "custom=2.0", "-s")
        assert result.ret == 0
        result.stdout.fnmatch_lines(["custom_option:2.0"])

        result = testrunnerer.runtestrunner(
            "--override-ini", "custom=2.0", "--override-ini=custom=3.0", "-s"
        )
        assert result.ret == 0
        result.stdout.fnmatch_lines(["custom_option:3.0"])

    def test_override_ini_paths(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("paths", "my new ini value", type="paths")"""
        )
        testrunnerer.makeini(
            """
            [testrunner]
            paths=blah.py"""
        )
        testrunnerer.makepyfile(
            r"""
            def test_overridden(testrunnerconfig):
                config_paths = testrunnerconfig.getini("paths")
                print(config_paths)
                for cpf in config_paths:
                    print('\nuser_path:%s' % cpf.name)
            """
        )
        result = testrunnerer.runtestrunner(
            "--override-ini", "paths=foo/bar1.py foo/bar2.py", "-s"
        )
        result.stdout.fnmatch_lines(["user_path:bar1.py", "user_path:bar2.py"])

    def test_override_multiple_and_default(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                addini = parser.addini
                addini("custom_option_1", "", default="o1")
                addini("custom_option_2", "", default="o2")
                addini("custom_option_3", "", default=False, type="bool")
                addini("custom_option_4", "", default=True, type="bool")"""
        )
        testrunnerer.makeini(
            """
            [testrunner]
            custom_option_1=custom_option_1
            custom_option_2=custom_option_2
        """
        )
        testrunnerer.makepyfile(
            """
            def test_multiple_options(testrunnerconfig):
                prefix = "custom_option"
                for x in range(1, 5):
                    ini_value=testrunnerconfig.getini("%s_%d" % (prefix, x))
                    print('\\nini%d:%s' % (x, ini_value))
        """
        )
        result = testrunnerer.runtestrunner(
            "--override-ini",
            "custom_option_1=fulldir=/tmp/user1",
            "-o",
            "custom_option_2=url=/tmp/user2?a=b&d=e",
            "-o",
            "custom_option_3=True",
            "-o",
            "custom_option_4=no",
            "-s",
        )
        result.stdout.fnmatch_lines(
            [
                "ini1:fulldir=/tmp/user1",
                "ini2:url=/tmp/user2?a=b&d=e",
                "ini3:True",
                "ini4:False",
            ]
        )

    def test_override_ini_usage_error_bad_style(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makeini(
            """
            [testrunner]
            xdist_strict=False
        """
        )
        result = testrunnerer.runtestrunner("--override-ini", "xdist_strict", "True")
        result.stderr.fnmatch_lines(
            [
                "ERROR: -o/--override-ini expects option=value style (got: 'xdist_strict').",
            ]
        )

    @testrunner.mark.parametrize("with_ini", [True, False])
    def test_override_ini_handled_asap(
        self, testrunnerer: Testrunnerer, with_ini: bool
    ) -> None:
        """-o should be handled as soon as possible and always override what's in config files (#2238)"""
        if with_ini:
            testrunnerer.makeini(
                """
                [testrunner]
                python_files=test_*.py
            """
            )
        testrunnerer.makepyfile(
            unittest_ini_handle="""
            def test():
                pass
        """
        )
        result = testrunnerer.runtestrunner(
            "--override-ini", "python_files=unittest_*.py"
        )
        result.stdout.fnmatch_lines(["*1 passed in*"])

    def test_addopts_before_initini(
        self, monkeypatch: MonkeyPatch, _config_for_test, _sys_snapshot
    ) -> None:
        cache_dir = ".custom_cache"
        monkeypatch.setenv("TESTRUNNER_ADDOPTS", f"-o cache_dir={cache_dir}")
        config = _config_for_test
        config.parse([], addopts=True)
        assert config._inicfg.get("cache_dir") == ConfigValue(
            cache_dir, origin="override", mode="ini"
        )

    def test_addopts_from_env_not_concatenated(
        self, monkeypatch: MonkeyPatch, _config_for_test
    ) -> None:
        """TESTRUNNER_ADDOPTS should not take values from normal args (#4265)."""
        monkeypatch.setenv("TESTRUNNER_ADDOPTS", "-o")
        config = _config_for_test
        with testrunner.raises(UsageError) as excinfo:
            config.parse(["cache_dir=ignored"], addopts=True)
        assert (
            "error: argument -o/--override-ini: expected one argument"
            in excinfo.value.args[0]
        )
        assert "via TESTRUNNER_ADDOPTS" in excinfo.value.args[0]

    def test_addopts_from_ini_not_concatenated(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """`addopts` from configuration should not take values from normal args (#4265)."""
        testrunnerer.makeini(
            """
            [testrunner]
            addopts=-o
        """
        )
        result = testrunnerer.runtestrunner("cache_dir=ignored")
        result.stderr.fnmatch_lines(
            [
                "*: error: argument -o/--override-ini: expected one argument",
                "  config source: via addopts config",
            ]
        )
        assert result.ret == _testrunner.config.ExitCode.USAGE_ERROR

    def test_override_ini_does_not_contain_paths(
        self, _config_for_test, _sys_snapshot
    ) -> None:
        """Check that -o no longer swallows all options after it (#3103)"""
        config = _config_for_test
        config.parse(["-o", "cache_dir=/cache", "/some/test/path"])
        assert config._inicfg.get("cache_dir") == ConfigValue(
            "/cache", origin="override", mode="ini"
        )

    def test_multiple_override_ini_options(self, testrunnerer: Testrunnerer) -> None:
        """Ensure a file path following a '-o' option does not generate an error (#3103)"""
        testrunnerer.makepyfile(
            **{
                "conftest.py": """
                def testrunner_addoption(parser):
                    parser.addini('foo', default=None, help='some option')
                    parser.addini('bar', default=None, help='some option')
            """,
                "test_foo.py": """
                def test(testrunnerconfig):
                    assert testrunnerconfig.getini('foo') == '1'
                    assert testrunnerconfig.getini('bar') == '0'
            """,
                "test_bar.py": """
                def test():
                    assert False
            """,
            }
        )
        result = testrunnerer.runtestrunner("-o", "foo=1", "-o", "bar=0", "test_foo.py")
        assert "ERROR:" not in result.stderr.str()
        result.stdout.fnmatch_lines(["collected 1 item", "*= 1 passed in *="])

    def test_override_ini_without_config_file(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makepyfile(**{"src/override_ini_without_config_file.py": ""})
        testrunnerer.makepyfile(
            **{
                "tests/test_override_ini_without_config_file.py": (
                    "import override_ini_without_config_file\ndef test(): pass"
                ),
            }
        )
        result = testrunnerer.runtestrunner("--override-ini", "pythonpath=src")
        result.assert_outcomes(passed=1)

    def test_override_ini_invalid_option(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("--override-ini", "doesnotexist=true")
        result.stdout.fnmatch_lines(
            [
                "=*= warnings summary =*=",
                "*TestrunnerConfigWarning:*Unknown config option: doesnotexist",
            ]
        )


def test_help_via_addopts(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeini(
        """
        [testrunner]
        addopts = --unknown-option-should-allow-for-help --help
    """
    )
    result = testrunnerer.runtestrunner()
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        [
            "usage: *",
            "positional arguments:",
            # Displays full/default help.
            "to see available markers type: testrunner --markers",
        ]
    )


def test_help_and_version_after_argument_error(testrunnerer: Testrunnerer) -> None:
    testrunnerer.makeconftest(
        """
        def validate(arg):
            raise argparse.ArgumentTypeError("argerror")

        def testrunner_addoption(parser):
            group = parser.getgroup('cov')
            group.addoption(
                "--invalid-option-should-allow-for-help",
                type=validate,
            )
        """
    )
    testrunnerer.makeini(
        """
        [testrunner]
        addopts = --invalid-option-should-allow-for-help
    """
    )
    result = testrunnerer.runtestrunner("--help")
    result.stdout.fnmatch_lines(
        [
            "usage: *",
            "positional arguments:",
            "NOTE: displaying only minimal help due to UsageError.",
        ]
    )
    result.stderr.fnmatch_lines(
        [
            "ERROR: usage: *",
            "*: error: argument --invalid-option-should-allow-for-help: expected one argument",
        ]
    )
    # Does not display full/default help.
    assert (
        "to see available markers type: testrunner --markers" not in result.stdout.lines
    )
    assert result.ret == ExitCode.USAGE_ERROR

    result = testrunnerer.runtestrunner("--version")
    result.stdout.fnmatch_lines([f"testrunner {testrunner.__version__}"])
    assert result.ret == ExitCode.OK


def test_help_formatter_uses_py_get_terminal_width(monkeypatch: MonkeyPatch) -> None:
    from _testrunner.config.argparsing import DropShorterLongHelpFormatter

    monkeypatch.setenv("COLUMNS", "90")
    formatter = DropShorterLongHelpFormatter("prog")
    assert formatter._width == 90

    monkeypatch.setattr("_testrunner._io.get_terminal_width", lambda: 160)
    formatter = DropShorterLongHelpFormatter("prog")
    assert formatter._width == 160

    formatter = DropShorterLongHelpFormatter("prog", width=42)
    assert formatter._width == 42


def test_config_does_not_load_blocked_plugin_from_args(
    testrunnerer: Testrunnerer,
) -> None:
    """This tests that testrunner's config setup handles "-p no:X"."""
    p = testrunnerer.makepyfile("def test(capfd): pass")
    result = testrunnerer.runtestrunner(str(p), "-pno:capture")
    result.stdout.fnmatch_lines(["E       fixture 'capfd' not found"])
    assert result.ret == ExitCode.TESTS_FAILED

    result = testrunnerer.runtestrunner(str(p), "-pno:capture", "-s")
    result.stderr.fnmatch_lines(["*: error: unrecognized arguments: -s"])
    assert result.ret == ExitCode.USAGE_ERROR

    result = testrunnerer.runtestrunner(str(p), "-p no:capture", "-s")
    result.stderr.fnmatch_lines(["*: error: unrecognized arguments: -s"])
    assert result.ret == ExitCode.USAGE_ERROR

    result = testrunnerer.runtestrunner(str(p), "-p no:/path/to/conftest.py", "-s")
    result.stderr.fnmatch_lines(["ERROR:*Blocking conftest files*"])
    assert result.ret == ExitCode.USAGE_ERROR


def test_invocation_args(testrunnerer: Testrunnerer) -> None:
    """Ensure that Config.invocation_* arguments are correctly defined"""

    class DummyPlugin:
        pass

    p = testrunnerer.makepyfile("def test(): pass")
    plugin = DummyPlugin()
    rec = testrunnerer.inline_run(p, "-v", plugins=[plugin])
    calls = rec.getcalls("testrunner_runtest_protocol")
    assert len(calls) == 1
    call = calls[0]
    config = call.item.config

    assert config.invocation_params.args == (str(p), "-v")
    assert config.invocation_params.dir == testrunnerer.path

    plugins = config.invocation_params.plugins
    assert len(plugins) == 2
    assert plugins[0] is plugin
    # Installed by testrunnerer.inline_run().
    assert type(plugins[1]).__name__ == "TestrunnererHelperPlugin"

    # args cannot be None
    with testrunner.raises(TypeError):
        Config.InvocationParams(args=None, plugins=None, dir=Path())  # type: ignore[arg-type]


@testrunner.mark.parametrize(
    "plugin",
    [
        x
        for x in _testrunner.config.default_plugins
        if x not in _testrunner.config.essential_plugins
    ],
)
def test_config_blocked_default_plugins(
    testrunnerer: Testrunnerer, plugin: str
) -> None:
    p = testrunnerer.makepyfile("def test(): pass")
    result = testrunnerer.runtestrunner(str(p), f"-pno:{plugin}")

    if plugin == "python":
        assert result.ret == ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(
            [
                "ERROR: not found: */test_config_blocked_default_plugins.py",
                "(no match in any of *<Dir *>*",
            ]
        )
        return

    assert result.ret == ExitCode.OK
    if plugin != "terminal":
        result.stdout.fnmatch_lines(["* 1 passed in *"])

    p = testrunnerer.makepyfile("def test(): assert 0")
    result = testrunnerer.runtestrunner(str(p), f"-pno:{plugin}")
    assert result.ret == ExitCode.TESTS_FAILED
    if plugin != "terminal":
        result.stdout.fnmatch_lines(["* 1 failed in *"])
    else:
        assert result.stdout.lines == []


class TestSetupCfg:
    def test_testrunner_setup_cfg_unsupported(self, testrunnerer: Testrunnerer) -> None:
        testrunnerer.makefile(
            ".cfg",
            setup="""
            [testrunner]
            addopts = --verbose
        """,
        )
        with testrunner.raises(testrunner.fail.Exception):
            testrunnerer.runtestrunner()

    def test_testrunner_custom_cfg_unsupported(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makefile(
            ".cfg",
            custom="""
            [testrunner]
            addopts = --verbose
        """,
        )
        with testrunner.raises(testrunner.fail.Exception):
            testrunnerer.runtestrunner("-c", "custom.cfg")

        with testrunner.raises(testrunner.fail.Exception):
            testrunnerer.runtestrunner("--config-file", "custom.cfg")


class TestTestrunnerPluginsVariable:
    def test_testrunner_plugins_in_non_top_level_conftest_unsupported(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            **{
                "subdirectory/conftest.py": """
            testrunner_plugins=['capture']
        """
            }
        )
        testrunnerer.makepyfile(
            """
            def test_func():
                pass
        """
        )
        res = testrunnerer.runtestrunner()
        assert res.ret == 2
        msg = "Defining 'testrunner_plugins' in a non-top-level conftest is no longer supported"
        res.stdout.fnmatch_lines([f"*{msg}*", f"*subdirectory{os.sep}conftest.py*"])

    @testrunner.mark.parametrize("use_pyargs", [True, False])
    def test_testrunner_plugins_in_non_top_level_conftest_unsupported_pyargs(
        self, testrunnerer: Testrunnerer, use_pyargs: bool
    ) -> None:
        """When using --pyargs, do not emit the warning about non-top-level conftest warnings (#4039, #4044)"""
        files = {
            "src/pkg/__init__.py": "",
            "src/pkg/conftest.py": "",
            "src/pkg/test_root.py": "def test(): pass",
            "src/pkg/sub/__init__.py": "",
            "src/pkg/sub/conftest.py": "testrunner_plugins=['capture']",
            "src/pkg/sub/test_bar.py": "def test(): pass",
        }
        testrunnerer.makepyfile(**files)
        testrunnerer.syspathinsert(testrunnerer.path.joinpath("src"))

        args = ("--pyargs", "pkg") if use_pyargs else ()
        res = testrunnerer.runtestrunner(*args)
        assert res.ret == (0 if use_pyargs else 2)
        msg = "Defining 'testrunner_plugins' in a non-top-level conftest is no longer supported"
        if use_pyargs:
            assert msg not in res.stdout.str()
        else:
            res.stdout.fnmatch_lines([f"*{msg}*"])

    def test_testrunner_plugins_in_non_top_level_conftest_unsupported_no_top_level_conftest(
        self, testrunnerer: Testrunnerer
    ) -> None:
        subdirectory = testrunnerer.path.joinpath("subdirectory")
        subdirectory.mkdir()
        testrunnerer.makeconftest(
            """
            testrunner_plugins=['capture']
        """
        )
        testrunnerer.path.joinpath("conftest.py").rename(
            subdirectory.joinpath("conftest.py")
        )

        testrunnerer.makepyfile(
            """
            def test_func():
                pass
        """
        )

        res = testrunnerer.runtestrunner_subprocess()
        assert res.ret == 2
        msg = "Defining 'testrunner_plugins' in a non-top-level conftest is no longer supported"
        res.stdout.fnmatch_lines([f"*{msg}*", f"*subdirectory{os.sep}conftest.py*"])

    def test_testrunner_plugins_in_non_top_level_conftest_unsupported_no_false_positives(
        self, testrunnerer: Testrunnerer
    ) -> None:
        testrunnerer.makepyfile(
            "def test_func(): pass",
            **{
                "subdirectory/conftest": "pass",
                "conftest": """
                    import warnings
                    warnings.filterwarnings('always', category=DeprecationWarning)
                    testrunner_plugins=['capture']
                    """,
            },
        )
        res = testrunnerer.runtestrunner_subprocess()
        assert res.ret == 0
        msg = "Defining 'testrunner_plugins' in a non-top-level conftest is no longer supported"
        assert msg not in res.stdout.str()


def test_conftest_import_error_repr(tmp_path: Path) -> None:
    """`ConftestImportFailure` should use a short error message and readable
    path to the failed conftest.py file."""
    path = tmp_path.joinpath("foo/conftest.py")
    with testrunner.raises(
        ConftestImportFailure,
        match=re.escape(f"RuntimeError: some error (from {path})"),
    ):
        try:
            raise RuntimeError("some error")
        except Exception as exc:
            raise ConftestImportFailure(path, cause=exc) from exc


def test_strtobool() -> None:
    assert _strtobool("YES")
    assert not _strtobool("NO")
    with testrunner.raises(ValueError):
        _strtobool("unknown")


@testrunner.mark.parametrize(
    "arg, escape, expected",
    [
        ("ignore", False, ("ignore", "", Warning, "", 0)),
        (
            "ignore::DeprecationWarning",
            False,
            ("ignore", "", DeprecationWarning, "", 0),
        ),
        (
            "ignore:some msg:DeprecationWarning",
            False,
            ("ignore", "some msg", DeprecationWarning, "", 0),
        ),
        (
            "ignore::DeprecationWarning:mod",
            False,
            ("ignore", "", DeprecationWarning, "mod", 0),
        ),
        (
            "ignore::DeprecationWarning:mod:42",
            False,
            ("ignore", "", DeprecationWarning, "mod", 42),
        ),
        ("error:some\\msg:::", True, ("error", "some\\\\msg", Warning, "", 0)),
        ("error:::mod\\foo:", True, ("error", "", Warning, "mod\\\\foo\\Z", 0)),
    ],
)
def test_parse_warning_filter(
    arg: str, escape: bool, expected: tuple[str, str, type[Warning], str, int]
) -> None:
    assert parse_warning_filter(arg, escape=escape) == expected


@testrunner.mark.parametrize(
    "arg",
    [
        # Too much parts.
        ":" * 5,
        # Invalid action.
        "FOO::",
        # Class is not a Warning subclass.
        "::list::",
        # Negative line number.
        "::::-1",
        # Not a line number.
        "::::not-a-number",
    ],
)
def test_parse_warning_filter_failure(arg: str) -> None:
    with testrunner.raises(testrunner.UsageError):
        parse_warning_filter(arg, escape=True)


class TestDebugOptions:
    def test_without_debug_does_not_write_log(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner()
        result.stderr.no_fnmatch_line(
            "*writing testrunner debug information to*testrunnerdebug.log"
        )
        result.stderr.no_fnmatch_line(
            "*wrote testrunner debug information to*testrunnerdebug.log"
        )
        assert not [f.name for f in testrunnerer.path.glob("**/*.log")]

    def test_with_only_debug_writes_testrunnerdebug_log(
        self, testrunnerer: Testrunnerer
    ) -> None:
        result = testrunnerer.runtestrunner("--debug")
        result.stderr.fnmatch_lines(
            [
                "*writing testrunner debug information to*testrunnerdebug.log",
                "*wrote testrunner debug information to*testrunnerdebug.log",
            ]
        )
        assert "testrunnerdebug.log" in [
            f.name for f in testrunnerer.path.glob("**/*.log")
        ]

    def test_multiple_custom_debug_logs(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("--debug", "bar.log")
        result.stderr.fnmatch_lines(
            [
                "*writing testrunner debug information to*bar.log",
                "*wrote testrunner debug information to*bar.log",
            ]
        )
        result = testrunnerer.runtestrunner("--debug", "foo.log")
        result.stderr.fnmatch_lines(
            [
                "*writing testrunner debug information to*foo.log",
                "*wrote testrunner debug information to*foo.log",
            ]
        )

        assert {"bar.log", "foo.log"} == {
            f.name for f in testrunnerer.path.glob("**/*.log")
        }

    def test_debug_help(self, testrunnerer: Testrunnerer) -> None:
        result = testrunnerer.runtestrunner("-h")
        result.stdout.fnmatch_lines(
            [
                "*Store internal tracing debug information in this log*",
                "*file. This file is opened with 'w' and truncated as a*",
                "*Default: testrunnerdebug.log.",
            ]
        )


class TestVerbosity:
    SOME_OUTPUT_TYPE = Config.VERBOSITY_ASSERTIONS
    SOME_OUTPUT_VERBOSITY_LEVEL = 5

    class VerbosityIni:
        def testrunner_addoption(self, parser: Parser) -> None:
            Config._add_verbosity_ini(
                parser, TestVerbosity.SOME_OUTPUT_TYPE, help="some help text"
            )

    def test_level_matches_verbose_when_not_specified(
        self, testrunnerer: Testrunnerer, tmp_path: Path
    ) -> None:
        tmp_path.joinpath("testrunner.ini").write_text(
            textwrap.dedent(
                """\
                [testrunner]
                addopts = --verbose
                """
            ),
            encoding="utf-8",
        )
        testrunnerer.plugins = [TestVerbosity.VerbosityIni()]

        config = testrunnerer.parseconfig(tmp_path)

        assert (
            config.get_verbosity(TestVerbosity.SOME_OUTPUT_TYPE)
            == config.option.verbose
        )

    def test_level_matches_verbose_when_not_known_type(
        self, testrunnerer: Testrunnerer, tmp_path: Path
    ) -> None:
        tmp_path.joinpath("testrunner.ini").write_text(
            textwrap.dedent(
                """\
                [testrunner]
                addopts = --verbose
                """
            ),
            encoding="utf-8",
        )
        testrunnerer.plugins = [TestVerbosity.VerbosityIni()]

        config = testrunnerer.parseconfig(tmp_path)

        assert config.get_verbosity("some fake verbosity type") == config.option.verbose

    def test_level_matches_specified_override(
        self, testrunnerer: Testrunnerer, tmp_path: Path
    ) -> None:
        setting_name = f"verbosity_{TestVerbosity.SOME_OUTPUT_TYPE}"
        tmp_path.joinpath("testrunner.ini").write_text(
            textwrap.dedent(
                f"""\
                [testrunner]
                addopts = --verbose
                {setting_name} = {TestVerbosity.SOME_OUTPUT_VERBOSITY_LEVEL}
                """
            ),
            encoding="utf-8",
        )
        testrunnerer.plugins = [TestVerbosity.VerbosityIni()]

        config = testrunnerer.parseconfig(tmp_path)

        assert (
            config.get_verbosity(TestVerbosity.SOME_OUTPUT_TYPE)
            == TestVerbosity.SOME_OUTPUT_VERBOSITY_LEVEL
        )


class TestNativeTomlConfig:
    """Test native TOML configuration parsing."""

    def test_values(self, testrunnerer: Testrunnerer) -> None:
        """Test that values are parsed as expected in TOML mode."""
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner]
            test_bool = true
            test_int = 5
            test_float = 30.5
            test_args = ["tests", "integration"]
            test_paths = ["src", "lib"]
            """
        )
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("test_bool", "Test boolean config", type="bool", default=False)
                parser.addini("test_int", "Test integer config", type="int", default=0)
                parser.addini("test_float", "Test float config", type="float", default=0.0)
                parser.addini("test_args", "Test args config", type="args")
                parser.addini("test_paths", "Test paths config", type="paths")
            """
        )
        config = testrunnerer.parseconfig()
        assert config.getini("test_bool") is True
        assert config.getini("test_int") == 5
        assert config.getini("test_float") == 30.5
        assert config.getini("test_args") == ["tests", "integration"]
        paths = config.getini("test_paths")
        assert len(paths) == 2
        # Paths should be resolved relative to pyproject.toml location.
        assert all(isinstance(p, Path) for p in paths)

    def test_override_with_list(self, testrunnerer: Testrunnerer) -> None:
        """Test that -o overrides work with INI-style list syntax even when
        config uses TOML mode."""
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner]
            test_override_list = ["tests"]
            """
        )
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("test_override_list", "Test override list", type="args")
            """
        )
        # -o uses INI mode, so uses space-separated syntax.
        config = testrunnerer.parseconfig("-o", "test_override_list=tests integration")
        assert config.getini("test_override_list") == ["tests", "integration"]

    def test_conflict_between_native_and_ini_options(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Test that using both [tool.testrunner] and [tool.testrunner.ini_options] fails."""
        testrunnerer.makepyprojecttoml(
            """
            [tool.testrunner]
            test_conflict_1 = true

            [tool.testrunner.ini_options]
            test_conflict_2 = true
            """,
        )
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("test_conflict_1", "Test conflict config 1", type="bool")
                parser.addini("test_conflict_2", "Test conflict config 2", type="bool")
            """
        )
        with testrunner.raises(UsageError, match="Cannot use both"):
            testrunnerer.parseconfig()

    def test_type_errors(self, testrunnerer: Testrunnerer) -> None:
        """Test all invalid-type cases in getini, reported as UsageError."""
        testrunnerer.maketoml(
            """
            [testrunner]
            paths_not_list = "should_be_list"
            paths_list_with_int = [1, 2]

            args_not_list = 123
            args_list_with_int = ["valid", 456]

            linelist_not_list = true
            linelist_list_with_bool = ["valid", false]

            bool_not_bool = "true"

            int_not_int = "123"
            int_is_bool = true

            float_not_float = "3.14"
            float_is_bool = false

            string_not_string = 123
            """
        )
        testrunnerer.makeconftest(
            """
            def testrunner_addoption(parser):
                parser.addini("paths_not_list", "test", type="paths")
                parser.addini("paths_list_with_int", "test", type="paths")
                parser.addini("args_not_list", "test", type="args")
                parser.addini("args_list_with_int", "test", type="args")
                parser.addini("linelist_not_list", "test", type="linelist")
                parser.addini("linelist_list_with_bool", "test", type="linelist")
                parser.addini("bool_not_bool", "test", type="bool")
                parser.addini("int_not_int", "test", type="int")
                parser.addini("int_is_bool", "test", type="int")
                parser.addini("float_not_float", "test", type="float")
                parser.addini("float_is_bool", "test", type="float")
                parser.addini("string_not_string", "test", type="string")
            """
        )
        config = testrunnerer.parseconfig()

        with testrunner.raises(
            UsageError, match=r"expects a list for type 'paths'.*got str"
        ):
            config.getini("paths_not_list")

        with testrunner.raises(
            UsageError, match=r"expects a list of strings.*item at index 0 is int"
        ):
            config.getini("paths_list_with_int")

        with testrunner.raises(
            UsageError, match=r"expects a list for type 'args'.*got int"
        ):
            config.getini("args_not_list")

        with testrunner.raises(
            UsageError, match=r"expects a list of strings.*item at index 1 is int"
        ):
            config.getini("args_list_with_int")

        with testrunner.raises(
            UsageError, match=r"expects a list for type 'linelist'.*got bool"
        ):
            config.getini("linelist_not_list")

        with testrunner.raises(
            UsageError, match=r"expects a list of strings.*item at index 1 is bool"
        ):
            config.getini("linelist_list_with_bool")

        with testrunner.raises(UsageError, match=r"expects a bool.*got str"):
            config.getini("bool_not_bool")

        with testrunner.raises(UsageError, match=r"expects an int.*got str"):
            config.getini("int_not_int")

        with testrunner.raises(UsageError, match=r"expects an int.*got bool"):
            config.getini("int_is_bool")

        with testrunner.raises(UsageError, match=r"expects a float.*got str"):
            config.getini("float_not_float")

        with testrunner.raises(UsageError, match=r"expects a float.*got bool"):
            config.getini("float_is_bool")

        with testrunner.raises(UsageError, match=r"expects a string.*got int"):
            config.getini("string_not_string")


class TestInicfgDeprecation:
    """Tests for the deprecation of config.inicfg."""

    def test_inicfg_deprecated(self, testrunnerer: Testrunnerer) -> None:
        """Test that accessing config.inicfg issues a deprecation warning."""
        testrunnerer.makeini(
            """
            [testrunner]
            minversion = 0.1.0.dev0
            """
        )
        config = testrunnerer.parseconfig()

        with testrunner.warns(
            TestrunnerDeprecationWarning, match=r"config\.inicfg is deprecated"
        ):
            inicfg = config.inicfg  # type: ignore[deprecated]

        assert config.getini("minversion") == "0.1.0.dev0"
        assert inicfg["minversion"] == "0.1.0.dev0"
        assert inicfg.get("minversion") == "0.1.0.dev0"
        del inicfg["minversion"]
        inicfg["minversion"] = "0.1.0"
        assert list(inicfg.keys()) == ["minversion"]
        assert list(inicfg.items()) == [("minversion", "0.1.0")]
        assert len(inicfg) == 1

    def test_issue_13946_setting_bool_no_longer_crashes(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Regression test for #13946 - setting inicfg doesn't cause a crash."""
        testrunnerer.makepyfile(
            """
            def testrunner_configure(config):
                config.inicfg["xfail_strict"] = True

            def test():
                pass
            """
        )

        result = testrunnerer.runtestrunner()
        assert result.ret == 0


class TestProgName:
    """Test program name display in help and error messages (issue #1764)."""

    def test_get_prog_name_direct_testrunner(self) -> None:
        """When argv[0] is a testrunner entry point, prog should be 'testrunner'."""
        assert _get_prog_name(["/usr/bin/testrunner", "--help"]) == "testrunner"
        assert _get_prog_name(["testrunner", "-v"]) == "testrunner"

    def test_get_prog_name_python_m_testrunner(self) -> None:
        """When argv[0] is __main__.py, prog should be 'python -m testrunner'."""
        assert (
            _get_prog_name(["/path/to/site-packages/testrunner/__main__.py", "--help"])
            == "python -m testrunner"
        )
        assert _get_prog_name(["__main__.py", "-v"]) == "python -m testrunner"

    def test_get_prog_name_empty_argv(self) -> None:
        """When argv is empty, should default to 'testrunner'."""
        assert _get_prog_name([]) == "testrunner"

    def test_prog_in_error_message_programmatic(
        self, testrunnerer: Testrunnerer
    ) -> None:
        """Error messages should show 'testrunner.main()' when called programmatically.

        runtestrunner_inprocess calls testrunner.main() directly, so it should show
        testrunner.main() as the program name.
        """
        result = testrunnerer.runtestrunner_inprocess("--invalid-option-xyz")
        result.stderr.fnmatch_lines(["*testrunner.main(): error:*invalid-option-xyz*"])

    def test_prog_in_error_message_cli(self, testrunnerer: Testrunnerer) -> None:
        """Error messages should show 'python -m testrunner' when called from CLI subprocess.

        runtestrunner_subprocess runs testrunner via 'python -m testrunner', so it should
        show 'python -m testrunner' as the program name.
        """
        result = testrunnerer.runtestrunner_subprocess("--invalid-option-xyz")
        result.stderr.fnmatch_lines(
            ["*python -m testrunner: error:*invalid-option-xyz*"]
        )

    def test_prog_in_usage_programmatic(self, testrunnerer: Testrunnerer) -> None:
        """Usage line should show 'testrunner.main()' when called programmatically."""
        result = testrunnerer.runtestrunner_inprocess("--help")
        result.stdout.fnmatch_lines(["usage: testrunner.main() *"])

    def test_prog_in_usage_cli(self, testrunnerer: Testrunnerer) -> None:
        """Usage line should show 'python -m testrunner' when called from CLI subprocess."""
        result = testrunnerer.runtestrunner_subprocess("--help")
        result.stdout.fnmatch_lines(["usage: python -m testrunner *"])

    def test_console_main_deprecated(self, monkeypatch: testrunner.MonkeyPatch) -> None:
        """Calling testrunner.console_main() should emit a deprecation warning."""
        monkeypatch.setattr("_testrunner.config._console_main", lambda: 0)
        with testrunner.warns(
            testrunner.TestrunnerRemovedIn10Warning,
            match="testrunner.console_main.*is deprecated",
        ):
            console_main()
