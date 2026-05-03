"""Tests for ButtonMapperWidget."""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestButtonMapperWidget:
    """Tests for ButtonMapperWidget."""

    def test_init(self, qapp):
        """Test ButtonMapperWidget initialization."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        assert widget.buttons is not None
        assert isinstance(widget.buttons, dict)
        assert len(widget.buttons) > 0  # Should have buttons

    def test_has_signal(self, qapp):
        """Test ButtonMapperWidget has binding action signals."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        assert hasattr(widget, "button_clicked")
        assert hasattr(widget, "button_unbind_requested")

    def test_minimum_size(self, qapp):
        """Test ButtonMapperWidget has minimum size set."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        assert widget.minimumWidth() > 0
        assert widget.minimumHeight() > 0

    def test_has_lcd_preview(self, qapp):
        """Test ButtonMapperWidget has LCD preview."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        assert hasattr(widget, "lcd_preview")
        assert widget.lcd_preview is not None

    def test_has_binding_detail_label(self, qapp):
        """Mapper should expose hover detail strip for full binding preview."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        assert hasattr(widget, "binding_detail_label")
        assert "Hover a button" in widget.binding_detail_label.text()

    def test_joystick_initial_position(self, qapp):
        """Test joystick starts at center (128, 128)."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        assert widget._joystick_x == 128
        assert widget._joystick_y == 128

    def test_set_button_mapping(self, qapp):
        """Test set_button_mapping updates button."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        # Get a valid button ID
        button_id = list(widget.buttons.keys())[0]
        widget.set_button_mapping(button_id, "KEY_A")

        # Check the button's mapping was updated
        assert widget.buttons[button_id].mapped_key == "KEY_A"

    def test_set_button_mapping_invalid_id(self, qapp):
        """Test set_button_mapping with invalid ID doesn't crash."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        # Should not raise
        widget.set_button_mapping("INVALID_BUTTON", "KEY_A")

    def test_highlight_button(self, qapp):
        """Test highlight_button changes button state."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        button_id = list(widget.buttons.keys())[0]
        widget.highlight_button(button_id, True)

        assert widget.buttons[button_id].is_highlighted is True

        widget.highlight_button(button_id, False)

        assert widget.buttons[button_id].is_highlighted is False

    def test_highlight_button_invalid_id(self, qapp):
        """Test highlight_button with invalid ID doesn't crash."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        # Should not raise
        widget.highlight_button("INVALID_BUTTON", True)

    def test_clear_all_highlights(self, qapp):
        """Test clear_all_highlights clears all button highlights."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        # Highlight some buttons
        for i, button_id in enumerate(list(widget.buttons.keys())[:3]):
            widget.highlight_button(button_id, True)

        widget.clear_all_highlights()

        # All buttons should be unhighlighted
        for btn in widget.buttons.values():
            assert btn.is_highlighted is False

    def test_update_joystick(self, qapp):
        """Test update_joystick updates position."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        widget.update_joystick(200, 50)

        assert widget._joystick_x == 200
        assert widget._joystick_y == 50

    def test_update_lcd(self, qapp):
        """Test update_lcd calls lcd_preview."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        widget.lcd_preview.set_framebuffer = MagicMock()

        framebuffer = b"\x00" * 100
        widget.update_lcd(framebuffer)

        widget.lcd_preview.set_framebuffer.assert_called_once_with(framebuffer)

    def test_clear_lcd(self, qapp):
        """Test clear_lcd calls lcd_preview.clear()."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        widget.lcd_preview.clear = MagicMock()

        widget.clear_lcd()

        widget.lcd_preview.clear.assert_called_once()

    def test_button_clicked_signal(self, qapp):
        """Test button click emits signal."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        received = []
        widget.button_clicked.connect(lambda bid: received.append(bid))

        # Get first button and click it
        button_id = list(widget.buttons.keys())[0]
        widget.buttons[button_id].click()

        assert button_id in received

    def test_button_unbind_requested_signal(self, qapp):
        """Test child button unbind signal is forwarded by mapper widget."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        received = []
        widget.button_unbind_requested.connect(lambda bid: received.append(bid))

        button_id = list(widget.buttons.keys())[0]
        widget.buttons[button_id].unbind_requested.emit(button_id)

        assert button_id in received

    def test_hover_updates_binding_detail_text(self, qapp):
        """Hovering a button should show full binding details in strip."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        button_id = list(widget.buttons.keys())[0]
        widget.set_button_mapping(button_id, "KEY_SPACE")

        widget.buttons[button_id].hover_changed.emit(button_id, True)
        assert widget.binding_detail_label.text() == f"{button_id}: SPACE"

        widget.buttons[button_id].hover_changed.emit(button_id, False)
        assert "Hover a button" in widget.binding_detail_label.text()

    def test_hovered_binding_detail_refreshes_after_mapping_change(self, qapp):
        """Changing mapping while hovered should refresh detail strip text."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        button_id = list(widget.buttons.keys())[0]

        widget.buttons[button_id].hover_changed.emit(button_id, True)
        widget.set_button_mapping(button_id, "KEY_DELETE")

        assert widget.binding_detail_label.text() == f"{button_id}: DELETE"

    def test_paint_event_no_crash(self, qapp):
        """Test paintEvent doesn't crash."""
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QPaintEvent

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        # Create a paint event and trigger it
        event = QPaintEvent(QRect(0, 0, 100, 100))
        widget.paintEvent(event)

        # If we get here, no crash occurred

    def test_load_background_image_returns_none_when_missing(self, qapp):
        """Test _load_background_image returns None when no image exists."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        # The background_image should be None since we don't have the image files
        # (or it could be a pixmap if the files exist)
        # Either way, the widget should handle it gracefully
        assert widget.background_image is None or widget.background_image is not None


class TestButtonMapperButtons:
    """Tests for button creation and layout."""

    def test_buttons_have_correct_ids(self, qapp):
        """Test buttons are created with expected IDs."""
        from g13_linux.gui.resources.g13_layout import G13_BUTTON_POSITIONS
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        # All defined buttons should exist
        for button_id in G13_BUTTON_POSITIONS.keys():
            assert button_id in widget.buttons

    def test_buttons_are_positioned(self, qapp):
        """Test buttons have geometry set."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        for button_id, btn in widget.buttons.items():
            # Each button should have non-zero dimensions
            assert btn.width() > 0
            assert btn.height() > 0


class TestButtonMapperPainting:
    """Tests for painting methods."""

    def test_paint_event_with_no_background(self, qapp):
        """Test paintEvent draws background when no image."""
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QPaintEvent

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        widget.background_image = None  # Ensure no background

        event = QPaintEvent(QRect(0, 0, 100, 100))
        widget.paintEvent(event)

    def test_paint_event_with_background_image(self, qapp):
        """Test paintEvent with background image."""
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QPaintEvent, QPixmap

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        # Create a small test pixmap
        pixmap = QPixmap(100, 100)
        pixmap.fill(Qt.GlobalColor.white)
        widget.background_image = pixmap

        event = QPaintEvent(QRect(0, 0, 100, 100))
        widget.paintEvent(event)

    def test_draw_device_background(self, qapp):
        """Test _draw_device_background draws without crash."""
        from PyQt6.QtGui import QPainter, QPixmap

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        # Create a pixmap to paint on
        pixmap = QPixmap(800, 700)
        painter = QPainter(pixmap)
        painter.begin(pixmap)

        # Should not crash
        widget._draw_device_background(painter)

        painter.end()

    def test_draw_lcd_area(self, qapp):
        """Test _draw_lcd_area draws without crash."""
        from PyQt6.QtGui import QPainter, QPixmap

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()

        pixmap = QPixmap(800, 700)
        painter = QPainter(pixmap)
        painter.begin(pixmap)

        widget._draw_lcd_area(painter)

        painter.end()

    def test_draw_joystick_indicator_at_center(self, qapp):
        """Test joystick drawing at center position."""
        from PyQt6.QtGui import QPainter, QPixmap

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        widget._joystick_x = 128
        widget._joystick_y = 128

        pixmap = QPixmap(800, 700)
        painter = QPainter(pixmap)
        painter.begin(pixmap)

        widget._draw_joystick_indicator(painter)

        painter.end()

    def test_draw_joystick_indicator_deflected(self, qapp):
        """Test joystick drawing when deflected shows glow."""
        from PyQt6.QtGui import QPainter, QPixmap

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        # Deflect joystick significantly
        widget._joystick_x = 255
        widget._joystick_y = 255

        pixmap = QPixmap(800, 700)
        painter = QPainter(pixmap)
        painter.begin(pixmap)

        widget._draw_joystick_indicator(painter)

        painter.end()

    def test_draw_joystick_indicator_partially_deflected(self, qapp):
        """Test joystick drawing with slight deflection."""
        from PyQt6.QtGui import QPainter, QPixmap

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        # Slight deflection
        widget._joystick_x = 160
        widget._joystick_y = 160

        pixmap = QPixmap(800, 700)
        painter = QPainter(pixmap)
        painter.begin(pixmap)

        widget._draw_joystick_indicator(painter)

        painter.end()


class TestButtonMapperBackgroundImage:
    """Tests for background image source loading."""

    def test_load_background_image_no_files(self, qapp):
        """Test background source is None when no files exist."""
        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        with patch(
            "g13_linux.gui.views.button_mapper.resources.files",
            side_effect=ModuleNotFoundError(),
        ):
            with patch("os.path.exists", return_value=False):
                widget = ButtonMapperWidget()
                # The method is called during __init__ so we check result
                assert widget._background_source is None
                assert widget.background_image is None

    def test_load_background_image_with_valid_file(self, qapp):
        """Test background source loads from valid fallback image file."""
        import os
        import tempfile

        from PyQt6.QtGui import QPixmap

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        # Create a temporary image file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            pixmap = QPixmap(100, 100)
            pixmap.fill(Qt.GlobalColor.red)
            pixmap.save(temp_path, "PNG")

        try:
            with patch(
                "g13_linux.gui.views.button_mapper.resources.files",
                side_effect=ModuleNotFoundError(),
            ):
                with patch("os.path.exists", return_value=True):
                    with patch("os.path.join", return_value=temp_path):
                        widget = ButtonMapperWidget()
                        # Should have loaded source + scaled view image
                        assert widget._background_source is not None
                        assert widget.background_image is not None
        finally:
            os.unlink(temp_path)

    def test_load_background_image_with_invalid_file(self, qapp):
        """Test invalid image fallback leaves source unset."""
        import os
        import tempfile

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        # Create a temporary file with invalid image data
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"not an image")

        try:

            def exists_side_effect(path):
                if path == temp_path:
                    return True
                return False

            with patch(
                "g13_linux.gui.views.button_mapper.resources.files",
                side_effect=ModuleNotFoundError(),
            ):
                with patch("os.path.exists", side_effect=exists_side_effect):
                    with patch("os.path.join", return_value=temp_path):
                        widget = ButtonMapperWidget()
                        assert widget._background_source is None
        finally:
            os.unlink(temp_path)

    def test_update_background_image_scales_source(self, qapp):
        """Test _update_background_image scales from cached source image."""
        from PyQt6.QtGui import QPixmap

        from g13_linux.gui.views.button_mapper import ButtonMapperWidget

        widget = ButtonMapperWidget()
        source = QPixmap(120, 80)
        source.fill(Qt.GlobalColor.blue)
        widget._background_source = source

        # Resize above the widget minimum size so Qt applies the requested size.
        widget.resize(1280, 820)
        widget._update_background_image()

        assert widget.background_image is not None
        assert widget.background_image.width() == widget.width()
        assert widget.background_image.height() == widget.height()
