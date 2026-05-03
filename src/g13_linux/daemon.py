"""
G13 Daemon

Main orchestrator for G13 device management.
Coordinates input handling, LCD menu, LED effects, and key mapping.
"""

import asyncio
import logging
import signal
import sys
import threading
import time
from datetime import datetime

from .device import find_device
from .gui.models.event_decoder import EventDecoder
from .gui.models.macro_manager import MacroManager
from .gui.models.profile_manager import ProfileManager
from .hardware.backlight import G13Backlight
from .hardware.lcd import G13LCD
from .input.handler import InputHandler
from .input.navigation import NavigationController
from .led.controller import LEDController
from .mapper import G13Mapper
from .menu.manager import ScreenManager
from .menu.screen import InputEvent
from .menu.screens.idle import IdleScreen
from .server import G13Server
from .settings import SettingsManager

logger = logging.getLogger(__name__)


class G13Daemon:
    """
    Main daemon for G13 device control.

    Coordinates:
    - Key input reading and mapping
    - LCD menu system with thumbstick navigation
    - LED backlight effects
    - Profile management
    """

    # Update intervals
    RENDER_FPS = 20
    RENDER_INTERVAL = 1.0 / RENDER_FPS

    def __init__(
        self,
        enable_server: bool = True,
        server_host: str = "127.0.0.1",
        server_port: int = 8765,
        static_dir: str | None = None,
        use_libusb: bool = False,
    ):
        """
        Initialize daemon (does not connect to device yet).

        Args:
            enable_server: Whether to start WebSocket/HTTP server
            server_host: Host to bind server to
            server_port: Port for server
            static_dir: Directory for web GUI static files (default: auto-detect)
            use_libusb: Prefer libusb backend first.
        """
        self._device = None
        self._mapper: G13Mapper | None = None
        self._lcd: G13LCD | None = None
        self._backlight: G13Backlight | None = None
        self._led_controller: LEDController | None = None
        self._screen_manager: ScreenManager | None = None
        self._input_handler: InputHandler | None = None
        self._nav_controller: NavigationController | None = None

        self._running = False
        self._render_thread: threading.Thread | None = None
        self._server_thread: threading.Thread | None = None
        self._start_time: datetime | None = None
        self._key_count = 0

        # Event decoder for button state tracking (WebSocket broadcasts)
        self._event_decoder = EventDecoder()
        self._last_joystick = (128, 128)  # Track joystick for change detection

        # Mode state (M1, M2, M3)
        self._current_mode = "M1"

        # Lock for shared mutable state accessed from multiple threads
        # Protects: _current_mode, _last_joystick
        self._state_lock = threading.Lock()

        # Server settings
        self._enable_server = enable_server
        self._server_host = server_host
        self._server_port = server_port
        self._static_dir = static_dir
        self._use_libusb = use_libusb
        self._server: G13Server | None = None
        self._server_loop: asyncio.AbstractEventLoop | None = None

        # Profile manager
        self.profile_manager = ProfileManager()

        # Macro manager
        self.macro_manager = MacroManager()

        # Settings manager
        self.settings_manager = SettingsManager()

    @property
    def uptime(self) -> str:
        """Get daemon uptime as formatted string."""
        if not self._start_time:
            return "0:00"
        delta = datetime.now() - self._start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @property
    def key_count(self) -> int:
        """Get total key press count."""
        return self._key_count

    def connect(self) -> bool:
        """
        Connect to G13 device and initialize components.

        Returns:
            True if connection successful
        """
        logger.info("Opening G13 device...")
        result = find_device(use_libusb=self._use_libusb, return_diagnostics=True)
        if isinstance(result, tuple):
            self._device, backend_errors = result
        else:  # Backward compatibility
            self._device = result
            backend_errors = {}

        if self._device is None:
            logger.error("Could not open G13")
            if backend_errors:
                for backend, error in backend_errors.items():
                    logger.error(f"  {backend} failed: {error}")
            return False

        # Initialize hardware controllers
        self._lcd = G13LCD(self._device)
        self._backlight = G13Backlight(self._device)
        self._led_controller = LEDController(backlight=self._backlight)

        # Initialize mapper for key translation
        self._mapper = G13Mapper()

        # Initialize screen manager with LCD
        self._screen_manager = ScreenManager(lcd=self._lcd)
        self._screen_manager.led_controller = self._led_controller
        self._screen_manager.profile_manager = self.profile_manager
        self._screen_manager.settings_manager = self.settings_manager
        self._screen_manager.daemon = self

        # Create idle screen
        idle_screen = IdleScreen(
            self._screen_manager,
            profile_manager=self.profile_manager,
            settings_manager=self.settings_manager,
        )

        # Initialize navigation controller
        self._nav_controller = NavigationController(self._screen_manager, idle_screen)

        # Setup M-key profile callbacks
        self._setup_mkey_callbacks()

        # Initialize input handler
        self._input_handler = InputHandler(self._device, self._on_input_event)

        # Load default profile if available
        self._load_default_profile()

        logger.info("G13 daemon initialized")
        return True

    def _broadcast_device_connected(self):
        """Broadcast device connection to WebSocket clients (called after server starts)."""
        if self._server:
            self._broadcast_async(self._server.broadcast_device_connected())

    def _setup_mkey_callbacks(self):
        """Setup M-key callbacks for quick profile access."""
        # M1/M2/M3 show profile info toast (could be extended to switch profiles)
        self._nav_controller.set_profile_callback(
            InputEvent.BUTTON_M1,
            lambda: self._on_mkey_pressed(1),
        )
        self._nav_controller.set_profile_callback(
            InputEvent.BUTTON_M2,
            lambda: self._on_mkey_pressed(2),
        )
        self._nav_controller.set_profile_callback(
            InputEvent.BUTTON_M3,
            lambda: self._on_mkey_pressed(3),
        )

    def _on_mkey_pressed(self, m_num: int):
        """
        Handle M-key press for profile mode switching.

        Args:
            m_num: M-key number (1, 2, or 3)
        """
        mode = f"M{m_num}"
        self.set_mode(mode)

    def set_mode(self, mode: str):
        """
        Set the active mode (M1, M2, or M3).

        Args:
            mode: Mode name ("M1", "M2", or "M3")
        """
        if mode not in ("M1", "M2", "M3"):
            logger.warning(f"Invalid mode: {mode}")
            return

        with self._state_lock:
            old_mode = self._current_mode
            self._current_mode = mode

        profile_name = "None"
        if self.profile_manager.current_profile:
            profile_name = self.profile_manager.current_profile.name

        self.show_toast(f"{mode}: {profile_name}", duration=1.5)

        # Broadcast mode change to WebSocket clients
        if self._server and old_mode != mode:
            self._broadcast_async(self._server._broadcast({"type": "mode_changed", "mode": mode}))

        logger.info(f"Mode changed: {old_mode} -> {mode}")

    def _load_default_profile(self):
        """Load default/first profile if available."""
        profiles = self.profile_manager.list_profiles()
        if not profiles:
            logger.info("No profiles found")
            return

        # Try to load 'default' or 'example' profile, otherwise first available
        for name in ["default", "example", profiles[0]]:
            if name in profiles:
                try:
                    self.load_profile(name)
                    logger.info(f"Loaded profile: {name}")
                    return
                except Exception as e:
                    logger.warning(f"Could not load profile '{name}': {e}")

    def load_profile(self, name: str) -> bool:
        """
        Load a profile by name and apply its settings.

        Args:
            name: Profile name to load

        Returns:
            True if successful
        """
        try:
            profile = self.profile_manager.load_profile(name)

            # Apply backlight color
            if self._led_controller and hasattr(profile, "backlight"):
                color = profile.backlight.get("color", "#FFFFFF")
                if color.startswith("#") and len(color) == 7:
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                    self._led_controller.set_color(r, g, b)

            # Update mapper with new mappings
            if self._mapper:
                from dataclasses import asdict

                self._mapper.load_profile(asdict(profile))

            # Force idle screen refresh
            if self._screen_manager and self._screen_manager.current:
                self._screen_manager.current.mark_dirty()

            # Broadcast to WebSocket clients
            self.broadcast_profile_change(name)

            return True

        except FileNotFoundError:
            logger.error(f"Profile not found: {name}")
            return False
        except Exception as e:
            logger.error(f"Error loading profile '{name}': {e}")
            return False

    def run(self):
        """
        Run the daemon main loop.

        Blocks until stopped via Ctrl+C or stop().
        """
        if not self._device:
            if not self.connect():
                sys.exit(1)

        self._running = True
        self._start_time = datetime.now()

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        # Start render thread
        self._render_thread = threading.Thread(target=self._render_loop, daemon=True, name="Render")
        self._render_thread.start()

        # Start WebSocket/HTTP server if enabled
        if self._enable_server:
            self._start_server()
            # Give server time to start, then broadcast connected
            time.sleep(0.1)
            self._broadcast_device_connected()

        # Force initial render
        self._screen_manager.force_render()

        logger.info("G13 daemon running. Press Ctrl+C to exit.")
        server_msg = (
            f" Server at http://{self._server_host}:{self._server_port}"
            if self._enable_server
            else ""
        )
        print(f"G13 opened. Press stick for menu.{server_msg} Ctrl+C to exit.")

        # Main loop - single source of device reads.
        # We read once and fan out to all consumers to avoid split/dropped events.
        try:
            while self._running:
                try:
                    data = self._device.read(timeout_ms=100)
                    if data:
                        if self._input_handler:
                            self._input_handler.process_report(data)
                        self._handle_raw_report(data)
                    elif self._input_handler:
                        self._input_handler.tick()
                except Exception as e:
                    logger.debug(f"Read error: {e}")
                    time.sleep(0.01)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, stopping daemon")
        finally:
            self.stop()

    def _stop_components(self):
        """Stop all daemon components."""
        if self._enable_server:
            self._stop_server()
        if self._input_handler:
            self._input_handler.stop()
        if self._led_controller:
            self._led_controller.stop_effect()
        if self._render_thread and self._render_thread.is_alive():
            self._render_thread.join(timeout=1.0)

    def _close_hardware(self):
        """Close hardware resources safely."""
        if self._mapper:
            self._mapper.close()
        if self._lcd:
            try:
                self._lcd.clear()
            except Exception:
                pass  # Best-effort cleanup, device may already be disconnected
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass  # Best-effort cleanup, device may already be closed

    def stop(self):
        """Stop the daemon and clean up resources."""
        if not self._running:
            return

        logger.info("Stopping G13 daemon...")
        self._running = False

        self._stop_components()
        self._close_hardware()

        logger.info("G13 daemon stopped")
        print("\nG13 daemon stopped.")

    def _start_server(self):
        """Start the WebSocket/HTTP server in a background thread."""
        self._server = G13Server(
            self, self._server_host, self._server_port, static_dir=self._static_dir
        )
        self._server_thread = threading.Thread(
            target=self._run_server_loop, daemon=True, name="Server"
        )
        self._server_thread.start()
        logger.info(f"Server thread started on {self._server_host}:{self._server_port}")

    def _run_server_loop(self):
        """Run the asyncio event loop for the server."""
        self._server_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._server_loop)

        try:
            self._server_loop.run_until_complete(self._server.start())
            self._server_loop.run_forever()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self._server_loop.close()

    def _stop_server(self):
        """Stop the WebSocket/HTTP server."""
        if self._server and self._server_loop:
            # Schedule server stop in the event loop
            future = asyncio.run_coroutine_threadsafe(self._server.stop(), self._server_loop)
            try:
                future.result(timeout=2.0)
            except Exception as e:
                logger.warning(f"Error stopping server: {e}")

            # Stop the event loop
            self._server_loop.call_soon_threadsafe(self._server_loop.stop)

            # Wait for server thread
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=2.0)

            logger.info("Server stopped")

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        self._running = False

    def _on_input_event(self, event: InputEvent):
        """
        Handle input events from InputHandler.

        Routes events to navigation controller for menu handling.

        Args:
            event: Input event
        """
        if self._nav_controller:
            self._nav_controller.on_input(event)

    def _handle_raw_report(self, data: bytes):
        """
        Handle raw HID report for key mapping and WebSocket broadcasting.

        Passes report to mapper for key translation and broadcasts
        button events to connected WebSocket clients.

        Args:
            data: Raw HID report bytes
        """
        if self._mapper:
            # Track key presses (rough count based on mapper activity)
            self._mapper.handle_raw_report(data)
            self._key_count += 1

        # Decode state and broadcast button changes
        if self._enable_server and self._server:
            try:
                state = self._event_decoder.decode_report(data)
                pressed, released = self._event_decoder.get_button_changes(state)

                # Broadcast button events
                for button in pressed:
                    self.broadcast_button_event(button, pressed=True)
                for button in released:
                    self.broadcast_button_event(button, pressed=False)

                # Broadcast joystick position if changed significantly
                joystick = (state.joystick_x, state.joystick_y)
                with self._state_lock:
                    changed = self._joystick_changed(joystick)
                    if changed:
                        self._last_joystick = joystick
                if changed:
                    self._broadcast_joystick(joystick)

            except Exception as e:
                logger.debug(f"Event decode error: {e}")

    def _joystick_changed(self, new_pos: tuple[int, int], threshold: int = 5) -> bool:
        """Check if joystick position changed enough to broadcast."""
        dx = abs(new_pos[0] - self._last_joystick[0])
        dy = abs(new_pos[1] - self._last_joystick[1])
        return dx > threshold or dy > threshold

    def _broadcast_joystick(self, position: tuple[int, int]):
        """Broadcast joystick position to WebSocket clients."""
        if self._server and self._server_loop and self._server_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._server._broadcast({"type": "joystick", "x": position[0], "y": position[1]}),
                self._server_loop,
            )

    def _render_loop(self):
        """Background thread for LCD rendering."""
        last_update = time.time()

        while self._running:
            try:
                now = time.time()
                dt = now - last_update
                last_update = now

                # Update screens
                if self._screen_manager:
                    self._screen_manager.update(dt)
                    self._screen_manager.render()

                # Sleep for target frame time
                elapsed = time.time() - now
                sleep_time = max(0, self.RENDER_INTERVAL - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Render error: {e}")
                time.sleep(self.RENDER_INTERVAL)

    def set_backlight_color(self, r: int, g: int, b: int):
        """
        Set backlight color.

        Args:
            r: Red (0-255)
            g: Green (0-255)
            b: Blue (0-255)
        """
        if self._led_controller:
            self._led_controller.set_color(r, g, b)

    def set_button_mapping(self, button: str, key: str) -> bool:
        """
        Update a single button mapping in the current profile.

        Args:
            button: Button ID (e.g., "G1", "G22", "LEFT")
            key: Key code string (e.g., "KEY_A") or combo dict

        Returns:
            True if successful
        """
        if not self.profile_manager.current_profile:
            logger.warning("No profile loaded - cannot update mapping")
            return False

        profile = self.profile_manager.current_profile

        # Update the mapping
        profile.mappings[button] = key

        # Save the profile
        try:
            self.profile_manager.save_profile(profile, self.profile_manager.current_name)
        except Exception as e:
            logger.error(f"Failed to save profile: {e}")
            return False

        # Reload mappings into mapper
        if self._mapper:
            from dataclasses import asdict

            self._mapper.load_profile(asdict(profile))

        logger.info(f"Updated mapping: {button} -> {key}")
        return True

    def show_toast(self, message: str, duration: float = 2.0):
        """
        Show a toast notification on LCD.

        Args:
            message: Message to display
            duration: Display duration in seconds
        """
        if self._nav_controller:
            self._nav_controller.show_toast(message, duration)

    # Server broadcast helpers

    def _broadcast_async(self, coro):
        """Schedule an async broadcast in the server's event loop."""
        if self._server and self._server_loop and self._server_loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._server_loop)

    def broadcast_button_event(self, button: str, pressed: bool):
        """Broadcast button press/release to WebSocket clients."""
        if self._server:
            if pressed:
                self._broadcast_async(self._server.broadcast_button_pressed(button))
            else:
                self._broadcast_async(self._server.broadcast_button_released(button))

    def broadcast_profile_change(self, name: str):
        """Broadcast profile activation to WebSocket clients."""
        if self._server:
            self._broadcast_async(self._server.broadcast_profile_activated(name))


def main():
    """Command-line entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    daemon = G13Daemon()
    daemon.run()


if __name__ == "__main__":
    main()
