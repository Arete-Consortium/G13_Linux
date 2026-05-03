# G13 Linux

[![PyPI](https://img.shields.io/pypi/v/g13-linux)](https://pypi.org/project/g13-linux/)
[![Downloads](https://img.shields.io/pypi/dm/g13-linux)](https://pypi.org/project/g13-linux/)
[![Python](https://img.shields.io/pypi/pyversions/g13-linux)](https://pypi.org/project/g13-linux/)
[![CI](https://github.com/AreteDriver/G13_Linux/actions/workflows/ci.yml/badge.svg)](https://github.com/AreteDriver/G13_Linux/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AreteDriver/G13_Linux/actions/workflows/codeql.yml/badge.svg)](https://github.com/AreteDriver/G13_Linux/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Python userspace driver for the Logitech G13 Gaming Keyboard on Linux.

## Features

- **22 Programmable G-Keys** with macro support
- **RGB Backlight Control** with full color range
- **160x43 LCD Display** with custom text and graphics
- **Thumbstick Support** with configurable zones
- **Profile Management** for different applications
- **Per-Application Profiles** - automatically switch profiles based on active window
- **PyQt6 GUI** for visual configuration

## Installation

```bash
# From PyPI
pip install g13-linux

# Or with pipx (recommended for CLI tools)
pipx install g13-linux
```

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt install libhidapi-hidraw0

# Fedora
sudo dnf install hidapi
```

### udev Rules (Required)

```bash
# Allow non-root access to G13
sudo cp udev/99-logitech-g13.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Usage

### CLI

```bash
g13-linux --help              # Show help
g13-linux --version           # Show version
g13-linux                     # Run the input daemon
g13-linux run                 # Run the input daemon (explicit)
g13-linux run --libusb        # Prefer libusb backend first for input capture

# LCD control
g13-linux lcd "Hello World"   # Display text on LCD
g13-linux lcd --clear         # Clear the LCD

# Backlight control
g13-linux color red           # Set backlight to red
g13-linux color "#FF6600"     # Set backlight to hex color
g13-linux color 255,128,0     # Set backlight to RGB

# Profile management
g13-linux profile list        # List available profiles
g13-linux profile show eve    # Show profile details
g13-linux profile load eve    # Load and apply a profile
g13-linux profile create new  # Create a new profile
g13-linux profile delete old  # Delete a profile
g13-linux profile migrate eve # Migrate one legacy profile to canonical joystick schema
g13-linux profile migrate --all --dry-run  # Preview migrations for all profiles

# Device diagnostics
g13-linux doctor              # Probe hidraw/libusb and print setup issues
g13-linux doctor --libusb-first  # Probe libusb first
# Includes hidraw access flags (rw/r-/--), plus detection source (uevent/usb_ids)
```

### GUI

```bash
g13-linux-gui         # Launch the configuration GUI
```

Binding workflow in the GUI:
- Start with **Quick Setup Wizard** to map core keys (G1-G8) in a guided sequence.
- Pick a starter template in the wizard (Manual/MMO/FPS/Productivity), then optionally fine-tune each key.
- Finish wizard by optionally saving the result as a new profile in one step.
- Left-click a G13 button to open key binding.
- Use **Start Keyboard Capture** in the dialog and press the desired key combo.
- Use **Common Shortcut Presets** (Copy/Paste/Cut/Save/Undo/Redo) for fast setup.
- Double-click a key (or press Enter) to accept it immediately.
- If a binding is already in use, choose **Move**, **Keep Duplicate**, or **Cancel**.
- Hover any on-device button to see a full binding detail strip without opening dialogs.
- Right-click a mapped button to quickly clear its binding.
- Use **Run Diagnostics** in the top status banner when the device is not detected.
- On first failed connection, the GUI opens a **Setup Assistant** with copy-ready udev/libusb commands.
- Keep the right panel in **Core** mode for daily setup; switch to **Core + Advanced** for macros, hardware tuning, and live monitor tools.
- Watch the session summary bar for active profile, bound-button count, and stick mode.
- Save the selected profile to persist changes.

### Python API

```python
from g13_linux import open_g13, G13Mapper

# Open device and start mapping
device = open_g13()
mapper = G13Mapper()

# Read events
while True:
    data = read_event(device)
    if data:
        mapper.handle_raw_report(data)
```

## Profile Format (Quick Reference)

Profile JSON files are loaded from:
- Source checkout: `configs/profiles/*.json`
- Installed package: `~/.config/g13-linux/profiles/*.json`

Button mappings support both simple and combo formats:

```json
{
  "mappings": {
    "G1": "KEY_1",
    "G2": {
      "keys": ["KEY_LEFTCTRL", "KEY_B"],
      "label": "Save location"
    },
    "STICK": {
      "keys": ["KEY_LEFTCTRL"],
      "label": "Joystick click"
    }
  }
}
```

Joystick settings should use the canonical schema:

```json
{
  "joystick": {
    "mode": "digital",
    "deadzone": 20,
    "sensitivity": 1.0,
    "key_up": "KEY_UP",
    "key_down": "KEY_DOWN",
    "key_left": "KEY_LEFT",
    "key_right": "KEY_RIGHT",
    "allow_diagonals": true
  }
}
```

`mode` values:
- `analog`: expose a virtual joystick device
- `digital`: map directions to keyboard keys
- `disabled`: ignore stick movement

Legacy joystick profiles that use `mode: "directional"` with nested `up/down/left/right` are still accepted for backward compatibility, but saving from the GUI rewrites them to the canonical schema above.

For step-by-step legacy conversion examples, see `docs/profile-migration.md`.
For release operations and PyPI trusted publisher setup, see `docs/release-checklist.md`.
For Linux CI parity testing, see `docs/testing-ubuntu.md`.

## Per-Application Profiles

Automatically switch G13 profiles when you switch applications. For example, load your EVE Online profile when EVE is focused, and switch to your browser profile when Firefox is active.

### Setup (GUI)

1. Launch the GUI: `g13-linux-gui`
2. Go to the **App Profiles** tab
3. Click **Add Rule** to create a new rule:
   - **Rule Name**: A friendly name (e.g., "EVE Online")
   - **Pattern**: Regex pattern to match (e.g., `EVE -` or `firefox`)
   - **Match Type**: Match against window name, WM_CLASS, or both
   - **Profile**: Select which profile to activate
4. Enable auto-switching with the toggle at the top
5. Click **Test** to see the current window's info

### Configuration File

Rules are stored in `~/.config/g13-linux/app_profiles.json`:

```json
{
  "rules": [
    {
      "name": "EVE Online",
      "pattern": "EVE -",
      "match_type": "window_name",
      "profile_name": "eve_online",
      "enabled": true
    },
    {
      "name": "Firefox",
      "pattern": "firefox",
      "match_type": "wm_class",
      "profile_name": "browser",
      "enabled": true
    }
  ],
  "default_profile": "default",
  "enabled": true
}
```

### Requirements

- **X11 only**: Requires `xdotool` for window detection (not available on Wayland)
- Install: `sudo apt install xdotool`

### How It Works

1. A background thread polls the active window every 500ms using `xdotool`
2. When the active window changes, rules are matched against window name and WM_CLASS
3. First matching rule triggers a profile switch
4. If no rules match, the default profile is loaded (if configured)

## Hardware

| Component | Status |
|-----------|--------|
| G1-G22 Keys | ✅ Working |
| M1-M3 Mode Keys | ✅ Working |
| MR Key | ✅ Working |
| Thumbstick | ✅ Working |
| LCD Display | ✅ Working |
| RGB Backlight | ✅ Working |

**Note**: Button input requires either:
- udev rules for hidraw access, or
- `sudo` with libusb mode (`g13-linux-gui --libusb`)

If detection fails, run `g13-linux doctor` for backend-level diagnostics and setup hints.

Linux kernel 6.19+ will include native `hid-lg-g15` support for G13.

## Development

```bash
# Clone and setup
git clone https://github.com/AreteDriver/G13_Linux.git
cd G13_Linux
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Ubuntu CI-like test path (installs Linux deps + runs under xvfb)
./scripts/test_ubuntu.sh --system-deps

# Lint
ruff check src/ tests/
```

Linux test setup details: `docs/testing-ubuntu.md`

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [PyPI Package](https://pypi.org/project/g13-linux/)
- [GitHub Issues](https://github.com/AreteDriver/G13_Linux/issues)
- [Logitech G13 Specs](https://support.logi.com/hc/en-us/articles/360024844133)
