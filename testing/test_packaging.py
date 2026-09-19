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


def _clean_environment(*, include_git: bool = True) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    for key in tuple(env):
        if key.startswith("SETUPTOOLS_SCM_PRETEND_VERSION"):
            env.pop(key)
    env["PYTHONNOUSERSITE"] = "1"
    path_entries = [Path(sys.executable).parent]
    if include_git and GIT is not None:
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


def _scm_version(root: Path, work: Path) -> str:
    python = _make_venv(work / "scm-venv")
    result = subprocess.run(
        [os.fspath(python), "-m", "pip", "install", "setuptools-scm[toml]>=10.1"],
        cwd=work,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    result = _run_python(
        python,
        root,
        "-c",
        "import setuptools_scm; print(setuptools_scm.get_version(root='.'))",
    )
    assert result.returncode == 0, result.stderr
    version = result.stdout.strip()
    _assert_valid_version(version)
    return version


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


def _cli_version(output: str) -> str:
    prefix = "testrunner "
    assert output.startswith(prefix)
    version = output[len(prefix) :]
    _assert_valid_version(version)
    return version


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
import os
import sys
import _testrunner
import testrunner

print(json.dumps({
    "version": _testrunner.__version__,
    "_testrunner_file": _testrunner.__file__,
    "testrunner_file": testrunner.__file__,
    "distribution_names": importlib.metadata.packages_distributions().get("_testrunner", []),
    "pythonpath": os.environ.get("PYTHONPATH"),
    "sys_path": sys.path,
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


def _build_artifacts(
    root: Path,
    output: Path,
    *,
    include_git: bool = True,
    build_sdist: bool = True,
) -> tuple[Path, Path | None]:
    build_python = _make_venv(output.parent / "build-venv")
    build_dependency_result = subprocess.run(
        [os.fspath(build_python), "-m", "pip", "install", "build"],
        cwd=output.parent,
        env=_clean_environment(include_git=include_git),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert build_dependency_result.returncode == 0, (
        f"stdout={build_dependency_result.stdout}\n"
        f"stderr={build_dependency_result.stderr}"
    )
    build_arguments = [
        os.fspath(build_python),
        "-m",
        "build",
        "--wheel",
    ]
    if build_sdist:
        build_arguments.append("--sdist")
    build_arguments.extend(("--outdir", os.fspath(output)))
    build_result = subprocess.run(
        build_arguments,
        cwd=root,
        env=_clean_environment(include_git=include_git),
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
    if build_sdist:
        assert len(sdists) == 1
        return wheels[0], sdists[0]
    assert not sdists
    return wheels[0], None


def _extract_sdist(artifact: Path, destination: Path) -> Path:
    destination = destination.resolve()
    with tarfile.open(artifact) as archive:
        destination.mkdir()
        for member in archive.getmembers():
            relative = Path(member.name)
            assert not relative.is_absolute()
            assert ".." not in relative.parts
            assert member.isfile() or member.isdir()
            target = (destination / relative).resolve()
            assert os.path.commonpath(
                (os.fspath(destination), os.fspath(target))
            ) == os.fspath(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            if sys.version_info >= (3, 12):
                archive.extract(member, destination, filter="data")
            else:
                archive.extract(member, destination)
    roots = sorted(path for path in destination.iterdir() if path.is_dir())
    assert len(roots) == 1
    return roots[0]


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


def _git_value(root: Path, *arguments: str) -> str:
    assert GIT is not None, "git executable is required for source-tree contracts"
    result = subprocess.run(
        [GIT, *arguments],
        cwd=root,
        env=_clean_environment(),
        capture_output=True,
        check=False,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    return result.stdout.strip()


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
    module_cli_version = _cli_version(module_result.stdout.strip())
    console_cli_version = _cli_version(cli_result.stdout.strip())
    assert module_cli_version == version
    assert console_cli_version == version
    assert probe["pythonpath"] is None
    assert all(os.fspath(root) not in entry for entry in probe["sys_path"])
    assert os.fspath(root) not in probe["_testrunner_file"]
    assert os.fspath(root) not in probe["testrunner_file"]
    probe["installed_version"] = metadata_version
    probe["module_cli_version"] = module_cli_version
    probe["console_cli_version"] = console_cli_version
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
def packaging_artifacts(
    tmp_path_factory: Any,
) -> Iterator[tuple[Path, Path, Path, Path]]:
    work = Path(tmp_path_factory.mktemp("packaging"))
    clone = work / "source"
    _clone_project(clone)
    output = work / "dist"
    output.mkdir()
    wheel, sdist = _build_artifacts(clone, output)
    assert sdist is not None
    assert _git_value(clone, "status", "--porcelain") == ""
    assert _git_value(clone, "rev-parse", "HEAD") == _git_value(
        PROJECT_ROOT, "rev-parse", "HEAD"
    )
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
    with TemporaryDirectory(prefix="testrunner-sdist-") as derived_temporary:
        derived_work = Path(derived_temporary)
        extracted = _extract_sdist(sdist, derived_work / "extracted")
        assert not (extracted / ".git").exists()
        derived_result = _build_artifacts(
            extracted,
            derived_work / "derived-dist",
            include_git=False,
            build_sdist=False,
        )
        derived_wheel = derived_result[0]
        assert derived_result[1] is None
        yield clone, wheel, sdist, derived_wheel
    shutil.rmtree(work, ignore_errors=True)


@testrunner.mark.slow
def test_wheel_version_contract(
    packaging_artifacts: tuple[Path, Path, Path, Path],
    tmp_path: Path,
) -> None:
    root, wheel, _, _ = packaging_artifacts
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert any(name.endswith("_testrunner/_version.py") for name in names)
        assert any(name.endswith(".dist-info/METADATA") for name in names)
        assert any(name.endswith(".dist-info/entry_points.txt") for name in names)
        assert any(name.startswith("_testrunner/") for name in names)
        assert any(name.startswith("testrunner/") for name in names)
        for name in names:
            parts = Path(name).parts
            assert ".git" not in parts
            assert "build" not in parts
            assert "dist" not in parts
            assert "__pycache__" not in parts
            assert ".pytest_cache" not in parts
            assert ".mypy_cache" not in parts
            assert not any(part.endswith(".egg-info") for part in parts)
    _install_and_probe(wheel, root, tmp_path)


@testrunner.mark.slow
def test_sdist_version_contract(
    packaging_artifacts: tuple[Path, Path, Path, Path],
    tmp_path: Path,
) -> None:
    root, _, sdist, derived_wheel = packaging_artifacts
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        assert any(name.endswith("/PKG-INFO") for name in names)
        assert any(name.endswith("/pyproject.toml") for name in names)
        assert any(name.endswith("src/_testrunner/_version.py") for name in names)
        assert any("/src/_testrunner/" in f"/{name}" for name in names)
        assert any("/src/testrunner/" in f"/{name}" for name in names)
        for name in names:
            parts = Path(name).parts
            assert ".git" not in parts
            assert "build" not in parts
            assert "dist" not in parts
            assert "__pycache__" not in parts
            assert ".pytest_cache" not in parts
            assert ".mypy_cache" not in parts

    sdist_name = _distribution_name(sdist)
    sdist_version = _distribution_version(sdist)
    derived_name = _distribution_name(derived_wheel)
    derived_version = _distribution_version(derived_wheel)
    assert canonicalize_name(derived_name) == canonicalize_name(sdist_name)
    assert Version(derived_version) == Version(sdist_version)
    wheel_name, wheel_version, _, _ = parse_wheel_filename(derived_wheel.name)
    assert wheel_name == canonicalize_name(derived_name)
    assert wheel_version == Version(derived_version)
    with zipfile.ZipFile(derived_wheel) as archive:
        for name in archive.namelist():
            parts = Path(name).parts
            assert ".git" not in parts
            assert "build" not in parts
            assert "dist" not in parts
            assert "__pycache__" not in parts
            assert ".pytest_cache" not in parts
            assert ".mypy_cache" not in parts
            assert not any(part.endswith(".egg-info") for part in parts)
    _install_and_probe(derived_wheel, root, tmp_path / "derived-wheel-install")

    _install_and_probe(sdist, root, tmp_path / "sdist-install")


@testrunner.mark.slow
def test_version_is_consistent_across_source_and_artifacts(
    packaging_artifacts: tuple[Path, Path, Path, Path],
    tmp_path: Path,
) -> None:
    root, wheel, sdist, derived_wheel = packaging_artifacts
    scm_version = _scm_version(root, tmp_path)
    source_python = _make_venv(tmp_path / "source-venv")
    _install_runtime_dependencies(source_python, root)
    source_probe = _read_probe(
        _run_python(
            source_python,
            tmp_path,
            "-c",
            _source_probe(),
            pythonpath=root / "src",
        )
    )
    source_cli = _run_python(
        source_python,
        tmp_path,
        "-m",
        "testrunner",
        "--version",
        pythonpath=root / "src",
    )
    assert source_cli.returncode == 0, source_cli.stderr
    source_cli_version = _cli_version(source_cli.stdout.strip())
    assert source_cli_version == scm_version

    wheel_probe = _install_and_probe(wheel, root, tmp_path / "wheel-install")
    sdist_probe = _install_and_probe(sdist, root, tmp_path / "sdist-install")
    derived_probe = _install_and_probe(
        derived_wheel, root, tmp_path / "derived-install"
    )
    versions = {
        scm_version,
        source_probe["version"],
        source_cli_version,
        _distribution_version(wheel),
        wheel_probe["installed_version"],
        wheel_probe["version"],
        wheel_probe["module_cli_version"],
        wheel_probe["console_cli_version"],
        _distribution_version(sdist),
        sdist_probe["installed_version"],
        sdist_probe["version"],
        sdist_probe["module_cli_version"],
        sdist_probe["console_cli_version"],
        _distribution_version(derived_wheel),
        derived_probe["installed_version"],
        derived_probe["version"],
        derived_probe["module_cli_version"],
        derived_probe["console_cli_version"],
    }
    assert versions == {scm_version}

    distribution_names = {
        canonicalize_name(_distribution_name(wheel)),
        canonicalize_name(_distribution_name(sdist)),
        canonicalize_name(_distribution_name(derived_wheel)),
        canonicalize_name(wheel_probe["distribution_names"][0]),
        canonicalize_name(sdist_probe["distribution_names"][0]),
        canonicalize_name(derived_probe["distribution_names"][0]),
    }
    assert distribution_names == {"testrunner"}


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
