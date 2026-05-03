"""Tests for GUI view widgets."""

from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication


def _tab_visible(tab_widget, index: int) -> bool:
    """Qt compatibility helper for tab visibility checks."""
    if hasattr(tab_widget, "isTabVisible"):
        return tab_widget.isTabVisible(index)
    return tab_widget.tabBar().isTabVisible(index)


# Ensure QApplication exists for widget tests
@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestMainWindow:
    """Tests for MainWindow."""

    def test_init(self, qapp):
        """Test MainWindow initialization."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()

        assert window.windowTitle() == "G13LogitechOPS - Configuration Tool"
        assert window.minimumWidth() >= 1200
        assert window.minimumHeight() >= 700

    def test_has_widgets(self, qapp):
        """Test MainWindow has all required widgets."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()

        assert window.button_mapper is not None
        assert window.profile_widget is not None
        assert window.monitor_widget is not None
        assert window.hardware_widget is not None
        assert window.macro_widget is not None
        assert window.session_summary is not None
        assert window.tab_hint_label is not None
        assert window.quick_setup_button is not None

    def test_has_status_bar(self, qapp):
        """Test MainWindow has status bar."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()

        assert window.status_bar is not None
        assert window.statusBar() == window.status_bar

    def test_set_status(self, qapp):
        """Test set_status updates status bar."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()
        window.set_status("Test message")

        assert window.status_bar.currentMessage() == "Test message"

    def test_set_session_summary(self, qapp):
        """Test session summary values are updated."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()
        window.set_session_summary("eve", 12, "digital")

        assert "eve" in window.session_summary.profile_label.text()
        assert "12" in window.session_summary.bindings_label.text()
        assert "digital" in window.session_summary.joystick_label.text()

    def test_diagnostics_button_visibility_tracks_connection(self, qapp):
        """Diagnostics button should hide on connect and show on disconnect."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()
        # Use hidden-state instead of isVisible(): top-level window is not shown in tests.
        assert window.device_banner.diagnostics_button.isHidden() is False

        window.set_device_connected(True, "Connected")
        assert window.device_banner.diagnostics_button.isHidden() is True

        window.set_device_connected(False, "Disconnected")
        assert window.device_banner.diagnostics_button.isHidden() is False

    def test_diagnostics_button_emits_main_window_signal(self, qapp):
        """Clicking diagnostics button should emit diagnostics_requested signal."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()
        received = []
        window.diagnostics_requested.connect(lambda: received.append(True))

        window.device_banner.diagnostics_button.click()

        assert received == [True]

    def test_quick_setup_button_emits_main_window_signal(self, qapp):
        """Clicking quick setup button should emit quick_setup_requested signal."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()
        received = []
        window.quick_setup_requested.connect(lambda: received.append(True))

        window.quick_setup_button.click()

        assert received == [True]

    def test_tab_hint_updates_for_selected_tab(self, qapp):
        """Test tab hint reflects the current selected tab."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()

        # Default tab hint should be populated
        assert len(window.tab_hint_label.text()) > 0

        # Select a different tab and ensure hint updates
        window.tab_scope_selector.setCurrentText("Core + Advanced")
        monitor_index = window._tabs.indexOf(window.monitor_widget)
        window._tabs.setCurrentIndex(monitor_index)
        assert "live button" in window.tab_hint_label.text().lower()

    def test_core_scope_hides_advanced_tabs_by_default(self, qapp):
        """Test core scope hides advanced tabs on startup."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()

        macros_idx = window._tabs.indexOf(window.macro_widget)
        hardware_idx = window._tabs.indexOf(window.hardware_widget)
        monitor_idx = window._tabs.indexOf(window.monitor_widget)

        assert window.tab_scope_selector.currentText() == "Core"
        assert _tab_visible(window._tabs, macros_idx) is False
        assert _tab_visible(window._tabs, hardware_idx) is False
        assert _tab_visible(window._tabs, monitor_idx) is False

    def test_scope_toggle_reveals_advanced_tabs(self, qapp):
        """Test switching to full scope reveals advanced tabs."""
        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()
        window.tab_scope_selector.setCurrentText("Core + Advanced")

        macros_idx = window._tabs.indexOf(window.macro_widget)
        hardware_idx = window._tabs.indexOf(window.hardware_widget)
        monitor_idx = window._tabs.indexOf(window.monitor_widget)

        assert _tab_visible(window._tabs, macros_idx) is True
        assert _tab_visible(window._tabs, hardware_idx) is True
        assert _tab_visible(window._tabs, monitor_idx) is True

    def test_setup_app_profiles(self, qapp):
        """Test setup_app_profiles adds widget and tab."""
        from unittest.mock import MagicMock

        from PyQt6.QtWidgets import QWidget

        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()
        mock_rules_manager = MagicMock()
        profiles = ["profile1", "profile2"]

        # Initially no app_profiles_widget
        assert window.app_profiles_widget is None

        with patch("g13_linux.gui.views.main_window.AppProfilesWidget") as mock_widget_cls:
            # Use a real QWidget to satisfy Qt's type checking
            real_widget = QWidget()
            mock_widget_cls.return_value = real_widget

            window.setup_app_profiles(mock_rules_manager, profiles)

            mock_widget_cls.assert_called_once_with(mock_rules_manager, profiles)
            assert window.app_profiles_widget == real_widget

    def test_setup_app_profiles_inserts_tab(self, qapp):
        """Test setup_app_profiles inserts tab at correct position."""
        from unittest.mock import MagicMock

        from PyQt6.QtWidgets import QWidget

        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()
        mock_rules_manager = MagicMock()

        # Count tabs before
        initial_tab_count = window._tabs.count()

        with patch("g13_linux.gui.views.main_window.AppProfilesWidget") as mock_widget_cls:
            real_widget = QWidget()
            mock_widget_cls.return_value = real_widget

            window.setup_app_profiles(mock_rules_manager, [])

            # Tab should be inserted
            assert window._tabs.count() == initial_tab_count + 1
            # Tab should be at index 1 (after Profiles)
            assert window._tabs.tabText(1) == "App Profiles"

    def test_setup_app_profiles_no_tabs(self, qapp):
        """Test setup_app_profiles handles missing _tabs gracefully."""
        from unittest.mock import MagicMock

        from PyQt6.QtWidgets import QWidget

        from g13_linux.gui.views.main_window import MainWindow

        window = MainWindow()
        window._tabs = None  # Simulate missing tabs
        mock_rules_manager = MagicMock()

        with patch("g13_linux.gui.views.main_window.AppProfilesWidget") as mock_widget_cls:
            real_widget = QWidget()
            mock_widget_cls.return_value = real_widget

            # Should not raise
            window.setup_app_profiles(mock_rules_manager, [])

            # Widget should still be set
            assert window.app_profiles_widget == real_widget


class TestLiveMonitorWidget:
    """Tests for LiveMonitorWidget."""

    def test_init(self, qapp):
        """Test LiveMonitorWidget initialization."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()

        assert widget.max_lines == 1000
        assert widget.event_log is not None
        assert widget.show_raw is not None
        assert widget.show_decoded is not None

    def test_show_decoded_checked_by_default(self, qapp):
        """Test show_decoded is checked by default."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()

        assert widget.show_decoded.isChecked() is True
        assert widget.show_raw.isChecked() is False

    def test_on_raw_event_when_enabled(self, qapp):
        """Test on_raw_event displays when show_raw is checked."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()
        widget.show_raw.setChecked(True)

        widget.on_raw_event(b"\x01\x02\x03")

        assert "RAW: 01 02 03" in widget.event_log.toPlainText()

    def test_on_raw_event_when_disabled(self, qapp):
        """Test on_raw_event does not display when show_raw is unchecked."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()
        widget.show_raw.setChecked(False)

        widget.on_raw_event(b"\x01\x02\x03")

        assert widget.event_log.toPlainText() == ""

    def test_on_button_event_pressed(self, qapp):
        """Test on_button_event displays pressed state."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()

        widget.on_button_event("G1", True)

        assert "G1: PRESSED" in widget.event_log.toPlainText()

    def test_on_button_event_released(self, qapp):
        """Test on_button_event displays released state."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()

        widget.on_button_event("G1", False)

        assert "G1: RELEASED" in widget.event_log.toPlainText()

    def test_on_button_event_when_disabled(self, qapp):
        """Test on_button_event does not display when show_decoded is unchecked."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()
        widget.show_decoded.setChecked(False)

        widget.on_button_event("G1", True)

        assert widget.event_log.toPlainText() == ""

    def test_on_joystick_event(self, qapp):
        """Test on_joystick_event displays coordinates."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()

        widget.on_joystick_event(150, 100)

        assert "JOYSTICK: X=150, Y=100" in widget.event_log.toPlainText()

    def test_on_joystick_event_when_disabled(self, qapp):
        """Test on_joystick_event does not display when show_decoded is unchecked."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()
        widget.show_decoded.setChecked(False)

        widget.on_joystick_event(150, 100)

        assert widget.event_log.toPlainText() == ""

    def test_append_log(self, qapp):
        """Test append_log adds message."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()

        widget.append_log("Test message")

        assert "Test message" in widget.event_log.toPlainText()

    def test_append_log_limits_lines(self, qapp):
        """Test append_log limits lines to max_lines."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()
        widget.max_lines = 10

        for i in range(20):
            widget.append_log(f"Line {i}")

        lines = widget.event_log.toPlainText().strip().split("\n")
        assert len(lines) <= 10

    def test_clear_log(self, qapp):
        """Test clear_log clears the event log."""
        from g13_linux.gui.views.live_monitor import LiveMonitorWidget

        widget = LiveMonitorWidget()
        widget.append_log("Some message")
        assert widget.event_log.toPlainText() != ""

        widget.clear_log()

        assert widget.event_log.toPlainText() == ""


class TestHardwareControlWidget:
    """Tests for HardwareControlWidget."""

    def test_init(self, qapp):
        """Test HardwareControlWidget initialization."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()

        assert widget.lcd_text is not None
        assert widget.brightness_slider is not None
        assert widget.brightness_value is not None

    def test_has_signals(self, qapp):
        """Test HardwareControlWidget has required signals."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()

        assert hasattr(widget, "lcd_text_changed")
        assert hasattr(widget, "backlight_color_changed")
        assert hasattr(widget, "backlight_brightness_changed")

    def test_brightness_slider_range(self, qapp):
        """Test brightness slider has correct range."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()

        assert widget.brightness_slider.minimum() == 0
        assert widget.brightness_slider.maximum() == 100
        assert widget.brightness_slider.value() == 100

    def test_brightness_slider_updates_label(self, qapp):
        """Test brightness slider updates label."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        widget.brightness_slider.setValue(50)

        assert widget.brightness_value.text() == "50%"

    def test_brightness_changed_signal(self, qapp):
        """Test brightness slider emits signal."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        received = []
        widget.backlight_brightness_changed.connect(lambda v: received.append(v))

        widget.brightness_slider.setValue(75)

        assert 75 in received

    def test_clock_checkbox_exists(self, qapp):
        """Test clock checkbox exists."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()

        assert widget.clock_checkbox is not None
        assert widget.clock_format is not None
        assert widget.show_seconds is not None
        assert widget.show_date is not None

    def test_toggle_clock_enables_timer(self, qapp):
        """Test enabling clock starts timer."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        assert widget._clock_enabled is False
        assert widget._clock_timer.isActive() is False

        widget._toggle_clock(True)

        assert widget._clock_enabled is True
        assert widget._clock_timer.isActive() is True
        assert widget.lcd_text.isEnabled() is False

        # Cleanup
        widget._toggle_clock(False)

    def test_toggle_clock_disables_timer(self, qapp):
        """Test disabling clock stops timer."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        widget._toggle_clock(True)
        assert widget._clock_timer.isActive() is True

        widget._toggle_clock(False)

        assert widget._clock_enabled is False
        assert widget._clock_timer.isActive() is False
        assert widget.lcd_text.isEnabled() is True

    def test_update_clock_24h_with_seconds(self, qapp):
        """Test clock update in 24h format with seconds."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        received = []
        widget.lcd_text_changed.connect(lambda t: received.append(t))

        widget.clock_format.setCurrentIndex(0)  # 24-hour
        widget.show_seconds.setChecked(True)
        widget.show_date.setChecked(False)

        widget._update_clock()

        assert len(received) == 1
        # Format: HH:MM:SS
        assert ":" in received[0]
        assert len(received[0].split(":")) == 3

    def test_update_clock_24h_without_seconds(self, qapp):
        """Test clock update in 24h format without seconds."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        received = []
        widget.lcd_text_changed.connect(lambda t: received.append(t))

        widget.clock_format.setCurrentIndex(0)  # 24-hour
        widget.show_seconds.setChecked(False)
        widget.show_date.setChecked(False)

        widget._update_clock()

        assert len(received) == 1
        # Format: HH:MM
        assert ":" in received[0]
        assert len(received[0].split(":")) == 2

    def test_update_clock_12h_with_seconds(self, qapp):
        """Test clock update in 12h format with seconds."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        received = []
        widget.lcd_text_changed.connect(lambda t: received.append(t))

        widget.clock_format.setCurrentIndex(1)  # 12-hour
        widget.show_seconds.setChecked(True)
        widget.show_date.setChecked(False)

        widget._update_clock()

        assert len(received) == 1
        # Format: HH:MM:SS AM/PM
        assert "AM" in received[0] or "PM" in received[0]

    def test_update_clock_12h_without_seconds(self, qapp):
        """Test clock update in 12h format without seconds."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        received = []
        widget.lcd_text_changed.connect(lambda t: received.append(t))

        widget.clock_format.setCurrentIndex(1)  # 12-hour
        widget.show_seconds.setChecked(False)
        widget.show_date.setChecked(False)

        widget._update_clock()

        assert len(received) == 1
        assert "AM" in received[0] or "PM" in received[0]

    def test_update_clock_with_date(self, qapp):
        """Test clock update with date enabled."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        received = []
        widget.lcd_text_changed.connect(lambda t: received.append(t))

        widget.show_date.setChecked(True)

        widget._update_clock()

        assert len(received) == 1
        # Should have newline for date
        assert "\n" in received[0]
        # Date format: YYYY-MM-DD
        assert "-" in received[0]

    def test_on_format_changed_updates_clock_when_enabled(self, qapp):
        """Test format change updates clock when enabled."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        received = []
        widget.lcd_text_changed.connect(lambda t: received.append(t))

        widget._clock_enabled = True
        widget._on_format_changed()

        assert len(received) == 1

        # Cleanup
        widget._clock_enabled = False

    def test_on_format_changed_does_nothing_when_disabled(self, qapp):
        """Test format change does nothing when clock disabled."""
        from g13_linux.gui.views.hardware_control import HardwareControlWidget

        widget = HardwareControlWidget()
        received = []
        widget.lcd_text_changed.connect(lambda t: received.append(t))

        widget._clock_enabled = False
        widget._on_format_changed()

        assert len(received) == 0


class TestProfileManagerWidget:
    """Tests for ProfileManagerWidget."""

    def test_init(self, qapp):
        """Test ProfileManagerWidget initialization."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()

        assert widget.profile_list is not None

    def test_has_signals(self, qapp):
        """Test ProfileManagerWidget has required signals."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()

        assert hasattr(widget, "profile_selected")
        assert hasattr(widget, "profile_saved")
        assert hasattr(widget, "profile_deleted")

    def test_update_profile_list(self, qapp):
        """Test update_profile_list populates list."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        widget.update_profile_list(["profile1", "profile2", "profile3"])

        assert widget.profile_list.count() == 3
        assert widget.profile_list.item(0).text() == "profile1"
        assert widget.profile_list.item(1).text() == "profile2"
        assert widget.profile_list.item(2).text() == "profile3"

    def test_update_profile_list_clears_previous(self, qapp):
        """Test update_profile_list clears previous items."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        widget.update_profile_list(["old1", "old2"])
        widget.update_profile_list(["new1"])

        assert widget.profile_list.count() == 1
        assert widget.profile_list.item(0).text() == "new1"

    def test_update_profile_list_preserves_selection(self, qapp):
        """Test update_profile_list preserves current selection."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        widget.update_profile_list(["profile1", "profile2"])
        widget.profile_list.setCurrentRow(1)  # Select profile2

        widget.update_profile_list(["profile1", "profile2", "profile3"])

        current = widget.profile_list.currentItem()
        assert current is not None
        assert current.text() == "profile2"

    def test_profile_selected_signal(self, qapp):
        """Test clicking profile emits signal."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        widget.update_profile_list(["test_profile"])

        received = []
        widget.profile_selected.connect(lambda name: received.append(name))

        # Simulate click
        item = widget.profile_list.item(0)
        widget.profile_list.itemClicked.emit(item)

        assert "test_profile" in received

    def test_on_new_profile(self, qapp):
        """Test new profile dialog."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        received = []
        widget.profile_selected.connect(lambda name: received.append(name))

        with patch("g13_linux.gui.views.profile_manager.QInputDialog") as mock_dialog:
            mock_dialog.getText.return_value = ("new_profile", True)
            widget._on_new_profile()

        assert "new_profile" in received

    def test_on_new_profile_cancelled(self, qapp):
        """Test new profile dialog cancelled."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        received = []
        widget.profile_selected.connect(lambda name: received.append(name))

        with patch("g13_linux.gui.views.profile_manager.QInputDialog") as mock_dialog:
            mock_dialog.getText.return_value = ("", False)
            widget._on_new_profile()

        assert received == []

    def test_on_save_profile(self, qapp):
        """Test save profile emits signal."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        widget.update_profile_list(["existing"])
        widget.profile_list.setCurrentRow(0)

        received = []
        widget.profile_saved.connect(lambda name: received.append(name))

        widget._on_save_profile()

        assert "existing" in received

    def test_on_save_profile_no_selection(self, qapp):
        """Test save profile with no selection opens save as."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        received = []
        widget.profile_saved.connect(lambda name: received.append(name))

        with patch("g13_linux.gui.views.profile_manager.QInputDialog") as mock_dialog:
            mock_dialog.getText.return_value = ("new_name", True)
            widget._on_save_profile()

        assert "new_name" in received

    def test_on_save_as_profile(self, qapp):
        """Test save as profile dialog."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        received = []
        widget.profile_saved.connect(lambda name: received.append(name))

        with patch("g13_linux.gui.views.profile_manager.QInputDialog") as mock_dialog:
            mock_dialog.getText.return_value = ("saved_as", True)
            widget._on_save_as_profile()

        assert "saved_as" in received

    def test_on_delete_profile(self, qapp):
        """Test delete profile emits signal on confirm."""
        from PyQt6.QtWidgets import QMessageBox

        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        widget.update_profile_list(["to_delete"])
        widget.profile_list.setCurrentRow(0)

        received = []
        widget.profile_deleted.connect(lambda name: received.append(name))

        with patch("g13_linux.gui.views.profile_manager.QMessageBox") as mock_box:
            mock_box.StandardButton.Yes = QMessageBox.StandardButton.Yes
            mock_box.StandardButton.No = QMessageBox.StandardButton.No
            mock_box.question.return_value = QMessageBox.StandardButton.Yes
            widget._on_delete_profile()

        assert "to_delete" in received

    def test_on_delete_profile_cancelled(self, qapp):
        """Test delete profile cancelled."""
        from PyQt6.QtWidgets import QMessageBox

        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        widget.update_profile_list(["to_delete"])
        widget.profile_list.setCurrentRow(0)

        received = []
        widget.profile_deleted.connect(lambda name: received.append(name))

        with patch("g13_linux.gui.views.profile_manager.QMessageBox") as mock_box:
            mock_box.StandardButton.Yes = QMessageBox.StandardButton.Yes
            mock_box.StandardButton.No = QMessageBox.StandardButton.No
            mock_box.question.return_value = QMessageBox.StandardButton.No
            widget._on_delete_profile()

        assert received == []

    def test_on_delete_profile_no_selection(self, qapp):
        """Test delete profile with no selection."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()

        received = []
        widget.profile_deleted.connect(lambda name: received.append(name))

        # Should not raise
        widget._on_delete_profile()

        assert received == []

    def test_update_profile_list_selection_not_found(self, qapp):
        """Test update_profile_list when previous selection not in new list.

        When the previously selected profile is not in the updated list,
        the 'if current_selection in profiles' check fails.
        """
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        widget.update_profile_list(["profile1", "profile2"])
        widget.profile_list.setCurrentRow(1)  # Select profile2

        # Update with list that doesn't contain profile2
        widget.update_profile_list(["profile1", "profile3"])

        # Selection should be cleared (profile2 not found)
        current = widget.profile_list.currentItem()
        # Either no selection or default to first item
        if current is not None:
            assert current.text() != "profile2"

    def test_update_profile_list_find_items_empty(self, qapp):
        """Test update_profile_list when findItems returns empty (line 82->exit).

        Edge case where current_selection is in profiles list but findItems
        returns empty (e.g., if widget state is inconsistent).
        """
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        widget.update_profile_list(["profile1", "profile2"])
        widget.profile_list.setCurrentRow(1)  # Select profile2

        # Mock findItems to return empty list even though item is in profiles
        with patch.object(widget.profile_list, "findItems", return_value=[]):
            widget.update_profile_list(["profile1", "profile2"])

        # No crash, and selection not restored (findItems returned empty)
        # The mocked findItems means setCurrentItem was never called

    def test_on_save_as_profile_cancelled(self, qapp):
        """Test save as profile dialog cancelled (line 102->exit)."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        received = []
        widget.profile_saved.connect(lambda name: received.append(name))

        with patch("g13_linux.gui.views.profile_manager.QInputDialog") as mock_dialog:
            mock_dialog.getText.return_value = ("", False)  # Cancelled
            widget._on_save_as_profile()

        assert received == []

    def test_on_save_as_profile_empty_name(self, qapp):
        """Test save as profile with empty name (line 102->exit)."""
        from g13_linux.gui.views.profile_manager import ProfileManagerWidget

        widget = ProfileManagerWidget()
        received = []
        widget.profile_saved.connect(lambda name: received.append(name))

        with patch("g13_linux.gui.views.profile_manager.QInputDialog") as mock_dialog:
            mock_dialog.getText.return_value = ("", True)  # OK but empty name
            widget._on_save_as_profile()

        assert received == []
