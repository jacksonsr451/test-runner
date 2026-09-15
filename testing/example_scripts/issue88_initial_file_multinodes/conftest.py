# mypy: allow-untyped-defs
from __future__ import annotations

import testrunner


class MyFile(testrunner.File):
    def collect(self):
        return [MyItem.from_parent(name="hello", parent=self)]


def testrunner_collect_file(file_path, parent):
    return MyFile.from_parent(path=file_path, parent=parent)


class MyItem(testrunner.Item):
    def runtest(self):
        raise NotImplementedError()
