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
```

### GUI

```bash
g13-linux-gui         # Launch the configuration GUI
```

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

# Lint
ruff check src/ tests/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [PyPI Package](https://pypi.org/project/g13-linux/)
- [GitHub Issues](https://github.com/AreteDriver/G13_Linux/issues)
- [Logitech G13 Specs](https://support.logi.com/hc/en-us/articles/360024844133)
- [Discord](https://discord.gg/fdzQkrt8) — Join the community
