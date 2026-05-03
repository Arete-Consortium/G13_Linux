"""Tests for JoystickHandler"""

from unittest.mock import MagicMock, patch

from g13_linux.gui.models.joystick_handler import (
    JoystickConfig,
    JoystickHandler,
    JoystickMode,
)


class TestJoystickMode:
    """Tests for JoystickMode enum"""

    def test_analog_mode(self):
        assert JoystickMode.ANALOG.value == "analog"

    def test_digital_mode(self):
        assert JoystickMode.DIGITAL.value == "digital"

    def test_disabled_mode(self):
        assert JoystickMode.DISABLED.value == "disabled"


class TestJoystickConfig:
    """Tests for JoystickConfig"""

    def test_default_config(self):
        config = JoystickConfig()
        assert config.mode == JoystickMode.ANALOG
        assert config.deadzone == 20
        assert config.sensitivity == 1.0
        assert config.key_up == "KEY_UP"
        assert config.key_down == "KEY_DOWN"
        assert config.key_left == "KEY_LEFT"
        assert config.key_right == "KEY_RIGHT"
        assert config.allow_diagonals is True

    def test_from_dict_defaults(self):
        config = JoystickConfig.from_dict({})
        assert config.mode == JoystickMode.ANALOG
        assert config.deadzone == 20

    def test_from_dict_custom(self):
        data = {
            "mode": "digital",
            "deadzone": 30,
            "sensitivity": 1.5,
            "key_up": "KEY_W",
            "key_down": "KEY_S",
            "key_left": "KEY_A",
            "key_right": "KEY_D",
            "allow_diagonals": False,
        }
        config = JoystickConfig.from_dict(data)
        assert config.mode == JoystickMode.DIGITAL
        assert config.deadzone == 30
        assert config.sensitivity == 1.5
        assert config.key_up == "KEY_W"
        assert config.key_down == "KEY_S"
        assert config.key_left == "KEY_A"
        assert config.key_right == "KEY_D"
        assert config.allow_diagonals is False

    def test_from_dict_invalid_mode(self):
        config = JoystickConfig.from_dict({"mode": "invalid"})
        assert config.mode == JoystickMode.ANALOG  # Defaults to analog

    def test_from_dict_legacy_directional_mode_alias(self):
        config = JoystickConfig.from_dict({"mode": "directional"})
        assert config.mode == JoystickMode.DIGITAL

    def test_from_dict_legacy_directional_mapping_objects(self):
        data = {
            "mode": "directional",
            "up": {"keys": ["KEY_W"], "label": "Up"},
            "down": {"keys": ["KEY_S"], "label": "Down"},
            "left": {"keys": ["KEY_LEFTALT", "KEY_LEFT"], "label": "Prev target"},
            "right": {"keys": ["KEY_LEFTALT", "KEY_RIGHT"], "label": "Next target"},
        }
        config = JoystickConfig.from_dict(data)
        assert config.mode == JoystickMode.DIGITAL
        assert config.key_up == "KEY_W"
        assert config.key_down == "KEY_S"
        # Legacy combo mappings are reduced to a usable primary key
        assert config.key_left == "KEY_LEFTALT"
        assert config.key_right == "KEY_LEFTALT"

    def test_to_dict(self):
        config = JoystickConfig(
            mode=JoystickMode.DIGITAL,
            deadzone=30,
            sensitivity=1.5,
            key_up="KEY_W",
            key_down="KEY_S",
            key_left="KEY_A",
            key_right="KEY_D",
            allow_diagonals=False,
        )
        data = config.to_dict()
        assert data["mode"] == "digital"
        assert data["deadzone"] == 30
        assert data["sensitivity"] == 1.5
        assert data["key_up"] == "KEY_W"
        assert data["allow_diagonals"] is False


class TestJoystickHandlerInit:
    """Tests for JoystickHandler initialization"""

    def test_init_default(self):
        handler = JoystickHandler()
        assert handler.config.mode == JoystickMode.ANALOG
        assert handler._analog_device is None
        assert handler._key_device is None
        assert handler._keys_pressed == set()
        assert handler._last_x == 128
        assert handler._last_y == 128

    def test_init_with_config(self):
        config = JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=30)
        handler = JoystickHandler(config)
        assert handler.config.mode == JoystickMode.DIGITAL
        assert handler.config.deadzone == 30


class TestJoystickHandlerStart:
    """Tests for JoystickHandler.start()"""

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_start_analog_mode(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG))
        result = handler.start()
        assert result is True
        assert mock_uinput.called
        # Check that capabilities include ABS_X, ABS_Y
        call_args = mock_uinput.call_args
        assert "name" in call_args.kwargs
        assert call_args.kwargs["name"] == "G13 Joystick"

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_start_digital_mode(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL))
        result = handler.start()
        assert result is True
        assert mock_uinput.called
        call_args = mock_uinput.call_args
        assert call_args.kwargs["name"] == "G13 Joystick Keys"

    def test_start_disabled_mode(self):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DISABLED))
        result = handler.start()
        assert result is True  # No error, just does nothing

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_start_exception(self, mock_uinput):
        mock_uinput.side_effect = Exception("Test error")
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG))
        result = handler.start()
        assert result is False


class TestJoystickHandlerStop:
    """Tests for JoystickHandler.stop()"""

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_stop_closes_analog_device(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG))
        handler.start()
        handler.stop()
        mock_uinput.return_value.close.assert_called()

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_stop_releases_keys_digital(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL))
        handler.start()
        handler._keys_pressed = {"KEY_UP"}
        handler.stop()
        assert handler._keys_pressed == set()

    def test_stop_no_device(self):
        handler = JoystickHandler()
        handler.stop()  # Should not raise


class TestJoystickHandlerSetConfig:
    """Tests for JoystickHandler.set_config()"""

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_set_config_mode_change(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG))
        handler.start()

        new_config = JoystickConfig(mode=JoystickMode.DIGITAL)
        handler.set_config(new_config)

        assert handler.config.mode == JoystickMode.DIGITAL
        # Should have stopped and restarted
        assert mock_uinput.return_value.close.called

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_set_config_same_mode(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG))
        handler.start()
        initial_close_count = mock_uinput.return_value.close.call_count

        new_config = JoystickConfig(mode=JoystickMode.ANALOG, deadzone=50)
        handler.set_config(new_config)

        assert handler.config.deadzone == 50
        # Should not have restarted (no close called)
        assert mock_uinput.return_value.close.call_count == initial_close_count


class TestJoystickHandlerUpdate:
    """Tests for JoystickHandler.update()"""

    def test_update_disabled_mode(self):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DISABLED))
        handler.update(200, 200)  # Should not raise

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_analog_mode(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG))
        handler.start()

        handler.update(200, 100)

        # Should have written to device
        mock_uinput.return_value.write.assert_called()
        mock_uinput.return_value.syn.assert_called()

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_digital_mode_up(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20))
        handler.start()

        # Move joystick up (Y < center - deadzone)
        handler.update(128, 50)  # Y=50 is up (negative centered_y)

        assert "KEY_UP" in handler._keys_pressed

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_digital_mode_down(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20))
        handler.start()

        handler.update(128, 200)  # Y=200 is down

        assert "KEY_DOWN" in handler._keys_pressed

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_digital_mode_left(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20))
        handler.start()

        handler.update(50, 128)  # X=50 is left

        assert "KEY_LEFT" in handler._keys_pressed

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_digital_mode_right(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20))
        handler.start()

        handler.update(200, 128)  # X=200 is right

        assert "KEY_RIGHT" in handler._keys_pressed

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_digital_mode_diagonal(self, mock_uinput):
        handler = JoystickHandler(
            JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20, allow_diagonals=True)
        )
        handler.start()

        handler.update(200, 50)  # Right-Up diagonal

        assert "KEY_RIGHT" in handler._keys_pressed
        assert "KEY_UP" in handler._keys_pressed

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_digital_mode_no_diagonal_vertical_dominates(self, mock_uinput):
        handler = JoystickHandler(
            JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20, allow_diagonals=False)
        )
        handler.start()

        # Vertical dominates: y=50 → |128-50|=78, x=200 → |200-128|=72
        handler.update(200, 50)

        # Should only have vertical key pressed (up, since y < 128)
        assert len(handler._keys_pressed) == 1
        assert "KEY_UP" in handler._keys_pressed

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_digital_mode_no_diagonal_horizontal_dominates(self, mock_uinput):
        handler = JoystickHandler(
            JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20, allow_diagonals=False)
        )
        handler.start()

        # Horizontal dominates: x=220 → |220-128|=92, y=100 → |128-100|=28
        handler.update(220, 100)

        # Should only have horizontal key pressed (right, since x > 128)
        assert len(handler._keys_pressed) == 1
        assert "KEY_RIGHT" in handler._keys_pressed

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_digital_mode_center(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20))
        handler.start()

        # First press a key
        handler.update(200, 128)
        assert "KEY_RIGHT" in handler._keys_pressed

        # Then center
        handler.update(128, 128)
        assert handler._keys_pressed == set()

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_update_sensitivity(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG, sensitivity=2.0))
        handler.start()

        handler.update(150, 128)  # Small movement

        # With 2x sensitivity, should be amplified
        mock_uinput.return_value.write.assert_called()


class TestJoystickHandlerStickClick:
    """Tests for JoystickHandler.handle_stick_click()"""

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_stick_click_pressed(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG))
        handler.start()

        handler.handle_stick_click(True)

        mock_uinput.return_value.write.assert_called()

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_stick_click_released(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG))
        handler.start()

        handler.handle_stick_click(False)

        mock_uinput.return_value.write.assert_called()

    def test_stick_click_no_device(self):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DISABLED))
        handler.handle_stick_click(True)  # Should not raise


class TestJoystickHandlerEmitKeyNoDevice:
    """Tests for _emit_key when _key_device is None"""

    def test_emit_key_no_device_digital_mode(self):
        """Test that digital mode update doesn't crash without device"""
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20))
        # Don't call start() - _key_device stays None

        # This should call _emit_key internally but return early because no device
        handler.update(200, 128)  # Should not raise

        # Keys should be tracked even without device for emission
        assert "KEY_RIGHT" in handler._keys_pressed


class TestJoystickHandlerDirectionCallback:
    """Tests for direction change callback"""

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_direction_callback(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20))
        handler.start()

        callback = MagicMock()
        handler.on_direction_change = callback

        handler.update(200, 128)  # Move right

        callback.assert_called_with("right")

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_direction_callback_diagonal(self, mock_uinput):
        handler = JoystickHandler(
            JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20, allow_diagonals=True)
        )
        handler.start()

        callback = MagicMock()
        handler.on_direction_change = callback

        handler.update(200, 200)  # Move right+down

        callback.assert_called_with("down+right")

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_direction_callback_center(self, mock_uinput):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.DIGITAL, deadzone=20))
        handler.start()

        callback = MagicMock()
        handler.on_direction_change = callback

        handler.update(128, 128)  # Center

        callback.assert_called_with("center")


class TestJoystickHandlerGetDirection:
    """Tests for JoystickHandler.get_current_direction()"""

    def test_get_direction_center(self):
        handler = JoystickHandler(JoystickConfig(deadzone=20))
        handler._last_x = 128
        handler._last_y = 128

        assert handler.get_current_direction() == "center"

    def test_get_direction_up(self):
        handler = JoystickHandler(JoystickConfig(deadzone=20))
        handler._last_x = 128
        handler._last_y = 50

        assert handler.get_current_direction() == "up"

    def test_get_direction_down(self):
        handler = JoystickHandler(JoystickConfig(deadzone=20))
        handler._last_x = 128
        handler._last_y = 200

        assert handler.get_current_direction() == "down"

    def test_get_direction_left(self):
        handler = JoystickHandler(JoystickConfig(deadzone=20))
        handler._last_x = 50
        handler._last_y = 128

        assert handler.get_current_direction() == "left"

    def test_get_direction_right(self):
        handler = JoystickHandler(JoystickConfig(deadzone=20))
        handler._last_x = 200
        handler._last_y = 128

        assert handler.get_current_direction() == "right"

    def test_get_direction_diagonal(self):
        handler = JoystickHandler(JoystickConfig(deadzone=20))
        handler._last_x = 200
        handler._last_y = 50

        direction = handler.get_current_direction()
        assert "up" in direction
        assert "right" in direction


class TestJoystickHandlerAnalogNoDevice:
    """Tests for analog mode without device"""

    def test_update_analog_no_device(self):
        handler = JoystickHandler(JoystickConfig(mode=JoystickMode.ANALOG))
        # Don't call start() - no device
        handler.update(200, 200)  # Should not raise


class TestJoystickHandlerDigitalInvalidKey:
    """Tests for digital mode with invalid key names"""

    @patch("g13_linux.gui.models.joystick_handler.UInput")
    def test_digital_invalid_key(self, mock_uinput):
        config = JoystickConfig(
            mode=JoystickMode.DIGITAL,
            key_up="INVALID_KEY",
            key_down="KEY_DOWN",
            key_left="KEY_LEFT",
            key_right="KEY_RIGHT",
        )
        handler = JoystickHandler(config)
        handler.start()

        # Should still work, just won't emit the invalid key
        handler.update(128, 50)  # Move up
