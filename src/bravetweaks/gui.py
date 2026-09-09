from __future__ import annotations

import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .brave import BraveDetector, BraveInstallation, target_browser
from .config import AppConfig
from .elevation import ensure_elevated
from .policies import CATEGORY_TITLES, PolicyDefinition, all_policies
from .profile import OriginProfile, PlanItem
from .registry import RegistryStore, RegistryUnavailableError

_ORIGIN_ONLY_MESSAGE = (
    "BraveTweaks applies Windows policies to regular Brave. "
    "Brave Origin is a separate product and is not a valid apply target."
)
_SHARED_HIVE_MESSAGE = (
    "Brave Origin is not the apply target, but it reads the same policy hive "
    "and will also show as managed."
)
_STYLE_SHEET = """
QMainWindow {
    background-color: #19191b;
}
QWidget {
    color: #f4f4f6;
}
QGroupBox {
    background-color: #2b2b2e;
    border: 1px solid #414146;
    border-radius: 6px;
    margin-top: 12px;
    padding: 12px 10px 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #ffffff;
}
QMessageBox {
    background-color: #2b2b2e;
}
QMessageBox QLabel {
    background-color: transparent;
}
QLabel, QCheckBox {
    background-color: transparent;
}
QLineEdit, QComboBox {
    background-color: #252527;
    color: #f4f4f6;
    border: 1px solid #414146;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: #5d5cf6;
}
QLineEdit:focus, QComboBox:focus {
    border: 2px solid #5d5cf6;
    padding: 5px 7px;
}
QPushButton {
    background-color: #2b2b2e;
    color: #f4f4f6;
    border: 1px solid #414146;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover {
    background-color: #3b3b40;
}
QPushButton:pressed {
    background-color: #252527;
}
QPushButton:focus {
    border: 2px solid #5d5cf6;
    padding: 6px 13px;
}
QPushButton:default {
    background-color: #5d5cf6;
    border-color: #7776ff;
    color: #ffffff;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    background-color: #252527;
    border: 1px solid #5f5f64;
    border-radius: 4px;
}
QCheckBox::indicator:hover {
    border-color: #7776ff;
}
QCheckBox::indicator:checked {
    background-color: #5d5cf6;
    border-color: #7776ff;
}
QCheckBox[pending="true"]::indicator {
    background-color: #6a5725;
    border-color: #d6ad4a;
}
QCheckBox[pending="true"]::indicator:checked {
    background-color: #d6ad4a;
    border-color: #f0d77a;
}
QAbstractScrollArea {
    border: none;
    background-color: #19191b;
}
QAbstractScrollArea::viewport {
    background-color: #19191b;
}
QWidget#policyViewport, QWidget#policyContent {
    background-color: #19191b;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #19191b;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #414146;
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
}
QScrollBar::handle:hover {
    background-color: #5f5f64;
}
QScrollBar::add-line, QScrollBar::sub-line {
    background: none;
    border: none;
}
QStatusBar {
    background-color: #19191b;
    color: #bdbdc4;
}
QToolTip {
    background-color: #2b2b2e;
    color: #f4f4f6;
    border: 1px solid #414146;
    padding: 4px;
}
"""


class BraveTweaksWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"BraveTweaks v{__version__}")
        self._toggles: dict[str, QCheckBox] = {}
        self._policy_tooltips: dict[str, str] = {}
        self._applied_states: dict[str, bool] = {}

        self.brave_path = QLineEdit()
        self.brave_path.setPlaceholderText("Leave blank to auto-detect Brave")
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_brave_path)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.brave_path)
        path_layout.addWidget(browse_button)

        self.scope = QComboBox()
        self.scope.addItem("User (HKCU)", "user")
        self.scope.addItem("Machine (HKLM)", "machine")
        self.scope.currentIndexChanged.connect(self._load_policy_state)

        target_box = QGroupBox("Target")
        target_form = QFormLayout(target_box)
        target_form.addRow("Detection path (optional)", path_layout)
        target_form.addRow("Registry scope", self.scope)

        preset_button = QPushButton("Brave Origin preset")
        preset_button.setToolTip(
            "Select Origin's default-off feature and telemetry policies. "
            "Nothing is written until you click Apply."
        )
        preset_button.clicked.connect(self.apply_origin_preset)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_selection)

        detect_button = QPushButton("Detect Brave")
        detect_button.clicked.connect(self.detect_brave)
        remove_button = QPushButton("Remove managed policies")
        remove_button.setToolTip(
            "Remove known BraveTweaks policy values from the selected registry scope. "
            "Unknown values are left untouched."
        )
        remove_button.clicked.connect(self.remove_managed_policies)
        apply_button = QPushButton("Apply policy state")
        apply_button.setDefault(True)
        apply_button.setToolTip(
            "Apply the checked policy state. If none are checked, reset managed policies."
        )
        apply_button.clicked.connect(self.apply_profile)
        verify_button = QPushButton("Verify")
        verify_button.clicked.connect(self.verify_profile)
        restore_button = QPushButton("Restore Backup")
        restore_button.clicked.connect(self.restore_backup)

        actions = QHBoxLayout()
        actions.addWidget(detect_button)
        actions.addWidget(remove_button)
        actions.addStretch()
        actions.addWidget(verify_button)
        actions.addWidget(restore_button)
        actions.addWidget(apply_button)

        self.policy_scroll = self._build_policy_toggles()
        layout = QVBoxLayout()
        layout.addWidget(target_box)
        policy_header = QHBoxLayout()
        policy_header.addWidget(QLabel("Policies"))
        self.selection_label = QLabel()
        policy_header.addWidget(self.selection_label)
        policy_header.addStretch()
        policy_header.addWidget(preset_button)
        policy_header.addWidget(clear_button)
        layout.addLayout(policy_header)
        layout.addWidget(self.policy_scroll, 1)
        layout.addLayout(actions)

        container = QWidget()
        container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        container.setLayout(layout)
        self.setCentralWidget(container)
        self._load_policy_state()
        self._fit_window_to_screen()

    def _build_policy_toggles(self) -> QWidget:
        grouped: dict[str, list[PolicyDefinition]] = {}
        for policy in all_policies():
            grouped.setdefault(policy.category, []).append(policy)

        inner = QGridLayout()
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setHorizontalSpacing(12)
        inner.setVerticalSpacing(12)
        row = 0
        column = 0
        for category in CATEGORY_TITLES:
            policies = grouped.get(category)
            if not policies:
                continue
            box = QGroupBox(CATEGORY_TITLES[category])
            box_layout = QGridLayout()
            box_layout.setContentsMargins(12, 8, 12, 8)
            box_layout.setColumnStretch(0, 1)
            box_layout.setColumnStretch(1, 1)
            box_layout.setVerticalSpacing(8)
            for index, policy in enumerate(policies):
                checkbox = QCheckBox(policy.label)
                checkbox.setSizePolicy(
                    QSizePolicy.Policy.Ignored,
                    QSizePolicy.Policy.Fixed,
                )
                checkbox.setChecked(False)
                description = textwrap.fill(policy.description, width=64)
                tooltip = (
                    f"{description}\n\n"
                    f"Policy: {policy.name}\n"
                    f"Value: {policy.value!r}"
                )
                checkbox.setToolTip(tooltip)
                checkbox.stateChanged.connect(self._update_selection_count)
                self._toggles[policy.name] = checkbox
                self._policy_tooltips[policy.name] = tooltip
                if category == "hardening":
                    box_layout.addWidget(checkbox, index, 0)
                else:
                    box_layout.addWidget(checkbox, index // 2, index % 2)
            box.setLayout(box_layout)
            if category in {"features", "hardening"}:
                inner.addWidget(box, row, 0, 1, 2)
                row += 1
            else:
                inner.addWidget(box, row, column)
                column += 1
                if column == 2:
                    row += 1
                    column = 0
        inner.setRowStretch(row, 1)

        content = QWidget()
        content.setObjectName("policyContent")
        content.setLayout(inner)
        scroll = QScrollArea()
        scroll.viewport().setObjectName("policyViewport")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        scroll.setMinimumHeight(content.sizeHint().height())
        return scroll

    def _fit_window_to_screen(self, *_args: object) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        max_width = max(1, available.width() - 32)
        max_height = max(1, available.height() - 32)

        self.policy_scroll.setMinimumHeight(
            self.policy_scroll.widget().sizeHint().height()
        )
        self.adjustSize()
        desired_size = self.sizeHint()
        height = min(desired_size.height(), max_height)
        if height < desired_size.height():
            self.policy_scroll.setMinimumHeight(0)

        minimum_width = min(self.minimumSizeHint().width(), max_width)
        width = max(minimum_width, min(900, max_width))
        self.setMinimumWidth(minimum_width)
        self.setFixedHeight(height)
        self.resize(width, height)

    def _update_selection_count(self, _state: int = 0) -> None:
        selected = sum(checkbox.isChecked() for checkbox in self._toggles.values())
        self.selection_label.setText(f"{selected} of {len(self._toggles)} selected")
        for name, checkbox in self._toggles.items():
            pending = (
                name in self._applied_states
                and checkbox.isChecked() != self._applied_states[name]
            )
            checkbox.setProperty("pending", "true" if pending else "false")
            checkbox.style().unpolish(checkbox)
            checkbox.style().polish(checkbox)
            checkbox.setToolTip(
                f"{self._policy_tooltips[name]}\n\n"
                "Status: this change has not been applied yet."
                if pending
                else self._policy_tooltips[name]
            )

    def _load_policy_state(self, _index: int = 0) -> None:
        scope = self.scope.currentData()
        try:
            store = RegistryStore(scope=scope)
        except (OSError, ValueError, RegistryUnavailableError) as error:
            self.statusBar().showMessage(str(error))
            return

        applied_states: dict[str, bool] = {}
        for policy in all_policies():
            _registry_name, current, registry_value = OriginProfile._current_value(
                store,
                policy,
            )
            checkbox = self._toggles[policy.name]
            applied = current is not None and current.value == registry_value
            applied_states[policy.name] = applied
            checkbox.setChecked(applied)
        self._applied_states = applied_states
        self._update_selection_count()
        selected = sum(checkbox.isChecked() for checkbox in self._toggles.values())
        self.statusBar().showMessage(
            f"Loaded {selected} active policies from {self._scope_label(scope)}."
        )

    def apply_origin_preset(self) -> None:
        by_name = {policy.name: policy for policy in all_policies()}
        for name, checkbox in self._toggles.items():
            checkbox.setChecked(by_name[name].origin_preset)
        self.statusBar().showMessage("Origin preset selected. Apply to write registry values.")

    def clear_selection(self) -> None:
        for checkbox in self._toggles.values():
            checkbox.setChecked(False)
        self.statusBar().showMessage("No policies selected.")

    def _selected_policies(self) -> tuple[PolicyDefinition, ...]:
        selected = []
        for policy in all_policies():
            checkbox = self._toggles.get(policy.name)
            if checkbox is not None and checkbox.isChecked():
                selected.append(policy)
        return tuple(selected)

    def browse_brave_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select brave.exe",
            "",
            "Brave executable (brave.exe);;All files (*)",
        )
        if path:
            self.brave_path.setText(path)

    def detect_brave(self) -> None:
        self._run("Detecting Brave installations", self._detect_brave)

    def apply_profile(self) -> None:
        self._run("Applying profile", self._apply_profile)

    def verify_profile(self) -> None:
        self._run("Verifying profile", self._verify_profile)

    def restore_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select BraveTweaks backup",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        self._run("Restoring backup", lambda: self._restore_backup(Path(path)))

    def _run(self, status: str, operation: Callable[[], None]) -> None:
        self.statusBar().showMessage(status)
        try:
            operation()
        except (OSError, ValueError, json.JSONDecodeError, RegistryUnavailableError) as error:
            self.statusBar().showMessage("Operation failed")
            QMessageBox.critical(self, "Operation failed", str(error))

    def _show_message(
        self,
        title: str,
        text: str,
        *,
        icon: QMessageBox.Icon = QMessageBox.Icon.Information,
        details: str | None = None,
    ) -> None:
        message = QMessageBox(self)
        if icon == QMessageBox.Icon.Information:
            information_icon = message.style().standardIcon(
                QStyle.StandardPixmap.SP_MessageBoxInformation
            )
            message.setIconPixmap(information_icon.pixmap(32, 32))
        else:
            message.setIcon(icon)
        message.setWindowTitle(title)
        message.setText(text)
        if details:
            message.setDetailedText(details)
        message.setStandardButtons(QMessageBox.StandardButton.Ok)
        message.exec()

    def _custom_path(self) -> Path | None:
        text = self.brave_path.text().strip()
        return Path(text) if text else None

    def _detect(
        self,
        *,
        show_details: bool = False,
    ) -> tuple[list[BraveInstallation], BraveInstallation | None]:
        detector = BraveDetector()
        installations = detector.detect(
            custom_path=self._custom_path(),
            probe_version=True,
        )
        browser = target_browser(installations)
        lines = ["Detected Brave installations:"]
        if not installations:
            lines.append("  None")
            if show_details:
                self._show_message(
                    "Brave detection",
                    "No Brave installations were found.",
                    details="\n".join(lines),
                )
            return installations, None

        origin_present = False
        for installation in installations:
            version = installation.version or "version not detected"
            label = installation.product_name or installation.product
            if installation.is_origin:
                origin_present = True
            lines.append(
                f"  {label} {version} ({installation.source}): "
                f"{installation.executable}"
            )
        if origin_present and browser is None:
            lines.append(_ORIGIN_ONLY_MESSAGE)
        elif origin_present:
            lines.append(_SHARED_HIVE_MESSAGE)
        if show_details:
            if browser is None:
                text = "Brave Origin was found, but regular Brave was not found."
                icon = QMessageBox.Icon.Warning
            else:
                text = f"Detected {len(installations)} Brave installation(s)."
                icon = QMessageBox.Icon.Information
            self._show_message(
                "Brave detection",
                text,
                icon=icon,
                details="\n".join(lines),
            )
        return installations, browser

    def _detect_brave(self) -> None:
        self._detect(show_details=True)
        self.statusBar().showMessage("Detection complete")

    def _profile_context(
        self,
    ) -> tuple[OriginProfile, RegistryStore, BraveInstallation | None, bool]:
        installations, browser = self._detect()
        store = RegistryStore(scope=self.scope.currentData())
        profile = OriginProfile(all_policies())
        origin_present = any(item.is_origin for item in installations)
        return profile, store, browser, origin_present

    @staticmethod
    def _plan_lines(plan: list[PlanItem]) -> list[str]:
        lines = []
        for item in plan:
            detail = item.reason or (
                f"current={item.current.value if item.current else None!r}"
            )
            registry_name = item.registry_name or item.policy.name
            registry_value = (
                item.registry_value
                if item.registry_value is not None
                else item.policy.value
            )
            label = (
                item.policy.name
                if registry_name == item.policy.name
                else f"{item.policy.name} ({registry_name})"
            )
            lines.append(
                f"[{item.action.upper()}] {label} = "
                f"{registry_value!r} ({detail})"
            )
        return lines

    @staticmethod
    def _scope_label(scope: str) -> str:
        return "User (HKCU)" if scope == "user" else "Machine (HKLM)"

    @staticmethod
    def _known_policy_names() -> set[str]:
        return {
            name
            for policy in all_policies()
            for name in (policy.name, *(name for name, _expected in policy.legacy_values))
        }

    def _alternate_scope_values(
        self,
        scope: str,
    ) -> tuple[str, list[str], list[str]]:
        alternate_scope = "machine" if scope == "user" else "user"
        alternate_store = RegistryStore(scope=alternate_scope)
        known_names = self._known_policy_names()
        managed = []
        unmanaged = []
        for name, (value, _registry_type) in sorted(alternate_store.read_values().items()):
            line = f"{name}={value!r}"
            (managed if name in known_names else unmanaged).append(line)
        return alternate_scope, managed, unmanaged

    @staticmethod
    def _scope_value_details(
        scope_label: str,
        managed: list[str],
        unmanaged: list[str],
    ) -> str:
        lines = [f"Existing values in {scope_label}:"]
        if managed:
            lines.append("  Known BraveTweaks policies:")
            lines.extend(f"    {value}" for value in managed)
        if unmanaged:
            lines.append("  Unmanaged values left untouched:")
            lines.extend(f"    {value}" for value in unmanaged)
        return "\n".join(lines)

    def remove_managed_policies(self) -> None:
        self._run("Removing managed policies", self._remove_managed_policies)

    def _remove_managed_policies(self) -> None:
        scope = self.scope.currentData()
        store = RegistryStore(scope=scope)
        values = store.read_values()
        known_names = self._known_policy_names()
        managed = [
            f"{name}={value!r}"
            for name, (value, _registry_type) in sorted(values.items())
            if name in known_names
        ]
        unmanaged = [
            f"{name}={value!r}"
            for name, (value, _registry_type) in sorted(values.items())
            if name not in known_names
        ]
        scope_label = self._scope_label(scope)
        if not managed:
            self._show_message(
                "No managed policies",
                f"No known BraveTweaks policies were found in {scope_label}.",
                details=self._scope_value_details(scope_label, [], unmanaged)
                if unmanaged
                else None,
            )
            self.statusBar().showMessage("No managed policies found")
            return

        confirmation = QMessageBox(self)
        confirmation.setIcon(QMessageBox.Icon.Question)
        confirmation.setWindowTitle("Remove managed policies")
        confirmation.setText(
            f"Remove {len(managed)} known policy value(s) from {scope_label}?"
        )
        confirmation.setDetailedText(
            self._scope_value_details(scope_label, managed, unmanaged)
        )
        confirmation.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirmation.exec() != QMessageBox.StandardButton.Yes:
            self.statusBar().showMessage("Policy removal cancelled")
            return

        names = [
            name
            for name in sorted(values)
            if name in known_names
        ]
        config = AppConfig(scope=scope)
        backup = store.create_backup(
            names,
            metadata={
                "operation": "remove_managed_policies",
                "scope": scope,
                "removed": names,
            },
        )
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
        backup_path = config.backup_dir / f"cleanup-{timestamp}.json"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(json.dumps(backup, indent=2), encoding="utf-8")
        for name in names:
            store.delete_value(name)
        self._load_policy_state()
        self._show_message(
            "Policies removed",
            f"Removed {len(names)} policy value(s) from {scope_label}.",
            details=f"Backup written to {backup_path}",
        )
        self.statusBar().showMessage("Managed policies removed")

    def _apply_profile(self) -> None:
        if not self._selected_policies():
            self._remove_managed_policies()
            return

        profile, store, browser, origin_present = self._profile_context()
        if browser is None and origin_present:
            QMessageBox.warning(self, "Regular Brave not found", _ORIGIN_ONLY_MESSAGE)
            self.statusBar().showMessage("Apply blocked")
            return

        brave_version = browser.version if browser else None
        selected_names = {policy.name for policy in self._selected_policies()}
        plan = profile.plan(
            store,
            brave_version=brave_version,
            enabled_names=selected_names,
        )
        plan_details = "\n".join(self._plan_lines(plan))

        changed = [
            item for item in plan if item.action in {"set", "update", "delete"}
        ]
        if not changed:
            self._show_message(
                "No changes needed",
                "The selected policies already match the requested values.",
                details=plan_details,
            )
            self.statusBar().showMessage("No changes needed")
            return

        alternate_scope, managed_values, unmanaged_values = self._alternate_scope_values(
            store.scope,
        )
        config = AppConfig(scope=self.scope.currentData())
        backup = store.create_backup(
            [
                item.registry_name or item.policy.name
                for item in plan
                if item.action != "skip"
            ],
            metadata={
                "profile": profile.name,
                "brave_version": brave_version,
                "selected": sorted(selected_names),
            },
        )
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
        backup_path = config.backup_dir / f"origin-{timestamp}.json"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(json.dumps(backup, indent=2), encoding="utf-8")
        profile.apply(store, plan)
        self._load_policy_state()

        if browser is None:
            text = "Selected policies staged for a future Brave install."
        else:
            text = "Selected policies applied. Restart Brave before checking behavior."
        if origin_present:
            text += " Brave Origin reads the same policy hive and will also show as managed."
        details = f"{plan_details}\n\nBackup written to {backup_path}"
        if managed_values or unmanaged_values:
            details += "\n\n" + self._scope_value_details(
                self._scope_label(alternate_scope),
                managed_values,
                unmanaged_values,
            )
        self._show_message("Profile applied", text, details=details)
        self.statusBar().showMessage("Profile applied")

    def _verify_profile(self) -> None:
        profile, store, browser, _origin_present = self._profile_context()
        selected_names = {policy.name for policy in self._selected_policies()}
        plan = profile.plan(
            store,
            brave_version=browser.version if browser else None,
            enabled_names=selected_names,
        )
        results = profile.verify(store, plan)
        lines = []
        for result in results:
            state = "OK" if result.ok else "MISMATCH"
            lines.append(
                f"[{state}] {result.policy.name}: "
                f"expected {result.expected!r}, actual {result.actual!r}"
            )
        alternate_scope, managed_values, unmanaged_values = (
            self._alternate_scope_values(store.scope)
        )
        details = "\n".join(lines) or None
        if managed_values or unmanaged_values:
            alternate_label = self._scope_label(alternate_scope)
            scope_details = self._scope_value_details(
                alternate_label,
                managed_values,
                unmanaged_values,
            )
            details = f"{details}\n\n{scope_details}" if details else scope_details
        mismatches = sum(not result.ok for result in results)
        if mismatches:
            text = f"Verification found {mismatches} mismatch(es)."
            icon = QMessageBox.Icon.Warning
        elif results:
            text = "Verification complete. All selected policies match."
            icon = QMessageBox.Icon.Information
        else:
            text = "No policies to verify."
            icon = QMessageBox.Icon.Information
        if managed_values or unmanaged_values:
            text += f" Values also exist in {self._scope_label(alternate_scope)}."
        self._show_message(
            "Verify profile",
            text,
            icon=icon,
            details=details,
        )
        self.statusBar().showMessage(
            "No policies to verify"
            if not results
            else (
                "Verification complete"
                if all(result.ok for result in results)
                else "Verification found mismatches"
            )
        )

    def _restore_backup(self, path: Path) -> None:
        store = RegistryStore(scope=self.scope.currentData())
        payload = json.loads(path.read_text(encoding="utf-8"))
        store.restore(payload)
        self._load_policy_state()
        self._show_message("Backup restored", f"Restored registry values from {path}")
        self.statusBar().showMessage("Backup restored")


def launch() -> int:
    if not ensure_elevated():
        return 1

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(_STYLE_SHEET)
    window = BraveTweaksWindow()
    window.show()
    QTimer.singleShot(0, window.centralWidget().setFocus)
    handle = window.windowHandle()
    if handle is not None:
        handle.screenChanged.connect(window._fit_window_to_screen)
        screen = handle.screen()
        if screen is not None:
            screen.availableGeometryChanged.connect(window._fit_window_to_screen)
            screen.logicalDotsPerInchChanged.connect(window._fit_window_to_screen)
    return app.exec()
