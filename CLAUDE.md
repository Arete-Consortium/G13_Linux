# CLAUDE.md — G13_Linux

## Project Overview

Linux userspace driver for Logitech G13 gaming keypad. Profile management, LCD control, RGB backlight, programmable macros, PyQt6 GUI, and WebSocket API.

**Version**: 1.7.0
**Language**: Python 3.10+
**License**: MIT
**PyPI**: `g13-linux`

## Architecture

```
Hardware (G13) → USB HID → udev rules → g13-daemon → CLI / GUI / WebSocket API
                                          │
                            ┌─────────────┼─────────────┐
                            ▼             ▼             ▼
                        Key Mapper    LCD Engine    Profile Manager
                        (evdev)       (Pillow)      (YAML + Schema)
```

### USB Details
- Vendor ID: `046d` (Logitech)
- Product ID: `c21c` (G13)
- Access modes: hidraw (preferred, via udev) or libusb (fallback, requires sudo)

### Key Directories
```
src/g13_linux/
├── cli.py              # CLI entry point (g13-linux)
├── daemon.py           # Main orchestrator
├── device.py           # USB HID device handling
├── mapper.py           # Key mapping + macro support
├── server.py           # aiohttp WebSocket/HTTP API
├── settings.py         # Persistent user settings
├── hardware/           # LCD + backlight control
├── input/              # Input handling + navigation
├── lcd/                # Canvas rendering engine
├── menu/               # On-device LCD menu system
└── gui/                # PyQt6 desktop application (MVC)
    ├── controllers/    # App logic (app_controller.py)
    ├── models/         # Data models, event decoder, macro recorder
    ├── views/          # UI views (profile manager, button mapper)
    ├── dialogs/        # Dialog windows
    └── widgets/        # Custom widgets
tests/                  # 37 test files, mocked hardware (1,717 tests, 87% coverage)
configs/                # Profile YAML templates
udev/                   # Device access rules
systemd/                # Service unit files
```

## Tech Stack

| Category | Tool |
|----------|------|
| GUI | PyQt6 6.7+ |
| USB/HID | hidapi, pyusb |
| Input | evdev, pynput |
| Server | aiohttp (async WebSocket + REST) |
| Graphics | Pillow (LCD rendering) |
| Testing | pytest, pytest-qt, pytest-cov |
| Linting | ruff (check + format), mypy, bandit |
| CI/CD | GitHub Actions (lint → test → typecheck → security → build) |
| Packaging | PyPI (Trusted Publisher), AppImage |

## Common Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Test (mocked, no hardware needed)
QT_QPA_PLATFORM=offscreen pytest -v --cov=g13_linux

# Lint + format (always run BOTH)
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/

# Security scan
bandit -r src/ -c pyproject.toml

# CLI entry points
g13-linux run|lcd|color|profile|daemon
g13-linux-gui
```

## Coding Standards

- **Naming**: snake_case
- **Quotes**: double quotes
- **Type hints**: required on all new code
- **Docstrings**: Google style
- **Paths**: `pathlib.Path` (never `os.path`)
- **Line length**: 100 (ruff config)
- **Coverage**: 80% minimum (enforced via `[tool.coverage.report] fail_under`)
- **Python versions**: 3.10, 3.11, 3.12

## Security Conventions

- **No shell execution in macros** — macros use evdev UInput only
- **Validate all USB input** — bounds checking on HID reports
- **Drop privileges after device open** — root only for hidraw access
- **Path traversal guards** in web API endpoints
- **No hardcoded credentials** — env vars or config files

## Anti-Patterns (Do NOT Do)

- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use `print()` for logging — use the `logging` module
- Do NOT use mutable default arguments
- Do NOT skip tests for new code
- Do NOT run shell commands from macro input (security boundary)
- Do NOT commit secrets, API keys, or credentials

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | Device + daemon status |
| `/api/profiles` | GET | List profiles |
| `/api/profiles/{name}` | GET/PUT | Get/update profile |
| `/api/profiles/{name}/activate` | POST | Switch active profile |
| `/api/macros` | GET | List macros |
| `/api/macros/{macro_id}` | GET/PUT/DELETE | CRUD macro |

## Dependencies

### Core
hidapi, evdev, pyusb, PyQt6, pynput, Pillow, aiohttp

### Dev
pytest, pytest-asyncio, pytest-aiohttp, pytest-cov, pytest-qt, ruff, mypy, build, twine, bandit

## Hardware Testing Status

| Feature | Tested | Notes |
|---------|--------|-------|
| Device connection | Yes | Via hidraw or libusb |
| LCD output | Yes | 5x7 font, 160x43 display |
| Backlight RGB | Yes | Full color control (255³) |
| Key detection | Yes | G1-G22, M1-M3, MR keys |
| Thumbstick | Yes | Analog position + click |
| Thumb buttons | Yes | LEFT, DOWN buttons |
| Profile switching | Yes | M1/M2/M3 mode switching |
| Joystick modes | Yes | Analog, Digital, Disabled |
| Macro recording | Yes | Recording + playback via evdev UInput |
| LCD clock | Yes | 12/24h, seconds, date options |

**Note**: Button/thumbstick input requires `sudo` or libusb mode. Use `g13-linux-gui.sh` for automatic privilege escalation via pkexec.

## Git Conventions

- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
- Pre-commit hooks: ruff format + check, trailing whitespace, YAML/JSON validation
