"""
Application Controller

Main orchestrator connecting models to views.
"""

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QInputDialog, QMessageBox, QWidget

from ...device import find_g13_hidraw_info, probe_device_backends
from ..dialogs.calibration_dialog import CalibrationDialog
from ..dialogs.setup_assistant_dialog import SetupAssistantDialog
from ..models.app_profile_rules import AppProfileRulesManager
from ..models.event_decoder import EventDecoder
from ..models.g13_device import G13Device
from ..models.global_hotkeys import GlobalHotkeyManager
from ..models.hardware_controller import HardwareController
from ..models.joystick_handler import JoystickConfig, JoystickHandler
from ..models.macro_manager import MacroManager
from ..models.macro_player import MacroPlayer
from ..models.macro_recorder import MacroRecorder, RecorderState
from ..models.profile_manager import ProfileManager
from ..models.window_monitor import WindowMonitorThread
from ..widgets.key_selector import KeySelectorDialog
from .device_event_controller import DeviceEventThread


class ApplicationController(QObject):
    """Main application orchestrator - connects models to views"""

    _QUICK_BIND_SEQUENCE = ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8")
    _QUICK_SETUP_MANUAL_TEMPLATE = "Manual (No Preset)"
    _QUICK_SETUP_TEMPLATES: dict[str, dict[str, str | dict]] = {
        _QUICK_SETUP_MANUAL_TEMPLATE: {},
        "MMO Starter (1-8 Keys)": {
            "G1": "KEY_1",
            "G2": "KEY_2",
            "G3": "KEY_3",
            "G4": "KEY_4",
            "G5": "KEY_5",
            "G6": "KEY_6",
            "G7": "KEY_7",
            "G8": "KEY_8",
        },
        "FPS Starter": {
            "G1": "KEY_R",
            "G2": "KEY_F",
            "G3": "KEY_G",
            "G4": "KEY_Q",
            "G5": "KEY_E",
            "G6": "KEY_LEFTSHIFT",
            "G7": "KEY_LEFTCTRL",
            "G8": "KEY_SPACE",
        },
        "Productivity Starter": {
            "G1": {"keys": ["KEY_LEFTCTRL", "KEY_C"], "label": "Copy"},
            "G2": {"keys": ["KEY_LEFTCTRL", "KEY_V"], "label": "Paste"},
            "G3": {"keys": ["KEY_LEFTCTRL", "KEY_X"], "label": "Cut"},
            "G4": {"keys": ["KEY_LEFTCTRL", "KEY_Z"], "label": "Undo"},
            "G5": {"keys": ["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_Z"], "label": "Redo"},
            "G6": {"keys": ["KEY_LEFTCTRL", "KEY_S"], "label": "Save"},
            "G7": "KEY_ENTER",
            "G8": "KEY_ESC",
        },
    }

    def __init__(self, main_window, use_libusb: bool = False):
        super().__init__()
        self.main_window = main_window

        # Models
        self.device = G13Device(use_libusb=use_libusb)
        self.profile_manager = ProfileManager()
        self.event_decoder = EventDecoder()
        self.hardware = HardwareController()

        # Joystick handler
        self.joystick_handler = JoystickHandler()

        # Macro system
        self.macro_recorder = MacroRecorder()
        self.macro_player = MacroPlayer()
        self.macro_manager = MacroManager()
        self.hotkey_manager = GlobalHotkeyManager()

        # Per-application profile switching
        self.window_monitor = WindowMonitorThread()
        self.app_profile_rules = AppProfileRulesManager()
        self.current_profile_name: str | None = None

        # State
        self.current_mappings = {}
        self.current_joystick_config: dict = {}
        self.event_thread = None
        self._mr_button_held = False
        self._setup_assistant_shown = False

        self._connect_signals()

    @staticmethod
    def _default_joystick_config() -> dict:
        """Return canonical default joystick settings."""
        return {
            "mode": "analog",
            "deadzone": 20,
            "sensitivity": 1.0,
            "key_up": "KEY_UP",
            "key_down": "KEY_DOWN",
            "key_left": "KEY_LEFT",
            "key_right": "KEY_RIGHT",
            "allow_diagonals": True,
        }

    @staticmethod
    def _format_mapping_label(mapping: str | dict) -> str:
        """Create short human-readable label for status updates."""
        if isinstance(mapping, dict):
            label = str(mapping.get("label", "")).strip()
            if label:
                return label
            keys = mapping.get("keys", [])
            return "+".join(str(key).replace("KEY_", "") for key in keys)

        return str(mapping).replace("KEY_", "")

    @staticmethod
    def _is_bound_mapping(mapping) -> bool:
        """Return True when mapping represents an active key bind."""
        if not mapping or mapping == "KEY_RESERVED":
            return False

        if isinstance(mapping, dict):
            keys = mapping.get("keys", [])
            if not isinstance(keys, list):
                return False
            return any(isinstance(key, str) and key and key != "KEY_RESERVED" for key in keys)

        return True

    @staticmethod
    def _normalize_mapping(mapping):
        """Normalize mapping shape so conflict checks compare semantically."""
        if isinstance(mapping, dict):
            keys = mapping.get("keys", [])
            if not isinstance(keys, list):
                keys = []
            filtered_keys = tuple(str(key) for key in keys if isinstance(key, str) and key)
            return ("combo", filtered_keys)
        return ("simple", mapping)

    def _mappings_equal(self, left, right) -> bool:
        """Compare two mapping payloads, handling dict/string formats."""
        return self._normalize_mapping(left) == self._normalize_mapping(right)

    def _find_conflicting_buttons(self, target_button_id: str, new_mapping) -> list[str]:
        """Find other buttons already mapped to the same target mapping."""
        conflicts = []
        for button_id, existing_mapping in self.current_mappings.items():
            if button_id == target_button_id:
                continue
            if not self._is_bound_mapping(existing_mapping):
                continue
            if self._mappings_equal(existing_mapping, new_mapping):
                conflicts.append(button_id)
        return conflicts

    def _bound_mapping_count(self) -> int:
        """Count bound buttons in current mappings."""
        return sum(
            1 for mapping in self.current_mappings.values() if self._is_bound_mapping(mapping)
        )

    def _refresh_session_summary(self):
        """Push current profile/binding/joystick state into main window summary."""
        profile_name = self.current_profile_name
        bound_count = self._bound_mapping_count()
        joystick_mode = self.current_joystick_config.get("mode", "analog")
        self.main_window.set_session_summary(profile_name, bound_count, joystick_mode)

    def _connect_signals(self):
        """Wire up all signals between models and views"""

        # Device events
        self.device.device_connected.connect(self._on_device_connected)
        self.device.device_disconnected.connect(self._on_device_disconnected)
        self.device.raw_event_received.connect(self._on_raw_event)
        self.device.error_occurred.connect(self._on_error)

        # Profile UI
        profile_widget = self.main_window.profile_widget
        profile_widget.profile_selected.connect(self._load_profile)
        profile_widget.profile_saved.connect(self._save_profile)
        profile_widget.profile_deleted.connect(self._delete_profile)
        profile_widget.profile_export_requested.connect(self._export_profile)
        profile_widget.profile_import_requested.connect(self._import_profile)

        # Button mapper
        mapper_widget = self.main_window.button_mapper
        mapper_widget.button_clicked.connect(self._assign_key_to_button)
        mapper_widget.button_unbind_requested.connect(self._clear_button_mapping)

        # Hardware controls
        hw_widget = self.main_window.hardware_widget
        hw_widget.lcd_text_changed.connect(self._update_lcd)
        hw_widget.backlight_color_changed.connect(self._update_backlight_color)
        hw_widget.backlight_brightness_changed.connect(self._update_backlight_brightness)
        hw_widget.calibration_requested.connect(self._open_calibration_dialog)

        # Macro recorder signals
        self.macro_recorder.state_changed.connect(self._on_recorder_state_changed)
        self.macro_recorder.recording_complete.connect(self._on_macro_recorded)
        self.macro_recorder.error_occurred.connect(self._on_error)

        # Macro player signals
        self.macro_player.playback_complete.connect(self._on_playback_complete)
        self.macro_player.error_occurred.connect(self._on_error)

        # Global hotkey signals
        self.hotkey_manager.hotkey_triggered.connect(self._on_hotkey_triggered)
        self.hotkey_manager.error_occurred.connect(self._on_error)

        # Macro editor signals - refresh hotkeys when macros are saved
        self.main_window.macro_widget.macro_saved.connect(self._on_macro_saved)

        # Joystick settings
        self.main_window.joystick_widget.config_changed.connect(self._on_joystick_config_changed)

        # Diagnostics shortcut from status banner
        if hasattr(self.main_window, "diagnostics_requested"):
            self.main_window.diagnostics_requested.connect(self._run_device_diagnostics)
        if hasattr(self.main_window, "quick_setup_requested"):
            self.main_window.quick_setup_requested.connect(self._run_quick_binding_wizard)

        # Wire joystick direction callback to update UI
        self.joystick_handler.on_direction_change = self._on_joystick_direction_change

        # Per-application profile switching
        self.window_monitor.window_changed.connect(self.app_profile_rules.on_window_changed)
        self.window_monitor.monitor_error.connect(self._on_window_monitor_error)
        self.app_profile_rules.profile_switch_requested.connect(self._on_app_profile_switch)

    def start(self):
        """Initialize application"""
        # Connect to device
        if self.device.connect():
            self.main_window.set_status("G13 device connected")
            self.main_window.set_device_connected(True, "G13 device connected")

            # Initialize hardware controller
            if self.device.handle:
                self.hardware.initialize(self.device.handle)

            # Start event thread
            self.event_thread = DeviceEventThread(self.device.handle)
            self.event_thread.event_received.connect(self._on_raw_event)
            self.event_thread.error_occurred.connect(self._on_error)
            self.event_thread.start()
        else:
            self.main_window.set_status("No G13 device found")
            self.main_window.set_device_connected(False, "No G13 device found")
            self._show_setup_assistant_if_needed()

        # Load available profiles
        profiles = self.profile_manager.list_profiles()
        self.main_window.profile_widget.update_profile_list(profiles)
        self.current_joystick_config = self._default_joystick_config()
        self._refresh_session_summary()

        # Set up app profiles widget
        self.main_window.setup_app_profiles(self.app_profile_rules, profiles)
        if self.main_window.app_profiles_widget:
            self.main_window.app_profiles_widget.enabled_changed.connect(
                self.set_app_profiles_enabled
            )

        # Load example profile if exists
        if "example" in profiles:
            self._load_profile("example")

        # Register global hotkeys from saved macros
        self._register_all_macro_hotkeys()
        self.hotkey_manager.start()

        # Start window monitor for per-app profiles (if enabled and available)
        if self.app_profile_rules.enabled and self.window_monitor.is_available:
            self.window_monitor.start()

    def _handle_mr_button(self, pressed: list, released: list):
        """Handle MR button press/release for macro recording."""
        if "MR" in pressed:
            self._on_mr_button_pressed()
        if "MR" in released:
            self._on_mr_button_released()

    def _forward_to_recorder(self, pressed: list, released: list):
        """Forward button events to macro recorder if recording."""
        if not self.macro_recorder.is_recording:
            return
        for button_id in pressed:
            self.macro_recorder.on_g13_button_event(button_id, True)
        for button_id in released:
            self.macro_recorder.on_g13_button_event(button_id, False)

    def _update_button_ui(self, pressed: list, released: list):
        """Update button highlights and monitor for press/release events."""
        for button_id in pressed:
            self.main_window.button_mapper.highlight_button(button_id, True)
            self.main_window.monitor_widget.on_button_event(button_id, True)
        for button_id in released:
            self.main_window.button_mapper.highlight_button(button_id, False)
            self.main_window.monitor_widget.on_button_event(button_id, False)

    def _handle_joystick_events(self, state, pressed: list, released: list):
        """Handle joystick position and click events."""
        self.main_window.button_mapper.update_joystick(state.joystick_x, state.joystick_y)
        self.joystick_handler.update(state.joystick_x, state.joystick_y)

        if "STICK" in pressed:
            self.joystick_handler.handle_stick_click(True)
        if "STICK" in released:
            self.joystick_handler.handle_stick_click(False)

        if abs(state.joystick_x - 128) > 20 or abs(state.joystick_y - 128) > 20:
            self.main_window.monitor_widget.on_joystick_event(state.joystick_x, state.joystick_y)

    @pyqtSlot(bytes)
    def _on_raw_event(self, data: bytes):
        """Handle raw HID event from device"""
        self.main_window.monitor_widget.on_raw_event(data)

        try:
            state = self.event_decoder.decode_report(data)
            pressed, released = self.event_decoder.get_button_changes(state)

            self._handle_mr_button(pressed, released)
            self._forward_to_recorder(pressed, released)
            for button_id in pressed:
                self._check_macro_trigger(button_id)
            self._update_button_ui(pressed, released)
            self._handle_joystick_events(state, pressed, released)

        except Exception as e:
            print(f"Decoder error: {e}")

    @pyqtSlot()
    def _on_device_connected(self):
        """Handle device connection"""
        self.main_window.set_status("G13 device connected")
        self.main_window.set_device_connected(True, "G13 device connected")

    @pyqtSlot()
    def _on_device_disconnected(self):
        """Handle device disconnection"""
        self.main_window.set_status("G13 device disconnected")
        self.main_window.set_device_connected(False, "G13 device disconnected")
        if self.event_thread:
            self.event_thread.stop()

    @pyqtSlot(str)
    def _on_error(self, message: str):
        """Handle errors"""
        self.main_window.set_status(f"Error: {message}")
        print(f"ERROR: {message}")

    @pyqtSlot()
    def _run_device_diagnostics(self):
        """Open setup assistant with backend diagnostics and quick actions."""
        self._open_setup_assistant(update_status=True)

    @pyqtSlot()
    def _run_quick_binding_wizard(self):
        """Guide users through mapping core buttons with a minimal-click flow."""
        sequence = list(self._QUICK_BIND_SEQUENCE)
        total = len(sequence)
        if total == 0:
            self.main_window.set_status("Quick setup has no configured steps")
            return

        start_reply = QMessageBox.question(
            self.main_window,
            "Quick Setup Wizard",
            (
                f"Map your core buttons in a guided flow ({total} steps: {', '.join(sequence)}).\n\n"
                "Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if start_reply != QMessageBox.StandardButton.Yes:
            self.main_window.set_status("Quick setup canceled")
            return

        template_name = self._select_quick_setup_template()
        if not template_name:
            self.main_window.set_status("Quick setup canceled")
            return

        updated = self._apply_quick_setup_template(template_name)
        skipped = 0

        if template_name != self._QUICK_SETUP_MANUAL_TEMPLATE:
            refine_reply = QMessageBox.question(
                self.main_window,
                "Quick Setup Wizard",
                (
                    f"Applied template: {template_name}\n\n"
                    "Yes: continue with guided per-button review.\n"
                    "No: finish now.\n"
                    "Cancel: stop quick setup."
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if refine_reply == QMessageBox.StandardButton.Cancel:
                self.main_window.set_status(
                    f"Quick setup stopped: updated {updated}/{total}, skipped {skipped}"
                )
                return
            if refine_reply == QMessageBox.StandardButton.No:
                self._maybe_save_quick_setup_profile(updated, total, skipped)
                return

        for index, button_id in enumerate(sequence, start=1):
            self.main_window.set_status(f"Quick setup {index}/{total}: map {button_id}")
            current_mapping = self.current_mappings.get(button_id)
            dialog = KeySelectorDialog(button_id, current_mapping, self.main_window)
            dialog.setWindowTitle(f"Quick Setup {index}/{total} - {button_id}")

            if not dialog.exec():
                skip_reply = QMessageBox.question(
                    self.main_window,
                    "Quick Setup Wizard",
                    (
                        f"No binding selected for {button_id}.\n\n"
                        "Yes: skip this button and continue.\n"
                        "No: stop quick setup."
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if skip_reply == QMessageBox.StandardButton.Yes:
                    skipped += 1
                    continue
                self.main_window.set_status(
                    f"Quick setup stopped: updated {updated}/{total}, skipped {skipped}"
                )
                return

            selected_key = dialog.selected_key
            if not selected_key:
                skipped += 1
                continue

            if self._apply_mapping_to_button(button_id, selected_key):
                updated += 1
            else:
                skipped += 1

        self._maybe_save_quick_setup_profile(updated, total, skipped)

    def _select_quick_setup_template(self) -> str | None:
        """Prompt for a starter template and return selected template name."""
        options = list(self._QUICK_SETUP_TEMPLATES.keys())
        selected, ok = QInputDialog.getItem(
            self.main_window,
            "Quick Setup Template",
            "Select a starter template:",
            options,
            0,
            False,
        )
        if not ok:
            return None
        return selected

    def _apply_quick_setup_template(self, template_name: str) -> int:
        """Apply starter template mappings. Returns number of applied bindings."""
        template = self._QUICK_SETUP_TEMPLATES.get(template_name, {})
        if not template:
            return 0

        applied = 0
        for button_id in self._QUICK_BIND_SEQUENCE:
            mapping = template.get(button_id)
            if not mapping:
                continue
            if self._apply_mapping_to_button(button_id, mapping):
                applied += 1
        return applied

    def _maybe_save_quick_setup_profile(self, updated: int, total: int, skipped: int):
        """Optionally save wizard results to a profile, otherwise post completion status."""
        save_reply = QMessageBox.question(
            self.main_window,
            "Quick Setup Wizard",
            "Save these quick setup mappings to a profile now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if save_reply != QMessageBox.StandardButton.Yes:
            self.main_window.set_status(
                f"Quick setup complete: updated {updated}/{total}, skipped {skipped}"
            )
            return

        suggested_name = self.current_profile_name or "quick_setup"
        profile_name, ok = QInputDialog.getText(
            self.main_window,
            "Save Quick Setup Profile",
            "Profile name:",
            text=suggested_name,
        )
        profile_name = profile_name.strip()
        if not ok or not profile_name:
            self.main_window.set_status(
                f"Quick setup complete: updated {updated}/{total}, skipped {skipped}"
            )
            return

        self._save_profile(profile_name)
        self.main_window.set_status(
            f"Quick setup saved to profile '{profile_name}' ({updated}/{total} updated, {skipped} skipped)"
        )

    def _build_device_diagnostics_report(self) -> tuple[str, list[str]]:
        """Build human-readable diagnostics details and list of available backends."""
        prefer_libusb = bool(getattr(self.device, "_use_libusb", False))
        probe_order = "libusb -> hidraw" if prefer_libusb else "hidraw -> libusb"
        hidraw_info = find_g13_hidraw_info()
        diagnostics = probe_device_backends(use_libusb=prefer_libusb)

        lines = ["G13 diagnostics", f"Probe order: {probe_order}"]
        if hidraw_info:
            lines.append(f"Hidraw path: {hidraw_info['path']}")
            access = []
            access.append("r" if hidraw_info.get("readable") else "-")
            access.append("w" if hidraw_info.get("writable") else "-")
            source = hidraw_info.get("detection_source") or "unknown"
            lines.append(f"Hidraw access: {''.join(access)} (detected via {source})")
        else:
            lines.append("Hidraw path: not found")

        ok_backends = []
        for result in diagnostics:
            backend = result.get("backend", "unknown")
            if result.get("ok"):
                ok_backends.append(backend)
                lines.append(f"{backend}: OK")
            else:
                error = result.get("error") or "unknown error"
                lines.append(f"{backend}: FAILED ({error})")

        if ok_backends:
            lines.append("")
            lines.append("At least one backend can open the device.")
            lines.append("If button input still fails, try libusb mode with sudo.")
            lines.append("Example: sudo g13-linux-gui --libusb")
            return "\n".join(lines), ok_backends

        lines.append("")
        lines.append("No backend could open the device.")
        lines.append("Checklist:")
        lines.append("1) Confirm the G13 is connected and re-plug it.")
        lines.append("2) Install/reload udev rules:")
        lines.append("   sudo cp udev/99-logitech-g13.rules /etc/udev/rules.d/")
        lines.append("   sudo udevadm control --reload-rules && sudo udevadm trigger")
        lines.append("3) Try libusb mode with elevated permissions:")
        lines.append("   sudo g13-linux-gui --libusb")
        lines.append("4) From terminal, run: g13-linux doctor")
        return "\n".join(lines), ok_backends

    def _open_setup_assistant(self, update_status: bool):
        """Open setup assistant dialog and optionally post status summary."""
        details, ok_backends = self._build_device_diagnostics_report()
        parent = self.main_window if isinstance(self.main_window, QWidget) else None
        dialog = SetupAssistantDialog(
            diagnostics_text=details,
            has_available_backend=bool(ok_backends),
            parent=parent,
        )
        dialog.exec()

        if not update_status:
            return

        if ok_backends:
            self.main_window.set_status(
                f"Diagnostics complete: available backend(s): {', '.join(ok_backends)}"
            )
        else:
            self.main_window.set_status("Diagnostics complete: no available backend")

    def _show_setup_assistant_if_needed(self):
        """Show setup assistant once per session after initial connection failure."""
        if self._setup_assistant_shown:
            return
        self._setup_assistant_shown = True
        self._open_setup_assistant(update_status=False)

    @pyqtSlot(str)
    def _load_profile(self, profile_name: str):
        """Load a profile and update UI"""
        try:
            profile = self.profile_manager.load_profile(profile_name)
            self.current_profile_name = profile_name
            self.current_mappings = profile.mappings.copy()

            # Update button mapper
            for button_id, key_name in profile.mappings.items():
                self.main_window.button_mapper.set_button_mapping(button_id, key_name)

            # Load joystick configuration
            self.current_joystick_config = self._default_joystick_config()
            raw_joystick_config = profile.joystick.copy() if profile.joystick else {}
            if raw_joystick_config:
                config = JoystickConfig.from_dict(raw_joystick_config)
                # Normalize legacy profile formats into canonical joystick schema.
                self.current_joystick_config = config.to_dict()
                self.joystick_handler.set_config(config)
                # Start joystick handler if not disabled
                if config.mode.value != "disabled":
                    self.joystick_handler.start()
            # Update joystick settings UI
            self.main_window.joystick_widget.set_config(self.current_joystick_config)
            self._refresh_session_summary()

            self.main_window.set_status(f"Loaded profile: {profile_name}")

        except Exception as e:
            self._on_error(f"Failed to load profile: {e}")
            QMessageBox.warning(
                self.main_window,
                "Profile Error",
                f"Failed to load profile '{profile_name}':\n{e}",
            )

    @pyqtSlot(str)
    def _save_profile(self, profile_name: str):
        """Save current configuration as profile"""
        try:
            # Create or update profile
            if self.profile_manager.profile_exists(profile_name):
                profile = self.profile_manager.load_profile(profile_name)
            else:
                profile = self.profile_manager.create_profile(profile_name)

            profile.mappings = self.current_mappings.copy()
            if self.current_joystick_config:
                profile.joystick = self.current_joystick_config.copy()
            elif not getattr(profile, "joystick", None):
                profile.joystick = self._default_joystick_config()
            self.profile_manager.save_profile(profile, profile_name)
            self.current_profile_name = profile_name
            self._refresh_session_summary()

            # Refresh profile list
            profiles = self.profile_manager.list_profiles()
            self.main_window.profile_widget.update_profile_list(profiles)

            self.main_window.set_status(f"Saved profile: {profile_name}")

        except Exception as e:
            self._on_error(f"Failed to save profile: {e}")
            QMessageBox.warning(
                self.main_window,
                "Profile Error",
                f"Failed to save profile '{profile_name}':\n{e}",
            )

    @pyqtSlot(str)
    def _delete_profile(self, profile_name: str):
        """Delete a profile"""
        try:
            self.profile_manager.delete_profile(profile_name)

            # Refresh profile list
            profiles = self.profile_manager.list_profiles()
            self.main_window.profile_widget.update_profile_list(profiles)

            self.main_window.set_status(f"Deleted profile: {profile_name}")

        except Exception as e:
            self._on_error(f"Failed to delete profile: {e}")

    @pyqtSlot(str, str)
    def _export_profile(self, profile_name: str, export_path: str):
        """Export a profile to an external file"""
        try:
            self.profile_manager.export_profile(profile_name, export_path)
            self.main_window.set_status(f"Exported profile: {profile_name}")
        except Exception as e:
            self._on_error(f"Failed to export profile: {e}")

    @pyqtSlot(str)
    def _import_profile(self, import_path: str):
        """Import a profile from an external file"""
        try:
            imported_name = self.profile_manager.import_profile(import_path)

            # Refresh profile list
            profiles = self.profile_manager.list_profiles()
            self.main_window.profile_widget.update_profile_list(profiles)

            self.main_window.set_status(f"Imported profile: {imported_name}")
        except Exception as e:
            self._on_error(f"Failed to import profile: {e}")

    @pyqtSlot(str)
    def _assign_key_to_button(self, button_id: str):
        """Open key selector for button"""
        current_mapping = self.current_mappings.get(button_id)
        dialog = KeySelectorDialog(button_id, current_mapping, self.main_window)
        if dialog.exec():
            key_name = dialog.selected_key
            if key_name:
                self._apply_mapping_to_button(button_id, key_name)

    def _apply_mapping_to_button(self, button_id: str, key_name: str | dict) -> bool:
        """Apply selected mapping payload to a button. Returns True when applied."""
        if key_name == "KEY_RESERVED":
            self._clear_button_mapping(button_id)
            return True

        conflict_buttons = self._find_conflicting_buttons(button_id, key_name)
        status_suffix = ""
        if conflict_buttons:
            conflict_list = ", ".join(conflict_buttons)
            display = self._format_mapping_label(key_name)
            choice = QMessageBox.question(
                self.main_window,
                "Binding Already In Use",
                (
                    f"{display} is already mapped to: {conflict_list}\n\n"
                    f"Yes: move binding to {button_id} and clear previous button(s).\n"
                    "No: keep duplicate mapping.\n"
                    "Cancel: keep existing mappings."
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )

            if choice == QMessageBox.StandardButton.Cancel:
                self.main_window.set_status(f"Mapping for {button_id} unchanged")
                return False

            if choice == QMessageBox.StandardButton.Yes:
                for conflict_button_id in conflict_buttons:
                    self.current_mappings.pop(conflict_button_id, None)
                    self.main_window.button_mapper.set_button_mapping(conflict_button_id, None)
                status_suffix = f" (moved from {conflict_list})"
            else:
                status_suffix = f" (also on {conflict_list})"

        self.current_mappings[button_id] = key_name
        self.main_window.button_mapper.set_button_mapping(button_id, key_name)
        display = self._format_mapping_label(key_name)
        self._refresh_session_summary()
        self.main_window.set_status(f"Mapped {button_id} to {display}{status_suffix}")
        return True

    @pyqtSlot(str)
    def _clear_button_mapping(self, button_id: str):
        """Clear mapping for one G13 button."""
        had_mapping = button_id in self.current_mappings
        self.current_mappings.pop(button_id, None)
        self.main_window.button_mapper.set_button_mapping(button_id, None)

        if had_mapping:
            self.main_window.set_status(f"Cleared mapping for {button_id}")
        else:
            self.main_window.set_status(f"{button_id} is already unbound")
        self._refresh_session_summary()

    @pyqtSlot(str)
    def _update_lcd(self, text: str):
        """Send text to LCD and update preview"""
        try:
            self.hardware.set_lcd_text(text)
            # Update LCD preview in button mapper
            if self.hardware.lcd:
                self.main_window.button_mapper.update_lcd(self.hardware.lcd._framebuffer)
            self.main_window.set_status("LCD updated")
        except Exception as e:
            self._on_error(f"LCD error: {e}")

    @pyqtSlot(str)
    def _update_backlight_color(self, color_hex: str):
        """Update backlight color"""
        try:
            self.hardware.set_backlight_color(color_hex)
            self.main_window.set_status(f"Backlight color: {color_hex}")
        except Exception as e:
            self._on_error(f"Backlight error: {e}")

    @pyqtSlot(int)
    def _update_backlight_brightness(self, brightness: int):
        """Update backlight brightness"""
        try:
            self.hardware.set_backlight_brightness(brightness)
            self.main_window.set_status(f"Backlight brightness: {brightness}%")
        except Exception as e:
            self._on_error(f"Backlight error: {e}")

    @pyqtSlot()
    def _open_calibration_dialog(self):
        """Open the button position calibration dialog."""
        dialog = CalibrationDialog(self.main_window)
        dialog.calibration_complete.connect(self._on_calibration_complete)
        dialog.exec()

    @pyqtSlot(dict)
    def _on_calibration_complete(self, positions: dict):
        """Handle completed calibration."""
        if not positions:
            return

        # Convert positions to the format expected by button mapper
        button_positions = {}
        lcd_area = None
        joystick_area = None

        for name, (x, y, w, h) in positions.items():
            pos_dict = {"x": x, "y": y, "width": w, "height": h}
            if name == "LCD":
                lcd_area = pos_dict
            elif name == "STICK":
                joystick_area = pos_dict
                button_positions[name] = pos_dict
            else:
                button_positions[name] = pos_dict

        # Update button mapper with new positions
        self.main_window.button_mapper.update_button_positions(
            button_positions, lcd_area, joystick_area
        )

        self.main_window.set_status(f"Calibration applied: {len(button_positions)} buttons")

        # Show message about saving
        QMessageBox.information(
            self.main_window,
            "Calibration Applied",
            f"Button positions have been updated ({len(button_positions)} buttons).\n\n"
            "To make this permanent, copy the generated code from the\n"
            "calibration dialog and save it to:\n"
            "src/g13_linux/gui/resources/g13_layout.py",
        )

    # Macro recording methods

    def _on_mr_button_pressed(self):
        """Handle MR button press - toggle recording"""
        self._mr_button_held = True

        if self.macro_recorder.is_recording:
            # Stop recording
            self.macro_recorder.stop_recording()
        else:
            # Start recording
            self.macro_recorder.start_recording()
            self.main_window.set_status("Macro recording started - press MR again to stop")

    def _on_mr_button_released(self):
        """Handle MR button release"""
        self._mr_button_held = False

    @pyqtSlot(object)
    def _on_recorder_state_changed(self, state: RecorderState):
        """Update UI based on recorder state"""
        status_messages = {
            RecorderState.IDLE: "Ready",
            RecorderState.WAITING: "Macro armed - press any key to start recording",
            RecorderState.RECORDING: "Recording macro...",
            RecorderState.SAVING: "Saving macro...",
        }
        self.main_window.set_status(status_messages.get(state, ""))

    @pyqtSlot(object)
    def _on_macro_recorded(self, macro):
        """Handle completed macro recording"""
        # Save to manager
        self.macro_manager.save_macro(macro)
        self.main_window.set_status(f"Macro recorded: {macro.step_count} steps")

        # Refresh macro list in UI
        if hasattr(self.main_window, "macro_widget"):
            self.main_window.macro_widget.refresh_macro_list()

    def _check_macro_trigger(self, button_id: str):
        """Check if button triggers a macro and play it"""
        mapping = self.current_mappings.get(button_id)
        if isinstance(mapping, dict) and "macro" in mapping:
            macro_id = mapping["macro"]
            try:
                macro = self.macro_manager.load_macro(macro_id)
                self.macro_player.play(macro)
            except FileNotFoundError:
                self._on_error(f"Macro not found: {macro_id}")

    @pyqtSlot()
    def _on_playback_complete(self):
        """Handle macro playback completion"""
        self.main_window.set_status("Macro playback complete")

    # Global hotkey methods

    def _register_all_macro_hotkeys(self) -> None:
        """Load all macros and register their hotkeys."""
        self.hotkey_manager.clear_all()
        for macro_id in self.macro_manager.list_macros():
            try:
                macro = self.macro_manager.load_macro(macro_id)
                if macro.global_hotkey:
                    self.hotkey_manager.register_hotkey(macro.global_hotkey, macro.id)
            except FileNotFoundError:
                pass

    @pyqtSlot(str)
    def _on_hotkey_triggered(self, macro_id: str) -> None:
        """Handle global hotkey press - play the macro."""
        try:
            macro = self.macro_manager.load_macro(macro_id)
            self.macro_player.play(macro)
            self.main_window.set_status(f"Hotkey triggered: {macro.name}")
        except FileNotFoundError:
            self._on_error(f"Macro not found: {macro_id}")

    @pyqtSlot(object)
    def _on_macro_saved(self, macro) -> None:
        """Handle macro save - update hotkey registrations."""
        # Unregister old hotkey for this macro
        self.hotkey_manager.unregister_macro(macro.id)

        # Register new hotkey if set
        if macro.global_hotkey:
            if self.hotkey_manager.register_hotkey(macro.global_hotkey, macro.id):
                self.main_window.set_status(
                    f"Hotkey registered: {macro.global_hotkey} → {macro.name}"
                )

    # Joystick methods

    @pyqtSlot(dict)
    def _on_joystick_config_changed(self, config_dict: dict) -> None:
        """Handle joystick settings change from UI."""
        config = JoystickConfig.from_dict(config_dict)
        self.current_joystick_config = config.to_dict()
        self.joystick_handler.set_config(config)

        # Restart handler with new config
        self.joystick_handler.stop()
        if config.mode.value != "disabled":
            self.joystick_handler.start()

        mode_name = config.mode.value.capitalize()
        self._refresh_session_summary()
        self.main_window.set_status(f"Joystick mode: {mode_name}")

    def _on_joystick_direction_change(self, direction: str) -> None:
        """Handle joystick direction change - update UI indicator."""
        self.main_window.joystick_widget.update_direction(direction)

    # Per-application profile methods

    @pyqtSlot(str)
    def _on_window_monitor_error(self, message: str) -> None:
        """Handle window monitor error."""
        print(f"Window monitor: {message}")
        # Don't show message box - just disable the feature silently

    @pyqtSlot(str)
    def _on_app_profile_switch(self, profile_name: str) -> None:
        """Handle automatic profile switch from window monitor."""
        if profile_name == self.current_profile_name:
            return  # Already on this profile

        if not self.profile_manager.profile_exists(profile_name):
            print(f"App profile switch: Profile '{profile_name}' not found")
            return

        self._load_profile(profile_name)
        self.main_window.set_status(f"Auto-switched to profile: {profile_name}")

    def set_app_profiles_enabled(self, enabled: bool) -> None:
        """Enable or disable per-application profile switching."""
        self.app_profile_rules.enabled = enabled
        if enabled and self.window_monitor.is_available:
            if not self.window_monitor.isRunning():
                self.window_monitor.start()
        else:
            if self.window_monitor.isRunning():
                self.window_monitor.stop()

    def shutdown(self):
        """Cleanup on application exit"""
        # Stop any active recording/playback
        if self.macro_recorder.is_recording:
            self.macro_recorder.cancel()
        if self.macro_player.is_playing:
            self.macro_player.stop()

        # Stop joystick handler
        self.joystick_handler.stop()

        # Stop hotkey listener
        self.hotkey_manager.stop()

        # Stop window monitor
        if self.window_monitor.isRunning():
            self.window_monitor.stop()

        if self.event_thread:
            self.event_thread.stop()
        if self.device.is_connected:
            self.device.disconnect()
