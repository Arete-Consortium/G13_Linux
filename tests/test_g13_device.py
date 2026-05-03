"""Tests for G13Device wrapper."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from g13_linux.gui.models.g13_device import G13Device

# Get the project root directory (parent of tests/)
PROJECT_ROOT = Path(__file__).parent.parent

# Tests spawning subprocesses that import PyQt6 need an X display
# Check for non-empty DISPLAY (empty string or None both mean no display)
DISPLAY_AVAILABLE = bool(os.environ.get("DISPLAY"))


class TestPyQt6Fallback:
    """Tests for PyQt6 import fallback (lines 9-15).

    Note: Lines 9-15 contain import-time fallback code that only executes
    when PyQt6 is not available. This code path is tested via subprocess
    to verify functionality, but cannot easily contribute to coverage.py
    metrics since coverage only tracks the main test process.

    The subprocess test below verifies the fallback works correctly.
    """

    @pytest.mark.skipif(
        not DISPLAY_AVAILABLE, reason="Subprocess imports PyQt6 which requires X display"
    )
    def test_fallback_import_via_subprocess(self):
        """Test module imports with fallback when PyQt6 is unavailable."""
        import subprocess
        import sys

        # Python script that tests the fallback code by blocking PyQt6 import
        test_script = """
import sys

# Block PyQt6 imports by raising ImportError
class BlockPyQt6Finder:
    def find_module(self, name, path=None):
        if name == "PyQt6" or name.startswith("PyQt6."):
            return self
        return None

    def load_module(self, name):
        raise ImportError(f"Blocked: {name}")

# Insert blocker at the start of meta_path
sys.meta_path.insert(0, BlockPyQt6Finder())

# Remove any already-imported PyQt6 modules
for mod in list(sys.modules.keys()):
    if mod.startswith("PyQt6"):
        del sys.modules[mod]

# Now import g13_device - should use fallback
try:
    from g13_linux.gui.models.g13_device import G13Device

    # Test that device can be created with fallback
    device = G13Device()

    # Signals should be None (fallback behavior)
    # In fallback mode, pyqtSignal returns None
    print("SUCCESS: Module loaded with fallback")
    sys.exit(0)
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
"""
        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            env={
                **dict(__import__("os").environ),
                "PYTHONPATH": str(PROJECT_ROOT / "src"),
            },
        )

        assert result.returncode == 0, f"Fallback test failed: {result.stderr}"
        assert "SUCCESS" in result.stdout


class TestG13DeviceInit:
    """Tests for G13Device initialization."""

    def test_init_default(self):
        """Test default initialization."""
        device = G13Device()

        assert device._handle is None
        assert device._is_connected is False
        assert device._use_libusb is False

    def test_init_with_libusb(self):
        """Test initialization with libusb flag."""
        device = G13Device(use_libusb=True)

        assert device._use_libusb is True

    def test_is_connected_initially_false(self):
        """Test is_connected is False initially."""
        device = G13Device()
        assert device.is_connected is False

    def test_handle_initially_none(self):
        """Test handle is None initially."""
        device = G13Device()
        assert device.handle is None


class TestG13DeviceConnect:
    """Tests for connect method."""

    def test_connect_success_hidraw(self, qtbot):
        """Test successful connection via hidraw."""
        device = G13Device(use_libusb=False)

        mock_handle = MagicMock()

        connected = []
        device.device_connected.connect(lambda: connected.append(True))

        with patch(
            "g13_linux.gui.models.g13_device.find_device",
            return_value=(mock_handle, {}),
        ) as mock_find:
            result = device.connect()

        assert result is True
        assert device.is_connected is True
        assert device.handle is mock_handle
        assert len(connected) == 1
        mock_find.assert_called_once_with(use_libusb=False, return_diagnostics=True)

    def test_connect_success_libusb(self, qtbot):
        """Test successful connection via libusb."""
        device = G13Device(use_libusb=True)

        mock_handle = MagicMock()

        with patch(
            "g13_linux.gui.models.g13_device.find_device",
            return_value=(mock_handle, {}),
        ) as mock_find:
            result = device.connect()

        assert result is True
        assert device.is_connected is True
        mock_find.assert_called_once_with(use_libusb=True, return_diagnostics=True)

    def test_connect_failure_runtime_error(self, qtbot):
        """Test connection failure with RuntimeError."""
        device = G13Device()

        errors = []
        device.error_occurred.connect(errors.append)

        with patch(
            "g13_linux.gui.models.g13_device.find_device",
            side_effect=RuntimeError("Device not found"),
        ):
            result = device.connect()

        assert result is False
        assert device.is_connected is False
        assert len(errors) == 1
        assert "Failed to connect" in errors[0]

    def test_connect_failure_exception(self, qtbot):
        """Test connection failure with generic exception."""
        device = G13Device()

        errors = []
        device.error_occurred.connect(errors.append)

        with patch(
            "g13_linux.gui.models.g13_device.find_device",
            side_effect=Exception("Unknown error"),
        ):
            result = device.connect()

        assert result is False
        assert device.is_connected is False
        assert len(errors) == 1
        assert "Unexpected error" in errors[0]

    def test_connect_failure_none_handle(self, qtbot):
        """Test connection failure when discovery returns no handle."""
        device = G13Device()
        errors = []
        device.error_occurred.connect(errors.append)

        with patch("g13_linux.gui.models.g13_device.find_device", return_value=(None, {})):
            result = device.connect()

        assert result is False
        assert device.is_connected is False
        assert len(errors) == 1
        assert "Failed to connect" in errors[0]

    def test_connect_failure_includes_backend_diagnostics(self, qtbot):
        """Test connection failure message includes backend-level diagnostics."""
        device = G13Device()
        errors = []
        device.error_occurred.connect(errors.append)

        with patch(
            "g13_linux.gui.models.g13_device.find_device",
            return_value=(None, {"hidraw": "Permission denied", "libusb": "pyusb not installed"}),
        ):
            result = device.connect()

        assert result is False
        assert len(errors) == 1
        assert "hidraw: Permission denied" in errors[0]
        assert "libusb: pyusb not installed" in errors[0]


class TestG13DeviceDisconnect:
    """Tests for disconnect method."""

    def test_disconnect_closes_handle(self, qtbot):
        """Test disconnect closes device handle."""
        device = G13Device()
        mock_handle = MagicMock()
        device._handle = mock_handle
        device._is_connected = True

        disconnected = []
        device.device_disconnected.connect(lambda: disconnected.append(True))

        device.disconnect()

        mock_handle.close.assert_called_once()
        assert device._handle is None
        assert device.is_connected is False
        assert len(disconnected) == 1

    def test_disconnect_when_not_connected(self, qtbot):
        """Test disconnect when not connected."""
        device = G13Device()

        disconnected = []
        device.device_disconnected.connect(lambda: disconnected.append(True))

        device.disconnect()

        assert device._handle is None
        assert len(disconnected) == 1

    def test_disconnect_handles_close_exception(self, qtbot):
        """Test disconnect handles close exception."""
        device = G13Device()
        mock_handle = MagicMock()
        mock_handle.close.side_effect = Exception("Close failed")
        device._handle = mock_handle
        device._is_connected = True

        errors = []
        device.error_occurred.connect(errors.append)

        device.disconnect()

        assert len(errors) == 1
        assert "Error closing device" in errors[0]
        assert device._handle is None


class TestG13DeviceReadEvent:
    """Tests for read_event_once method."""

    def test_read_event_not_connected(self):
        """Test read_event_once when not connected."""
        device = G13Device()

        result = device.read_event_once()

        assert result is None

    def test_read_event_no_handle(self):
        """Test read_event_once with no handle."""
        device = G13Device()
        device._is_connected = True  # Connected but no handle

        result = device.read_event_once()

        assert result is None

    def test_read_event_success(self, qtbot):
        """Test successful event read."""
        device = G13Device()
        device._is_connected = True
        device._handle = MagicMock()

        test_data = bytes([0x00, 0x80, 0x80, 0x01, 0x00, 0x00, 0x00, 0x00])

        events = []
        device.raw_event_received.connect(events.append)

        with patch("g13_linux.gui.models.g13_device.read_event", return_value=test_data):
            result = device.read_event_once()

        assert result == test_data
        assert len(events) == 1
        assert events[0] == test_data

    def test_read_event_no_data(self, qtbot):
        """Test read_event_once with no data available."""
        device = G13Device()
        device._is_connected = True
        device._handle = MagicMock()

        events = []
        device.raw_event_received.connect(events.append)

        with patch("g13_linux.gui.models.g13_device.read_event", return_value=None):
            result = device.read_event_once()

        assert result is None
        assert len(events) == 0

    def test_read_event_exception(self, qtbot):
        """Test read_event_once handles exception."""
        device = G13Device()
        device._is_connected = True
        device._handle = MagicMock()

        errors = []
        device.error_occurred.connect(errors.append)

        with patch(
            "g13_linux.gui.models.g13_device.read_event",
            side_effect=Exception("Read error"),
        ):
            result = device.read_event_once()

        assert result is None
        assert len(errors) == 1
        assert "Error reading event" in errors[0]


class TestG13DeviceCleanup:
    """Tests for cleanup behavior."""

    def test_del_closes_handle(self):
        """Test __del__ closes handle."""
        device = G13Device()
        mock_handle = MagicMock()
        device._handle = mock_handle

        device.__del__()

        mock_handle.close.assert_called_once()
        assert device._handle is None
        assert device._is_connected is False

    def test_del_handles_exception(self):
        """Test __del__ handles close exception silently."""
        device = G13Device()
        mock_handle = MagicMock()
        mock_handle.close.side_effect = Exception("Close failed")
        device._handle = mock_handle

        # Should not raise
        device.__del__()

        assert device._handle is None

    def test_del_with_no_handle(self):
        """Test __del__ with no handle is safe."""
        device = G13Device()

        # Should not raise
        device.__del__()


class TestG13DeviceProperties:
    """Tests for property getters."""

    def test_is_connected_true(self):
        """Test is_connected returns True when connected."""
        device = G13Device()
        device._is_connected = True

        assert device.is_connected is True

    def test_is_connected_false(self):
        """Test is_connected returns False when not connected."""
        device = G13Device()
        device._is_connected = False

        assert device.is_connected is False

    def test_handle_returns_internal_handle(self):
        """Test handle property returns internal handle."""
        device = G13Device()
        mock_handle = MagicMock()
        device._handle = mock_handle

        assert device.handle is mock_handle
