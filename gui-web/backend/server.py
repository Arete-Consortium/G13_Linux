#!/usr/bin/env python3
"""
G13 Web GUI Backend Server

WebSocket server that bridges the G13 device with the React frontend.
Provides real-time button events and profile/macro management.
"""

import asyncio
import json
import logging
import re
import sys
from contextlib import suppress
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add G13_Linux to path
G13_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(G13_ROOT / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="G13 Web API", version="1.0.0")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Profile and Macro paths
PROFILES_DIR = G13_ROOT / "configs" / "profiles"
MACROS_DIR = G13_ROOT / "configs" / "macros"

# Ensure directories exist
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
MACROS_DIR.mkdir(parents=True, exist_ok=True)


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")


manager = ConnectionManager()


# Device state (simulated when no hardware)
class DeviceState:
    def __init__(self):
        self.connected = False
        self.active_profile: str | None = None
        self.active_mode = "M1"
        self.pressed_keys: set[str] = set()
        self.joystick = {"x": 0.0, "y": 0.0}
        self.backlight = {"color": "#ff6b00", "brightness": 100}

    def to_dict(self):
        return {
            "connected": self.connected,
            "active_profile": self.active_profile,
            "active_mode": self.active_mode,
            "pressed_keys": list(self.pressed_keys),
            "joystick": self.joystick,
            "backlight": self.backlight,
        }


device_state = DeviceState()


# Pydantic models
class ProfileData(BaseModel):
    name: str
    description: str = ""
    mappings: dict = {}
    backlight: dict = {"color": "#ff6b00", "brightness": 100}
    joystick: dict = {"mode": "analog", "deadzone": 20}


class MacroData(BaseModel):
    name: str
    description: str = ""
    steps: list = []
    speed_multiplier: float = 1.0
    repeat_count: int = 1


def _safe_path(base_dir: Path, name: str) -> Path:
    """Resolve a user-supplied name to a safe path within base_dir."""
    safe_name = re.sub(r"[^a-zA-Z0-9_\-.]", "", name)
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid name")
    filepath = (base_dir / f"{safe_name}.json").resolve()
    if not filepath.is_relative_to(base_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid name")
    return filepath


# REST API Endpoints


@app.get("/api/status")
async def get_status():
    """Get current device status."""
    return device_state.to_dict()


@app.get("/api/profiles")
async def list_profiles():
    """List all available profiles."""
    profiles = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            profiles.append(
                {
                    "name": data.get("name", f.stem),
                    "filename": f.name,
                    "description": data.get("description", ""),
                }
            )
        except Exception as e:
            logger.error(f"Error reading profile {f}: {e}")
    return {"profiles": profiles}


@app.get("/api/profiles/{name}")
async def get_profile(name: str):
    """Get a specific profile."""
    profile_path = _safe_path(PROFILES_DIR, name)
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    return json.loads(profile_path.read_text())


@app.post("/api/profiles/{name}")
async def save_profile(name: str, profile: ProfileData):
    """Save a profile."""
    profile_path = _safe_path(PROFILES_DIR, name)
    data = profile.model_dump()
    data["name"] = name
    profile_path.write_text(json.dumps(data, indent=2))
    await manager.broadcast({"type": "profile_saved", "name": name})
    return {"status": "ok", "name": name}


@app.delete("/api/profiles/{name}")
async def delete_profile(name: str):
    """Delete a profile."""
    profile_path = _safe_path(PROFILES_DIR, name)
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    profile_path.unlink()
    await manager.broadcast({"type": "profile_deleted", "name": name})
    return {"status": "ok"}


@app.post("/api/profiles/{name}/activate")
async def activate_profile(name: str):
    """Activate a profile."""
    profile_path = _safe_path(PROFILES_DIR, name)
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    device_state.active_profile = name
    await manager.broadcast({"type": "profile_activated", "name": name})
    return {"status": "ok", "name": name}


@app.get("/api/macros")
async def list_macros():
    """List all macros."""
    macros = []
    for f in MACROS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            macros.append(
                {
                    "id": f.stem,
                    "name": data.get("name", f.stem),
                    "description": data.get("description", ""),
                    "steps_count": len(data.get("steps", [])),
                }
            )
        except Exception as e:
            logger.error(f"Error reading macro {f}: {e}")
    return {"macros": macros}


@app.get("/api/macros/{macro_id}")
async def get_macro(macro_id: str):
    """Get a specific macro."""
    macro_path = _safe_path(MACROS_DIR, macro_id)
    if not macro_path.exists():
        raise HTTPException(status_code=404, detail="Macro not found")
    return json.loads(macro_path.read_text())


@app.post("/api/macros")
async def create_macro(macro: MacroData):
    """Create a new macro."""
    import uuid

    macro_id = str(uuid.uuid4())
    macro_path = MACROS_DIR / f"{macro_id}.json"
    data = macro.model_dump()
    data["id"] = macro_id
    macro_path.write_text(json.dumps(data, indent=2))
    await manager.broadcast({"type": "macro_created", "id": macro_id})
    return {"status": "ok", "id": macro_id}


@app.delete("/api/macros/{macro_id}")
async def delete_macro(macro_id: str):
    """Delete a macro."""
    macro_path = _safe_path(MACROS_DIR, macro_id)
    if not macro_path.exists():
        raise HTTPException(status_code=404, detail="Macro not found")
    macro_path.unlink()
    await manager.broadcast({"type": "macro_deleted", "id": macro_id})
    return {"status": "ok"}


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for real-time updates."""
    await manager.connect(websocket)

    # Send initial state
    await websocket.send_json({"type": "state", "data": device_state.to_dict()})

    try:
        while True:
            data = await websocket.receive_json()
            await handle_ws_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def handle_ws_message(websocket: WebSocket, message: dict):
    """Handle incoming WebSocket messages."""
    msg_type = message.get("type")

    if msg_type == "set_mode":
        mode = message.get("mode", "M1")
        if mode in ("M1", "M2", "M3"):
            device_state.active_mode = mode
            await manager.broadcast({"type": "mode_changed", "mode": mode})

    elif msg_type == "set_mapping":
        button = message.get("button")
        key = message.get("key")
        # Update mapping in active profile (sanitize for log injection)
        safe_button = str(button).replace("\n", "").replace("\r", "")[:20]
        safe_key = str(key).replace("\n", "").replace("\r", "")[:20]
        logger.info(f"Set mapping: {safe_button} -> {safe_key}")
        await manager.broadcast({"type": "mapping_changed", "button": button, "key": key})

    elif msg_type == "simulate_press":
        button = message.get("button")
        device_state.pressed_keys.add(button)
        await manager.broadcast({"type": "button_pressed", "button": button})

    elif msg_type == "simulate_release":
        button = message.get("button")
        device_state.pressed_keys.discard(button)
        await manager.broadcast({"type": "button_released", "button": button})

    elif msg_type == "get_state":
        await websocket.send_json({"type": "state", "data": device_state.to_dict()})

    elif msg_type == "set_backlight":
        color = message.get("color")
        brightness = message.get("brightness")
        if color:
            device_state.backlight["color"] = color
        if brightness is not None:
            device_state.backlight["brightness"] = brightness
        await manager.broadcast({"type": "backlight_changed", "backlight": device_state.backlight})


# Device integration (when hardware available)
device_task: asyncio.Task | None = None


async def device_event_loop():
    """Poll device for events and broadcast to clients."""
    device = None
    try:
        from g13_linux import device as g13_device
        from g13_linux.gui.models.event_decoder import EventDecoder

        decoder = EventDecoder()
        find_device = getattr(g13_device, "find_device", None)
        if callable(find_device):
            device = find_device(use_libusb=True)
        elif hasattr(g13_device, "open_g13_libusb"):
            logger.warning("find_device unavailable; falling back to open_g13_libusb()")
            device = g13_device.open_g13_libusb()
        elif hasattr(g13_device, "open_g13"):
            logger.warning("find_device unavailable; falling back to open_g13()")
            device = g13_device.open_g13()
        else:
            raise RuntimeError("No compatible device discovery function available")

        if device:
            device_state.connected = True
            await manager.broadcast({"type": "device_connected"})
            logger.info("G13 device connected")

            while True:
                try:
                    data = device.read(timeout_ms=100)
                    if data:
                        state = decoder.decode_report(data)
                        # Broadcast button changes
                        for btn, pressed in state.buttons.items():
                            if pressed and btn not in device_state.pressed_keys:
                                device_state.pressed_keys.add(btn)
                                await manager.broadcast({"type": "button_pressed", "button": btn})
                            elif not pressed and btn in device_state.pressed_keys:
                                device_state.pressed_keys.discard(btn)
                                await manager.broadcast({"type": "button_released", "button": btn})
                except Exception as e:
                    logger.debug(f"Device read: {e}")

                await asyncio.sleep(0.01)
        else:
            logger.info("No G13 device detected; running in simulation mode")
    except ImportError:
        logger.warning("G13 device module not available, running in simulation mode")
    except asyncio.CancelledError:
        # Normal shutdown path
        pass
    except Exception as e:
        logger.error(f"Device loop error: {e}")
    finally:
        if device is not None:
            try:
                device.close()
            except Exception as e:
                logger.debug(f"Device close failed: {e}")

        if device_state.connected:
            device_state.connected = False
            with suppress(Exception):
                await manager.broadcast({"type": "device_disconnected"})


@app.on_event("startup")
async def startup_event():
    """Start device polling on server startup."""
    global device_task
    device_task = asyncio.create_task(device_event_loop())
    logger.info("G13 Web API server started")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on server shutdown."""
    if device_task:
        device_task.cancel()
        with suppress(asyncio.CancelledError):
            await device_task
    logger.info("G13 Web API server stopped")


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=True, log_level="info")
