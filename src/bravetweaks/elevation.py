from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path


def ensure_elevated() -> bool:
    if sys.platform != "win32" or ctypes.windll.shell32.IsUserAnAdmin():
        return True

    executable, parameters = _relaunch_command()
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        parameters,
        str(Path.cwd()),
        1,
    )
    if result <= 32:
        ctypes.windll.user32.MessageBoxW(
            None,
            "BraveTweaks requires Administrator permission to modify Brave policies.",
            "BraveTweaks",
            0x10,
        )
    return False


def _relaunch_command() -> tuple[str, str]:
    executable = sys.executable
    if getattr(sys, "frozen", False):
        arguments = sys.argv[1:]
    else:
        original_arguments = getattr(sys, "orig_argv", None)
        arguments = (
            original_arguments[1:]
            if original_arguments
            else [sys.argv[0], *sys.argv[1:]]
        )
    return executable, subprocess.list2cmdline(arguments)
