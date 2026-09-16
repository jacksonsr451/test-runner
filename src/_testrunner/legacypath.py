# mypy: allow-untyped-defs
"""Add backward compatibility support for the legacy py path type."""

from __future__ import annotations

import dataclasses
from pathlib import Path
import shlex
import subprocess
from typing import Final
from typing import final
from typing import TYPE_CHECKING

from iniconfig import SectionWrapper

from _testrunner.cacheprovider import Cache
from _testrunner.compat import LEGACY_PATH
from _testrunner.compat import legacy_path
from _testrunner.config import Config
from _testrunner.config import hookimpl
from _testrunner.config import TestrunnerPluginManager
from _testrunner.deprecated import check_istestrunner
from _testrunner.fixtures import fixture
from _testrunner.fixtures import FixtureRequest
from _testrunner.main import Session
from _testrunner.monkeypatch import MonkeyPatch
from _testrunner.nodes import Collector
from _testrunner.nodes import Item
from _testrunner.nodes import Node
from _testrunner.terminal import TerminalReporter
from _testrunner.testrunnerer import HookRecorder
from _testrunner.testrunnerer import RunResult
from _testrunner.testrunnerer import Testrunnerer
from _testrunner.tmpdir import TempPathFactory


if TYPE_CHECKING:
    import pexpect


@final
class Testdir:
    """
    Similar to :class:`Testrunnerer`, but this class works with legacy legacy_path objects instead.

    All methods just forward to an internal :class:`Testrunnerer` instance, converting results
    to `legacy_path` objects as necessary.
    """

    __test__ = False

    CLOSE_STDIN: Final = Testrunnerer.CLOSE_STDIN
    TimeoutExpired: Final = Testrunnerer.TimeoutExpired

    def __init__(
        self, testrunnerer: Testrunnerer, *, _istestrunner: bool = False
    ) -> None:
        check_istestrunner(_istestrunner)
        self._testrunnerer = testrunnerer

    @property
    def tmpdir(self) -> LEGACY_PATH:
        """Temporary directory where tests are executed."""
        return legacy_path(self._testrunnerer.path)

    @property
    def test_tmproot(self) -> LEGACY_PATH:
        return legacy_path(self._testrunnerer._test_tmproot)

    @property
    def request(self):
        return self._testrunnerer._request

    @property
    def plugins(self):
        return self._testrunnerer.plugins

    @plugins.setter
    def plugins(self, plugins):
        self._testrunnerer.plugins = plugins

    @property
    def monkeypatch(self) -> MonkeyPatch:
        return self._testrunnerer._monkeypatch

    def make_hook_recorder(self, pluginmanager) -> HookRecorder:
        """See :meth:`Testrunnerer.make_hook_recorder`."""
        return self._testrunnerer.make_hook_recorder(pluginmanager)

    def chdir(self) -> None:
        """See :meth:`Testrunnerer.chdir`."""
        return self._testrunnerer.chdir()

    def finalize(self) -> None:
        return self._testrunnerer._finalize()

    def makefile(self, ext, *args, **kwargs) -> LEGACY_PATH:
        """See :meth:`Testrunnerer.makefile`."""
        if ext and not ext.startswith("."):
            # testrunnerer.makefile is going to throw a ValueError in a way that
            # testdir.makefile did not, because
            # pathlib.Path is stricter suffixes than py.path
            # This ext arguments is likely user error, but since testdir has
            # allowed this, we will prepend "." as a workaround to avoid breaking
            # testdir usage that worked before
            ext = "." + ext
        return legacy_path(self._testrunnerer.makefile(ext, *args, **kwargs))

    def makeconftest(self, source) -> LEGACY_PATH:
        """See :meth:`Testrunnerer.makeconftest`."""
        return legacy_path(self._testrunnerer.makeconftest(source))

    def makeini(self, source) -> LEGACY_PATH:
        """See :meth:`Testrunnerer.makeini`."""
        return legacy_path(self._testrunnerer.makeini(source))

    def getinicfg(self, source: str) -> SectionWrapper:
        """See :meth:`Testrunnerer.getinicfg`."""
        return self._testrunnerer.getinicfg(source)

    def makepyprojecttoml(self, source) -> LEGACY_PATH:
        """See :meth:`Testrunnerer.makepyprojecttoml`."""
        return legacy_path(self._testrunnerer.makepyprojecttoml(source))

    def makepyfile(self, *args, **kwargs) -> LEGACY_PATH:
        """See :meth:`Testrunnerer.makepyfile`."""
        return legacy_path(self._testrunnerer.makepyfile(*args, **kwargs))

    def maketxtfile(self, *args, **kwargs) -> LEGACY_PATH:
        """See :meth:`Testrunnerer.maketxtfile`."""
        return legacy_path(self._testrunnerer.maketxtfile(*args, **kwargs))

    def syspathinsert(self, path=None) -> None:
        """See :meth:`Testrunnerer.syspathinsert`."""
        return self._testrunnerer.syspathinsert(path)

    def mkdir(self, name) -> LEGACY_PATH:
        """See :meth:`Testrunnerer.mkdir`."""
        return legacy_path(self._testrunnerer.mkdir(name))

    def mkpydir(self, name) -> LEGACY_PATH:
        """See :meth:`Testrunnerer.mkpydir`."""
        return legacy_path(self._testrunnerer.mkpydir(name))

    def copy_example(self, name=None) -> LEGACY_PATH:
        """See :meth:`Testrunnerer.copy_example`."""
        return legacy_path(self._testrunnerer.copy_example(name))

    def getnode(self, config: Config, arg) -> Item | Collector | None:
        """See :meth:`Testrunnerer.getnode`."""
        return self._testrunnerer.getnode(config, arg)

    def getpathnode(self, path):
        """See :meth:`Testrunnerer.getpathnode`."""
        return self._testrunnerer.getpathnode(path)

    def genitems(self, colitems: list[Item | Collector]) -> list[Item]:
        """See :meth:`Testrunnerer.genitems`."""
        return self._testrunnerer.genitems(colitems)

    def runitem(self, source):
        """See :meth:`Testrunnerer.runitem`."""
        return self._testrunnerer.runitem(source)

    def inline_runsource(self, source, *cmdlineargs):
        """See :meth:`Testrunnerer.inline_runsource`."""
        return self._testrunnerer.inline_runsource(source, *cmdlineargs)

    def inline_genitems(self, *args):
        """See :meth:`Testrunnerer.inline_genitems`."""
        return self._testrunnerer.inline_genitems(*args)

    def inline_run(self, *args, plugins=(), no_reraise_ctrlc: bool = False):
        """See :meth:`Testrunnerer.inline_run`."""
        return self._testrunnerer.inline_run(
            *args, plugins=plugins, no_reraise_ctrlc=no_reraise_ctrlc
        )

    def runtestrunner_inprocess(self, *args, **kwargs) -> RunResult:
        """See :meth:`Testrunnerer.runtestrunner_inprocess`."""
        return self._testrunnerer.runtestrunner_inprocess(*args, **kwargs)

    def runtestrunner(self, *args, **kwargs) -> RunResult:
        """See :meth:`Testrunnerer.runtestrunner`."""
        return self._testrunnerer.runtestrunner(*args, **kwargs)

    def parseconfig(self, *args) -> Config:
        """See :meth:`Testrunnerer.parseconfig`."""
        return self._testrunnerer.parseconfig(*args)

    def parseconfigure(self, *args) -> Config:
        """See :meth:`Testrunnerer.parseconfigure`."""
        return self._testrunnerer.parseconfigure(*args)

    def getitem(self, source, funcname="test_func"):
        """See :meth:`Testrunnerer.getitem`."""
        return self._testrunnerer.getitem(source, funcname)

    def getitems(self, source):
        """See :meth:`Testrunnerer.getitems`."""
        return self._testrunnerer.getitems(source)

    def getmodulecol(self, source, configargs=(), withinit=False):
        """See :meth:`Testrunnerer.getmodulecol`."""
        return self._testrunnerer.getmodulecol(
            source, configargs=configargs, withinit=withinit
        )

    def collect_by_name(self, modcol: Collector, name: str) -> Item | Collector | None:
        """See :meth:`Testrunnerer.collect_by_name`."""
        return self._testrunnerer.collect_by_name(modcol, name)

    def popen(
        self,
        cmdargs,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=CLOSE_STDIN,
        **kw,
    ):
        """See :meth:`Testrunnerer.popen`."""
        return self._testrunnerer.popen(cmdargs, stdout, stderr, stdin, **kw)

    def run(self, *cmdargs, timeout=None, stdin=CLOSE_STDIN) -> RunResult:
        """See :meth:`Testrunnerer.run`."""
        return self._testrunnerer.run(*cmdargs, timeout=timeout, stdin=stdin)

    def runpython(self, script) -> RunResult:
        """See :meth:`Testrunnerer.runpython`."""
        return self._testrunnerer.runpython(script)

    def runpython_c(self, command):
        """See :meth:`Testrunnerer.runpython_c`."""
        return self._testrunnerer.runpython_c(command)

    def runtestrunner_subprocess(self, *args, timeout=None) -> RunResult:
        """See :meth:`Testrunnerer.runtestrunner_subprocess`."""
        return self._testrunnerer.runtestrunner_subprocess(*args, timeout=timeout)

    def spawn_testrunner(
        self, string: str, expect_timeout: float = 10.0
    ) -> pexpect.spawn:
        """See :meth:`Testrunnerer.spawn_testrunner`."""
        return self._testrunnerer.spawn_testrunner(
            string, expect_timeout=expect_timeout
        )

    def spawn(self, cmd: str, expect_timeout: float = 10.0) -> pexpect.spawn:
        """See :meth:`Testrunnerer.spawn`."""
        return self._testrunnerer.spawn(cmd, expect_timeout=expect_timeout)

    def __repr__(self) -> str:
        return f"<Testdir {self.tmpdir!r}>"

    def __str__(self) -> str:
        return str(self.tmpdir)


class LegacyTestdirPlugin:
    @fixture
    @staticmethod
    def testdir(testrunnerer: Testrunnerer) -> Testdir:
        """
        Identical to :fixture:`testrunnerer`, and provides an instance whose methods return
        legacy ``LEGACY_PATH`` objects instead when applicable.

        New code should avoid using :fixture:`testdir` in favor of :fixture:`testrunnerer`.
        """
        return Testdir(testrunnerer, _istestrunner=True)


@final
@dataclasses.dataclass
class TempdirFactory:
    """Backward compatibility wrapper that implements ``py.path.local``
    for :class:`TempPathFactory`.

    .. note::
        These days, it is preferred to use ``tmp_path_factory``.

        :ref:`About the tmpdir and tmpdir_factory fixtures<tmpdir and tmpdir_factory>`.

    """

    _tmppath_factory: TempPathFactory

    def __init__(
        self, tmppath_factory: TempPathFactory, *, _istestrunner: bool = False
    ) -> None:
        check_istestrunner(_istestrunner)
        self._tmppath_factory = tmppath_factory

    def mktemp(self, basename: str, numbered: bool = True) -> LEGACY_PATH:
        """Same as :meth:`TempPathFactory.mktemp`, but returns a ``py.path.local`` object."""
        return legacy_path(self._tmppath_factory.mktemp(basename, numbered).resolve())

    def getbasetemp(self) -> LEGACY_PATH:
        """Same as :meth:`TempPathFactory.getbasetemp`, but returns a ``py.path.local`` object."""
        return legacy_path(self._tmppath_factory.getbasetemp().resolve())


class LegacyTmpdirPlugin:
    @fixture(scope="session")
    @staticmethod
    def tmpdir_factory(request: FixtureRequest) -> TempdirFactory:
        """Return a :class:`testrunner.TempdirFactory` instance for the test session."""
        # Set dynamically by testrunner_configure().
        return request.config._tmpdirhandler  # type: ignore

    @fixture
    @staticmethod
    def tmpdir(tmp_path: Path) -> LEGACY_PATH:
        """Return a temporary directory (as `legacy_path`_ object)
        which is unique to each test function invocation.
        The temporary directory is created as a subdirectory
        of the base temporary directory, with configurable retention,
        as discussed in :ref:`temporary directory location and retention`.

        .. note::
            These days, it is preferred to use ``tmp_path``.

            :ref:`About the tmpdir and tmpdir_factory fixtures<tmpdir and tmpdir_factory>`.

        .. _legacy_path: https://py.readthedocs.io/en/latest/path.html
        """
        return legacy_path(tmp_path)


def Cache_makedir(self: Cache, name: str) -> LEGACY_PATH:
    """Return a directory path object with the given name.

    Same as :func:`mkdir`, but returns a legacy py path instance.
    """
    return legacy_path(self.mkdir(name))


def FixtureRequest_fspath(self: FixtureRequest) -> LEGACY_PATH:
    """(deprecated) The file system path of the test module which collected this test."""
    return legacy_path(self.path)


def TerminalReporter_startdir(self: TerminalReporter) -> LEGACY_PATH:
    """The directory from which testrunner was invoked.

    Prefer to use ``startpath`` which is a :class:`pathlib.Path`.

    :type: LEGACY_PATH
    """
    return legacy_path(self.startpath)


def Config_invocation_dir(self: Config) -> LEGACY_PATH:
    """The directory from which testrunner was invoked.

    Prefer to use :attr:`invocation_params.dir <InvocationParams.dir>`,
    which is a :class:`pathlib.Path`.

    :type: LEGACY_PATH
    """
    return legacy_path(str(self.invocation_params.dir))


def Config_rootdir(self: Config) -> LEGACY_PATH:
    """The path to the :ref:`rootdir <rootdir>`.

    Prefer to use :attr:`rootpath`, which is a :class:`pathlib.Path`.

    :type: LEGACY_PATH
    """
    return legacy_path(str(self.rootpath))


def Config_inifile(self: Config) -> LEGACY_PATH | None:
    """The path to the :ref:`configfile <configfiles>`.

    Prefer to use :attr:`inipath`, which is a :class:`pathlib.Path`.

    :type: Optional[LEGACY_PATH]
    """
    return legacy_path(str(self.inipath)) if self.inipath else None


def Session_startdir(self: Session) -> LEGACY_PATH:
    """The path from which testrunner was invoked.

    Prefer to use ``startpath`` which is a :class:`pathlib.Path`.

    :type: LEGACY_PATH
    """
    return legacy_path(self.startpath)


def Config__getini_unknown_type(self, name: str, type: str, value: str | list[str]):
    if type == "pathlist":
        # TODO: This assert is probably not valid in all cases.
        assert self.inipath is not None
        dp = self.inipath.parent
        input_values = shlex.split(value) if isinstance(value, str) else value
        return [legacy_path(str(dp / x)) for x in input_values]
    else:
        raise ValueError(f"unknown configuration type: {type}", value)


def Node_fspath(self: Node) -> LEGACY_PATH:
    """(deprecated) returns a legacy_path copy of self.path"""
    return legacy_path(self.path)


def Node_fspath_set(self: Node, value: LEGACY_PATH) -> None:
    self.path = Path(value)


@hookimpl(tryfirst=True)
def testrunner_load_initial_conftests(early_config: Config) -> None:
    """Monkeypatch legacy path attributes in several classes, as early as possible."""
    mp = MonkeyPatch()
    early_config.add_cleanup(mp.undo)

    # Add Cache.makedir().
    mp.setattr(Cache, "makedir", Cache_makedir, raising=False)

    # Add FixtureRequest.fspath property.
    mp.setattr(FixtureRequest, "fspath", property(FixtureRequest_fspath), raising=False)

    # Add TerminalReporter.startdir property.
    mp.setattr(
        TerminalReporter, "startdir", property(TerminalReporter_startdir), raising=False
    )

    # Add Config.{invocation_dir,rootdir,inifile} properties.
    mp.setattr(Config, "invocation_dir", property(Config_invocation_dir), raising=False)
    mp.setattr(Config, "rootdir", property(Config_rootdir), raising=False)
    mp.setattr(Config, "inifile", property(Config_inifile), raising=False)

    # Add Session.startdir property.
    mp.setattr(Session, "startdir", property(Session_startdir), raising=False)

    # Add pathlist configuration type.
    mp.setattr(Config, "_getini_unknown_type", Config__getini_unknown_type)

    # Add Node.fspath property.
    mp.setattr(Node, "fspath", property(Node_fspath, Node_fspath_set), raising=False)


@hookimpl
def testrunner_configure(config: Config) -> None:
    """Installs the LegacyTmpdirPlugin if the ``tmpdir`` plugin is also installed."""
    if config.pluginmanager.has_plugin("tmpdir"):
        mp = MonkeyPatch()
        config.add_cleanup(mp.undo)
        # Create TmpdirFactory and attach it to the config object.
        #
        # This is to comply with existing plugins which expect the handler to be
        # available at testrunner_configure time, but ideally should be moved entirely
        # to the tmpdir_factory session fixture.
        try:
            tmp_path_factory = config._tmp_path_factory  # type: ignore[attr-defined]
        except AttributeError:
            # tmpdir plugin is blocked.
            pass
        else:
            _tmpdirhandler = TempdirFactory(tmp_path_factory, _istestrunner=True)
            mp.setattr(config, "_tmpdirhandler", _tmpdirhandler, raising=False)

        # Register an instance so @fixture above @staticmethod unwraps to a bare
        # function. Class registration would keep the staticmethod descriptor,
        # which resolve_fixture_function then binds onto test instances (#13564).
        config.pluginmanager.register(LegacyTmpdirPlugin(), "legacypath-tmpdir")


@hookimpl
def testrunner_plugin_registered(
    plugin: object, manager: TestrunnerPluginManager
) -> None:
    # testrunnerer is not loaded by default and is commonly loaded from a conftest,
    # so checking for it in `testrunner_configure` is not enough.
    is_testrunnerer = plugin is manager.get_plugin("testrunnerer")
    if is_testrunnerer and not manager.has_plugin("legacypath-testrunnerer"):
        manager.register(LegacyTestdirPlugin(), "legacypath-testrunnerer")
