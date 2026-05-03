#!/usr/bin/env bash
# Run G13 Linux tests on Ubuntu in a CI-like environment.
#
# Examples:
#   ./scripts/test_ubuntu.sh --system-deps
#   ./scripts/test_ubuntu.sh --system-deps --no-cov
#   ./scripts/test_ubuntu.sh -- tests/test_cli.py -k migrate

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_SYSTEM_DEPS=false
NO_COV=false
EXTRA_PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --system-deps)
            INSTALL_SYSTEM_DEPS=true
            shift
            ;;
        --no-cov)
            NO_COV=true
            shift
            ;;
        --python)
            PYTHON_BIN="$2"
            shift 2
            ;;
        --)
            shift
            EXTRA_PYTEST_ARGS=("$@")
            break
            ;;
        *)
            EXTRA_PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ "${INSTALL_SYSTEM_DEPS}" == "true" ]]; then
    echo "[ubuntu-test] Installing Ubuntu system dependencies..."
    sudo apt-get update
    sudo apt-get install -y \
        build-essential \
        python3-venv \
        libhidapi-dev \
        libhidapi-hidraw0 \
        libusb-1.0-0-dev \
        libegl1 \
        libopengl0 \
        libxcb-cursor0 \
        libxkbcommon0 \
        xvfb
fi

if [[ ! -d "${VENV_DIR}" ]]; then
    echo "[ubuntu-test] Creating virtual environment at ${VENV_DIR}..."
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

echo "[ubuntu-test] Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

export QT_QPA_PLATFORM=offscreen

if [[ "${NO_COV}" == "true" ]]; then
    echo "[ubuntu-test] Running tests without coverage gate..."
    xvfb-run -a pytest -o addopts='' tests/ -v --tb=short "${EXTRA_PYTEST_ARGS[@]}"
else
    echo "[ubuntu-test] Running tests with project defaults..."
    xvfb-run -a pytest -v --tb=short --cov-report=xml "${EXTRA_PYTEST_ARGS[@]}"
fi
