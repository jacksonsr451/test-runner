"""Deprecation messages and bits of code used elsewhere in the codebase that
is planned to be removed in the next testrunner release.

Keeping it in a central location makes it easy to track what is deprecated and should
be removed when the time comes.

All constants defined in this module should be either instances of
:class:`TestrunnerWarning`, or :class:`UnformattedWarning`
in case of warnings which need to format their messages.
"""

from __future__ import annotations

from warnings import warn

from _testrunner.warning_types import TestrunnerDeprecationWarning
from _testrunner.warning_types import TestrunnerRemovedIn10Warning
from _testrunner.warning_types import UnformattedWarning


# set of plugins which have been integrated into the core; we use this list to ignore
# them during registration to avoid conflicts
DEPRECATED_EXTERNAL_PLUGINS = {
    "testrunner_catchlog",
    "testrunner_capturelog",
    "testrunner_faulthandler",
    "testrunner_subtests",
}


# This could have been removed testrunner 8, but it's harmless and common, so no rush to remove.
YIELD_FIXTURE = TestrunnerRemovedIn10Warning(
    "@testrunner.yield_fixture is deprecated.\n"
    "Use @testrunner.fixture instead; they are the same."
)

CLASS_FIXTURE_INSTANCE_METHOD = UnformattedWarning(
    TestrunnerRemovedIn10Warning,
    "{scope}-scoped fixtures defined as instance methods are deprecated.\n"
    "Instance attributes set in the {fixturename!r} fixture will NOT be visible to test methods,\n"
    "as each test gets a new instance while the fixture runs only once per class.\n"
    "Use a @classmethod decorator below @testrunner.fixture and set attributes on cls instead.\n"
    "See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#class-scoped-fixture-as-instance-method",
)

# This deprecation is never really meant to be removed.
PRIVATE = TestrunnerDeprecationWarning(
    "A private testrunner class or function was used."
)


HOOK_LEGACY_MARKING = UnformattedWarning(
    TestrunnerRemovedIn10Warning,
    "The hook{type} {fullname} uses old-style configuration options (marks or attributes).\n"
    "Please use the testrunner.hook{type}({hook_opts}) decorator instead\n"
    " to configure the hooks.\n"
    " See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html"
    "#configuring-hook-specs-impls-using-markers",
)

MONKEYPATCH_LEGACY_NAMESPACE_PACKAGES = TestrunnerRemovedIn10Warning(
    "monkeypatch.syspath_prepend() called with pkg_resources legacy namespace packages detected.\n"
    "Legacy namespace packages (using pkg_resources.declare_namespace) are deprecated.\n"
    "Please use native namespace packages (PEP 420) instead.\n"
    "See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#monkeypatch-fixup-namespace-packages"
)

PARAMETRIZE_NON_COLLECTION_ITERABLE = UnformattedWarning(
    TestrunnerRemovedIn10Warning,
    "Passing a non-Collection iterable to parametrize is deprecated.\n"
    "Test: {nodeid}, argvalues type: {type_name}\n"
    "Please convert to a list or tuple.\n"
    "See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#parametrize-iterators",
)

CONSOLE_MAIN = TestrunnerRemovedIn10Warning(
    "testrunner.console_main() is deprecated and will be removed in testrunner 10.\n"
    "It was never intended for programmatic use; use testrunner.main() instead.\n"
    "See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#console-main"
)

CONFIG_INICFG = TestrunnerRemovedIn10Warning(
    "config.inicfg is deprecated, use config.getini() to access configuration values instead.\n"
    "See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#config-inicfg"
)

FIXTURE_GETFIXTUREVALUE_DURING_TEARDOWN = UnformattedWarning(
    TestrunnerRemovedIn10Warning,
    'Calling request.getfixturevalue("{argname}") during teardown is deprecated.\n'
    "Please request the fixture before teardown begins, either by declaring it in the fixture signature "
    "or by calling request.getfixturevalue() before the fixture yields.\n"
    "See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#dynamic-fixture-request-during-teardown",
)

PASTEBIN = TestrunnerRemovedIn10Warning(
    "The --pastebin option is deprecated. "
    "The functionality is now available in an external plugin package, testrunner-pastebin.\n"
    "See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#the-pastebin-option"
)

INI_STRING_TYPE_NON_STR_VALUE = TestrunnerRemovedIn10Warning(
    "Passing a value that is not a string to a 'string'-typed ini option is deprecated.\n"
    "In a future version this will raise a TypeError, matching the behavior of the "
    "corresponding TOML config path.\n"
    "If your plugin intentionally accepts non-string values, declare an explicit type "
    '(e.g. type="args") instead of relying on the implicit string default.'
)

# You want to make some `__init__` or function "private".
#
#   def my_private_function(some, args):
#       ...
#
# Do this:
#
#   def my_private_function(some, args, *, _istestrunner: bool = False):
#       check_istestrunner(_istestrunner)
#       ...
#
# Change all internal/allowed calls to
#
#   my_private_function(some, args, _istestrunner=True)
#
# All other calls will get the default _istestrunner=False and trigger
# the warning (possibly error in the future).


FIXTURE_BASEID_DEPRECATED = TestrunnerRemovedIn10Warning(
    "Passing baseid to FixtureDef is deprecated. Pass node instead for fixture scoping."
)

FIXTURE_NODEID_DEPRECATED = TestrunnerRemovedIn10Warning(
    "Passing nodeid to _register_fixture is deprecated. "
    "Pass node instead for fixture scoping."
)

FIXTUREDEF_HAS_LOCATION_DEPRECATED = TestrunnerRemovedIn10Warning(
    "FixtureDef.has_location is deprecated and will be removed in testrunner 10. "
    "See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#fixturedef-has-location-deprecated"
)

PARSEFACTORIES_NODEID_DEPRECATED = TestrunnerRemovedIn10Warning(
    "Passing nodeid string to parsefactories is deprecated. "
    "Use parsefactories(holder=obj, node=node) instead."
)

CALLSPEC2_RENAMED = TestrunnerRemovedIn10Warning(
    "_testrunner.python.CallSpec2 has been renamed to CallSpec.\n"
    "The CallSpec2 alias will be removed in testrunner 10.\n"
    "Update imports to use CallSpec instead.\n"
    "See https://github.com/jacksonsr451/test-runner/tree/main/doc/en/deprecations.html#callspec2-renamed"
)


def check_istestrunner(istestrunner: bool) -> None:
    if not istestrunner:
        warn(PRIVATE, stacklevel=3)
