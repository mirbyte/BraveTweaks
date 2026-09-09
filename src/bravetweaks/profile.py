from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .policies import PolicyDefinition
from .registry import RegistryStore


def version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.split("."):
        if not part.isdigit():
            break
        parts.append(int(part))
    return tuple(parts)


@dataclass(frozen=True)
class CurrentValue:
    value: Any
    registry_type: int


@dataclass(frozen=True)
class PlanItem:
    policy: PolicyDefinition
    current: CurrentValue | None
    action: str
    reason: str = ""
    registry_name: str = ""
    registry_value: Any = None


@dataclass(frozen=True)
class VerificationResult:
    policy: PolicyDefinition
    expected: Any
    actual: Any
    ok: bool


class OriginProfile:
    name = "origin"

    def __init__(self, policies: tuple[PolicyDefinition, ...] = ()) -> None:
        self.policies = policies

    @staticmethod
    def _current_value(
        store: RegistryStore,
        policy: PolicyDefinition,
    ) -> tuple[str, CurrentValue | None, Any]:
        current_raw = store.read_value(policy.name)
        if current_raw is not None:
            return policy.name, CurrentValue(*current_raw), policy.value
        for name, expected in policy.legacy_values:
            current_raw = store.read_value(name)
            if current_raw is not None:
                return name, CurrentValue(*current_raw), expected
        return policy.name, None, policy.value

    def plan(
        self,
        store: RegistryStore,
        brave_version: str | None = None,
        enabled_names: set[str] | None = None,
    ) -> list[PlanItem]:
        plan: list[PlanItem] = []
        for policy in self.policies:
            registry_name, current, registry_value = self._current_value(store, policy)
            if policy.min_version and brave_version and version_tuple(brave_version) < version_tuple(policy.min_version):
                plan.append(
                    PlanItem(
                        policy,
                        current,
                        "skip",
                        f"requires Brave {policy.min_version} or newer",
                        registry_name,
                        registry_value,
                    )
                )
                continue
            enabled = enabled_names is None or policy.name in enabled_names
            if not enabled:
                reason = "not selected"
                if current is None:
                    plan.append(
                        PlanItem(
                            policy,
                            None,
                            "skip",
                            reason,
                            registry_name,
                            registry_value,
                        )
                    )
                else:
                    plan.append(
                        PlanItem(
                            policy,
                            current,
                            "delete",
                            f"{reason}; current={current.value!r}",
                            registry_name,
                            registry_value,
                        )
                    )
                continue
            if current is not None and current.value == registry_value:
                plan.append(
                    PlanItem(
                        policy,
                        current,
                        "unchanged",
                        registry_name=registry_name,
                        registry_value=registry_value,
                    )
                )
            elif current is None:
                plan.append(
                    PlanItem(
                        policy,
                        None,
                        "set",
                        registry_name=registry_name,
                        registry_value=registry_value,
                    )
                )
            else:
                plan.append(
                    PlanItem(
                        policy,
                        current,
                        "update",
                        registry_name=registry_name,
                        registry_value=registry_value,
                    )
                )
        return plan

    def apply(self, store: RegistryStore, plan: list[PlanItem]) -> None:
        for item in plan:
            if item.action == "delete":
                store.delete_value(item.registry_name or item.policy.name)
            elif item.action in {"set", "update"}:
                store.set_value(
                    item.registry_name or item.policy.name,
                    item.registry_value
                    if item.registry_value is not None
                    else item.policy.value,
                )

    def verify(self, store: RegistryStore, plan: list[PlanItem]) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        for item in plan:
            if item.action == "skip":
                continue
            registry_name = item.registry_name or item.policy.name
            if item.action == "delete":
                current = store.read_value(registry_name)
                actual = current[0] if current is not None else None
                results.append(
                    VerificationResult(
                        item.policy,
                        None,
                        actual,
                        actual is None,
                    )
                )
                continue
            expected = (
                item.registry_value
                if item.registry_value is not None
                else item.policy.value
            )
            current = store.read_value(registry_name)
            actual = current[0] if current is not None else None
            results.append(
                VerificationResult(
                    item.policy,
                    expected,
                    actual,
                    actual == expected,
                )
            )
        return results
