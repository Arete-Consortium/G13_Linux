"""
G13 Button Widget

Custom QPushButton representing a single G13 button with Logitech-style theming.
Supports highlighting when physically pressed, bound state display, and tooltips.
"""

try:
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtGui import QCursor, QFont
    from PyQt6.QtWidgets import QMenu, QPushButton
except ImportError:  # pragma: no cover
    # Stub for development without PyQt6
    class QPushButton:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

    class Qt:  # type: ignore[no-redef]
        class CursorShape:
            PointingHandCursor = 0

    class QCursor:  # type: ignore[no-redef]
        pass

    class QFont:  # type: ignore[no-redef]
        Bold = 75

    class QMenu:  # type: ignore[no-redef]
        pass

    def pyqtSignal(*args):  # type: ignore[no-redef]
        return None


# Logitech blue theme colors (semi-transparent for overlay on device image)
LOGITECH_BLUE = "#00B8FC"
LOGITECH_BLUE_HOVER = "#33c9ff"

# Button state styles - improved visibility with better contrast
STYLE_NORMAL = """
    QPushButton {
        background: rgba(30, 30, 35, 200);
        color: rgba(220, 220, 220, 255);
        border: 1px solid rgba(80, 80, 85, 220);
        border-radius: 4px;
        font-size: 9px;
        font-weight: bold;
        padding: 2px;
    }
"""

STYLE_HOVER = """
    QPushButton {
        background: rgba(45, 55, 70, 220);
        color: #ffffff;
        border: 2px solid #00B8FC;
        border-radius: 4px;
        font-size: 9px;
        font-weight: bold;
        padding: 2px;
    }
"""

STYLE_ACTIVE = """
    QPushButton {
        background: rgba(0, 184, 252, 230);
        color: #000000;
        border: 2px solid #00D4FF;
        border-radius: 4px;
        font-size: 9px;
        font-weight: bold;
        padding: 2px;
    }
"""

STYLE_BOUND = """
    QPushButton {
        background: rgba(35, 55, 35, 200);
        color: #99dd99;
        border: 1px solid rgba(80, 120, 80, 230);
        border-radius: 4px;
        font-size: 9px;
        font-weight: bold;
        padding: 2px;
    }
"""

STYLE_BOUND_HOVER = """
    QPushButton {
        background: rgba(45, 75, 55, 220);
        color: #bbffbb;
        border: 2px solid #00B8FC;
        border-radius: 4px;
        font-size: 9px;
        font-weight: bold;
        padding: 2px;
    }
"""


class G13Button(QPushButton):
    """
    Individual G13 button widget with Logitech-style theming.

    Features:
    - Visual states: normal, hover, active (pressed), bound
    - Semi-transparent background to show device image
    - Logitech blue hover/active accent color
    - Tooltip showing current binding
    - Truncated binding display on button face
    """

    clicked_with_id = pyqtSignal(str)  # Emits button_id when clicked
    unbind_requested = pyqtSignal(str)  # Emits button_id when unbind is requested
    hover_changed = pyqtSignal(str, bool)  # Emits button_id + hover state

    _DISPLAY_ALIASES = {
        "LEFTCTRL": "LCTRL",
        "RIGHTCTRL": "RCTRL",
        "LEFTSHIFT": "LSHFT",
        "RIGHTSHIFT": "RSHFT",
        "LEFTALT": "LALT",
        "RIGHTALT": "RALT",
        "LEFTMETA": "LSUPR",
        "RIGHTMETA": "RSUPR",
        "BACKSPACE": "BSP",
        "DELETE": "DEL",
        "INSERT": "INS",
        "PAGEUP": "PGUP",
        "PAGEDOWN": "PGDN",
        "ESCAPE": "ESC",
    }

    def __init__(self, button_id: str, parent=None):
        super().__init__(button_id, parent)
        self.button_id = button_id
        self.mapped_key = None
        self.is_highlighted = False
        self._is_hovered = False

        # Setup cursor and font
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        self.setFont(font)

        self._update_display()
        self._apply_style()

    def set_mapping(self, key_name: str | dict | None):
        """
        Set the mapped key and update display.

        Args:
            key_name: Key code name (e.g., 'KEY_1'), combo dict, or None to clear
                      Combo format: {'keys': ['KEY_LEFTCTRL', 'KEY_B'], 'label': '...'}
        """
        self.mapped_key = key_name
        self._update_display()
        self._apply_style()

    def set_highlighted(self, highlight: bool):
        """
        Highlight button when physically pressed on device.

        Args:
            highlight: True to highlight, False to unhighlight
        """
        self.is_highlighted = highlight
        self._apply_style()

    def _has_mapping(self) -> bool:
        """Check if button has a valid mapping."""
        if not self.mapped_key:
            return False
        if self.mapped_key == "KEY_RESERVED":
            return False
        if isinstance(self.mapped_key, dict):
            return bool(self.mapped_key.get("keys"))
        return True

    def _get_binding_display(self) -> str:
        """Get the binding text for display on button (truncated if needed)."""
        if not self.mapped_key or self.mapped_key == "KEY_RESERVED":
            return ""

        if isinstance(self.mapped_key, dict):
            # Combo key format
            label = self.mapped_key.get("label", "")
            if label:
                binding = label
            else:
                keys = self.mapped_key.get("keys", [])
                short_keys = [self._compact_key_name(k) for k in keys if isinstance(k, str) and k]
                if not short_keys:
                    return ""
                binding = "+".join(short_keys)
                if len(binding) > 9 and len(short_keys) >= 2:
                    compressed = [key[0] if len(key) > 1 else key for key in short_keys[:-1]]
                    compressed.append(short_keys[-1][:3])
                    binding = "+".join(compressed)
        else:
            # Simple key format
            binding = self._compact_key_name(str(self.mapped_key))

        # Truncate long bindings
        if len(binding) > 9:
            return binding[:8] + "…"
        return binding

    def _compact_key_name(self, key_name: str) -> str:
        """Return compact display token for KEY_* values."""
        raw = key_name.replace("KEY_", "")
        return self._DISPLAY_ALIASES.get(raw, raw)

    def _get_binding_full(self) -> str:
        """Get the full binding text for tooltip."""
        if not self.mapped_key or self.mapped_key == "KEY_RESERVED":
            return "Unbound"

        if isinstance(self.mapped_key, dict):
            label = self.mapped_key.get("label", "")
            keys = self.mapped_key.get("keys", [])
            short_keys = [k.replace("KEY_", "") for k in keys]
            combo = "+".join(short_keys)
            if label:
                return f"{label} ({combo})"
            return combo

        return self.mapped_key.replace("KEY_", "")

    def _update_display(self):
        """Update button text and tooltip."""
        binding = self._get_binding_display()

        if binding:
            # Show mapped action only to reduce visual clutter in dense layouts.
            self.setText(binding)
        else:
            self.setText(self.button_id)

        # Update tooltip
        full_binding = self._get_binding_full()
        self.setToolTip(
            f"{self.button_id}: {full_binding}\nLeft-click to change binding\n"
            "Right-click for binding actions"
        )

    def get_binding_summary(self) -> str:
        """Return full binding summary for hover/details panels."""
        return f"{self.button_id}: {self._get_binding_full()}"

    def _apply_style(self):
        """Apply appropriate style based on current state."""
        if self.is_highlighted:
            # Physically pressed on device - bright Logitech blue
            self.setStyleSheet(STYLE_ACTIVE)
        elif self._is_hovered:
            # Mouse hovering
            if self._has_mapping():
                self.setStyleSheet(STYLE_BOUND_HOVER)
            else:
                self.setStyleSheet(STYLE_HOVER)
        elif self._has_mapping():
            # Has a binding - green tint
            self.setStyleSheet(STYLE_BOUND)
        else:
            # Normal state - transparent
            self.setStyleSheet(STYLE_NORMAL)

    def enterEvent(self, event):
        """Mouse hover enter."""
        self._is_hovered = True
        if not self.is_highlighted:
            self._apply_style()
        self.hover_changed.emit(self.button_id, True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse hover leave."""
        self._is_hovered = False
        if not self.is_highlighted:
            self._apply_style()
        self.hover_changed.emit(self.button_id, False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Emit clicked_with_id signal."""
        self.clicked_with_id.emit(self.button_id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """Show quick actions for this button."""
        menu = QMenu(self)
        clear_action = menu.addAction("Clear Binding")
        clear_action.setEnabled(self._has_mapping())

        selected_action = menu.exec(event.globalPos())
        if selected_action == clear_action and self._has_mapping():
            self.unbind_requested.emit(self.button_id)
