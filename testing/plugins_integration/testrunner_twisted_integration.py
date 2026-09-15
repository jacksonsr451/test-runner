# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner_twisted
from twisted.internet.task import deferLater


def sleep():
    import twisted.internet.reactor

    return deferLater(clock=twisted.internet.reactor, delay=0)


@testrunner_twisted.inlineCallbacks
def test_inlineCallbacks():
    yield sleep()


@testrunner_twisted.ensureDeferred
async def test_inlineCallbacks_async():
    await sleep()
