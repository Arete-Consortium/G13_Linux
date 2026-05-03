import logging

try:
    from evdev import UInput
    from evdev import ecodes as e
except Exception:  # pragma: no cover - exercised on non-Linux/dev hosts
    UInput = None
    e = None

from g13_linux.gui.models.event_decoder import EventDecoder

logger = logging.getLogger(__name__)


class _NoopUInput:
    """Fallback UInput adapter when evdev is unavailable."""

    def write(self, *args, **kwargs):
        del args, kwargs
        return None

    def syn(self):
        return None

    def close(self):
        return None


class G13Mapper:
    """
    G13 event mapper - converts button presses to keyboard events.

    Supports both simple keys and key combinations (e.g., Ctrl+B).
    """

    def __init__(self):
        self._evdev_available = UInput is not None and e is not None
        if self._evdev_available:
            self.ui = UInput()
        else:
            self.ui = _NoopUInput()
            logger.warning("evdev unavailable; G13Mapper key injection disabled on this host")
        # button_id (str) -> list of evdev keycodes (for combos)
        self.button_map: dict[str, list[int]] = {}
        # Decoder for raw HID reports
        self.decoder = EventDecoder()

    def close(self):
        self.ui.close()

    def load_profile(self, profile_data: dict):
        """
        Load button mappings from profile.

        Supports two formats:
        - Simple: {'G1': 'KEY_1', ...}
        - Combo:  {'G1': {'keys': ['KEY_LEFTCTRL', 'KEY_B'], 'label': '...'}, ...}
        """
        self.button_map = {}
        mappings = profile_data.get("mappings", {})

        for button_id, mapping in mappings.items():
            keycodes = self._parse_mapping(mapping)
            if keycodes:
                self.button_map[button_id] = keycodes

    def _parse_mapping(self, mapping: str | dict) -> list[int]:
        """Parse a mapping entry into a list of keycodes."""
        if isinstance(mapping, str):
            # Simple format: 'KEY_1'
            if e and hasattr(e, mapping):
                return [getattr(e, mapping)]
            return []

        if isinstance(mapping, dict):
            # Combo format: {'keys': ['KEY_LEFTCTRL', 'KEY_B'], ...}
            keys = mapping.get("keys", [])
            keycodes = []
            for key_name in keys:
                if e and hasattr(e, key_name):
                    keycodes.append(getattr(e, key_name))
            return keycodes

        return []

    def handle_button_event(self, button_id: str, is_pressed: bool):
        """
        Handle decoded button event from GUI.

        For key combinations, press all keys in order on press,
        and release all keys in reverse order on release.
        """
        if button_id not in self.button_map:
            return
        if not self._evdev_available:
            return

        keycodes = self.button_map[button_id]
        state = 1 if is_pressed else 0

        if is_pressed:
            # Press in order (modifiers first)
            for keycode in keycodes:
                self.ui.write(e.EV_KEY, keycode, state)
        else:
            # Release in reverse order
            for keycode in reversed(keycodes):
                self.ui.write(e.EV_KEY, keycode, state)

        self.ui.syn()

    def send_key(self, keycode):
        """Emit a single key press + release."""
        if not self._evdev_available:
            return
        self.ui.write(e.EV_KEY, keycode, 1)
        self.ui.write(e.EV_KEY, keycode, 0)
        self.ui.syn()

    def handle_raw_report(self, data: bytes | list[int]):
        """
        Given a raw G13 report (list of bytes), decode which logical button
        changed and emit the mapped key, if any.

        NOTE: This is the legacy CLI interface. The GUI uses handle_button_event instead.
        """
        try:
            state = self.decoder.decode_report(data)
            pressed, released = self.decoder.get_button_changes(state)

            # Emit key events for button changes
            for button_id in pressed:
                self.handle_button_event(button_id, is_pressed=True)

            for button_id in released:
                self.handle_button_event(button_id, is_pressed=False)

        except ValueError:
            # Invalid report length - ignore
            pass
