# mypy: allow-untyped-defs
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

from _testrunner.config import UsageError
from _testrunner.config.findpaths import ConfigValue
from _testrunner.config.findpaths import get_common_ancestor
from _testrunner.config.findpaths import get_dirs_from_args
from _testrunner.config.findpaths import is_fs_root
from _testrunner.config.findpaths import load_config_dict_from_file
import testrunner


class TestLoadConfigDictFromFile:
    @testrunner.mark.parametrize("filename", ["testrunner.ini", ".testrunner.ini"])
    def test_empty_testrunner_ini(self, tmp_path: Path, filename: str) -> None:
        """testrunner.ini files are always considered for configuration, even if empty"""
        fn = tmp_path / filename
        fn.write_text("", encoding="utf-8")
        assert load_config_dict_from_file(fn) == {}

    def test_testrunner_ini(self, tmp_path: Path) -> None:
        """[testrunner] section in testrunner.ini files is read correctly"""
        fn = tmp_path / "testrunner.ini"
        fn.write_text("[testrunner]\nx=1", encoding="utf-8")
        assert load_config_dict_from_file(fn) == {
            "x": ConfigValue("1", origin="file", mode="ini")
        }

    def test_custom_ini(self, tmp_path: Path) -> None:
        """[testrunner] section in any .ini file is read correctly"""
        fn = tmp_path / "custom.ini"
        fn.write_text("[testrunner]\nx=1", encoding="utf-8")
        assert load_config_dict_from_file(fn) == {
            "x": ConfigValue("1", origin="file", mode="ini")
        }

    def test_custom_ini_without_section(self, tmp_path: Path) -> None:
        """Custom .ini files without [testrunner] section are not considered for configuration"""
        fn = tmp_path / "custom.ini"
        fn.write_text("[custom]", encoding="utf-8")
        assert load_config_dict_from_file(fn) is None

    def test_custom_cfg_file(self, tmp_path: Path) -> None:
        """Custom .cfg files without [tool:testrunner] section are not considered for configuration"""
        fn = tmp_path / "custom.cfg"
        fn.write_text("[custom]", encoding="utf-8")
        assert load_config_dict_from_file(fn) is None

    def test_valid_cfg_file(self, tmp_path: Path) -> None:
        """Custom .cfg files with [tool:testrunner] section are read correctly"""
        fn = tmp_path / "custom.cfg"
        fn.write_text("[tool:testrunner]\nx=1", encoding="utf-8")
        assert load_config_dict_from_file(fn) == {
            "x": ConfigValue("1", origin="file", mode="ini")
        }

    def test_unsupported_testrunner_section_in_cfg_file(self, tmp_path: Path) -> None:
        """.cfg files with [testrunner] section are no longer supported and should fail to alert users"""
        fn = tmp_path / "custom.cfg"
        fn.write_text("[testrunner]", encoding="utf-8")
        with testrunner.raises(testrunner.fail.Exception):
            load_config_dict_from_file(fn)

    def test_invalid_toml_file(self, tmp_path: Path) -> None:
        """Invalid .toml files should raise `UsageError`."""
        fn = tmp_path / "myconfig.toml"
        fn.write_text("]invalid toml[", encoding="utf-8")
        with testrunner.raises(UsageError):
            load_config_dict_from_file(fn)

    def test_custom_toml_file_reads_testrunner_table(self, tmp_path: Path) -> None:
        """.toml files with an arbitrary name read [testrunner], like testrunner.toml (#14705)."""
        fn = tmp_path / "myconfig.toml"
        fn.write_text(
            dedent(
                """
            [testrunner]
            xfail_strict = true
            testpaths = ["tests", "integration"]
            """
            ),
            encoding="utf-8",
        )
        assert load_config_dict_from_file(fn) == {
            "xfail_strict": ConfigValue(True, origin="file", mode="toml"),
            "testpaths": ConfigValue(
                ["tests", "integration"], origin="file", mode="toml"
            ),
        }

    def test_custom_toml_file_with_both_table_styles(self, tmp_path: Path) -> None:
        """[testrunner] and [tool.testrunner] in one file is ambiguous (#14705)."""
        fn = tmp_path / "myconfig.toml"
        fn.write_text(
            dedent(
                """
            [testrunner]
            xfail_strict = true

            [tool.testrunner.ini_options]
            xfail_strict = "false"
            """
            ),
            encoding="utf-8",
        )
        with testrunner.raises(UsageError, match="Cannot use both"):
            load_config_dict_from_file(fn)

    def test_custom_toml_file_with_top_level_options(self, tmp_path: Path) -> None:
        """Options outside of any table name the table that was meant."""
        fn = tmp_path / "myconfig.toml"
        fn.write_text("xfail_strict = true\n", encoding="utf-8")
        with testrunner.raises(
            UsageError, match=r"must be under a \[testrunner\] table"
        ):
            load_config_dict_from_file(fn)

    def test_custom_toml_file(self, tmp_path: Path) -> None:
        """.toml files with neither [testrunner] nor [tool.testrunner] hold no configuration."""
        fn = tmp_path / "myconfig.toml"
        fn.write_text(
            dedent(
                """
            [build_system]
            x = 1
            """
            ),
            encoding="utf-8",
        )
        assert load_config_dict_from_file(fn) is None

    def test_valid_toml_file(self, tmp_path: Path) -> None:
        """.toml files with [tool.testrunner.ini_options] are read correctly, including changing
        data types to str/list for compatibility with other configuration options."""
        fn = tmp_path / "myconfig.toml"
        fn.write_text(
            dedent(
                """
            [tool.testrunner.ini_options]
            x = 1
            y = 20.0
            values = ["tests", "integration"]
            name = "foo"
            heterogeneous_array = [1, "str"]
            """
            ),
            encoding="utf-8",
        )
        assert load_config_dict_from_file(fn) == {
            "x": ConfigValue("1", origin="file", mode="ini"),
            "y": ConfigValue("20.0", origin="file", mode="ini"),
            "values": ConfigValue(["tests", "integration"], origin="file", mode="ini"),
            "name": ConfigValue("foo", origin="file", mode="ini"),
            "heterogeneous_array": ConfigValue([1, "str"], origin="file", mode="ini"),
        }

    def test_native_toml_config(self, tmp_path: Path) -> None:
        """[tool.testrunner] sections with native types are parsed correctly without coercion."""
        fn = tmp_path / "pyproject.toml"
        fn.write_text(
            dedent(
                """
                [tool.testrunner]
                minversion = "7.0"
                xfail_strict = true
                testpaths = ["tests", "integration"]
                python_files = ["test_*.py", "*_test.py"]
                verbosity_assertions = 2
                maxfail = 5
                timeout = 300.5
                """
            ),
            encoding="utf-8",
        )
        result = load_config_dict_from_file(fn)
        assert result == {
            "minversion": ConfigValue("7.0", origin="file", mode="toml"),
            "xfail_strict": ConfigValue(True, origin="file", mode="toml"),
            "testpaths": ConfigValue(
                ["tests", "integration"], origin="file", mode="toml"
            ),
            "python_files": ConfigValue(
                ["test_*.py", "*_test.py"], origin="file", mode="toml"
            ),
            "verbosity_assertions": ConfigValue(2, origin="file", mode="toml"),
            "maxfail": ConfigValue(5, origin="file", mode="toml"),
            "timeout": ConfigValue(300.5, origin="file", mode="toml"),
        }

    def test_native_and_ini_conflict(self, tmp_path: Path) -> None:
        """Using both [tool.testrunner] and [tool.testrunner.ini_options] should raise an error."""
        fn = tmp_path / "pyproject.toml"
        fn.write_text(
            dedent(
                """
            [tool.testrunner]
            xfail_strict = true

            [tool.testrunner.ini_options]
            minversion = "7.0"
            """
            ),
            encoding="utf-8",
        )
        with testrunner.raises(UsageError, match="Cannot use both"):
            load_config_dict_from_file(fn)

    def test_invalid_suffix(self, tmp_path: Path) -> None:
        """A file with an unknown suffix is ignored."""
        fn = tmp_path / "testrunner.config"
        fn.write_text("", encoding="utf-8")
        assert load_config_dict_from_file(fn) is None


class TestCommonAncestor:
    def test_has_ancestor(self, tmp_path: Path) -> None:
        fn1 = tmp_path / "foo" / "bar" / "test_1.py"
        fn1.parent.mkdir(parents=True)
        fn1.touch()
        fn2 = tmp_path / "foo" / "zaz" / "test_2.py"
        fn2.parent.mkdir(parents=True)
        fn2.touch()
        cwd = Path.cwd()
        assert get_common_ancestor(cwd, [fn1, fn2]) == tmp_path / "foo"
        assert get_common_ancestor(cwd, [fn1.parent, fn2]) == tmp_path / "foo"
        assert get_common_ancestor(cwd, [fn1.parent, fn2.parent]) == tmp_path / "foo"
        assert get_common_ancestor(cwd, [fn1, fn2.parent]) == tmp_path / "foo"

    def test_single_dir(self, tmp_path: Path) -> None:
        assert get_common_ancestor(Path.cwd(), [tmp_path]) == tmp_path

    def test_single_file(self, tmp_path: Path) -> None:
        fn = tmp_path / "foo.py"
        fn.touch()
        assert get_common_ancestor(Path.cwd(), [fn]) == tmp_path


def test_get_dirs_from_args(tmp_path):
    """get_dirs_from_args() skips over non-existing directories and files"""
    fn = tmp_path / "foo.py"
    fn.touch()
    d = tmp_path / "tests"
    d.mkdir()
    option = "--foobar=/foo.txt"
    # xdist uses options in this format for its rsync feature (#7638)
    xdist_rsync_option = "popen=c:/dest"
    assert get_dirs_from_args(
        [str(fn), str(tmp_path / "does_not_exist"), str(d), option, xdist_rsync_option]
    ) == [fn.parent, d]


@testrunner.mark.parametrize(
    "path, expected",
    [
        testrunner.param(
            f"e:{os.sep}", True, marks=testrunner.mark.skipif("sys.platform != 'win32'")
        ),
        (f"{os.sep}", True),
        (f"e:{os.sep}projects", False),
        (f"{os.sep}projects", False),
    ],
)
def test_is_fs_root(path: Path, expected: bool) -> None:
    assert is_fs_root(Path(path)) is expected
