import fcntl
import glob
import importlib
import logging
import os
from pathlib import Path

G13_VENDOR_ID = 0x046D
G13_PRODUCT_ID = 0xC21C

logger = logging.getLogger(__name__)


def _hidiocsfeature(length):
    """HIDIOCSFEATURE ioctl for setting feature reports."""
    return 0xC0004806 | (length << 16)


def _hidiocgfeature(length):
    """HIDIOCGFEATURE ioctl for getting feature reports."""
    return 0xC0004807 | (length << 16)


class HidrawDevice:
    """Wrapper for hidraw device file to provide consistent interface."""

    def __init__(self, path):
        self.path = path
        self._fd = None
        self._file = None

    def open(self):
        self._file = open(self.path, "rb+", buffering=0)
        self._fd = self._file.fileno()
        os.set_blocking(self._fd, False)

    def read(self, size=64, timeout_ms=None):
        """
        Read an input report from hidraw.

        Args:
            size: Number of bytes to read (default: 64)
            timeout_ms: Accepted for API compatibility with LibUSBDevice.read().
                Ignored for hidraw since file descriptor is non-blocking.
        """
        del timeout_ms  # Non-blocking hidraw reads return immediately
        try:
            data = self._file.read(size)
            return list(data) if data else None
        except BlockingIOError:
            return None

    def write(self, data):
        """Write an output report to the device."""
        return self._file.write(bytes(data))

    def send_feature_report(self, data):
        """
        Send a HID feature report to the device.

        Args:
            data: Report data (first byte should be report ID)

        Returns:
            Number of bytes written
        """
        if self._fd is None:
            raise RuntimeError("Device not open")

        buf = bytes(data)
        return fcntl.ioctl(self._fd, _hidiocsfeature(len(buf)), buf)

    def get_feature_report(self, report_id, size):
        """
        Get a HID feature report from the device.

        Args:
            report_id: Report ID to request
            size: Expected report size

        Returns:
            Report data as bytes
        """
        if self._fd is None:
            raise RuntimeError("Device not open")

        buf = bytearray(size)
        buf[0] = report_id
        fcntl.ioctl(self._fd, _hidiocgfeature(size), buf)
        return bytes(buf)

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
            self._fd = None


def _parse_hid_id(content):
    """Parse HID_ID line from uevent content and return (vendor_id, product_id)."""
    for line in content.splitlines():
        if not line.startswith("HID_ID="):
            continue
        value = line.split("=", 1)[1].strip()
        parts = value.split(":")
        if len(parts) != 3:
            return None
        try:
            return int(parts[1], 16), int(parts[2], 16)
        except ValueError:
            return None
    return None


def _read_usb_ids_from_sysfs(start_path):
    """
    Walk up sysfs from hidraw device and try to read USB idVendor/idProduct.

    Some kernel/device paths don't expose HID_ID reliably in uevent; this
    fallback improves detection coverage for those systems.
    """
    current = Path(start_path).resolve()
    while True:
        vendor_path = current / "idVendor"
        product_path = current / "idProduct"

        if vendor_path.exists() and product_path.exists():
            try:
                vendor = int(vendor_path.read_text().strip(), 16)
                product = int(product_path.read_text().strip(), 16)
                return vendor, product
            except (OSError, ValueError):
                return None

        parent = current.parent
        if parent == current:
            return None
        current = parent


def scan_hidraw_devices():
    """
    Discover hidraw devices and annotate detection/permission details.

    Returns:
        List[dict] with keys:
            - path: /dev/hidrawX
            - matched: whether VID/PID match Logitech G13
            - vendor_id: int | None
            - product_id: int | None
            - readable: bool
            - writable: bool
            - detection_source: "uevent" | "usb_ids" | None
            - error: str | None
    """
    results = []
    for hidraw in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        device_name = os.path.basename(hidraw)
        dev_path = f"/dev/{device_name}"
        device_dir = os.path.join(hidraw, "device")
        uevent_path = os.path.join(device_dir, "uevent")

        entry = {
            "path": dev_path,
            "matched": False,
            "vendor_id": None,
            "product_id": None,
            "readable": os.access(dev_path, os.R_OK),
            "writable": os.access(dev_path, os.W_OK),
            "detection_source": None,
            "error": None,
        }

        ids = None
        try:
            with open(uevent_path) as f:
                ids = _parse_hid_id(f.read())
            if ids is not None:
                entry["detection_source"] = "uevent"
        except OSError as exc:
            entry["error"] = str(exc) or exc.__class__.__name__

        if ids is None:
            ids = _read_usb_ids_from_sysfs(device_dir)
            if ids is not None:
                entry["detection_source"] = "usb_ids"

        if ids is not None:
            vendor_id, product_id = ids
            entry["vendor_id"] = vendor_id
            entry["product_id"] = product_id
            entry["matched"] = vendor_id == G13_VENDOR_ID and product_id == G13_PRODUCT_ID

        results.append(entry)

    return results


def find_g13_hidraw_info():
    """Return the first matched hidraw discovery entry for G13, if present."""
    for entry in scan_hidraw_devices():
        if entry["matched"]:
            return entry
    return None


def find_g13_hidraw():
    """Find the hidraw device path for the G13."""
    info = find_g13_hidraw_info()
    return info["path"] if info else None


def open_g13():
    """Open the G13 device and return a handle."""
    hidraw_info = find_g13_hidraw_info()
    if not hidraw_info:
        raise RuntimeError("Logitech G13 not found")

    hidraw_path = hidraw_info["path"]
    device = HidrawDevice(hidraw_path)
    try:
        device.open()
    except PermissionError as err:
        raise RuntimeError(
            f"Permission denied opening {hidraw_path}. "
            "Install udev rules or run with elevated permissions."
        ) from err
    return device


def read_event(handle):
    """Read a HID report from the device."""
    data = handle.read(64)
    return data if data else None


class LibUSBDevice:
    """
    Direct libusb access for G13 input reading.

    Required because hid-generic kernel driver consumes input reports
    and doesn't pass them to hidraw. This requires root/sudo to detach
    the kernel driver.

    Note: Linux kernel 6.19+ will have proper hid-lg-g15 support for G13.
    """

    ENDPOINT_IN = 0x81  # EP 1 IN for button/joystick data
    ENDPOINT_OUT = 0x02  # EP 2 OUT for LCD data
    REPORT_SIZE = 8  # 7 bytes data + 1 byte report ID

    def __init__(self):
        self._dev = None
        self._reattach = False

    def open(self):
        """Open G13 via libusb, detaching kernel driver."""
        try:
            usb_core = importlib.import_module("usb.core")
            usb_util = importlib.import_module("usb.util")
        except ImportError as err:
            raise RuntimeError("pyusb not installed. Run: pip install pyusb") from err

        self._dev = usb_core.find(idVendor=G13_VENDOR_ID, idProduct=G13_PRODUCT_ID)
        if self._dev is None:
            raise RuntimeError("G13 not found")

        # Detach kernel driver from all interfaces
        for intf_num in range(2):
            try:
                if self._dev.is_kernel_driver_active(intf_num):
                    self._dev.detach_kernel_driver(intf_num)
                    self._reattach = True
            except OSError:
                pass  # Driver may not be attached

        # Set configuration
        try:
            self._dev.set_configuration()
        except OSError:
            pass  # May already be configured

        # Claim both interfaces
        for intf_num in range(2):
            try:
                usb_util.claim_interface(self._dev, intf_num)
            except OSError:
                pass  # May already be claimed

        # Get endpoints from interface 0
        cfg = self._dev.get_active_configuration()
        intf = cfg[(0, 0)]

        self._ep_in = usb_util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb_util.endpoint_direction(e.bEndpointAddress) == usb_util.ENDPOINT_IN
            ),
        )
        self._ep_out = usb_util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb_util.endpoint_direction(e.bEndpointAddress) == usb_util.ENDPOINT_OUT
            ),
        )

    def read(self, timeout_ms=100):
        """
        Read button/joystick report.

        Returns:
            List of bytes or None on timeout
        """
        try:
            data = self._ep_in.read(64, timeout=timeout_ms)
            return list(data) if data else None
        except (OSError, ValueError):
            return None

    def write(self, data):
        """
        Write output data (for LCD) via interrupt transfer.

        Uses endpoint 0x02 OUT which is the LCD data endpoint.
        """
        # Use direct interrupt write to endpoint 0x02
        return self._dev.write(self.ENDPOINT_OUT, bytes(data), timeout=1000)

    def send_feature_report(self, data):
        """Send feature report via control transfer."""
        report_id = data[0]
        return self._dev.ctrl_transfer(
            0x21,  # bmRequestType: Host-to-device, Class, Interface
            0x09,  # bRequest: SET_REPORT
            0x0300 | report_id,  # wValue: Feature report + report ID
            0,  # wIndex: Interface 0
            bytes(data),
            1000,  # timeout
        )

    def close(self):
        """Close device and reattach kernel driver."""
        if self._dev:
            try:
                usb_util = importlib.import_module("usb.util")
            except ImportError:
                usb_util = None

            # Release both interfaces
            for intf_num in range(2):
                try:
                    if usb_util is not None:
                        usb_util.release_interface(self._dev, intf_num)
                except OSError:
                    pass  # Best-effort cleanup

            # Reattach kernel drivers
            if self._reattach:
                for intf_num in range(2):
                    try:
                        self._dev.attach_kernel_driver(intf_num)
                    except OSError:
                        pass  # Best-effort cleanup

            self._dev = None


def open_g13_libusb():
    """
    Open G13 using libusb for input reading.

    Requires root/sudo to detach kernel driver.
    Use this when you need button/joystick input.
    """
    device = LibUSBDevice()
    device.open()
    return device


def _backend_openers(use_libusb=False):
    """Return backend openers in preferred order."""
    if use_libusb:
        return [("libusb", open_g13_libusb), ("hidraw", open_g13)]
    return [("hidraw", open_g13), ("libusb", open_g13_libusb)]


def probe_device_backends(use_libusb=False):
    """
    Probe each backend and collect diagnostics.

    Returns:
        List[dict]: entries with keys:
            - backend: "hidraw" or "libusb"
            - ok: bool
            - error: str | None
    """
    diagnostics = []

    for backend_name, opener in _backend_openers(use_libusb):
        result = {"backend": backend_name, "ok": False, "error": None}
        handle = None
        try:
            handle = opener()
            result["ok"] = True
        except Exception as e:
            result["error"] = str(e) or e.__class__.__name__
            logger.debug(f"{backend_name} probe failed: {e}")
        finally:
            if handle is not None:
                try:
                    handle.close()
                except Exception as e:
                    logger.debug(f"{backend_name} close after probe failed: {e}")

        diagnostics.append(result)

    return diagnostics


def find_device(use_libusb=False, return_diagnostics=False):
    """
    Find and open a G13 device handle.

    Args:
        use_libusb: Prefer libusb backend first.
        return_diagnostics: When True, return (handle, backend_errors).

    Returns:
        Opened device handle, or None if unavailable.
        If return_diagnostics=True, returns tuple:
            (handle_or_none, {backend_name: error_message})
    """
    backend_errors = {}

    for backend_name, opener in _backend_openers(use_libusb):
        try:
            handle = opener()
            if return_diagnostics:
                return handle, backend_errors
            return handle
        except Exception as e:
            opener_name = getattr(opener, "__name__", opener.__class__.__name__)
            backend_errors[backend_name] = str(e) or e.__class__.__name__
            logger.debug(f"{opener_name} failed: {e}")

    if return_diagnostics:
        return None, backend_errors

    return None
