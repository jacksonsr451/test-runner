testrunner 2.1.2: bug fixes and fixes for jython
===========================================================================

testrunner-2.1.2 is a minor backward compatible maintenance release of the
popular testrunner testing tool.  testrunner is commonly used for unit,
functional- and integration testing.  See extensive docs with examples
here:

     http://testrunner.org/

Most bug fixes address remaining issues with the perfected assertions
introduced in the 2.1 series - many thanks to the bug reporters and to Benjamin
Peterson for helping to fix them.  testrunner should also work better with
Jython-2.5.1 (and Jython trunk).

If you want to install or upgrade testrunner, just type one of::

    pip install -U testrunner # or
    easy_install -U testrunner

best,
holger krekel / https://merlinux.eu/

Changes between 2.1.1 and 2.1.2
----------------------------------------

- fix assertion rewriting on files with windows newlines on some Python versions
- refine test discovery by package/module name (--pyargs), thanks Florian Mayer
- fix issue69 / assertion rewriting fixed on some boolean operations
- fix issue68 / packages now work with assertion rewriting
- fix issue66: use different assertion rewriting caches when the -O option is passed
- don't try assertion rewriting on Jython, use reinterp
