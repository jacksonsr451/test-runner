# mypy: allow-untyped-defs
from __future__ import annotations

from pathlib import Path
import re
import warnings

from _testrunner import nodes
from _testrunner.outcomes import OutcomeException
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.warning_types import TestrunnerWarning
import testrunner


def test_node_from_parent_disallowed_arguments() -> None:
    with testrunner.raises(TypeError, match="session is"):
        nodes.Node.from_parent(None, session=None)  # type: ignore[arg-type]
    with testrunner.raises(TypeError, match="config is"):
        nodes.Node.from_parent(None, config=None)  # type: ignore[arg-type]


def test_node_direct_construction_deprecated() -> None:
    with testrunner.raises(
        OutcomeException,
        match=(
            r"Direct construction of _testrunner\.nodes\.Node has been deprecated, please "
            r"use _testrunner\.nodes\.Node\.from_parent.\nSee "
            r"https://docs\.testrunner\.org/en/stable/deprecations\.html#node-construction-changed-to-node-from-parent"
            r" for more details\."
        ),
    ):
        nodes.Node(None, session=None)  # type: ignore[arg-type]


def test_subclassing_both_item_and_collector_deprecated(
    request, tmp_path: Path
) -> None:
    """Verifies we warn on diamond inheritance from both Item and Collector."""
    # We do not expect any warnings messages to be issued during class definition.
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        class SoWrong(nodes.Item, nodes.File):
            def __init__(self, parent: nodes.Collector, path: Path) -> None:
                super().__init__(name="broken", parent=parent, path=path)

            def collect(self):
                raise NotImplementedError()

            def runtest(self):
                raise NotImplementedError()

    with testrunner.warns(TestrunnerWarning) as rec:
        SoWrong.from_parent(request.session, path=tmp_path / "broken.txt")
    messages = [str(x.message) for x in rec]
    assert any(
        re.search(".*SoWrong.* not using a cooperative constructor.*", x)
        for x in messages
    )
    assert any(
        re.search("(?m)SoWrong .* should not be a collector", x) for x in messages
    )


@testrunner.mark.parametrize(
    "warn_type, msg", [(DeprecationWarning, "deprecated"), (TestrunnerWarning, "testrunner")]
)
def test_node_warn_is_no_longer_only_testrunner_warnings(
    testrunnerer: Testrunnerer, warn_type: type[Warning], msg: str
) -> None:
    items = testrunnerer.getitems(
        """
        def test():
            pass
    """
    )
    with testrunner.warns(warn_type, match=msg):
        items[0].warn(warn_type(msg))


def test_node_warning_enforces_warning_types(testrunnerer: Testrunnerer) -> None:
    items = testrunnerer.getitems(
        """
        def test():
            pass
    """
    )
    with testrunner.raises(
        ValueError, match="warning must be an instance of Warning or subclass"
    ):
        items[0].warn(Exception("ok"))  # type: ignore[arg-type]


class TestNormSep:
    """Tests for the norm_sep helper function."""

    def test_forward_slashes_unchanged(self) -> None:
        """Forward slashes pass through unchanged."""
        assert nodes.norm_sep("a/b/c") == "a/b/c"

    def test_backslashes_converted(self) -> None:
        """Backslashes are converted to forward slashes."""
        assert nodes.norm_sep("a\\b\\c") == "a/b/c"

    def test_mixed_separators(self) -> None:
        """Mixed separators are all normalized to forward slashes."""
        assert nodes.norm_sep("a\\b/c\\d") == "a/b/c/d"

    def test_pathlike_input(self, tmp_path: Path) -> None:
        """PathLike objects are converted to string with normalized separators."""
        # Create a path and verify it's normalized
        result = nodes.norm_sep(tmp_path / "subdir" / "file.py")
        assert "\\" not in result
        assert "subdir/file.py" in result

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert nodes.norm_sep("") == ""

    def test_windows_absolute_path(self) -> None:
        """Windows absolute paths have backslashes converted."""
        assert nodes.norm_sep("C:\\Users\\test\\project") == "C:/Users/test/project"


def test__check_initialpaths_for_relpath() -> None:
    """Ensure that it handles dirs, and does not always use dirname."""
    cwd = Path.cwd()

    initial_paths = frozenset({cwd})

    assert nodes._check_initialpaths_for_relpath(initial_paths, cwd) == ""

    sub = cwd / "file"
    assert nodes._check_initialpaths_for_relpath(initial_paths, sub) == "file"

    outside = Path("/outside-this-does-not-exist")
    assert nodes._check_initialpaths_for_relpath(initial_paths, outside) is None


def test_failure_with_changed_cwd(testrunnerer: Testrunnerer) -> None:
    """
    Test failure lines should use absolute paths if cwd has changed since
    invocation, so the path is correct (#6428).
    """
    p = testrunnerer.makepyfile(
        """
        import os
        import testrunner

        @testrunner.fixture
        def private_dir():
            out_dir = 'ddd'
            os.mkdir(out_dir)
            old_dir = os.getcwd()
            os.chdir(out_dir)
            yield out_dir
            os.chdir(old_dir)

        def test_show_wrong_path(private_dir):
            assert False
    """
    )
    result = testrunnerer.runtestrunner()
    result.stdout.fnmatch_lines([str(p) + ":*: AssertionError", "*1 failed in *"])
