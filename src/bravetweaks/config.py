from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    scope: str = "user"
    data_dir: Path = default_data_dir()

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"
