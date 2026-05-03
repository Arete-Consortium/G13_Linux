"""Tests for profile migration helpers."""

import json

from g13_linux.profile_migration import (
    migrate_profile_dict,
    migrate_profile_file,
    normalize_joystick_config,
)


def test_normalize_joystick_config_from_legacy_directional():
    legacy = {
        "mode": "directional",
        "up": {"keys": ["KEY_W"], "label": "Up"},
        "down": {"keys": ["KEY_S"], "label": "Down"},
        "left": {"keys": ["KEY_A"], "label": "Left"},
        "right": {"keys": ["KEY_D"], "label": "Right"},
        "allow_diagonals": False,
    }

    normalized = normalize_joystick_config(legacy)

    assert normalized["mode"] == "digital"
    assert normalized["key_up"] == "KEY_W"
    assert normalized["key_down"] == "KEY_S"
    assert normalized["key_left"] == "KEY_A"
    assert normalized["key_right"] == "KEY_D"
    assert normalized["allow_diagonals"] is False


def test_migrate_profile_dict_moves_click_to_stick_mapping():
    profile = {
        "name": "Legacy",
        "mappings": {"G1": "KEY_1"},
        "joystick": {
            "mode": "directional",
            "up": {"keys": ["KEY_UP"]},
            "down": {"keys": ["KEY_DOWN"]},
            "left": {"keys": ["KEY_LEFT"]},
            "right": {"keys": ["KEY_RIGHT"]},
            "click": {"keys": ["KEY_LEFTCTRL"], "label": "Ctrl modifier"},
        },
    }

    migrated, changed, details = migrate_profile_dict(profile)

    assert changed is True
    assert migrated["joystick"]["mode"] == "digital"
    assert migrated["mappings"]["STICK"]["keys"] == ["KEY_LEFTCTRL"]
    assert migrated["mappings"]["STICK"]["label"] == "Ctrl modifier"
    assert any("moved legacy joystick.click" in detail for detail in details)


def test_migrate_profile_dict_preserves_existing_stick_mapping():
    profile = {
        "name": "Legacy",
        "mappings": {"STICK": "KEY_SPACE"},
        "joystick": {
            "mode": "directional",
            "up": {"keys": ["KEY_UP"]},
            "click": {"keys": ["KEY_LEFTCTRL"]},
        },
    }

    migrated, changed, details = migrate_profile_dict(profile)

    assert changed is True
    assert migrated["mappings"]["STICK"] == "KEY_SPACE"
    assert any("did not overwrite" in detail for detail in details)


def test_migrate_profile_file_writes_canonical_json(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "name": "Legacy",
                "mappings": {},
                "joystick": {
                    "mode": "directional",
                    "up": {"keys": ["KEY_UP"]},
                    "down": {"keys": ["KEY_DOWN"]},
                    "left": {"keys": ["KEY_LEFT"]},
                    "right": {"keys": ["KEY_RIGHT"]},
                },
            }
        )
    )

    result = migrate_profile_file(path, dry_run=False)

    assert result.changed is True
    assert result.written is True

    saved = json.loads(path.read_text())
    assert saved["joystick"]["mode"] == "digital"
    assert saved["joystick"]["key_up"] == "KEY_UP"


def test_migrate_profile_file_dry_run_does_not_write(tmp_path):
    path = tmp_path / "legacy.json"
    original = {
        "name": "Legacy",
        "joystick": {"mode": "directional", "up": {"keys": ["KEY_UP"]}},
    }
    path.write_text(json.dumps(original))

    result = migrate_profile_file(path, dry_run=True)

    assert result.changed is True
    assert result.written is False
    assert json.loads(path.read_text()) == original
