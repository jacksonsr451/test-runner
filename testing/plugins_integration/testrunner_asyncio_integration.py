# mypy: allow-untyped-defs
from __future__ import annotations

import asyncio

import testrunner


@testrunner.mark.asyncio
async def test_sleep():
    await asyncio.sleep(0)
