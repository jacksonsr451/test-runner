from __future__ import annotations

from _testrunner.config import Config
from _testrunner.config import ExitCode
from _testrunner.config.argparsing import Parser
from _testrunner.fixtures import FixtureDef
from _testrunner.fixtures import SubRequest
import testrunner


def testrunner_addoption(parser: Parser) -> None:
    group = parser.getgroup("debugconfig")
    group.addoption(
        "--setupplan",
        "--setup-plan",
        action="store_true",
        help="Show what fixtures and tests would be executed but "
        "don't execute anything",
    )


@testrunner.hookimpl(tryfirst=True)
def testrunner_fixture_setup(
    fixturedef: FixtureDef[object], request: SubRequest
) -> object | None:
    # Will return a dummy fixture if the setuponly option is provided.
    if request.config.option.setupplan:
        my_cache_key = fixturedef.cache_key(request)
        fixturedef.cached_result = (None, my_cache_key, None)
        return fixturedef.cached_result
    return None


@testrunner.hookimpl(tryfirst=True)
def testrunner_cmdline_main(config: Config) -> int | ExitCode | None:
    if config.option.setupplan:
        config.option.setuponly = True
        config.option.setupshow = True
    return None
