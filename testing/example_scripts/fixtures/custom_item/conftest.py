# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


class CustomItem(testrunner.Item):
    def runtest(self):
        pass


class CustomFile(testrunner.File):
    def collect(self):
        yield CustomItem.from_parent(name="foo", parent=self)


def testrunner_collect_file(file_path, parent):
    return CustomFile.from_parent(path=file_path, parent=parent)
