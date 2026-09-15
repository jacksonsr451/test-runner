# content of conftest.py
from __future__ import annotations

import json

import testrunner


class ManifestDirectory(testrunner.Directory):
    def collect(self):
        # The standard testrunner behavior is to loop over all `test_*.py` files and
        # call `testrunner_collect_file` on each file. This collector instead reads
        # the `manifest.json` file and only calls `testrunner_collect_file` for the
        # files defined there.
        manifest_path = self.path / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ihook = self.ihook
        for file in manifest["files"]:
            yield from ihook.testrunner_collect_file(
                file_path=self.path / file, parent=self
            )


@testrunner.hookimpl
def testrunner_collect_directory(path, parent):
    # Use our custom collector for directories containing a `manifest.json` file.
    if path.joinpath("manifest.json").is_file():
        return ManifestDirectory.from_parent(parent=parent, path=path)
    # Otherwise fallback to the standard behavior.
    return None
