
.. _usage:

How to invoke testrunner
==========================================

..  seealso:: :ref:`Complete testrunner command-line flags reference <command-line-flags>`

In general, testrunner is invoked with the command ``testrunner`` (see below for :ref:`other ways to invoke testrunner
<invoke-other>`). This will execute all tests in all files whose names follow the form ``test_*.py`` or ``*_test.py``
in the current directory and its subdirectories. More generally, testrunner follows :ref:`standard test discovery rules
<test discovery>`.


.. _select-tests:

Specifying which tests to run
------------------------------

Testrunner supports several ways to run and select tests from the command-line or from a file
(see below for :ref:`reading arguments from file <args-from-file>`).

**Run tests in a module**

.. code-block:: bash

    testrunner test_mod.py

**Run tests in a directory**

.. code-block:: bash

    testrunner testing/

**Run tests by keyword expressions**

.. code-block:: bash

    testrunner -k 'MyClass and not method'

This will run tests which contain names that match the given *string expression* (case-insensitive),
which can include Python operators that use filenames, class names and function names as variables.
The example above will run ``TestMyClass.test_something``  but not ``TestMyClass.test_method_simple``.
Use ``""`` instead of ``''`` in expression when running this on Windows

.. _nodeids:

**Run tests by collection arguments**

Pass the module filename relative to the working directory, followed by specifiers like the class name and function name
separated by ``::`` characters, and parameters from parameterization enclosed in ``[]``.

To run a specific test within a module:

.. code-block:: bash

    testrunner tests/test_mod.py::test_func

To run all tests in a class:

.. code-block:: bash

    testrunner tests/test_mod.py::TestClass

Specifying a specific test method:

.. code-block:: bash

    testrunner tests/test_mod.py::TestClass::test_method

Specifying a specific parametrization of a test:

.. code-block:: bash

    testrunner tests/test_mod.py::test_func[x1,y2]

**Run tests by marker expressions**

To run all tests which are decorated with the ``@testrunner.mark.slow`` decorator:

.. code-block:: bash

    testrunner -m slow


To run all tests which are decorated with the annotated ``@testrunner.mark.slow(phase=1)`` decorator,
with the ``phase`` keyword argument set to ``1``:

.. code-block:: bash

    testrunner -m "slow(phase=1)"

For more information see :ref:`marks <mark>`.

**Run tests from packages**

.. code-block:: bash

    testrunner --pyargs pkg.testing

This will import ``pkg.testing`` and use its filesystem location to find and run tests from.

.. _args-from-file:

**Read arguments from file**

.. versionadded:: 8.2

All of the above can be read from a file using the ``@`` prefix:

.. code-block:: bash

    testrunner @tests_to_run.txt

where ``tests_to_run.txt`` contains an entry per line, e.g.:

.. code-block:: text

    tests/test_file.py
    tests/test_mod.py::test_func[x1,y2]
    tests/test_mod.py::TestClass
    -m slow

This file can also be generated using ``testrunner --collect-only -q`` and modified as needed.

Getting help on version, option names, environment variables
--------------------------------------------------------------

.. code-block:: bash

    testrunner --version   # shows where testrunner was imported from
    testrunner --fixtures  # show available builtin function arguments
    testrunner -h | --help # show help on command line and config file options


.. _durations:

Profiling test execution duration
-------------------------------------

.. versionchanged:: 6.0

To get a list of the slowest 10 test durations over 1.0s long:

.. code-block:: bash

    testrunner --durations=10 --durations-min=1.0

By default, testrunner will not show test durations that are too small (<0.005s) unless ``-vv`` is passed on the command-line.


Managing loading of plugins
-------------------------------

Early loading plugins
~~~~~~~~~~~~~~~~~~~~~~~

You can early-load plugins (internal and external) explicitly in the command-line with the :option:`-p` option::

    testrunner -p mypluginmodule

The option receives a ``name`` parameter, which can be:

* A full module dotted name, for example ``myproject.plugins``. This dotted name must be importable.
* The entry-point name of a plugin. This is the name passed to ``importlib`` when the plugin is
  registered. For example to early-load the :pypi:`testrunner-cov` plugin you can use::

    testrunner -p testrunner_cov


Disabling plugins
~~~~~~~~~~~~~~~~~~

To disable loading specific plugins at invocation time, use the :option:`-p` option
together with the prefix ``no:``.

Example: to disable loading the plugin ``doctest``, which is responsible for
executing doctest tests from text files, invoke testrunner like this:

.. code-block:: bash

    testrunner -p no:doctest


.. _invoke-other:

Other ways of calling testrunner
-----------------------------------------------------

.. _invoke-python:

Calling testrunner through ``python -m testrunner``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can invoke testing through the Python interpreter from the command line:

.. code-block:: text

    python -m testrunner [...]

This is almost equivalent to invoking the command line script ``testrunner [...]``
directly, except that calling via ``python`` will also add the current directory to ``sys.path``.


.. _`testrunner.main-usage`:

Calling testrunner from Python code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can invoke ``testrunner`` from Python code directly:

.. code-block:: python

    retcode = testrunner.main()

this acts as if you would call "testrunner" from the command line.
It will not raise :class:`SystemExit` but return the :ref:`exit code <exit-codes>` instead.
If you don't pass it any arguments, ``main`` reads the arguments from the command line arguments of the process (:data:`sys.argv`), which may be undesirable.
You can pass in options and arguments explicitly:

.. code-block:: python

    retcode = testrunner.main(["-x", "mytestdir"])

You can specify additional plugins to ``testrunner.main``:

.. code-block:: python

    # content of myinvoke.py
    import sys

    import testrunner


    class MyPlugin:
        def testrunner_sessionfinish(self):
            print("*** test run reporting finishing")


    if __name__ == "__main__":
        sys.exit(testrunner.main(["-qq"], plugins=[MyPlugin()]))

Running it will show that ``MyPlugin`` was added and its
hook was invoked:

.. code-block:: testrunner

    $ python myinvoke.py
    *** test run reporting finishing


.. note::

    Calling ``testrunner.main()`` will result in importing your tests and any modules
    that they import. Due to the caching mechanism of python's import system,
    making subsequent calls to ``testrunner.main()`` from the same process will not
    reflect changes to those files between the calls. For this reason, making
    multiple calls to ``testrunner.main()`` from the same process (in order to re-run
    tests, for example) is not recommended.
