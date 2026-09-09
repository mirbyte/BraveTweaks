from __future__ import annotations

import ctypes
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from bravetweaks.gui import launch

    raise SystemExit(launch())
except Exception as error:
    ctypes.windll.user32.MessageBoxW(
        0,
        f"{error}\n\nInstall the dependencies with:\n"
        f"py -3 -m pip install -r \"{PROJECT_ROOT / 'requirements.txt'}\"",
        "BraveTweaks failed to start",
        0x10,
    )
    raise
