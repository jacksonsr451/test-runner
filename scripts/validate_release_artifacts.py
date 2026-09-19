from __future__ import annotations

import argparse
from email.message import Message
from email.parser import Parser
from pathlib import Path
import tarfile
import zipfile

from packaging.utils import canonicalize_name
from packaging.utils import parse_sdist_filename
from packaging.utils import parse_wheel_filename
from packaging.version import Version


DISTRIBUTION_NAME = "jsr-testrunner"


def _metadata(contents: str) -> Message:
    metadata = Parser().parsestr(contents)
    if metadata.get("Name") != DISTRIBUTION_NAME:
        raise ValueError(f"metadata Name must be {DISTRIBUTION_NAME!r}")
    return metadata


def _entry_point(contents: str) -> None:
    in_console_scripts = False
    entry_points: dict[str, str] = {}
    for line in contents.splitlines():
        if line.startswith("["):
            in_console_scripts = line == "[console_scripts]"
            continue
        if in_console_scripts and "=" in line:
            name, value = (part.strip() for part in line.split("=", 1))
            entry_points[name] = value
    if entry_points.get("testrunner") != "_testrunner.config:_console_main":
        raise ValueError("testrunner console entry point is incorrect")


def _source_package_files(source_root: Path, package: str) -> set[str]:
    package_root = source_root / "src" / package
    return {
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def _validate_wheel(path: Path, version: str, source_root: Path) -> None:
    wheel_name, wheel_version, _, _ = parse_wheel_filename(path.name)
    if wheel_name != canonicalize_name(DISTRIBUTION_NAME) or wheel_version != Version(
        version
    ):
        raise ValueError(f"wheel filename has the wrong name or version: {path.name}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        metadata_names = [
            name for name in names if name.endswith(".dist-info/METADATA")
        ]
        entry_point_names = [
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        ]
        if len(metadata_names) != 1 or len(entry_point_names) != 1:
            raise ValueError("wheel metadata files are missing or ambiguous")
        metadata = _metadata(archive.read(metadata_names[0]).decode())
        if metadata.get("Version") != version:
            raise ValueError("wheel metadata version does not match the tag")
        _entry_point(archive.read(entry_point_names[0]).decode())
        package_files = {
            name
            for name in names
            if not name.endswith("/") and ".dist-info/" not in name
        }
        expected_files = {
            f"{package}/{relative}"
            for package in ("testrunner", "_testrunner")
            for relative in _source_package_files(source_root, package)
        }
        missing_files = expected_files.difference(package_files)
        if missing_files:
            raise ValueError(f"wheel is missing files: {sorted(missing_files)}")


def _validate_sdist(path: Path, version: str, source_root: Path) -> None:
    sdist_name, sdist_version = parse_sdist_filename(path.name)
    if sdist_name != canonicalize_name(DISTRIBUTION_NAME) or sdist_version != Version(
        version
    ):
        raise ValueError(f"sdist filename has the wrong name or version: {path.name}")
    with tarfile.open(path) as archive:
        names = archive.getnames()
        pkg_info_names = [
            name
            for name in names
            if len(Path(name).parts) == 2 and name.endswith("/PKG-INFO")
        ]
        if len(pkg_info_names) != 1:
            raise ValueError("sdist PKG-INFO is missing or ambiguous")
        metadata = _metadata(
            archive.extractfile(pkg_info_names[0]).read().decode()  # type: ignore[union-attr]
        )
        if metadata.get("Version") != version:
            raise ValueError("sdist PKG-INFO version does not match the tag")
        roots = {Path(name).parts[0] for name in names if Path(name).parts}
        if len(roots) != 1:
            raise ValueError("sdist must have one source root")
        root = next(iter(roots))
        package_files = {name for name in names if not name.endswith("/")}
        expected_files = {
            f"{root}/src/{package}/{relative}"
            for package in ("testrunner", "_testrunner")
            for relative in _source_package_files(source_root, package)
        }
        missing_files = expected_files.difference(package_files)
        if missing_files:
            raise ValueError(f"sdist is missing files: {sorted(missing_files)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()

    wheels = sorted(args.dist.glob("*.whl"))
    sdists = sorted(args.dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("release must contain exactly one wheel and one sdist")
    _validate_wheel(wheels[0], args.version, args.source_root)
    _validate_sdist(sdists[0], args.version, args.source_root)
    print(f"validated {wheels[0].name} and {sdists[0].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
