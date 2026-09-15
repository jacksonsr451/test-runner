testrunner-2.3.2: some fixes and more traceback-printing speed
===========================================================================

testrunner-2.3.2 is another stabilization release:

- issue 205: fixes a regression with conftest detection
- issue 208/29: fixes traceback-printing speed in some bad cases
- fix teardown-ordering for parametrized setups
- fix unittest and trial compat behaviour with respect  to runTest() methods
- issue 206 and others: some improvements to packaging
- fix issue127 and others: improve some docs

See

     http://testrunner.org/

for general information.  To install or upgrade testrunner:

    pip install -U testrunner # or
    easy_install -U testrunner

best,
holger krekel


Changes between 2.3.1 and 2.3.2
-----------------------------------

- fix issue208 and fix issue29 use new py version to avoid long pauses
  when printing tracebacks in long modules

- fix issue205 - conftests in subdirs customizing
  testrunner_pycollect_makemodule and testrunner_pycollect_makeitem
  now work properly

- fix teardown-ordering for parametrized setups

- fix issue127 - better documentation for testrunner_addoption
  and related objects.

- fix unittest behaviour: TestCase.runtest only called if there are
  test methods defined

- improve trial support: don't collect its empty
  unittest.TestCase.runTest() method

- "python setup.py test" now works with testrunner itself

- fix/improve internal/packaging related bits:

  - exception message check of test_nose.py now passes on python33 as well

  - issue206 - fix test_assertrewrite.py to work when a global
    PYTHONDONTWRITEBYTECODE=1 is present

  - add tox.ini to testrunner distribution so that ignore-dirs and others config
    bits are properly distributed for maintainers who run testrunner-own tests
