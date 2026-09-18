from __future__ import annotations

from collections.abc import Iterator
from email.message import Message
from email.parser import Parser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from typing import Any
from typing import cast
import venv
import zipfile

from packaging.utils import canonicalize_name
from packaging.utils import parse_sdist_filename
from packaging.utils import parse_wheel_filename
from packaging.version import Version

import testrunner


PROJECT_ROOT = Path(__file__).parents[1]
VERSION_SENTINELS = {"unknown", "0.0.0"}
GIT = shutil.which("git")
SUBPROCESS_TIMEOUT = 300
RUNTIME_DEPENDENCIES = (
    "colorama>=0.4",
    "exceptiongroup>=1; python_version<'3.11'",
    "iniconfig>=2",
    "packaging>=24",
    "pluggy>=1.5,<2",
    "pygments>=2.15",
    "tomli>=2; python_version<'3.11'",
)


def _clean_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    path_entries = [Path(sys.executable).parent]
    if GIT is not None:
        path_entries.append(Path(GIT).parent)
    env["PATH"] = os.pathsep.join(map(os.fspath, path_entries))
    return env


def _python_path(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _script_path(environment: Path, name: str) -> Path:
    directory = "Scripts" if sys.platform == "win32" else "bin"
    suffix = ".exe" if sys.platform == "win32" else ""
    return environment / directory / f"{name}{suffix}"


def _make_venv(path: Path) -> Path:
    venv.EnvBuilder(with_pip=True, clear=True).create(path)
    return _python_path(path)


def _install_runtime_dependencies(python: Path, cwd: Path) -> None:
    result = subprocess.run(
        [os.fspath(python), "-m", "pip", "install", *RUNTIME_DEPENDENCIES],
        cwd=cwd,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def _bootstrap_source_checkout(clone: Path, python: Path) -> None:
    dependency_result = subprocess.run(
        [
            os.fspath(python),
            "-m",
            "pip",
            "install",
            "setuptools-scm[toml]>=10.1",
        ],
        cwd=clone,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert dependency_result.returncode == 0, (
        f"stdout={dependency_result.stdout}\nstderr={dependency_result.stderr}"
    )
    result = subprocess.run(
        [os.fspath(python), "-m", "setuptools_scm", "--force-write-version-files"],
        cwd=clone,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    _install_runtime_dependencies(python, clone)


def _run_python(
    python: Path,
    cwd: Path,
    *arguments: str,
    pythonpath: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = _clean_environment()
    if pythonpath is not None:
        environment["PYTHONPATH"] = os.fspath(pythonpath)
    return subprocess.run(
        [os.fspath(python), *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )


def _assert_valid_version(version: str) -> None:
    assert version not in VERSION_SENTINELS
    Version(version)


def _version_probe() -> str:
    return """
import json
import _testrunner

print(json.dumps({
    "version": _testrunner.__version__,
    "_testrunner_file": _testrunner.__file__,
}))
"""


def _artifact_probe() -> str:
    return """
import json
import importlib.metadata
import _testrunner
import testrunner

print(json.dumps({
    "version": _testrunner.__version__,
    "_testrunner_file": _testrunner.__file__,
    "testrunner_file": testrunner.__file__,
    "distribution_names": importlib.metadata.packages_distributions().get("_testrunner", []),
}))
"""


def _source_probe() -> str:
    return """
import json
import _testrunner
import testrunner

print(json.dumps({
    "version": _testrunner.__version__,
    "_testrunner_file": _testrunner.__file__,
    "testrunner_file": testrunner.__file__,
}))
"""


def _read_probe(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    return cast(dict[str, str], json.loads(result.stdout))


def _distribution_metadata(artifact: Path) -> Message:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            metadata_name = next(
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            )
            metadata = archive.read(metadata_name).decode()
    else:
        with tarfile.open(artifact) as archive:
            metadata_name = next(
                name for name in archive.getnames() if name.endswith("/PKG-INFO")
            )
            metadata = archive.extractfile(metadata_name).read().decode()  # type: ignore[union-attr]
    return Parser().parsestr(metadata)


def _distribution_name(artifact: Path) -> str:
    name = _distribution_metadata(artifact).get("Name")
    assert name
    return name


def _distribution_version(artifact: Path) -> str:
    version = _distribution_metadata(artifact).get("Version")
    assert version
    return version


def _build_artifacts(root: Path, output: Path) -> tuple[Path, Path]:
    build_python = _make_venv(output.parent / "build-venv")
    build_dependency_result = subprocess.run(
        [os.fspath(build_python), "-m", "pip", "install", "build"],
        cwd=output.parent,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert build_dependency_result.returncode == 0, (
        f"stdout={build_dependency_result.stdout}\n"
        f"stderr={build_dependency_result.stderr}"
    )
    build_result = subprocess.run(
        [
            os.fspath(build_python),
            "-m",
            "build",
            "--wheel",
            "--sdist",
            "--outdir",
            os.fspath(output),
        ],
        cwd=root,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert build_result.returncode == 0, (
        f"stdout={build_result.stdout}\nstderr={build_result.stderr}"
    )
    wheels = sorted(output.glob("*.whl"))
    sdists = sorted(output.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1
    return wheels[0], sdists[0]


def _clone_project(path: Path) -> None:
    assert GIT is not None, "git executable is required for source-tree contracts"
    result = subprocess.run(
        [
            GIT,
            "clone",
            "--local",
            "--no-hardlinks",
            os.fspath(PROJECT_ROOT),
            os.fspath(path),
        ],
        cwd=path.parent,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def _install_and_probe(artifact: Path, root: Path, work: Path) -> dict[str, Any]:
    environment = work / "venv"
    python = _make_venv(environment)
    result = subprocess.run(
        [os.fspath(python), "-m", "pip", "install", os.fspath(artifact)],
        cwd=work,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    probe = _read_probe(_run_python(python, work, "-c", _artifact_probe()))
    distribution_names = sorted(set(probe["distribution_names"]))
    assert len(distribution_names) == 1
    metadata_name = distribution_names[0]
    metadata_result = _run_python(
        python,
        work,
        "-c",
        f"import importlib.metadata; print(importlib.metadata.version({metadata_name!r}))",
    )
    assert metadata_result.returncode == 0, metadata_result.stderr
    metadata_version = metadata_result.stdout.strip()
    module_result = _run_python(python, work, "-m", "testrunner", "--version")
    cli = _script_path(environment, "testrunner")
    cli_result = subprocess.run(
        [os.fspath(cli), "--version"],
        cwd=work,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert module_result.returncode == 0, module_result.stderr
    assert cli_result.returncode == 0, cli_result.stderr
    version = probe["version"]
    _assert_valid_version(version)
    assert metadata_version == version
    assert module_result.stdout.strip() == f"testrunner {version}"
    assert cli_result.stdout.strip() == f"testrunner {version}"
    assert os.fspath(root) not in probe["_testrunner_file"]
    assert os.fspath(root) not in probe["testrunner_file"]
    return probe


@testrunner.mark.slow
def test_raw_source_checkout_starts_without_generated_version() -> None:
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        clone = work / "source"
        _clone_project(clone)
        assert (clone / ".git").exists()
        assert not (clone / "src" / "_testrunner" / "_version.py").exists()
        assert not (clone / "build").exists()
        assert not (clone / "dist").exists()
        assert not (clone / "src" / "testrunner.egg-info").exists()


@testrunner.mark.slow
def test_source_version_bootstrap_generates_runtime_version() -> None:
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        clone = work / "source"
        _clone_project(clone)
        python = _make_venv(work / "venv")
        version_file = clone / "src" / "_testrunner" / "_version.py"
        assert not version_file.exists()
        _bootstrap_source_checkout(clone, python)
        assert version_file.exists()
        result = _run_python(
            python,
            work,
            "-c",
            _version_probe(),
            pythonpath=clone / "src",
        )
        probe = _read_probe(result)
        _assert_valid_version(probe["version"])
        cli_result = _run_python(
            python,
            work,
            "-m",
            "testrunner",
            "--version",
            pythonpath=clone / "src",
        )
        assert cli_result.returncode == 0, cli_result.stderr
        assert cli_result.stdout.strip() == f"testrunner {probe['version']}"


@testrunner.mark.slow
def test_prepared_source_checkout_reports_runtime_version() -> None:
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        clone = work / "source"
        _clone_project(clone)
        python = _make_venv(work / "venv")
        _bootstrap_source_checkout(clone, python)
        probe = _read_probe(
            _run_python(
                python,
                work,
                "-c",
                _source_probe(),
                pythonpath=clone / "src",
            )
        )
        _assert_valid_version(probe["version"])
        assert probe["_testrunner_file"].startswith(os.fspath(clone / "src"))
        assert probe["testrunner_file"].startswith(os.fspath(clone / "src"))
        cli_result = _run_python(
            python,
            work,
            "-m",
            "testrunner",
            "--version",
            pythonpath=clone / "src",
        )
        assert cli_result.returncode == 0, cli_result.stderr
        assert cli_result.stdout.strip() == f"testrunner {probe['version']}"


@testrunner.fixture(scope="session")
def packaging_artifacts(tmp_path_factory: Any) -> Iterator[tuple[Path, Path, Path]]:
    work = Path(tmp_path_factory.mktemp("packaging"))
    clone = work / "source"
    _clone_project(clone)
    output = work / "dist"
    output.mkdir()
    wheel, sdist = _build_artifacts(clone, output)
    distribution_name = _distribution_name(wheel)
    version = _distribution_version(wheel)
    assert distribution_name == _distribution_name(sdist)
    assert version == _distribution_version(sdist)
    wheel_name, wheel_version, _, _ = parse_wheel_filename(wheel.name)
    sdist_name, sdist_version = parse_sdist_filename(sdist.name)
    assert wheel_name == canonicalize_name(distribution_name)
    assert sdist_name == canonicalize_name(distribution_name)
    assert wheel_version == Version(version)
    assert sdist_version == Version(version)
    assert (clone / "src" / "_testrunner" / "_version.py").exists()
    assert (clone / "build").exists()
    assert output.exists()
    yield clone, wheel, sdist
    shutil.rmtree(work, ignore_errors=True)


@testrunner.mark.slow
def test_wheel_version_contract(
    packaging_artifacts: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    root, wheel, _ = packaging_artifacts
    with zipfile.ZipFile(wheel) as archive:
        assert any(
            name.endswith("_testrunner/_version.py") for name in archive.namelist()
        )
    _install_and_probe(wheel, root, tmp_path)


@testrunner.mark.slow
def test_sdist_version_contract(
    packaging_artifacts: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    root, _, sdist = packaging_artifacts
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        assert any(name.endswith("/PKG-INFO") for name in names)
        assert any(name.endswith("/pyproject.toml") for name in names)
        assert any(name.endswith("_testrunner/_version.py") for name in names)
        assert not any(".git" in Path(name).parts for name in names)
    _install_and_probe(sdist, root, tmp_path)


@testrunner.mark.slow
def test_editable_install_bootstraps_version(tmp_path: Path) -> None:
    clone = tmp_path / "source"
    _clone_project(clone)
    version_file = clone / "src" / "_testrunner" / "_version.py"
    assert not version_file.exists()
    python = _make_venv(tmp_path / "venv")
    result = subprocess.run(
        [os.fspath(python), "-m", "pip", "install", "--editable", os.fspath(clone)],
        cwd=tmp_path,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert version_file.exists()
    probe = _read_probe(_run_python(python, tmp_path, "-c", _artifact_probe()))
    _assert_valid_version(probe["version"])
    distribution_names = sorted(set(probe["distribution_names"]))
    assert len(distribution_names) == 1
    metadata_result = _run_python(
        python,
        tmp_path,
        "-c",
        "import importlib.metadata, sys; print(importlib.metadata.version(sys.argv[1]))",
        distribution_names[0],
    )
    assert metadata_result.returncode == 0, metadata_result.stderr
    assert metadata_result.stdout.strip() == probe["version"]
    module_result = _run_python(python, tmp_path, "-m", "testrunner", "--version")
    assert module_result.returncode == 0, module_result.stderr
    assert module_result.stdout.strip() == f"testrunner {probe['version']}"
    cli_result = subprocess.run(
        [os.fspath(_script_path(tmp_path / "venv", "testrunner")), "--version"],
        cwd=tmp_path,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert cli_result.returncode == 0, cli_result.stderr
    assert cli_result.stdout.strip() == f"testrunner {probe['version']}"
