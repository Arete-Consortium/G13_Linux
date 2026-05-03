# G13 Profile Migration Guide

This guide shows how to migrate legacy joystick profile data to the current canonical schema used by the GUI and backend.

## What Changed

Legacy profiles often used:
- `joystick.mode: "directional"`
- Nested joystick direction objects (`up`, `down`, `left`, `right`)
- Optional joystick `click` mapping under `joystick`

Canonical profiles use:
- `joystick.mode: "digital"` (or `analog` / `disabled`)
- Flat direction keys: `key_up`, `key_down`, `key_left`, `key_right`
- Stick click mapped as normal button mapping on `mappings.STICK`

## CLI Helper

Use the built-in migration command:

```bash
# Preview all migrations
g13-linux profile migrate --all --dry-run

# Migrate one profile file by name
g13-linux profile migrate eve_online

# Migrate all profile files in-place
g13-linux profile migrate --all
```

## Before (Legacy)

```json
{
  "mappings": {
    "G1": "KEY_1"
  },
  "joystick": {
    "mode": "directional",
    "up": { "keys": ["KEY_W"], "label": "Up" },
    "down": { "keys": ["KEY_S"], "label": "Down" },
    "left": { "keys": ["KEY_A"], "label": "Left" },
    "right": { "keys": ["KEY_D"], "label": "Right" },
    "click": { "keys": ["KEY_LEFTCTRL"], "label": "Stick click" }
  }
}
```

## After (Canonical)

```json
{
  "mappings": {
    "G1": "KEY_1",
    "STICK": { "keys": ["KEY_LEFTCTRL"], "label": "Stick click" }
  },
  "joystick": {
    "mode": "digital",
    "deadzone": 20,
    "sensitivity": 1.0,
    "key_up": "KEY_W",
    "key_down": "KEY_S",
    "key_left": "KEY_A",
    "key_right": "KEY_D",
    "allow_diagonals": true
  }
}
```

## Notes

- Existing legacy profiles still load correctly.
- When you save a profile from the GUI, joystick data is normalized to canonical fields.
- If you used legacy `joystick.click`, move that action to `mappings.STICK` to preserve behavior.
