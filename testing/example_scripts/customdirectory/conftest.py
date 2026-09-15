# mypy: allow-untyped-defs
# content of conftest.py
from __future__ import annotations

import json

import testrunner


class ManifestDirectory(testrunner.Directory):
    def collect(self):
        manifest_path = self.path / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ihook = self.ihook
        for file in manifest["files"]:
            yield from ihook.testrunner_collect_file(
                file_path=self.path / file, parent=self
            )


@testrunner.hookimpl
def testrunner_collect_directory(path, parent):
    if path.joinpath("manifest.json").is_file():
        return ManifestDirectory.from_parent(parent=parent, path=path)
    return None
