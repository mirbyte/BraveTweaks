from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, Iterable

try:
    import winreg
except ImportError:
    winreg = None


DEFAULT_KEY_PATH = r"Software\Policies\BraveSoftware\Brave"


class RegistryUnavailableError(RuntimeError):
    pass


class RegistryStore:
    def __init__(self, scope: str = "user", key_path: str = DEFAULT_KEY_PATH) -> None:
        if sys.platform != "win32" or winreg is None:
            raise RegistryUnavailableError("BraveTweaks registry operations require Windows.")
        if scope not in {"user", "machine"}:
            raise ValueError("scope must be 'user' or 'machine'")
        self.scope = scope
        self.key_path = key_path
        self.hive_name = "HKCU" if scope == "user" else "HKLM"
        self.hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE

    def read_value(self, name: str) -> tuple[Any, int] | None:
        try:
            with winreg.OpenKey(self.hive, self.key_path, 0, winreg.KEY_READ) as key:
                return winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None

    def read_values(self) -> dict[str, tuple[Any, int]]:
        try:
            with winreg.OpenKey(self.hive, self.key_path, 0, winreg.KEY_READ) as key:
                value_count = winreg.QueryInfoKey(key)[1]
                values = {}
                for index in range(value_count):
                    name, value, registry_type = winreg.EnumValue(key, index)
                    values[name] = (value, registry_type)
                return values
        except FileNotFoundError:
            return {}

    def set_value(
        self,
        name: str,
        value: Any,
        registry_type: int | None = None,
    ) -> None:
        if registry_type is None:
            registry_type = (
                winreg.REG_DWORD
                if isinstance(value, bool) or isinstance(value, int)
                else winreg.REG_SZ
            )
        stored_value = int(value) if isinstance(value, bool) else value
        try:
            with winreg.CreateKeyEx(self.hive, self.key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, name, 0, registry_type, stored_value)
        except PermissionError as error:
            raise RegistryUnavailableError(self._permission_message()) from error

    def delete_value(self, name: str) -> None:
        try:
            with winreg.OpenKey(self.hive, self.key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            return
        except PermissionError as error:
            raise RegistryUnavailableError(self._permission_message()) from error

    def _permission_message(self) -> str:
        return (
            f"Access denied writing {self.hive_name}\\{self.key_path}. "
            "On this PC the Policies key is read-only for the current user; "
            "run BraveTweaks as Administrator."
        )

    def create_backup(self, names: Iterable[str], metadata: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for name in names:
            current = self.read_value(name)
            if current is None:
                values[name] = {"exists": False}
            else:
                value, registry_type = current
                values[name] = {"exists": True, "value": value, "registry_type": registry_type}
        return {
            "format_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "hive": self.hive_name,
            "scope": self.scope,
            "key_path": self.key_path,
            "metadata": metadata,
            "values": values,
        }

    def validate_backup(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Backup file is not a BraveTweaks backup.")
        if payload.get("format_version") != 1:
            raise ValueError("Backup format is not supported.")
        if payload.get("hive") != self.hive_name or payload.get("scope") != self.scope:
            raise ValueError("Backup scope does not match the selected registry scope.")
        if payload.get("key_path") != self.key_path:
            raise ValueError("Backup key does not match the Brave policy key.")
        values = payload.get("values")
        if not isinstance(values, dict) or not values:
            raise ValueError("Backup does not contain any registry values.")
        for name, saved in values.items():
            if not isinstance(name, str) or not name:
                raise ValueError("Backup contains an invalid policy name.")
            if not isinstance(saved, dict):
                raise ValueError(f"Backup entry {name!r} is invalid.")
            if saved.get("exists") and "value" not in saved:
                raise ValueError(f"Backup entry {name!r} is missing a value.")
        return values

    def restore(self, payload: dict[str, Any]) -> None:
        values = self.validate_backup(payload)
        for name, saved in values.items():
            if saved.get("exists"):
                registry_type = saved.get("registry_type")
                if registry_type is not None and not isinstance(registry_type, int):
                    raise ValueError(
                        f"Backup entry {name!r} has an invalid registry type."
                    )
                self.set_value(name, saved["value"], registry_type)
            else:
                self.delete_value(name)
