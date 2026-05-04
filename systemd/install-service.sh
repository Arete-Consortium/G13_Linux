#!/bin/bash
# Install the G13 Linux input daemon as a systemd user service.
#
# What this does:
#   1. Verifies g13-linux is on PATH
#   2. Copies g13-linux.service to ~/.config/systemd/user/
#   3. Reloads systemd user units
#   4. Optionally configures uinput to auto-load at boot (needs sudo)
#   5. Prints the enable/start commands

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="${SCRIPT_DIR}/g13-linux.service"
UINPUT_CONF="${SCRIPT_DIR}/uinput.conf"
USER_UNIT_DIR="${HOME}/.config/systemd/user"

echo "G13 Linux Service Installer"
echo "==========================="
echo

# 1. Verify g13-linux is installed
if ! command -v g13-linux &>/dev/null; then
    echo "[ERROR] g13-linux not found on PATH."
    echo "Install first with one of:"
    echo "  pipx install g13-linux       # recommended"
    echo "  pip install --user g13-linux"
    exit 1
fi
G13_BIN="$(command -v g13-linux)"
G13_VERSION="$(g13-linux --version 2>&1 || echo unknown)"
echo "[OK] Found ${G13_VERSION} at ${G13_BIN}"

# 2. Verify the user is in the 'input' group (required for /dev/uinput access)
if ! id -nG "$(whoami)" | grep -qw input; then
    echo "[WARN] Your user is NOT in the 'input' group."
    echo "       The daemon needs /dev/uinput access to inject keystrokes."
    echo "       Add yourself with:"
    echo "         sudo usermod -aG input $(whoami)"
    echo "       Then log out and back in for the group change to take effect."
    echo
fi

# 3. Install the user unit
mkdir -p "${USER_UNIT_DIR}"
cp "${SERVICE_FILE}" "${USER_UNIT_DIR}/g13-linux.service"
echo "[OK] Installed unit: ${USER_UNIT_DIR}/g13-linux.service"

# 4. Reload systemd user manager
systemctl --user daemon-reload
echo "[OK] Reloaded systemd --user"

# 5. Optionally install uinput modules-load.d config
echo
read -r -p "Install /etc/modules-load.d/uinput.conf so uinput loads at boot? (sudo required) [Y/n] " resp
case "${resp:-y}" in
    [Yy]|[Yy][Ee][Ss]|"")
        sudo cp "${UINPUT_CONF}" /etc/modules-load.d/uinput.conf
        sudo modprobe uinput
        echo "[OK] uinput will load at boot and is loaded now."
        ;;
    *)
        echo "[SKIP] Skipped uinput auto-load. Make sure 'uinput' is loaded before"
        echo "       starting the service (sudo modprobe uinput)."
        ;;
esac

# 6. Print enable/start instructions
echo
echo "Done. Next steps:"
echo
echo "  Enable on login:    systemctl --user enable g13-linux.service"
echo "  Start now:          systemctl --user start g13-linux.service"
echo "  Status:             systemctl --user status g13-linux.service"
echo "  Live logs:          journalctl --user -u g13-linux.service -f"
echo
echo "To run as a one-shot foreground process instead (for debugging):"
echo "  g13-linux run --debug"
