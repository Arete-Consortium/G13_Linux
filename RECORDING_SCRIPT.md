# G13_Linux - 90 Second Demo Recording Script

## Recording Setup
- **Tool:** `peek` or `simplescreenrecorder`
- **Resolution:** 1920x1080 or 1280x720
- **FPS:** 20
- **Duration:** 90 seconds
- **Output:** `demo.gif`
- **Camera:** Consider using phone camera to show physical keyboard + screen recording split-screen

## Hardware Requirements
- **Logitech G13 Gaming Keyboard** connected via USB
- Driver unloaded initially (will load during demo)

## Pre-Recording Checklist
- [ ] G13 keyboard connected but driver NOT loaded
- [ ] Terminal window open and ready
- [ ] Configuration files prepared at `~/.g13/default.conf`
- [ ] Second terminal or text editor ready for showing macro definitions
- [ ] Screen recording tool launched and area selected

---

## Shot-by-Shot Script (90 seconds)

### 0:00-0:15 | Kernel Module Load (15s)
**Action:**
1. Start with terminal showing:
   ```bash
   $ lsusb | grep Logitech
   Bus 001 Device 005: ID 046d:c21c Logitech, Inc. G13 Advanced Gameboard
   ```
2. Show G13 is detected but inactive (LEDs off)
3. Load the kernel module:
   ```bash
   $ sudo modprobe g13
   ```
4. **Camera on keyboard:** LEDs light up (blue/green/red cycle)
5. Terminal shows:
   ```bash
   [  123.456] g13: Logitech G13 detected
   [  123.789] g13: Device initialized successfully
   ```
6. Check device node created:
   ```bash
   $ ls -l /dev/g13-*
   crw-rw---- 1 root input 251 0 Dec 25 10:30 /dev/g13-0
   ```

**Key Visual:** Kernel integration, hardware activation, device node creation

---

### 0:15-0:30 | LCD Display Initialization (15s)
**Action:**
1. G13 LCD screen (160x43 monochrome display) comes to life
2. Default boot logo appears (or custom logo if configured)
3. Show LCD display in split-screen or phone camera close-up
4. Terminal command:
   ```bash
   $ cat /sys/class/g13/g13-0/lcd_brightness
   5
   $ echo 7 > /sys/class/g13/g13-0/lcd_brightness
   ```
5. **Camera on G13:** LCD brightness increases
6. Write custom text to LCD:
   ```bash
   $ echo "G13 LINUX DRIVER" > /sys/class/g13/g13-0/lcd
   $ echo "by AreteDriver" >> /sys/class/g13/g13-0/lcd
   ```
7. **Camera on G13:** Custom text appears on LCD

**Key Visual:** LCD control, sysfs interface, real-time hardware feedback

---

### 0:30-0:45 | LED Control (15s)
**Action:**
1. Show LED color control via sysfs:
   ```bash
   # Red LEDs
   $ echo 255 0 0 > /sys/class/g13/g13-0/led_color
   ```
2. **Camera on G13:** Keys glow RED
3. Change to green:
   ```bash
   $ echo 0 255 0 > /sys/class/g13/g13-0/led_color
   ```
4. **Camera on G13:** Keys glow GREEN
5. Change to blue:
   ```bash
   $ echo 0 0 255 > /sys/class/g13/g13-0/led_color
   ```
6. **Camera on G13:** Keys glow BLUE
7. Set to custom purple:
   ```bash
   $ echo 128 0 255 > /sys/class/g13/g13-0/led_color
   ```

**Key Visual:** RGB LED control, sysfs API, real-time color changes

---

### 0:45-0:60 | Macro Configuration (15s)
**Action:**
1. Open configuration file in editor:
   ```bash
   $ cat ~/.g13/default.conf
   ```
2. Show sample macro definitions:
   ```
   # G1 key - Screenshot
   bind G1 "import -window root screenshot.png"

   # G2 key - Volume up
   bind G2 "amixer set Master 5%+"

   # G3 key - Launch terminal
   bind G3 "gnome-terminal"

   # G4 key - EVE Online macro (F1-F8 sequence)
   bind G4 "xdotool key F1 F2 F3 F4 F5 F6 F7 F8"
   ```
3. Show joystick bindings:
   ```
   # Joystick as arrow keys
   joy_up KEY_UP
   joy_down KEY_DOWN
   joy_left KEY_LEFT
   joy_right KEY_RIGHT
   ```
4. Load configuration:
   ```bash
   $ g13d --config ~/.g13/default.conf
   G13 daemon started
   Configuration loaded: 22 bindings active
   ```

**Key Visual:** Powerful macro system, configuration flexibility

---

### 0:60-0:75 | Live Macro Execution (15s)
**Action:**
1. **Camera on G13 keyboard** (or indicator showing which key is pressed)
2. Press **G1** key:
   - Terminal shows: `Executing: import -window root screenshot.png`
   - Screenshot taken (flash on screen or notification)
3. Press **G2** key:
   - Volume indicator appears on screen showing increase
   - Terminal shows: `Executing: amixer set Master 5%+`
4. Press **G3** key:
   - New terminal window opens instantly
   - Shows macro execution speed
5. Press **G4** key (EVE macro simulation):
   - If EVE is running: weapons fire in sequence
   - OR show in terminal: `Executing: xdotool key F1 F2...`

**Key Visual:** Real-time macro execution, instant response, practical use cases

---

### 0:75-0:90 | Profile Switching (15s)
**Action:**
1. Show multiple profiles available:
   ```bash
   $ ls ~/.g13/
   default.conf  gaming.conf  productivity.conf
   ```
2. Switch to gaming profile:
   ```bash
   $ g13d --config ~/.g13/gaming.conf
   Switching profile: gaming
   ```
3. **Camera on G13:**
   - LCD updates showing: "GAMING MODE"
   - LEDs change color to red (gaming theme)
4. Switch to productivity profile:
   ```bash
   $ g13d --config ~/.g13/productivity.conf
   ```
5. **Camera on G13:**
   - LCD updates: "PRODUCTIVITY"
   - LEDs change to blue (calm theme)
6. Terminal shows:
   ```bash
   $ dmesg | tail -5
   [  450.123] g13: Profile switched: productivity
   [  450.124] g13: 18 macros loaded
   [  450.125] g13: LED mode: static blue
   ```

**Key Visual:** Profile management, context switching, professional workflow

---

## Post-Recording

### Optimize GIF
```bash
# Reduce FPS and size for GitHub
ffmpeg -i demo.gif -vf "fps=15,scale=1280:-1:flags=lanczos" -y demo_optimized.gif

# Check size (target <10MB)
ls -lh demo_optimized.gif
```

### Add to Repository
```bash
cp demo_optimized.gif /home/arete/G13_Linux/demo.gif

# Update README.md (add at top)
# ![Demo](demo.gif)

git add demo.gif README.md
git commit -m "Add 90-second kernel driver demo"
git push origin main
```

---

## Recording Tips

### Split-Screen Setup
Consider using OBS Studio for professional split-screen:
- **Left:** Terminal commands and output
- **Right:** G13 keyboard close-up (phone camera via DroidCam or similar)
- **Bottom:** LCD display close-up

### Hardware Close-ups
- Use phone camera on tripod for stable keyboard shots
- Ensure LEDs are clearly visible (slight darkness helps RGB pop)
- LCD text must be readable (adjust brightness before recording)

### Terminal Aesthetics
```bash
# Use a good terminal theme
# Make font size large enough: 14-16pt
# Enable prompt colors

# Example .bashrc addition for recording:
PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
```

### Timing
- Allow 2-3 seconds for each visual change (LED color, LCD text)
- Camera transitions should be smooth (if using multiple angles)
- Command typing can be pre-written and pasted (or use `script` command for clean replay)

### Pre-Record Testing
Practice the full sequence 2-3 times:
1. Module load → LEDs activate (5s)
2. LCD control → brightness + text (10s)
3. LED colors → RGB cycle (10s)
4. Config display → macro definitions (15s)
5. Macro execution → live demos (15s)
6. Profile switching → mode changes (15s)

---

## Alternative: Pure Terminal Demo
If hardware close-up is not possible, focus on terminal output:
- Show `watch -n 0.5 cat /sys/class/g13/g13-0/keys_pressed` in split pane
- Press keys, watch real-time key codes appear
- Demonstrates kernel integration without needing camera

---

## Installation Commands for Recording Tools

### Install Peek (GIF recorder)
```bash
sudo apt install peek
```

### Install OBS Studio (advanced)
```bash
sudo apt install obs-studio
```

### Install DroidCam (phone as webcam)
```bash
# For hardware close-ups
# Download from: https://www.dev47apps.com/droidcam/linux/
```

---

**Goal:** Viewer watches and thinks "This is legitimate kernel-level hardware integration. This developer knows systems programming."
