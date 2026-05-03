# G13 Linux Web GUI

Browser-based key mapper and configuration interface for the Logitech G13 gaming keypad.

## Features

- **Visual Key Mapper** — Click buttons on an interactive G13 device to configure mappings
- **Real-time Feedback** — See button presses live via WebSocket connection
- **Profile Management** — Create, save, load, and switch between profiles
- **Macro Support** — Create and assign macros to buttons
- **Backlight Control** — Adjust RGB color and brightness
- **Simulation Mode** — Works without hardware for testing and development

## Architecture

```
┌─────────────────────┐     WebSocket      ┌─────────────────────┐
│   React Frontend    │ ◄──────────────────► │  FastAPI Backend    │
│   (localhost:5173)  │                      │  (localhost:8765)   │
└─────────────────────┘     REST API       └──────────┬──────────┘
                                                       │
                                                       │ hidapi/libusb
                                                       ▼
                                              ┌─────────────────┐
                                              │   G13 Device    │
                                              └─────────────────┘
```

### Frontend (gui-web/)

- **Framework**: React 18 + TypeScript + Vite
- **Components**:
  - `G13Device` — Interactive device visualization
  - `G13Button` — Clickable button with hover/active states
  - `KeyMappingPanel` — Configure key bindings
  - `MacroPanel` — Create and manage macros
- **Hooks**:
  - `useG13WebSocket` — WebSocket connection with auto-reconnect
- **API**:
  - `g13Api.ts` — REST client for profiles and macros

### Backend (gui-web/backend/)

- **Framework**: FastAPI + uvicorn
- **Endpoints**:
  - `GET /api/status` — Device connection status
  - `GET/POST/DELETE /api/profiles/{name}` — Profile CRUD
  - `POST /api/profiles/{name}/activate` — Load a profile
  - `GET/POST/DELETE /api/macros` — Macro CRUD
  - `WS /ws` — Real-time button events

## Quick Start

### 1. Start the Backend

```bash
cd gui-web/backend

# Create virtual environment (first time)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run server
python server.py
```

Server starts at `http://127.0.0.1:8765`

### 2. Start the Frontend

```bash
cd gui-web

# Install dependencies (first time)
npm install

# Run dev server
npm run dev
```

Opens at `http://localhost:5173`

## Usage

1. **Configure Buttons**: Click any G-key on the device image to open the mapping panel
2. **Test Buttons**: Right-click a button to simulate a press (useful without hardware)
3. **Switch Modes**: Click M1/M2/M3 to switch between key binding modes
4. **Save Profile**: Click "Save Profile" to persist your configuration
5. **Load Profile**: Click "Load Profile" to switch between saved configurations
6. **Adjust Backlight**: Use the color picker and brightness slider

## Development

```bash
# Frontend lint
cd gui-web && npm run lint

# Frontend build
npm run build

# Backend (from project root)
cd gui-web/backend
ruff check server.py
```

## Requirements

### Frontend
- Node.js 18+
- npm or pnpm

### Backend
- Python 3.9+
- fastapi
- uvicorn
- pydantic

See `backend/requirements.txt` for exact versions.

## Configuration

Profiles and macros are stored in:
- `configs/profiles/*.json` — Key binding profiles
- `configs/macros/*.json` — Macro definitions

Joystick config in profile JSON should use:

```json
{
  "joystick": {
    "mode": "analog",
    "deadzone": 20,
    "sensitivity": 1.0,
    "key_up": "KEY_UP",
    "key_down": "KEY_DOWN",
    "key_left": "KEY_LEFT",
    "key_right": "KEY_RIGHT",
    "allow_diagonals": true
  }
}
```

Legacy `mode: "directional"` profiles are still loaded, but saving from the GUI or API should use the canonical schema above.
Migration examples: `docs/profile-migration.md` (project root).
CLI helper: `g13-linux profile migrate --all --dry-run`

## Simulation Mode

When no G13 hardware is detected, the backend runs in simulation mode:
- All UI features work normally
- Button presses can be simulated via right-click
- Profile/macro management is fully functional
- Useful for development and testing

## Hardware Detection Troubleshooting

1. Check backend status:
   - `curl http://127.0.0.1:8765/api/status`
   - Confirm `"connected": true`
2. Verify Linux can see the device:
   - `lsusb | grep -i logitech`
3. Ensure access permissions are applied:
   - Install and reload `udev/99-logitech-g13.rules`
4. Make sure no other app has exclusive access to the device.
