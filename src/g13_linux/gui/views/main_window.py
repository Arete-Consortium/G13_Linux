"""
Main Window

Primary application window for G13LogitechOPS GUI.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .app_profiles import AppProfilesWidget
from .button_mapper import ButtonMapperWidget
from .hardware_control import HardwareControlWidget
from .joystick_settings import JoystickSettingsWidget
from .live_monitor import LiveMonitorWidget
from .macro_editor import MacroEditorWidget
from .profile_manager import ProfileManagerWidget


class DeviceStatusBanner(QFrame):
    """Banner showing device connection status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("deviceStatusBanner")
        self._is_connected = False

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 10, 6)

        self.icon_label = QLabel("⚠")
        self.icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.icon_label)

        self.text_label = QLabel("G13 device not connected")
        self.text_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.text_label)

        layout.addStretch()

        self.hint_label = QLabel("Connect your G13 or run with sudo for button input")
        self.hint_label.setStyleSheet("font-size: 11px; color: #aaa;")
        layout.addWidget(self.hint_label)

        self.diagnostics_button = QPushButton("Run Diagnostics")
        self.diagnostics_button.setToolTip("Check hidraw/libusb detection and setup guidance.")
        self.diagnostics_button.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.diagnostics_button.setVisible(True)
        layout.addWidget(self.diagnostics_button)

        self.setLayout(layout)
        self._update_style()

    def set_connected(self, connected: bool, message: str = ""):
        """Update connection status."""
        self._is_connected = connected
        if connected:
            self.icon_label.setText("✓")
            self.text_label.setText(message or "G13 device connected")
            self.hint_label.setText("")
            self.diagnostics_button.setVisible(False)
        else:
            self.icon_label.setText("⚠")
            self.text_label.setText(message or "G13 device not connected")
            self.hint_label.setText(
                "Connect your G13, check udev/sudo setup, or run diagnostics for detailed checks."
            )
            self.diagnostics_button.setVisible(True)
        self._update_style()

    def _update_style(self):
        """Update banner style based on connection state."""
        if self._is_connected:
            self.setStyleSheet("""
                #deviceStatusBanner {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1a3a1a, stop:1 #0d2a0d);
                    border: 1px solid #2a5a2a;
                    border-radius: 4px;
                }
                #deviceStatusBanner QLabel {
                    color: #88ff88;
                }
            """)
        else:
            self.setStyleSheet("""
                #deviceStatusBanner {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3a2a1a, stop:1 #2a1a0d);
                    border: 1px solid #5a3a2a;
                    border-radius: 4px;
                }
                #deviceStatusBanner QLabel {
                    color: #ffaa55;
                }
            """)


class SessionSummaryBar(QFrame):
    """Compact summary of current profile/session state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sessionSummaryBar")

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(14)

        self.profile_label = QLabel("Profile: (none)")
        self.profile_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.profile_label)

        self.bindings_label = QLabel("Bound Buttons: 0")
        layout.addWidget(self.bindings_label)

        self.joystick_label = QLabel("Stick Mode: analog")
        layout.addWidget(self.joystick_label)

        layout.addStretch()
        self.setLayout(layout)
        self.setStyleSheet("""
            #sessionSummaryBar {
                background: #202328;
                border: 1px solid #2f3540;
                border-radius: 4px;
            }
            #sessionSummaryBar QLabel {
                color: #c8d0dd;
            }
        """)

    def set_summary(self, profile_name: str | None, bound_count: int, joystick_mode: str | None):
        """Update displayed session summary."""
        profile_display = profile_name if profile_name else "(none)"
        mode_display = joystick_mode if joystick_mode else "analog"

        self.profile_label.setText(f"Profile: {profile_display}")
        self.bindings_label.setText(f"Bound Buttons: {bound_count}")
        self.joystick_label.setText(f"Stick Mode: {mode_display}")


class MainWindow(QMainWindow):
    """Main application window"""

    diagnostics_requested = pyqtSignal()
    quick_setup_requested = pyqtSignal()

    _ADVANCED_TAB_NAMES = {"Macros", "Hardware", "Monitor"}
    _CORE_SCOPE_LABEL = "Core"
    _ALL_SCOPE_LABEL = "Core + Advanced"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("G13LogitechOPS - Configuration Tool")
        self.setMinimumSize(1200, 700)

        # Create widgets
        self.device_banner = DeviceStatusBanner()
        self.device_banner.diagnostics_button.clicked.connect(self.diagnostics_requested.emit)
        self.session_summary = SessionSummaryBar()
        self.button_mapper = ButtonMapperWidget()
        self.quick_setup_button = QPushButton("Quick Setup Wizard")
        self.quick_setup_button.clicked.connect(self.quick_setup_requested.emit)
        self.profile_widget = ProfileManagerWidget()
        self.monitor_widget = LiveMonitorWidget()
        self.hardware_widget = HardwareControlWidget()
        self.macro_widget = MacroEditorWidget()
        self.joystick_widget = JoystickSettingsWidget()
        self.tab_scope_selector = QComboBox()
        self.tab_hint_label = QLabel()
        self.app_profiles_widget: AppProfilesWidget | None = None  # Set by controller
        self._tabs: QTabWidget | None = None

        self._init_ui()

    def _init_ui(self):
        """Setup UI layout"""

        # Central widget with vertical layout
        central = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Device status banner at top
        main_layout.addWidget(self.device_banner)
        main_layout.addWidget(self.session_summary)

        # Main splitter (left/right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        # Left side: Button mapper
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        quick_help = QLabel(
            "Quick setup: click a G13 button to bind it. "
            "Right-click a bound button to clear it. Save the profile when done."
        )
        quick_help.setWordWrap(True)
        quick_help.setStyleSheet(
            "color: #aaa; padding: 4px 6px; background: #1f1f1f; border-radius: 4px;"
        )
        left_layout.addWidget(quick_help)

        self.quick_setup_button.setToolTip(
            "Guided setup for core keys (G1-G8). You can skip or stop at any step."
        )
        self.quick_setup_button.setStyleSheet("padding: 4px 10px;")
        left_layout.addWidget(self.quick_setup_button, alignment=Qt.AlignmentFlag.AlignLeft)
        left_layout.addWidget(self.button_mapper)
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # Right side: Tabs
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setUsesScrollButtons(True)
        self._tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self._tabs.addTab(self.profile_widget, "Profiles")
        self._tabs.addTab(self.joystick_widget, "Joystick")
        self._tabs.addTab(self.macro_widget, "Macros")
        self._tabs.addTab(self.hardware_widget, "Hardware")
        self._tabs.addTab(self.monitor_widget, "Monitor")
        self._set_tab_tooltips()
        self._tabs.currentChanged.connect(self._update_tab_hint)

        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        scope_row = QHBoxLayout()
        scope_row.setContentsMargins(0, 0, 0, 0)
        scope_row.setSpacing(6)
        scope_label = QLabel("Section:")
        scope_label.setStyleSheet("color: #9aa3b2;")
        self.tab_scope_selector.addItems([self._CORE_SCOPE_LABEL, self._ALL_SCOPE_LABEL])
        self.tab_scope_selector.setToolTip(
            "Core keeps daily setup tabs visible. Core + Advanced reveals macro, hardware, and monitor tools."
        )
        self.tab_scope_selector.currentTextChanged.connect(self._on_scope_changed)
        scope_row.addWidget(scope_label)
        scope_row.addWidget(self.tab_scope_selector)
        scope_row.addStretch()

        self.tab_hint_label.setWordWrap(True)
        self.tab_hint_label.setStyleSheet(
            "color: #9aa3b2; padding: 4px 6px; background: #1f1f1f; border-radius: 4px;"
        )
        right_layout.addLayout(scope_row)
        right_layout.addWidget(self.tab_hint_label)
        right_layout.addWidget(self._tabs)
        right_widget.setLayout(right_layout)
        self._apply_scope(self._CORE_SCOPE_LABEL)
        self._update_tab_hint()

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([840, 460])

        main_layout.addWidget(splitter, 1)  # Stretch factor 1

        central.setLayout(main_layout)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - No device connected")

        self.setCentralWidget(central)

    def set_status(self, message: str):
        """Update status bar message"""
        self.status_bar.showMessage(message)

    def set_device_connected(self, connected: bool, message: str = ""):
        """Update device connection status banner."""
        self.device_banner.set_connected(connected, message)

    def set_session_summary(
        self,
        profile_name: str | None,
        bound_count: int,
        joystick_mode: str | None = None,
    ):
        """Update top-level session summary values."""
        self.session_summary.set_summary(profile_name, bound_count, joystick_mode)

    def _set_tab_tooltips(self):
        """Set tooltips for right-panel tabs."""
        if not self._tabs:
            return

        tab_hints = {
            "Profiles": "Create, load, save, import, and export keybinding profiles.",
            "App Profiles": "Auto-switch profiles by active app window.",
            "Joystick": "Set thumbstick mode, deadzone, and direction key mappings.",
            "Macros": "Record and manage macro sequences.",
            "Hardware": "Adjust LCD text and backlight settings.",
            "Monitor": "View live button and joystick events.",
        }
        for index in range(self._tabs.count()):
            tab_name = self._tabs.tabText(index)
            hint = tab_hints.get(tab_name)
            if hint:
                self._tabs.setTabToolTip(index, hint)

    def _update_tab_hint(self, index: int | None = None):
        """Show contextual guidance for the active tab."""
        if not self._tabs:
            self.tab_hint_label.setText("")
            return

        if index is None:
            index = self._tabs.currentIndex()

        if index < 0 or index >= self._tabs.count():
            self.tab_hint_label.setText("")
            return

        tab_name = self._tabs.tabText(index)
        hint = self._tabs.tabToolTip(index) or f"Manage settings in the {tab_name} tab."
        if self.tab_scope_selector.currentText() == self._CORE_SCOPE_LABEL:
            hint = f"Core: {hint}"
        self.tab_hint_label.setText(hint)

    def _tab_index(self, tab_name: str) -> int:
        """Return index for a tab name, or -1 if not present."""
        if not self._tabs:
            return -1
        for index in range(self._tabs.count()):
            if self._tabs.tabText(index) == tab_name:
                return index
        return -1

    def _set_tab_visible(self, tab_name: str, visible: bool):
        """Set visibility for a tab by name."""
        if not self._tabs:
            return
        index = self._tab_index(tab_name)
        if index < 0:
            return

        if hasattr(self._tabs, "setTabVisible"):
            self._tabs.setTabVisible(index, visible)
        else:
            self._tabs.tabBar().setTabVisible(index, visible)

    def _apply_scope(self, scope_label: str):
        """Show core tabs only, or reveal advanced tabs."""
        show_advanced = scope_label == self._ALL_SCOPE_LABEL
        for tab_name in self._ADVANCED_TAB_NAMES:
            self._set_tab_visible(tab_name, show_advanced)

        if self._tabs:
            current_index = self._tabs.currentIndex()
            if current_index >= 0:
                current_name = self._tabs.tabText(current_index)
                if not show_advanced and current_name in self._ADVANCED_TAB_NAMES:
                    fallback_index = self._tab_index("Profiles")
                    if fallback_index >= 0:
                        self._tabs.setCurrentIndex(fallback_index)

    def _on_scope_changed(self, scope_label: str):
        """Handle section scope changes."""
        self._apply_scope(scope_label)
        self._update_tab_hint()

    def setup_app_profiles(self, rules_manager, profiles: list[str]):
        """Set up the app profiles widget with the rules manager.

        Called by ApplicationController after initialization.
        """

        self.app_profiles_widget = AppProfilesWidget(rules_manager, profiles)
        if self._tabs:
            # Insert after Profiles tab
            self._tabs.insertTab(1, self.app_profiles_widget, "App Profiles")
            self._set_tab_tooltips()
            self._apply_scope(self.tab_scope_selector.currentText())
            self._update_tab_hint(self._tabs.currentIndex())
