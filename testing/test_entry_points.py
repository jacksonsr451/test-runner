# mypy: allow-untyped-defs
from __future__ import annotations

import importlib.metadata


def test_testrunner_entry_points_are_identical():
    dist = importlib.metadata.distribution("jsr-testrunner")
    entry_map = {ep.name: ep for ep in dist.entry_points}
    assert entry_map["testrunner"].value == "_testrunner.config:_console_main"
