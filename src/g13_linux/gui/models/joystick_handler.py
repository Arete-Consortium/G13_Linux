"""
Joystick Handler

Handles G13 joystick input with two modes:
1. Analog mode: Outputs as a virtual joystick device
2. Digital mode: Maps joystick directions to keyboard keys
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

try:
    from evdev import AbsInfo, UInput
    from evdev import ecodes as e
except Exception:  # pragma: no cover - exercised on non-Linux/dev hosts

    class AbsInfo:  # type: ignore[no-redef]
        """Lightweight fallback to preserve constructor compatibility in tests."""

        def __init__(self, value=0, min=0, max=0, fuzz=0, flat=0, resolution=0):
            self.value = value
            self.min = min
            self.max = max
            self.fuzz = fuzz
            self.flat = flat
            self.resolution = resolution

    class _FallbackEcodes:
        """Best-effort ecodes shim when evdev is unavailable."""

        EV_KEY = 0x01
        EV_ABS = 0x03
        ABS_X = 0x00
        ABS_Y = 0x01
        BTN_JOYSTICK = 0x120

        def __init__(self):
            self._key_cache: dict[str, int] = {}

        def __getattr__(self, name: str) -> int:
            if name.startswith("KEY_"):
                if name not in self._key_cache:
                    # Keep deterministic synthetic keycodes.
                    self._key_cache[name] = len(self._key_cache) + 0x100
                return self._key_cache[name]
            raise AttributeError(name)

    class UInput:  # type: ignore[no-redef]
        """Fallback UInput that raises; caller catches and surfaces cleanly."""

        def __init__(self, *args, **kwargs):
            del args, kwargs
            raise RuntimeError("evdev unavailable")

    e = _FallbackEcodes()  # type: ignore[assignment]


logger = logging.getLogger(__name__)


class JoystickMode(Enum):
    """Joystick operation mode"""

    ANALOG = "analog"  # Virtual joystick output
    DIGITAL = "digital"  # Direction-to-key mapping
    DISABLED = "disabled"  # Passthrough only (for games with native support)


@dataclass
class JoystickConfig:
    """Joystick configuration"""

    mode: JoystickMode = JoystickMode.ANALOG
    deadzone: int = 20  # Center deadzone (0-127)
    sensitivity: float = 1.0  # Axis sensitivity multiplier

    # Digital mode key mappings (evdev key names).
    # Each direction can be a single key OR a modifier combo (e.g. Ctrl+L).
    # Stored as a tuple so the dataclass default is hashable. JSON profiles
    # can specify either a string ("KEY_L") or a list (["KEY_LEFTCTRL", "KEY_L"])
    # — both are normalized to a tuple via _parse_key_mapping.
    key_up: tuple[str, ...] = ("KEY_UP",)
    key_down: tuple[str, ...] = ("KEY_DOWN",)
    key_left: tuple[str, ...] = ("KEY_LEFT",)
    key_right: tuple[str, ...] = ("KEY_RIGHT",)

    # Diagonal support
    allow_diagonals: bool = True

    def __post_init__(self):
        """Normalize key_* fields to tuples regardless of caller input shape.

        Allows direct construction with strings (legacy) or lists, e.g.:
            JoystickConfig(key_up="KEY_W")
            JoystickConfig(key_up=["KEY_LEFTCTRL", "KEY_L"])
        Both end up as tuples internally.
        """
        self.key_up = self._coerce_key_seq(self.key_up)
        self.key_down = self._coerce_key_seq(self.key_down)
        self.key_left = self._coerce_key_seq(self.key_left)
        self.key_right = self._coerce_key_seq(self.key_right)

    @staticmethod
    def _coerce_key_seq(value) -> tuple[str, ...]:
        """Coerce a value (str/list/tuple) into a tuple of key names."""
        if isinstance(value, tuple):
            return value
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list):
            return tuple(v for v in value if isinstance(v, str))
        return (str(value),)

    @staticmethod
    def _parse_key_mapping(value, default: str) -> tuple[str, ...]:
        """
        Parse key mapping from modern, combo, or legacy profile formats.

        Returns a tuple of evdev key names. Single-key values become a
        1-tuple; combos return all modifier+key components in order.

        Supported formats:
        - "KEY_W" → ("KEY_W",)
        - ["KEY_LEFTCTRL", "KEY_L"] → ("KEY_LEFTCTRL", "KEY_L")
        - {"keys": ["KEY_LEFTCTRL", "KEY_L"], ...} → ("KEY_LEFTCTRL", "KEY_L")
        - {"key": "KEY_W"} → ("KEY_W",)
        """
        if isinstance(value, str):
            return (value,)

        if isinstance(value, dict):
            keys = value.get("keys", [])
            if isinstance(keys, list):
                collected = tuple(k for k in keys if isinstance(k, str))
                if collected:
                    return collected

            key_name = value.get("key")
            if isinstance(key_name, str):
                return (key_name,)

            return (default,)

        if isinstance(value, list | tuple):
            collected = tuple(k for k in value if isinstance(k, str))
            if collected:
                return collected

        return (default,)

    @classmethod
    def from_dict(cls, data: dict) -> "JoystickConfig":
        """Create config from dict (profile loading), including legacy formats."""
        if not isinstance(data, dict):
            data = {}

        mode_str = data.get("mode")
        if mode_str is None:
            # Legacy directional configs without explicit modern mode
            if any(direction in data for direction in ("up", "down", "left", "right")):
                mode_str = "digital"
            else:
                mode_str = "analog"

        mode_aliases = {
            "directional": "digital",  # legacy profile value
        }
        mode_str = mode_aliases.get(str(mode_str).lower(), str(mode_str).lower())

        try:
            mode = JoystickMode(mode_str)
        except ValueError:
            mode = JoystickMode.ANALOG

        # Accept both modern flat keys and legacy directional objects
        key_up = data.get("key_up", data.get("up"))
        key_down = data.get("key_down", data.get("down"))
        key_left = data.get("key_left", data.get("left"))
        key_right = data.get("key_right", data.get("right"))

        return cls(
            mode=mode,
            deadzone=data.get("deadzone", 20),
            sensitivity=data.get("sensitivity", 1.0),
            key_up=cls._parse_key_mapping(key_up, "KEY_UP"),
            key_down=cls._parse_key_mapping(key_down, "KEY_DOWN"),
            key_left=cls._parse_key_mapping(key_left, "KEY_LEFT"),
            key_right=cls._parse_key_mapping(key_right, "KEY_RIGHT"),
            allow_diagonals=data.get("allow_diagonals", True),
        )

    def to_dict(self) -> dict:
        """Convert to dict (profile saving).

        For backward compatibility, single-key directions serialize as strings
        (the legacy format). Combos serialize as lists. This way pre-combo
        profiles round-trip identically.
        """

        def _serialize(keys: tuple[str, ...]):
            return keys[0] if len(keys) == 1 else list(keys)

        return {
            "mode": self.mode.value,
            "deadzone": self.deadzone,
            "sensitivity": self.sensitivity,
            "key_up": _serialize(self.key_up),
            "key_down": _serialize(self.key_down),
            "key_left": _serialize(self.key_left),
            "key_right": _serialize(self.key_right),
            "allow_diagonals": self.allow_diagonals,
        }


class JoystickHandler:
    """
    Handles G13 joystick with analog and digital modes.

    Analog mode creates a virtual joystick device that games can use.
    Digital mode converts stick position to keyboard arrow keys.
    """

    # G13 joystick is centered at approximately these values
    CENTER_X = 128
    CENTER_Y = 128

    def __init__(self, config: JoystickConfig | None = None):
        self.config = config or JoystickConfig()
        self._analog_device: UInput | None = None
        self._key_device: UInput | None = None

        # Track digital mode key states to avoid repeat events
        self._keys_pressed: set[str] = set()

        # Last raw position (for change detection)
        self._last_x = self.CENTER_X
        self._last_y = self.CENTER_Y

        # Callback for UI updates
        self.on_direction_change: Callable[[str], None] | None = None

    def start(self) -> bool:
        """Initialize the joystick device based on mode"""
        try:
            if self.config.mode == JoystickMode.ANALOG:
                self._start_analog()
            elif self.config.mode == JoystickMode.DIGITAL:
                self._start_digital()
            return True
        except Exception as e:
            logger.warning(f"Failed to start joystick handler: {e}")
            return False

    def _start_analog(self):
        """Create virtual joystick device"""
        # Define joystick capabilities
        capabilities = {
            e.EV_ABS: [
                # X axis: 0-255, centered at 128
                (e.ABS_X, AbsInfo(value=128, min=0, max=255, fuzz=0, flat=15, resolution=0)),
                # Y axis: 0-255, centered at 128
                (e.ABS_Y, AbsInfo(value=128, min=0, max=255, fuzz=0, flat=15, resolution=0)),
            ],
            e.EV_KEY: [e.BTN_JOYSTICK],  # Joystick button (stick click)
        }

        self._analog_device = UInput(
            capabilities, name="G13 Joystick", vendor=0x046D, product=0xC21C
        )

    def _start_digital(self):
        """Create keyboard device for direction keys"""
        # Collect all configured keys (each direction may be a combo, so flatten)
        keys = set()
        for key_tuple in [
            self.config.key_up,
            self.config.key_down,
            self.config.key_left,
            self.config.key_right,
        ]:
            for key_name in key_tuple:
                if hasattr(e, key_name):
                    keys.add(getattr(e, key_name))

        if keys:
            self._key_device = UInput({e.EV_KEY: list(keys)}, name="G13 Joystick Keys")

    def stop(self):
        """Close joystick devices"""
        if self._analog_device:
            self._analog_device.close()
            self._analog_device = None
        if self._key_device:
            # Release any held keys
            for key_name in self._keys_pressed:
                self._emit_key(key_name, False)
            self._keys_pressed.clear()
            self._key_device.close()
            self._key_device = None

    def set_config(self, config: JoystickConfig):
        """Update configuration (may require restart)"""
        mode_changed = config.mode != self.config.mode
        self.config = config

        if mode_changed:
            self.stop()
            self.start()

    def update(self, raw_x: int, raw_y: int):
        """
        Process joystick position update.

        Args:
            raw_x: Raw X axis value (0-255, center ~128)
            raw_y: Raw Y axis value (0-255, center ~128)
        """
        if self.config.mode == JoystickMode.DISABLED:
            return

        # Apply sensitivity
        centered_x = raw_x - self.CENTER_X
        centered_y = raw_y - self.CENTER_Y

        scaled_x = int(centered_x * self.config.sensitivity)
        scaled_y = int(centered_y * self.config.sensitivity)

        # Clamp to valid range
        final_x = max(0, min(255, scaled_x + self.CENTER_X))
        final_y = max(0, min(255, scaled_y + self.CENTER_Y))

        if self.config.mode == JoystickMode.ANALOG:
            self._update_analog(final_x, final_y)
        elif self.config.mode == JoystickMode.DIGITAL:
            self._update_digital(centered_x, centered_y)

        self._last_x = raw_x
        self._last_y = raw_y

    def _update_analog(self, x: int, y: int):
        """Send analog joystick events"""
        if not self._analog_device:
            return

        self._analog_device.write(e.EV_ABS, e.ABS_X, x)
        self._analog_device.write(e.EV_ABS, e.ABS_Y, y)
        self._analog_device.syn()

    def _update_digital(self, centered_x: int, centered_y: int):
        """Convert joystick position to key presses"""
        deadzone = self.config.deadzone

        # Determine which directions are active
        left = centered_x < -deadzone
        right = centered_x > deadzone
        up = centered_y < -deadzone  # Y is inverted (up = negative)
        down = centered_y > deadzone

        # Build set of keys that should be pressed.
        # Each direction may be a combo (e.g. Ctrl+L), so .update() with the
        # whole tuple — not .add() of a single key.
        should_press: set[str] = set()

        if up:
            should_press.update(self.config.key_up)
        if down:
            should_press.update(self.config.key_down)
        if left:
            should_press.update(self.config.key_left)
        if right:
            should_press.update(self.config.key_right)

        # Handle diagonal restriction.
        # NOTE: count by number of *active directions*, not number of keys
        # (a single combo direction can produce 2+ keys).
        active_dirs = sum([up, down, left, right])
        if not self.config.allow_diagonals and active_dirs > 1:
            # Pick the dominant direction (larger magnitude)
            if abs(centered_x) > abs(centered_y):
                should_press = set(self.config.key_left if left else self.config.key_right)
            else:
                should_press = set(self.config.key_up if up else self.config.key_down)

        # Release keys that should no longer be pressed
        for key_name in self._keys_pressed - should_press:
            self._emit_key(key_name, False)

        # Press keys that should now be pressed
        for key_name in should_press - self._keys_pressed:
            self._emit_key(key_name, True)

        self._keys_pressed = should_press

        # Notify UI of direction
        if self.on_direction_change:
            direction = self._get_direction_string(up, down, left, right)
            self.on_direction_change(direction)

    def _emit_key(self, key_name: str, pressed: bool):
        """Emit a key press/release event"""
        if not self._key_device:
            return

        if hasattr(e, key_name):
            keycode = getattr(e, key_name)
            self._key_device.write(e.EV_KEY, keycode, 1 if pressed else 0)
            self._key_device.syn()

    def _get_direction_string(self, up: bool, down: bool, left: bool, right: bool) -> str:
        """Get human-readable direction string"""
        if not any([up, down, left, right]):
            return "center"

        parts = []
        if up:
            parts.append("up")
        if down:
            parts.append("down")
        if left:
            parts.append("left")
        if right:
            parts.append("right")

        return "+".join(parts)

    def handle_stick_click(self, pressed: bool):
        """Handle joystick button (stick click) in analog mode"""
        if self._analog_device and self.config.mode == JoystickMode.ANALOG:
            self._analog_device.write(e.EV_KEY, e.BTN_JOYSTICK, 1 if pressed else 0)
            self._analog_device.syn()

    def get_current_direction(self) -> str:
        """Get current direction based on last position"""
        centered_x = self._last_x - self.CENTER_X
        centered_y = self._last_y - self.CENTER_Y
        deadzone = self.config.deadzone

        up = centered_y < -deadzone
        down = centered_y > deadzone
        left = centered_x < -deadzone
        right = centered_x > deadzone

        return self._get_direction_string(up, down, left, right)
