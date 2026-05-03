"""Tests for G13 daemon read-loop behavior."""

from unittest.mock import MagicMock, patch

from g13_linux.daemon import G13Daemon


def _make_daemon_for_run_loop() -> G13Daemon:
    """Create a daemon instance with heavy components mocked out."""
    daemon = G13Daemon(enable_server=False)
    daemon._render_loop = MagicMock()  # avoid running real render loop in test thread
    daemon._screen_manager = MagicMock()
    daemon._screen_manager.force_render = MagicMock()
    daemon._stop_server = MagicMock()
    daemon._close_hardware = MagicMock()
    daemon._led_controller = None
    return daemon


def test_run_fans_out_single_device_read_to_input_and_mapper():
    """Each report read once should be sent to both input handler and mapper path."""
    daemon = _make_daemon_for_run_loop()
    daemon._input_handler = MagicMock()
    daemon._mapper = MagicMock()

    report = [0x00] * 8
    daemon._device = MagicMock()
    daemon._device.read.side_effect = [report, KeyboardInterrupt]

    daemon._handle_raw_report = MagicMock()
    daemon.run()

    daemon._device.read.assert_called_with(timeout_ms=100)
    daemon._input_handler.process_report.assert_called_once_with(report)
    daemon._handle_raw_report.assert_called_once_with(report)
    daemon._input_handler.start.assert_not_called()


def test_run_ticks_input_handler_when_no_data():
    """When no report is available, daemon should tick repeat timers."""
    daemon = _make_daemon_for_run_loop()
    daemon._input_handler = MagicMock()
    daemon._mapper = MagicMock()

    daemon._device = MagicMock()
    daemon._device.read.side_effect = [None, KeyboardInterrupt]

    daemon._handle_raw_report = MagicMock()
    daemon.run()

    daemon._input_handler.tick.assert_called_once()
    daemon._input_handler.process_report.assert_not_called()
    daemon._handle_raw_report.assert_not_called()


def test_connect_uses_backend_detection_with_libusb_preference():
    """connect() should call find_device with configured backend preference."""
    mock_device = MagicMock()
    mock_screen_manager = MagicMock()
    mock_idle_screen = MagicMock()

    with (
        patch("g13_linux.daemon.find_device", return_value=(mock_device, {})) as mock_find,
        patch("g13_linux.daemon.G13LCD"),
        patch("g13_linux.daemon.G13Backlight"),
        patch("g13_linux.daemon.LEDController"),
        patch("g13_linux.daemon.G13Mapper"),
        patch("g13_linux.daemon.ScreenManager", return_value=mock_screen_manager),
        patch("g13_linux.daemon.IdleScreen", return_value=mock_idle_screen),
        patch("g13_linux.daemon.NavigationController"),
        patch("g13_linux.daemon.InputHandler"),
        patch.object(G13Daemon, "_setup_mkey_callbacks"),
        patch.object(G13Daemon, "_load_default_profile"),
    ):
        daemon = G13Daemon(enable_server=False, use_libusb=True)
        assert daemon.connect() is True

    mock_find.assert_called_once_with(use_libusb=True, return_diagnostics=True)


def test_connect_returns_false_when_all_backends_fail():
    """connect() should fail cleanly when no backend opens the device."""
    with patch(
        "g13_linux.daemon.find_device",
        return_value=(None, {"hidraw": "Permission denied", "libusb": "G13 not found"}),
    ) as mock_find:
        daemon = G13Daemon(enable_server=False)
        assert daemon.connect() is False

    mock_find.assert_called_once_with(use_libusb=False, return_diagnostics=True)
