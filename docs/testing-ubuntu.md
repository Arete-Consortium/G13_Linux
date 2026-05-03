# Ubuntu Test Path

This project is Linux-first and expects `evdev`/HID userspace dependencies that do not build on macOS.
Use this guide to run tests on Ubuntu with the same dependency shape as CI.

On non-Linux hosts, core profile/mapping logic can still be developed and tested, but actual key injection and virtual input device behavior require Linux.

## One-Command Path

From the project root:

```bash
./scripts/test_ubuntu.sh --system-deps
```

This will:
- install required Ubuntu packages
- create `.venv` if missing
- install `.[dev]`
- run tests under `xvfb` with Qt offscreen mode
- write `coverage.xml` when coverage is enabled (for CI/codecov upload)

## Useful Variants

Run without coverage gate (fast local iteration):

```bash
./scripts/test_ubuntu.sh --system-deps --no-cov
```

Run a focused subset:

```bash
./scripts/test_ubuntu.sh --system-deps -- --maxfail=1 tests/test_cli.py -k migrate
```

Use a custom Python interpreter:

```bash
PYTHON_BIN=python3.11 ./scripts/test_ubuntu.sh --system-deps
```

## Manual Equivalent

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential python3-venv \
  libhidapi-dev libhidapi-hidraw0 libusb-1.0-0-dev \
  libegl1 libopengl0 libxcb-cursor0 libxkbcommon0 xvfb

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Optional: confirm device detection diagnostics
# Look for "Hidraw access: rw" (or r-/--) and detection source details.
g13-linux doctor

QT_QPA_PLATFORM=offscreen xvfb-run -a pytest -v --tb=short --cov-report=xml
```
