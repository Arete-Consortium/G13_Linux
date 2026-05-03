"""
Joystick Settings Widget

UI for configuring G13 joystick behavior: analog vs digital mode,
deadzone, sensitivity, and directional key mappings.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class JoystickSettingsWidget(QWidget):
    """Widget for configuring joystick settings"""

    # Emitted when any setting changes
    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Choose how the thumbstick should behave. "
            "Use Button Mapper to set the STICK click action."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #888;")
        layout.addWidget(intro)

        # Mode selection
        mode_group = QGroupBox("Joystick Mode")
        mode_layout = QFormLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Analog (Virtual Gamepad)", "analog")
        self.mode_combo.addItem("Digital (Map to Keys)", "digital")
        self.mode_combo.addItem("Disabled", "disabled")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addRow("Mode:", self.mode_combo)

        # Mode description
        self.mode_desc = QLabel()
        self.mode_desc.setWordWrap(True)
        self.mode_desc.setStyleSheet("color: #888; font-style: italic;")
        mode_layout.addRow(self.mode_desc)

        layout.addWidget(mode_group)

        # Analog settings
        self.analog_group = QGroupBox("Analog Mode Settings")
        analog_layout = QFormLayout(self.analog_group)

        self.sensitivity_slider = QSlider()
        self.sensitivity_slider.setOrientation(Qt.Orientation.Horizontal)
        self.sensitivity_slider.setMinimum(50)
        self.sensitivity_slider.setMaximum(200)
        self.sensitivity_slider.setValue(100)
        self.sensitivity_slider.valueChanged.connect(self._on_setting_changed)

        sensitivity_row = QHBoxLayout()
        sensitivity_row.addWidget(self.sensitivity_slider)
        self.sensitivity_label = QLabel("100%")
        sensitivity_row.addWidget(self.sensitivity_label)
        analog_layout.addRow("Sensitivity:", sensitivity_row)

        layout.addWidget(self.analog_group)

        # Digital settings
        self.digital_group = QGroupBox("Digital Mode Settings")
        digital_layout = QFormLayout(self.digital_group)

        # Deadzone
        self.deadzone_spin = QSpinBox()
        self.deadzone_spin.setMinimum(5)
        self.deadzone_spin.setMaximum(127)
        self.deadzone_spin.setValue(20)
        self.deadzone_spin.setSuffix(" (0-127)")
        self.deadzone_spin.setToolTip(
            "How far the stick must move before a direction key is pressed."
        )
        self.deadzone_spin.valueChanged.connect(self._on_setting_changed)
        digital_layout.addRow("Deadzone:", self.deadzone_spin)

        # Key mappings
        self.key_up_combo = self._create_key_combo()
        self.key_down_combo = self._create_key_combo()
        self.key_left_combo = self._create_key_combo()
        self.key_right_combo = self._create_key_combo()
        self.key_up_combo.setToolTip("Key sent when pushing the stick up")
        self.key_down_combo.setToolTip("Key sent when pushing the stick down")
        self.key_left_combo.setToolTip("Key sent when pushing the stick left")
        self.key_right_combo.setToolTip("Key sent when pushing the stick right")

        digital_layout.addRow("Up:", self.key_up_combo)
        digital_layout.addRow("Down:", self.key_down_combo)
        digital_layout.addRow("Left:", self.key_left_combo)
        digital_layout.addRow("Right:", self.key_right_combo)

        # Diagonals checkbox would go here but using combo for simplicity
        self.diagonals_combo = QComboBox()
        self.diagonals_combo.addItem("8-way (Allow Diagonals)", True)
        self.diagonals_combo.addItem("4-way (No Diagonals)", False)
        self.diagonals_combo.setToolTip(
            "8-way can press two direction keys together. 4-way restricts to one direction."
        )
        self.diagonals_combo.currentIndexChanged.connect(self._on_setting_changed)
        digital_layout.addRow("Diagonals:", self.diagonals_combo)

        layout.addWidget(self.digital_group)

        # Current direction indicator
        self.direction_label = QLabel("Stick direction: center")
        self.direction_label.setStyleSheet("background: #333; padding: 8px; border-radius: 4px;")
        layout.addWidget(self.direction_label)

        layout.addStretch()

        # Initialize visibility
        self._update_mode_description()
        self._update_group_visibility()

    def _create_key_combo(self) -> QComboBox:
        """Create a key selection combo box"""
        combo = QComboBox()

        # Common keys
        common_keys = [
            ("Up Arrow", "KEY_UP"),
            ("Down Arrow", "KEY_DOWN"),
            ("Left Arrow", "KEY_LEFT"),
            ("Right Arrow", "KEY_RIGHT"),
            ("W", "KEY_W"),
            ("A", "KEY_A"),
            ("S", "KEY_S"),
            ("D", "KEY_D"),
            ("Space", "KEY_SPACE"),
            ("Shift", "KEY_LEFTSHIFT"),
            ("Ctrl", "KEY_LEFTCTRL"),
            ("Alt", "KEY_LEFTALT"),
            ("Tab", "KEY_TAB"),
            ("Escape", "KEY_ESC"),
            ("Enter", "KEY_ENTER"),
        ]

        for label, key in common_keys:
            combo.addItem(label, key)

        combo.currentIndexChanged.connect(self._on_setting_changed)
        return combo

    def _on_mode_changed(self, index: int):
        """Handle mode selection change"""
        self._update_mode_description()
        self._update_group_visibility()
        self._on_setting_changed()

    def _update_mode_description(self):
        """Update the mode description label"""
        mode = self.mode_combo.currentData()
        descriptions = {
            "analog": "Use this when a game supports controllers/joysticks directly.",
            "digital": "Use this to translate stick movement into keyboard keys (for example WASD or arrows).",
            "disabled": "Ignore stick movement. STICK click can still be mapped in Button Mapper.",
        }
        self.mode_desc.setText(descriptions.get(mode, ""))

    def _update_group_visibility(self):
        """Show/hide settings groups based on mode"""
        mode = self.mode_combo.currentData()
        self.analog_group.setVisible(mode == "analog")
        self.digital_group.setVisible(mode == "digital")

    def _on_setting_changed(self):
        """Emit config_changed when any setting changes"""
        config = self.get_config()
        self.config_changed.emit(config)

    def get_config(self) -> dict:
        """Get current configuration as dict"""
        return {
            "mode": self.mode_combo.currentData(),
            "deadzone": self.deadzone_spin.value(),
            "sensitivity": self.sensitivity_slider.value() / 100.0,
            "key_up": self.key_up_combo.currentData(),
            "key_down": self.key_down_combo.currentData(),
            "key_left": self.key_left_combo.currentData(),
            "key_right": self.key_right_combo.currentData(),
            "allow_diagonals": self.diagonals_combo.currentData(),
        }

    def set_config(self, config: dict):
        """Load configuration into widget"""
        # Block signals during update
        for widget in [
            self.mode_combo,
            self.deadzone_spin,
            self.sensitivity_slider,
            self.key_up_combo,
            self.key_down_combo,
            self.key_left_combo,
            self.key_right_combo,
            self.diagonals_combo,
        ]:
            widget.blockSignals(True)

        # Set mode
        mode = config.get("mode", "analog")
        index = self.mode_combo.findData(mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)

        # Set deadzone
        self.deadzone_spin.setValue(config.get("deadzone", 20))

        # Set sensitivity
        sensitivity = int(config.get("sensitivity", 1.0) * 100)
        self.sensitivity_slider.setValue(sensitivity)
        self.sensitivity_label.setText(f"{sensitivity}%")

        # Set key mappings
        for combo, key in [
            (self.key_up_combo, config.get("key_up", "KEY_UP")),
            (self.key_down_combo, config.get("key_down", "KEY_DOWN")),
            (self.key_left_combo, config.get("key_left", "KEY_LEFT")),
            (self.key_right_combo, config.get("key_right", "KEY_RIGHT")),
        ]:
            index = combo.findData(key)
            if index >= 0:
                combo.setCurrentIndex(index)

        # Set diagonals
        diagonals = config.get("allow_diagonals", True)
        index = self.diagonals_combo.findData(diagonals)
        if index >= 0:
            self.diagonals_combo.setCurrentIndex(index)

        # Unblock signals
        for widget in [
            self.mode_combo,
            self.deadzone_spin,
            self.sensitivity_slider,
            self.key_up_combo,
            self.key_down_combo,
            self.key_left_combo,
            self.key_right_combo,
            self.diagonals_combo,
        ]:
            widget.blockSignals(False)

        # Update UI
        self._update_mode_description()
        self._update_group_visibility()

    def update_direction(self, direction: str):
        """Update the direction indicator"""
        self.direction_label.setText(f"Stick direction: {direction}")

        # Color based on direction
        if direction == "center":
            color = "#333"
        else:
            color = "#2a5"  # Green when active
        self.direction_label.setStyleSheet(
            f"background: {color}; padding: 8px; border-radius: 4px;"
        )
