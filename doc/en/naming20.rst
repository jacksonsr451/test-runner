
.. _naming20:

New testrunner names in 2.0 (flat is better than nested)
----------------------------------------------------

If you used older version of the ``py`` distribution (which
included the testrunner command line tool and Python name space)
you accessed helpers and possibly collection classes through
the ``testrunner`` Python namespaces.  The new ``testrunner``
Python module flatly provides the same objects, following
these renaming rules::

    testrunner.XYZ          -> testrunner.XYZ
    testrunner.collect.XYZ  -> testrunner.XYZ
    testrunner.cmdline.main -> testrunner.main

The old ``testrunner.*`` ways to access functionality remain
valid but you are encouraged to do global renaming according
to the above rules in your test code.
