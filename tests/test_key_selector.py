"""Tests for KeySelectorDialog widget."""

import pytest
from PyQt6.QtCore import Qt


class TestKeySelectorDialog:
    """Tests for KeySelectorDialog."""

    @pytest.fixture
    def dialog(self, qtbot):
        """Create KeySelectorDialog instance."""
        from g13_linux.gui.widgets.key_selector import KeySelectorDialog

        dlg = KeySelectorDialog("G5")
        qtbot.addWidget(dlg)
        return dlg

    def test_init_button_id(self, dialog):
        """Test dialog stores button ID."""
        assert dialog.button_id == "G5"

    def test_init_no_selection(self, dialog):
        """Test dialog starts with no selection."""
        assert dialog.selected_key is None

    def test_window_title(self, dialog):
        """Test window title includes button ID."""
        assert "G5" in dialog.windowTitle()

    def test_minimum_size(self, dialog):
        """Test minimum size is set."""
        assert dialog.minimumWidth() >= 500
        assert dialog.minimumHeight() >= 400

    def test_has_tab_widget(self, dialog):
        """Test dialog has tab widget."""
        from PyQt6.QtWidgets import QTabWidget

        tabs = dialog.findChild(QTabWidget)
        assert tabs is not None

    def test_has_four_tabs(self, dialog):
        """Test dialog has four tabs."""
        from PyQt6.QtWidgets import QTabWidget

        tabs = dialog.findChild(QTabWidget)
        assert tabs.count() == 4

    def test_tab_names(self, dialog):
        """Test tab names are correct."""
        from PyQt6.QtWidgets import QTabWidget

        tabs = dialog.findChild(QTabWidget)
        assert tabs.tabText(0) == "Common Keys"
        assert tabs.tabText(1) == "Function Keys"
        assert tabs.tabText(2) == "Modifiers"
        assert tabs.tabText(3) == "All Keys"

    def test_common_keys_tab_has_keys(self, dialog):
        """Test common keys tab has expected keys."""
        from PyQt6.QtWidgets import QListWidget, QTabWidget

        tabs = dialog.findChild(QTabWidget)
        common_tab = tabs.widget(0)
        list_widget = common_tab.findChild(QListWidget)

        items = [list_widget.item(i).text() for i in range(list_widget.count())]
        assert "KEY_1" in items
        assert "KEY_A" in items
        assert "KEY_SPACE" in items
        # Modifiers are now in a separate tab
        assert "KEY_LEFTCTRL" not in items

    def test_function_keys_tab_has_f_keys(self, dialog):
        """Test function keys tab has F1-F24."""
        from PyQt6.QtWidgets import QListWidget, QTabWidget

        tabs = dialog.findChild(QTabWidget)
        fn_tab = tabs.widget(1)
        list_widget = fn_tab.findChild(QListWidget)

        items = [list_widget.item(i).text() for i in range(list_widget.count())]
        assert "KEY_F1" in items
        assert "KEY_F12" in items
        assert "KEY_F24" in items
        assert list_widget.count() == 24

    def test_all_keys_tab_has_many_keys(self, dialog):
        """Test all keys tab has many keys from evdev."""
        from PyQt6.QtWidgets import QListWidget, QTabWidget

        tabs = dialog.findChild(QTabWidget)
        all_tab = tabs.widget(3)  # Now at index 3 (after Modifiers tab)
        list_widget = all_tab.findChild(QListWidget)

        # Should have many keys from evdev
        assert list_widget.count() > 100

    def test_modifiers_tab_has_modifier_keys(self, dialog):
        """Test modifiers tab has modifier keys."""
        from PyQt6.QtWidgets import QListWidget, QTabWidget

        tabs = dialog.findChild(QTabWidget)
        mod_tab = tabs.widget(2)
        list_widget = mod_tab.findChild(QListWidget)

        items = [list_widget.item(i).text() for i in range(list_widget.count())]
        assert "KEY_LEFTCTRL" in items
        assert "KEY_LEFTALT" in items
        assert "KEY_LEFTSHIFT" in items
        assert "KEY_LEFTMETA" in items

    def test_has_ok_button(self, dialog):
        """Test dialog has OK button."""
        from PyQt6.QtWidgets import QPushButton

        buttons = dialog.findChildren(QPushButton)
        ok_btn = next((b for b in buttons if b.text() == "OK"), None)
        assert ok_btn is not None

    def test_has_cancel_button(self, dialog):
        """Test dialog has Cancel button."""
        from PyQt6.QtWidgets import QPushButton

        buttons = dialog.findChildren(QPushButton)
        cancel_btn = next((b for b in buttons if b.text() == "Cancel"), None)
        assert cancel_btn is not None

    def test_has_clear_mapping_button(self, dialog):
        """Test dialog has Unbind Button button."""
        from PyQt6.QtWidgets import QPushButton

        buttons = dialog.findChildren(QPushButton)
        clear_btn = next((b for b in buttons if b.text() == "Unbind Button"), None)
        assert clear_btn is not None

    def test_has_keyboard_capture_button(self, dialog):
        """Test dialog has keyboard capture shortcut flow."""
        from PyQt6.QtWidgets import QPushButton

        buttons = dialog.findChildren(QPushButton)
        capture_btn = next((b for b in buttons if "Keyboard Capture" in b.text()), None)
        assert capture_btn is not None

    def test_select_key_from_list(self, dialog, qtbot):
        """Test selecting a key from list sets internal state."""
        from PyQt6.QtWidgets import QListWidget, QTabWidget

        tabs = dialog.findChild(QTabWidget)
        common_tab = tabs.widget(0)
        list_widget = common_tab.findChild(QListWidget)

        # Click on first item
        item = list_widget.item(0)
        list_widget.setCurrentItem(item)
        qtbot.mouseClick(
            list_widget.viewport(),
            Qt.MouseButton.LeftButton,
            pos=list_widget.visualItemRect(item).center(),
        )

        # The main key should be set (selected_key is set on accept())
        assert dialog._main_key is not None

    def test_double_click_key_accepts_immediately(self, dialog):
        """Double-click should select and accept in one action."""
        from PyQt6.QtWidgets import QListWidget, QTabWidget

        tabs = dialog.findChild(QTabWidget)
        common_tab = tabs.widget(0)
        list_widget = common_tab.findChild(QListWidget)
        item = list_widget.item(0)

        dialog._on_key_double_clicked(item)

        assert dialog.selected_key == item.text()

    def test_clear_mapping_sets_reserved(self, dialog, qtbot):
        """Test Unbind Button sets KEY_RESERVED."""
        from PyQt6.QtWidgets import QPushButton

        buttons = dialog.findChildren(QPushButton)
        clear_btn = next(b for b in buttons if b.text() == "Unbind Button")

        # Need to block accept() from closing
        dialog.done = lambda x: None
        qtbot.mouseClick(clear_btn, Qt.MouseButton.LeftButton)

        assert dialog.selected_key == "KEY_RESERVED"

    def test_search_filters_list(self, dialog, qtbot):
        """Test search box filters key list."""
        from PyQt6.QtWidgets import QLineEdit, QListWidget, QTabWidget

        tabs = dialog.findChild(QTabWidget)
        common_tab = tabs.widget(0)
        list_widget = common_tab.findChild(QListWidget)
        search_box = common_tab.findChild(QLineEdit)

        initial_count = list_widget.count()

        # Type in search box to filter (using SPACE since CTRL is in Modifiers tab now)
        search_box.setText("SPACE")
        qtbot.wait(50)  # Allow filter to apply

        # Should have fewer items
        assert list_widget.count() < initial_count
        # All items should contain SPACE
        for i in range(list_widget.count()):
            assert "SPACE" in list_widget.item(i).text()

    def test_different_button_id(self, qtbot):
        """Test dialog with different button ID."""
        from g13_linux.gui.widgets.key_selector import KeySelectorDialog

        dlg = KeySelectorDialog("G22")
        qtbot.addWidget(dlg)

        assert dlg.button_id == "G22"
        assert "G22" in dlg.windowTitle()


class TestKeySelectorComboKeys:
    """Tests for combo key functionality."""

    @pytest.fixture
    def dialog(self, qtbot):
        """Create KeySelectorDialog instance."""
        from g13_linux.gui.widgets.key_selector import KeySelectorDialog

        dlg = KeySelectorDialog("G5")
        qtbot.addWidget(dlg)
        return dlg

    def test_has_modifier_checkboxes(self, dialog):
        """Test dialog has modifier checkboxes."""
        from PyQt6.QtWidgets import QCheckBox

        checkboxes = dialog.findChildren(QCheckBox)
        labels = [cb.text() for cb in checkboxes]

        assert "Ctrl" in labels
        assert "Alt" in labels
        assert "Shift" in labels
        assert "Super" in labels

    def test_has_label_input(self, dialog):
        """Test dialog has label input field."""
        from PyQt6.QtWidgets import QLineEdit

        # Find the label input (not search boxes)
        line_edits = dialog.findChildren(QLineEdit)
        label_edit = next((le for le in line_edits if "Copy" in (le.placeholderText() or "")), None)
        assert label_edit is not None

    def test_has_preview_label(self, dialog):
        """Test dialog has preview label."""
        from PyQt6.QtWidgets import QLabel

        labels = dialog.findChildren(QLabel)
        preview = next((lbl for lbl in labels if "select a main key" in lbl.text()), None)
        assert preview is not None

    def test_simple_key_returns_string(self, dialog):
        """Test selecting key without modifiers returns string."""
        dialog._main_key = "KEY_A"
        dialog.accept()

        assert dialog.selected_key == "KEY_A"

    def test_combo_key_returns_dict(self, dialog):
        """Test selecting key with modifiers returns dict."""
        dialog._main_key = "KEY_A"
        dialog.ctrl_check.setChecked(True)
        dialog.accept()

        assert isinstance(dialog.selected_key, dict)
        assert "keys" in dialog.selected_key
        assert "KEY_LEFTCTRL" in dialog.selected_key["keys"]
        assert "KEY_A" in dialog.selected_key["keys"]

    def test_combo_with_label(self, dialog):
        """Test combo key with custom label."""
        dialog._main_key = "KEY_C"
        dialog.ctrl_check.setChecked(True)
        dialog.label_edit.setText("Copy")
        dialog.accept()

        assert isinstance(dialog.selected_key, dict)
        assert dialog.selected_key["label"] == "Copy"

    def test_multiple_modifiers(self, dialog):
        """Test selecting multiple modifiers."""
        dialog._main_key = "KEY_S"
        dialog.ctrl_check.setChecked(True)
        dialog.shift_check.setChecked(True)
        dialog.accept()

        assert isinstance(dialog.selected_key, dict)
        keys = dialog.selected_key["keys"]
        assert "KEY_LEFTCTRL" in keys
        assert "KEY_LEFTSHIFT" in keys
        assert "KEY_S" in keys

    def test_has_common_shortcut_preset_buttons(self, dialog):
        """Quick preset buttons should exist for common actions."""
        from PyQt6.QtWidgets import QPushButton

        buttons = dialog.findChildren(QPushButton)
        labels = {btn.text() for btn in buttons}
        assert "Copy" in labels
        assert "Paste" in labels
        assert "Save" in labels

    def test_apply_copy_preset(self, dialog):
        """Applying Copy preset should prefill Ctrl+C mapping."""
        dialog._apply_preset("Copy")
        dialog.accept()

        assert isinstance(dialog.selected_key, dict)
        assert dialog.selected_key["label"] == "Copy"
        assert "KEY_LEFTCTRL" in dialog.selected_key["keys"]
        assert "KEY_C" in dialog.selected_key["keys"]

    def test_enter_accepts_current_selection(self, dialog, qtbot):
        """Enter key should accept when a main key is selected."""
        dialog._main_key = "KEY_A"

        qtbot.keyClick(dialog, Qt.Key.Key_Return)

        assert dialog.selected_key == "KEY_A"

    def test_qt_key_to_evdev_letter(self):
        """Qt letter key should map to KEY_*."""
        from g13_linux.gui.widgets.key_selector import KeySelectorDialog

        assert KeySelectorDialog._qt_key_to_evdev(Qt.Key.Key_Q) == "KEY_Q"

    def test_qt_key_to_evdev_function_key(self):
        """Qt function key should map to KEY_F*."""
        from g13_linux.gui.widgets.key_selector import KeySelectorDialog

        assert KeySelectorDialog._qt_key_to_evdev(Qt.Key.Key_F5) == "KEY_F5"

    def test_load_existing_simple_mapping(self, qtbot):
        """Test loading existing simple mapping."""
        from g13_linux.gui.widgets.key_selector import KeySelectorDialog

        dlg = KeySelectorDialog("G5", current_mapping="KEY_F1")
        qtbot.addWidget(dlg)

        assert dlg._main_key == "KEY_F1"
        assert not dlg.ctrl_check.isChecked()

    def test_load_existing_combo_mapping(self, qtbot):
        """Test loading existing combo mapping."""
        from g13_linux.gui.widgets.key_selector import KeySelectorDialog

        mapping = {"keys": ["KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_DELETE"], "label": "CAD"}
        dlg = KeySelectorDialog("G5", current_mapping=mapping)
        qtbot.addWidget(dlg)

        assert dlg._main_key == "KEY_DELETE"
        assert dlg.ctrl_check.isChecked()
        assert dlg.alt_check.isChecked()
        assert not dlg.shift_check.isChecked()
        assert dlg.label_edit.text() == "CAD"
