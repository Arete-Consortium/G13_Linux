"""App Profiles Widget for per-application profile switching.

Provides a UI to manage rules that map window patterns to G13 profiles.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models.app_profile_rules import AppProfileRule, AppProfileRulesManager
from ..models.window_monitor import WindowMonitorThread, get_active_window_info


class RuleEditDialog(QDialog):
    """Dialog for adding/editing an app profile rule."""

    def __init__(self, rule: AppProfileRule | None = None, profiles: list[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Rule" if rule else "Add Rule")
        self.setMinimumWidth(400)
        self.profiles = profiles or []

        layout = QVBoxLayout(self)

        # Form layout
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., EVE Online")
        form.addRow("Rule Name:", self.name_edit)

        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText("e.g., EVE - or firefox")
        form.addRow("Pattern (regex):", self.pattern_edit)

        self.match_type_combo = QComboBox()
        self.match_type_combo.addItems(["Window Name", "WM Class", "Both"])
        form.addRow("Match:", self.match_type_combo)

        self.profile_combo = QComboBox()
        self.profile_combo.addItems(self.profiles)
        self.profile_combo.setEditable(True)  # Allow typing new profile names
        form.addRow("Profile:", self.profile_combo)

        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        form.addRow("", self.enabled_check)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Populate if editing
        if rule:
            self.name_edit.setText(rule.name)
            self.pattern_edit.setText(rule.pattern)
            match_types = {"window_name": 0, "wm_class": 1, "both": 2}
            self.match_type_combo.setCurrentIndex(match_types.get(rule.match_type, 0))
            idx = self.profile_combo.findText(rule.profile_name)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
            else:
                self.profile_combo.setEditText(rule.profile_name)
            self.enabled_check.setChecked(rule.enabled)

    def get_rule(self) -> AppProfileRule | None:
        """Get the rule from dialog values."""
        name = self.name_edit.text().strip()
        pattern = self.pattern_edit.text().strip()
        profile = self.profile_combo.currentText().strip()

        if not name or not pattern or not profile:
            return None

        match_types = {0: "window_name", 1: "wm_class", 2: "both"}
        match_type = match_types.get(self.match_type_combo.currentIndex(), "window_name")

        return AppProfileRule(
            name=name,
            pattern=pattern,
            match_type=match_type,
            profile_name=profile,
            enabled=self.enabled_check.isChecked(),
        )


class AppProfilesWidget(QWidget):
    """Widget for managing per-application profile rules.

    Signals:
        enabled_changed(bool): Emitted when auto-switching is enabled/disabled
    """

    enabled_changed = pyqtSignal(bool)

    def __init__(
        self, rules_manager: AppProfileRulesManager, profiles: list[str] = None, parent=None
    ):
        super().__init__(parent)
        self.rules_manager = rules_manager
        self.profiles = profiles or []
        self.window_monitor = WindowMonitorThread()

        self._setup_ui()
        self._refresh_rules_list()

    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header with enable toggle
        header = QHBoxLayout()

        self.enabled_check = QCheckBox("Enable Auto Profile Switching")
        self.enabled_check.setChecked(self.rules_manager.enabled)
        self.enabled_check.toggled.connect(self._on_enabled_toggled)
        header.addWidget(self.enabled_check)

        header.addStretch()

        # Test button - shows current window info
        self.test_btn = QPushButton("Test Current Window")
        self.test_btn.clicked.connect(self._on_test_clicked)
        self.test_btn.setToolTip("Show current window fields and which rule would match")
        header.addWidget(self.test_btn)

        layout.addLayout(header)

        helper = QLabel("Rules run top-to-bottom. Keep specific app patterns above broader ones.")
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #888;")
        layout.addWidget(helper)

        # Status indicator
        self.status_label = QLabel()
        self._update_status()
        layout.addWidget(self.status_label)

        # Rules list
        rules_group = QGroupBox("Profile Rules (first match wins)")
        rules_layout = QVBoxLayout(rules_group)

        self.rules_list = QListWidget()
        self.rules_list.setMinimumHeight(200)
        self.rules_list.itemDoubleClicked.connect(self._on_edit_rule)
        self.rules_list.itemSelectionChanged.connect(self._update_rule_button_states)
        rules_layout.addWidget(self.rules_list)

        # Rule buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add Rule")
        self.add_btn.clicked.connect(self._on_add_rule)
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self._on_delete_rule)
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        self.move_up_btn = QPushButton("Move Up")
        self.move_up_btn.clicked.connect(self._on_move_up)
        btn_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("Move Down")
        self.move_down_btn.clicked.connect(self._on_move_down)
        btn_layout.addWidget(self.move_down_btn)

        rules_layout.addLayout(btn_layout)
        layout.addWidget(rules_group)

        # Default profile
        default_group = QGroupBox("Default Profile")
        default_layout = QHBoxLayout(default_group)

        self.default_combo = QComboBox()
        self.default_combo.addItem("(None - keep current)")
        self.default_combo.addItems(self.profiles)
        self.default_combo.currentTextChanged.connect(self._on_default_changed)

        # Set current default
        if self.rules_manager.default_profile:
            idx = self.default_combo.findText(self.rules_manager.default_profile)
            if idx >= 0:
                self.default_combo.setCurrentIndex(idx)

        default_layout.addWidget(QLabel("When no rule matches:"))
        default_layout.addWidget(self.default_combo, 1)
        layout.addWidget(default_group)

        layout.addStretch()
        self._update_rule_button_states()

    def _update_status(self):
        """Update the status label."""
        if not self.window_monitor.is_available:
            self.status_label.setText(
                "⚠️ Window monitoring not available (xdotool missing or Wayland)"
            )
            self.status_label.setStyleSheet("color: orange;")
            self.enabled_check.setEnabled(False)
        elif self.rules_manager.enabled:
            self.status_label.setText("✓ Auto profile switching is active")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText("Auto profile switching is disabled")
            self.status_label.setStyleSheet("color: gray;")

    def _refresh_rules_list(self):
        """Refresh the rules list widget."""
        self.rules_list.clear()
        for rule in self.rules_manager.rules:
            status = "✓" if rule.enabled else "○"
            item = QListWidgetItem(f"{status} {rule.name} → {rule.profile_name}")
            item.setToolTip(
                f"Pattern: {rule.pattern}\nMatch: {rule.match_type}\nEnabled: {rule.enabled}"
            )
            item.setData(Qt.ItemDataRole.UserRole, rule)
            if not rule.enabled:
                item.setForeground(Qt.GlobalColor.gray)
            self.rules_list.addItem(item)
        self._update_rule_button_states()

    def _update_rule_button_states(self):
        """Enable/disable rule action buttons based on current selection."""
        row = self.rules_list.currentRow()
        has_selection = row >= 0
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.move_up_btn.setEnabled(has_selection and row > 0)
        self.move_down_btn.setEnabled(has_selection and row < self.rules_list.count() - 1)

    def _on_enabled_toggled(self, enabled: bool):
        """Handle enable checkbox toggle."""
        self.rules_manager.enabled = enabled
        self._update_status()
        self.enabled_changed.emit(enabled)

    def _on_test_clicked(self):
        """Show current window info for testing rules."""
        info = get_active_window_info()
        if info:
            match = self.rules_manager.match(info.name, info.wm_class)
            match_text = f"→ Would switch to: {match}" if match else "→ No matching rule"
            QMessageBox.information(
                self,
                "Current Window",
                f"Window Name: {info.name}\n"
                f"WM Class: {info.wm_class}\n"
                f"Window ID: {info.window_id}\n\n"
                f"{match_text}",
            )
        else:
            QMessageBox.warning(
                self,
                "Window Detection",
                "Could not detect current window.\n\n"
                "Make sure xdotool is installed:\n"
                "sudo apt install xdotool",
            )

    def _on_add_rule(self):
        """Add a new rule."""
        dialog = RuleEditDialog(profiles=self.profiles, parent=self)
        if dialog.exec():
            rule = dialog.get_rule()
            if rule:
                self.rules_manager.add_rule(rule)
                self._refresh_rules_list()

    def _on_edit_clicked(self):
        """Edit selected rule."""
        item = self.rules_list.currentItem()
        if item:
            self._on_edit_rule(item)

    def _on_edit_rule(self, item: QListWidgetItem):
        """Edit a rule from double-click."""
        rule = item.data(Qt.ItemDataRole.UserRole)
        index = self.rules_list.row(item)

        dialog = RuleEditDialog(rule=rule, profiles=self.profiles, parent=self)
        if dialog.exec():
            new_rule = dialog.get_rule()
            if new_rule:
                self.rules_manager.update_rule(index, new_rule)
                self._refresh_rules_list()

    def _on_delete_rule(self):
        """Delete selected rule."""
        item = self.rules_list.currentItem()
        if item:
            reply = QMessageBox.question(
                self,
                "Delete Rule",
                f"Delete rule '{item.data(Qt.ItemDataRole.UserRole).name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                index = self.rules_list.row(item)
                self.rules_manager.remove_rule(index)
                self._refresh_rules_list()

    def _on_move_up(self):
        """Move selected rule up."""
        row = self.rules_list.currentRow()
        if row > 0:
            self.rules_manager.move_rule(row, row - 1)
            self._refresh_rules_list()
            self.rules_list.setCurrentRow(row - 1)

    def _on_move_down(self):
        """Move selected rule down."""
        row = self.rules_list.currentRow()
        if row < self.rules_list.count() - 1:
            self.rules_manager.move_rule(row, row + 1)
            self._refresh_rules_list()
            self.rules_list.setCurrentRow(row + 1)

    def _on_default_changed(self, text: str):
        """Handle default profile change."""
        if text == "(None - keep current)":
            self.rules_manager.default_profile = None
        else:
            self.rules_manager.default_profile = text

    def update_profiles(self, profiles: list[str]):
        """Update the available profiles list."""
        self.profiles = profiles

        # Update default combo
        current = self.default_combo.currentText()
        self.default_combo.clear()
        self.default_combo.addItem("(None - keep current)")
        self.default_combo.addItems(profiles)
        idx = self.default_combo.findText(current)
        if idx >= 0:
            self.default_combo.setCurrentIndex(idx)
