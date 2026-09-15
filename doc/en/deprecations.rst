.. _deprecations:

Deprecations and Removals
=========================

This page lists all testrunner features that are currently deprecated or have been removed in past major releases.
The objective is to give users a clear rationale why a certain feature has been removed, and what alternatives
should be used instead.


Deprecated Features
-------------------

Below is a complete list of all testrunner features which are considered deprecated. Using those features will issue
:class:`~testrunner.TestrunnerWarning` or subclasses, which can be filtered using :ref:`standard warning filters <warnings>`.


.. _callspec2-renamed:

``_testrunner.python.CallSpec2`` renamed to ``CallSpec``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.1

The private ``_testrunner.python.CallSpec2`` name has been renamed to ``CallSpec``.

Plugins that import ``CallSpec2`` should update to ``CallSpec``. The old
``CallSpec2`` alias remains available for now and will be removed in testrunner 10.


.. _fixture-nodeid-deprecated:

Passing ``baseid``/``nodeid`` strings to fixture registration APIs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.1

Passing ``baseid`` to :class:`~testrunner.FixtureDef` or ``nodeid`` strings to
``FixtureManager._register_fixture`` and ``FixtureManager.parsefactories``
is deprecated. These are internal testrunner APIs that are used by some plugins.

Use the ``node`` parameter instead for fixture scoping. This enables more robust
node-based matching instead of fragile string prefix matching.

.. code-block:: python

    # Deprecated
    fixture_manager.parsefactories(plugin_obj, nodeid="tests/sub")
    fixture_manager._register_fixture(name="fix", func=func, nodeid="tests/sub")

    # Use instead
    fixture_manager.parsefactories(holder=plugin_obj, node=directory_node)
    testrunner.register_fixture(name="fix", func=func, node=directory_node)

The equivalent of passing ``nodeid=None`` (global visibility) is ``node=session``.

In testrunner 10, the ``baseid`` and ``nodeid`` string parameters will be removed.


.. _fixturedef-has-location-deprecated:

``FixtureDef.has_location``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.1

The private ``FixtureDef.has_location`` attribute is deprecated and will be removed in testrunner 10.

It indicated whether a fixture was found from a node or a conftest in the collection tree (as opposed to a non-conftest plugin).
It was used to determine the override order of fixtures, pushing fixtures with "no location" to the front of the override chain (such that they are chosen last).
The override order is now determined by the visibility of the fixtures in the collection tree, making this distinction obsolete.


.. _console-main:

``testrunner.console_main()``
~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.1

:func:`testrunner.console_main` is deprecated and will be removed in testrunner 10.

This function is the CLI entry point used internally by the ``testrunner`` console script
and ``python -m testrunner``. It was never intended for programmatic use, and exposing it
in the public API led to confusion with :func:`testrunner.main`, which is the correct way
to invoke testrunner from Python code.

If you are calling ``testrunner.console_main()`` in your code, replace it with :func:`testrunner.main`:

.. code-block:: python

    # Deprecated
    testrunner.console_main()

    # Use this instead
    exit_code = testrunner.main()


.. _pastebin-deprecated:

The ``--pastebin`` option
~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.1

The :option:`--pastebin` option has been deprecated due to being very niche, being the only feature in core testrunner relying on an external service and having low usage.

The plugin which implements ``--pastebin`` has been extracted to a separate package, :pypi:`testrunner-pastebin`.
Please install ``testrunner-pastebin`` if you want to keep using ``--pastebin``.


.. _dynamic-fixture-request-during-teardown:

``request.getfixturevalue()`` during fixture teardown
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.1

Calling :meth:`request.getfixturevalue() <testrunner.FixtureRequest.getfixturevalue>`
during teardown to request a fixture that was not already requested is deprecated.

This pattern is brittle because teardown runs after testrunner has started unwinding active scopes.
Depending on the requested fixture's scope and the current teardown order, the lookup may appear
to work, or it may fail.

In testrunner 10, first-time fixture requests made during teardown will become an error.
If teardown logic needs another fixture, request it before teardown begins, either by
declaring it in the fixture signature or by calling ``request.getfixturevalue()`` before
the fixture yields.

Fixtures that were already requested before teardown started are unaffected and may still
be retrieved while they remain active, though this is discouraged.


.. _config-inicfg:

``config.inicfg``
~~~~~~~~~~~~~~~~~

.. deprecated:: 9.0

The private ``config.inicfg`` attribute is deprecated.
Use :meth:`config.getini() <testrunner.Config.getini>` to access configuration values instead.

``config.inicfg`` was never documented and it should have had a ``_`` prefix from the start.
Testrunner performs caching, transformation and aliasing on configuration options which make direct access to the raw ``config.inicfg`` untenable.

**Reading configuration values:**

Instead of accessing ``config.inicfg`` directly, use :meth:`config.getini() <testrunner.Config.getini>`:

.. code-block:: python

    # Deprecated
    value = config.inicfg["some_option"]

    # Use this instead
    value = config.getini("some_option")

**Setting configuration values:**

Setting or deleting configuration values after initialization is not supported.
If you need to override configuration values, use the ``-o`` command line option:

.. code-block:: bash

    testrunner -o some_option=value

or set them in your configuration file instead.


.. _parametrize-iterators:

Non-Collection iterables in ``@testrunner.mark.parametrize``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.1

Using non-:class:`~collections.abc.Collection` iterables (such as generators, iterators, or custom iterable objects)
for the ``argvalues`` parameter in :ref:`@testrunner.mark.parametrize <testrunner.mark.parametrize ref>`
and :meth:`metafunc.parametrize <testrunner.Metafunc.parametrize>` is deprecated.

These iterables get exhausted after the first iteration, leading to tests getting unexpectedly skipped in cases such as:

* Running :func:`testrunner.main()` multiple times in the same process
* Using class-level parametrize decorators where the same mark is applied to multiple test methods
* Collecting tests multiple times

Example of problematic code:

.. code-block:: python

    import testrunner


    def data_generator():
        yield 1
        yield 2


    @testrunner.mark.parametrize("n", data_generator())
    class Test:
        def test_1(self, n):
            pass

        # test_2 will be skipped because data_generator() is exhausted.
        def test_2(self, n):
            pass

You can fix it by converting generators and iterators to lists or tuples:

.. code-block:: python

    import testrunner


    def data_generator():
        yield 1
        yield 2


    @testrunner.mark.parametrize("n", list(data_generator()))
    class Test:
        def test_1(self, n):
            pass

        def test_2(self, n):
            pass

Note that :class:`range` objects are ``Collection`` and are not affected by this deprecation.


.. _class-scoped-fixture-as-instance-method:

Class-scoped fixture as instance method
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.1

Defining a class-scoped fixture as an instance method (without ``@classmethod``) is deprecated
and will be removed in testrunner 10.0.

When a class-scoped fixture is defined as an instance method, any attributes set on ``self``
will not be visible to test methods. This happens because testrunner creates a new instance of the
test class for each test method, while the fixture runs only once per class on a different instance.

**Before** (deprecated):

.. code-block:: python

    class TestExample:
        @testrunner.fixture(scope="class")
        def setup_data(self):
            self.data = [1, 2, 3]  # This won't be visible to tests!

        def test_something(self, setup_data):
            assert self.data == [
                1,
                2,
                3,
            ]  # AttributeError: 'TestExample' object has no attribute 'data'

**After** (recommended):

.. code-block:: python

    class TestExample:
        @testrunner.fixture(scope="class")
        @classmethod
        def setup_data(cls):
            cls.data = [1, 2, 3]

        def test_something(self, setup_data):
            assert self.data == [1, 2, 3]  # Works correctly

Using ``@classmethod`` ensures attributes are set on the class itself, making them accessible
to all test methods.

.. deprecated:: 9.2

Similarly, using a scope higher than ``class`` (``module``, ``package`` or ``session``)
without using ``@classmethod`` (or ``@staticmethod``) is deprecated and will be
removed in testrunner 10.0.

.. _monkeypatch-fixup-namespace-packages:

``monkeypatch.syspath_prepend`` with legacy namespace packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.0

When using :meth:`monkeypatch.syspath_prepend() <testrunner.MonkeyPatch.syspath_prepend>`,
testrunner automatically calls ``pkg_resources.fixup_namespace_packages()`` if ``pkg_resources`` is imported.
This is only needed for legacy namespace packages that use ``pkg_resources.declare_namespace()``.

Legacy namespace packages are deprecated in favor of native namespace packages (:pep:`420`).
If you are using ``pkg_resources.declare_namespace()`` in your ``__init__.py`` files,
you should migrate to native namespace packages by removing the ``__init__.py`` files from your namespace packages.

This deprecation warning will only be issued when:

1. ``pkg_resources`` is imported, and
2. The specific path being prepended contains a declared namespace package (via ``pkg_resources.declare_namespace()``)

To fix this warning, convert your legacy namespace packages to native namespace packages:

**Legacy namespace package** (deprecated):

.. code-block:: python

    # mypkg/__init__.py
    __import__("pkg_resources").declare_namespace(__name__)

**Native namespace package** (recommended):

Simply remove the ``__init__.py`` file entirely.
Python 3.3+ natively supports namespace packages without ``__init__.py``.


.. _hook-markers:

Configuring hook specs/impls using markers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.2

Before pluggy, testrunner's plugin library, was its own package and had a clear API,
testrunner just used ``testrunner.mark`` to configure hooks.

The :py:func:`testrunner.hookimpl` and :py:func:`testrunner.hookspec` decorators
have been available since years and should be used instead.

.. code-block:: python

    @testrunner.mark.tryfirst
    def testrunner_runtest_call(): ...


    # or
    def testrunner_runtest_call(): ...


    testrunner_runtest_call.tryfirst = True

should be changed to:

.. code-block:: python

    @testrunner.hookimpl(tryfirst=True)
    def testrunner_runtest_call(): ...

Changed ``hookimpl`` attributes:

* ``tryfirst``
* ``trylast``
* ``optionalhook``
* ``hookwrapper``

Changed ``hookwrapper`` attributes:

* ``firstresult``
* ``historic``


Directly constructing internal classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.0

Directly constructing the following classes is now deprecated:

- ``_testrunner.mark.structures.Mark``
- ``_testrunner.mark.structures.MarkDecorator``
- ``_testrunner.mark.structures.MarkGenerator``
- ``_testrunner.python.Metafunc``
- ``_testrunner.runner.CallInfo``
- ``_testrunner._code.ExceptionInfo``
- ``_testrunner.config.argparsing.Parser``
- ``_testrunner.config.argparsing.OptionGroup``
- ``_testrunner.testrunnerer.HookRecorder``

These constructors have always been considered private, but now issue a deprecation warning, which may become a hard error in testrunner 8.

.. _diamond-inheritance-deprecated:

Diamond inheritance between :class:`testrunner.Collector` and :class:`testrunner.Item`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.0

Defining a custom testrunner node type which is both an :class:`~testrunner.Item` and a :class:`~testrunner.Collector` (e.g. :class:`~testrunner.File`) now issues a warning.
It was never sanely supported and triggers hard to debug errors.

Some plugins providing linting/code analysis have been using this as a hack.
Instead, a separate collector node should be used, which collects the item. See
:ref:`non-python tests` for an example, as well as an `example pr fixing inheritance`_.

.. _example pr fixing inheritance: https://github.com/asmeurer/testrunner-flakes/pull/40/files


.. _uncooperative-constructors-deprecated:

Constructors of custom :class:`~_testrunner.nodes.Node` subclasses should take ``**kwargs``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.0

If custom subclasses of nodes like :class:`testrunner.Item` override the
``__init__`` method, they should take ``**kwargs``. Thus,

.. code-block:: python

    class CustomItem(testrunner.Item):
        def __init__(self, name, parent, additional_arg):
            super().__init__(name, parent)
            self.additional_arg = additional_arg

should be turned into:

.. code-block:: python

    class CustomItem(testrunner.Item):
        def __init__(self, *, additional_arg, **kwargs):
            super().__init__(**kwargs)
            self.additional_arg = additional_arg

to avoid hard-coding the arguments testrunner can pass to the superclass.
See :ref:`non-python tests` for a full example.

For cases without conflicts, no deprecation warning is emitted. For cases with
conflicts (such as :class:`testrunner.File` now taking ``path`` instead of
``fspath``, as :ref:`outlined above <node-ctor-fspath-deprecation>`), a
deprecation warning is now raised.


.. _yield-fixture-deprecated:

The ``yield_fixture`` function/decorator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 6.2

``testrunner.yield_fixture`` is a deprecated alias for :func:`testrunner.fixture` and will be removed in testrunner 10.

It has been so for a very long time, so it can be searched/replaced safely.


Removed Features and Breaking Changes
-------------------------------------

As stated in our :ref:`backwards-compatibility` policy, deprecated features are removed only in major releases after
an appropriate period of deprecation has passed.

Some breaking changes which could not be deprecated are also listed.


.. _import-or-skip-import-error:

``testrunner.importorskip`` default behavior regarding :class:`ImportError`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 8.2
.. versionremoved:: 9.1

Traditionally :func:`testrunner.importorskip` captured :class:`ImportError`, with the original intent being to skip
tests where a dependent module is not installed, for example testing with different dependencies.

However, some packages might be installed in the system but not importable due to some other issue, for example
a compilation error or a broken installation. In those cases, :func:`testrunner.importorskip` would still silently skip
the test, but more often than not users would rather see the unexpected error so the underlying issue can be fixed.

In ``8.2``, the ``exc_type`` parameter was added, giving users the ability to pass
:class:`ModuleNotFoundError` to skip tests only if the module cannot really be found, and not because of some other
error.

As of ``9.1``, :func:`testrunner.importorskip` only captures :class:`ModuleNotFoundError` by default.
If you want to preserve the previous behavior and skip on other :class:`ImportError` exceptions during import,
pass ``exc_type=ImportError`` explicitly.


.. _node-ctor-fspath-deprecation:

``fspath`` argument for Node constructors replaced with ``pathlib.Path``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.0
.. versionremoved:: 9.1

In order to support the transition from ``py.path.local`` to :mod:`pathlib`,
the ``fspath`` argument to :class:`~_testrunner.nodes.Node` constructors like
:func:`testrunner.Function.from_parent()` and :func:`testrunner.Class.from_parent()`
is now deprecated.

Plugins which construct nodes should pass the ``path`` argument, of type
:class:`pathlib.Path`, instead of the ``fspath`` argument.

Plugins which implement custom items and collectors are encouraged to replace
``fspath`` parameters (``py.path.local``) with ``path`` parameters
(``pathlib.Path``), and drop any other usage of the ``py`` library if possible.

If possible, plugins with custom items should use :ref:`cooperative
constructors <uncooperative-constructors-deprecated>` to avoid hardcoding
arguments they only pass on to the superclass.

.. note::
    The name of the :class:`~_testrunner.nodes.Node` arguments and attributes (the
    new attribute being ``path``) is **the opposite** of the situation for
    hooks, :ref:`outlined below <legacy-path-hooks-deprecated>` (the old
    argument being ``path``).

    This is an unfortunate artifact due to historical reasons, which should be
    resolved in future versions as we slowly get rid of the :pypi:`py`
    dependency (see :issue:`9283` for a longer discussion).

Due to the ongoing migration of methods like :meth:`~testrunner.Item.reportinfo`
which still is expected to return a ``py.path.local`` object, nodes still have
both ``fspath`` (``py.path.local``) and ``path`` (``pathlib.Path``) attributes,
no matter what argument was used in the constructor. We expect to deprecate the
``fspath`` attribute in a future release.


.. _sync-test-async-fixture:

sync test depending on async fixture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 8.4
.. versionremoved:: 9.0

Testrunner has for a long time given an error when encountering an asynchronous test function, prompting the user to install
a plugin that can handle it. It has not given any errors if you have an asynchronous fixture that's depended on by a
synchronous test. If the fixture was an async function you did get an "unawaited coroutine" warning, but for async yield fixtures you didn't even get that.
This is a problem even if you do have a plugin installed for handling async tests, as they may require
special decorators for async fixtures to be handled, and some may not robustly handle if a user accidentally requests an
async fixture from their sync tests. Fixture values being cached can make this even more unintuitive, where everything will
"work" if the fixture is first requested by an async test, and then requested by a synchronous test.

Unfortunately there is no 100% reliable method of identifying when a user has made a mistake, versus when they expect an
unawaited object from their fixture that they will handle on their own. To suppress this warning
when you in fact did intend to handle this you can wrap your async fixture in a synchronous fixture:

.. code-block:: python

    import asyncio
    import testrunner


    @testrunner.fixture
    async def unawaited_fixture():
        return 1


    def test_foo(unawaited_fixture):
        assert 1 == asyncio.run(unawaited_fixture)

should be changed to


.. code-block:: python

    import asyncio
    import testrunner


    @testrunner.fixture
    def unawaited_fixture():
        async def inner_fixture():
            return 1

        return inner_fixture()


    def test_foo(unawaited_fixture):
        assert 1 == asyncio.run(unawaited_fixture)


You can also make use of `testrunner_fixture_setup` to handle the coroutine/asyncgen before testrunner sees it - this is the way current async testrunner plugins handle it.

If a user has an async fixture with ``autouse=True`` in their ``conftest.py``, or in a file
containing both synchronous tests and the fixture, they will receive this warning.
Unless you're using a plugin that specifically handles async fixtures
with synchronous tests, we strongly recommend against this practice.
It can lead to unpredictable behavior (with larger scopes, it may appear to "work" if an async
test is the first to request the fixture, due to value caching) and will generate
unawaited-coroutine runtime warnings (but only for non-yield fixtures).
Additionally, it creates ambiguity for other developers about whether the fixture is intended to perform
setup for synchronous tests.

The `anyio testrunner plugin <https://anyio.readthedocs.io/en/stable/testing.html>`_ supports
synchronous tests with async fixtures, though certain limitations apply.



Applying a mark to a fixture function
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.4
.. versionremoved:: 9.0

Applying a mark to a fixture function never had any effect, but it is a common user error.

.. code-block:: python

    @testrunner.mark.usefixtures("clean_database")
    @testrunner.fixture
    def user() -> User: ...

Users expected in this case that the ``usefixtures`` mark would have its intended effect of using the ``clean_database`` fixture when ``user`` was invoked, when in fact it has no effect at all.

Now testrunner will issue a warning when it encounters this problem, and will raise an error in the future versions.

.. _legacy-path-hooks-deprecated:

``py.path.local`` arguments for hooks replaced with ``pathlib.Path``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.0
.. versionremoved:: 9.0

In order to support the transition from ``py.path.local`` to :mod:`pathlib`, the following hooks now receive additional arguments:

*  :hook:`testrunner_ignore_collect(collection_path: pathlib.Path) <testrunner_ignore_collect>` as equivalent to ``path``
*  :hook:`testrunner_collect_file(file_path: pathlib.Path) <testrunner_collect_file>` as equivalent to ``path``
*  :hook:`testrunner_pycollect_makemodule(module_path: pathlib.Path) <testrunner_pycollect_makemodule>` as equivalent to ``path``
*  :hook:`testrunner_report_header(start_path: pathlib.Path) <testrunner_report_header>` as equivalent to ``startdir``
*  :hook:`testrunner_report_collectionfinish(start_path: pathlib.Path) <testrunner_report_collectionfinish>` as equivalent to ``startdir``

The accompanying ``py.path.local`` based paths have been deprecated: plugins which manually invoke those hooks should only pass the new ``pathlib.Path`` arguments, and users should change their hook implementations to use the new ``pathlib.Path`` arguments.

.. note::
    The name of the :class:`~_testrunner.nodes.Node` arguments and attributes,
    :ref:`outlined above <node-ctor-fspath-deprecation>` (the new attribute
    being ``path``) is **the opposite** of the situation for hooks (the old
    argument being ``path``).

    This is an unfortunate artifact due to historical reasons, which should be
    resolved in future versions as we slowly get rid of the :pypi:`py`
    dependency (see :issue:`9283` for a longer discussion).

.. _yield tests deprecated:

``yield`` tests
~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

    ``yield`` tests ``xfail``.

.. versionremoved:: 8.4

    ``yield`` tests raise a collection error.

testrunner no longer supports ``yield``-style tests, where a test function actually ``yield`` functions and values
that are then turned into proper test methods. Example:

.. code-block:: python

    def check(x, y):
        assert x**x == y


    def test_squared():
        yield check, 2, 4
        yield check, 3, 9

This would result in two actual test functions being generated.

This form of test function doesn't support fixtures properly, and users should switch to ``testrunner.mark.parametrize``:

.. code-block:: python

    @testrunner.mark.parametrize("x, y", [(2, 4), (3, 9)])
    def test_squared(x, y):
        assert x**x == y

.. _nose-deprecation:

Support for tests written for nose
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.2
.. versionremoved:: 8.0

Support for running tests written for `nose <https://nose.readthedocs.io/en/latest/>`__ is now deprecated.

``nose`` has been in maintenance mode-only for years, and maintaining the plugin is not trivial as it spills
over the code base (see :issue:`9886` for more details).

setup/teardown
^^^^^^^^^^^^^^

One thing that might catch users by surprise is that plain ``setup`` and ``teardown`` methods are not testrunner native,
they are in fact part of the ``nose`` support.


.. code-block:: python

    class Test:
        def setup(self):
            self.resource = make_resource()

        def teardown(self):
            self.resource.close()

        def test_foo(self): ...

        def test_bar(self): ...



Native testrunner support uses ``setup_method`` and ``teardown_method`` (see :ref:`xunit-method-setup`), so the above should be changed to:

.. code-block:: python

    class Test:
        def setup_method(self):
            self.resource = make_resource()

        def teardown_method(self):
            self.resource.close()

        def test_foo(self): ...

        def test_bar(self): ...


This is easy to do in an entire code base by doing a simple find/replace.

@with_setup
^^^^^^^^^^^

Code using `@with_setup <with-setup-nose>`_ such as this:

.. code-block:: python

    from nose.tools import with_setup


    def setup_some_resource(): ...


    def teardown_some_resource(): ...


    @with_setup(setup_some_resource, teardown_some_resource)
    def test_foo(): ...

Will also need to be ported to a supported testrunner style. One way to do it is using a fixture:

.. code-block:: python

    import testrunner


    def setup_some_resource(): ...


    def teardown_some_resource(): ...


    @testrunner.fixture
    def some_resource():
        setup_some_resource()
        yield
        teardown_some_resource()


    def test_foo(some_resource): ...


.. _`with-setup-nose`: https://nose.readthedocs.io/en/latest/testing_tools.html?highlight=with_setup#nose.tools.with_setup


The ``compat_co_firstlineno`` attribute
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Nose inspects this attribute on function objects to allow overriding the function's inferred line number.
Testrunner no longer respects this attribute.



Passing ``msg=`` to ``testrunner.skip``, ``testrunner.fail`` or ``testrunner.exit``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.0
.. versionremoved:: 8.0

Passing the keyword argument ``msg`` to :func:`testrunner.skip`, :func:`testrunner.fail` or :func:`testrunner.exit`
is now deprecated and ``reason`` should be used instead.  This change is to bring consistency between these
functions and the ``@testrunner.mark.skip`` and ``@testrunner.mark.xfail`` markers which already accept a ``reason`` argument.

.. code-block:: python

    def test_fail_example():
        # old
        testrunner.fail(msg="foo")
        # new
        testrunner.fail(reason="bar")


    def test_skip_example():
        # old
        testrunner.skip(msg="foo")
        # new
        testrunner.skip(reason="bar")


    def test_exit_example():
        # old
        testrunner.exit(msg="foo")
        # new
        testrunner.exit(reason="bar")


.. _instance-collector-deprecation:

The ``testrunner.Instance`` collector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 7.0

The ``testrunner.Instance`` collector type has been removed.

Previously, Python test methods were collected as :class:`~testrunner.Class` -> ``Instance`` -> :class:`~testrunner.Function`.
Now :class:`~testrunner.Class` collects the test methods directly.

Most plugins which reference ``Instance`` do so in order to ignore or skip it,
using a check such as ``if isinstance(node, Instance): return``.
Such plugins should simply remove consideration of ``Instance`` on testrunner>=7.
However, to keep such uses working, a dummy type has been instanced in ``testrunner.Instance`` and ``_testrunner.python.Instance``,
and importing it emits a deprecation warning. This was removed in testrunner 8.


Using ``testrunner.warns(None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.0
.. versionremoved:: 8.0

:func:`testrunner.warns(None) <testrunner.warns>` is now deprecated because it was frequently misused.
Its correct usage was checking that the code emits at least one warning of any type - like ``testrunner.warns()``
or ``testrunner.warns(Warning)``.

See :ref:`warns use cases` for examples.


Backward compatibilities in ``Parser.addoption``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 2.4
.. versionremoved:: 8.0

Several behaviors of :meth:`Parser.addoption <testrunner.Parser.addoption>` are now
removed in testrunner 8 (deprecated since testrunner 2.4.0):

- ``parser.addoption(..., help=".. %default ..")`` - use ``%(default)s`` instead.
- ``parser.addoption(..., type="int/string/float/complex")`` - use ``type=int`` etc. instead.


The ``--strict`` command-line option (reintroduced)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 6.2
.. versionchanged:: 9.0

The ``--strict`` command-line option had been deprecated in favor of ``--strict-markers``, which
better conveys what the option does.

In version 8.1, we accidentally un-deprecated ``--strict``.

In version 9.0, we changed ``--strict`` to make it set the new :confval:`strict`
configuration option. It now enables all strictness related options (including
:confval:`strict_markers`).


.. _cmdline-preparse-deprecated:

Implementing the ``testrunner_cmdline_preparse`` hook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 7.0
.. versionremoved:: 8.0

Implementing the ``testrunner_cmdline_preparse`` hook has been officially deprecated.
Implement the :hook:`testrunner_load_initial_conftests` hook instead.

.. code-block:: python

    def testrunner_cmdline_preparse(config: Config, args: List[str]) -> None: ...


    # becomes:


    def testrunner_load_initial_conftests(
        early_config: Config, parser: Parser, args: List[str]
    ) -> None: ...


Collection changes in testrunner 8
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Added a new :class:`testrunner.Directory` base collection node, which all collector nodes for filesystem directories are expected to subclass.
This is analogous to the existing :class:`testrunner.File` for file nodes.

Changed :class:`testrunner.Package` to be a subclass of :class:`testrunner.Directory`.
A ``Package`` represents a filesystem directory which is a Python package,
i.e. contains an ``__init__.py`` file.

:class:`testrunner.Package` now only collects files in its own directory; previously it collected recursively.
Sub-directories are collected as sub-collector nodes, thus creating a collection tree which mirrors the filesystem hierarchy.

:attr:`session.name <testrunner.Session.name>` is now ``""``; previously it was the rootdir directory name.
This matches :attr:`session.nodeid <_testrunner.nodes.Node.nodeid>` which has always been `""`.

Added a new :class:`testrunner.Dir` concrete collection node, a subclass of :class:`testrunner.Directory`.
This node represents a filesystem directory, which is not a :class:`testrunner.Package`,
i.e. does not contain an ``__init__.py`` file.
Similarly to ``Package``, it only collects the files in its own directory,
while collecting sub-directories as sub-collector nodes.

Files and directories are now collected in alphabetical order jointly, unless changed by a plugin.
Previously, files were collected before directories.

The collection tree now contains directories/packages up to the :ref:`rootdir <rootdir>`,
for initial arguments that are found within the rootdir.
For files outside the rootdir, only the immediate directory/package is collected --
note however that collecting from outside the rootdir is discouraged.

As an example, given the following filesystem tree::

    myroot/
        testrunner.ini
        top/
        ├── aaa
        │   └── test_aaa.py
        ├── test_a.py
        ├── test_b
        │   ├── __init__.py
        │   └── test_b.py
        ├── test_c.py
        └── zzz
            ├── __init__.py
            └── test_zzz.py

the collection tree, as shown by `testrunner --collect-only top/` but with the otherwise-hidden :class:`~testrunner.Session` node added for clarity,
is now the following::

    <Session>
      <Dir myroot>
        <Dir top>
          <Dir aaa>
            <Module test_aaa.py>
              <Function test_it>
          <Module test_a.py>
            <Function test_it>
          <Package test_b>
            <Module test_b.py>
              <Function test_it>
          <Module test_c.py>
            <Function test_it>
          <Package zzz>
            <Module test_zzz.py>
              <Function test_it>

Previously, it was::

    <Session>
      <Module top/test_a.py>
        <Function test_it>
      <Module top/test_c.py>
        <Function test_it>
      <Module top/aaa/test_aaa.py>
        <Function test_it>
      <Package test_b>
        <Module test_b.py>
          <Function test_it>
      <Package zzz>
        <Module test_zzz.py>
          <Function test_it>

Code/plugins which rely on a specific shape of the collection tree might need to update.


:class:`testrunner.Package` is no longer a :class:`testrunner.Module` or :class:`testrunner.File`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionchanged:: 8.0

The ``Package`` collector node designates a Python package, that is, a directory with an `__init__.py` file.
Previously ``Package`` was a subtype of ``testrunner.Module`` (which represents a single Python module),
the module being the `__init__.py` file.
This has been deemed a design mistake (see :issue:`11137` and :issue:`7777` for details).

The ``path`` property of ``Package`` nodes now points to the package directory instead of the ``__init__.py`` file.

Note that a ``Module`` node for ``__init__.py`` (which is not a ``Package``) may still exist,
if it is picked up during collection (e.g. if you configured :confval:`python_files` to include ``__init__.py`` files).


Collecting ``__init__.py`` files no longer collects package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 8.0

Running `testrunner pkg/__init__.py` now collects the `pkg/__init__.py` file (module) only.
Previously, it collected the entire `pkg` package, including other test files in the directory, but excluding tests in the `__init__.py` file itself
(unless :confval:`python_files` was changed to allow `__init__.py` file).

To collect the entire package, specify just the directory: `testrunner pkg`.


The ``testrunner.collect`` module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 6.0
.. versionremoved:: 7.0

The ``testrunner.collect`` module is no longer part of the public API, all its names
should now be imported from ``testrunner`` directly instead.



The ``testrunner_warning_captured`` hook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 6.0
.. versionremoved:: 7.0

This hook has an `item` parameter which cannot be serialized by ``testrunner-xdist``.

Use the ``testrunner_warning_recorded`` hook instead, which replaces the ``item`` parameter
by a ``nodeid`` parameter.



The ``testrunner._fillfuncargs`` function
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 6.0
.. versionremoved:: 7.0

This function was kept for backward compatibility with an older plugin.

Its functionality is not meant to be used directly, but if you must replace
it, use `function._request._fillfixtures()` instead, though note this is not
a public API and may break in the future.


``--no-print-logs`` command-line option
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 5.4
.. versionremoved:: 6.0


The ``--no-print-logs`` option and ``log_print`` ini setting are removed. If
you used them, please use ``--show-capture`` instead.

A ``--show-capture`` command-line option was added in ``testrunner 3.5.0`` which allows to specify how to
display captured output when tests fail: ``no``, ``stdout``, ``stderr``, ``log`` or ``all`` (the default).


.. _resultlog deprecated:

Result log (``--result-log``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 4.0
.. versionremoved:: 6.0

The ``--result-log`` option produces a stream of test reports which can be
analysed at runtime, but it uses a custom format which requires users to implement their own
parser.

The :pypi:`testrunner-reportlog` plugin provides a ``--report-log`` option, a more standard and extensible alternative, producing
one JSON object per-line, and should cover the same use cases. Please try it out and provide feedback.

The ``testrunner-reportlog`` plugin might even be merged into the core
at some point, depending on the plans for the plugins and number of users using it.

``testrunner_collect_directory`` hook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 6.0

The ``testrunner_collect_directory`` hook has not worked properly for years (it was called
but the results were ignored). Users may consider using :hook:`testrunner_collection_modifyitems` instead.

TerminalReporter.writer
~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 6.0

The ``TerminalReporter.writer`` attribute has been deprecated and should no longer be used. This
was inadvertently exposed as part of the public API of that plugin and ties it too much
with ``py.io.TerminalWriter``.

Plugins that used ``TerminalReporter.writer`` directly should instead use ``TerminalReporter``
methods that provide the same functionality.

.. _junit-family changed default value:

``junit_family`` default value change to "xunit2"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionchanged:: 6.0

The default value of ``junit_family`` option will change to ``xunit2`` in testrunner 6.0, which
is an update of the old ``xunit1`` format and is supported by default in modern tools
that manipulate this type of file (for example, Jenkins, Azure Pipelines, etc.).

Users are recommended to try the new ``xunit2`` format and see if their tooling that consumes the JUnit
XML file supports it.

To use the new format, update your configuration file:

.. tab:: toml

    .. code-block:: toml

        [testrunner]
        junit_family = "xunit2"

.. tab:: ini

    .. code-block:: ini

        [testrunner]
        junit_family = xunit2

If you discover that your tooling does not support the new format, and want to keep using the
legacy version, set the option to ``legacy`` instead:

.. tab:: toml

    .. code-block:: toml

        [testrunner]
        junit_family = "legacy"

.. tab:: ini

    .. code-block:: ini

        [testrunner]
        junit_family = legacy

By using ``legacy`` you will keep using the legacy/xunit1 format when upgrading to
testrunner 6.0, where the default format will be ``xunit2``.

In order to let users know about the transition, testrunner will issue a warning in case
the ``--junit-xml`` option is given in the command line but ``junit_family`` is not explicitly
configured in ``testrunner.ini``.

Services known to support the ``xunit2`` format:

* `Jenkins <https://www.jenkins.io/>`__ with the `JUnit <https://plugins.jenkins.io/junit>`__ plugin.
* `Azure Pipelines <https://azure.microsoft.com/en-us/services/devops/pipelines>`__.

Node Construction changed to ``Node.from_parent``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionchanged:: 6.0

The construction of nodes now should use the named constructor ``from_parent``.
This limitation in api surface intends to enable better/simpler refactoring of the collection tree.

This means that instead of :code:`MyItem(name="foo", parent=collector, obj=42)`
one now has to invoke :code:`MyItem.from_parent(collector, name="foo")`.

Plugins that wish to support older versions of testrunner and suppress the warning can use
`hasattr` to check if `from_parent` exists in that version:

.. code-block:: python

    def testrunner_pycollect_makeitem(collector, name, obj):
        if hasattr(MyItem, "from_parent"):
            item = MyItem.from_parent(collector, name="foo")
            item.obj = 42
            return item
        else:
            return MyItem(name="foo", parent=collector, obj=42)

Note that ``from_parent`` should only be called with keyword arguments for the parameters.


``testrunner.fixture`` arguments are keyword only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 6.0

Passing arguments to testrunner.fixture() as positional arguments has been removed - pass them by keyword instead.

``funcargnames`` alias for ``fixturenames``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 6.0

The ``FixtureRequest``, ``Metafunc``, and ``Function`` classes track the names of
their associated fixtures, with the aptly-named ``fixturenames`` attribute.

Prior to testrunner 2.3, this attribute was named ``funcargnames``, and we have kept
that as an alias since.  It is finally due for removal, as it is often confusing
in places where we or plugin authors must distinguish between fixture names and
names supplied by non-fixture things such as ``testrunner.mark.parametrize``.


.. _testrunner.config global deprecated:

``testrunner.config`` global
~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 5.0

The ``testrunner.config`` global object is deprecated.  Instead use
``request.config`` (via the ``request`` fixture) or if you are a plugin author
use the ``testrunner_configure(config)`` hook. Note that many hooks can also access
the ``config`` object indirectly, through ``session.config`` or ``item.config`` for example.


.. _`raises message deprecated`:

``"message"`` parameter of ``testrunner.raises``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 5.0

It is a common mistake to think this parameter will match the exception message, while in fact
it only serves to provide a custom message in case the ``testrunner.raises`` check fails. To prevent
users from making this mistake, and because it is believed to be little used, testrunner is
deprecating it without providing an alternative for the moment.

If you have a valid use case for this parameter, consider that to obtain the same results
you can just call ``testrunner.fail`` manually at the end of the ``with`` statement.

For example:

.. code-block:: python

    with testrunner.raises(TimeoutError, message="Client got unexpected message"):
        wait_for(websocket.recv(), 0.5)


Becomes:

.. code-block:: python

    with testrunner.raises(TimeoutError):
        wait_for(websocket.recv(), 0.5)
        testrunner.fail("Client got unexpected message")


If you still have concerns about this deprecation and future removal, please comment on
:issue:`3974`.


.. _raises-warns-exec:

``raises`` / ``warns`` with a string as the second argument
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 5.0

Use the context manager form of these instead.  When necessary, invoke ``exec``
directly.

Example:

.. code-block:: python

    testrunner.raises(ZeroDivisionError, "1 / 0")
    testrunner.raises(SyntaxError, "a $ b")

    testrunner.warns(DeprecationWarning, "my_function()")
    testrunner.warns(SyntaxWarning, "assert(1, 2)")

Becomes:

.. code-block:: python

    with testrunner.raises(ZeroDivisionError):
        1 / 0
    with testrunner.raises(SyntaxError):
        exec("a $ b")  # exec is required for invalid syntax

    with testrunner.warns(DeprecationWarning):
        my_function()
    with testrunner.warns(SyntaxWarning):
        exec("assert(1, 2)")  # exec is used to avoid a top-level warning




Using ``Class`` in custom Collectors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

Using objects named ``"Class"`` as a way to customize the type of nodes that are collected in ``Collector``
subclasses has been deprecated. Users instead should use ``testrunner_pycollect_makeitem`` to customize node types during
collection.

This issue should affect only advanced plugins who create new collection types, so if you see this warning
message please contact the authors so they can change the code.


.. _marks in testrunner.parametrize deprecated:

marks in ``testrunner.mark.parametrize``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

Applying marks to values of a ``testrunner.mark.parametrize`` call is now deprecated. For example:

.. code-block:: python

    @testrunner.mark.parametrize(
        "a, b",
        [
            (3, 9),
            testrunner.mark.xfail(reason="flaky")(6, 36),
            (10, 100),
            (20, 200),
            (40, 400),
            (50, 500),
        ],
    )
    def test_foo(a, b): ...

This code applies the ``testrunner.mark.xfail(reason="flaky")`` mark to the ``(6, 36)`` value of the above parametrization
call.

This was considered hard to read and understand, and also its implementation presented problems to the code preventing
further internal improvements in the marks architecture.

To update the code, use ``testrunner.param``:

.. code-block:: python

    @testrunner.mark.parametrize(
        "a, b",
        [
            (3, 9),
            testrunner.param(6, 36, marks=testrunner.mark.xfail(reason="flaky")),
            (10, 100),
            (20, 200),
            (40, 400),
            (50, 500),
        ],
    )
    def test_foo(a, b): ...


.. _testrunner_funcarg__ prefix deprecated:

``testrunner_funcarg__`` prefix
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

In very early testrunner versions fixtures could be defined using the ``testrunner_funcarg__`` prefix:

.. code-block:: python

    def testrunner_funcarg__data():
        return SomeData()

Switch over to the ``@testrunner.fixture`` decorator:

.. code-block:: python

    @testrunner.fixture
    def data():
        return SomeData()



[testrunner] section in setup.cfg files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

``[testrunner]`` sections in ``setup.cfg`` files should now be named ``[tool:testrunner]``
to avoid conflicts with other distutils commands.


.. _metafunc.addcall deprecated:

Metafunc.addcall
~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

``Metafunc.addcall`` was a precursor to the current parametrized mechanism. Users should use
:meth:`testrunner.Metafunc.parametrize` instead.

Example:

.. code-block:: python

    def testrunner_generate_tests(metafunc):
        metafunc.addcall({"i": 1}, id="1")
        metafunc.addcall({"i": 2}, id="2")

Becomes:

.. code-block:: python

    def testrunner_generate_tests(metafunc):
        metafunc.parametrize("i", [1, 2], ids=["1", "2"])


.. _cached_setup deprecated:

``cached_setup``
~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

``request.cached_setup`` was the precursor of the setup/teardown mechanism available to fixtures.

Example:

.. code-block:: python

    @testrunner.fixture
    def db_session():
        return request.cached_setup(
            setup=Session.create, teardown=lambda session: session.close(), scope="module"
        )

This should be updated to make use of standard fixture mechanisms:

.. code-block:: python

    @testrunner.fixture(scope="module")
    def db_session():
        session = Session.create()
        yield session
        session.close()


You can consult :std:doc:`funcarg comparison section in the docs <funcarg_compare>` for
more information.


.. _testrunner_plugins in non-top-level conftest files deprecated:

testrunner_plugins in non-top-level conftest files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

Defining :globalvar:`testrunner_plugins` is now deprecated in non-top-level conftest.py
files because they will activate referenced plugins *globally*, which is surprising because for all other testrunner
features ``conftest.py`` files are only *active* for tests at or below it.


.. _config.warn and node.warn deprecated:

``Config.warn`` and ``Node.warn``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

Those methods were part of the internal testrunner warnings system, but since ``3.8`` testrunner is using the builtin warning
system for its own warnings, so those two functions are now deprecated.

``Config.warn`` should be replaced by calls to the standard ``warnings.warn``, example:

.. code-block:: python

    config.warn("C1", "some warning")

Becomes:

.. code-block:: python

    warnings.warn(testrunner.TestrunnerWarning("some warning"))

``Node.warn`` now supports two signatures:

* ``node.warn(TestrunnerWarning("some message"))``: is now the **recommended** way to call this function.
  The warning instance must be a TestrunnerWarning or subclass.

* ``node.warn("CI", "some message")``: this code/message form has been **removed** and should be converted to the warning instance form above.

.. _record_xml_property deprecated:

record_xml_property
~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

The ``record_xml_property`` fixture is now deprecated in favor of the more generic ``record_property``, which
can be used by other consumers (for example ``testrunner-html``) to obtain custom information about the test run.

This is just a matter of renaming the fixture as the API is the same:

.. code-block:: python

    def test_foo(record_xml_property): ...

Change to:

.. code-block:: python

    def test_foo(record_property): ...


.. _passing command-line string to testrunner.main deprecated:

Passing command-line string to ``testrunner.main()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

Passing a command-line string to ``testrunner.main()`` is deprecated:

.. code-block:: python

    testrunner.main("-v -s")

Pass a list instead:

.. code-block:: python

    testrunner.main(["-v", "-s"])


By passing a string, users expect that testrunner will interpret that command-line using the shell rules they are working
on (for example ``bash`` or ``Powershell``), but this is very hard/impossible to do in a portable way.


.. _calling fixtures directly deprecated:

Calling fixtures directly
~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

Calling a fixture function directly, as opposed to request them in a test function, is deprecated.

For example:

.. code-block:: python

    @testrunner.fixture
    def cell():
        return ...


    @testrunner.fixture
    def full_cell():
        cell = cell()
        cell.make_full()
        return cell

This is a great source of confusion to new users, which will often call the fixture functions and request them from test functions interchangeably, which breaks the fixture resolution model.

In those cases just request the function directly in the dependent fixture:

.. code-block:: python

    @testrunner.fixture
    def cell():
        return ...


    @testrunner.fixture
    def full_cell(cell):
        cell.make_full()
        return cell

Alternatively if the fixture function is called multiple times inside a test (making it hard to apply the above pattern) or
if you would like to make minimal changes to the code, you can create a fixture which calls the original function together
with the ``name`` parameter:

.. code-block:: python

    def cell():
        return ...


    @testrunner.fixture(name="cell")
    def cell_fixture():
        return cell()


.. _internal classes accessed through node deprecated:

Internal classes accessed through ``Node``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

Access of ``Module``, ``Function``, ``Class``, ``Instance``, ``File`` and ``Item`` through ``Node`` instances now issue
this warning:

.. code-block:: text

    usage of Function.Module is deprecated, please use testrunner.Module instead

Users should just ``import testrunner`` and access those objects using the ``testrunner`` module.

This has been documented as deprecated for years, but only now we are actually emitting deprecation warnings.

``Node.get_marker``
~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

As part of a large :ref:`marker-revamp`, ``_testrunner.nodes.Node.get_marker`` is removed. See
:ref:`the documentation <update marker code>` on tips on how to update your code.


``somefunction.markname``
~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

As part of a large :ref:`marker-revamp` we already deprecated using ``MarkInfo``
the only correct way to get markers of an element is via ``node.iter_markers(name)``.


.. _testrunner.namespace deprecated:

``testrunner_namespace``
~~~~~~~~~~~~~~~~~~~~

.. versionremoved:: 4.0

This hook is deprecated because it greatly complicates the testrunner internals regarding configuration and initialization, making some
bug fixes and refactorings impossible.

Example of usage:

.. code-block:: python

    class MySymbol: ...


    def testrunner_namespace():
        return {"my_symbol": MySymbol()}


Plugin authors relying on this hook should instead require that users now import the plugin modules directly (with an appropriate public API).

As a stopgap measure, plugin authors may still inject their names into testrunner's namespace, usually during ``testrunner_configure``:

.. code-block:: python

    import testrunner


    def testrunner_configure():
        testrunner.my_symbol = MySymbol()
