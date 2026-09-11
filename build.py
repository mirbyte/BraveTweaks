from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP_NAME = "BraveTweaks"
ENTRYPOINT = ROOT / "main.pyw"
ICON = ROOT / "assets" / "icon.ico"


def check_requirements() -> None:
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required.")

    if not ENTRYPOINT.is_file():
        raise SystemExit(f"Missing entry point: {ENTRYPOINT}")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise SystemExit(
            "PyInstaller is not installed. Run: "
            f"{sys.executable} -m pip install pyinstaller"
        )

    print(f"Using PyInstaller {result.stdout.strip()}")


def clean() -> None:
    for path in (ROOT / "build", ROOT / "dist", ROOT / f"{APP_NAME}.spec"):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def build() -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--name",
        APP_NAME,
        "--paths",
        str(ROOT / "src"),
    ]

    if ICON.is_file():
        command.extend(["--icon", str(ICON)])
        print(f"Using icon: {ICON}")

    command.append(str(ENTRYPOINT))
    subprocess.run(command, cwd=ROOT, check=True)

    executable = ROOT / "dist" / f"{APP_NAME}.exe"
    size_mb = executable.stat().st_size / (1024 * 1024)
    print(f"Build complete: {executable} ({size_mb:.1f} MB)")


def pause() -> None:
    if sys.stdin.isatty():
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        check_requirements()
        clean()
        build()
    except SystemExit as error:
        if error.code not in (None, 0):
            print(f"\n{error.code}")
        pause()
        raise SystemExit(error.code if isinstance(error.code, int) else 1)
    except Exception as error:
        print(f"\nBuild failed: {error}")
        pause()
        raise SystemExit(1)
    pause()
