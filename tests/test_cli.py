"""Tests for CLI commands."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from g13_linux.cli import (
    COLOR_PRESETS,
    cmd_color,
    cmd_doctor,
    cmd_lcd,
    cmd_profile,
    cmd_run,
    main,
)


class TestColorPresets:
    """Tests for color presets."""

    def test_has_common_colors(self):
        """Test COLOR_PRESETS has common colors."""
        assert "red" in COLOR_PRESETS
        assert "green" in COLOR_PRESETS
        assert "blue" in COLOR_PRESETS
        assert "white" in COLOR_PRESETS
        assert "off" in COLOR_PRESETS

    def test_red_is_correct(self):
        """Test red preset is correct RGB."""
        assert COLOR_PRESETS["red"] == (255, 0, 0)

    def test_green_is_correct(self):
        """Test green preset is correct RGB."""
        assert COLOR_PRESETS["green"] == (0, 255, 0)

    def test_blue_is_correct(self):
        """Test blue preset is correct RGB."""
        assert COLOR_PRESETS["blue"] == (0, 0, 255)

    def test_off_is_black(self):
        """Test off preset is black (0,0,0)."""
        assert COLOR_PRESETS["off"] == (0, 0, 0)


class TestCmdRun:
    """Tests for cmd_run command."""

    def test_cmd_run_opens_device(self, capsys):
        """Test cmd_run opens G13 device in simple mode."""
        mock_handle = MagicMock()
        # Make read() raise KeyboardInterrupt to exit the loop
        mock_handle.read.side_effect = KeyboardInterrupt

        with (
            patch("g13_linux.device.open_g13", return_value=mock_handle) as mock_open,
            patch("g13_linux.mapper.G13Mapper"),
        ):
            args = MagicMock()
            args.simple = True  # Test simple mode which calls open_g13
            cmd_run(args)

        mock_open.assert_called_once()
        mock_handle.close.assert_called_once()

    def test_cmd_run_handles_device_error(self, capsys):
        """Test cmd_run handles device open error in simple mode."""
        with patch("g13_linux.device.open_g13", side_effect=Exception("Device not found")):
            args = MagicMock()
            args.simple = True  # Test simple mode

            with pytest.raises(SystemExit) as exc_info:
                cmd_run(args)

            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "Could not open G13" in captured.err

    def test_cmd_run_processes_events(self, capsys):
        """Test cmd_run processes events until KeyboardInterrupt in simple mode."""
        mock_handle = MagicMock()
        mock_mapper = MagicMock()

        call_count = [0]

        def fake_read(timeout_ms=None):
            call_count[0] += 1
            if call_count[0] >= 3:
                raise KeyboardInterrupt
            return b"\x00" * 8

        mock_handle.read.side_effect = fake_read

        with (
            patch("g13_linux.device.open_g13", return_value=mock_handle),
            patch("g13_linux.mapper.G13Mapper", return_value=mock_mapper),
        ):
            args = MagicMock()
            args.simple = True  # Test simple mode
            cmd_run(args)

        assert mock_mapper.handle_raw_report.call_count == 2

    def test_cmd_run_full_mode_passes_libusb_flag(self):
        """Full daemon mode should forward --libusb preference."""
        mock_daemon = MagicMock()
        with patch("g13_linux.daemon.G13Daemon", return_value=mock_daemon) as mock_daemon_cls:
            args = MagicMock()
            args.simple = False
            args.no_server = False
            args.server_host = "127.0.0.1"
            args.server_port = 8765
            args.static_dir = None
            args.libusb = True
            cmd_run(args)

        mock_daemon_cls.assert_called_once_with(
            enable_server=True,
            server_host="127.0.0.1",
            server_port=8765,
            static_dir=None,
            use_libusb=True,
        )
        mock_daemon.run.assert_called_once()


class TestCmdLcd:
    """Tests for cmd_lcd command."""

    def test_cmd_lcd_clear(self, capsys):
        """Test cmd_lcd with --clear flag."""
        mock_device = MagicMock()
        mock_lcd = MagicMock()

        with (
            patch("g13_linux.device.open_g13", return_value=mock_device),
            patch("g13_linux.hardware.lcd.G13LCD", return_value=mock_lcd),
        ):
            args = MagicMock()
            args.clear = True
            args.text = None

            cmd_lcd(args)

        mock_lcd.clear.assert_called_once()
        mock_device.close.assert_called_once()

    def test_cmd_lcd_with_text(self, capsys):
        """Test cmd_lcd with text."""
        mock_device = MagicMock()
        mock_lcd = MagicMock()

        with (
            patch("g13_linux.device.open_g13", return_value=mock_device),
            patch("g13_linux.hardware.lcd.G13LCD", return_value=mock_lcd),
        ):
            args = MagicMock()
            args.clear = False
            args.text = ["Hello", "World"]

            cmd_lcd(args)

        mock_lcd.clear.assert_called_once()
        mock_lcd.write_text_centered.assert_called_once_with("Hello World")
        mock_device.close.assert_called_once()

    def test_cmd_lcd_no_text_no_clear(self, capsys):
        """Test cmd_lcd with no text and no --clear exits with error."""
        mock_device = MagicMock()
        mock_lcd = MagicMock()

        with (
            patch("g13_linux.device.open_g13", return_value=mock_device),
            patch("g13_linux.hardware.lcd.G13LCD", return_value=mock_lcd),
        ):
            args = MagicMock()
            args.clear = False
            args.text = []

            with pytest.raises(SystemExit) as exc_info:
                cmd_lcd(args)

            assert exc_info.value.code == 1

    def test_cmd_lcd_device_error(self, capsys):
        """Test cmd_lcd handles device open error."""
        with patch("g13_linux.device.open_g13", side_effect=Exception("Device not found")):
            args = MagicMock()
            args.clear = True
            args.text = None

            with pytest.raises(SystemExit) as exc_info:
                cmd_lcd(args)

            assert exc_info.value.code == 1


class TestCmdColor:
    """Tests for cmd_color command."""

    def test_cmd_color_preset(self, capsys):
        """Test cmd_color with preset name."""
        mock_device = MagicMock()
        mock_backlight = MagicMock()

        with (
            patch("g13_linux.device.open_g13", return_value=mock_device),
            patch("g13_linux.hardware.backlight.G13Backlight", return_value=mock_backlight),
        ):
            args = MagicMock()
            args.color = "red"

            cmd_color(args)

        mock_backlight.set_color.assert_called_once_with(255, 0, 0)
        mock_device.close.assert_called_once()

    def test_cmd_color_hex_without_hash(self, capsys):
        """Test cmd_color with hex color without #."""
        mock_device = MagicMock()
        mock_backlight = MagicMock()

        with (
            patch("g13_linux.device.open_g13", return_value=mock_device),
            patch("g13_linux.hardware.backlight.G13Backlight", return_value=mock_backlight),
        ):
            args = MagicMock()
            args.color = "FF8000"

            cmd_color(args)

        mock_backlight.set_color.assert_called_once_with(255, 128, 0)

    def test_cmd_color_hex_with_hash(self, capsys):
        """Test cmd_color with hex color with #."""
        mock_device = MagicMock()
        mock_backlight = MagicMock()

        with (
            patch("g13_linux.device.open_g13", return_value=mock_device),
            patch("g13_linux.hardware.backlight.G13Backlight", return_value=mock_backlight),
        ):
            args = MagicMock()
            args.color = "#00FF80"

            cmd_color(args)

        mock_backlight.set_color.assert_called_once_with(0, 255, 128)

    def test_cmd_color_rgb_values(self, capsys):
        """Test cmd_color with RGB comma-separated values."""
        mock_device = MagicMock()
        mock_backlight = MagicMock()

        with (
            patch("g13_linux.device.open_g13", return_value=mock_device),
            patch("g13_linux.hardware.backlight.G13Backlight", return_value=mock_backlight),
        ):
            args = MagicMock()
            args.color = "100,200,50"

            cmd_color(args)

        mock_backlight.set_color.assert_called_once_with(100, 200, 50)

    def test_cmd_color_invalid(self, capsys):
        """Test cmd_color with invalid color."""
        args = MagicMock()
        args.color = "invalid_color"

        with pytest.raises(SystemExit) as exc_info:
            cmd_color(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error: Invalid color" in captured.err

    def test_cmd_color_device_error(self, capsys):
        """Test cmd_color handles device open error."""
        with patch("g13_linux.device.open_g13", side_effect=Exception("Device not found")):
            args = MagicMock()
            args.color = "red"

            with pytest.raises(SystemExit) as exc_info:
                cmd_color(args)

            assert exc_info.value.code == 1


class TestCmdDoctor:
    """Tests for cmd_doctor command."""

    def test_cmd_doctor_reports_success(self, capsys):
        """Doctor should report success when any backend opens."""
        with (
            patch(
                "g13_linux.device.find_g13_hidraw_info",
                return_value={
                    "path": "/dev/hidraw3",
                    "readable": True,
                    "writable": True,
                    "detection_source": "uevent",
                },
            ),
            patch(
                "g13_linux.device.probe_device_backends",
                return_value=[
                    {"backend": "hidraw", "ok": True, "error": None},
                    {"backend": "libusb", "ok": False, "error": "pyusb not installed"},
                ],
            ),
        ):
            args = MagicMock()
            args.libusb_first = False
            cmd_doctor(args)

        captured = capsys.readouterr()
        assert "G13 Linux Doctor" in captured.out
        assert "Hidraw path: /dev/hidraw3" in captured.out
        assert "Hidraw access: rw (detected via uevent)" in captured.out
        assert "hidraw: OK" in captured.out
        assert "Result: at least one backend can open the G13." in captured.out

    def test_cmd_doctor_reports_failure_and_exits(self, capsys):
        """Doctor should exit 1 when no backend can open device."""
        with (
            patch("g13_linux.device.find_g13_hidraw_info", return_value=None),
            patch(
                "g13_linux.device.probe_device_backends",
                return_value=[
                    {"backend": "hidraw", "ok": False, "error": "Permission denied"},
                    {"backend": "libusb", "ok": False, "error": "G13 not found"},
                ],
            ),
        ):
            args = MagicMock()
            args.libusb_first = True
            with pytest.raises(SystemExit) as exc_info:
                cmd_doctor(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Probe order: libusb -> hidraw" in captured.out
        assert "hidraw: FAILED (Permission denied)" in captured.out
        assert "Result: no backend could open the G13." in captured.out


class TestCmdProfile:
    """Tests for cmd_profile command."""

    def test_cmd_profile_list_with_profiles(self, capsys):
        """Test profile list with profiles."""
        mock_pm = MagicMock()
        mock_pm.list_profiles.return_value = ["profile1", "profile2"]

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "list"

            cmd_profile(args)

        captured = capsys.readouterr()
        assert "profile1" in captured.out
        assert "profile2" in captured.out

    def test_cmd_profile_list_empty(self, capsys):
        """Test profile list with no profiles."""
        mock_pm = MagicMock()
        mock_pm.list_profiles.return_value = []

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "list"

            cmd_profile(args)

        captured = capsys.readouterr()
        assert "No profiles found" in captured.out

    def test_cmd_profile_show(self, capsys):
        """Test profile show command."""
        mock_pm = MagicMock()
        mock_profile = MagicMock()
        mock_profile.name = "test_profile"
        mock_profile.description = "Test description"
        mock_profile.backlight = {"color": "#FF0000"}
        mock_profile.lcd = "Hello"
        mock_profile.mappings = {"G1": "a", "G2": "b"}
        mock_pm.load_profile.return_value = mock_profile

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "show"
            args.name = "test_profile"

            cmd_profile(args)

        captured = capsys.readouterr()
        assert "test_profile" in captured.out
        assert "Test description" in captured.out

    def test_cmd_profile_show_not_found(self, capsys):
        """Test profile show with non-existent profile."""
        mock_pm = MagicMock()
        mock_pm.load_profile.side_effect = FileNotFoundError()

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "show"
            args.name = "missing"

            with pytest.raises(SystemExit) as exc_info:
                cmd_profile(args)

            assert exc_info.value.code == 1

    def test_cmd_profile_load(self, capsys):
        """Test profile load command."""
        mock_pm = MagicMock()
        mock_profile = MagicMock()
        mock_profile.name = "test_profile"
        mock_profile.backlight = {"color": "#FF0000"}
        mock_pm.load_profile.return_value = mock_profile

        mock_device = MagicMock()
        mock_backlight = MagicMock()

        with (
            patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm),
            patch("g13_linux.device.open_g13", return_value=mock_device),
            patch("g13_linux.hardware.backlight.G13Backlight", return_value=mock_backlight),
        ):
            args = MagicMock()
            args.profile_cmd = "load"
            args.name = "test_profile"

            cmd_profile(args)

        mock_backlight.set_color.assert_called_once_with(255, 0, 0)

    def test_cmd_profile_load_no_device(self, capsys):
        """Test profile load when device not available."""
        mock_pm = MagicMock()
        mock_profile = MagicMock()
        mock_profile.name = "test_profile"
        mock_profile.backlight = {"color": "#FF0000"}
        mock_pm.load_profile.return_value = mock_profile

        with (
            patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm),
            patch("g13_linux.device.open_g13", side_effect=Exception("No device")),
        ):
            args = MagicMock()
            args.profile_cmd = "load"
            args.name = "test_profile"

            # Should not raise, just print note
            cmd_profile(args)

        captured = capsys.readouterr()
        assert "Could not apply to device" in captured.out

    def test_cmd_profile_create(self, capsys):
        """Test profile create command."""
        mock_pm = MagicMock()
        mock_pm.profile_exists.return_value = False
        mock_profile = MagicMock()
        mock_pm.create_profile.return_value = mock_profile

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "create"
            args.name = "new_profile"

            cmd_profile(args)

        mock_pm.create_profile.assert_called_once_with("new_profile")
        mock_pm.save_profile.assert_called_once_with(mock_profile)

    def test_cmd_profile_create_exists(self, capsys):
        """Test profile create when profile already exists."""
        mock_pm = MagicMock()
        mock_pm.profile_exists.return_value = True

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "create"
            args.name = "existing"

            with pytest.raises(SystemExit) as exc_info:
                cmd_profile(args)

            assert exc_info.value.code == 1

    def test_cmd_profile_delete(self, capsys):
        """Test profile delete command."""
        mock_pm = MagicMock()

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "delete"
            args.name = "to_delete"

            cmd_profile(args)

        mock_pm.delete_profile.assert_called_once_with("to_delete")

    def test_cmd_profile_delete_not_found(self, capsys):
        """Test profile delete with non-existent profile."""
        mock_pm = MagicMock()
        mock_pm.delete_profile.side_effect = FileNotFoundError()

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "delete"
            args.name = "missing"

            with pytest.raises(SystemExit) as exc_info:
                cmd_profile(args)

            assert exc_info.value.code == 1

    def test_cmd_profile_migrate_single(self, tmp_path, capsys):
        """Test profile migrate for a single profile."""
        profile_path = tmp_path / "legacy.json"
        profile_path.write_text("{}")

        mock_pm = MagicMock()
        mock_pm.profiles_dir = tmp_path

        result = MagicMock()
        result.error = None
        result.changed = True
        result.details = ["normalized joystick fields to canonical schema"]

        with (
            patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm),
            patch(
                "g13_linux.profile_migration.migrate_profile_file", return_value=result
            ) as mock_mig,
        ):
            args = MagicMock()
            args.profile_cmd = "migrate"
            args.name = "legacy"
            args.all = False
            args.dry_run = False
            cmd_profile(args)

        mock_mig.assert_called_once_with(profile_path, dry_run=False)
        captured = capsys.readouterr()
        assert "Migrated: legacy" in captured.out
        assert "Migration complete: 1 migrated, 0 unchanged, 0 errors." in captured.out

    def test_cmd_profile_migrate_all_dry_run(self, tmp_path, capsys):
        """Test profile migrate --all in dry-run mode."""
        (tmp_path / "legacy.json").write_text("{}")
        (tmp_path / "modern.json").write_text("{}")

        mock_pm = MagicMock()
        mock_pm.profiles_dir = tmp_path

        changed_result = MagicMock()
        changed_result.error = None
        changed_result.changed = True
        changed_result.details = ["moved legacy joystick.click mapping to mappings.STICK"]

        unchanged_result = MagicMock()
        unchanged_result.error = None
        unchanged_result.changed = False
        unchanged_result.details = []

        def fake_migrate(path: Path, dry_run: bool):
            if path.stem == "legacy":
                return changed_result
            return unchanged_result

        with (
            patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm),
            patch("g13_linux.profile_migration.migrate_profile_file", side_effect=fake_migrate),
        ):
            args = MagicMock()
            args.profile_cmd = "migrate"
            args.name = None
            args.all = True
            args.dry_run = True
            cmd_profile(args)

        captured = capsys.readouterr()
        assert "Would migrate: legacy" in captured.out
        assert "No changes: modern" in captured.out
        assert "Dry run complete: 1 to migrate, 1 unchanged, 0 errors." in captured.out

    def test_cmd_profile_migrate_requires_name_or_all(self):
        """Test profile migrate errors if no target is provided."""
        mock_pm = MagicMock()

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "migrate"
            args.name = None
            args.all = False
            args.dry_run = False

            with pytest.raises(SystemExit) as exc_info:
                cmd_profile(args)

            assert exc_info.value.code == 1

    def test_cmd_profile_migrate_rejects_name_and_all(self):
        """Test profile migrate errors if name and --all are both provided."""
        mock_pm = MagicMock()

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "migrate"
            args.name = "legacy"
            args.all = True
            args.dry_run = False

            with pytest.raises(SystemExit) as exc_info:
                cmd_profile(args)

            assert exc_info.value.code == 1


class TestMain:
    """Tests for main() entry point."""

    def test_main_version(self, capsys):
        """Test --version flag."""
        with patch.object(sys, "argv", ["g13-linux", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0

    def test_main_no_args_runs_daemon(self):
        """Test main with no args runs daemon."""
        with patch.object(sys, "argv", ["g13-linux"]), patch("g13_linux.cli.cmd_run") as mock_run:
            mock_run.side_effect = SystemExit(0)

            with pytest.raises(SystemExit):
                main()

            mock_run.assert_called_once()

    def test_main_lcd_command(self):
        """Test main with lcd command."""
        with (
            patch.object(sys, "argv", ["g13-linux", "lcd", "--clear"]),
            patch("g13_linux.cli.cmd_lcd") as mock_lcd,
        ):
            mock_lcd.side_effect = SystemExit(0)

            with pytest.raises(SystemExit):
                main()

            mock_lcd.assert_called_once()

    def test_main_color_command(self):
        """Test main with color command."""
        with (
            patch.object(sys, "argv", ["g13-linux", "color", "red"]),
            patch("g13_linux.cli.cmd_color") as mock_color,
        ):
            mock_color.side_effect = SystemExit(0)

            with pytest.raises(SystemExit):
                main()

            mock_color.assert_called_once()

    def test_main_profile_list_command(self):
        """Test main with profile list command."""
        with (
            patch.object(sys, "argv", ["g13-linux", "profile", "list"]),
            patch("g13_linux.cli.cmd_profile") as mock_profile,
        ):
            mock_profile.side_effect = SystemExit(0)

            with pytest.raises(SystemExit):
                main()

            mock_profile.assert_called_once()

    def test_main_profile_migrate_command(self):
        """Test main with profile migrate command."""
        with (
            patch.object(sys, "argv", ["g13-linux", "profile", "migrate", "--all", "--dry-run"]),
            patch("g13_linux.cli.cmd_profile") as mock_profile,
        ):
            mock_profile.side_effect = SystemExit(0)

            with pytest.raises(SystemExit):
                main()

            mock_profile.assert_called_once()

    def test_main_doctor_command(self):
        """Test main with doctor command."""
        with (
            patch.object(sys, "argv", ["g13-linux", "doctor"]),
            patch("g13_linux.cli.cmd_doctor") as mock_doctor,
        ):
            mock_doctor.side_effect = SystemExit(0)

            with pytest.raises(SystemExit):
                main()

            mock_doctor.assert_called_once()

    def test_main_run_libusb_flag_sets_arg(self):
        """main should parse run --libusb into cmd_run args."""
        with (
            patch.object(sys, "argv", ["g13-linux", "run", "--libusb"]),
            patch("g13_linux.cli.cmd_run") as mock_run,
        ):
            mock_run.side_effect = SystemExit(0)

            with pytest.raises(SystemExit):
                main()

            run_args = mock_run.call_args[0][0]
            assert run_args.libusb is True

    def test_main_profile_no_subcommand(self, capsys):
        """Test main with profile but no subcommand."""
        with patch.object(sys, "argv", ["g13-linux", "profile"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1


class TestCLIMissingCoverage:
    """Tests for edge cases to achieve 100% coverage."""

    def test_cmd_run_read_event_returns_none(self, capsys):
        """Test cmd_run when read returns None (simple mode)."""
        mock_handle = MagicMock()
        mock_mapper = MagicMock()

        call_count = [0]

        def fake_read(timeout_ms=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return None  # First call returns None
            if call_count[0] == 2:
                return b"\x00" * 8  # Second call returns data
            raise KeyboardInterrupt  # Third call exits

        mock_handle.read.side_effect = fake_read

        with (
            patch("g13_linux.device.open_g13", return_value=mock_handle),
            patch("g13_linux.mapper.G13Mapper", return_value=mock_mapper),
        ):
            args = MagicMock()
            args.simple = True  # Test simple mode
            cmd_run(args)

        # Should only handle the one valid event (not the None)
        assert mock_mapper.handle_raw_report.call_count == 1

    def test_cmd_profile_show_dict_mapping(self, capsys):
        """Test profile show with dict mapping value (line 154)."""
        mock_pm = MagicMock()
        mock_profile = MagicMock()
        mock_profile.name = "test_profile"
        mock_profile.description = None
        mock_profile.backlight = {}
        mock_profile.lcd = ""
        mock_profile.mappings = {"G1": {"keys": ["a", "b"], "type": "macro"}}
        mock_pm.load_profile.return_value = mock_profile

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "show"
            args.name = "test_profile"

            cmd_profile(args)

        captured = capsys.readouterr()
        assert "['a', 'b']" in captured.out

    def test_cmd_profile_show_reserved_key(self, capsys):
        """Test profile show skips KEY_RESERVED mappings (line 155->152)."""
        mock_pm = MagicMock()
        mock_profile = MagicMock()
        mock_profile.name = "test_profile"
        mock_profile.description = None
        mock_profile.backlight = {}
        mock_profile.lcd = ""
        mock_profile.mappings = {"G1": "a", "G2": "KEY_RESERVED", "G3": "b"}
        mock_pm.load_profile.return_value = mock_profile

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "show"
            args.name = "test_profile"

            cmd_profile(args)

        captured = capsys.readouterr()
        # Should show G1 and G3 but not G2 with KEY_RESERVED
        assert "G1: a" in captured.out
        assert "G3: b" in captured.out
        assert "KEY_RESERVED" not in captured.out

    def test_cmd_profile_load_color_without_hash(self, capsys):
        """Test profile load with color that doesn't start with # (lines 175->182)."""
        mock_pm = MagicMock()
        mock_profile = MagicMock()
        mock_profile.name = "test_profile"
        mock_profile.backlight = {"color": "FF0000"}  # No hash prefix
        mock_pm.load_profile.return_value = mock_profile

        mock_device = MagicMock()
        mock_backlight = MagicMock()

        with (
            patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm),
            patch("g13_linux.device.open_g13", return_value=mock_device),
            patch("g13_linux.hardware.backlight.G13Backlight", return_value=mock_backlight),
        ):
            args = MagicMock()
            args.profile_cmd = "load"
            args.name = "test_profile"

            cmd_profile(args)

        # Color without # prefix should skip the color application
        mock_backlight.set_color.assert_not_called()
        captured = capsys.readouterr()
        assert "Loaded profile" in captured.out

    def test_cmd_profile_load_not_found(self, capsys):
        """Test profile load with non-existent profile (lines 186-188)."""
        mock_pm = MagicMock()
        mock_pm.load_profile.side_effect = FileNotFoundError()

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "load"
            args.name = "missing_profile"

            with pytest.raises(SystemExit) as exc_info:
                cmd_profile(args)

            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_main_unknown_command_no_func(self, capsys):
        """Test main when command exists but has no func attribute (lines 264-265)."""
        # Create a namespace that looks like a parsed command but lacks func
        mock_namespace = MagicMock()
        mock_namespace.command = "unknown"
        del mock_namespace.func  # Remove the func attribute

        with patch("argparse.ArgumentParser.parse_args", return_value=mock_namespace):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    def test_cmd_profile_unknown_subcommand(self, capsys):
        """Test profile with unknown subcommand exits gracefully (line 198->exit)."""
        mock_pm = MagicMock()

        with patch("g13_linux.gui.models.profile_manager.ProfileManager", return_value=mock_pm):
            args = MagicMock()
            args.profile_cmd = "unknown_cmd"  # Not list, show, load, create, or delete

            # Should just return without error (falls through all if/elif)
            cmd_profile(args)

        # Should not have called any profile manager methods
        mock_pm.list_profiles.assert_not_called()
        mock_pm.load_profile.assert_not_called()
        mock_pm.create_profile.assert_not_called()
        mock_pm.delete_profile.assert_not_called()
