:tocdepth: 3

.. _`api-reference`:

API Reference
=============

This page contains the full reference to testrunner's API.


Constants
---------

testrunner.__version__
~~~~~~~~~~~~~~~~~~

The current testrunner version, as a string::

    >>> import testrunner
    >>> testrunner.__version__
    '9.0.2'

.. _`hidden-param`:

testrunner.HIDDEN_PARAM
~~~~~~~~~~~~~~~~~~~

.. versionadded:: 8.4

Can be passed to ``ids`` of :py:func:`Metafunc.parametrize <testrunner.Metafunc.parametrize>`
or to ``id`` of :func:`testrunner.param` to hide a parameter set from the test name.
Can only be used at most 1 time, as test names need to be unique.

.. _`version-tuple`:

testrunner.version_tuple
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 7.0

The current testrunner version, as a tuple::

    >>> import testrunner
    >>> testrunner.version_tuple
    (7, 0, 0)

For pre-releases, the last component will be a string with the prerelease version::

    >>> import testrunner
    >>> testrunner.version_tuple
    (7, 0, '0rc1')


Functions
---------

testrunner.approx
~~~~~~~~~~~~~

.. autofunction:: testrunner.approx

testrunner.fail
~~~~~~~~~~~

**Tutorial**: :ref:`skipping`

.. autofunction:: testrunner.fail(reason, [pytrace=True])

.. class:: testrunner.fail.Exception

    The exception raised by :func:`testrunner.fail`.

testrunner.skip
~~~~~~~~~~~

.. autofunction:: testrunner.skip(reason, [allow_module_level=False])

.. class:: testrunner.skip.Exception

    The exception raised by :func:`testrunner.skip`.

.. _`testrunner.importorskip ref`:

testrunner.importorskip
~~~~~~~~~~~~~~~~~~~

.. autofunction:: testrunner.importorskip

testrunner.xfail
~~~~~~~~~~~~

.. autofunction:: testrunner.xfail

.. class:: testrunner.xfail.Exception

    The exception raised by :func:`testrunner.xfail`.

testrunner.exit
~~~~~~~~~~~

.. autofunction:: testrunner.exit(reason, [returncode=None])

.. class:: testrunner.exit.Exception

    The exception raised by :func:`testrunner.exit`.

testrunner.main
~~~~~~~~~~~

**Tutorial**: :ref:`testrunner.main-usage`

.. autofunction:: testrunner.main

testrunner.param
~~~~~~~~~~~~

.. autofunction:: testrunner.param(*values, [id], [marks])

testrunner.raises
~~~~~~~~~~~~~

**Tutorial**: :ref:`assertraises`

.. autofunction:: testrunner.raises(expected_exception: Exception [, *, match])
    :with: excinfo

testrunner.deprecated_call
~~~~~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`ensuring_function_triggers`

.. autofunction:: testrunner.deprecated_call([match])
    :with:

testrunner.register_assert_rewrite
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`assertion-rewriting`

.. autofunction:: testrunner.register_assert_rewrite

testrunner.register_fixture
~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: testrunner.register_fixture

testrunner.warns
~~~~~~~~~~~~

**Tutorial**: :ref:`assertwarnings`

.. autofunction:: testrunner.warns(expected_warning: Exception, [match])
    :with:

testrunner.freeze_includes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`freezing-testrunner`

.. autofunction:: testrunner.freeze_includes

.. _`marks ref`:

Marks
-----

Marks can be used to apply metadata to *test functions* (but not fixtures), which can then be accessed by
fixtures or plugins.




.. _`testrunner.mark.filterwarnings ref`:

testrunner.mark.filterwarnings
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`filterwarnings`

Add warning filters to marked test items.

.. py:function:: testrunner.mark.filterwarnings(filter)

    :keyword str filter:
        A *warning specification string*, which is composed of contents of the tuple ``(action, message, category, module, lineno)``
        as specified in :ref:`python:warning-filter` section of
        the Python documentation, separated by ``":"``. Optional fields can be omitted.
        Module names passed for filtering are not regex-escaped.

        For example:

        .. code-block:: python

            @testrunner.mark.filterwarnings(r"ignore:.*usage will be deprecated.*:DeprecationWarning")
            def test_foo(): ...


.. _`testrunner.mark.parametrize ref`:

testrunner.mark.parametrize
~~~~~~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`parametrize`

This mark has the same signature as :py:meth:`testrunner.Metafunc.parametrize`; see there.


.. _`testrunner.mark.skip ref`:

testrunner.mark.skip
~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`skip`

Unconditionally skip a test function.

.. py:function:: testrunner.mark.skip(reason="unconditional skip")

    :keyword str reason: Reason why the test function is being skipped.


.. _`testrunner.mark.skipif ref`:

testrunner.mark.skipif
~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`skipif`

Skip a test function if a condition is ``True``.

.. py:function:: testrunner.mark.skipif(condition, *, reason=None)

    :type condition: bool or str
    :param condition: ``True/False`` if the condition should be skipped or a :ref:`condition string <string conditions>`.
    :keyword str reason: Reason why the test function is being skipped.


.. _`testrunner.mark.usefixtures ref`:

testrunner.mark.usefixtures
~~~~~~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`usefixtures`

Mark a test function as using the given fixture names.

.. py:function:: testrunner.mark.usefixtures(*names)

    :param args: The names of the fixture to use, as strings.

.. note::

    When using `usefixtures` in hooks, it can only load fixtures when applied to a test function before test setup
    (for example in the `testrunner_collection_modifyitems` hook).

    Also note that this mark has no effect when applied to **fixtures**.



.. _`testrunner.mark.xfail ref`:

testrunner.mark.xfail
~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`xfail`

Marks a test function as *expected to fail*.

.. py:function:: testrunner.mark.xfail(condition=True, *, reason=None, raises=None, run=True, strict=strict_xfail)

    :keyword Union[bool, str] condition:
        Condition for marking the test function as xfail (``True/False`` or a
        :ref:`condition string <string conditions>`). If a ``bool``, you also have
        to specify ``reason`` (see :ref:`condition string <string conditions>`).
    :keyword str reason:
        Reason why the test function is marked as xfail.
    :keyword raises:
        Exception class (or tuple of classes) expected to be raised by the test function; other exceptions will fail the test.
        Note that subclasses of the classes passed will also result in a match (similar to how the ``except`` statement works).
    :type raises: Type[:py:exc:`Exception`] | Tuple[Type[:py:exc:`Exception`], ...] | None

    :keyword bool run:
        Whether the test function should actually be executed. If ``False``, the function will always xfail and will
        not be executed (useful if a function is segfaulting).
    :keyword bool strict:
        * If ``False`` the function will be shown in the terminal output as ``xfailed`` if it fails
          and as ``xpass`` if it passes. In both cases this will not cause the test suite to fail as a whole. This
          is particularly useful to mark *flaky* tests (tests that fail at random) to be tackled later.
        * If ``True``, the function will be shown in the terminal output as ``xfailed`` if it fails, but if it
          unexpectedly passes then it will **fail** the test suite. This is particularly useful to mark functions
          that are always failing and there should be a clear indication if they unexpectedly start to pass (for example
          a new release of a library fixes a known bug).

        Defaults to :confval:`strict_xfail`, which is ``False`` by default.


Custom marks
~~~~~~~~~~~~

Marks are created dynamically using the factory object ``testrunner.mark`` and applied as a decorator.

For example:

.. code-block:: python

    @testrunner.mark.timeout(10, "slow", method="thread")
    def test_function(): ...

Will create and attach a :class:`Mark <testrunner.Mark>` object to the collected
:class:`Item <testrunner.Item>`, which can then be accessed by fixtures or hooks with
:meth:`Node.iter_markers <_testrunner.nodes.Node.iter_markers>`. The ``mark`` object will have the following attributes:

.. code-block:: python

    mark.args == (10, "slow")
    mark.kwargs == {"method": "thread"}

Example for using multiple custom markers:

.. code-block:: python

    @testrunner.mark.timeout(10, "slow", method="thread")
    @testrunner.mark.slow
    def test_function(): ...

When :meth:`Node.iter_markers <_testrunner.nodes.Node.iter_markers>` or :meth:`Node.iter_markers_with_node <_testrunner.nodes.Node.iter_markers_with_node>` is used with multiple markers, the marker closest to the function will be iterated over first. The above example will result in ``@testrunner.mark.slow`` followed by ``@testrunner.mark.timeout(...)``.

.. _`fixtures-api`:

Fixtures
--------

**Tutorial**: :ref:`fixture`

Fixtures are requested by test functions or other fixtures by declaring them as argument names.


Example of a test requiring a fixture:

.. code-block:: python

    def test_output(capsys):
        print("hello")
        out, err = capsys.readouterr()
        assert out == "hello\n"


Example of a fixture requiring another fixture:

.. code-block:: python

    @testrunner.fixture
    def db_session(tmp_path):
        fn = tmp_path / "db.file"
        return connect(fn)

For more details, consult the full :ref:`fixtures docs <fixture>`.


.. _`testrunner.fixture-api`:

@testrunner.fixture
~~~~~~~~~~~~~~~

.. autofunction:: testrunner.fixture
    :decorator:


.. fixture:: capfd

capfd
~~~~~~

**Tutorial**: :ref:`captures`

.. autofunction:: _testrunner.capture.capfd()
    :no-auto-options:


.. fixture:: capfdbinary

capfdbinary
~~~~~~~~~~~~

**Tutorial**: :ref:`captures`

.. autofunction:: _testrunner.capture.capfdbinary()
    :no-auto-options:


.. fixture:: caplog

caplog
~~~~~~

**Tutorial**: :ref:`logging`

.. autofunction:: _testrunner.logging.caplog()
    :no-auto-options:

    Returns a :class:`testrunner.LogCaptureFixture` instance.

.. autoclass:: testrunner.LogCaptureFixture()
    :members:


.. fixture:: capsys

capsys
~~~~~~

**Tutorial**: :ref:`captures`

.. autofunction:: _testrunner.capture.capsys()
    :no-auto-options:

.. autoclass:: testrunner.CaptureFixture()
    :members:

.. fixture:: capteesys

capteesys
~~~~~~~~~

**Tutorial**: :ref:`captures`

.. autofunction:: _testrunner.capture.capteesys()
    :no-auto-options:

.. fixture:: capsysbinary

capsysbinary
~~~~~~~~~~~~

**Tutorial**: :ref:`captures`

.. autofunction:: _testrunner.capture.capsysbinary()
    :no-auto-options:


.. fixture:: cache

config.cache
~~~~~~~~~~~~

**Tutorial**: :ref:`cache`

The ``config.cache`` object allows other plugins and fixtures
to store and retrieve values across test runs. To access it from fixtures
request ``testrunnerconfig`` into your fixture and get it with ``testrunnerconfig.cache``.

Under the hood, the cache plugin uses the simple
``dumps``/``loads`` API of the :py:mod:`json` stdlib module.

``config.cache`` is an instance of :class:`testrunner.Cache`:

.. autoclass:: testrunner.Cache()
   :members:


.. fixture:: doctest_namespace

doctest_namespace
~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`doctest`

.. autofunction:: _testrunner.doctest.doctest_namespace()


.. fixture:: monkeypatch

monkeypatch
~~~~~~~~~~~

**Tutorial**: :ref:`monkeypatching`

.. autofunction:: _testrunner.monkeypatch.monkeypatch()
    :no-auto-options:

    Returns a :class:`~testrunner.MonkeyPatch` instance.

.. autoclass:: testrunner.MonkeyPatch
    :members:


.. fixture:: testrunnerconfig

testrunnerconfig
~~~~~~~~~~~~

.. autofunction:: _testrunner.fixtures.testrunnerconfig()


.. fixture:: testrunnerer

testrunnerer
~~~~~~~~

.. versionadded:: 6.2

Provides a :class:`~testrunner.Testrunnerer` instance that can be used to run and test testrunner itself.

It provides an empty directory where testrunner can be executed in isolation, and contains facilities
to write tests, configuration files, and match against expected output.

To use it, include in your topmost ``conftest.py`` file:

.. code-block:: python

    testrunner_plugins = "testrunnerer"



.. autoclass:: testrunner.Testrunnerer()
    :members:

.. autoclass:: testrunner.RunResult()
    :members:

.. autoclass:: testrunner.LineMatcher()
    :members:
    :special-members: __str__

.. autoclass:: testrunner.HookRecorder()
    :members:

.. autoclass:: testrunner.RecordedHookCall()
    :members:


.. fixture:: record_property

record_property
~~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`record_property example`

.. autofunction:: _testrunner.junitxml.record_property()


.. fixture:: record_testsuite_property

record_testsuite_property
~~~~~~~~~~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`record_testsuite_property example`

.. autofunction:: _testrunner.junitxml.record_testsuite_property()


.. fixture:: recwarn

recwarn
~~~~~~~

**Tutorial**: :ref:`recwarn`

.. autofunction:: _testrunner.recwarn.recwarn()
    :no-auto-options:

.. autoclass:: testrunner.WarningsRecorder()
    :members:
    :special-members: __getitem__, __iter__, __len__


.. fixture:: request

request
~~~~~~~

**Example**: :ref:`request example`

The ``request`` fixture is a special fixture providing information of the requesting test function.

.. autoclass:: testrunner.FixtureRequest()
    :members:


.. fixture:: subtests

subtests
~~~~~~~~

The ``subtests`` fixture enables declaring subtests inside test functions.

**Tutorial**: :ref:`subtests`

.. autoclass:: testrunner.Subtests()
    :members:


.. fixture:: testdir

testdir
~~~~~~~

Identical to :fixture:`testrunnerer`, but provides an instance whose methods return
legacy ``py.path.local`` objects instead when applicable.

New code should avoid using :fixture:`testdir` in favor of :fixture:`testrunnerer`.

.. autoclass:: testrunner.Testdir()
    :members:
    :noindex: TimeoutExpired


.. fixture:: tmp_path

tmp_path
~~~~~~~~

**Tutorial**: :ref:`tmp_path`

.. autofunction:: _testrunner.tmpdir.tmp_path()
    :no-auto-options:


.. fixture:: tmp_path_factory

tmp_path_factory
~~~~~~~~~~~~~~~~

**Tutorial**: :ref:`tmp_path_factory example`

.. _`tmp_path_factory factory api`:

``tmp_path_factory`` is an instance of :class:`~testrunner.TempPathFactory`:

.. autoclass:: testrunner.TempPathFactory()
    :members:


.. fixture:: tmpdir

tmpdir
~~~~~~

**Tutorial**: :ref:`tmpdir and tmpdir_factory`

.. autofunction:: _testrunner.legacypath.LegacyTmpdirPlugin.tmpdir()
    :no-auto-options:


.. fixture:: tmpdir_factory

tmpdir_factory
~~~~~~~~~~~~~~

**Tutorial**: :ref:`tmpdir and tmpdir_factory`

``tmpdir_factory`` is an instance of :class:`~testrunner.TempdirFactory`:

.. autoclass:: testrunner.TempdirFactory()
    :members:


.. _`hook-reference`:

Hooks
-----

**Tutorial**: :ref:`writing-plugins`

Reference to all hooks which can be implemented by :ref:`conftest.py files <localplugin>` and :ref:`plugins <plugins>`.

@testrunner.hookimpl
~~~~~~~~~~~~~~~~

.. function:: testrunner.hookimpl
    :decorator:

    testrunner's decorator for marking functions as hook implementations.

    See :ref:`writinghooks` and :func:`pluggy.HookimplMarker`.

@testrunner.hookspec
~~~~~~~~~~~~~~~~

.. function:: testrunner.hookspec
    :decorator:

    testrunner's decorator for marking functions as hook specifications.

    See :ref:`declaringhooks` and :func:`pluggy.HookspecMarker`.

.. currentmodule:: _testrunner.hookspec

Bootstrapping hooks
~~~~~~~~~~~~~~~~~~~

Bootstrapping hooks called for plugins registered early enough (internal and third-party plugins).

.. hook:: testrunner_load_initial_conftests
.. autofunction:: testrunner_load_initial_conftests
.. hook:: testrunner_cmdline_parse
.. autofunction:: testrunner_cmdline_parse
.. hook:: testrunner_cmdline_main
.. autofunction:: testrunner_cmdline_main

.. _`initialization-hooks`:

Initialization hooks
~~~~~~~~~~~~~~~~~~~~

Initialization hooks called for plugins and ``conftest.py`` files.

.. hook:: testrunner_addoption
.. autofunction:: testrunner_addoption
.. hook:: testrunner_addhooks
.. autofunction:: testrunner_addhooks
.. hook:: testrunner_configure
.. autofunction:: testrunner_configure
.. hook:: testrunner_unconfigure
.. autofunction:: testrunner_unconfigure
.. hook:: testrunner_sessionstart
.. autofunction:: testrunner_sessionstart
.. hook:: testrunner_sessionfinish
.. autofunction:: testrunner_sessionfinish

.. hook:: testrunner_plugin_registered
.. autofunction:: testrunner_plugin_registered

Collection hooks
~~~~~~~~~~~~~~~~

``testrunner`` calls the following hooks for collecting files and directories:

.. hook:: testrunner_collection
.. autofunction:: testrunner_collection
.. hook:: testrunner_ignore_collect
.. autofunction:: testrunner_ignore_collect
.. hook:: testrunner_collect_directory
.. autofunction:: testrunner_collect_directory
.. hook:: testrunner_collect_file
.. autofunction:: testrunner_collect_file
.. hook:: testrunner_pycollect_makemodule
.. autofunction:: testrunner_pycollect_makemodule

For influencing the collection of objects in Python modules
you can use the following hook:

.. hook:: testrunner_pycollect_makeitem
.. autofunction:: testrunner_pycollect_makeitem
.. hook:: testrunner_generate_tests
.. autofunction:: testrunner_generate_tests
.. hook:: testrunner_make_parametrize_id
.. autofunction:: testrunner_make_parametrize_id

Hooks for influencing test skipping:

.. hook:: testrunner_markeval_namespace
.. autofunction:: testrunner_markeval_namespace

After collection is complete, you can modify the order of
items, delete or otherwise amend the test items:

.. hook:: testrunner_collection_modifyitems
.. autofunction:: testrunner_collection_modifyitems

.. note::
    If this hook is implemented in ``conftest.py`` files, it always receives all collected items, not only those
    under the ``conftest.py`` where it is implemented.

.. hook:: testrunner_collection_finish
.. autofunction:: testrunner_collection_finish

Test running (runtest) hooks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All runtest related hooks receive a :py:class:`testrunner.Item <testrunner.Item>` object.

.. hook:: testrunner_runtestloop
.. autofunction:: testrunner_runtestloop
.. hook:: testrunner_runtest_protocol
.. autofunction:: testrunner_runtest_protocol
.. hook:: testrunner_runtest_logstart
.. autofunction:: testrunner_runtest_logstart
.. hook:: testrunner_runtest_logfinish
.. autofunction:: testrunner_runtest_logfinish
.. hook:: testrunner_runtest_setup
.. autofunction:: testrunner_runtest_setup
.. hook:: testrunner_runtest_call
.. autofunction:: testrunner_runtest_call
.. hook:: testrunner_runtest_teardown
.. autofunction:: testrunner_runtest_teardown
.. hook:: testrunner_runtest_makereport
.. autofunction:: testrunner_runtest_makereport
.. hook:: testrunner_fixture_setup
.. autofunction:: testrunner_fixture_setup
.. hook:: testrunner_fixture_post_finalizer
.. autofunction:: testrunner_fixture_post_finalizer

For deeper understanding you may look at the default implementation of
these hooks in ``_testrunner.runner`` and maybe also
in ``_testrunner.pdb`` which interacts with ``_testrunner.capture``
and its input/output capturing in order to immediately drop
into interactive debugging when a test failure occurs.

.. hook:: testrunner_pyfunc_call
.. autofunction:: testrunner_pyfunc_call

Reporting hooks
~~~~~~~~~~~~~~~

Session related reporting hooks:

.. hook:: testrunner_collectstart
.. autofunction:: testrunner_collectstart
.. hook:: testrunner_make_collect_report
.. autofunction:: testrunner_make_collect_report
.. hook:: testrunner_itemcollected
.. autofunction:: testrunner_itemcollected
.. hook:: testrunner_collectreport
.. autofunction:: testrunner_collectreport
.. hook:: testrunner_deselected
.. autofunction:: testrunner_deselected
.. hook:: testrunner_report_header
.. autofunction:: testrunner_report_header
.. hook:: testrunner_report_collectionfinish
.. autofunction:: testrunner_report_collectionfinish
.. hook:: testrunner_report_teststatus
.. autofunction:: testrunner_report_teststatus
.. hook:: testrunner_report_to_serializable
.. autofunction:: testrunner_report_to_serializable
.. hook:: testrunner_report_from_serializable
.. autofunction:: testrunner_report_from_serializable
.. hook:: testrunner_terminal_summary
.. autofunction:: testrunner_terminal_summary
.. hook:: testrunner_warning_recorded
.. autofunction:: testrunner_warning_recorded

Central hook for reporting about test execution:

.. hook:: testrunner_runtest_logreport
.. autofunction:: testrunner_runtest_logreport

Assertion related hooks:

.. hook:: testrunner_assertrepr_compare
.. autofunction:: testrunner_assertrepr_compare
.. hook:: testrunner_assertion_pass
.. autofunction:: testrunner_assertion_pass


Debugging/Interaction hooks
~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are few hooks which can be used for special
reporting or interaction with exceptions:

.. hook:: testrunner_internalerror
.. autofunction:: testrunner_internalerror
.. hook:: testrunner_keyboard_interrupt
.. autofunction:: testrunner_keyboard_interrupt
.. hook:: testrunner_exception_interact
.. autofunction:: testrunner_exception_interact
.. hook:: testrunner_enter_pdb
.. autofunction:: testrunner_enter_pdb
.. hook:: testrunner_leave_pdb
.. autofunction:: testrunner_leave_pdb


Collection tree objects
-----------------------

These are the collector and item classes (collectively called "nodes") which
make up the collection tree.

Node
~~~~

.. autoclass:: _testrunner.nodes.Node()
    :members:
    :show-inheritance:

Collector
~~~~~~~~~

.. autoclass:: testrunner.Collector()
    :members:
    :show-inheritance:

Item
~~~~

.. autoclass:: testrunner.Item()
    :members:
    :show-inheritance:

File
~~~~

.. autoclass:: testrunner.File()
    :members:
    :show-inheritance:

FSCollector
~~~~~~~~~~~

.. autoclass:: _testrunner.nodes.FSCollector()
    :members:
    :show-inheritance:

Session
~~~~~~~

.. autoclass:: testrunner.Session()
    :members:
    :show-inheritance:

Package
~~~~~~~

.. autoclass:: testrunner.Package()
    :members:
    :show-inheritance:

Module
~~~~~~

.. autoclass:: testrunner.Module()
    :members:
    :show-inheritance:

Class
~~~~~

.. autoclass:: testrunner.Class()
    :members:
    :show-inheritance:

Function
~~~~~~~~

.. autoclass:: testrunner.Function()
    :members:
    :show-inheritance:

FunctionDefinition
~~~~~~~~~~~~~~~~~~

.. autoclass:: _testrunner.python.FunctionDefinition()
    :members:
    :show-inheritance:


Objects
-------

Objects accessible from :ref:`fixtures <fixture>` or :ref:`hooks <hook-reference>`
or importable from ``testrunner``.

Approx
~~~~~~

.. autoclass:: testrunner.Approx()
    :members:

CallInfo
~~~~~~~~

.. autoclass:: testrunner.CallInfo()
    :members:

CollectReport
~~~~~~~~~~~~~

.. autoclass:: testrunner.CollectReport()
    :members:
    :show-inheritance:
    :inherited-members:

Config
~~~~~~

.. autoclass:: testrunner.Config()
    :members:

Dir
~~~

.. autoclass:: testrunner.Dir()
    :members:

Directory
~~~~~~~~~

.. autoclass:: testrunner.Directory()
    :members:

ExceptionInfo
~~~~~~~~~~~~~

.. autoclass:: testrunner.ExceptionInfo()
    :members:


ExitCode
~~~~~~~~

.. autoclass:: testrunner.ExitCode
    :members:


FixtureDef
~~~~~~~~~~

.. autoclass:: testrunner.FixtureDef()
    :members:
    :show-inheritance:

MarkDecorator
~~~~~~~~~~~~~

.. autoclass:: testrunner.MarkDecorator()
    :members:


MarkGenerator
~~~~~~~~~~~~~

.. autoclass:: testrunner.MarkGenerator()
    :members:


Mark
~~~~

.. autoclass:: testrunner.Mark()
    :members:


Metafunc
~~~~~~~~

.. autoclass:: testrunner.Metafunc()
    :members:

Parser
~~~~~~

.. autoclass:: testrunner.Parser()
    :members:

OptionGroup
~~~~~~~~~~~

.. autoclass:: testrunner.OptionGroup()
    :members:

TestrunnerPluginManager
~~~~~~~~~~~~~~~~~~~

.. autoclass:: testrunner.TestrunnerPluginManager()
    :members:
    :undoc-members:
    :inherited-members:
    :show-inheritance:

RaisesExc
~~~~~~~~~

.. autoclass:: testrunner.RaisesExc()
    :members:

    .. autoattribute:: fail_reason

RaisesGroup
~~~~~~~~~~~
**Tutorial**: :ref:`assert-matching-exception-groups`

.. autoclass:: testrunner.RaisesGroup()
    :members:

    .. autoattribute:: fail_reason

TerminalReporter
~~~~~~~~~~~~~~~~

.. autoclass:: testrunner.TerminalReporter
    :members:
    :inherited-members:

TestReport
~~~~~~~~~~

.. autoclass:: testrunner.TestReport()
    :members:
    :show-inheritance:
    :inherited-members:

TestShortLogReport
~~~~~~~~~~~~~~~~~~

.. autoclass:: testrunner.TestShortLogReport()
    :members:

Result
~~~~~~~

Result object used within :ref:`hook wrappers <hookwrapper>`, see :py:class:`Result in the pluggy documentation <pluggy.Result>` for more information.

Stash
~~~~~

.. autoclass:: testrunner.Stash
    :special-members: __setitem__, __getitem__, __delitem__, __contains__, __len__
    :members:

.. autoclass:: testrunner.StashKey
    :show-inheritance:
    :members:


Global Variables
----------------

testrunner treats some global variables in a special manner when defined in a test module or
``conftest.py`` files.


.. globalvar:: collect_ignore

**Tutorial**: :ref:`customizing-test-collection`

Can be declared in *conftest.py files* to exclude test directories or modules.
Needs to be a list of paths (``str``, :class:`pathlib.Path` or any :class:`os.PathLike`).

.. code-block:: python

  collect_ignore = ["setup.py"]


.. globalvar:: collect_ignore_glob

**Tutorial**: :ref:`customizing-test-collection`

Can be declared in *conftest.py files* to exclude test directories or modules
with Unix shell-style wildcards. Needs to be ``list[str]`` where ``str`` can
contain glob patterns.

.. code-block:: python

  collect_ignore_glob = ["*_ignore.py"]


.. globalvar:: testrunner_plugins

**Tutorial**: :ref:`available installable plugins`

Can be declared at the **global** level in *test modules* and *conftest.py files* to register additional plugins.
Can be either a ``str`` or ``Sequence[str]``.
Each entry can be the name of an importable module or the entry point name of an installed plugin.

.. code-block:: python

    testrunner_plugins = "myapp.testsupport.myplugin"

.. code-block:: python

    testrunner_plugins = ("myapp.testsupport.tools", "myapp.testsupport.regression")

.. versionchanged:: 9.2
   Entry point names of installed plugins are now also accepted, in addition
   to importable module names.


.. globalvar:: _testrunner_mark

**Tutorial**: :ref:`scoped-marking`

Can be declared at the **global** level in *test modules* to apply one or more :ref:`marks <marks ref>` to all
test functions and methods. Can be either a single mark or a list of marks (applied in left-to-right order).

.. code-block:: python

    import testrunner

    _testrunner_mark = testrunner.mark.webtest


.. code-block:: python

    import testrunner

    _testrunner_mark = [testrunner.mark.integration, testrunner.mark.slow]


Environment Variables
---------------------

Environment variables that can be used to change testrunner's behavior.

.. envvar:: CI

   When set to a non-empty value, testrunner acknowledges that it is running in a CI process. See also :ref:`ci-pipelines`.

.. envvar:: BUILD_NUMBER

   When set to a non-empty value, testrunner acknowledges that it is running in a CI process. Alternative to :envvar:`CI`. See also :ref:`ci-pipelines`.

.. envvar:: TESTRUNNER_ADDOPTS

   This contains a command-line (parsed by the py:mod:`shlex` module) that will be **prepended** to the command line given
   by the user, see :ref:`adding default options` for more information.

.. envvar:: TESTRUNNER_VERSION

   This environment variable is defined at the start of the testrunner session and is undefined afterwards.
   It contains the value of ``testrunner.__version__``, and among other things can be used to easily check if a code is running from within a testrunner run.

.. envvar:: TESTRUNNER_CURRENT_TEST

   This is not meant to be set by users, but is set by testrunner internally with the name of the current test so other
   processes can inspect it, see :ref:`testrunner current test env` for more information.

.. envvar:: TESTRUNNER_DEBUG

   When set, testrunner will print tracing and debug information.

.. envvar:: TESTRUNNER_DEBUG_TEMPROOT

   Root for temporary directories produced by fixtures like :fixture:`tmp_path`
   as discussed in :ref:`temporary directory location and retention`.

.. envvar:: TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD

   When set, disables plugin auto-loading through :std:doc:`entry point packaging
   metadata <packaging:guides/creating-and-discovering-plugins>`. Only plugins
   explicitly specified in :envvar:`TESTRUNNER_PLUGINS` or with :option:`-p` will be loaded.
   See also :ref:`--disable-plugin-autoload <disable_plugin_autoload>`.

.. envvar:: TESTRUNNER_PLUGINS

   Contains comma-separated list of modules or plugin entry point names that
   should be loaded as plugins:

   .. code-block:: bash

       export TESTRUNNER_PLUGINS=mymodule.plugin,xdist

   See also :option:`-p`.

   .. versionchanged:: 9.2
      Entry point names of installed plugins are now also accepted, in
      addition to importable module names.

.. envvar:: TESTRUNNER_THEME

   Sets a `pygment style <https://pygments.org/docs/styles/>`_ to use for the code output.

.. envvar:: TESTRUNNER_THEME_MODE

   Sets the :envvar:`TESTRUNNER_THEME` to be either *dark* or *light*.

.. envvar:: PY_COLORS

   When set to ``1``, testrunner will use color in terminal output.
   When set to ``0``, testrunner will not use color.
   ``PY_COLORS`` takes precedence over ``NO_COLOR`` and ``FORCE_COLOR``.

.. envvar:: NO_COLOR

   When set to a non-empty string (regardless of value), testrunner will not use color in terminal output.
   ``PY_COLORS`` takes precedence over ``NO_COLOR``, which takes precedence over ``FORCE_COLOR``.
   See `no-color.org <https://no-color.org/>`__ for other libraries supporting this community standard.

.. envvar:: FORCE_COLOR

   When set to a non-empty string (regardless of value), testrunner will use color in terminal output.
   ``PY_COLORS`` and ``NO_COLOR`` take precedence over ``FORCE_COLOR``.

Exceptions
----------

.. autoexception:: testrunner.UsageError()
    :show-inheritance:

.. autoexception:: testrunner.FixtureLookupError()
    :show-inheritance:

.. _`warnings ref`:

Warnings
--------

Custom warnings generated in some situations such as improper usage or deprecated features.

.. autoclass:: testrunner.TestrunnerWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerApproxDecimalToleranceWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerAssertRewriteWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerCacheWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerCollectionWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerConfigWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerDeprecationWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerExperimentalApiWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerReturnNotNoneWarning
  :show-inheritance:

.. autoclass:: testrunner.TestrunnerRemovedIn10Warning
  :show-inheritance:

.. autoclass:: testrunner.TestrunnerUnknownMarkWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerUnraisableExceptionWarning
   :show-inheritance:

.. autoclass:: testrunner.TestrunnerUnhandledThreadExceptionWarning
   :show-inheritance:


Consult the :ref:`internal-warnings` section in the documentation for more information.


.. _`ini options ref`:

Configuration Options
---------------------

Here is a list of builtin configuration options that may be written in a ``testrunner.ini`` (or ``.testrunner.ini``),
``pyproject.toml``, ``tox.ini``, or ``setup.cfg`` file, usually located at the root of your repository.

To see each file format in detail, see :ref:`config file formats`.

.. warning::
    Usage of ``setup.cfg`` is not recommended except for very simple use cases. ``.cfg``
    files use a different parser than ``testrunner.ini`` and ``tox.ini`` which might cause hard to track
    down problems.
    When possible, it is recommended to use the latter files, or ``testrunner.toml`` or ``pyproject.toml``, to hold your testrunner configuration.

Configuration options may be overwritten in the command-line by using ``-o/--override-ini``, which can also be
passed multiple times. The expected format is ``name=value``. For example::

   testrunner -o console_output_style=classic -o cache_dir=/tmp/mycache


.. confval:: addopts
   :type: ``list[str]``

   Add the specified ``OPTS`` to the set of command line arguments as if they
   had been specified by the user. Example: if you have this configuration file content:

   .. code-block:: toml

        # content of testrunner.toml
        [testrunner]
        addopts = ["--maxfail=2", "-rf"]  # exit after 2 failures, report fail info

   issuing ``testrunner test_hello.py`` actually means:

   .. code-block:: bash

        testrunner --maxfail=2 -rf test_hello.py


.. confval:: cache_dir
   :type: ``str``
   :default: ``".testrunner_cache"``

   Sets the directory where the cache plugin's content is stored.
   Directory may be relative or absolute path. If setting relative path, then directory is created
   relative to :ref:`rootdir <rootdir>`. Additionally, a path may contain environment
   variables, that will be expanded. For more information about cache plugin
   please refer to :ref:`cache_provider`.

.. confval:: collect_imported_tests
   :type: ``bool``
   :default: ``true``

   .. versionadded:: 8.4

   Setting this to ``false`` will make testrunner collect classes/functions from test
   files **only** if they are defined in that file (as opposed to imported there).

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            collect_imported_tests = false

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            collect_imported_tests = false

   testrunner traditionally collects classes/functions in the test module namespace even if they are imported from another file.

   For example:

   .. code-block:: python

       # contents of src/domain.py
       class Testament: ...


       # contents of tests/test_testament.py
       from domain import Testament


       def test_testament(): ...

   In this scenario, with the default options, testrunner will collect the class `Testament` from `tests/test_testament.py` because it starts with `Test`, even though in this case it is a production class being imported in the test module namespace.

   Set ``collected_imported_tests`` to ``false`` in the configuration file prevents that.

.. confval:: consider_namespace_packages
   :type: ``bool``
   :default: ``false``

   Controls if testrunner should attempt to identify `namespace packages <https://packaging.python.org/en/latest/guides/packaging-namespace-packages>`__
   when collecting Python modules.

   Set to ``True`` if the package you are testing is part of a namespace package.
   Namespace packages are also supported as :option:`--pyargs` target.

   Only `native namespace packages <https://packaging.python.org/en/latest/guides/packaging-namespace-packages/#native-namespace-packages>`__
   are supported, with no plans to support `legacy namespace packages <https://packaging.python.org/en/latest/guides/packaging-namespace-packages/#legacy-namespace-packages>`__.

   For best results when using `consider_namespace_packages`,
   testrunner needs to be able to import your namespace packages.
   This is best achieved by installing the packages in your environment,
   most commonly in `"editable" mode <https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/#working-in-development-mode>`_.
   If you can't install the packages, consider adding the namespace root paths to :confval:`pythonpath`.

   .. versionadded:: 8.1

.. confval:: console_output_style
   :type: ``"classic" | "progress" | "count" | "times" | "progress-even-when-capture-no"``
   :default: ``"progress"``

   Sets the console output style while running tests:

   * ``classic``: classic testrunner output.
   * ``progress``: like classic testrunner output, but with a progress indicator.
   * ``progress-even-when-capture-no``: allows the use of the progress indicator even when ``capture=no``.
   * ``count``: like progress, but shows progress as the number of tests completed instead of a percent.
   * ``times``: show tests duration.

   You can fallback to ``classic`` if you prefer or
   the new mode is causing unexpected problems:

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            console_output_style = "classic"

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            console_output_style = classic


.. confval:: disable_test_id_escaping_and_forfeit_all_rights_to_community_support
   :type: ``bool``
   :default: ``false``

   .. versionadded:: 4.4

   testrunner by default escapes any non-ascii characters used in unicode strings
   for the parametrization because it has several downsides.
   If however you would like to use unicode strings in parametrization
   and see them in the terminal as is (non-escaped), use this option
   in your configuration file:

   .. tab:: toml

       .. code-block:: toml

           [testrunner]
           disable_test_id_escaping_and_forfeit_all_rights_to_community_support = true

   .. tab:: ini

       .. code-block:: ini

           [testrunner]
           disable_test_id_escaping_and_forfeit_all_rights_to_community_support = true

   Keep in mind however that this might cause unwanted side effects and
   even bugs depending on the OS used and plugins currently installed,
   so use it at your own risk.

   See :ref:`parametrizemark`.


.. confval:: parametrize_long_str_id_strategy
   :type: ``str``
   :default: ``"short"``

   .. versionadded:: 9.1

   Strategy for handling long ``str`` or ``bytes`` parameter values when
   auto-generating test IDs for ``@testrunner.mark.parametrize``. This only
   affects auto-generated IDs — explicit IDs set via ``ids=[...]`` or
   ``testrunner.param(..., id=...)`` are never affected.

   Available strategies:

   ``short``
       Values over 100 characters are replaced with ``<argname><index>``
       (e.g. ``a0``, ``a1``). This is the default.

   ``sha256``
       Replace the value with its SHA-256 hex digest, producing a
       fixed-length, content-based ID.

   ``legacy``
       Keep the full value as the ID regardless of length. Use this for
       temporary backward compatibility during migration.

   ``disallow``
       Raise an error for values over 100 characters, requiring the user
       to set explicit IDs.

   Example configuration:

   .. tab:: toml

       .. code-block:: toml

           [testrunner]
           parametrize_long_str_id_strategy = "sha256"

   .. tab:: ini

       .. code-block:: ini

           [testrunner]
           parametrize_long_str_id_strategy = sha256

   See :ref:`parametrizemark`.

.. confval:: doctest_encoding
   :type: ``str``
   :default: ``"utf-8"``

   Default encoding to use to decode text files with docstrings.
   :ref:`See how testrunner handles doctests <doctest>`.


.. confval:: doctest_optionflags
   :type: ``list[str]``

   One or more doctest flag names from the standard ``doctest`` module.
   :ref:`See how testrunner handles doctests <doctest>`.


.. confval:: empty_parameter_set_mark
    :type: ``"skip" | "xfail" | "fail_at_collect"``
    :default: ``"skip"``

    Allows to pick the action for empty parametersets in parameterization

    * ``skip`` skips tests with an empty parameterset
    * ``xfail`` marks tests with an empty parameterset as xfail(run=False)
    * ``fail_at_collect`` raises an exception if parametrize collects an empty parameter set

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            empty_parameter_set_mark = "xfail"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            empty_parameter_set_mark = xfail

    .. note::

      The default value of this option is planned to change to ``xfail`` in future releases
      as this is considered less error prone, see :issue:`3155` for more details.


.. confval:: enable_assertion_pass_hook
   :type: ``bool``
   :default: ``false``

   Enables the :hook:`testrunner_assertion_pass` hook.
   Make sure to delete any previously generated ``.pyc`` cache files.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            enable_assertion_pass_hook = true

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            enable_assertion_pass_hook = true


.. confval:: faulthandler_exit_on_timeout
   :type: ``bool``
   :default: ``false``

   Exit the testrunner process after the per-test timeout is reached by passing
   `exit=True` to the :func:`faulthandler.dump_traceback_later` function. This
   is particularly useful to avoid wasting CI resources for test suites that
   are prone to putting the main Python interpreter into a deadlock state.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            faulthandler_timeout = 5
            faulthandler_exit_on_timeout = true

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            faulthandler_timeout = 5
            faulthandler_exit_on_timeout = true



.. confval:: faulthandler_timeout
   :type: ``float``
   :default: ``0`` (disabled)

   Dumps the tracebacks of all threads if a test takes longer than ``X`` seconds to run (including
   fixture setup and teardown). Implemented using the :func:`faulthandler.dump_traceback_later` function,
   so all caveats there apply.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            faulthandler_timeout = 5

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            faulthandler_timeout = 5

   For more information please refer to :ref:`faulthandler`.


.. confval:: filterwarnings
   :type: ``list[str]``

   Sets a list of filters and actions that should be taken for matched
   warnings. By default all warnings emitted during the test session
   will be displayed in a summary at the end of the test session.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            filterwarnings = [
                'error',
                'ignore::DeprecationWarning',
                # Note the use of single quote below to denote "raw" strings in TOML.
                'ignore:function ham\(\) should not be used:UserWarning',
            ]

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            filterwarnings =
                error
                ignore::DeprecationWarning
                ignore:function ham\(\) should not be used:UserWarning

   This tells testrunner to ignore deprecation warnings and turn all other warnings
   into errors. For more information please refer to :ref:`warnings`.


.. confval:: max_warnings
   :type: ``int | str``

   .. versionadded:: 9.1
   .. versionchanged:: 9.2
        Added support for specifying the value as an integer in TOML configuration.

   Maximum number of warnings allowed before the test run is considered a failure.
   When all tests pass, but the total number of warnings exceeds this value, testrunner exits with
   :class:`testrunner.ExitCode` ``MAX_WARNINGS_ERROR`` (code ``6``).

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            max_warnings = 10

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            max_warnings = 10

   Note that :confval:`filtered warnings <filterwarnings>` do not count toward this maximum total.

   Can also be set via the :option:`--max-warnings` command-line option.


.. confval:: junit_duration_report
    :type: ``"total" | "call"``
    :default: ``"total"``

    .. versionadded:: 4.1

    Configures how durations are recorded into the JUnit XML report:

    * ``total``: duration times reported include setup, call, and teardown times.
    * ``call``: duration times reported include only call times, excluding setup and teardown.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            junit_duration_report = "call"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            junit_duration_report = call


.. confval:: junit_family
    :type: ``"legacy" | "xunit1" | "xunit2"``
    :default: ``"xunit2"``

    .. versionadded:: 4.2
    .. versionchanged:: 6.1
        Default changed to ``xunit2``.

    Configures the format of the generated JUnit XML file. The possible options are:

    * ``xunit1`` (or ``legacy``): produces old style output, compatible with the xunit 1.0 format.
    * ``xunit2``: produces `xunit 2.0 style output <https://github.com/jenkinsci/xunit-plugin/blob/xunit-2.3.2/src/main/resources/org/jenkinsci/plugins/xunit/types/model/xsd/junit-10.xsd>`__, which should be more compatible with latest Jenkins versions.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            junit_family = "xunit2"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            junit_family = xunit2


.. confval:: junit_log_passing_tests
    :type: ``bool``
    :default: ``true``

    .. versionadded:: 4.6

    If ``junit_logging != "no"``, configures if the captured output should be written
    to the JUnit XML file for **passing** tests.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            junit_log_passing_tests = false

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            junit_log_passing_tests = False


.. confval:: junit_logging
    :type: ``"no" | "log" | "system-out" | "system-err" | "out-err" | "all"``
    :default: ``"no"``

    .. versionadded:: 3.5
    .. versionchanged:: 5.4
        ``log``, ``all``, ``out-err`` options added.

    Configures if captured output should be written to the JUnit XML file. Valid values are:

    * ``log``: write only ``logging`` captured output.
    * ``system-out``: write captured ``stdout`` contents.
    * ``system-err``: write captured ``stderr`` contents.
    * ``out-err``: write both captured ``stdout`` and ``stderr`` contents.
    * ``all``: write captured ``logging``, ``stdout`` and ``stderr`` contents.
    * ``no``: no captured output is written.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            junit_logging = "system-out"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            junit_logging = system-out


.. confval:: junit_suite_name
    :type: ``str``
    :default: ``"testrunner"``

    To set the name of the root test suite xml item, you can configure the ``junit_suite_name`` option in your config file:

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            junit_suite_name = "my_suite"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            junit_suite_name = my_suite

.. confval:: log_auto_indent
    :type: ``str``
    :default: ``"false"``

    Allow selective auto-indentation of multiline log messages.

    Supports command line option :option:`--log-auto-indent=[value]`
    and config option ``log_auto_indent = [value]`` to set the
    auto-indentation behavior for all logging.

    ``[value]`` can be:
        * "True" or "On" - Dynamically auto-indent multiline log messages
        * "False" or "Off" or "0" - Do not auto-indent multiline log messages
        * "[positive integer]" - auto-indent multiline log messages by [value] spaces

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_auto_indent = "false"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_auto_indent = false

    Supports passing kwarg ``extra={"auto_indent": [value]}`` to
    calls to ``logging.log()`` to specify auto-indentation behavior for
    a specific entry in the log. ``extra`` kwarg overrides the value specified
    on the command line or in the config.

.. confval:: log_cli
    :type: ``bool``
    :default: ``false``

    Enable log display during test run (also known as :ref:`"live logging" <live_logs>`).

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_cli = true

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_cli = true

.. confval:: log_cli_date_format
    :type: ``str``
    :default: Fallback to ``log_date_format``

    Sets a :py:func:`time.strftime`-compatible string that will be used when formatting dates for live logging.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_cli_date_format = "%Y-%m-%d %H:%M:%S"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_cli_date_format = %Y-%m-%d %H:%M:%S

    For more information, see :ref:`live_logs`.

.. confval:: log_cli_format
    :type: ``str``
    :default: Fallback to ``log_format``

    Sets a :py:mod:`logging`-compatible string used to format live logging messages.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_cli_format = "%(asctime)s %(levelname)s %(message)s"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_cli_format = %(asctime)s %(levelname)s %(message)s

    For more information, see :ref:`live_logs`.


.. confval:: log_cli_level
    :type: ``str``
    :default: Fallback to ``log_level``

    Sets the minimum log message level that should be captured for live logging. The integer value or
    the names of the levels can be used. Note in TOML the integer must be quoted, as there is no support
    for config parameters of mixed type.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_cli_level = "INFO"
            log_cli_level = "10"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_cli_level = INFO
            log_cli_level = 10

    For more information, see :ref:`live_logs`.


.. confval:: log_date_format
    :type: ``str``
    :default: ``"%H:%M:%S"``

    Sets a :py:func:`time.strftime`-compatible string that will be used when formatting dates for logging capture.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_date_format = "%Y-%m-%d %H:%M:%S"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_date_format = %Y-%m-%d %H:%M:%S

    For more information, see :ref:`logging`.


.. confval:: log_file
    :type: ``str``

    Sets a file name relative to the current working directory where log messages should be written to, in addition
    to the other logging facilities that are active.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_file = "logs/testrunner-logs.txt"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_file = logs/testrunner-logs.txt

    For more information, see :ref:`logging`.


.. confval:: log_file_date_format
    :type: ``str``
    :default: Fallback to ``log_date_format``

    Sets a :py:func:`time.strftime`-compatible string that will be used when formatting dates for the logging file.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_file_date_format = "%Y-%m-%d %H:%M:%S"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_file_date_format = %Y-%m-%d %H:%M:%S

    For more information, see :ref:`logging`.

.. confval:: log_file_format
    :type: ``str``
    :default: Fallback to ``log_format``

    Sets a :py:mod:`logging`-compatible string used to format logging messages redirected to the logging file.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_file_format = "%(asctime)s %(levelname)s %(message)s"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_file_format = %(asctime)s %(levelname)s %(message)s

    For more information, see :ref:`logging`.

.. confval:: log_file_level
    :type: ``str``
    :default: Fallback to ``log_level``

    Sets the minimum log message level that should be captured for the logging file.
    The integer value (in TOML, as a string) or the names of the levels can be used.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_file_level = "INFO"
            log_cli_level = "10"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_file_level = INFO
            log_cli_level = 10

    For more information, see :ref:`logging`.


.. confval:: log_file_mode
    :type: ``str``
    :default: ``"w"``

    Sets the mode that the logging file is opened with.
    The options are ``"w"`` to recreate the file or ``"a"`` to append to the file.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_file_mode = "a"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_file_mode = a

    For more information, see :ref:`logging`.


.. confval:: log_format
    :type: ``str``
    :default: ``%(levelname)-8s %(name)s:%(filename)s:%(lineno)d %(message)s``

    Sets a :py:mod:`logging`-compatible string used to format captured logging messages.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_format = "%(asctime)s %(levelname)s %(message)s"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_format = %(asctime)s %(levelname)s %(message)s

    For more information, see :ref:`logging`.


.. confval:: log_level
    :type: ``str``

    Sets the minimum log message level that should be captured for logging capture.
    Not set by default, so it depends on the root/parent log handler's effective level,
    where it is ``"WARNING"`` by default.
    The integer value (in TOML, as a string) or the names of the levels can be used.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            log_level = "INFO"
            log_cli_level = "10"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            log_level = INFO
            log_cli_level = 10

    For more information, see :ref:`logging`.


.. confval:: markers
    :type: ``list[str]``

    When the :confval:`strict_markers` configuration option is set,
    only known markers - defined in code by core testrunner or some plugin - are allowed.

    You can list additional markers in this setting to add them to the whitelist,
    in which case you probably want to set :confval:`strict_markers` to ``true``
    to avoid future regressions:

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            addopts = ["--strict-markers"]
            markers = ["slow", "serial"]

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            strict_markers = true
            markers =
                slow
                serial


.. confval:: minversion
   :type: ``str``

   Specifies a minimal testrunner version required for running tests.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            minversion = 3.0  # will fail if we run with testrunner-2.8

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            minversion = 3.0  # will fail if we run with testrunner-2.8


.. confval:: norecursedirs
   :type: ``list[str]``
   :default: ``["*.egg", ".*", "_darcs", "build", "CVS", "dist", "node_modules", "venv", "{arch}"]``

   Set the directory basename patterns to avoid when recursing
   for test discovery.  The individual (fnmatch-style) patterns are
   applied to the basename of a directory to decide if to recurse into it.
   Pattern matching characters::

        *       matches everything
        ?       matches any single character
        [seq]   matches any character in seq
        [!seq]  matches any char not in seq

   Setting a ``norecursedirs`` replaces the default.  Here is an example of
   how to avoid certain directories:

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            norecursedirs = [".svn", "_build", "tmp*"]

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            norecursedirs = .svn _build tmp*

   This would tell ``testrunner`` to not look into typical subversion or
   sphinx-build directories or into any ``tmp`` prefixed directory.

   Additionally, ``testrunner`` will attempt to intelligently identify and ignore
   a virtualenv.  Any directory deemed to be the root of a virtual environment
   will not be considered during test collection unless
   :option:`--collect-in-virtualenv` is given.  Note also that ``norecursedirs``
   takes precedence over ``--collect-in-virtualenv``; e.g. if you intend to
   run tests in a virtualenv with a base directory that matches ``'.*'`` you
   *must* override ``norecursedirs`` in addition to using the
   ``--collect-in-virtualenv`` flag.


.. confval:: python_classes
   :type: ``list[str]``
   :default: ``["Test"]``

   One or more name prefixes or glob-style patterns determining which classes
   are considered for test collection. Search for multiple glob patterns by
   adding a space between patterns. By default, testrunner will consider any
   class prefixed with ``Test`` as a test collection.  Here is an example of how
   to collect tests from classes that end in ``Suite``:

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            python_classes = ["*Suite"]

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            python_classes = *Suite

   Note that ``unittest.TestCase`` derived classes are always collected
   regardless of this option, as ``unittest``'s own collection framework is used
   to collect those tests.


.. confval:: python_files
   :type: ``list[str]``
   :default: ``["test_*.py", "*_test.py"]``

   One or more Glob-style file patterns determining which python files
   are considered as test modules. Search for multiple glob patterns by
   adding a space between patterns:

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            python_files = ["test_*.py", "check_*.py", "example_*.py"]

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            python_files = test_*.py check_*.py example_*.py

       Or one per line:

       .. code-block:: ini

            [testrunner]
            python_files =
                test_*.py
                check_*.py
                example_*.py



.. confval:: python_functions
   :type: ``list[str]``
   :default: ``["test"]``

   One or more name prefixes or glob-patterns determining which test functions
   and methods are considered tests. Search for multiple glob patterns by
   adding a space between patterns. By default, testrunner will consider any
   function prefixed with ``test`` as a test.  Here is an example of how
   to collect test functions and methods that end in ``_test``:

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            python_functions = ["*_test"]

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            python_functions = *_test

   Note that this has no effect on methods that live on a ``unittest.TestCase``
   derived class, as ``unittest``'s own collection framework is used
   to collect those tests.

   See :ref:`change naming conventions` for more detailed examples.


.. confval:: pythonpath
   :type: ``list[str]``

   Sets list of directories that should be added to the python search path.
   Directories will be added to the head of :data:`sys.path`.
   Similar to the :envvar:`PYTHONPATH` environment variable, the directories will be
   included in where Python will look for imported modules.
   Paths are relative to the :ref:`rootdir <rootdir>` directory.
   Directories remain in path for the duration of the test session.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            pythonpath = ["src1", "src2"]

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            pythonpath = src1 src2


.. confval:: required_plugins
   :type: ``list[str]``

   A space separated list of plugins that must be present for testrunner to run.
   Plugins can be listed with or without version specifiers directly following
   their name. Whitespace between different version specifiers is not allowed.
   If any one of the plugins is not found, emit an error.

   .. tab:: toml

       .. code-block:: toml

           [testrunner]
           required_plugins = ["testrunner-django>=3.0.0,<4.0.0", "testrunner-html", "testrunner-xdist>=1.0.0"]

   .. tab:: ini

       .. code-block:: ini

           [testrunner]
           required_plugins = testrunner-django>=3.0.0,<4.0.0 testrunner-html testrunner-xdist>=1.0.0


.. confval:: strict
    :type: ``bool``
    :default: ``false``

    If set to ``true``, enable "strict mode", which enables the following options:

    * :confval:`strict_config`
    * :confval:`strict_markers`
    * :confval:`strict_parametrization_ids`
    * :confval:`strict_xfail`

    Plugins may also enable their own strictness options.

    If you explicitly set an individual strictness option, it takes precedence over ``strict``.

    .. note::
        If testrunner adds new strictness options in the future, they will also be enabled in strict mode.
        Therefore, you should only enable strict mode if you use a pinned/locked version of testrunner,
        or if you want to proactively adopt new strictness options as they are added.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            strict = true

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            strict = true

    .. versionadded:: 9.0


.. confval:: strict_config
    :type: ``bool``
    :default: ``false``

    If set to ``true``, any warnings encountered while parsing the ``testrunner`` section of the configuration file will raise errors.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            strict_config = true

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            strict_config = true

    You can also enable this option via the :confval:`strict` option.


.. confval:: strict_markers
    :type: ``bool``
    :default: ``false``

    If set to ``true``, markers not registered in the ``markers`` section of the configuration file will raise errors.

    This applies both to markers applied to tests (e.g. ``@testrunner.mark.slow``) and to marker
    names used in :option:`-m` expressions.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            strict_markers = true

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            strict_markers = true

    You can also enable this option via the :confval:`strict` option.


.. confval:: strict_parametrization_ids
    :type: ``bool``
    :default: ``false``

    If set to ``true``, testrunner emits an error if it detects non-unique parameter set IDs.

    If not set, testrunner automatically handles this by adding `0`, `1`, ... to duplicate IDs,
    making them unique.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            strict_parametrization_ids = true

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            strict_parametrization_ids = true

    You can also enable this option via the :confval:`strict` option.

    For example,

    .. code-block:: python

        import testrunner


        @testrunner.mark.parametrize("letter", ["a", "a"])
        def test_letter_is_ascii(letter):
            assert letter.isascii()

    will emit an error because both cases (parameter sets) have the same auto-generated ID "a".

    To fix the error, if you decide to keep the duplicates, explicitly assign unique IDs:

    .. code-block:: python

        import testrunner


        @testrunner.mark.parametrize("letter", ["a", "a"], ids=["a0", "a1"])
        def test_letter_is_ascii(letter):
            assert letter.isascii()

    See :func:`parametrize <testrunner.Metafunc.parametrize>` and :func:`testrunner.param` for other ways to set IDs.


.. confval:: strict_xfail
    :type: ``bool``
    :default: ``false``

    If set to ``true``, tests marked with ``@testrunner.mark.xfail`` that actually succeed will by default fail the
    test suite.
    For more information, see :ref:`xfail strict tutorial`.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            strict_xfail = true

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            strict_xfail = true

    You can also enable this option via the :confval:`strict` option.

    .. versionchanged:: 9.0
        Renamed from ``xfail_strict`` to ``strict_xfail``.
        ``xfail_strict`` is accepted as an alias for ``strict_xfail``.


.. confval:: testpaths
   :type: ``list[str]``

   Sets list of directories that should be searched for tests when
   no specific directories, files or test ids are given in the command line when
   executing testrunner from the :ref:`rootdir <rootdir>` directory.
   File system paths may use shell-style wildcards, including the recursive
   ``**`` pattern.

   Useful when all project tests are in a known location to speed up
   test collection and to avoid picking up undesired tests by accident.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            testpaths = ["testing", "doc"]

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            testpaths = testing doc

   This configuration means that executing:

   .. code-block:: console

       testrunner

   has the same practical effects as executing:

   .. code-block:: console

       testrunner testing doc

.. confval:: tmp_path_retention_count
   :type: ``str``
   :default: ``"3"``

   How many sessions should testrunner keep the `tmp_path` directories,
   according to :confval:`tmp_path_retention_policy`.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            tmp_path_retention_count = "3"

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            tmp_path_retention_count = 3


.. confval:: tmp_path_retention_policy
   :type: ``"all" | "failed" | "none"``
   :default: ``"all"``

   Controls which directories created by the `tmp_path` fixture are kept around,
   based on test outcome.

    * `all`: retains directories for all tests, regardless of the outcome.
    * `failed`: retains directories only for tests with outcome `error` or `failed`.
    * `none`: directories are always removed after each test ends, regardless of the outcome.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            tmp_path_retention_policy = "all"

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            tmp_path_retention_policy = all


.. confval:: truncation_limit_chars
   :type: ``int | str``
   :default: ``640``

   Controls maximum number of characters to truncate assertion message contents.

   Setting value to ``0`` disables the character limit for truncation.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            truncation_limit_chars = 640

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            truncation_limit_chars = 640

   testrunner truncates the assert messages to a certain limit by default to prevent comparison with large data to overload the console output.

   .. note::

        If testrunner detects it is :ref:`running on CI <ci-pipelines>`, truncation is disabled automatically.


.. confval:: truncation_limit_lines
   :type: ``int | str``
   :default: ``8``

   Controls maximum number of lines to truncate assertion message contents.

   Setting value to ``0`` disables the lines limit for truncation.

   .. tab:: toml

       .. code-block:: toml

            [testrunner]
            truncation_limit_lines = 8

   .. tab:: ini

       .. code-block:: ini

            [testrunner]
            truncation_limit_lines = 8

   testrunner truncates the assert messages to a certain limit by default to prevent comparison with large data to overload the console output.

   .. note::

        If testrunner detects it is :ref:`running on CI <ci-pipelines>`, truncation is disabled automatically.


.. confval:: usefixtures
    :type: ``list[str]``

    List of fixtures that will be applied to all test functions; this is semantically the same as applying
    the ``@testrunner.mark.usefixtures`` marker to all test functions.


    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            usefixtures = ["clean_db"]

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            usefixtures =
                clean_db


.. confval:: verbosity_assertions
    :type: ``str``
    :default: ``"auto"``

    Set a verbosity level specifically for assertion related output, overriding the application wide level.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            verbosity_assertions = "2"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            verbosity_assertions = 2

    A special value of ``"auto"`` can be used to explicitly use the global verbosity level.


.. confval:: assertion_text_diff_style
    :type: ``"ndiff" | "block"``
    :default: ``"ndiff"``

    Set how testrunner renders diffs for string equality assertions.

    Supported values are:

    * ``ndiff``: use the inline diff rendering markers.
    * ``block``: render each string in separate ``Left:`` and ``Right:`` blocks.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            assertion_text_diff_style = "block"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            assertion_text_diff_style = block


.. confval:: verbosity_subtests
    :type: ``str``
    :default: ``"auto"``

    Set the verbosity level specifically for **passed** subtests.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            verbosity_subtests = "1"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            verbosity_subtests = 1

    A value of ``1`` or higher will show output for **passed** subtests (**failed** subtests are always reported).
    Passed subtests output can be suppressed with the value ``0``, which overwrites the :option:`-v` command-line option.

    A special value of ``"auto"`` can be used to explicitly use the global verbosity level.

    See also: :ref:`subtests`.


.. confval:: verbosity_test_cases
    :type: ``str``
    :default: ``"auto"``

    Set a verbosity level specifically for test case execution related output, overriding the application wide level.

    .. tab:: toml

        .. code-block:: toml

            [testrunner]
            verbosity_test_cases = "2"

    .. tab:: ini

        .. code-block:: ini

            [testrunner]
            verbosity_test_cases = 2

    A special value of ``"auto"`` can be used to explicitly use the global verbosity level.


.. _`command-line-flags`:

Command-line Flags
------------------

This section documents all command-line options provided by testrunner's core plugins.

.. note::

    External plugins can add their own command-line options.
    This reference documents only the options from testrunner's core plugins.
    To see all available options including those from installed plugins, run ``testrunner --help``.

Test Selection
~~~~~~~~~~~~~~

.. option:: -k EXPRESSION

    Only run tests which match the given substring expression.
    An expression is a Python evaluable expression where all names are substring-matched against test names and their parent classes.

    Examples::

        testrunner -k "test_method or test_other"  # matches names containing 'test_method' OR 'test_other'
        testrunner -k "not test_method"            # matches names NOT containing 'test_method'
        testrunner -k "not test_method and not test_other"  # excludes both

    The matching is case-insensitive.
    Keywords are also matched to classes and functions containing extra names in their ``extra_keyword_matches`` set.

    See :ref:`select-tests` for more information and examples.

.. option:: -m MARKEXPR

    Only run tests matching given mark expression.
    Supports ``and``, ``or``, and ``not`` operators.

    Examples::

        testrunner -m slow                  # run tests marked with @testrunner.mark.slow
        testrunner -m "not slow"            # run tests NOT marked slow
        testrunner -m "mark1 and not mark2" # run tests marked mark1 but not mark2

    See :ref:`mark` for more information on markers.

.. option:: --markers

    Show all available markers (builtin, plugin, and per-project markers defined in configuration).

Test Execution Control
~~~~~~~~~~~~~~~~~~~~~~~

.. option:: -x, --exitfirst

    Exit instantly on first error or failed test.

.. option:: --maxfail=NUM

    Exit after first ``num`` failures or errors.
    Useful for CI environments where you want to fail fast but see a few failures.

.. option:: --last-failed, --lf

    Rerun only the tests that failed at the last run.
    If no tests failed (or no cached data exists), all tests are run.
    See also :confval:`cache_dir` and :ref:`cache`.

.. option:: --failed-first, --ff

    Run all tests, but run the last failures first.
    This may re-order tests and thus lead to repeated fixture setup/teardown.

.. option:: --new-first, --nf

    Run tests from new files first, then the rest of the tests sorted by file modification time.

.. option:: --stepwise, --sw

    Exit on test failure and continue from last failing test next time.
    Useful for fixing multiple test failures one at a time.

    See :ref:`cache stepwise` for more information.

.. option:: --stepwise-skip, --sw-skip

    Ignore the first failing test but stop on the next failing test.
    Implicitly enables :option:`--stepwise`.

.. option:: --stepwise-reset, --sw-reset

    Resets stepwise state, restarting the stepwise workflow.
    Implicitly enables :option:`--stepwise`.

.. option:: --last-failed-no-failures, --lfnf

    With :option:`--last-failed`, determines whether to execute tests when there are no previously known failures or when no cached ``lastfailed`` data was found.

    * ``all`` (default): runs the full test suite again
    * ``none``: just emits a message about no known failures and exits successfully

.. option:: --runxfail

    Report the results of xfail tests as if they were not marked.
    Useful for debugging xfailed tests.
    See :ref:`xfail`.

Collection
~~~~~~~~~~

.. option:: --collect-only, --co

    Only collect tests, don't execute them.
    Shows which tests would be collected and run.

.. option:: --pyargs

    Try to interpret all arguments as Python packages.
    Useful for running tests of installed packages::

        testrunner --pyargs pkg.testing

.. option:: --ignore=PATH

    Ignore path during collection (multi-allowed).
    Can be specified multiple times.

.. option:: --ignore-glob=PATTERN

    Ignore path pattern during collection (multi-allowed).
    Supports glob patterns.

.. option:: --deselect=NODEID_PREFIX

    Deselect item (via node id prefix) during collection (multi-allowed).

.. option:: --confcutdir=DIR

    Only load ``conftest.py`` files relative to specified directory.

.. option:: --noconftest

    Don't load any ``conftest.py`` files.

.. option:: --keep-duplicates

    Keep duplicate tests. By default, testrunner removes duplicate test items.

.. option:: --collect-in-virtualenv

    Don't ignore tests in a local virtualenv directory.
    By default, testrunner skips tests in virtualenv directories.

.. option:: --continue-on-collection-errors

    Force test execution even if collection errors occur.

.. option:: --import-mode

    Prepend/append to sys.path when importing test modules and conftest files.

    * ``prepend`` (default): prepend to sys.path
    * ``append``: append to sys.path
    * ``importlib``: use importlib to import test modules

    See :ref:`pythonpath` for more information.

Fixtures
~~~~~~~~

.. option:: --fixtures, --funcargs

    Show available fixtures, sorted by plugin appearance.
    Fixtures with leading ``_`` are only shown with :option:`--verbose`.

.. option:: --fixtures-per-test

    Show fixtures per test.

.. option:: --setup-only

    Only setup fixtures, do not execute tests.
    See :ref:`how-to-fixtures`.

.. option:: --setup-show

    Show setup of fixtures while executing tests.

.. option:: --setup-plan

    Show what fixtures and tests would be executed but don't execute anything.

Debugging
~~~~~~~~~

.. option:: --pdb

    Start the interactive Python debugger on errors or KeyboardInterrupt.
    See :ref:`pdb-option`.

.. option:: --pdbcls=MODULENAME:CLASSNAME

    Specify a custom interactive Python debugger for use with :option:`--pdb`.

    Example::

        testrunner --pdbcls=IPython.terminal.debugger:TerminalPdb

.. option:: --trace

    Immediately break when running each test.

    See :ref:`trace-option` for more information.

.. option:: --full-trace

    Don't cut any tracebacks (default is to cut).

    See :ref:`how-to-modifying-python-tb-printing` for more information.

.. option:: --debug, --debug=DEBUG_FILE_NAME

    Store internal tracing debug information in this log file.
    This file is opened with ``'w'`` and truncated as a result, care advised.
    Default file name if not specified: ``testrunnerdebug.log``.

.. option:: --trace-config

    Trace considerations of conftest.py files.

Output and Reporting
~~~~~~~~~~~~~~~~~~~~

.. option:: -v, --verbose

    Increase verbosity.
    Can be specified multiple times (e.g., ``-vv``) for even more verbose output.

    See :ref:`testrunner.fine_grained_verbosity` for fine-grained control over verbosity.

.. option:: -q, --quiet

    Decrease verbosity.

.. option:: --verbosity=NUM

    Set verbosity level explicitly. Default: 0.

.. option:: -r CHARS, --report-chars=CHARS

    Show extra test summary info as specified by chars:

    * ``f``: failed
    * ``E``: error
    * ``s``: skipped
    * ``x``: xfailed
    * ``X``: xpassed
    * ``p``: passed
    * ``P``: passed with output
    * ``a``: all except passed (p/P)
    * ``A``: all
    * ``w``: warnings (enabled by default)
    * ``N``: resets the list

    Default: ``'fE'``

    Examples::

        testrunner -rA           # show all outcomes
        testrunner -rfE          # show only failed and errors (default)
        testrunner -rfs          # show failed and skipped

    See :ref:`testrunner.detailed_failed_tests_usage` for more information.

.. option:: --no-header

    Disable header.

.. option:: --no-summary

    Disable summary.

.. option:: --no-fold-skipped

    Do not fold skipped tests in short summary.

.. option:: --force-short-summary

    Force condensed summary output regardless of verbosity level.

.. option:: -l, --showlocals

    Show locals in tracebacks (disabled by default).

.. option:: --no-showlocals

    Hide locals in tracebacks (negate :option:`--showlocals` passed through addopts).

.. option:: --tb=STYLE

    Traceback print mode:

    * ``auto``: intelligent traceback formatting (default)
    * ``long``: exhaustive, informative traceback formatting
    * ``short``: shorter traceback format
    * ``line``: only the failing line
    * ``native``: Python's standard traceback
    * ``no``: no traceback

    See :ref:`how-to-modifying-python-tb-printing` for examples.

.. option:: --xfail-tb

    Show tracebacks for xfail (as long as :option:`--tb` != ``no``).

.. option:: --show-capture

    Controls how captured stdout/stderr/log is shown on failed tests.

    * ``no``: don't show captured output
    * ``stdout``: show captured stdout
    * ``stderr``: show captured stderr
    * ``log``: show captured logging
    * ``all`` (default): show all captured output

.. option:: --color=WHEN

    Color terminal output:

    * ``yes``: always use color
    * ``no``: never use color
    * ``auto`` (default): use color if terminal supports it

.. option:: --code-highlight={yes,no}

    Whether code should be highlighted (only if :option:`--color` is also enabled).
    Default: ``yes``.

.. option:: --pastebin=MODE

    Send failed|all info to bpaste.net pastebin service.

.. option:: --durations=NUM

    Show N slowest setup/test durations (N=0 for all).
    See :ref:`durations`.

.. option:: --durations-min=NUM

    Minimal duration in seconds for inclusion in slowest list.
    Default: 0.005 (or 0.0 if ``-vv`` is given).

Output Capture
~~~~~~~~~~~~~~

.. option:: --capture=METHOD

    Per-test capturing method:

    * ``fd``: capture at file descriptor level (default)
    * ``sys``: capture at sys level
    * ``no``: don't capture output
    * ``tee-sys``: capture but also show output on terminal

    See :ref:`captures`.

.. option:: -s

    Shortcut for :option:`--capture=no`.

JUnit XML
~~~~~~~~~

.. option:: --junit-xml=PATH, --junitxml=PATH

    Create junit-xml style report file at given path.

.. option:: --junit-prefix=STR, --junitprefix=STR

    Prepend prefix to classnames in junit-xml output.

Cache
~~~~~

.. option:: --cache-show[=PATTERN]

    Show cache contents, don't perform collection or tests.
    Default glob pattern: ``'*'``.

.. option:: --cache-clear

    Remove all cache contents at start of test run.
    See :ref:`cache`.

Warnings
~~~~~~~~

.. option:: --disable-testrunner-warnings, --disable-warnings

    Disable warnings summary.

.. option:: -W WARNING, --pythonwarnings=WARNING

    Set which warnings to report, see ``-W`` option of Python itself.
    Can be specified multiple times.

.. option:: --max-warnings=NUM

    Exit with :class:`testrunner.ExitCode` ``MAX_WARNINGS_ERROR`` (code ``6``) if all the tests pass, but the number
    of warnings exceeds the given threshold. By default there is no limit.
    Can also be set via the :confval:`max_warnings` configuration option.

Doctest
~~~~~~~

.. option:: --doctest-modules

    Run doctests in all .py modules.

    See :ref:`doctest` for more information on using doctests with testrunner.

.. option:: --doctest-report

    Choose another output format for diffs on doctest failure:

    * ``none``
    * ``cdiff``
    * ``ndiff``
    * ``udiff``
    * ``only_first_failure``

.. option:: --doctest-glob=PATTERN

    Doctests file matching pattern.
    Default: ``test*.txt``.

.. option:: --doctest-ignore-import-errors

    Ignore doctest collection errors.

.. option:: --doctest-continue-on-failure

    For a given doctest, continue to run after the first failure.

Configuration
~~~~~~~~~~~~~

.. option:: -c FILE, --config-file=FILE

    Load configuration from ``FILE`` instead of trying to locate one of the implicit configuration files.

.. option:: --rootdir=ROOTDIR

    Define root directory for tests.
    Can be relative path: ``'root_dir'``, ``'./root_dir'``, ``'root_dir/another_dir/'``; absolute path: ``'/home/user/root_dir'``; path with variables: ``'$HOME/root_dir'``.

.. option:: --basetemp=DIR

    Base temporary directory for this test run.
    Warning: this directory is removed if it exists.

    See :ref:`temporary directory location and retention` for more information.

.. option:: -o OPTION=VALUE, --override-ini=OPTION=VALUE

    Override configuration option with ``option=value`` style.
    Can be specified multiple times.

    Example::

        testrunner -o strict_xfail=true -o cache_dir=cache

.. option:: --strict-config

    Enables the :confval:`strict_config` option.

.. option:: --strict-markers

    Enables the :confval:`strict_markers` option.

.. option:: --strict

    Enables the :confval:`strict` option (which enables all strictness options).

.. option:: --assert=MODE

    Control assertion debugging tools:

    * ``plain``: performs no assertion debugging
    * ``rewrite`` (default): rewrites assert statements in test modules on import to provide assert expression information

Logging
~~~~~~~

See :ref:`logging` for a guide on using these flags.

.. option:: --log-level=LEVEL

    Level of messages to catch/display.
    Not set by default, so it depends on the root/parent log handler's effective level, where it is ``WARNING`` by default.

.. option:: --log-format=FORMAT

    Log format used by the logging module.

.. option:: --log-date-format=FORMAT

    Log date format used by the logging module.

.. option:: --log-cli-level=LEVEL

    CLI logging level. See :ref:`live_logs`.

.. option:: --log-cli-format=FORMAT

    Log format used by the logging module for CLI output.

.. option:: --log-cli-date-format=FORMAT

    Log date format used by the logging module for CLI output.

.. option:: --log-file=PATH

    Path to a file logging will be written to.

.. option:: --log-file-mode

    Log file open mode:

    * ``w`` (default): recreate the file
    * ``a``: append to the file

.. option:: --log-file-level=LEVEL

    Log file logging level.

.. option:: --log-file-format=FORMAT

    Log format used by the logging module for the log file.

.. option:: --log-file-date-format=FORMAT

    Log date format used by the logging module for the log file.

.. option:: --log-auto-indent=VALUE

    Auto-indent multiline messages passed to the logging module.
    Accepts ``true|on``, ``false|off`` or an integer.

.. option:: --log-disable=LOGGER

    Disable a logger by name. Can be passed multiple times.

Plugin and Extension Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. option:: -p NAME

    Early-load given plugin module name or entry point (multi-allowed).
    To avoid loading of plugins, use the ``no:`` prefix, e.g. ``no:doctest``.
    See also :option:`--disable-plugin-autoload`.

.. option:: --disable-plugin-autoload

    Disable plugin auto-loading through entry point packaging metadata.
    Only plugins explicitly specified in :option:`-p` or env var :envvar:`TESTRUNNER_PLUGINS` will be loaded.

Version and Help
~~~~~~~~~~~~~~~~

.. option:: -V, --version

    Display testrunner version and information about plugins. When given twice, also display information about plugins.

.. option:: -h, --help

    Show help message and configuration info.

Complete Help Output
~~~~~~~~~~~~~~~~~~~~

All the command-line flags can also be obtained by running ``testrunner --help``::

    $ testrunner --help
    usage: testrunner [options] [file_or_dir] [file_or_dir] [...]

    positional arguments:
      file_or_dir

    general:
      -k EXPRESSION         Only run tests which match the given substring
                            expression. An expression is a Python evaluable
                            expression where all names are substring-matched
                            against test names and their parent classes.
                            Example: -k 'test_method or test_other' matches all
                            test functions and classes whose name contains
                            'test_method' or 'test_other', while -k 'not
                            test_method' matches those that don't contain
                            'test_method' in their names. -k 'not test_method
                            and not test_other' will eliminate the matches.
                            Additionally keywords are matched to classes and
                            functions containing extra names in their
                            'extra_keyword_matches' set, as well as functions
                            which have names assigned directly to them. The
                            matching is case-insensitive.
      -m MARKEXPR           Only run tests matching given mark expression. For
                            example: -m 'mark1 and not mark2'.
      --markers             show markers (builtin, plugin and per-project ones).
      -x, --exitfirst       Exit instantly on first error or failed test
      --maxfail=num         Exit after first num failures or errors
      --strict-config       Enables the strict_config option
      --strict-markers      Enables the strict_markers option
      --strict              Enables the strict option
      --fixtures, --funcargs
                            Show available fixtures, sorted by plugin appearance
                            (fixtures with leading '_' are only shown with '-v')
      --fixtures-per-test   Show fixtures per test
      --pdb                 Start the interactive Python debugger on errors or
                            KeyboardInterrupt
      --pdbcls=modulename:classname
                            Specify a custom interactive Python debugger for use
                            with --pdb.For example:
                            --pdbcls=IPython.terminal.debugger:TerminalPdb
      --trace               Immediately break when running each test
      --capture=method      Per-test capturing method: one of fd|sys|no|tee-sys
      -s                    Shortcut for --capture=no
      --runxfail            Report the results of xfail tests as if they were
                            not marked
      --lf, --last-failed   Rerun only the tests that failed at the last run (or
                            all if none failed)
      --ff, --failed-first  Run all tests, but run the last failures first. This
                            may re-order tests and thus lead to repeated fixture
                            setup/teardown.
      --nf, --new-first     Run tests from new files first, then the rest of the
                            tests sorted by file mtime
      --cache-show=[CACHESHOW]
                            Show cache contents, don't perform collection or
                            tests. Optional argument: glob (default: '*').
      --cache-clear         Remove all cache contents at start of test run
      --lfnf, --last-failed-no-failures={all,none}
                            With ``--lf``, determines whether to execute tests
                            when there are no previously (known) failures or
                            when no cached ``lastfailed`` data was found.
                            ``all`` (the default) runs the full test suite
                            again. ``none`` just emits a message about no known
                            failures and exits successfully.
      --sw, --stepwise      Exit on test failure and continue from last failing
                            test next time
      --sw-skip, --stepwise-skip
                            Ignore the first failing test but stop on the next
                            failing test. Implicitly enables --stepwise.
      --sw-reset, --stepwise-reset
                            Resets stepwise state, restarting the stepwise
                            workflow. Implicitly enables --stepwise.

    Reporting:
      --durations=N         Show N slowest setup/test durations (N=0 for all)
      --durations-min=N     Minimal duration in seconds for inclusion in slowest
                            list. Default: 0.005 (or 0.0 if -vv is given).
      -v, --verbose         Increase verbosity
      --no-header           Disable header
      --no-summary          Disable summary
      --no-fold-skipped     Do not fold skipped tests in short summary.
      --force-short-summary
                            Force condensed summary output regardless of
                            verbosity level.
      -q, --quiet           Decrease verbosity
      --verbosity=VERBOSE   Set verbosity. Default: 0.
      -r, --report-chars chars
                            Show extra test summary info as specified by chars:
                            (f)ailed, (E)rror, (s)kipped, (x)failed, (X)passed,
                            (p)assed, (P)assed with output, (a)ll except passed
                            (p/P), or (A)ll. (w)arnings are enabled by default
                            (see --disable-warnings), 'N' can be used to reset
                            the list. (default: 'fE').
      --disable-warnings, --disable-testrunner-warnings
                            Disable warnings summary
      -l, --showlocals      Show locals in tracebacks (disabled by default)
      --no-showlocals       Hide locals in tracebacks (negate --showlocals
                            passed through addopts)
      --tb=style            Traceback print mode
                            (auto/long/short/line/native/no)
      --xfail-tb            Show tracebacks for xfail (as long as --tb != no)
      --show-capture={no,stdout,stderr,log,all}
                            Controls how captured stdout/stderr/log is shown on
                            failed tests. Default: all.
      --full-trace          Don't cut any tracebacks (default is to cut)
      --color=color         Color terminal output (yes/no/auto)
      --code-highlight={yes,no}
                            Whether code should be highlighted (only if --color
                            is also enabled). Default: yes.
      --pastebin=mode       Send failed|all info to bpaste.net pastebin service
      --junitxml, --junit-xml=path
                            Create junit-xml style report file at given path
      --junitprefix, --junit-prefix=str
                            Prepend prefix to classnames in junit-xml output

    testrunner-warnings:
      -W, --pythonwarnings PYTHONWARNINGS
                            Set which warnings to report, see -W option of
                            Python itself
      --max-warnings=num    Exit with error if all tests pass but the number of
                            warnings exceeds this threshold

    collection:
      --collect-only, --co  Only collect tests, don't execute them
      --pyargs              Try to interpret all arguments as Python packages
      --ignore=path         Ignore path during collection (multi-allowed)
      --ignore-glob=path    Ignore path pattern during collection (multi-
                            allowed)
      --deselect=nodeid_prefix
                            Deselect item (via node id prefix) during collection
                            (multi-allowed)
      --confcutdir=dir      Only load conftest.py's relative to specified dir
      --noconftest          Don't load any conftest.py files
      --keep-duplicates     Keep duplicate tests
      --collect-in-virtualenv
                            Don't ignore tests in a local virtualenv directory
      --continue-on-collection-errors
                            Force test execution even if collection errors occur
      --import-mode={prepend,append,importlib}
                            Prepend/append to sys.path when importing test
                            modules and conftest files. Default: prepend.
      --doctest-modules     Run doctests in all .py modules
      --doctest-report={none,cdiff,ndiff,udiff,only_first_failure}
                            Choose another output format for diffs on doctest
                            failure
      --doctest-glob=pat    Doctests file matching pattern, default: test*.txt
      --doctest-ignore-import-errors
                            Ignore doctest collection errors
      --doctest-continue-on-failure
                            For a given doctest, continue to run after the first
                            failure

    test session debugging and configuration:
      -c, --config-file FILE
                            Load configuration from `FILE` instead of trying to
                            locate one of the implicit configuration files.
      --rootdir=ROOTDIR     Define root directory for tests. Can be relative
                            path: 'root_dir', './root_dir',
                            'root_dir/another_dir/'; absolute path:
                            '/home/user/root_dir'; path with variables:
                            '$HOME/root_dir'.
      --basetemp=dir        Base temporary directory for this test run.
                            (Warning: this directory is removed if it exists.)
      -V, --version         Display testrunner version and information about
                            plugins. When given twice, also display information
                            about plugins.
      -h, --help            Show help message and configuration info
      -p name               Early-load given plugin module name or entry point
                            (multi-allowed). To avoid loading of plugins, use
                            the `no:` prefix, e.g. `no:doctest`. See also
                            --disable-plugin-autoload.
      --disable-plugin-autoload
                            Disable plugin auto-loading through entry point
                            packaging metadata. Only plugins explicitly
                            specified in -p or env var TESTRUNNER_PLUGINS will be
                            loaded.
      --trace-config        Trace considerations of conftest.py files
      --debug=[DEBUG_FILE_NAME]
                            Store internal tracing debug information in this log
                            file. This file is opened with 'w' and truncated as
                            a result, care advised. Default: testrunnerdebug.log.
      -o, --override-ini OVERRIDE_INI
                            Override configuration option with "option=value"
                            style, e.g. `-o strict_xfail=True -o
                            cache_dir=cache`.
      --assert=MODE         Control assertion debugging tools.
                            'plain' performs no assertion debugging.
                            'rewrite' (the default) rewrites assert statements
                            in test modules on import to provide assert
                            expression information.
      --setup-only          Only setup fixtures, do not execute tests
      --setup-show          Show setup of fixtures while executing tests
      --setup-plan          Show what fixtures and tests would be executed but
                            don't execute anything

    logging:
      --log-level=LEVEL     Level of messages to catch/display. Not set by
                            default, so it depends on the root/parent log
                            handler's effective level, where it is "WARNING" by
                            default.
      --log-format=LOG_FORMAT
                            Log format used by the logging module
      --log-date-format=LOG_DATE_FORMAT
                            Log date format used by the logging module
      --log-cli-level=LOG_CLI_LEVEL
                            CLI logging level
      --log-cli-format=LOG_CLI_FORMAT
                            Log format used by the logging module
      --log-cli-date-format=LOG_CLI_DATE_FORMAT
                            Log date format used by the logging module
      --log-file=LOG_FILE   Path to a file when logging will be written to
      --log-file-mode={w,a}
                            Log file open mode
      --log-file-level=LOG_FILE_LEVEL
                            Log file logging level
      --log-file-format=LOG_FILE_FORMAT
                            Log format used by the logging module
      --log-file-date-format=LOG_FILE_DATE_FORMAT
                            Log date format used by the logging module
      --log-auto-indent=LOG_AUTO_INDENT
                            Auto-indent multiline messages passed to the logging
                            module. Accepts true|on, false|off or an integer.
      --log-disable=LOGGER_DISABLE
                            Disable a logger by name. Can be passed multiple
                            times.

    [testrunner] configuration options in the first testrunner.toml|testrunner.ini|tox.ini|setup.cfg|pyproject.toml file found:

      markers (linelist):   Register new markers for test functions
      empty_parameter_set_mark ('skip' | 'xfail' | 'fail_at_collect'):
                            Default marker for empty parametersets
      strict_config (bool): Any warnings encountered while parsing the `testrunner`
                            section of the configuration file raise errors
      strict_markers (bool):
                            Markers not registered in the `markers` section of
                            the configuration file raise errors
      strict (bool):        Enables all strictness options, currently:
                            strict_config, strict_markers, strict_xfail,
                            strict_parametrization_ids
      filterwarnings (linelist):
                            Each line specifies a pattern for
                            warnings.filterwarnings. Processed after
                            -W/--pythonwarnings.
      max_warnings (int | string):
                            Exit with error if all tests pass but the number of
                            warnings exceeds this threshold
      norecursedirs (args): Directory patterns to avoid for recursion
      testpaths (args):     Directories to search for tests when no files or
                            directories are given on the command line
      collect_imported_tests (bool):
                            Whether to collect tests in imported modules outside
                            `testpaths`
      consider_namespace_packages (bool):
                            Consider namespace packages when resolving module
                            names during import
      usefixtures (args):   List of default fixtures to be used with this
                            project
      python_files (args):  Glob-style file patterns for Python test module
                            discovery
      python_classes (args):
                            Prefixes or glob names for Python test class
                            discovery
      python_functions (args):
                            Prefixes or glob names for Python test function and
                            method discovery
      disable_test_id_escaping_and_forfeit_all_rights_to_community_support (bool):
                            Disable string escape non-ASCII characters, might
                            cause unwanted side effects(use at your own risk)
      strict_parametrization_ids (bool):
                            Emit an error if non-unique parameter set IDs are
                            detected
      console_output_style ('classic' | 'progress' | 'count' | 'times' | 'progress-even-when-capture-no'):
                            Console output: "classic", or with additional
                            progress information ("progress" (percentage) |
                            "count" | "times" | "progress-even-when-capture-no"
                            (forces progress even when capture=no)
      verbosity_test_cases (string):
                            Specify a verbosity level for test case execution,
                            overriding the main level. Higher levels will
                            provide more detailed information about each test
                            case executed.
      strict_xfail (bool):  Default for the strict parameter of xfail markers
                            when not given explicitly (default: False) (alias:
                            xfail_strict)
      tmp_path_retention_count (string):
                            How many sessions should we keep the `tmp_path`
                            directories, according to
                            `tmp_path_retention_policy`.
      tmp_path_retention_policy ('all' | 'failed' | 'none'):
                            Controls which directories created by the `tmp_path`
                            fixture are kept around, based on test outcome.
      enable_assertion_pass_hook (bool):
                            Enables the testrunner_assertion_pass hook. Make sure to
                            delete any previously generated pyc cache files.
      truncation_limit_lines (int | string):
                            Set threshold of LINES after which truncation will
                            take effect
      truncation_limit_chars (int | string):
                            Set threshold of CHARS after which truncation will
                            take effect
      assertion_text_diff_style ('ndiff' | 'block'):
                            Choose how testrunner renders diffs for string equality
                            assertions
      verbosity_assertions (string):
                            Specify a verbosity level for assertions, overriding
                            the main level. Higher levels will provide more
                            detailed explanation when an assertion fails.
      junit_suite_name (string):
                            Test suite name for JUnit report
      junit_logging ('no' | 'log' | 'system-out' | 'system-err' | 'out-err' | 'all'):
                            Write captured log messages to JUnit report
      junit_log_passing_tests (bool):
                            Capture log information for passing tests to JUnit
                            report:
      junit_duration_report ('total' | 'call'):
                            Duration time to report
      junit_family ('legacy' | 'xunit1' | 'xunit2'):
                            Emit XML for schema
      doctest_optionflags (args):
                            Option flags for doctests
      doctest_encoding (string):
                            Encoding used for doctest files
      cache_dir (string):   Cache directory path
      log_level (string):   Default value for --log-level
      log_format (string):  Default value for --log-format
      log_date_format (string):
                            Default value for --log-date-format
      log_cli (bool):       Enable log display during test run (also known as
                            "live logging")
      log_cli_level (string):
                            Default value for --log-cli-level
      log_cli_format (string):
                            Default value for --log-cli-format
      log_cli_date_format (string):
                            Default value for --log-cli-date-format
      log_file (string):    Default value for --log-file
      log_file_mode (string):
                            Default value for --log-file-mode
      log_file_level (string):
                            Default value for --log-file-level
      log_file_format (string):
                            Default value for --log-file-format
      log_file_date_format (string):
                            Default value for --log-file-date-format
      log_auto_indent (string):
                            Default value for --log-auto-indent
      faulthandler_timeout (string):
                            Dump the traceback of all threads if a test takes
                            more than TIMEOUT seconds to finish
      faulthandler_exit_on_timeout (bool):
                            Exit the test process if a test takes more than
                            faulthandler_timeout seconds to finish
      verbosity_subtests (string):
                            Specify verbosity level for subtests. Higher levels
                            will generate output for passed subtests. Failed
                            subtests are always reported.
      addopts (args):       Extra command line options
      minversion (string):  Minimally required testrunner version
      pythonpath (paths):   Add paths to sys.path
      required_plugins (args):
                            Plugins that must be present for testrunner to run

    Environment variables:
      CI                       When set to a non-empty value, testrunner knows it is running in a CI process and does not truncate summary info
      BUILD_NUMBER             Equivalent to CI
      TESTRUNNER_ADDOPTS           Extra command line options
      TESTRUNNER_PLUGINS           Comma-separated plugins to load during startup
      TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD Set to disable plugin auto-loading
      TESTRUNNER_DEBUG             Set to enable debug tracing of testrunner's internals
      TESTRUNNER_DEBUG_TEMPROOT    Override the system temporary directory
      TESTRUNNER_THEME             The Pygments style to use for code output
      TESTRUNNER_THEME_MODE        Set the TESTRUNNER_THEME to be either 'dark' or 'light'


    to see available markers type: testrunner --markers
    to see available fixtures type: testrunner --fixtures
    (shown according to specified file_or_dir or current dir if not specified; fixtures with leading '_' are only shown with the '-v' option
