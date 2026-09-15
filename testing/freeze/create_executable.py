"""Generate an executable with testrunner runner embedded using PyInstaller."""

from __future__ import annotations


if __name__ == "__main__":
    import subprocess

    import testrunner

    hidden = []
    for x in testrunner.freeze_includes():
        hidden.extend(["--hidden-import", x])
    hidden.extend(["--hidden-import", "distutils"])
    args = ["pyinstaller", "--noconfirm", *hidden, "runtests_script.py"]
    subprocess.check_call(" ".join(args), shell=True)
