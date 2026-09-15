testrunner-2.7.0: fixes, features, speed improvements
===========================================================================

testrunner is a mature Python testing tool with more than 1100 tests
against itself, passing on many different interpreters and platforms.
This release is supposed to be drop-in compatible to 2.6.X.

See below for the changes and see docs at:

    http://testrunner.org

As usual, you can upgrade from pypi via::

    pip install -U testrunner

Thanks to all who contributed, among them:

    Anatoly Bubenkoff
    Floris Bruynooghe
    Brianna Laugher
    Eric Siegerman
    Daniel Hahler
    Charles Cloud
    Tom Viner
    Holger Peters
    Ldiary Translations
    almarklein

have fun,
holger krekel

2.7.0 (compared to 2.6.4)
-----------------------------

- fix issue435: make reload() work when assert rewriting is active.
  Thanks Daniel Hahler.

- fix issue616: conftest.py files and their contained fixtures are now
  properly considered for visibility, independently from the exact
  current working directory and test arguments that are used.
  Many thanks to Eric Siegerman and his PR235 which contains
  systematic tests for conftest visibility and now passes.
  This change also introduces the concept of a ``rootdir`` which
  is printed as a new testrunner header and documented in the testrunner
  customize web page.

- change reporting of "diverted" tests, i.e. tests that are collected
  in one file but actually come from another (e.g. when tests in a test class
  come from a base class in a different file).  We now show the nodeid
  and indicate via a postfix the other file.

- add ability to set command line options by environment variable TESTRUNNER_ADDOPTS.

- added documentation on the new testrunner-dev teams on bitbucket and
  github.  See https://testrunner.org/en/stable/contributing.html .
  Thanks to Anatoly for pushing and initial work on this.

- fix issue650: new option ``--doctest-ignore-import-errors`` which
  will turn import errors in doctests into skips.  Thanks Charles Cloud
  for the complete PR.

- fix issue655: work around different ways that cause python2/3
  to leak sys.exc_info into fixtures/tests causing failures in 3rd party code

- fix issue615: assertion rewriting did not correctly escape % signs
  when formatting boolean operations, which tripped over mixing
  booleans with modulo operators.  Thanks to Tom Viner for the report,
  triaging and fix.

- implement issue351: add ability to specify parametrize ids as a callable
  to generate custom test ids.  Thanks Brianna Laugher for the idea and
  implementation.

- introduce and document new hookwrapper mechanism useful for plugins
  which want to wrap the execution of certain hooks for their purposes.
  This supersedes the undocumented ``__multicall__`` protocol which
  testrunner itself and some external plugins use.  Note that testrunner-2.8
  is scheduled to drop supporting the old ``__multicall__``
  and only support the hookwrapper protocol.

- majorly speed up invocation of plugin hooks

- use hookwrapper mechanism in builtin testrunner plugins.

- add a doctest ini option for doctest flags, thanks Holger Peters.

- add note to docs that if you want to mark a parameter and the
  parameter is a callable, you also need to pass in a reason to disambiguate
  it from the "decorator" case.  Thanks Tom Viner.

- "python_classes" and "python_functions" options now support glob-patterns
  for test discovery, as discussed in issue600. Thanks Ldiary Translations.

- allow to override parametrized fixtures with non-parametrized ones and vice versa (bubenkoff).

- fix issue463: raise specific error for 'parameterize' misspelling (pfctdayelise).

- On failure, the ``sys.last_value``, ``sys.last_type`` and
  ``sys.last_traceback`` are set, so that a user can inspect the error
  via postmortem debugging (almarklein).
