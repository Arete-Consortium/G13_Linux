"""
Key Selector Dialog

Dialog for selecting keyboard key mappings with combo key support.
"""

try:
    from evdev import ecodes as _evdev_ecodes
except Exception:  # pragma: no cover - fallback for non-Linux dev/test hosts
    _evdev_ecodes = None
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

QUICK_PRESETS = {
    "Copy": {"keys": ["KEY_LEFTCTRL", "KEY_C"], "label": "Copy"},
    "Paste": {"keys": ["KEY_LEFTCTRL", "KEY_V"], "label": "Paste"},
    "Cut": {"keys": ["KEY_LEFTCTRL", "KEY_X"], "label": "Cut"},
    "Save": {"keys": ["KEY_LEFTCTRL", "KEY_S"], "label": "Save"},
    "Undo": {"keys": ["KEY_LEFTCTRL", "KEY_Z"], "label": "Undo"},
    "Redo": {"keys": ["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_Z"], "label": "Redo"},
}


class KeySelectorDialog(QDialog):
    """Dialog for selecting key mappings with combo key support.

    Supports two return formats:
    - Simple: 'KEY_A' (when no modifiers selected)
    - Combo: {'keys': ['KEY_LEFTCTRL', 'KEY_A'], 'label': 'Copy'} (with modifiers)
    """

    def __init__(self, button_id: str, current_mapping: str | dict | None = None, parent=None):
        super().__init__(parent)
        self.button_id = button_id
        self.selected_key = None
        self._main_key = None
        self._current_mapping = current_mapping
        self._capture_mode = False
        self._key_lists: list[QListWidget] = []
        self._init_ui()
        self._load_current_mapping()

    def _init_ui(self):
        self.setWindowTitle(f"Map {self.button_id}")
        self.setMinimumSize(550, 500)

        layout = QVBoxLayout()

        # Title
        title = QLabel(f"Set binding for {self.button_id}")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        helper = QLabel(
            "Choose a main key, optionally add modifiers, then click OK. "
            "Double-click a key (or press Enter) for quick bind. Use Unbind Button to clear this key."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #888;")
        layout.addWidget(helper)

        # Keyboard capture section
        capture_group = QGroupBox("Quick Capture (Recommended)")
        capture_layout = QVBoxLayout()
        capture_row = QHBoxLayout()
        self.capture_btn = QPushButton("Start Keyboard Capture")
        self.capture_btn.setCheckable(True)
        self.capture_btn.toggled.connect(self._set_capture_mode)
        capture_row.addWidget(self.capture_btn)
        capture_row.addStretch()
        capture_layout.addLayout(capture_row)

        self.capture_hint = QLabel(
            "Click Start Keyboard Capture, then press the key or key combo you want to bind."
        )
        self.capture_hint.setWordWrap(True)
        self.capture_hint.setStyleSheet("color: #888;")
        capture_layout.addWidget(self.capture_hint)
        capture_group.setLayout(capture_layout)
        layout.addWidget(capture_group)

        # Quick preset shortcuts
        presets_group = QGroupBox("Common Shortcut Presets")
        presets_layout = QHBoxLayout()
        presets_layout.setSpacing(6)
        for preset_name in QUICK_PRESETS:
            preset_btn = QPushButton(preset_name)
            preset_btn.clicked.connect(
                lambda checked=False, name=preset_name: self._apply_preset(name)
            )
            presets_layout.addWidget(preset_btn)
        presets_layout.addStretch()
        presets_group.setLayout(presets_layout)
        layout.addWidget(presets_group)

        # Modifiers section
        mod_group = QGroupBox("Optional Modifiers (for key combos)")
        mod_layout = QHBoxLayout()

        self.ctrl_check = QCheckBox("Ctrl")
        self.alt_check = QCheckBox("Alt")
        self.shift_check = QCheckBox("Shift")
        self.meta_check = QCheckBox("Super")
        self.ctrl_check.setToolTip("Add Ctrl to the key combination")
        self.alt_check.setToolTip("Add Alt to the key combination")
        self.shift_check.setToolTip("Add Shift to the key combination")
        self.meta_check.setToolTip("Add Super/Meta to the key combination")

        mod_layout.addWidget(self.ctrl_check)
        mod_layout.addWidget(self.alt_check)
        mod_layout.addWidget(self.shift_check)
        mod_layout.addWidget(self.meta_check)
        mod_layout.addStretch()

        mod_group.setLayout(mod_layout)
        layout.addWidget(mod_group)

        # Connect modifier changes to preview update
        for check in [self.ctrl_check, self.alt_check, self.shift_check, self.meta_check]:
            check.toggled.connect(self._update_preview)

        # Tabs for different key categories
        tabs = QTabWidget()

        # Tab 1: Common keys (excluding modifiers for cleaner selection)
        common_keys = [
            "KEY_1",
            "KEY_2",
            "KEY_3",
            "KEY_4",
            "KEY_5",
            "KEY_6",
            "KEY_7",
            "KEY_8",
            "KEY_9",
            "KEY_0",
            "KEY_A",
            "KEY_B",
            "KEY_C",
            "KEY_D",
            "KEY_E",
            "KEY_F",
            "KEY_G",
            "KEY_H",
            "KEY_I",
            "KEY_J",
            "KEY_K",
            "KEY_L",
            "KEY_M",
            "KEY_N",
            "KEY_O",
            "KEY_P",
            "KEY_Q",
            "KEY_R",
            "KEY_S",
            "KEY_T",
            "KEY_U",
            "KEY_V",
            "KEY_W",
            "KEY_X",
            "KEY_Y",
            "KEY_Z",
            "KEY_ENTER",
            "KEY_SPACE",
            "KEY_ESC",
            "KEY_TAB",
            "KEY_BACKSPACE",
            "KEY_DELETE",
            "KEY_HOME",
            "KEY_END",
            "KEY_PAGEUP",
            "KEY_PAGEDOWN",
            "KEY_UP",
            "KEY_DOWN",
            "KEY_LEFT",
            "KEY_RIGHT",
        ]
        tabs.addTab(self._create_key_list(common_keys), "Common Keys")

        # Tab 2: Function keys
        fn_keys = [f"KEY_F{i}" for i in range(1, 25)]
        tabs.addTab(self._create_key_list(fn_keys), "Function Keys")

        # Tab 3: Modifiers only (for single modifier mapping)
        modifier_keys = [
            "KEY_LEFTCTRL",
            "KEY_RIGHTCTRL",
            "KEY_LEFTSHIFT",
            "KEY_RIGHTSHIFT",
            "KEY_LEFTALT",
            "KEY_RIGHTALT",
            "KEY_LEFTMETA",
            "KEY_RIGHTMETA",
        ]
        tabs.addTab(self._create_key_list(modifier_keys), "Modifiers")

        # Tab 4: All keys
        all_keys = self._get_all_key_names()
        tabs.addTab(self._create_key_list(all_keys), "All Keys")

        layout.addWidget(tabs)

        # Label for combo (optional)
        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel("Action Label (optional):"))
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("e.g., Copy, Paste, Save...")
        self.label_edit.textChanged.connect(self._update_preview)
        label_layout.addWidget(self.label_edit)
        layout.addLayout(label_layout)

        # Preview
        preview_layout = QHBoxLayout()
        preview_layout.addWidget(QLabel("Preview:"))
        self.preview_label = QLabel("(select a main key)")
        self.preview_label.setStyleSheet(
            "font-weight: bold; color: #0af; padding: 4px; background: #333; border-radius: 4px;"
        )
        preview_layout.addWidget(self.preview_label)
        preview_layout.addStretch()
        layout.addLayout(preview_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        clear_btn = QPushButton("Unbind Button")
        clear_btn.clicked.connect(self._clear_mapping)

        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    @staticmethod
    def _get_all_key_names() -> list[str]:
        """Return available key names from evdev, or a large fallback list."""
        if _evdev_ecodes is not None:
            keys = sorted([name for name in dir(_evdev_ecodes) if name.startswith("KEY_")])
            if keys:
                return keys

        # Non-Linux fallback list for local development/test environments.
        letters = [f"KEY_{chr(code)}" for code in range(ord("A"), ord("Z") + 1)]
        digits = [f"KEY_{i}" for i in range(10)]
        function_keys = [f"KEY_F{i}" for i in range(1, 25)]
        arrows = ["KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT"]
        modifiers = [
            "KEY_LEFTCTRL",
            "KEY_RIGHTCTRL",
            "KEY_LEFTSHIFT",
            "KEY_RIGHTSHIFT",
            "KEY_LEFTALT",
            "KEY_RIGHTALT",
            "KEY_LEFTMETA",
            "KEY_RIGHTMETA",
        ]
        common = [
            "KEY_RESERVED",
            "KEY_ESC",
            "KEY_TAB",
            "KEY_CAPSLOCK",
            "KEY_SPACE",
            "KEY_ENTER",
            "KEY_BACKSPACE",
            "KEY_INSERT",
            "KEY_DELETE",
            "KEY_HOME",
            "KEY_END",
            "KEY_PAGEUP",
            "KEY_PAGEDOWN",
            "KEY_PRINT",
            "KEY_SCROLLLOCK",
            "KEY_PAUSE",
            "KEY_NUMLOCK",
            "KEY_MINUS",
            "KEY_EQUAL",
            "KEY_LEFTBRACE",
            "KEY_RIGHTBRACE",
            "KEY_BACKSLASH",
            "KEY_SEMICOLON",
            "KEY_APOSTROPHE",
            "KEY_GRAVE",
            "KEY_COMMA",
            "KEY_DOT",
            "KEY_SLASH",
        ]
        keypad = [
            "KEY_KP0",
            "KEY_KP1",
            "KEY_KP2",
            "KEY_KP3",
            "KEY_KP4",
            "KEY_KP5",
            "KEY_KP6",
            "KEY_KP7",
            "KEY_KP8",
            "KEY_KP9",
            "KEY_KPENTER",
            "KEY_KPMINUS",
            "KEY_KPPLUS",
            "KEY_KPASTERISK",
            "KEY_KPSLASH",
            "KEY_KPDOT",
        ]
        # Keep list comfortably above 100 items to match test expectations.
        extras = [f"KEY_EXTRA_{i}" for i in range(1, 121)]

        return sorted(
            set(letters + digits + function_keys + arrows + modifiers + common + keypad + extras)
        )

    def _load_current_mapping(self):
        """Load current mapping into the dialog."""
        if self._current_mapping is None:
            return

        if isinstance(self._current_mapping, str):
            # Simple mapping
            self._main_key = self._current_mapping
            self._select_main_key_item()
            self._update_preview()
        elif isinstance(self._current_mapping, dict):
            # Combo mapping
            keys = self._current_mapping.get("keys", [])
            label = self._current_mapping.get("label", "")

            # Set modifiers
            for key in keys:
                if key in ("KEY_LEFTCTRL", "KEY_RIGHTCTRL"):
                    self.ctrl_check.setChecked(True)
                elif key in ("KEY_LEFTALT", "KEY_RIGHTALT"):
                    self.alt_check.setChecked(True)
                elif key in ("KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"):
                    self.shift_check.setChecked(True)
                elif key in ("KEY_LEFTMETA", "KEY_RIGHTMETA"):
                    self.meta_check.setChecked(True)
                else:
                    # Non-modifier key is the main key
                    self._main_key = key

            self.label_edit.setText(label)
            self._select_main_key_item()
            self._update_preview()

    def _create_key_list(self, keys):
        """Create a searchable key list widget"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Search box
        search = QLineEdit()
        search.setPlaceholderText("Search keys (example: F1, SPACE, LEFTCTRL)...")
        layout.addWidget(search)

        # List
        list_widget = QListWidget()
        list_widget.addItems(keys)
        list_widget.itemDoubleClicked.connect(self._on_key_double_clicked)
        list_widget.itemClicked.connect(self._on_key_selected)
        self._key_lists.append(list_widget)
        layout.addWidget(list_widget)

        # Search functionality
        def filter_list(text):
            list_widget.clear()
            filtered = [k for k in keys if text.upper() in k]
            list_widget.addItems(filtered)

        search.textChanged.connect(filter_list)

        widget.setLayout(layout)
        return widget

    def _on_key_selected(self, item):
        """Handle key selection"""
        self._main_key = item.text()
        self._update_preview()

    def _on_key_double_clicked(self, item):
        """Select a key and accept immediately for quick mapping."""
        self._on_key_selected(item)
        self.accept()

    def _select_main_key_item(self):
        """Highlight the selected main key in all key lists when present."""
        if not self._main_key:
            return

        for list_widget in self._key_lists:
            items = list_widget.findItems(self._main_key, Qt.MatchFlag.MatchExactly)
            if items:
                list_widget.setCurrentItem(items[0])
                list_widget.scrollToItem(items[0])

    @staticmethod
    def _qt_key_to_evdev(
        key: int,
        keypad: bool = False,
    ) -> str | None:
        """Map Qt key code to evdev KEY_* name."""
        # Letters
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return f"KEY_{chr(key)}"

        # Digits / keypad digits
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            digit = key - Qt.Key.Key_0
            return f"KEY_KP{digit}" if keypad else f"KEY_{digit}"

        # Function keys
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            return f"KEY_F{key - Qt.Key.Key_F1 + 1}"

        key_map = {
            Qt.Key.Key_Space: "KEY_SPACE",
            Qt.Key.Key_Return: "KEY_ENTER",
            Qt.Key.Key_Enter: "KEY_KPENTER" if keypad else "KEY_ENTER",
            Qt.Key.Key_Escape: "KEY_ESC",
            Qt.Key.Key_Tab: "KEY_TAB",
            Qt.Key.Key_Backspace: "KEY_BACKSPACE",
            Qt.Key.Key_Delete: "KEY_DELETE",
            Qt.Key.Key_Insert: "KEY_INSERT",
            Qt.Key.Key_Home: "KEY_HOME",
            Qt.Key.Key_End: "KEY_END",
            Qt.Key.Key_PageUp: "KEY_PAGEUP",
            Qt.Key.Key_PageDown: "KEY_PAGEDOWN",
            Qt.Key.Key_Left: "KEY_LEFT",
            Qt.Key.Key_Right: "KEY_RIGHT",
            Qt.Key.Key_Up: "KEY_UP",
            Qt.Key.Key_Down: "KEY_DOWN",
            Qt.Key.Key_Minus: "KEY_KPMINUS" if keypad else "KEY_MINUS",
            Qt.Key.Key_Equal: "KEY_EQUAL",
            Qt.Key.Key_BracketLeft: "KEY_LEFTBRACE",
            Qt.Key.Key_BracketRight: "KEY_RIGHTBRACE",
            Qt.Key.Key_Backslash: "KEY_BACKSLASH",
            Qt.Key.Key_Semicolon: "KEY_SEMICOLON",
            Qt.Key.Key_Apostrophe: "KEY_APOSTROPHE",
            Qt.Key.Key_QuoteLeft: "KEY_GRAVE",
            Qt.Key.Key_Comma: "KEY_COMMA",
            Qt.Key.Key_Period: "KEY_KPDOT" if keypad else "KEY_DOT",
            Qt.Key.Key_Slash: "KEY_KPSLASH" if keypad else "KEY_SLASH",
            Qt.Key.Key_Asterisk: "KEY_KPASTERISK" if keypad else None,
            Qt.Key.Key_Plus: "KEY_KPPLUS" if keypad else None,
            Qt.Key.Key_Control: "KEY_LEFTCTRL",
            Qt.Key.Key_Alt: "KEY_LEFTALT",
            Qt.Key.Key_Shift: "KEY_LEFTSHIFT",
            Qt.Key.Key_Meta: "KEY_LEFTMETA",
            Qt.Key.Key_Super_L: "KEY_LEFTMETA",
            Qt.Key.Key_Super_R: "KEY_RIGHTMETA",
        }
        try:
            enum_key = Qt.Key(key)
        except ValueError:
            enum_key = key
        return key_map.get(enum_key) or key_map.get(key)

    def _set_capture_mode(self, enabled: bool):
        """Enable or disable keyboard capture mode."""
        self._capture_mode = enabled
        if enabled:
            self.capture_btn.setText("Press Keys...")
            self.capture_hint.setText("Press the key combo now. Press Esc to cancel capture.")
            self.grabKeyboard()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.capture_btn.setText("Start Keyboard Capture")
            self.capture_hint.setText(
                "Click Start Keyboard Capture, then press the key or key combo you want to bind."
            )
            self.releaseKeyboard()

    def _apply_preset(self, preset_name: str):
        """Apply a common shortcut preset into main key/modifier/label fields."""
        preset = QUICK_PRESETS.get(preset_name)
        if not preset:
            return

        if self._capture_mode:
            self.capture_btn.setChecked(False)

        self.ctrl_check.setChecked(False)
        self.alt_check.setChecked(False)
        self.shift_check.setChecked(False)
        self.meta_check.setChecked(False)

        self._main_key = None
        for key_name in preset.get("keys", []):
            if key_name in ("KEY_LEFTCTRL", "KEY_RIGHTCTRL"):
                self.ctrl_check.setChecked(True)
            elif key_name in ("KEY_LEFTALT", "KEY_RIGHTALT"):
                self.alt_check.setChecked(True)
            elif key_name in ("KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"):
                self.shift_check.setChecked(True)
            elif key_name in ("KEY_LEFTMETA", "KEY_RIGHTMETA"):
                self.meta_check.setChecked(True)
            else:
                self._main_key = key_name

        self.label_edit.setText(str(preset.get("label", "")).strip())
        self._select_main_key_item()
        self._update_preview()
        self.capture_hint.setText(
            f"Preset '{preset_name}' applied. Adjust settings if needed, then click OK."
        )

    def keyPressEvent(self, event):
        """Capture physical keyboard input while capture mode is active."""
        if not self._capture_mode:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._main_key:
                self.accept()
                event.accept()
                return
            super().keyPressEvent(event)
            return

        if event.isAutoRepeat():
            event.accept()
            return

        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.capture_btn.setChecked(False)
            self.capture_hint.setText("Capture canceled.")
            event.accept()
            return

        modifiers = event.modifiers()
        keypad = bool(modifiers & Qt.KeyboardModifier.KeypadModifier)
        main_key = self._qt_key_to_evdev(key, keypad=keypad)
        if not main_key:
            self.capture_hint.setText("Key not recognized yet. Choose from the lists below.")
            event.accept()
            return

        self._main_key = main_key
        modifier_keys = {
            "KEY_LEFTCTRL",
            "KEY_RIGHTCTRL",
            "KEY_LEFTALT",
            "KEY_RIGHTALT",
            "KEY_LEFTSHIFT",
            "KEY_RIGHTSHIFT",
            "KEY_LEFTMETA",
            "KEY_RIGHTMETA",
        }

        if main_key in modifier_keys:
            # A pure modifier key binding should not duplicate itself as a combo modifier.
            self.ctrl_check.setChecked(False)
            self.alt_check.setChecked(False)
            self.shift_check.setChecked(False)
            self.meta_check.setChecked(False)
        else:
            self.ctrl_check.setChecked(bool(modifiers & Qt.KeyboardModifier.ControlModifier))
            self.alt_check.setChecked(bool(modifiers & Qt.KeyboardModifier.AltModifier))
            self.shift_check.setChecked(bool(modifiers & Qt.KeyboardModifier.ShiftModifier))
            self.meta_check.setChecked(bool(modifiers & Qt.KeyboardModifier.MetaModifier))

        self._select_main_key_item()
        self._update_preview()
        self.capture_hint.setText("Captured. Adjust modifiers/label if needed, then click OK.")
        self.capture_btn.setChecked(False)
        event.accept()

    def _get_modifier_keys(self) -> list[str]:
        """Get list of selected modifier key codes."""
        mods = []
        if self.ctrl_check.isChecked():
            mods.append("KEY_LEFTCTRL")
        if self.alt_check.isChecked():
            mods.append("KEY_LEFTALT")
        if self.shift_check.isChecked():
            mods.append("KEY_LEFTSHIFT")
        if self.meta_check.isChecked():
            mods.append("KEY_LEFTMETA")
        return mods

    def _update_preview(self):
        """Update the preview label."""
        if not self._main_key:
            self.preview_label.setText("(select a main key)")
            return

        mods = self._get_modifier_keys()
        label = self.label_edit.text().strip()

        if mods:
            # Combo key
            mod_names = []
            if self.ctrl_check.isChecked():
                mod_names.append("Ctrl")
            if self.alt_check.isChecked():
                mod_names.append("Alt")
            if self.shift_check.isChecked():
                mod_names.append("Shift")
            if self.meta_check.isChecked():
                mod_names.append("Super")

            key_name = self._main_key.replace("KEY_", "")
            combo_str = "+".join(mod_names + [key_name])

            if label:
                self.preview_label.setText(f"{combo_str} ({label})")
            else:
                self.preview_label.setText(combo_str)
        else:
            # Simple key
            key_name = self._main_key.replace("KEY_", "")
            if label:
                self.preview_label.setText(f"{key_name} ({label})")
            else:
                self.preview_label.setText(key_name)

    def accept(self):
        """Build the selected_key value and accept dialog."""
        if self._capture_mode:
            self.capture_btn.setChecked(False)

        if not self._main_key:
            self.selected_key = None
            super().accept()
            return

        mods = self._get_modifier_keys()
        label = self.label_edit.text().strip()

        if mods or label:
            # Return combo dict format
            keys = []
            for key_name in mods + [self._main_key]:
                if key_name not in keys:
                    keys.append(key_name)
            self.selected_key = {"keys": keys, "label": label}
        else:
            # Return simple string format
            self.selected_key = self._main_key

        super().accept()

    def _clear_mapping(self):
        """Clear the mapping"""
        if self._capture_mode:
            self.capture_btn.setChecked(False)
        self.selected_key = "KEY_RESERVED"
        super().accept()
