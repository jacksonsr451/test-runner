"""
This is the script that is actually frozen into an executable: simply executes
testrunner main().
"""

from __future__ import annotations


if __name__ == "__main__":
    import sys

    import testrunner

    sys.exit(testrunner.main())
