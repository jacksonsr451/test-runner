testrunner-2.2.4: bug fixes, better junitxml/unittest/python3 compat
===========================================================================

testrunner-2.2.4 is a minor backward-compatible release of the versatile
testrunner testing tool.   It contains bug fixes and a few refinements
to junitxml reporting, better unittest- and python3 compatibility.

For general information see here:

     http://testrunner.org/

To install or upgrade testrunner:

    pip install -U testrunner # or
    easy_install -U testrunner

Special thanks for helping on this release to Ronny Pfannschmidt
and Benjamin Peterson and the contributors of issues.

best,
holger krekel

Changes between 2.2.3 and 2.2.4
-----------------------------------

- fix error message for rewritten assertions involving the % operator
- fix issue 126: correctly match all invalid xml characters for junitxml
  binary escape
- fix issue with unittest: now @unittest.expectedFailure markers should
  be processed correctly (you can also use @testrunner.mark markers)
- document integration with the extended distribute/setuptools test commands
- fix issue 140: properly get the real functions
  of bound classmethods for setup/teardown_class
- fix issue #141: switch from the deceased paste.pocoo.org to bpaste.net
- fix issue #143: call unconfigure/sessionfinish always when
  configure/sessionstart where called
- fix issue #144: better mangle test ids to junitxml classnames
- upgrade distribute_setup.py to 0.6.27
