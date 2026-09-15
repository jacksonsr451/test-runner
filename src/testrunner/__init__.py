# PYTHON_ARGCOMPLETE_OK
"""testrunner: unit and functional testing with Python."""

from __future__ import annotations

from _testrunner import __version__
from _testrunner import version_tuple
from _testrunner._code import ExceptionInfo
from _testrunner.approx import Approx
from _testrunner.approx import approx
from _testrunner.assertion import register_assert_rewrite
from _testrunner.cacheprovider import Cache
from _testrunner.capture import CaptureFixture
from _testrunner.config import cmdline
from _testrunner.config import Config
from _testrunner.config import console_main
from _testrunner.config import ExitCode
from _testrunner.config import hookimpl
from _testrunner.config import hookspec
from _testrunner.config import main
from _testrunner.config import TestrunnerPluginManager
from _testrunner.config import UsageError
from _testrunner.config.argparsing import OptionGroup
from _testrunner.config.argparsing import Parser
from _testrunner.debugging import testrunnerPDB as __testrunnerPDB
from _testrunner.doctest import DoctestItem
from _testrunner.fixtures import fixture
from _testrunner.fixtures import FixtureDef
from _testrunner.fixtures import FixtureFunctionDefinition
from _testrunner.fixtures import FixtureLookupError
from _testrunner.fixtures import FixtureRequest
from _testrunner.fixtures import register_fixture
from _testrunner.fixtures import yield_fixture  # type: ignore[deprecated]
from _testrunner.freeze_support import freeze_includes
from _testrunner.legacypath import TempdirFactory
from _testrunner.legacypath import Testdir
from _testrunner.logging import LogCaptureFixture
from _testrunner.main import Dir
from _testrunner.main import Session
from _testrunner.mark import HIDDEN_PARAM
from _testrunner.mark import Mark
from _testrunner.mark import MARK_GEN as mark
from _testrunner.mark import MarkDecorator
from _testrunner.mark import MarkGenerator
from _testrunner.mark import param
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.nodes import Collector
from _testrunner.nodes import Directory
from _testrunner.nodes import File
from _testrunner.nodes import Item
from _testrunner.outcomes import exit
from _testrunner.outcomes import fail
from _testrunner.outcomes import importorskip
from _testrunner.outcomes import skip
from _testrunner.outcomes import xfail
from _testrunner.testrunnerer import HookRecorder
from _testrunner.testrunnerer import LineMatcher
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.testrunnerer import RecordedHookCall
from _testrunner.testrunnerer import RunResult
from _testrunner.python import Class
from _testrunner.python import Function
from _testrunner.python import Metafunc
from _testrunner.python import Module
from _testrunner.python import Package
from _testrunner.raises import raises
from _testrunner.raises import RaisesExc
from _testrunner.raises import RaisesGroup
from _testrunner.recwarn import deprecated_call
from _testrunner.recwarn import WarningsRecorder
from _testrunner.recwarn import warns
from _testrunner.reports import CollectReport
from _testrunner.reports import TestReport
from _testrunner.runner import CallInfo
from _testrunner.scope import ScopeName
from _testrunner.stash import Stash
from _testrunner.stash import StashKey
from _testrunner.subtests import SubtestReport
from _testrunner.subtests import Subtests
from _testrunner.terminal import TerminalReporter
from _testrunner.terminal import TestShortLogReport
from _testrunner.tmpdir import TempPathFactory
from _testrunner.warning_types import TestrunnerApproxDecimalToleranceWarning
from _testrunner.warning_types import TestrunnerAssertRewriteWarning
from _testrunner.warning_types import TestrunnerCacheWarning
from _testrunner.warning_types import TestrunnerCollectionWarning
from _testrunner.warning_types import TestrunnerConfigWarning
from _testrunner.warning_types import TestrunnerDeprecationWarning
from _testrunner.warning_types import TestrunnerExperimentalApiWarning
from _testrunner.warning_types import TestrunnerFDWarning
from _testrunner.warning_types import TestrunnerRemovedIn10Warning
from _testrunner.warning_types import TestrunnerReturnNotNoneWarning
from _testrunner.warning_types import TestrunnerUnhandledThreadExceptionWarning
from _testrunner.warning_types import TestrunnerUnknownMarkWarning
from _testrunner.warning_types import TestrunnerUnraisableExceptionWarning
from _testrunner.warning_types import TestrunnerWarning


set_trace = __testrunnerPDB.set_trace


__all__ = [
    "HIDDEN_PARAM",
    "Approx",
    "Cache",
    "CallInfo",
    "CaptureFixture",
    "Class",
    "CollectReport",
    "Collector",
    "Config",
    "Dir",
    "Directory",
    "DoctestItem",
    "ExceptionInfo",
    "ExitCode",
    "File",
    "FixtureDef",
    "FixtureFunctionDefinition",
    "FixtureLookupError",
    "FixtureRequest",
    "Function",
    "HookRecorder",
    "Item",
    "LineMatcher",
    "LogCaptureFixture",
    "Mark",
    "MarkDecorator",
    "MarkGenerator",
    "Metafunc",
    "Module",
    "MonkeyPatch",
    "OptionGroup",
    "Package",
    "Parser",
    "TestrunnerApproxDecimalToleranceWarning",
    "TestrunnerAssertRewriteWarning",
    "TestrunnerCacheWarning",
    "TestrunnerCollectionWarning",
    "TestrunnerConfigWarning",
    "TestrunnerDeprecationWarning",
    "TestrunnerExperimentalApiWarning",
    "TestrunnerFDWarning",
    "TestrunnerPluginManager",
    "TestrunnerRemovedIn10Warning",
    "TestrunnerReturnNotNoneWarning",
    "TestrunnerUnhandledThreadExceptionWarning",
    "TestrunnerUnknownMarkWarning",
    "TestrunnerUnraisableExceptionWarning",
    "TestrunnerWarning",
    "Testrunnerer",
    "RaisesExc",
    "RaisesGroup",
    "RecordedHookCall",
    "RunResult",
    "ScopeName",
    "Session",
    "Stash",
    "StashKey",
    "SubtestReport",
    "Subtests",
    "TempPathFactory",
    "TempdirFactory",
    "TerminalReporter",
    "TestReport",
    "TestShortLogReport",
    "Testdir",
    "UsageError",
    "WarningsRecorder",
    "__version__",
    "approx",
    "cmdline",
    "console_main",
    "deprecated_call",
    "exit",
    "fail",
    "fixture",
    "freeze_includes",
    "hookimpl",
    "hookspec",
    "importorskip",
    "main",
    "mark",
    "param",
    "raises",
    "register_assert_rewrite",
    "register_fixture",
    "set_trace",
    "skip",
    "version_tuple",
    "warns",
    "xfail",
    "yield_fixture",
]
