"""
G13 Device Wrapper

Thread-safe Qt wrapper around the G13 USB device for GUI integration.
"""

try:
    from PyQt6.QtCore import QObject, pyqtSignal
except ImportError:  # pragma: no cover
    # Fallback for development/testing without PyQt6
    class QObject:
        pass

    def pyqtSignal(*args, **kwargs):
        return None


from ...device import find_device, read_event


class G13Device(QObject):
    """
    Thread-safe G13 device wrapper with Qt signals.

    Provides Qt-friendly interface to the G13 hardware with signals
    for device events, button presses, and errors.
    """

    # Signals for GUI updates
    device_connected = pyqtSignal()
    device_disconnected = pyqtSignal()
    raw_event_received = pyqtSignal(bytes)  # Raw HID report
    button_event = pyqtSignal(str, bool)  # (button_id, is_pressed)
    joystick_moved = pyqtSignal(int, int)  # (x, y)
    error_occurred = pyqtSignal(str)

    def __init__(self, use_libusb: bool = False):
        super().__init__()
        self._handle = None
        self._event_thread = None
        self._is_connected = False
        self._use_libusb = use_libusb

    @property
    def is_connected(self) -> bool:
        """Check if device is currently connected"""
        return self._is_connected

    @property
    def handle(self):
        """Get raw device handle (for advanced use)"""
        return self._handle

    def connect(self) -> bool:
        """
        Open G13 device and prepare for event reading.

        Returns:
            True if connection successful, False otherwise

        Emits:
            device_connected on success
            error_occurred on failure

        Note:
            If use_libusb=True was passed to __init__, uses libusb which
            requires root/sudo but receives button input. Otherwise uses
            hidraw which works without root but kernel driver blocks input.
        """
        try:
            result = find_device(use_libusb=self._use_libusb, return_diagnostics=True)
            if isinstance(result, tuple):
                self._handle, backend_errors = result
            else:  # Backward compatibility for mocked/older find_device return style
                self._handle = result
                backend_errors = {}

            if self._handle is None:
                details = self._format_backend_error_details(backend_errors)
                raise RuntimeError(f"Logitech G13 not found{details}")
            self._is_connected = True
            self.device_connected.emit()
            return True

        except RuntimeError as e:
            self._is_connected = False
            error_msg = f"Failed to connect to G13: {e}"
            self.error_occurred.emit(error_msg)
            return False

        except Exception as e:
            self._is_connected = False
            error_msg = f"Unexpected error connecting to G13: {e}"
            self.error_occurred.emit(error_msg)
            return False

    @staticmethod
    def _format_backend_error_details(backend_errors: dict) -> str:
        """Return short backend error summary for connection diagnostics."""
        if not backend_errors:
            return ""

        order = ["hidraw", "libusb"]
        parts = []

        for backend in order:
            if backend in backend_errors:
                parts.append(f"{backend}: {backend_errors[backend]}")
        for backend, message in backend_errors.items():
            if backend not in order:
                parts.append(f"{backend}: {message}")

        if not parts:
            return ""
        return f" ({'; '.join(parts)})"

    def disconnect(self):
        """
        Close device connection.

        Emits:
            device_disconnected
        """
        if self._handle:
            try:
                self._handle.close()
            except Exception as e:
                self.error_occurred.emit(f"Error closing device: {e}")

        self._handle = None
        self._is_connected = False
        self.device_disconnected.emit()

    def read_event_once(self) -> bytes | None:
        """
        Read a single event from the device.

        Returns:
            Event data bytes or None if no event available

        Note:
            This is a non-blocking read. For continuous event monitoring,
            use DeviceEventThread from the controllers module.
        """
        if not self._is_connected or not self._handle:
            return None

        try:
            data = read_event(self._handle)
            if data:
                self.raw_event_received.emit(bytes(data))
            return data

        except Exception as e:
            self.error_occurred.emit(f"Error reading event: {e}")
            return None

    def __del__(self):
        """Cleanup on object destruction - just close handle, don't emit signals"""
        if self._handle:
            try:
                self._handle.close()
            except Exception:
                pass  # Ignore errors during cleanup
        self._handle = None
        self._is_connected = False
