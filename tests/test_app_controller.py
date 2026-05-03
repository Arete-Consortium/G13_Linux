"""Tests for ApplicationController."""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QMessageBox

from g13_linux.gui.controllers.app_controller import ApplicationController
from g13_linux.gui.models.macro_recorder import RecorderState


@pytest.fixture
def mock_main_window():
    """Create a mock main window with all required widgets."""
    window = MagicMock()

    # Profile widget
    window.profile_widget = MagicMock()
    window.profile_widget.profile_selected = MagicMock()
    window.profile_widget.profile_saved = MagicMock()
    window.profile_widget.profile_deleted = MagicMock()

    # Button mapper
    window.button_mapper = MagicMock()
    window.button_mapper.button_clicked = MagicMock()
    window.button_mapper.button_unbind_requested = MagicMock()

    # Hardware widget
    window.hardware_widget = MagicMock()
    window.hardware_widget.lcd_text_changed = MagicMock()
    window.hardware_widget.backlight_color_changed = MagicMock()
    window.hardware_widget.backlight_brightness_changed = MagicMock()

    # Monitor widget
    window.monitor_widget = MagicMock()

    # Macro widget
    window.macro_widget = MagicMock()
    window.macro_widget.macro_saved = MagicMock()

    # Session summary bar updater
    window.set_session_summary = MagicMock()
    window.diagnostics_requested = MagicMock()
    window.quick_setup_requested = MagicMock()

    return window


@pytest.fixture(autouse=True)
def mock_setup_assistant_dialog():
    """Prevent real Qt dialog creation in non-Qt tests."""
    with patch("g13_linux.gui.controllers.app_controller.SetupAssistantDialog") as mock_dialog_cls:
        mock_dialog_cls.return_value.exec.return_value = 0
        yield mock_dialog_cls


@pytest.fixture
def mock_dependencies():
    """Patch all external dependencies."""
    with (
        patch("g13_linux.gui.controllers.app_controller.G13Device") as mock_device_cls,
        patch("g13_linux.gui.controllers.app_controller.ProfileManager") as mock_profile_cls,
        patch("g13_linux.gui.controllers.app_controller.EventDecoder") as mock_decoder_cls,
        patch("g13_linux.gui.controllers.app_controller.HardwareController") as mock_hw_cls,
        patch("g13_linux.gui.controllers.app_controller.MacroRecorder") as mock_recorder_cls,
        patch("g13_linux.gui.controllers.app_controller.MacroPlayer") as mock_player_cls,
        patch("g13_linux.gui.controllers.app_controller.MacroManager") as mock_macro_mgr_cls,
        patch("g13_linux.gui.controllers.app_controller.GlobalHotkeyManager") as mock_hotkey_cls,
    ):
        # Configure device mock
        mock_device = MagicMock()
        mock_device.device_connected = MagicMock()
        mock_device.device_disconnected = MagicMock()
        mock_device.raw_event_received = MagicMock()
        mock_device.error_occurred = MagicMock()
        mock_device_cls.return_value = mock_device

        # Configure recorder mock
        mock_recorder = MagicMock()
        mock_recorder.state_changed = MagicMock()
        mock_recorder.recording_complete = MagicMock()
        mock_recorder.error_occurred = MagicMock()
        mock_recorder.is_recording = False
        mock_recorder_cls.return_value = mock_recorder

        # Configure player mock
        mock_player = MagicMock()
        mock_player.playback_complete = MagicMock()
        mock_player.error_occurred = MagicMock()
        mock_player.is_playing = False
        mock_player_cls.return_value = mock_player

        # Configure hotkey mock
        mock_hotkey = MagicMock()
        mock_hotkey.hotkey_triggered = MagicMock()
        mock_hotkey.error_occurred = MagicMock()
        mock_hotkey_cls.return_value = mock_hotkey

        yield {
            "device_cls": mock_device_cls,
            "device": mock_device,
            "profile_mgr_cls": mock_profile_cls,
            "profile_mgr": mock_profile_cls.return_value,
            "decoder_cls": mock_decoder_cls,
            "decoder": mock_decoder_cls.return_value,
            "hw_cls": mock_hw_cls,
            "hardware": mock_hw_cls.return_value,
            "recorder_cls": mock_recorder_cls,
            "recorder": mock_recorder,
            "player_cls": mock_player_cls,
            "player": mock_player,
            "macro_mgr_cls": mock_macro_mgr_cls,
            "macro_mgr": mock_macro_mgr_cls.return_value,
            "hotkey_cls": mock_hotkey_cls,
            "hotkey": mock_hotkey,
        }


class TestApplicationControllerInit:
    """Tests for ApplicationController initialization."""

    def test_init_creates_device(self, mock_main_window, mock_dependencies):
        """Test init creates G13Device."""
        controller = ApplicationController(mock_main_window)

        mock_dependencies["device_cls"].assert_called_once_with(use_libusb=False)
        assert controller.device is mock_dependencies["device"]

    def test_init_with_libusb(self, mock_main_window, mock_dependencies):
        """Test init with libusb flag."""
        ApplicationController(mock_main_window, use_libusb=True)

        mock_dependencies["device_cls"].assert_called_once_with(use_libusb=True)

    def test_init_creates_models(self, mock_main_window, mock_dependencies):
        """Test init creates all model instances."""
        controller = ApplicationController(mock_main_window)

        assert controller.profile_manager is mock_dependencies["profile_mgr"]
        assert controller.event_decoder is mock_dependencies["decoder"]
        assert controller.hardware is mock_dependencies["hardware"]

    def test_init_creates_macro_system(self, mock_main_window, mock_dependencies):
        """Test init creates macro system components."""
        controller = ApplicationController(mock_main_window)

        assert controller.macro_recorder is mock_dependencies["recorder"]
        assert controller.macro_player is mock_dependencies["player"]
        assert controller.macro_manager is mock_dependencies["macro_mgr"]
        assert controller.hotkey_manager is mock_dependencies["hotkey"]

    def test_init_state(self, mock_main_window, mock_dependencies):
        """Test init sets default state."""
        controller = ApplicationController(mock_main_window)

        assert controller.current_mappings == {}
        assert controller.event_thread is None
        assert controller._mr_button_held is False


class TestApplicationControllerStart:
    """Tests for start method."""

    def test_start_connects_device(self, mock_main_window, mock_dependencies):
        """Test start attempts device connection."""
        mock_dependencies["device"].connect.return_value = True
        mock_dependencies["device"].handle = MagicMock()
        mock_dependencies["profile_mgr"].list_profiles.return_value = []

        with patch("g13_linux.gui.controllers.app_controller.DeviceEventThread"):
            controller = ApplicationController(mock_main_window)
            controller.start()

        mock_dependencies["device"].connect.assert_called_once()

    def test_start_sets_status_when_connected(self, mock_main_window, mock_dependencies):
        """Test start sets connected status."""
        mock_dependencies["device"].connect.return_value = True
        mock_dependencies["device"].handle = MagicMock()
        mock_dependencies["profile_mgr"].list_profiles.return_value = []

        with patch("g13_linux.gui.controllers.app_controller.DeviceEventThread"):
            controller = ApplicationController(mock_main_window)
            controller.start()

        mock_main_window.set_status.assert_any_call("G13 device connected")

    def test_start_sets_status_when_not_connected(self, mock_main_window, mock_dependencies):
        """Test start sets not found status."""
        mock_dependencies["device"].connect.return_value = False
        mock_dependencies["profile_mgr"].list_profiles.return_value = []

        with patch("g13_linux.gui.controllers.app_controller.SetupAssistantDialog"):
            controller = ApplicationController(mock_main_window)
            controller.start()

        mock_main_window.set_status.assert_any_call("No G13 device found")

    def test_start_not_connected_opens_setup_assistant_once(
        self, mock_main_window, mock_dependencies
    ):
        """Initial connection failure should open setup assistant only once per controller."""
        mock_dependencies["device"].connect.return_value = False
        mock_dependencies["profile_mgr"].list_profiles.return_value = []

        with (
            patch(
                "g13_linux.gui.controllers.app_controller.probe_device_backends",
                return_value=[{"backend": "hidraw", "ok": False, "error": "Permission denied"}],
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.find_g13_hidraw_info", return_value=None
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.SetupAssistantDialog"
            ) as mock_dialog_cls,
        ):
            controller = ApplicationController(mock_main_window)
            controller.start()
            controller.start()

        mock_dialog_cls.assert_called_once()
        mock_dialog_cls.return_value.exec.assert_called_once()

    def test_start_initializes_hardware(self, mock_main_window, mock_dependencies):
        """Test start initializes hardware controller."""
        mock_handle = MagicMock()
        mock_dependencies["device"].connect.return_value = True
        mock_dependencies["device"].handle = mock_handle
        mock_dependencies["profile_mgr"].list_profiles.return_value = []

        with patch("g13_linux.gui.controllers.app_controller.DeviceEventThread"):
            controller = ApplicationController(mock_main_window)
            controller.start()

        mock_dependencies["hardware"].initialize.assert_called_once_with(mock_handle)

    def test_start_loads_profile_list(self, mock_main_window, mock_dependencies):
        """Test start loads profile list."""
        mock_dependencies["device"].connect.return_value = False
        mock_dependencies["profile_mgr"].list_profiles.return_value = ["profile1", "profile2"]

        controller = ApplicationController(mock_main_window)
        controller.start()

        mock_main_window.profile_widget.update_profile_list.assert_called_once_with(
            ["profile1", "profile2"]
        )

    def test_start_loads_example_profile(self, mock_main_window, mock_dependencies):
        """Test start loads example profile if exists."""
        mock_dependencies["device"].connect.return_value = False
        mock_dependencies["profile_mgr"].list_profiles.return_value = ["example", "other"]

        mock_profile = MagicMock()
        mock_profile.mappings = {"G1": "a"}
        mock_dependencies["profile_mgr"].load_profile.return_value = mock_profile

        controller = ApplicationController(mock_main_window)
        controller.start()

        mock_dependencies["profile_mgr"].load_profile.assert_called_with("example")

    def test_start_starts_hotkey_manager(self, mock_main_window, mock_dependencies):
        """Test start starts global hotkey manager."""
        mock_dependencies["device"].connect.return_value = False
        mock_dependencies["profile_mgr"].list_profiles.return_value = []

        controller = ApplicationController(mock_main_window)
        controller.start()

        mock_dependencies["hotkey"].start.assert_called_once()


class TestApplicationControllerDeviceEvents:
    """Tests for device event handling."""

    def test_on_device_connected(self, mock_main_window, mock_dependencies):
        """Test device connected handler."""
        controller = ApplicationController(mock_main_window)
        controller._on_device_connected()

        mock_main_window.set_status.assert_called_with("G13 device connected")

    def test_on_device_disconnected(self, mock_main_window, mock_dependencies):
        """Test device disconnected handler."""
        controller = ApplicationController(mock_main_window)
        mock_thread = MagicMock()
        controller.event_thread = mock_thread

        controller._on_device_disconnected()

        mock_main_window.set_status.assert_called_with("G13 device disconnected")
        mock_thread.stop.assert_called_once()

    def test_on_error(self, mock_main_window, mock_dependencies, capsys):
        """Test error handler."""
        controller = ApplicationController(mock_main_window)
        controller._on_error("Test error message")

        mock_main_window.set_status.assert_called_with("Error: Test error message")
        captured = capsys.readouterr()
        assert "ERROR: Test error message" in captured.out

    def test_run_device_diagnostics_success(self, mock_main_window, mock_dependencies):
        """Diagnostics should report available backends with info dialog."""
        with (
            patch(
                "g13_linux.gui.controllers.app_controller.find_g13_hidraw_info",
                return_value={
                    "path": "/dev/hidraw2",
                    "readable": True,
                    "writable": True,
                    "detection_source": "uevent",
                },
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.probe_device_backends",
                return_value=[
                    {"backend": "hidraw", "ok": True, "error": None},
                    {"backend": "libusb", "ok": False, "error": "pyusb not installed"},
                ],
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.SetupAssistantDialog"
            ) as mock_dialog_cls,
        ):
            controller = ApplicationController(mock_main_window)
            controller._run_device_diagnostics()

        mock_dialog_cls.assert_called_once()
        assert "hidraw: OK" in mock_dialog_cls.call_args.kwargs["diagnostics_text"]
        mock_main_window.set_status.assert_any_call(
            "Diagnostics complete: available backend(s): hidraw"
        )

    def test_run_device_diagnostics_failure(self, mock_main_window, mock_dependencies):
        """Diagnostics should show checklist and warning when all backends fail."""
        with (
            patch(
                "g13_linux.gui.controllers.app_controller.find_g13_hidraw_info", return_value=None
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.probe_device_backends",
                return_value=[
                    {"backend": "hidraw", "ok": False, "error": "Permission denied"},
                    {"backend": "libusb", "ok": False, "error": "G13 not found"},
                ],
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.SetupAssistantDialog"
            ) as mock_dialog_cls,
        ):
            controller = ApplicationController(mock_main_window)
            controller._run_device_diagnostics()

        mock_dialog_cls.assert_called_once()
        assert "Checklist:" in mock_dialog_cls.call_args.kwargs["diagnostics_text"]
        mock_main_window.set_status.assert_any_call("Diagnostics complete: no available backend")


class TestApplicationControllerProfiles:
    """Tests for profile management."""

    def test_load_profile_success(self, mock_main_window, mock_dependencies):
        """Test loading a profile."""
        mock_profile = MagicMock()
        mock_profile.mappings = {"G1": "a", "G2": "b"}
        mock_dependencies["profile_mgr"].load_profile.return_value = mock_profile

        controller = ApplicationController(mock_main_window)
        controller._load_profile("test_profile")

        mock_dependencies["profile_mgr"].load_profile.assert_called_with("test_profile")
        assert controller.current_mappings == {"G1": "a", "G2": "b"}
        mock_main_window.set_status.assert_called_with("Loaded profile: test_profile")

    def test_load_profile_updates_mapper(self, mock_main_window, mock_dependencies):
        """Test loading a profile updates button mapper."""
        mock_profile = MagicMock()
        mock_profile.mappings = {"G1": "a", "G2": "b"}
        mock_dependencies["profile_mgr"].load_profile.return_value = mock_profile

        controller = ApplicationController(mock_main_window)
        controller._load_profile("test_profile")

        mock_main_window.button_mapper.set_button_mapping.assert_any_call("G1", "a")
        mock_main_window.button_mapper.set_button_mapping.assert_any_call("G2", "b")

    def test_load_profile_error(self, mock_main_window, mock_dependencies):
        """Test loading profile handles error."""
        mock_dependencies["profile_mgr"].load_profile.side_effect = FileNotFoundError("Not found")

        with patch.object(ApplicationController, "_on_error") as mock_on_error:
            controller = ApplicationController(mock_main_window)

            with patch("g13_linux.gui.controllers.app_controller.QMessageBox"):
                controller._load_profile("missing")

            mock_on_error.assert_called()

    def test_save_profile_new(self, mock_main_window, mock_dependencies):
        """Test saving a new profile."""
        mock_dependencies["profile_mgr"].profile_exists.return_value = False
        mock_profile = MagicMock()
        mock_dependencies["profile_mgr"].create_profile.return_value = mock_profile
        mock_dependencies["profile_mgr"].list_profiles.return_value = ["new_profile"]

        controller = ApplicationController(mock_main_window)
        controller.current_mappings = {"G1": "x"}
        controller._save_profile("new_profile")

        mock_dependencies["profile_mgr"].create_profile.assert_called_with("new_profile")
        mock_dependencies["profile_mgr"].save_profile.assert_called()
        mock_main_window.set_status.assert_called_with("Saved profile: new_profile")

    def test_save_profile_existing(self, mock_main_window, mock_dependencies):
        """Test saving an existing profile."""
        mock_dependencies["profile_mgr"].profile_exists.return_value = True
        mock_profile = MagicMock()
        mock_dependencies["profile_mgr"].load_profile.return_value = mock_profile
        mock_dependencies["profile_mgr"].list_profiles.return_value = ["existing"]

        controller = ApplicationController(mock_main_window)
        controller.current_mappings = {"G1": "y"}
        controller._save_profile("existing")

        mock_dependencies["profile_mgr"].load_profile.assert_called_with("existing")
        mock_dependencies["profile_mgr"].save_profile.assert_called()

    def test_save_profile_persists_joystick_config(self, mock_main_window, mock_dependencies):
        """Test save profile writes joystick config to profile data."""
        mock_dependencies["profile_mgr"].profile_exists.return_value = False
        mock_profile = MagicMock()
        mock_dependencies["profile_mgr"].create_profile.return_value = mock_profile
        mock_dependencies["profile_mgr"].list_profiles.return_value = ["new_profile"]

        controller = ApplicationController(mock_main_window)
        controller.current_mappings = {"G1": "x"}
        controller.current_joystick_config = {
            "mode": "digital",
            "deadzone": 25,
            "sensitivity": 1.2,
            "key_up": "KEY_W",
            "key_down": "KEY_S",
            "key_left": "KEY_A",
            "key_right": "KEY_D",
            "allow_diagonals": False,
        }
        controller._save_profile("new_profile")

        assert mock_profile.joystick == controller.current_joystick_config

    def test_delete_profile(self, mock_main_window, mock_dependencies):
        """Test deleting a profile."""
        mock_dependencies["profile_mgr"].list_profiles.return_value = []

        controller = ApplicationController(mock_main_window)
        controller._delete_profile("to_delete")

        mock_dependencies["profile_mgr"].delete_profile.assert_called_with("to_delete")
        mock_main_window.set_status.assert_called_with("Deleted profile: to_delete")


class TestApplicationControllerButtonMapping:
    """Tests for button mapping."""

    def test_is_bound_mapping_helper(self, mock_main_window, mock_dependencies):
        """Bound mapping helper should classify legacy/unbound values correctly."""
        controller = ApplicationController(mock_main_window)

        assert controller._is_bound_mapping("KEY_A") is True
        assert controller._is_bound_mapping({"keys": ["KEY_LEFTCTRL", "KEY_B"]}) is True
        assert controller._is_bound_mapping({"keys": ["KEY_RESERVED"]}) is False
        assert controller._is_bound_mapping("KEY_RESERVED") is False
        assert controller._is_bound_mapping(None) is False

    def test_assign_key_to_button(self, mock_main_window, mock_dependencies):
        """Test assigning a key to a button."""
        with patch("g13_linux.gui.controllers.app_controller.KeySelectorDialog") as mock_dialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = True
            mock_dialog_instance.selected_key = "space"
            mock_dialog.return_value = mock_dialog_instance

            controller = ApplicationController(mock_main_window)
            controller._assign_key_to_button("G5")

            assert controller.current_mappings["G5"] == "space"
            mock_main_window.button_mapper.set_button_mapping.assert_called_with("G5", "space")
            mock_main_window.set_status.assert_called_with("Mapped G5 to space")
            mock_main_window.set_session_summary.assert_called_with(None, 1, "analog")

    def test_assign_key_cancelled(self, mock_main_window, mock_dependencies):
        """Test cancelling key assignment."""
        with patch("g13_linux.gui.controllers.app_controller.KeySelectorDialog") as mock_dialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = False
            mock_dialog.return_value = mock_dialog_instance

            controller = ApplicationController(mock_main_window)
            controller._assign_key_to_button("G5")

            assert "G5" not in controller.current_mappings

    def test_assign_key_status_strips_key_prefix(self, mock_main_window, mock_dependencies):
        """Status should display readable key names without KEY_ prefix."""
        with patch("g13_linux.gui.controllers.app_controller.KeySelectorDialog") as mock_dialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = True
            mock_dialog_instance.selected_key = "KEY_SPACE"
            mock_dialog.return_value = mock_dialog_instance

            controller = ApplicationController(mock_main_window)
            controller._assign_key_to_button("G5")

            mock_main_window.set_status.assert_called_with("Mapped G5 to SPACE")

    def test_assign_key_reserved_clears_mapping(self, mock_main_window, mock_dependencies):
        """KEY_RESERVED from selector should clear existing mapping."""
        with patch("g13_linux.gui.controllers.app_controller.KeySelectorDialog") as mock_dialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = True
            mock_dialog_instance.selected_key = "KEY_RESERVED"
            mock_dialog.return_value = mock_dialog_instance

            controller = ApplicationController(mock_main_window)
            controller.current_mappings["G5"] = "KEY_F1"
            controller._assign_key_to_button("G5")

            assert "G5" not in controller.current_mappings
            mock_main_window.button_mapper.set_button_mapping.assert_called_with("G5", None)
            mock_main_window.set_status.assert_called_with("Cleared mapping for G5")

    def test_assign_key_conflict_move_clears_previous_button(
        self, mock_main_window, mock_dependencies
    ):
        """Choosing move on conflict should clear old binding and keep one owner."""
        with (
            patch("g13_linux.gui.controllers.app_controller.KeySelectorDialog") as mock_dialog,
            patch(
                "g13_linux.gui.controllers.app_controller.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ) as mock_question,
        ):
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = True
            mock_dialog_instance.selected_key = "KEY_SPACE"
            mock_dialog.return_value = mock_dialog_instance

            controller = ApplicationController(mock_main_window)
            controller.current_mappings = {"G3": "KEY_SPACE", "G5": "KEY_F1"}
            controller._assign_key_to_button("G5")

            assert "G3" not in controller.current_mappings
            assert controller.current_mappings["G5"] == "KEY_SPACE"
            mock_question.assert_called_once()
            mock_main_window.button_mapper.set_button_mapping.assert_any_call("G3", None)
            mock_main_window.button_mapper.set_button_mapping.assert_any_call("G5", "KEY_SPACE")
            mock_main_window.set_status.assert_called_with("Mapped G5 to SPACE (moved from G3)")

    def test_assign_key_conflict_keep_duplicate(self, mock_main_window, mock_dependencies):
        """Choosing keep duplicate should preserve existing owner and map target too."""
        with (
            patch("g13_linux.gui.controllers.app_controller.KeySelectorDialog") as mock_dialog,
            patch(
                "g13_linux.gui.controllers.app_controller.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ) as mock_question,
        ):
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = True
            mock_dialog_instance.selected_key = "KEY_SPACE"
            mock_dialog.return_value = mock_dialog_instance

            controller = ApplicationController(mock_main_window)
            controller.current_mappings = {"G3": "KEY_SPACE"}
            controller._assign_key_to_button("G5")

            assert controller.current_mappings["G3"] == "KEY_SPACE"
            assert controller.current_mappings["G5"] == "KEY_SPACE"
            mock_question.assert_called_once()
            mock_main_window.set_status.assert_called_with("Mapped G5 to SPACE (also on G3)")

    def test_assign_key_conflict_cancel_keeps_existing_mapping(
        self, mock_main_window, mock_dependencies
    ):
        """Canceling conflict prompt should leave mappings unchanged."""
        with (
            patch("g13_linux.gui.controllers.app_controller.KeySelectorDialog") as mock_dialog,
            patch(
                "g13_linux.gui.controllers.app_controller.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Cancel,
            ) as mock_question,
        ):
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = True
            mock_dialog_instance.selected_key = "KEY_SPACE"
            mock_dialog.return_value = mock_dialog_instance

            controller = ApplicationController(mock_main_window)
            controller.current_mappings = {"G3": "KEY_SPACE", "G5": "KEY_F2"}
            controller._assign_key_to_button("G5")

            assert controller.current_mappings["G3"] == "KEY_SPACE"
            assert controller.current_mappings["G5"] == "KEY_F2"
            mock_question.assert_called_once()
            mock_main_window.set_status.assert_called_with("Mapping for G5 unchanged")

    def test_clear_button_mapping(self, mock_main_window, mock_dependencies):
        """Direct clear request removes mapping and updates UI."""
        controller = ApplicationController(mock_main_window)
        controller.current_mappings["G7"] = "KEY_F2"

        controller._clear_button_mapping("G7")

        assert "G7" not in controller.current_mappings
        mock_main_window.button_mapper.set_button_mapping.assert_called_with("G7", None)
        mock_main_window.set_status.assert_called_with("Cleared mapping for G7")
        mock_main_window.set_session_summary.assert_called_with(None, 0, "analog")

    def test_clear_button_mapping_when_already_unbound(self, mock_main_window, mock_dependencies):
        """Clearing unbound key should keep map empty and show helpful status."""
        controller = ApplicationController(mock_main_window)

        controller._clear_button_mapping("G22")

        assert "G22" not in controller.current_mappings
        mock_main_window.button_mapper.set_button_mapping.assert_called_with("G22", None)
        mock_main_window.set_status.assert_called_with("G22 is already unbound")
        mock_main_window.set_session_summary.assert_called_with(None, 0, "analog")


class TestApplicationControllerQuickSetup:
    """Tests for guided quick setup wizard."""

    def test_quick_setup_wizard_cancelled_before_start(self, mock_main_window, mock_dependencies):
        """Canceling start prompt should leave mappings unchanged."""
        with patch(
            "g13_linux.gui.controllers.app_controller.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Cancel,
        ) as mock_question:
            controller = ApplicationController(mock_main_window)
            controller._QUICK_BIND_SEQUENCE = ("G1", "G2")
            controller._run_quick_binding_wizard()

        assert controller.current_mappings == {}
        mock_question.assert_called_once()
        mock_main_window.set_status.assert_called_with("Quick setup canceled")

    def test_quick_setup_wizard_applies_bindings(self, mock_main_window, mock_dependencies):
        """Wizard should apply selected bindings and report completion summary."""
        first_dialog = MagicMock()
        first_dialog.exec.return_value = True
        first_dialog.selected_key = "KEY_1"

        second_dialog = MagicMock()
        second_dialog.exec.return_value = True
        second_dialog.selected_key = "KEY_2"

        with (
            patch(
                "g13_linux.gui.controllers.app_controller.QMessageBox.question",
                side_effect=[QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No],
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.QInputDialog.getItem",
                return_value=(ApplicationController._QUICK_SETUP_MANUAL_TEMPLATE, True),
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.KeySelectorDialog",
                side_effect=[first_dialog, second_dialog],
            ) as mock_dialog_cls,
        ):
            controller = ApplicationController(mock_main_window)
            controller._QUICK_BIND_SEQUENCE = ("G1", "G2")
            controller._run_quick_binding_wizard()

        assert controller.current_mappings["G1"] == "KEY_1"
        assert controller.current_mappings["G2"] == "KEY_2"
        assert mock_dialog_cls.call_count == 2
        mock_main_window.set_status.assert_any_call("Quick setup complete: updated 2/2, skipped 0")

    def test_quick_setup_wizard_stop_after_cancelled_step(
        self, mock_main_window, mock_dependencies
    ):
        """Canceling a step and choosing stop should end wizard immediately."""
        first_dialog = MagicMock()
        first_dialog.exec.return_value = False

        with (
            patch(
                "g13_linux.gui.controllers.app_controller.QMessageBox.question",
                side_effect=[QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No],
            ) as mock_question,
            patch(
                "g13_linux.gui.controllers.app_controller.QInputDialog.getItem",
                return_value=(ApplicationController._QUICK_SETUP_MANUAL_TEMPLATE, True),
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.KeySelectorDialog",
                return_value=first_dialog,
            ),
        ):
            controller = ApplicationController(mock_main_window)
            controller._QUICK_BIND_SEQUENCE = ("G1", "G2")
            controller._run_quick_binding_wizard()

        assert controller.current_mappings == {}
        assert mock_question.call_count == 2
        mock_main_window.set_status.assert_any_call("Quick setup stopped: updated 0/2, skipped 0")

    def test_quick_setup_wizard_skip_step_and_continue(self, mock_main_window, mock_dependencies):
        """Choosing skip should continue wizard and map later steps."""
        first_dialog = MagicMock()
        first_dialog.exec.return_value = False

        second_dialog = MagicMock()
        second_dialog.exec.return_value = True
        second_dialog.selected_key = "KEY_2"

        with (
            patch(
                "g13_linux.gui.controllers.app_controller.QMessageBox.question",
                side_effect=[
                    QMessageBox.StandardButton.Yes,
                    QMessageBox.StandardButton.Yes,
                    QMessageBox.StandardButton.No,
                ],
            ) as mock_question,
            patch(
                "g13_linux.gui.controllers.app_controller.QInputDialog.getItem",
                return_value=(ApplicationController._QUICK_SETUP_MANUAL_TEMPLATE, True),
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.KeySelectorDialog",
                side_effect=[first_dialog, second_dialog],
            ),
        ):
            controller = ApplicationController(mock_main_window)
            controller._QUICK_BIND_SEQUENCE = ("G1", "G2")
            controller._run_quick_binding_wizard()

        assert "G1" not in controller.current_mappings
        assert controller.current_mappings["G2"] == "KEY_2"
        assert mock_question.call_count == 3
        mock_main_window.set_status.assert_any_call("Quick setup complete: updated 1/2, skipped 1")

    def test_quick_setup_wizard_template_applies_without_review(
        self, mock_main_window, mock_dependencies
    ):
        """Template flow can finish immediately without per-button review dialogs."""
        with (
            patch(
                "g13_linux.gui.controllers.app_controller.QMessageBox.question",
                side_effect=[
                    QMessageBox.StandardButton.Yes,  # Start wizard
                    QMessageBox.StandardButton.No,  # Skip guided review after template
                    QMessageBox.StandardButton.No,  # Don't save profile
                ],
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.QInputDialog.getItem",
                return_value=("MMO Starter (1-8 Keys)", True),
            ),
            patch("g13_linux.gui.controllers.app_controller.KeySelectorDialog") as mock_dialog_cls,
        ):
            controller = ApplicationController(mock_main_window)
            controller._QUICK_BIND_SEQUENCE = ("G1", "G2")
            controller._run_quick_binding_wizard()

        assert controller.current_mappings["G1"] == "KEY_1"
        assert controller.current_mappings["G2"] == "KEY_2"
        mock_dialog_cls.assert_not_called()
        mock_main_window.set_status.assert_any_call("Quick setup complete: updated 2/2, skipped 0")

    def test_quick_setup_wizard_template_then_save_profile(
        self, mock_main_window, mock_dependencies
    ):
        """Wizard can save template-driven setup into a named profile."""
        with (
            patch(
                "g13_linux.gui.controllers.app_controller.QMessageBox.question",
                side_effect=[
                    QMessageBox.StandardButton.Yes,  # Start wizard
                    QMessageBox.StandardButton.No,  # Skip guided review after template
                    QMessageBox.StandardButton.Yes,  # Save profile
                ],
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.QInputDialog.getItem",
                return_value=("MMO Starter (1-8 Keys)", True),
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.QInputDialog.getText",
                return_value=("wizard_profile", True),
            ),
            patch.object(ApplicationController, "_save_profile") as mock_save_profile,
        ):
            controller = ApplicationController(mock_main_window)
            controller._QUICK_BIND_SEQUENCE = ("G1",)
            controller._run_quick_binding_wizard()

        mock_save_profile.assert_called_once_with("wizard_profile")
        mock_main_window.set_status.assert_any_call(
            "Quick setup saved to profile 'wizard_profile' (1/1 updated, 0 skipped)"
        )

    def test_quick_setup_wizard_canceled_template_selection(
        self, mock_main_window, mock_dependencies
    ):
        """Canceling template picker should abort wizard cleanly."""
        with (
            patch(
                "g13_linux.gui.controllers.app_controller.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch(
                "g13_linux.gui.controllers.app_controller.QInputDialog.getItem",
                return_value=("", False),
            ),
        ):
            controller = ApplicationController(mock_main_window)
            controller._QUICK_BIND_SEQUENCE = ("G1",)
            controller._run_quick_binding_wizard()

        assert controller.current_mappings == {}
        mock_main_window.set_status.assert_any_call("Quick setup canceled")


class TestApplicationControllerHardware:
    """Tests for hardware control methods."""

    def test_update_lcd(self, mock_main_window, mock_dependencies):
        """Test updating LCD text."""
        mock_lcd = MagicMock()
        mock_lcd._framebuffer = b"\x00" * 100
        mock_dependencies["hardware"].lcd = mock_lcd

        controller = ApplicationController(mock_main_window)
        controller._update_lcd("Hello")

        mock_dependencies["hardware"].set_lcd_text.assert_called_with("Hello")
        mock_main_window.set_status.assert_called_with("LCD updated")

    def test_update_lcd_error(self, mock_main_window, mock_dependencies):
        """Test LCD update error handling."""
        mock_dependencies["hardware"].set_lcd_text.side_effect = Exception("LCD error")

        controller = ApplicationController(mock_main_window)
        controller._update_lcd("Test")

        # Error should be reported
        mock_main_window.set_status.assert_called()

    def test_update_backlight_color(self, mock_main_window, mock_dependencies):
        """Test updating backlight color."""
        controller = ApplicationController(mock_main_window)
        controller._update_backlight_color("#FF0000")

        mock_dependencies["hardware"].set_backlight_color.assert_called_with("#FF0000")
        mock_main_window.set_status.assert_called_with("Backlight color: #FF0000")

    def test_update_backlight_brightness(self, mock_main_window, mock_dependencies):
        """Test updating backlight brightness."""
        controller = ApplicationController(mock_main_window)
        controller._update_backlight_brightness(75)

        mock_dependencies["hardware"].set_backlight_brightness.assert_called_with(75)
        mock_main_window.set_status.assert_called_with("Backlight brightness: 75%")


class TestApplicationControllerMacroRecording:
    """Tests for macro recording."""

    def test_mr_button_pressed_starts_recording(self, mock_main_window, mock_dependencies):
        """Test MR button starts recording when idle."""
        mock_dependencies["recorder"].is_recording = False

        controller = ApplicationController(mock_main_window)
        controller._on_mr_button_pressed()

        mock_dependencies["recorder"].start_recording.assert_called_once()
        assert controller._mr_button_held is True

    def test_mr_button_pressed_stops_recording(self, mock_main_window, mock_dependencies):
        """Test MR button stops recording when recording."""
        mock_dependencies["recorder"].is_recording = True

        controller = ApplicationController(mock_main_window)
        controller._on_mr_button_pressed()

        mock_dependencies["recorder"].stop_recording.assert_called_once()

    def test_mr_button_released(self, mock_main_window, mock_dependencies):
        """Test MR button released."""
        controller = ApplicationController(mock_main_window)
        controller._mr_button_held = True

        controller._on_mr_button_released()

        assert controller._mr_button_held is False

    def test_on_recorder_state_changed_idle(self, mock_main_window, mock_dependencies):
        """Test recorder state change to idle."""
        controller = ApplicationController(mock_main_window)
        controller._on_recorder_state_changed(RecorderState.IDLE)

        mock_main_window.set_status.assert_called_with("Ready")

    def test_on_recorder_state_changed_recording(self, mock_main_window, mock_dependencies):
        """Test recorder state change to recording."""
        controller = ApplicationController(mock_main_window)
        controller._on_recorder_state_changed(RecorderState.RECORDING)

        mock_main_window.set_status.assert_called_with("Recording macro...")

    def test_on_macro_recorded(self, mock_main_window, mock_dependencies):
        """Test completed macro recording."""
        mock_macro = MagicMock()
        mock_macro.step_count = 5

        controller = ApplicationController(mock_main_window)
        controller._on_macro_recorded(mock_macro)

        mock_dependencies["macro_mgr"].save_macro.assert_called_with(mock_macro)
        mock_main_window.macro_widget.refresh_macro_list.assert_called_once()


class TestApplicationControllerMacroPlayback:
    """Tests for macro playback."""

    def test_check_macro_trigger(self, mock_main_window, mock_dependencies):
        """Test button triggers macro playback."""
        mock_macro = MagicMock()
        mock_dependencies["macro_mgr"].load_macro.return_value = mock_macro

        controller = ApplicationController(mock_main_window)
        controller.current_mappings = {"G1": {"macro": "macro-123"}}

        controller._check_macro_trigger("G1")

        mock_dependencies["macro_mgr"].load_macro.assert_called_with("macro-123")
        mock_dependencies["player"].play.assert_called_with(mock_macro)

    def test_check_macro_trigger_not_macro(self, mock_main_window, mock_dependencies):
        """Test button with key mapping doesn't trigger macro."""
        controller = ApplicationController(mock_main_window)
        controller.current_mappings = {"G1": "a"}

        controller._check_macro_trigger("G1")

        mock_dependencies["player"].play.assert_not_called()

    def test_check_macro_trigger_not_found(self, mock_main_window, mock_dependencies):
        """Test macro not found error handling."""
        mock_dependencies["macro_mgr"].load_macro.side_effect = FileNotFoundError()

        controller = ApplicationController(mock_main_window)
        controller.current_mappings = {"G1": {"macro": "missing"}}

        controller._check_macro_trigger("G1")

        mock_main_window.set_status.assert_called()

    def test_on_playback_complete(self, mock_main_window, mock_dependencies):
        """Test playback complete handler."""
        controller = ApplicationController(mock_main_window)
        controller._on_playback_complete()

        mock_main_window.set_status.assert_called_with("Macro playback complete")


class TestApplicationControllerHotkeys:
    """Tests for global hotkey handling."""

    def test_register_all_macro_hotkeys(self, mock_main_window, mock_dependencies):
        """Test registering all macro hotkeys."""
        mock_macro = MagicMock()
        mock_macro.global_hotkey = "ctrl+shift+a"
        mock_macro.id = "macro-1"

        mock_dependencies["macro_mgr"].list_macros.return_value = ["macro-1"]
        mock_dependencies["macro_mgr"].load_macro.return_value = mock_macro

        controller = ApplicationController(mock_main_window)
        controller._register_all_macro_hotkeys()

        mock_dependencies["hotkey"].clear_all.assert_called()
        mock_dependencies["hotkey"].register_hotkey.assert_called_with("ctrl+shift+a", "macro-1")

    def test_on_hotkey_triggered(self, mock_main_window, mock_dependencies):
        """Test hotkey triggers macro playback."""
        mock_macro = MagicMock()
        mock_macro.name = "Test Macro"
        mock_dependencies["macro_mgr"].load_macro.return_value = mock_macro

        controller = ApplicationController(mock_main_window)
        controller._on_hotkey_triggered("macro-123")

        mock_dependencies["macro_mgr"].load_macro.assert_called_with("macro-123")
        mock_dependencies["player"].play.assert_called_with(mock_macro)
        mock_main_window.set_status.assert_called_with("Hotkey triggered: Test Macro")

    def test_on_macro_saved(self, mock_main_window, mock_dependencies):
        """Test macro save updates hotkey registrations."""
        mock_macro = MagicMock()
        mock_macro.id = "macro-1"
        mock_macro.global_hotkey = "ctrl+alt+x"
        mock_macro.name = "My Macro"
        mock_dependencies["hotkey"].register_hotkey.return_value = True

        controller = ApplicationController(mock_main_window)
        controller._on_macro_saved(mock_macro)

        mock_dependencies["hotkey"].unregister_macro.assert_called_with("macro-1")
        mock_dependencies["hotkey"].register_hotkey.assert_called_with("ctrl+alt+x", "macro-1")


class TestApplicationControllerShutdown:
    """Tests for shutdown method."""

    def test_shutdown_stops_recording(self, mock_main_window, mock_dependencies):
        """Test shutdown stops active recording."""
        mock_dependencies["recorder"].is_recording = True

        controller = ApplicationController(mock_main_window)
        controller.shutdown()

        mock_dependencies["recorder"].cancel.assert_called_once()

    def test_shutdown_stops_playback(self, mock_main_window, mock_dependencies):
        """Test shutdown stops active playback."""
        mock_dependencies["player"].is_playing = True

        controller = ApplicationController(mock_main_window)
        controller.shutdown()

        mock_dependencies["player"].stop.assert_called_once()

    def test_shutdown_stops_hotkey_manager(self, mock_main_window, mock_dependencies):
        """Test shutdown stops hotkey manager."""
        controller = ApplicationController(mock_main_window)
        controller.shutdown()

        mock_dependencies["hotkey"].stop.assert_called_once()

    def test_shutdown_stops_event_thread(self, mock_main_window, mock_dependencies):
        """Test shutdown stops event thread."""
        mock_thread = MagicMock()

        controller = ApplicationController(mock_main_window)
        controller.event_thread = mock_thread
        controller.shutdown()

        mock_thread.stop.assert_called_once()

    def test_shutdown_disconnects_device(self, mock_main_window, mock_dependencies):
        """Test shutdown disconnects device."""
        mock_dependencies["device"].is_connected = True

        controller = ApplicationController(mock_main_window)
        controller.shutdown()

        mock_dependencies["device"].disconnect.assert_called_once()


class TestApplicationControllerRawEvent:
    """Tests for raw event handling."""

    def test_on_raw_event_forwards_to_monitor(self, mock_main_window, mock_dependencies):
        """Test raw event is forwarded to monitor widget."""
        mock_state = MagicMock()
        mock_state.joystick_x = 128
        mock_state.joystick_y = 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = (set(), set())

        controller = ApplicationController(mock_main_window)
        controller._on_raw_event(b"\x00" * 8)

        mock_main_window.monitor_widget.on_raw_event.assert_called_once_with(b"\x00" * 8)

    def test_on_raw_event_handles_mr_button(self, mock_main_window, mock_dependencies):
        """Test raw event handles MR button press."""
        mock_state = MagicMock()
        mock_state.joystick_x = 128
        mock_state.joystick_y = 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = ({"MR"}, set())

        controller = ApplicationController(mock_main_window)
        controller._on_raw_event(b"\x00" * 8)

        # MR button should trigger recording toggle
        assert controller._mr_button_held is True

    def test_on_raw_event_highlights_buttons(self, mock_main_window, mock_dependencies):
        """Test raw event highlights pressed buttons."""
        mock_state = MagicMock()
        mock_state.joystick_x = 128
        mock_state.joystick_y = 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = ({"G1", "G2"}, set())

        controller = ApplicationController(mock_main_window)
        controller._on_raw_event(b"\x00" * 8)

        mock_main_window.button_mapper.highlight_button.assert_any_call("G1", True)
        mock_main_window.button_mapper.highlight_button.assert_any_call("G2", True)

    def test_on_raw_event_updates_joystick(self, mock_main_window, mock_dependencies):
        """Test raw event updates joystick visual."""
        mock_state = MagicMock()
        mock_state.joystick_x = 200
        mock_state.joystick_y = 50
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = (set(), set())

        controller = ApplicationController(mock_main_window)
        controller._on_raw_event(b"\x00" * 8)

        mock_main_window.button_mapper.update_joystick.assert_called_with(200, 50)

    def test_on_raw_event_forwards_joystick_when_moved(self, mock_main_window, mock_dependencies):
        """Test raw event forwards joystick to monitor when significantly moved."""
        mock_state = MagicMock()
        mock_state.joystick_x = 200  # > 128 + 20
        mock_state.joystick_y = 100  # Within deadzone from 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = (set(), set())

        controller = ApplicationController(mock_main_window)
        controller._on_raw_event(b"\x00" * 8)

        mock_main_window.monitor_widget.on_joystick_event.assert_called_once_with(200, 100)

    def test_on_raw_event_handles_decode_error(self, mock_main_window, mock_dependencies, capsys):
        """Test raw event handles decoder errors gracefully."""
        mock_dependencies["decoder"].decode_report.side_effect = ValueError("Bad data")

        controller = ApplicationController(mock_main_window)
        controller._on_raw_event(b"\x00" * 8)

        captured = capsys.readouterr()
        assert "Decoder error" in captured.out

    def test_on_raw_event_forwards_to_recorder(self, mock_main_window, mock_dependencies):
        """Test raw event forwards button presses to recorder when recording."""
        mock_state = MagicMock()
        mock_state.joystick_x = 128
        mock_state.joystick_y = 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = ({"G3"}, set())
        mock_dependencies["recorder"].is_recording = True

        controller = ApplicationController(mock_main_window)
        controller._on_raw_event(b"\x00" * 8)

        mock_dependencies["recorder"].on_g13_button_event.assert_called_with("G3", True)


class TestApplicationControllerMissingCoverage:
    """Tests for edge cases to achieve 100% coverage."""

    def test_start_without_device_handle(self, mock_main_window, mock_dependencies):
        """Test start() when device.handle is None (line 97->101)."""
        mock_dependencies["device"].connect.return_value = True
        mock_dependencies["device"].handle = None  # No handle
        mock_dependencies["profile_mgr"].list_profiles.return_value = []

        controller = ApplicationController(mock_main_window)
        controller.start()

        # Should not initialize hardware when no handle
        mock_dependencies["hardware"].initialize.assert_not_called()

    def test_on_raw_event_mr_button_released(self, mock_main_window, mock_dependencies):
        """Test raw event handles MR button release (line 135)."""
        mock_state = MagicMock()
        mock_state.joystick_x = 128
        mock_state.joystick_y = 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = (set(), {"MR"})

        controller = ApplicationController(mock_main_window)
        controller._mr_button_held = True
        controller._on_raw_event(b"\x00" * 8)

        # MR release should clear the flag
        assert controller._mr_button_held is False

    def test_on_raw_event_released_buttons_when_recording(
        self, mock_main_window, mock_dependencies
    ):
        """Test raw event forwards button releases to recorder (line 142)."""
        mock_state = MagicMock()
        mock_state.joystick_x = 128
        mock_state.joystick_y = 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = (set(), {"G5"})
        mock_dependencies["recorder"].is_recording = True

        controller = ApplicationController(mock_main_window)
        controller._on_raw_event(b"\x00" * 8)

        mock_dependencies["recorder"].on_g13_button_event.assert_called_with("G5", False)

    def test_on_raw_event_released_buttons_highlights(self, mock_main_window, mock_dependencies):
        """Test raw event un-highlights released buttons (lines 154-155)."""
        mock_state = MagicMock()
        mock_state.joystick_x = 128
        mock_state.joystick_y = 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = (set(), {"G7", "G8"})

        controller = ApplicationController(mock_main_window)
        controller._on_raw_event(b"\x00" * 8)

        mock_main_window.button_mapper.highlight_button.assert_any_call("G7", False)
        mock_main_window.button_mapper.highlight_button.assert_any_call("G8", False)
        mock_main_window.monitor_widget.on_button_event.assert_any_call("G7", False)
        mock_main_window.monitor_widget.on_button_event.assert_any_call("G8", False)

    def test_save_profile_exception(self, mock_main_window, mock_dependencies):
        """Test save profile handles exception (lines 230-232)."""
        mock_dependencies["profile_mgr"].profile_exists.return_value = False
        mock_dependencies["profile_mgr"].create_profile.side_effect = Exception("Save failed")

        with patch("g13_linux.gui.controllers.app_controller.QMessageBox"):
            controller = ApplicationController(mock_main_window)
            controller._save_profile("bad_profile")

        mock_main_window.set_status.assert_called()

    def test_delete_profile_exception(self, mock_main_window, mock_dependencies):
        """Test delete profile handles exception (lines 250-251)."""
        mock_dependencies["profile_mgr"].delete_profile.side_effect = Exception("Delete failed")

        controller = ApplicationController(mock_main_window)
        controller._delete_profile("locked_profile")

        mock_main_window.set_status.assert_called()

    def test_assign_key_to_button_no_key_selected(self, mock_main_window, mock_dependencies):
        """Test assign key when dialog returns None key (line 259->exit)."""
        with patch("g13_linux.gui.controllers.app_controller.KeySelectorDialog") as mock_dialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = True
            mock_dialog_instance.selected_key = None  # No key selected
            mock_dialog.return_value = mock_dialog_instance

            controller = ApplicationController(mock_main_window)
            controller._assign_key_to_button("G10")

            # Should not update mappings when no key selected
            assert "G10" not in controller.current_mappings
            mock_main_window.button_mapper.set_button_mapping.assert_not_called()

    def test_update_lcd_with_lcd_preview(self, mock_main_window, mock_dependencies):
        """Test LCD update also updates preview (lines 270-274)."""
        mock_lcd = MagicMock()
        mock_lcd._framebuffer = b"\x00" * 860
        mock_dependencies["hardware"].lcd = mock_lcd

        controller = ApplicationController(mock_main_window)
        controller._update_lcd("Test")

        mock_main_window.button_mapper.update_lcd.assert_called_with(b"\x00" * 860)

    def test_update_backlight_color_exception(self, mock_main_window, mock_dependencies):
        """Test backlight color handles exception (lines 284-285)."""
        mock_dependencies["hardware"].set_backlight_color.side_effect = Exception("Color error")

        controller = ApplicationController(mock_main_window)
        controller._update_backlight_color("#FF0000")

        mock_main_window.set_status.assert_called()

    def test_update_backlight_brightness_exception(self, mock_main_window, mock_dependencies):
        """Test backlight brightness handles exception (lines 293-294)."""
        mock_dependencies["hardware"].set_backlight_brightness.side_effect = Exception(
            "Brightness error"
        )

        controller = ApplicationController(mock_main_window)
        controller._update_backlight_brightness(50)

        mock_main_window.set_status.assert_called()

    def test_on_macro_recorded_no_macro_widget(self, mock_main_window, mock_dependencies):
        """Test macro recorded when main_window lacks macro_widget (line 335->exit)."""
        mock_macro = MagicMock()
        mock_macro.step_count = 3

        controller = ApplicationController(mock_main_window)

        # After controller is created, replace main_window with one that lacks macro_widget
        window_without_widget = MagicMock(spec=["set_status"])
        controller.main_window = window_without_widget

        controller._on_macro_recorded(mock_macro)

        mock_dependencies["macro_mgr"].save_macro.assert_called_with(mock_macro)
        # Should not crash when macro_widget is missing

    def test_register_macro_hotkeys_no_hotkey(self, mock_main_window, mock_dependencies):
        """Test registering macros without global_hotkey (line 362->359)."""
        mock_macro = MagicMock()
        mock_macro.global_hotkey = None  # No hotkey set
        mock_macro.id = "macro-no-hotkey"

        mock_dependencies["macro_mgr"].list_macros.return_value = ["macro-no-hotkey"]
        mock_dependencies["macro_mgr"].load_macro.return_value = mock_macro

        controller = ApplicationController(mock_main_window)
        controller._register_all_macro_hotkeys()

        # Should not register when no hotkey
        mock_dependencies["hotkey"].register_hotkey.assert_not_called()

    def test_register_macro_hotkeys_file_not_found(self, mock_main_window, mock_dependencies):
        """Test registering macros handles FileNotFoundError (lines 364-365)."""
        mock_dependencies["macro_mgr"].list_macros.return_value = ["missing-macro"]
        mock_dependencies["macro_mgr"].load_macro.side_effect = FileNotFoundError()

        controller = ApplicationController(mock_main_window)
        # Should not raise
        controller._register_all_macro_hotkeys()

        mock_dependencies["hotkey"].clear_all.assert_called()

    def test_on_hotkey_triggered_macro_not_found(self, mock_main_window, mock_dependencies):
        """Test hotkey trigger handles missing macro (lines 374-375)."""
        mock_dependencies["macro_mgr"].load_macro.side_effect = FileNotFoundError()

        controller = ApplicationController(mock_main_window)
        controller._on_hotkey_triggered("missing-macro")

        mock_main_window.set_status.assert_called()

    def test_on_macro_saved_no_hotkey(self, mock_main_window, mock_dependencies):
        """Test macro saved without hotkey (line 384->exit)."""
        mock_macro = MagicMock()
        mock_macro.id = "macro-1"
        mock_macro.global_hotkey = None  # No hotkey

        controller = ApplicationController(mock_main_window)
        controller._on_macro_saved(mock_macro)

        mock_dependencies["hotkey"].unregister_macro.assert_called_with("macro-1")
        mock_dependencies["hotkey"].register_hotkey.assert_not_called()

    def test_on_macro_saved_register_fails(self, mock_main_window, mock_dependencies):
        """Test macro saved when hotkey registration fails (line 385->exit)."""
        mock_macro = MagicMock()
        mock_macro.id = "macro-1"
        mock_macro.global_hotkey = "ctrl+x"
        mock_macro.name = "Failed Macro"
        mock_dependencies["hotkey"].register_hotkey.return_value = False  # Registration fails

        controller = ApplicationController(mock_main_window)
        controller._on_macro_saved(mock_macro)

        mock_dependencies["hotkey"].register_hotkey.assert_called_with("ctrl+x", "macro-1")
        # Should not set status when registration fails

    def test_shutdown_device_not_connected(self, mock_main_window, mock_dependencies):
        """Test shutdown when device is not connected (line 403->exit)."""
        mock_dependencies["device"].is_connected = False

        controller = ApplicationController(mock_main_window)
        controller.shutdown()

        mock_dependencies["device"].disconnect.assert_not_called()

    def test_on_device_disconnected_no_event_thread(self, mock_main_window, mock_dependencies):
        """Test device disconnection when event_thread is None (line 181->exit)."""
        controller = ApplicationController(mock_main_window)
        controller.event_thread = None  # No event thread

        controller._on_device_disconnected()

        # Should not crash when event_thread is None
        mock_main_window.set_status.assert_called_with("G13 device disconnected")

    def test_update_lcd_no_lcd_hardware(self, mock_main_window, mock_dependencies):
        """Test LCD update when hardware.lcd is None (line 270->274)."""
        mock_dependencies["hardware"].lcd = None

        controller = ApplicationController(mock_main_window)
        controller._update_lcd("Test")

        mock_dependencies["hardware"].set_lcd_text.assert_called_with("Test")
        # Should not update LCD preview when hardware.lcd is None
        mock_main_window.button_mapper.update_lcd.assert_not_called()


class TestPerApplicationProfiles:
    """Tests for per-application profile switching."""

    def test_on_window_monitor_error(self, mock_main_window, mock_dependencies, capsys):
        """Test window monitor error handler prints message."""
        controller = ApplicationController(mock_main_window)
        controller._on_window_monitor_error("xdotool not found")

        captured = capsys.readouterr()
        assert "Window monitor: xdotool not found" in captured.out

    def test_on_app_profile_switch_same_profile(self, mock_main_window, mock_dependencies):
        """Test profile switch is skipped when already on same profile."""
        controller = ApplicationController(mock_main_window)
        controller.current_profile_name = "current_profile"

        # Reset mock to track calls after this point
        mock_dependencies["profile_mgr"].load_profile.reset_mock()

        controller._on_app_profile_switch("current_profile")

        # Should not load profile since already on it
        mock_dependencies["profile_mgr"].load_profile.assert_not_called()

    def test_on_app_profile_switch_profile_not_found(
        self, mock_main_window, mock_dependencies, capsys
    ):
        """Test profile switch when profile doesn't exist."""
        controller = ApplicationController(mock_main_window)
        controller.current_profile_name = "old_profile"
        mock_dependencies["profile_mgr"].profile_exists.return_value = False

        controller._on_app_profile_switch("missing_profile")

        captured = capsys.readouterr()
        assert "Profile 'missing_profile' not found" in captured.out
        mock_dependencies["profile_mgr"].load_profile.assert_not_called()

    def test_on_app_profile_switch_success(self, mock_main_window, mock_dependencies):
        """Test successful automatic profile switch."""
        mock_profile = MagicMock()
        mock_profile.mappings = {"G1": "a"}
        mock_dependencies["profile_mgr"].load_profile.return_value = mock_profile
        mock_dependencies["profile_mgr"].profile_exists.return_value = True

        controller = ApplicationController(mock_main_window)
        controller.current_profile_name = "old_profile"

        controller._on_app_profile_switch("new_profile")

        mock_dependencies["profile_mgr"].load_profile.assert_called_with("new_profile")
        mock_main_window.set_status.assert_called_with("Auto-switched to profile: new_profile")

    def test_set_app_profiles_enabled_starts_monitor(self, mock_main_window, mock_dependencies):
        """Test enabling app profiles starts window monitor."""
        with patch("g13_linux.gui.controllers.app_controller.WindowMonitorThread") as mock_wm_cls:
            mock_wm = MagicMock()
            mock_wm.is_available = True
            mock_wm.isRunning.return_value = False
            mock_wm_cls.return_value = mock_wm

            with patch(
                "g13_linux.gui.controllers.app_controller.AppProfileRulesManager"
            ) as mock_apr_cls:
                mock_apr = MagicMock()
                mock_apr.enabled = False
                mock_apr_cls.return_value = mock_apr

                controller = ApplicationController(mock_main_window)
                controller.set_app_profiles_enabled(True)

                assert mock_apr.enabled is True
                mock_wm.start.assert_called_once()

    def test_set_app_profiles_enabled_stops_monitor(self, mock_main_window, mock_dependencies):
        """Test disabling app profiles stops window monitor."""
        with patch("g13_linux.gui.controllers.app_controller.WindowMonitorThread") as mock_wm_cls:
            mock_wm = MagicMock()
            mock_wm.is_available = True
            mock_wm.isRunning.return_value = True
            mock_wm_cls.return_value = mock_wm

            with patch(
                "g13_linux.gui.controllers.app_controller.AppProfileRulesManager"
            ) as mock_apr_cls:
                mock_apr = MagicMock()
                mock_apr.enabled = True
                mock_apr_cls.return_value = mock_apr

                controller = ApplicationController(mock_main_window)
                controller.set_app_profiles_enabled(False)

                assert mock_apr.enabled is False
                mock_wm.stop.assert_called_once()

    def test_set_app_profiles_enabled_monitor_not_available(
        self, mock_main_window, mock_dependencies
    ):
        """Test enabling when window monitor is not available."""
        with patch("g13_linux.gui.controllers.app_controller.WindowMonitorThread") as mock_wm_cls:
            mock_wm = MagicMock()
            mock_wm.is_available = False
            mock_wm.isRunning.return_value = False
            mock_wm_cls.return_value = mock_wm

            with patch(
                "g13_linux.gui.controllers.app_controller.AppProfileRulesManager"
            ) as mock_apr_cls:
                mock_apr = MagicMock()
                mock_apr_cls.return_value = mock_apr

                controller = ApplicationController(mock_main_window)
                mock_wm.start.reset_mock()

                controller.set_app_profiles_enabled(True)

                # Should not start monitor when not available
                mock_wm.start.assert_not_called()

    def test_shutdown_stops_window_monitor(self, mock_main_window, mock_dependencies):
        """Test shutdown stops window monitor if running."""
        with patch("g13_linux.gui.controllers.app_controller.WindowMonitorThread") as mock_wm_cls:
            mock_wm = MagicMock()
            mock_wm.isRunning.return_value = True
            mock_wm_cls.return_value = mock_wm

            controller = ApplicationController(mock_main_window)
            controller.shutdown()

            mock_wm.stop.assert_called_once()

    def test_shutdown_window_monitor_not_running(self, mock_main_window, mock_dependencies):
        """Test shutdown doesn't stop monitor if not running."""
        with patch("g13_linux.gui.controllers.app_controller.WindowMonitorThread") as mock_wm_cls:
            mock_wm = MagicMock()
            mock_wm.isRunning.return_value = False
            mock_wm_cls.return_value = mock_wm

            controller = ApplicationController(mock_main_window)
            mock_wm.stop.reset_mock()

            controller.shutdown()

            mock_wm.stop.assert_not_called()


class TestJoystickMethods:
    """Tests for joystick-related methods."""

    def test_on_joystick_config_changed_analog(self, mock_main_window, mock_dependencies):
        """Test joystick config change to analog mode."""
        with (
            patch("g13_linux.gui.controllers.app_controller.JoystickHandler") as mock_jh_cls,
            patch("g13_linux.gui.controllers.app_controller.JoystickConfig") as mock_jc_cls,
        ):
            mock_jh = MagicMock()
            mock_jh_cls.return_value = mock_jh

            mock_config = MagicMock()
            mock_config.mode.value = "analog"
            mock_jc_cls.from_dict.return_value = mock_config

            controller = ApplicationController(mock_main_window)

            config_dict = {"mode": "analog", "deadzone": 0.15}
            controller._on_joystick_config_changed(config_dict)

            mock_jc_cls.from_dict.assert_called_with(config_dict)
            mock_jh.set_config.assert_called_with(mock_config)
            mock_jh.stop.assert_called()
            mock_jh.start.assert_called()
            mock_main_window.set_status.assert_called_with("Joystick mode: Analog")

    def test_on_joystick_config_changed_disabled(self, mock_main_window, mock_dependencies):
        """Test joystick config change to disabled mode."""
        with (
            patch("g13_linux.gui.controllers.app_controller.JoystickHandler") as mock_jh_cls,
            patch("g13_linux.gui.controllers.app_controller.JoystickConfig") as mock_jc_cls,
        ):
            mock_jh = MagicMock()
            mock_jh_cls.return_value = mock_jh

            mock_config = MagicMock()
            mock_config.mode.value = "disabled"
            mock_jc_cls.from_dict.return_value = mock_config

            controller = ApplicationController(mock_main_window)
            mock_jh.start.reset_mock()

            config_dict = {"mode": "disabled"}
            controller._on_joystick_config_changed(config_dict)

            mock_jh.stop.assert_called()
            mock_jh.start.assert_not_called()
            mock_main_window.set_status.assert_called_with("Joystick mode: Disabled")

    def test_on_joystick_direction_change(self, mock_main_window, mock_dependencies):
        """Test joystick direction change updates UI."""
        controller = ApplicationController(mock_main_window)
        controller._on_joystick_direction_change("up")

        mock_main_window.joystick_widget.update_direction.assert_called_with("up")

    def test_load_profile_with_joystick_config(self, mock_main_window, mock_dependencies):
        """Test loading profile applies joystick configuration."""
        mock_profile = MagicMock()
        mock_profile.mappings = {"G1": "a"}
        mock_profile.joystick = {"mode": "digital", "deadzone": 0.2}
        mock_dependencies["profile_mgr"].load_profile.return_value = mock_profile

        with (
            patch("g13_linux.gui.controllers.app_controller.JoystickHandler") as mock_jh_cls,
            patch("g13_linux.gui.controllers.app_controller.JoystickConfig") as mock_jc_cls,
        ):
            mock_jh = MagicMock()
            mock_jh_cls.return_value = mock_jh

            mock_config = MagicMock()
            mock_config.mode.value = "digital"
            mock_jc_cls.from_dict.return_value = mock_config

            controller = ApplicationController(mock_main_window)
            mock_jh.start.reset_mock()

            controller._load_profile("test_profile")

            mock_jc_cls.from_dict.assert_called()
            mock_jh.set_config.assert_called_with(mock_config)
            mock_jh.start.assert_called()
            mock_main_window.joystick_widget.set_config.assert_called()


class TestStickButtonHandling:
    """Tests for STICK (joystick click) button handling."""

    def test_stick_button_pressed(self, mock_main_window, mock_dependencies):
        """Test STICK button press is forwarded to joystick handler."""
        mock_state = MagicMock()
        mock_state.joystick_x = 128
        mock_state.joystick_y = 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = ({"STICK"}, set())

        with patch("g13_linux.gui.controllers.app_controller.JoystickHandler") as mock_jh_cls:
            mock_jh = MagicMock()
            mock_jh_cls.return_value = mock_jh

            controller = ApplicationController(mock_main_window)
            controller._on_raw_event(b"\x00" * 8)

            mock_jh.handle_stick_click.assert_called_with(True)

    def test_stick_button_released(self, mock_main_window, mock_dependencies):
        """Test STICK button release is forwarded to joystick handler."""
        mock_state = MagicMock()
        mock_state.joystick_x = 128
        mock_state.joystick_y = 128
        mock_dependencies["decoder"].decode_report.return_value = mock_state
        mock_dependencies["decoder"].get_button_changes.return_value = (set(), {"STICK"})

        with patch("g13_linux.gui.controllers.app_controller.JoystickHandler") as mock_jh_cls:
            mock_jh = MagicMock()
            mock_jh_cls.return_value = mock_jh

            controller = ApplicationController(mock_main_window)
            controller._on_raw_event(b"\x00" * 8)

            mock_jh.handle_stick_click.assert_called_with(False)


class TestAppProfilesWidgetIntegration:
    """Tests for app profiles widget integration."""

    def test_start_connects_app_profiles_widget(self, mock_main_window, mock_dependencies):
        """Test start() connects app_profiles_widget.enabled_changed signal."""
        mock_main_window.app_profiles_widget = MagicMock()
        mock_dependencies["profile_mgr"].list_profiles.return_value = ["example"]

        with patch(
            "g13_linux.gui.controllers.app_controller.AppProfileRulesManager"
        ) as mock_apr_cls:
            mock_apr = MagicMock()
            mock_apr.enabled = False
            mock_apr_cls.return_value = mock_apr

            controller = ApplicationController(mock_main_window)
            mock_dependencies["device"].connect.return_value = False

            controller.start()

            # Verify setup_app_profiles was called
            mock_main_window.setup_app_profiles.assert_called_once()

            # Verify enabled_changed was connected
            mock_main_window.app_profiles_widget.enabled_changed.connect.assert_called_once()

    def test_start_window_monitor_when_enabled(self, mock_main_window, mock_dependencies):
        """Test start() starts window monitor when app profiles enabled."""
        mock_main_window.app_profiles_widget = MagicMock()
        mock_dependencies["profile_mgr"].list_profiles.return_value = []
        mock_dependencies["device"].connect.return_value = False

        with (
            patch("g13_linux.gui.controllers.app_controller.WindowMonitorThread") as mock_wm_cls,
            patch(
                "g13_linux.gui.controllers.app_controller.AppProfileRulesManager"
            ) as mock_apr_cls,
        ):
            mock_wm = MagicMock()
            mock_wm.is_available = True
            mock_wm_cls.return_value = mock_wm

            mock_apr = MagicMock()
            mock_apr.enabled = True
            mock_apr_cls.return_value = mock_apr

            controller = ApplicationController(mock_main_window)
            controller.start()

            mock_wm.start.assert_called_once()
