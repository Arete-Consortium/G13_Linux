"""
G13 Linux CLI

Command-line interface for controlling the Logitech G13.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__

# Color presets
COLOR_PRESETS = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "white": (255, 255, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "orange": (255, 128, 0),
    "purple": (128, 0, 255),
    "off": (0, 0, 0),
}


def cmd_doctor(args):
    """Diagnose G13 detection, backend availability, and common setup issues."""
    from .device import find_g13_hidraw_info, probe_device_backends

    prefer_libusb = getattr(args, "libusb_first", False)
    backend_order = "libusb -> hidraw" if prefer_libusb else "hidraw -> libusb"

    print("G13 Linux Doctor")
    print("================")
    print(f"Probe order: {backend_order}")

    hidraw_info = find_g13_hidraw_info()
    if hidraw_info:
        hidraw_path = hidraw_info["path"]
        print(f"Hidraw path: {hidraw_path}")
        access = []
        access.append("r" if hidraw_info.get("readable") else "-")
        access.append("w" if hidraw_info.get("writable") else "-")
        source = hidraw_info.get("detection_source") or "unknown"
        print(f"Hidraw access: {''.join(access)} (detected via {source})")
    else:
        print("Hidraw path: not found in /sys/class/hidraw")

    diagnostics = probe_device_backends(use_libusb=prefer_libusb)
    any_ok = False
    for result in diagnostics:
        backend = result.get("backend", "unknown")
        if result.get("ok"):
            any_ok = True
            print(f"{backend}: OK")
        else:
            error = result.get("error") or "unknown error"
            print(f"{backend}: FAILED ({error})")

    if any_ok:
        print("Result: at least one backend can open the G13.")
        return

    print("Result: no backend could open the G13.")
    print("Troubleshooting:")
    print("  1) Verify udev rules are installed and reloaded.")
    print("     sudo cp udev/99-logitech-g13.rules /etc/udev/rules.d/")
    print("     sudo udevadm control --reload-rules && sudo udevadm trigger")
    print("  2) Re-plug the G13 and run this command again.")
    print("  3) For input capture, try libusb mode with elevated permissions.")
    print("     sudo g13-linux-gui --libusb")
    sys.exit(1)


def cmd_run(args):
    """Run the G13 input daemon."""
    if getattr(args, "simple", False):
        # Simple mode: key mapping only, no LCD menu
        from .device import open_g13
        from .mapper import G13Mapper

        print("Opening Logitech G13 (simple mode)…")
        try:
            h = open_g13()
        except Exception as e:
            print(f"Error: Could not open G13 device: {e}", file=sys.stderr)
            print("Make sure the G13 is connected and udev rules are installed.", file=sys.stderr)
            sys.exit(1)

        mapper = G13Mapper()
        print("G13 opened. Press keys; Ctrl+C to exit.")

        try:
            while True:
                data = h.read(timeout_ms=100)
                if data:
                    mapper.handle_raw_report(data)
        except KeyboardInterrupt:
            print("\nExiting.")
        finally:
            h.close()
            mapper.close()
    else:
        # Full daemon with LCD menu
        from .daemon import G13Daemon

        enable_server = not getattr(args, "no_server", False)
        server_host = getattr(args, "server_host", "127.0.0.1")
        server_port = getattr(args, "server_port", 8765)
        static_dir = getattr(args, "static_dir", None)
        use_libusb = getattr(args, "libusb", False)

        print("Starting G13 daemon...")
        daemon = G13Daemon(
            enable_server=enable_server,
            server_host=server_host,
            server_port=server_port,
            static_dir=static_dir,
            use_libusb=use_libusb,
        )
        daemon.run()


def cmd_lcd(args):
    """Display text on the LCD."""
    from .device import open_g13
    from .hardware.lcd import G13LCD

    try:
        device = open_g13()
    except Exception as e:
        print(f"Error: Could not open G13: {e}", file=sys.stderr)
        sys.exit(1)

    lcd = G13LCD(device)

    if args.clear:
        lcd.clear()
        print("LCD cleared.")
    else:
        text = " ".join(args.text) if args.text else ""
        if text:
            lcd.clear()
            lcd.write_text_centered(text)
            print(f"LCD: {text}")
        else:
            print("No text provided. Use --clear to clear the LCD.", file=sys.stderr)
            sys.exit(1)

    device.close()


def cmd_color(args):
    """Set the backlight color."""
    from .device import open_g13
    from .hardware.backlight import G13Backlight

    # Parse color
    if args.color in COLOR_PRESETS:
        r, g, b = COLOR_PRESETS[args.color]
    elif len(args.color) == 6 and all(c in "0123456789abcdefABCDEF" for c in args.color):
        # Hex color without #
        r = int(args.color[0:2], 16)
        g = int(args.color[2:4], 16)
        b = int(args.color[4:6], 16)
    elif args.color.startswith("#") and len(args.color) == 7:
        # Hex color with #
        r = int(args.color[1:3], 16)
        g = int(args.color[3:5], 16)
        b = int(args.color[5:7], 16)
    else:
        # Try RGB values
        try:
            parts = args.color.split(",")
            if len(parts) == 3:
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                raise ValueError()
        except ValueError:
            print(f"Error: Invalid color '{args.color}'", file=sys.stderr)
            print("Use: preset name, hex (#FF0000), or RGB (255,0,0)", file=sys.stderr)
            print(f"Presets: {', '.join(COLOR_PRESETS.keys())}", file=sys.stderr)
            sys.exit(1)

    try:
        device = open_g13()
    except Exception as e:
        print(f"Error: Could not open G13: {e}", file=sys.stderr)
        sys.exit(1)

    backlight = G13Backlight(device)
    backlight.set_color(r, g, b)
    print(f"Backlight: RGB({r}, {g}, {b})")
    device.close()


def cmd_effect(args):
    """Control LED effects."""
    from .device import open_g13
    from .hardware.backlight import G13Backlight
    from .led import RGB, EffectType, LEDController

    try:
        device = open_g13()
    except Exception as e:
        print(f"Error: Could not open G13: {e}", file=sys.stderr)
        sys.exit(1)

    backlight = G13Backlight(device)
    led = LEDController(backlight=backlight)

    effect_name = args.effect.lower()

    if effect_name == "off" or effect_name == "stop":
        led.stop_effect()
        led.off()
        print("LED off")
    elif effect_name == "solid":
        led.stop_effect()
        color = _parse_effect_color(args.color)
        led.set_rgb(color)
        print(f"Solid: {color.to_hex()}")
    elif effect_name == "pulse":
        color = _parse_effect_color(args.color)
        speed = args.speed or 1.0
        led.start_effect(EffectType.PULSE, color=color, speed=speed)
        print(f"Pulse: {color.to_hex()} @ {speed}x")
        _wait_for_effect(led)
    elif effect_name == "rainbow":
        speed = args.speed or 0.5
        led.start_effect(EffectType.RAINBOW, speed=speed)
        print(f"Rainbow @ {speed}x")
        _wait_for_effect(led)
    elif effect_name == "fade":
        color1 = _parse_effect_color(args.color)
        color2 = _parse_effect_color(args.color2) if args.color2 else RGB(0, 0, 255)
        speed = args.speed or 0.5
        led.start_effect(EffectType.FADE, color1=color1, color2=color2, speed=speed)
        print(f"Fade: {color1.to_hex()} <-> {color2.to_hex()} @ {speed}x")
        _wait_for_effect(led)
    elif effect_name == "alert":
        color = _parse_effect_color(args.color) if args.color else RGB(255, 0, 0)
        count = args.count or 3
        led.run_alert(color=color, count=count, blocking=True)
        print(f"Alert: {color.to_hex()} x{count}")
    elif effect_name == "list":
        print("Available effects:")
        print("  solid   - Static color")
        print("  pulse   - Breathing effect")
        print("  rainbow - Color cycle")
        print("  fade    - Two-color transition")
        print("  alert   - Flash notification")
        print("  off     - Turn off LED")
    else:
        print(f"Unknown effect: {effect_name}", file=sys.stderr)
        print("Use 'g13-linux effect list' to see available effects", file=sys.stderr)
        sys.exit(1)

    device.close()


def _parse_effect_color(color_str: str | None):
    """Parse color string for effects and return RGB instance."""
    from .led import NAMED_COLORS, RGB

    if not color_str:
        return RGB(255, 0, 0)  # Default red

    color_str = color_str.lower()
    if color_str in NAMED_COLORS:
        return NAMED_COLORS[color_str]
    elif color_str.startswith("#"):
        return RGB.from_hex(color_str)
    elif len(color_str) == 6:
        return RGB.from_hex(color_str)
    else:
        try:
            parts = color_str.split(",")
            return RGB(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            print(f"Warning: Invalid color '{color_str}', using red", file=sys.stderr)
            return RGB(255, 0, 0)


def _wait_for_effect(led):
    """Wait for user interrupt while effect runs."""
    import time

    print("Press Ctrl+C to stop...")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        led.stop_effect()
        print("\nStopped")


def _profile_list(pm, args):
    """List all profiles."""
    profiles = pm.list_profiles()
    if profiles:
        print("Available profiles:")
        for p in profiles:
            print(f"  - {p}")
    else:
        print("No profiles found.")


def _profile_show(pm, args):
    """Show profile details."""
    try:
        profile = pm.load_profile(args.name)
        print(f"Profile: {profile.name}")
        print(f"Description: {profile.description or '(none)'}")
        print(f"Backlight: {profile.backlight}")
        print(f"LCD: {profile.lcd}")
        print(f"Mappings ({len(profile.mappings)}):")
        for key, value in sorted(profile.mappings.items()):
            if isinstance(value, dict):
                print(f"  {key}: {value.get('keys', value)}")
            elif value != "KEY_RESERVED":
                print(f"  {key}: {value}")
    except FileNotFoundError:
        print(f"Error: Profile '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)


def _profile_load(pm, args):
    """Load and apply a profile."""
    try:
        profile = pm.load_profile(args.name)
        print(f"Loaded profile: {profile.name}")
        _apply_profile_backlight(profile)
    except FileNotFoundError:
        print(f"Error: Profile '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)


def _apply_profile_backlight(profile):
    """Apply profile backlight to device if available."""
    try:
        from .device import open_g13
        from .hardware.backlight import G13Backlight

        device = open_g13()
        backlight = G13Backlight(device)

        color = profile.backlight.get("color", "#FFFFFF")
        if color.startswith("#"):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            backlight.set_color(r, g, b)
            print(f"Applied backlight: RGB({r}, {g}, {b})")

        device.close()
    except Exception as e:
        print(f"Note: Could not apply to device: {e}")


def _profile_create(pm, args):
    """Create a new profile."""
    if pm.profile_exists(args.name):
        print(f"Error: Profile '{args.name}' already exists.", file=sys.stderr)
        sys.exit(1)
    profile = pm.create_profile(args.name)
    pm.save_profile(profile)
    print(f"Created profile: {args.name}")


def _profile_delete(pm, args):
    """Delete a profile."""
    try:
        pm.delete_profile(args.name)
        print(f"Deleted profile: {args.name}")
    except FileNotFoundError:
        print(f"Error: Profile '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)


def _profile_migrate(pm, args):
    """Migrate legacy profile joystick fields to canonical schema."""
    from .profile_migration import migrate_profile_file

    if args.all and args.name:
        print("Error: Provide a profile name or --all, not both.", file=sys.stderr)
        sys.exit(1)
    if not args.all and not args.name:
        print("Error: Provide a profile name or use --all.", file=sys.stderr)
        sys.exit(1)

    if args.all:
        profile_paths = sorted(pm.profiles_dir.glob("*.json"))
        if not profile_paths:
            print("No profiles found.")
            return
    else:
        profile_path = pm.profiles_dir / f"{args.name}.json"
        if not profile_path.exists():
            print(f"Error: Profile '{args.name}' not found.", file=sys.stderr)
            sys.exit(1)
        profile_paths = [profile_path]

    changed = 0
    unchanged = 0
    errors = 0

    for path in profile_paths:
        result = migrate_profile_file(path, dry_run=args.dry_run)
        if result.error:
            errors += 1
            print(f"Error: {path.name}: {result.error}", file=sys.stderr)
            continue

        if result.changed:
            changed += 1
            action = "Would migrate" if args.dry_run else "Migrated"
            print(f"{action}: {path.stem}")
            for detail in result.details:
                print(f"  - {detail}")
        else:
            unchanged += 1
            print(f"No changes: {path.stem}")

    if args.dry_run:
        print(f"Dry run complete: {changed} to migrate, {unchanged} unchanged, {errors} errors.")
    else:
        print(f"Migration complete: {changed} migrated, {unchanged} unchanged, {errors} errors.")

    if errors:
        sys.exit(1)


# Profile command dispatch
_PROFILE_COMMANDS = {
    "list": _profile_list,
    "show": _profile_show,
    "load": _profile_load,
    "create": _profile_create,
    "delete": _profile_delete,
    "migrate": _profile_migrate,
}


def cmd_profile(args):
    """Manage profiles."""
    from .gui.models.profile_manager import ProfileManager

    pm = ProfileManager()
    handler = _PROFILE_COMMANDS.get(args.profile_cmd)
    if handler:
        handler(pm, args)


def main():
    parser = argparse.ArgumentParser(
        prog="g13-linux",
        description="Logitech G13 Linux driver",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", "-v", action="version", version=f"g13-linux {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run the input daemon")
    run_parser.add_argument(
        "--simple",
        "-s",
        action="store_true",
        help="Simple mode: key mapping only, no LCD menu",
    )
    run_parser.add_argument(
        "--libusb",
        action="store_true",
        help="Prefer libusb backend first (often requires sudo for input capture)",
    )
    run_parser.add_argument(
        "--no-server",
        action="store_true",
        help="Disable WebSocket/HTTP server for GUI",
    )
    run_parser.add_argument(
        "--server-host",
        default="127.0.0.1",
        help="Server bind address (default: 127.0.0.1)",
    )
    run_parser.add_argument(
        "--server-port",
        type=int,
        default=8765,
        help="Server port (default: 8765)",
    )
    run_parser.add_argument(
        "--static-dir",
        help="Directory for web GUI static files (default: auto-detect)",
    )
    run_parser.set_defaults(func=cmd_run)

    # lcd command
    lcd_parser = subparsers.add_parser("lcd", help="Control the LCD display")
    lcd_parser.add_argument("text", nargs="*", help="Text to display")
    lcd_parser.add_argument("--clear", "-c", action="store_true", help="Clear the LCD")
    lcd_parser.set_defaults(func=cmd_lcd)

    # color command
    color_parser = subparsers.add_parser("color", help="Set backlight color")
    color_parser.add_argument(
        "color",
        help=f"Color: preset ({', '.join(COLOR_PRESETS.keys())}), hex (#FF0000), or RGB (255,0,0)",
    )
    color_parser.set_defaults(func=cmd_color)

    # effect command
    effect_parser = subparsers.add_parser("effect", help="Control LED effects")
    effect_parser.add_argument(
        "effect",
        help="Effect: solid, pulse, rainbow, fade, alert, off, or list",
    )
    effect_parser.add_argument(
        "--color",
        "-c",
        help="Primary color (name, hex, or R,G,B)",
    )
    effect_parser.add_argument(
        "--color2",
        help="Secondary color for fade effect",
    )
    effect_parser.add_argument(
        "--speed",
        "-s",
        type=float,
        help="Effect speed multiplier (default: 1.0)",
    )
    effect_parser.add_argument(
        "--count",
        "-n",
        type=int,
        help="Flash count for alert effect (default: 3)",
    )
    effect_parser.set_defaults(func=cmd_effect)

    # doctor command
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnose G13 detection and backend setup",
    )
    doctor_parser.add_argument(
        "--libusb-first",
        action="store_true",
        help="Probe libusb first, then hidraw",
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    # profile command
    profile_parser = subparsers.add_parser("profile", help="Manage profiles")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_cmd", help="Profile commands")

    profile_subparsers.add_parser("list", help="List profiles")
    profile_show = profile_subparsers.add_parser("show", help="Show profile details")
    profile_show.add_argument("name", help="Profile name")
    profile_load = profile_subparsers.add_parser("load", help="Load a profile")
    profile_load.add_argument("name", help="Profile name")
    profile_create = profile_subparsers.add_parser("create", help="Create a new profile")
    profile_create.add_argument("name", help="Profile name")
    profile_delete = profile_subparsers.add_parser("delete", help="Delete a profile")
    profile_delete.add_argument("name", help="Profile name")
    profile_migrate = profile_subparsers.add_parser(
        "migrate",
        help="Migrate legacy joystick profile fields to canonical schema",
    )
    profile_migrate.add_argument(
        "name",
        nargs="?",
        help="Profile name (omit when using --all)",
    )
    profile_migrate.add_argument(
        "--all",
        action="store_true",
        help="Migrate all profiles in the profiles directory",
    )
    profile_migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migrations without writing changes",
    )

    profile_parser.set_defaults(func=cmd_profile)

    args = parser.parse_args()

    if args.command is None:
        # Default: run daemon
        cmd_run(args)
    elif hasattr(args, "func"):
        if args.command == "profile" and args.profile_cmd is None:
            profile_parser.print_help()
            sys.exit(1)
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
