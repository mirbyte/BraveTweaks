from __future__ import annotations

import ctypes
import os
import shutil
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PRODUCT_BROWSER = "browser"
PRODUCT_ORIGIN = "origin"
PRODUCT_UNKNOWN = "unknown"

_ORIGIN_DIR = "brave-origin"
_BROWSER_DIR = "brave-browser"


class _VSFixedFileInfo(ctypes.Structure):
    _fields_ = (
        ("signature", wintypes.DWORD),
        ("struct_version", wintypes.DWORD),
        ("file_version_ms", wintypes.DWORD),
        ("file_version_ls", wintypes.DWORD),
        ("product_version_ms", wintypes.DWORD),
        ("product_version_ls", wintypes.DWORD),
        ("file_flags_mask", wintypes.DWORD),
        ("file_flags", wintypes.DWORD),
        ("file_os", wintypes.DWORD),
        ("file_type", wintypes.DWORD),
        ("file_subtype", wintypes.DWORD),
        ("file_date_ms", wintypes.DWORD),
        ("file_date_ls", wintypes.DWORD),
    )


@dataclass(frozen=True)
class BraveInstallation:
    executable: Path
    source: str
    version: str | None = None
    product: str = PRODUCT_UNKNOWN
    product_name: str | None = None

    @property
    def is_browser(self) -> bool:
        return self.product == PRODUCT_BROWSER

    @property
    def is_origin(self) -> bool:
        return self.product == PRODUCT_ORIGIN


def classify_product(executable: Path, product_name: str | None = None) -> str:
    parts = [part.lower() for part in executable.parts]
    if any(part == _ORIGIN_DIR or part.startswith(f"{_ORIGIN_DIR}-") for part in parts):
        return PRODUCT_ORIGIN
    if product_name and "origin" in product_name.lower():
        return PRODUCT_ORIGIN
    if any(part == _BROWSER_DIR or part.startswith(f"{_BROWSER_DIR}-") for part in parts):
        return PRODUCT_BROWSER
    if product_name and "brave" in product_name.lower():
        return PRODUCT_BROWSER
    return PRODUCT_UNKNOWN


def target_browser(installations: Iterable[BraveInstallation]) -> BraveInstallation | None:
    for installation in installations:
        if installation.is_browser:
            return installation
    return None


class BraveDetector:
    def detect(self, custom_path: Path | None = None, probe_version: bool = False) -> list[BraveInstallation]:
        candidates = list(self._custom_candidates(custom_path))
        candidates.extend(self._standard_candidates())
        candidates.extend(self._path_candidates())

        installations: list[BraveInstallation] = []
        seen: set[str] = set()
        for candidate, source in candidates:
            if not candidate.is_file():
                continue
            key = str(candidate.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            version = None
            product_name = None
            if probe_version:
                version, product_name = self.probe_file_info(candidate)
            product = classify_product(candidate, product_name)
            installations.append(
                BraveInstallation(
                    executable=candidate.resolve(),
                    source=source,
                    version=version,
                    product=product,
                    product_name=product_name,
                )
            )
        return installations

    def _custom_candidates(self, custom_path: Path | None) -> Iterable[tuple[Path, str]]:
        path = custom_path
        if path is None:
            configured_path = os.environ.get("BRAVE_PATH")
            path = Path(configured_path) if configured_path else None
        if path is None:
            return []
        if path.is_file():
            return [(path, "custom path")]
        return [
            (path / "brave.exe", "custom directory"),
            (path / "Application" / "brave.exe", "custom directory"),
        ]

    def _standard_candidates(self) -> Iterable[tuple[Path, str]]:
        locations = (
            ("LOCALAPPDATA", "per-user install"),
            ("PROGRAMFILES", "machine install"),
            ("PROGRAMFILES(X86)", "32-bit machine install"),
        )
        products = (
            ("Brave-Browser", "browser"),
            ("Brave-Origin", "origin"),
        )
        candidates: list[tuple[Path, str]] = []
        for variable, location in locations:
            root = os.environ.get(variable)
            if not root:
                continue
            for folder, product in products:
                candidates.append(
                    (
                        Path(root) / "BraveSoftware" / folder / "Application" / "brave.exe",
                        f"{product} {location}",
                    )
                )
        return candidates

    def _path_candidates(self) -> Iterable[tuple[Path, str]]:
        for executable_name in ("brave.exe", "brave"):
            executable = shutil.which(executable_name)
            if executable:
                yield Path(executable), "PATH"

    @staticmethod
    def probe_version(executable: Path) -> str | None:
        version, _product_name = BraveDetector.probe_file_info(executable)
        return version

    @staticmethod
    def probe_file_info(executable: Path) -> tuple[str | None, str | None]:
        if os.name != "nt":
            return None, None

        try:
            version_dll = ctypes.WinDLL("version", use_last_error=True)
            get_size = version_dll.GetFileVersionInfoSizeW
            get_size.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
            get_size.restype = wintypes.DWORD

            unused_handle = wintypes.DWORD()
            size = get_size(str(executable), ctypes.byref(unused_handle))
            if not size:
                return None, None

            buffer = ctypes.create_string_buffer(size)
            get_info = version_dll.GetFileVersionInfoW
            get_info.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
            ]
            get_info.restype = wintypes.BOOL
            if not get_info(str(executable), 0, size, buffer):
                return None, None

            query_value = version_dll.VerQueryValueW
            query_value.argtypes = [
                ctypes.c_void_p,
                wintypes.LPCWSTR,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(wintypes.UINT),
            ]
            query_value.restype = wintypes.BOOL

            value = ctypes.c_void_p()
            value_size = wintypes.UINT()
            version = None
            if query_value(buffer, "\\", ctypes.byref(value), ctypes.byref(value_size)):
                fixed_info = ctypes.cast(value, ctypes.POINTER(_VSFixedFileInfo)).contents
                if fixed_info.signature == 0xFEEF04BD:
                    major = fixed_info.file_version_ms >> 16
                    minor = fixed_info.file_version_ms & 0xFFFF
                    build = fixed_info.file_version_ls >> 16
                    revision = fixed_info.file_version_ls & 0xFFFF
                    version = f"{major}.{minor}.{build}.{revision}"

            product_name = None
            if query_value(
                buffer,
                r"\VarFileInfo\Translation",
                ctypes.byref(value),
                ctypes.byref(value_size),
            ) and value_size.value >= 4:
                translation = ctypes.cast(value, ctypes.POINTER(wintypes.WORD))
                lang = translation[0]
                codepage = translation[1]
                name_path = f"\\StringFileInfo\\{lang:04X}{codepage:04X}\\ProductName"
                if query_value(
                    buffer,
                    name_path,
                    ctypes.byref(value),
                    ctypes.byref(value_size),
                ) and value.value:
                    product_name = ctypes.wstring_at(value.value) or None

            return version, product_name
        except (OSError, ValueError, ctypes.ArgumentError):
            return None, None
