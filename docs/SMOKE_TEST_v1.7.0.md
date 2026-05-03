# v1.7.0 Hardware Smoke Test

Hardware-in-the-loop validation for the v1.7.0 release. The mocked test suite passes (1,717 tests, 87% coverage) but the load-bearing change — daemon HID single-read-loop fan-out — only manifests against real hardware under sustained input.

**When to run:** Before declaring v1.7.0 stable. Allow ~30 minutes.

**Setup:**

```bash
# Plug in the G13. Verify it's recognized:
lsusb | grep 046d:c21c
# Expected: Bus XXX Device YYY: ID 046d:c21c Logitech, Inc. G13 Advanced Gameboard
```

If you see no device, run the diagnostics first (Test 5 below) — the Setup Assistant is partially designed for exactly that path.

---

## Test 1 — Daemon HID fan-out (load-bearing fix)

**What it validates:** The fix in `daemon.py` + `input/handler.py` that replaced the dual-thread read loop with single-source fan-out.

**The bug it fixes:** Before, `InputHandler._poll_loop` and the daemon main loop both read from the same hidraw fd. Reports got split between consumers under sustained input → dropped/garbled events.

```bash
# Run daemon in foreground with debug logging
g13-linux daemon --debug 2>&1 | tee /tmp/g13-smoke-1.log

# In another terminal, hammer keys for 30 seconds:
# - Hold G1 down
# - Mash G2-G22 in random order at maximum speed
# - Wiggle the thumbstick continuously
# - Click thumb buttons (LEFT, DOWN)

# Stop daemon (Ctrl+C). Check log:
grep -E "(dropped|split|read error|Read error)" /tmp/g13-smoke-1.log
```

**Pass:** No "dropped" or "split report" messages. Single transient "Read error" lines under heavy load are OK (they get retried).

**Fail:** Repeated dropped events, especially while keys are held. File an issue tagged `smoke-test-v1.7.0`.

---

## Test 2 — Quick Setup Wizard

**What it validates:** New starter-template flow in the GUI.

```bash
g13-linux-gui
```

In the GUI:
1. From a fresh state (delete `~/.config/g13-linux/profiles/*` if you want a clean slate; back it up first).
2. The Quick Setup Wizard should auto-launch on first run.
3. Try each template: **Manual**, **MMO**, **FPS**, **Productivity**.
4. For each: confirm preview shows the right key bindings, then save.
5. Verify saved profile appears in `~/.config/g13-linux/profiles/`.

**Pass:** All 4 templates render, save, and produce a valid profile JSON.

**Fail:** Wizard crashes, template renders no bindings, save throws. File issue with template name + console traceback.

---

## Test 3 — Setup Assistant dialog (first-run failure path)

**What it validates:** The new dialog at `gui/dialogs/setup_assistant_dialog.py` that surfaces when the GUI can't open the device.

```bash
# Force a connection failure to trigger the assistant.
# Easy way: unplug the G13, then launch the GUI.
g13-linux-gui
```

The Setup Assistant should appear with:
- Diagnostics report (hidraw scan, permission flags, detection_source)
- 4 "Copy" buttons: udev commands, libusb launch, doctor command, full report
- Clear summary text indicating no backend can open the device

Click each Copy button, paste somewhere to verify the right text was copied.

**Pass:** Dialog renders, diagnostics are populated, all 4 copy buttons work.

**Fail:** Dialog doesn't appear (silent failure), diagnostics empty, copy buttons no-op.

---

## Test 4 — Profile migration CLI

**What it validates:** New `g13-linux profile migrate` command for legacy joystick schemas.

Create a legacy-format profile:

```bash
mkdir -p /tmp/g13-smoke-profiles
cat > /tmp/g13-smoke-profiles/legacy.json <<'EOF'
{
  "name": "legacy-test",
  "joystick": {
    "mode": "directional",
    "up": "KEY_W",
    "down": "KEY_S",
    "left": "KEY_A",
    "right": "KEY_D",
    "click": {"keys": ["KEY_SPACE"], "label": "jump"}
  }
}
EOF

# Dry run first
g13-linux profile migrate --all --dry-run --profiles-dir /tmp/g13-smoke-profiles

# Real migration
g13-linux profile migrate legacy --profiles-dir /tmp/g13-smoke-profiles

# Inspect result
cat /tmp/g13-smoke-profiles/legacy.json
```

**Pass:**
- Dry run reports "would migrate 1 profile" without writing.
- Real run normalizes `mode: directional` → `mode: digital`, flat `key_up`/`key_down`/`key_left`/`key_right` fields, `click` moved to `mappings.STICK`.

**Fail:** CLI errors, schema not normalized, dry-run writes anyway.

---

## Test 5 — Device discovery diagnostics

**What it validates:** Rich diagnostic output from `scan_hidraw_devices()`.

```bash
# With G13 plugged in:
python3 -c "
from g13_linux.device import scan_hidraw_devices
import json
print(json.dumps(scan_hidraw_devices(), indent=2))
"
```

**Pass:** Output is a list of dicts. The G13 entry has:
- `matched: true`
- `vendor_id: 1133` (0x046d) and `product_id: 49692` (0xc21c)
- `detection_source: "uevent"` or `"usb_ids"`
- `readable: true` and `writable: true` (if udev rules are installed)

If `readable: false` or `writable: false` → udev rules issue, document the actual values.

---

## Test 6 — Backward compat (regression check)

**What it validates:** Existing profiles still load.

```bash
# Use any existing profile from before the upgrade
g13-linux profile list
g13-linux profile show <name>
g13-linux profile load <name>
```

**Pass:** All pre-existing profiles list, show, and load without errors.

**Fail:** Schema rejection, key error on missing field. Capture the profile JSON + traceback.

---

## Reporting

For any failure: open an issue at https://github.com/AreteDriver/G13_Linux/issues with:
- Test number + name
- Console output / traceback
- Profile JSON if relevant
- `lsusb` output and `g13-linux doctor` output

Tag with `smoke-test-v1.7.0`.

---

## Cleanup

```bash
rm -rf /tmp/g13-smoke-profiles /tmp/g13-smoke-1.log
```
