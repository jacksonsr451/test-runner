.. image:: https://github.com/jacksonsr451/test-runner/raw/main/doc/en/img/testrunner_logo_curves.svg
   :target: https://github.com/jacksonsr451/test-runner/tree/main/doc/en/
   :align: center
   :height: 200
   :alt: testrunner


------

.. image:: https://img.shields.io/pypi/v/testrunner.svg
    :target: https://pypi.org/project/testrunner/

.. image:: https://img.shields.io/conda/vn/conda-forge/testrunner.svg
    :target: https://anaconda.org/conda-forge/testrunner

.. image:: https://img.shields.io/pypi/pyversions/testrunner.svg
    :target: https://pypi.org/project/testrunner/

.. image:: https://codecov.io/gh/jacksonsr451/test-runner/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/jacksonsr451/test-runner
    :alt: Code coverage Status

.. image:: https://github.com/jacksonsr451/test-runner/actions/workflows/test.yml/badge.svg
    :target: https://github.com/jacksonsr451/test-runner/actions?query=workflow%3Atest

.. image:: https://results.pre-commit.ci/badge/github/jacksonsr451/test-runner/main.svg
   :target: https://results.pre-commit.ci/latest/github/jacksonsr451/test-runner/main
   :alt: pre-commit.ci status

.. image:: https://www.codetriage.com/jacksonsr451/test-runner/badges/users.svg
    :target: https://www.codetriage.com/jacksonsr451/test-runner

.. image:: https://readthedocs.org/projects/testrunner/badge/?version=latest
    :target: https://testrunner.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/badge/Discord-testrunner--dev-blue
    :target: https://discord.com/invite/testrunner-dev
    :alt: Discord

.. image:: https://img.shields.io/badge/Libera%20chat-%23testrunner-orange
    :target: https://web.libera.chat/#testrunner
    :alt: Libera chat


The ``testrunner`` framework makes it easy to write small tests, yet
scales to support complex functional testing for applications and libraries.

An example of a simple test:

.. code-block:: python

    # content of test_sample.py
    def inc(x):
        return x + 1


    def test_answer():
        assert inc(3) == 5


To execute it::

    $ testrunner
    ============================= test session starts =============================
    collected 1 items

    test_sample.py F

    ================================== FAILURES ===================================
    _________________________________ test_answer _________________________________

        def test_answer():
    >       assert inc(3) == 5
    E       assert 4 == 5
    E        +  where 4 = inc(3)

    test_sample.py:5: AssertionError
    ========================== 1 failed in 0.04 seconds ===========================


Thanks to ``testrunner``'s detailed assertion introspection, you can simply use plain ``assert`` statements. See `getting-started <https://github.com/jacksonsr451/test-runner/tree/main/doc/en/getting-started.html#our-first-test-run>`_ for more examples.


Features
--------

- Detailed info on failing `assert statements <https://github.com/jacksonsr451/test-runner/tree/main/doc/en/how-to/assert.html>`_ (no need to remember ``self.assert*`` names)

- `Auto-discovery
  <https://github.com/jacksonsr451/test-runner/tree/main/doc/en/explanation/goodpractices.html#python-test-discovery>`_
  of test modules and functions

- `Modular fixtures <https://github.com/jacksonsr451/test-runner/tree/main/doc/en/explanation/fixtures.html>`_ for
  managing small or parametrized long-lived test resources

- Can run `unittest <https://github.com/jacksonsr451/test-runner/tree/main/doc/en/how-to/unittest.html>`_ (or trial)
  test suites out of the box

- Python 3.10+ or PyPy3

- Rich plugin architecture, with over 1300+ `external plugins <https://github.com/jacksonsr451/test-runner/tree/main/doc/en/reference/plugin_list.html>`_ and thriving community


Documentation
-------------

For full documentation, including installation, tutorials and PDF documents, please see https://github.com/jacksonsr451/test-runner/tree/main/doc/en/.


Bugs/Requests
-------------

Please use the `GitHub issue tracker <https://github.com/jacksonsr451/test-runner/issues>`_ to submit bugs or request features.


Changelog
---------

Consult the `Changelog <https://github.com/jacksonsr451/test-runner/tree/main/doc/en/changelog.html>`__ page for fixes and enhancements of each version.


Support testrunner
------------------

`Open Collective`_ is an online funding platform for open and transparent communities.
It provides tools to raise money and share your finances in full transparency.

It is the platform of choice for individuals and companies that want to make one-time or
monthly donations directly to the project.

See more details in the `testrunner collective`_.

.. _Open Collective: https://opencollective.com
.. _testrunner collective: https://opencollective.com/testrunner


testrunner for enterprise
-------------------------

Available as part of the Tidelift Subscription.

The maintainers of testrunner and thousands of other packages are working with Tidelift to deliver commercial support and
maintenance for the open source dependencies you use to build your applications.
Save time, reduce risk, and improve code health, while paying the maintainers of the exact dependencies you use.

`Learn more. <https://tidelift.com/subscription/pkg/pypi-testrunner?utm_source=pypi-testrunner&utm_medium=referral&utm_campaign=enterprise&utm_term=repo>`_

Security
^^^^^^^^

If you have found an issue that you believe is a security vulnerability, please do not create an issue -- instead, report it via a `new security advisory <https://github.com/jacksonsr451/test-runner/security/advisories/new>`__.


License
-------

Copyright Holger Krekel and others, 2004.

Distributed under the terms of the `MIT`_ license, testrunner is free and open source software.

.. _`MIT`: https://github.com/jacksonsr451/test-runner/blob/main/LICENSE
