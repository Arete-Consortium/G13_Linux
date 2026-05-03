"""
Input Handler

Processes G13 input and emits InputEvents for menu navigation.
"""

import logging
import threading
import time
from collections.abc import Callable

from ..gui.models.event_decoder import EventDecoder
from ..menu.screen import InputEvent

logger = logging.getLogger(__name__)


class InputHandler:
    """
    Handles G13 input for menu navigation.

    Reads from device and emits InputEvents based on thumbstick
    and button states.
    """

    # Thumbstick thresholds
    STICK_CENTER = 128
    STICK_THRESHOLD = 50  # Dead zone from center
    STICK_REPEAT_DELAY = 0.4  # Seconds before repeat starts
    STICK_REPEAT_RATE = 0.15  # Seconds between repeats

    def __init__(self, device, callback: Callable[[InputEvent], None]):
        """
        Initialize input handler.

        Args:
            device: G13 device handle with read() method
            callback: Function to call with InputEvents
        """
        self.device = device
        self.callback = callback
        self._decoder = EventDecoder()
        self._running = False
        self._thread: threading.Thread | None = None

        # Thumbstick state
        self._stick_x = self.STICK_CENTER
        self._stick_y = self.STICK_CENTER
        self._stick_pressed = False

        # Direction repeat tracking
        self._repeat_direction: InputEvent | None = None
        self._repeat_start_time: float = 0
        self._last_repeat_time: float = 0

        # Button state for edge detection
        self._button_state: dict[str, bool] = {}

    def start(self):
        """Start input polling thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="InputHandler")
        self._thread.start()
        logger.info("Input handler started")

    def stop(self):
        """Stop input polling."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("Input handler stopped")

    def process_report(self, data: bytes | list[int]):
        """
        Process one raw report without reading from the device.

        This allows a single external read loop (for example, the daemon)
        to fan out each report to both mapper and navigation handling.
        """
        self._process_report(data)

    def tick(self):
        """
        Advance repeat timers when no new report is available.

        Useful when this handler is driven by an external polling loop.
        """
        self._check_stick_repeat()

    def _poll_loop(self):
        """Main polling loop."""
        while self._running:
            try:
                data = self.device.read(timeout_ms=100)
                if data:
                    self._process_report(data)
                else:
                    # Check for stick repeat even without new data
                    self._check_stick_repeat()
            except Exception as e:
                logger.debug(f"Input read: {e}")
                time.sleep(0.01)

    def _process_report(self, data: bytes):
        """
        Parse HID report and emit events.

        Args:
            data: Raw HID report bytes
        """
        try:
            state = self._decoder.decode_report(data)
        except ValueError as e:
            logger.warning(f"Invalid report: {e}")
            return

        # Process thumbstick
        self._process_thumbstick(state.joystick_x, state.joystick_y)

        # Process stick button
        self._process_stick_button(state.raw_data)

        # Process navigation buttons
        self._process_buttons(state.raw_data)

    def _process_thumbstick(self, x: int, y: int):
        """
        Process thumbstick position and emit directional events.

        Args:
            x: X position (0-255, 128 center)
            y: Y position (0-255, 128 center)
        """
        self._stick_x = x
        self._stick_y = y

        # Determine direction
        direction = None

        # Y axis (up/down) - note: Y may be inverted
        if y < self.STICK_CENTER - self.STICK_THRESHOLD:
            direction = InputEvent.STICK_UP
        elif y > self.STICK_CENTER + self.STICK_THRESHOLD:
            direction = InputEvent.STICK_DOWN

        # X axis (left/right) - only if no Y direction
        if direction is None:
            if x < self.STICK_CENTER - self.STICK_THRESHOLD:
                direction = InputEvent.STICK_LEFT
            elif x > self.STICK_CENTER + self.STICK_THRESHOLD:
                direction = InputEvent.STICK_RIGHT

        # Handle direction changes and repeats
        if direction != self._repeat_direction:
            if direction:
                # New direction - emit immediately
                self._emit(direction)
                self._repeat_direction = direction
                self._repeat_start_time = time.time()
                self._last_repeat_time = time.time()
            else:
                # Back to center - stop repeating
                self._repeat_direction = None

    def _check_stick_repeat(self):
        """Check if stick repeat should trigger."""
        if not self._repeat_direction:
            return

        now = time.time()
        elapsed = now - self._repeat_start_time

        # Wait for initial delay
        if elapsed < self.STICK_REPEAT_DELAY:
            return

        # Check if enough time for next repeat
        if now - self._last_repeat_time >= self.STICK_REPEAT_RATE:
            self._emit(self._repeat_direction)
            self._last_repeat_time = now

    def _process_stick_button(self, data: bytes):
        """
        Process thumbstick button press.

        Args:
            data: Raw HID report
        """
        if len(data) < 8:
            return

        # STICK button is byte 7, bit 3
        is_pressed = bool(data[7] & 0x08)

        if is_pressed and not self._stick_pressed:
            self._emit(InputEvent.STICK_PRESS)

        self._stick_pressed = is_pressed

    def _process_buttons(self, data: bytes):
        """
        Process navigation buttons (BD, M1-M3, MR).

        Args:
            data: Raw HID report
        """
        if len(data) < 8:
            return

        # Button mappings from EventDecoder
        button_map = {
            "BD": (6, 0, InputEvent.BUTTON_BD),
            "LEFT": (7, 1, InputEvent.BUTTON_LEFT),
            "M1": (6, 5, InputEvent.BUTTON_M1),
            "M2": (6, 6, InputEvent.BUTTON_M2),
            "M3": (6, 7, InputEvent.BUTTON_M3),
            "MR": (7, 0, InputEvent.BUTTON_MR),
        }

        for name, (byte_idx, bit_pos, event) in button_map.items():
            is_pressed = bool(data[byte_idx] & (1 << bit_pos))
            was_pressed = self._button_state.get(name, False)

            # Emit on rising edge only
            if is_pressed and not was_pressed:
                self._emit(event)

            self._button_state[name] = is_pressed

    def _emit(self, event: InputEvent):
        """
        Emit input event to callback.

        Args:
            event: Event to emit
        """
        try:
            self.callback(event)
        except Exception as e:
            logger.error(f"Callback error: {e}")


class SimulatedInputHandler:
    """
    Simulated input handler for testing without hardware.

    Allows manual injection of events.
    """

    def __init__(self, callback: Callable[[InputEvent], None]):
        """
        Initialize simulated handler.

        Args:
            callback: Function to call with InputEvents
        """
        self.callback = callback
        self._running = False

    def start(self):
        """Start (no-op for simulation)."""
        self._running = True

    def stop(self):
        """Stop (no-op for simulation)."""
        self._running = False

    def inject_event(self, event: InputEvent):
        """
        Inject an input event.

        Args:
            event: Event to inject
        """
        if self._running:
            self.callback(event)

    def inject_stick_up(self):
        """Simulate stick up."""
        self.inject_event(InputEvent.STICK_UP)

    def inject_stick_down(self):
        """Simulate stick down."""
        self.inject_event(InputEvent.STICK_DOWN)

    def inject_stick_press(self):
        """Simulate stick press."""
        self.inject_event(InputEvent.STICK_PRESS)

    def inject_back(self):
        """Simulate back button."""
        self.inject_event(InputEvent.BUTTON_BD)
