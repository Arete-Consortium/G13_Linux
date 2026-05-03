"""Profile migration helpers for legacy joystick schemas."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

CANONICAL_JOYSTICK_DEFAULTS = {
    "mode": "analog",
    "deadzone": 20,
    "sensitivity": 1.0,
    "key_up": "KEY_UP",
    "key_down": "KEY_DOWN",
    "key_left": "KEY_LEFT",
    "key_right": "KEY_RIGHT",
    "allow_diagonals": True,
}

_VALID_MODES = {"analog", "digital", "disabled"}
_MODE_ALIASES = {"directional": "digital"}
_LEGACY_DIRECTION_KEYS = ("up", "down", "left", "right")


@dataclass
class ProfileMigrationResult:
    """Result for a single migrated profile file."""

    path: Path
    changed: bool = False
    written: bool = False
    details: list[str] = field(default_factory=list)
    error: str | None = None


def _parse_key_mapping(value, default: str) -> str:
    """Extract a key string from modern or legacy mapping values."""
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        keys = value.get("keys", [])
        if isinstance(keys, list):
            for key_name in keys:
                if isinstance(key_name, str):
                    return key_name

        key_name = value.get("key")
        if isinstance(key_name, str):
            return key_name

        return default

    if isinstance(value, (list, tuple)):
        for key_name in value:
            if isinstance(key_name, str):
                return key_name

    return default


def _normalize_deadzone(value, default: int = 20) -> int:
    """Normalize deadzone into int 0..127."""
    try:
        deadzone = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(127, deadzone))


def _normalize_sensitivity(value, default: float = 1.0) -> float:
    """Normalize sensitivity into positive float."""
    try:
        sensitivity = float(value)
    except (TypeError, ValueError):
        return default
    return sensitivity if sensitivity > 0 else default


def normalize_joystick_config(data: dict | None) -> dict:
    """Normalize joystick config into canonical schema."""
    if not isinstance(data, dict):
        return CANONICAL_JOYSTICK_DEFAULTS.copy()

    mode_str = data.get("mode")
    if mode_str is None:
        if any(direction in data for direction in _LEGACY_DIRECTION_KEYS):
            mode_str = "digital"
        else:
            mode_str = "analog"

    normalized_mode = _MODE_ALIASES.get(str(mode_str).lower(), str(mode_str).lower())
    if normalized_mode not in _VALID_MODES:
        normalized_mode = "analog"

    key_up = _parse_key_mapping(data.get("key_up", data.get("up")), "KEY_UP")
    key_down = _parse_key_mapping(data.get("key_down", data.get("down")), "KEY_DOWN")
    key_left = _parse_key_mapping(data.get("key_left", data.get("left")), "KEY_LEFT")
    key_right = _parse_key_mapping(data.get("key_right", data.get("right")), "KEY_RIGHT")

    return {
        "mode": normalized_mode,
        "deadzone": _normalize_deadzone(data.get("deadzone", 20)),
        "sensitivity": _normalize_sensitivity(data.get("sensitivity", 1.0)),
        "key_up": key_up,
        "key_down": key_down,
        "key_left": key_left,
        "key_right": key_right,
        "allow_diagonals": bool(data.get("allow_diagonals", True)),
    }


def _extract_stick_mapping(click_value) -> dict | None:
    """Extract STICK mapping from legacy joystick.click value."""
    if isinstance(click_value, dict):
        keys = click_value.get("keys", [])
        label = click_value.get("label")
        if isinstance(keys, list):
            valid_keys = [key for key in keys if isinstance(key, str)]
            if valid_keys:
                mapping: dict = {"keys": valid_keys}
                if isinstance(label, str) and label.strip():
                    mapping["label"] = label
                return mapping

        key_name = click_value.get("key")
        if isinstance(key_name, str):
            mapping = {"keys": [key_name]}
            if isinstance(label, str) and label.strip():
                mapping["label"] = label
            return mapping
        return None

    if isinstance(click_value, str):
        return {"keys": [click_value]}

    if isinstance(click_value, (list, tuple)):
        valid_keys = [key for key in click_value if isinstance(key, str)]
        if valid_keys:
            return {"keys": valid_keys}

    return None


def migrate_profile_dict(profile_data: dict) -> tuple[dict, bool, list[str]]:
    """Migrate legacy joystick fields in one profile dictionary."""
    if not isinstance(profile_data, dict):
        return profile_data, False, ["Profile data is not an object"]

    migrated = copy.deepcopy(profile_data)
    joystick = migrated.get("joystick")
    if not isinstance(joystick, dict):
        return migrated, False, []

    has_legacy_mode = str(joystick.get("mode", "")).lower() == "directional"
    has_legacy_directions = any(key in joystick for key in _LEGACY_DIRECTION_KEYS)
    has_legacy_click = "click" in joystick

    if not (has_legacy_mode or has_legacy_directions or has_legacy_click):
        return migrated, False, []

    details: list[str] = []
    migrated["joystick"] = normalize_joystick_config(joystick)
    details.append("normalized joystick fields to canonical schema")

    if has_legacy_click:
        mappings = migrated.get("mappings")
        if not isinstance(mappings, dict):
            mappings = {}
            migrated["mappings"] = mappings

        if "STICK" not in mappings:
            stick_mapping = _extract_stick_mapping(joystick.get("click"))
            if stick_mapping:
                mappings["STICK"] = stick_mapping
                details.append("moved legacy joystick.click mapping to mappings.STICK")
            else:
                details.append("legacy joystick.click present but could not parse keys")
        else:
            details.append("kept existing mappings.STICK (did not overwrite)")

    return migrated, True, details


def migrate_profile_file(path: Path, dry_run: bool = False) -> ProfileMigrationResult:
    """Migrate a profile JSON file in-place."""
    result = ProfileMigrationResult(path=path)

    try:
        with open(path) as f:
            raw_data = json.load(f)
    except Exception as exc:
        result.error = str(exc)
        return result

    migrated, changed, details = migrate_profile_dict(raw_data)
    result.changed = changed
    result.details = details

    if changed and not dry_run:
        with open(path, "w") as f:
            json.dump(migrated, f, indent=2)
            f.write("\n")
        result.written = True

    return result
