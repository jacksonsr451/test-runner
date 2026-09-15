.. _plugins:
.. _`writing-plugins`:

Writing plugins
===============

It is easy to implement `local conftest plugins`_ for your own project
or `pip-installable plugins`_ that can be used throughout many projects,
including third party projects.  Please refer to :ref:`using plugins` if you
only want to use but not write plugins.

A plugin contains one or multiple hook functions. :ref:`Writing hooks <writinghooks>`
explains the basics and details of how you can write a hook function yourself.
``testrunner`` implements all aspects of configuration, collection, running and
reporting by calling :ref:`well specified hooks <hook-reference>` of the following plugins:

* builtin plugins: loaded from testrunner's internal ``_testrunner`` directory.

* :ref:`external plugins <extplugins>`: installed third-party modules discovered
  through :ref:`entry points <pip-installable plugins>` in their packaging metadata

* `conftest.py plugins`_: modules auto-discovered in test directories

In principle, each hook call is a ``1:N`` Python function call where ``N`` is the
number of registered implementation functions for a given specification.
All specifications and implementations follow the ``testrunner_`` prefix
naming convention, making them easy to distinguish and find.

.. _`pluginorder`:

Plugin discovery order at tool startup
--------------------------------------

``testrunner`` loads plugin modules at tool startup in the following way:

1. by scanning the command line for the ``-p no:name`` option
   and *blocking* that plugin from being loaded (even builtin plugins can
   be blocked this way). This happens before normal command-line parsing.

2. by loading all builtin plugins.

3. by scanning the command line for the ``-p name`` option
   and loading the specified plugin. This happens before normal command-line parsing.

4. by loading all plugins registered through installed third-party package
   :ref:`entry points <pip-installable plugins>`, unless the
   :envvar:`TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD` environment variable is set.

5. by loading all plugins specified through the :envvar:`TESTRUNNER_PLUGINS` environment variable.

6. by loading all "initial" :file:`conftest.py` files:

   - determine the test paths: specified on the command line, otherwise in
     :confval:`testpaths` if defined and running from the rootdir, otherwise the
     current dir
   - for each test path, load ``conftest.py`` and ``test*/conftest.py`` relative
     to the directory part of the test path, if they exist. Before a ``conftest.py``
     file is loaded, load ``conftest.py`` files in its parent directories up to
     the :option:`--confcutdir` limit. When ``--confcutdir`` is not provided,
     the cutoff defaults to the directory containing the config file, or to the
     :ref:`rootdir <rootdir>` if no config file is found.
     After a ``conftest.py`` file is loaded, recursively load all plugins specified
     in its :globalvar:`testrunner_plugins` variable if present.


.. _`conftest.py plugins`:
.. _`localplugin`:
.. _`local conftest plugins`:

conftest.py: local per-directory plugins
----------------------------------------

Local ``conftest.py`` plugins contain directory-specific hook
implementations.  Hook Session and test running activities will
invoke all hooks defined in ``conftest.py`` files closer to the
root of the filesystem.  Example of implementing the
``testrunner_runtest_setup`` hook so that is called for tests in the ``a``
sub directory but not for other directories::

    a/conftest.py:
        def testrunner_runtest_setup(item):
            # called for running each test in 'a' directory
            print("setting up", item)

    a/test_sub.py:
        def test_sub():
            pass

    test_flat.py:
        def test_flat():
            pass

Here is how you might run it::

     testrunner test_flat.py --capture=no  # will not show "setting up"
     testrunner a/test_sub.py --capture=no  # will show "setting up"

.. note::
    If you have ``conftest.py`` files which do not reside in a
    python package directory (i.e. one containing an ``__init__.py``) then
    "import conftest" can be ambiguous because there might be other
    ``conftest.py`` files as well on your ``PYTHONPATH`` or ``sys.path``.
    It is thus good practice for projects to either put ``conftest.py``
    under a package scope or to never import anything from a
    ``conftest.py`` file.

    See also: :ref:`pythonpath`.

.. note::
    Some hooks cannot be implemented in conftest.py files which are not
    :ref:`initial <pluginorder>` due to how testrunner discovers plugins during
    startup. See the documentation of each hook for details.

Writing your own plugin
-----------------------

If you want to write a plugin, there are many real-life examples
you can copy from:

* a custom collection example plugin: :ref:`yaml plugin`
* builtin plugins which provide testrunner's own functionality
* many :ref:`external plugins <plugin-list>` providing additional features

All of these plugins implement :ref:`hooks <hook-reference>` and/or :ref:`fixtures <fixture>`
to extend and add functionality.

.. note::
    Make sure to check out the excellent
    `cookiecutter-testrunner-plugin <https://github.com/testrunner-dev/cookiecutter-testrunner-plugin>`_
    project, which is a `cookiecutter template <https://github.com/audreyr/cookiecutter>`_
    for authoring plugins.

    The template provides an excellent starting point with a working plugin,
    tests running with tox, a comprehensive README file as well as a
    pre-configured entry-point.

Also consider :ref:`contributing your plugin to testrunner-dev<submitplugin>`
once it has some happy users other than yourself.


.. _`setuptools entry points`:
.. _`pip-installable plugins`:

Making your plugin installable by others
----------------------------------------

If you want to make your plugin externally available, you
may define a so-called entry point for your distribution so
that ``testrunner`` finds your plugin module. Entry points are
a feature that is provided by :std:doc:`packaging tools
<packaging:specifications/entry-points>`.

testrunner looks up the ``testrunner11`` entrypoint to discover its
plugins, thus you can make your plugin available by defining
it in your ``pyproject.toml`` file.

.. sourcecode:: toml

    # sample ./pyproject.toml file
    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"

    [project]
    name = "myproject"
    classifiers = [
        "Framework :: Testrunner",
    ]

    [project.entry-points.testrunner11]
    myproject = "myproject.pluginmodule"

If a package is installed this way, ``testrunner`` will load
``myproject.pluginmodule`` as a plugin which can define
:ref:`hooks <hook-reference>`. Confirm registration with ``testrunner --trace-config``

.. note::

    Make sure to include ``Framework :: Testrunner`` in your list of
    `PyPI classifiers <https://pypi.org/classifiers/>`_
    to make it easy for users to find your plugin.


.. _assertion-rewriting:

Assertion Rewriting
-------------------

One of the main features of ``testrunner`` is the use of plain assert
statements and the detailed introspection of expressions upon
assertion failures.  This is provided by "assertion rewriting" which
modifies the parsed AST before it gets compiled to bytecode.  This is
done via a :pep:`302` import hook which gets installed early on when
``testrunner`` starts up and will perform this rewriting when modules get
imported.  However, since we do not want to test different bytecode
from what you will run in production, this hook only rewrites test modules
themselves (as defined by the :confval:`python_files` configuration option),
and any modules which are part of plugins.
Any other imported module will not be rewritten and normal assertion behaviour
will happen.

If you have assertion helpers in other modules where you would need
assertion rewriting to be enabled you need to ask ``testrunner``
explicitly to rewrite this module before it gets imported.

.. autofunction:: testrunner.register_assert_rewrite
    :noindex:

This is especially important when you write a testrunner plugin which is
created using a package.  The import hook only treats ``conftest.py``
files and any modules which are listed in the ``testrunner11`` entrypoint
as plugins.  As an example consider the following package::

   testrunner_foo/__init__.py
   testrunner_foo/plugin.py
   testrunner_foo/helper.py

With the following typical ``pyproject.toml`` extract:

.. code-block:: toml

   [project.entry-points.testrunner11]
   foo = "testrunner_foo.plugin"

In this case only ``testrunner_foo/plugin.py`` will be rewritten.  If the
helper module also contains assert statements which need to be
rewritten it needs to be marked as such, before it gets imported.
This is easiest by marking it for rewriting inside the
``__init__.py`` module, which will always be imported first when a
module inside a package is imported.  This way ``plugin.py`` can still
import ``helper.py`` normally.  The contents of
``testrunner_foo/__init__.py`` will then need to look like this:

.. code-block:: python

   import testrunner

   testrunner.register_assert_rewrite("testrunner_foo.helper")


Requiring/Loading plugins in a test module or conftest file
-----------------------------------------------------------

You can require plugins in a test module or a ``conftest.py`` file using :globalvar:`testrunner_plugins`:

.. code-block:: python

    testrunner_plugins = ["name1", "name2"]

When the test module or conftest plugin is loaded the specified plugins
will be loaded as well. Any module can be blessed as a plugin, including internal
application modules:

.. code-block:: python

    testrunner_plugins = "myapp.testsupport.myplugin"

The entry point name of an installed plugin can also be used, just like with
the :option:`-p` command-line option:

.. code-block:: python

    testrunner_plugins = ("xdist",)

:globalvar:`testrunner_plugins` are processed recursively, so note that in the example above
if ``myapp.testsupport.myplugin`` also declares :globalvar:`testrunner_plugins`, the contents
of the variable will also be loaded as plugins, and so on.

.. _`requiring plugins in non-root conftests`:

.. note::
    Requiring plugins using :globalvar:`testrunner_plugins` variable in non-root
    ``conftest.py`` files is deprecated.

    This is important because ``conftest.py`` files implement per-directory
    hook implementations, but once a plugin is imported, it will affect the
    entire directory tree. In order to avoid confusion, defining
    :globalvar:`testrunner_plugins` in any ``conftest.py`` file which is not located in the
    tests root directory is deprecated, and will raise a warning.

This mechanism makes it easy to share fixtures within applications or even
external applications without the need to create external plugins using the
:std:doc:`entry point packaging metadata
<packaging:guides/creating-and-discovering-plugins>` technique.

Plugins imported by :globalvar:`testrunner_plugins` will also automatically be marked
for assertion rewriting (see :func:`testrunner.register_assert_rewrite`).
However for this to have any effect the module must not be
imported already; if it was already imported at the time the
:globalvar:`testrunner_plugins` statement is processed, a warning will result and
assertions inside the plugin will not be rewritten.  To fix this you
can either call :func:`testrunner.register_assert_rewrite` yourself before
the module is imported, or you can arrange the code to delay the
importing until after the plugin is registered.


Accessing another plugin by name
--------------------------------

If a plugin wants to collaborate with code from
another plugin it can obtain a reference through
the plugin manager like this:

.. sourcecode:: python

    plugin = config.pluginmanager.get_plugin("name_of_plugin")

If you want to look at the names of existing plugins, use
the :option:`--trace-config` option.


.. _registering-markers:

Registering custom markers
--------------------------

If your plugin uses any markers, you should register them so that they appear in
testrunner's help text and do not :ref:`cause spurious warnings <unknown-marks>`.
For example, the following plugin would register ``cool_marker`` and
``mark_with`` for all users:

.. code-block:: python

    def testrunner_configure(config):
        config.addinivalue_line("markers", "cool_marker: this one is for cool tests.")
        config.addinivalue_line(
            "markers", "mark_with(arg, arg2): this marker takes arguments."
        )


Testing plugins
---------------

testrunner comes with a plugin named ``testrunnerer`` that helps you write tests for
your plugin code. The plugin is disabled by default, so you will have to enable
it before you can use it.

You can do so by adding the following line to a ``conftest.py`` file in your
testing directory:

.. code-block:: python

    # content of conftest.py

    testrunner_plugins = ["testrunnerer"]

Alternatively you can invoke testrunner with the ``-p testrunnerer`` command line
option.

This will allow you to use the :py:class:`testrunnerer <testrunner.Testrunnerer>`
fixture for testing your plugin code.

Let's demonstrate what you can do with the plugin with an example. Imagine we
developed a plugin that provides a fixture ``hello`` which yields a function
and we can invoke this function with one optional parameter. It will return a
string value of ``Hello World!`` if we do not supply a value or ``Hello
{value}!`` if we do supply a string value.

.. code-block:: python

    import testrunner


    def testrunner_addoption(parser):
        group = parser.getgroup("helloworld")
        group.addoption(
            "--name",
            action="store",
            dest="name",
            default="World",
            help='Default "name" for hello().',
        )


    @testrunner.fixture
    def hello(request):
        name = request.config.getoption("name")

        def _hello(name=None):
            if not name:
                name = request.config.getoption("name")
            return f"Hello {name}!"

        return _hello


Now the ``testrunnerer`` fixture provides a convenient API for creating temporary
``conftest.py`` files and test files. It also allows us to run the tests and
return a result object, with which we can assert the tests' outcomes.

.. code-block:: python

    def test_hello(testrunnerer):
        """Make sure that our plugin works."""

        # create a temporary conftest.py file
        testrunnerer.makeconftest(
            """
            import testrunner

            @testrunner.fixture(params=[
                "Brianna",
                "Andreas",
                "Floris",
            ])
            def name(request):
                return request.param
        """
        )

        # create a temporary testrunner test file
        testrunnerer.makepyfile(
            """
            def test_hello_default(hello):
                assert hello() == "Hello World!"

            def test_hello_name(hello, name):
                assert hello(name) == "Hello {0}!".format(name)
        """
        )

        # run all tests with testrunner
        result = testrunnerer.runtestrunner()

        # check that all 4 tests passed
        result.assert_outcomes(passed=4)

.. note::

    :meth:`testrunner.RunResult.assert_outcomes` parses testrunner's standard terminal
    summary. A plugin that changes or removes that summary can make outcome
    parsing fail. Disable the output-changing plugin for the nested run with
    ``-p no:<plugin>``, or set ``TESTRUNNER_DISABLE_PLUGIN_AUTOLOAD=1`` when the
    nested run should not discover third-party plugins.


Additionally it is possible to copy examples to the ``testrunnerer``'s isolated environment
before running testrunner on it. This way we can abstract the tested logic to separate files,
which is especially useful for longer tests and/or longer ``conftest.py`` files.

Note that for ``testrunnerer.copy_example`` to work we need to set `testrunnerer_example_dir`
in our configuration file to tell testrunner where to look for example files.

.. code-block:: toml

    # content of testrunner.toml
    [testrunner]
    testrunnerer_example_dir = "."


.. code-block:: python

    # content of test_example.py


    def test_plugin(testrunnerer):
        testrunnerer.copy_example("test_example.py")
        testrunnerer.runtestrunner("-k", "test_example")


    def test_example():
        pass

.. code-block:: testrunner

    $ testrunner
    =========================== test session starts ============================
    platform linux -- Python 3.x.y, testrunner-9.x.y, pluggy-1.x.y
    rootdir: /home/sweet/project
    configfile: testrunner.toml
    collected 2 items

    test_example.py ..                                                   [100%]

    ============================ 2 passed in 0.12s =============================

For more information about the result object that ``runtestrunner()`` returns, and
the methods that it provides please check out the :py:class:`RunResult
<_testrunner.testrunnerer.RunResult>` documentation.
