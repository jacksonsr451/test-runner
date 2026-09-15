.. _exit-codes:

Exit codes
========================================================

Running ``testrunner`` can result in seven different exit codes:

:Exit code 0: All tests were collected and passed successfully
:Exit code 1: Tests were collected and run but some of the tests failed
:Exit code 2: Test execution was interrupted by the user
:Exit code 3: Internal error happened while executing tests, or a plugin raised while importing
:Exit code 4: testrunner command line usage error, including a plugin that cannot be found or a ``conftest.py`` that fails to import
:Exit code 5: No tests were collected
:Exit code 6: Maximum number of warnings exceeded (see :option:`--max-warnings`)

They are represented by the :class:`testrunner.ExitCode` enum. The exit codes being a part of the public API can be imported and accessed directly using:

.. code-block:: python

    from testrunner import ExitCode

.. note::

    If you would like to customize the exit code in some scenarios, specifically when
    no tests are collected, consider using the
    `testrunner-custom_exit_code <https://github.com/yashtodi94/testrunner-custom_exit_code>`__
    plugin.
