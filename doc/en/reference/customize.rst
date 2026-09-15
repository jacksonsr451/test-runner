Configuration
=============

Command line options and configuration file settings
-----------------------------------------------------------------

You can get help on command line and configuration options by using the general help option:

.. code-block:: bash

    testrunner -h   # prints options _and_ config file settings

This will display command line and configuration file settings
which were registered by installed plugins.

.. _`config file formats`:

Configuration file formats
--------------------------

Many :ref:`testrunner settings <ini options ref>` can be set in a *configuration file*, which
by convention resides in the root directory of your repository.

A quick example of the configuration files supported by testrunner:

testrunner.toml
~~~~~~~~~~~

.. versionadded:: 9.0

``testrunner.toml`` files take precedence over other files, even when empty.

Alternatively, the hidden version ``.testrunner.toml`` can be used.

.. tab:: toml

    .. code-block:: toml

        # testrunner.toml or .testrunner.toml
        [testrunner]
        minversion = "9.0"
        addopts = ["-ra", "-q"]
        testpaths = [
            "tests",
            "integration",
        ]

testrunner.ini
~~~~~~~~~~

``testrunner.ini`` files take precedence over other files (except ``testrunner.toml`` and ``.testrunner.toml``), even when empty.

Alternatively, the hidden version ``.testrunner.ini`` can be used.

.. tab:: ini

    .. code-block:: ini

        # testrunner.ini or .testrunner.ini
        [testrunner]
        minversion = 6.0
        addopts = -ra -q
        testpaths =
            tests
            integration


pyproject.toml
~~~~~~~~~~~~~~

.. versionadded:: 6.0
.. versionchanged:: 9.0

``pyproject.toml`` files are supported for configuration.

.. tab:: toml

    Use ``[tool.testrunner]`` to leverage native TOML types (supported since testrunner 9.0):

    .. code-block:: toml

        # pyproject.toml
        [tool.testrunner]
        minversion = "9.0"
        addopts = ["-ra", "-q"]
        testpaths = [
            "tests",
            "integration",
        ]

.. tab:: ini

    Use ``[tool.testrunner.ini_options]`` for INI-style configuration (supported since testrunner 6.0):

    .. code-block:: toml

        # pyproject.toml
        [tool.testrunner.ini_options]
        minversion = "6.0"
        addopts = "-ra -q"
        testpaths = [
            "tests",
            "integration",
        ]

    For projects that still run testrunner versions older than 6.0, keep
    ``minversion`` in ``testrunner.ini`` or ``tox.ini`` too. Those versions
    do not read ``pyproject.toml``.

tox.ini
~~~~~~~

``tox.ini`` files are the configuration files of the `tox <https://tox.readthedocs.io>`__ project,
and can also be used to hold testrunner configuration if they have a ``[testrunner]`` section.

.. tab:: ini

    .. code-block:: ini

        # tox.ini
        [testrunner]
        minversion = 6.0
        addopts = -ra -q
        testpaths =
            tests
            integration


setup.cfg
~~~~~~~~~

``setup.cfg`` files are general purpose configuration files, used originally by ``distutils`` (now deprecated) and :std:doc:`setuptools <setuptools:userguide/declarative_config>`, and can also be used to hold testrunner configuration
if they have a ``[tool:testrunner]`` section.

.. tab:: ini

    .. code-block:: ini

        # setup.cfg
        [tool:testrunner]
        minversion = 6.0
        addopts = -ra -q
        testpaths =
            tests
            integration

.. warning::

    Usage of ``setup.cfg`` is not recommended unless for very simple use cases. ``.cfg``
    files use a different parser than ``testrunner.ini`` and ``tox.ini`` which might cause hard to track
    down problems.
    When possible, it is recommended to use the latter files, or ``pyproject.toml``, to hold your
    testrunner configuration.


.. _rootdir:
.. _configfiles:

Initialization: determining rootdir and configfile
--------------------------------------------------

testrunner determines a ``rootdir`` for each test run which depends on
the command line arguments (specified test files, paths) and on
the existence of configuration files.  The determined ``rootdir`` and ``configfile`` are
printed as part of the testrunner header during startup.

Here's a summary of what ``testrunner`` uses ``rootdir`` for:

* Construct *nodeids* during collection; each test is assigned
  a unique *nodeid* which is rooted at the ``rootdir`` and takes into account
  the full path, class name, function name and parametrization (if any).

* Is used by plugins as a stable location to store project/test run specific information;
  for example, the internal :ref:`cache <cache>` plugin creates a ``.testrunner_cache`` subdirectory
  in ``rootdir`` to store its cross-test run state.

``rootdir`` is **NOT** used to modify ``sys.path``/``PYTHONPATH`` or
influence how modules are imported. See :ref:`pythonpath` for more details.

The :option:`--rootdir=path` command-line option can be used to force a specific directory.
Note that contrary to other command-line options, ``--rootdir`` cannot be used with
:confval:`addopts` inside a configuration file because the ``rootdir`` is used to *find* the configuration file
already.

Finding the ``rootdir``
~~~~~~~~~~~~~~~~~~~~~~~

Here is the algorithm which finds the rootdir from ``args``:

- If :option:`-c` is passed in the command-line, use that as configuration file, and its directory as ``rootdir``.

- Determine the common ancestor directory for the specified ``args`` that are
  recognised as paths that exist in the file system. If no such paths are
  found, the common ancestor directory is set to the current working directory.

- Look for ``testrunner.toml``, ``.testrunner.toml``, ``testrunner.ini``, ``.testrunner.ini``, ``pyproject.toml``, ``tox.ini``, and ``setup.cfg`` files in the ancestor
  directory and upwards.  If one is matched, it becomes the ``configfile`` and its
  directory becomes the ``rootdir``.

- If no configuration file was found, look for ``setup.py`` upwards from the common
  ancestor directory to determine the ``rootdir``.

- If no ``setup.py`` was found, look for ``testrunner.toml``, ``.testrunner.toml``, ``testrunner.ini``, ``.testrunner.ini``, ``pyproject.toml``, ``tox.ini``, and
  ``setup.cfg`` in each of the specified ``args`` and upwards. If one is
  matched, it becomes the ``configfile`` and its directory becomes the ``rootdir``.

- If no ``configfile`` was found and no configuration argument is passed, use the already determined common ancestor as root
  directory. This allows the use of testrunner in structures that are not part of
  a package and don't have any particular configuration file.

If no ``args`` are given, testrunner collects tests below the current working
directory and also starts determining the ``rootdir`` from there.

Files will only be matched for configuration if:

* ``testrunner.toml``: will always match and take highest precedence, even if empty.
* ``testrunner.ini``: will always match and take precedence (after ``testrunner.toml`` and ``.testrunner.toml``), even if empty.
* ``pyproject.toml``: contains a ``[tool.testrunner]`` or ``[tool.testrunner.ini_options]`` table.
* ``tox.ini``: contains a ``[testrunner]`` section.
* ``setup.cfg``: contains a ``[tool:testrunner]`` section.

Finally, a ``pyproject.toml`` file will be considered the ``configfile`` if no other match was found, in this case
even if it does not contain a ``[tool.testrunner]`` table (since version ``9.0``) or a ``[tool.testrunner.ini_options]``
table (since version ``8.1``).

The files are considered in the order above. Options from multiple ``configfiles`` candidates
are never merged - the first match wins.

The configuration file also determines the value of the ``rootpath``.

The :class:`Config <testrunner.Config>` object (accessible via hooks or through the :fixture:`testrunnerconfig` fixture)
will subsequently carry these attributes:

- :attr:`config.rootpath <testrunner.Config.rootpath>`: the determined root directory, guaranteed to exist. It is used as
  a reference directory for constructing test addresses ("nodeids") and can be used also by plugins for storing
  per-testrun information.

- :attr:`config.inipath <testrunner.Config.inipath>`: the determined ``configfile``, may be ``None``
  (it is named ``inipath`` for historical reasons).

.. versionadded:: 6.1
    The ``config.rootpath`` and ``config.inipath`` properties. They are :class:`pathlib.Path`
    versions of the older ``config.rootdir`` and ``config.inifile``, which have type
    ``py.path.local``, and still exist for backward compatibility.



Example:

.. code-block:: bash

    testrunner path/to/testdir path/other/

will determine the common ancestor as ``path`` and then
check for configuration files as follows:

.. code-block:: text

    # first look for path/testrunner.toml
    path/testrunner.toml
    path/testrunner.ini
    path/pyproject.toml  # must contain a [tool.testrunner] table to match
    path/tox.ini         # must contain [testrunner] section to match
    path/setup.cfg       # must contain [tool:testrunner] section to match
    testrunner.toml
    testrunner.ini
    ... # all the way up to the root

    # now look for setup.py
    path/setup.py
    setup.py
    ... # all the way up to the root


.. warning::

    Custom testrunner plugin commandline arguments may include a path, as in
    ``testrunner --log-output ../../test.log args``. Then ``args`` is mandatory,
    otherwise testrunner uses the directory of test.log for rootdir determination
    (see also :issue:`1435`).
    A dot ``.`` for referencing the current working directory is also
    possible.


.. _`how to change command line options defaults`:
.. _`adding default options`:


Builtin configuration file options
----------------------------------------------

For the full list of options consult the :ref:`reference documentation <ini options ref>`.

Syntax highlighting theme customization
---------------------------------------

The syntax highlighting themes used by testrunner can be customized using two environment variables:

- :envvar:`TESTRUNNER_THEME` sets a `pygment style <https://pygments.org/docs/styles/>`_ to use.
- :envvar:`TESTRUNNER_THEME_MODE` sets this style to *light* or *dark*.
