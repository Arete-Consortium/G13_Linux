#!/bin/bash
# Build G13 Linux AppImage
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build/appimage"
APPDIR="${BUILD_DIR}/G13_Linux.AppDir"

echo "=== G13 Linux AppImage Builder ==="
echo "Project root: ${PROJECT_ROOT}"
echo "Build dir: ${BUILD_DIR}"

# Clean previous build
rm -rf "${BUILD_DIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Get Python version
PYTHON="python3"
PYTHON_VERSION=$(${PYTHON} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

echo "=== Creating virtual environment ==="
${PYTHON} -m venv "${BUILD_DIR}/venv"
source "${BUILD_DIR}/venv/bin/activate"

echo "=== Installing g13-linux and dependencies ==="
pip install --upgrade pip
pip install "${PROJECT_ROOT}"

echo "=== Copying Python installation ==="
# Copy Python interpreter
cp "$(which python3)" "${APPDIR}/usr/bin/python${PYTHON_VERSION}"
ln -sf "python${PYTHON_VERSION}" "${APPDIR}/usr/bin/python3"
ln -sf "python${PYTHON_VERSION}" "${APPDIR}/usr/bin/python"

# Copy Python standard library
PYTHON_LIB="/usr/lib/python${PYTHON_VERSION}"
if [ -d "${PYTHON_LIB}" ]; then
    cp -r "${PYTHON_LIB}" "${APPDIR}/usr/lib/"
fi

# Copy site-packages from venv
cp -r "${BUILD_DIR}/venv/lib/python${PYTHON_VERSION}/site-packages" "${APPDIR}/usr/lib/python${PYTHON_VERSION}/"

echo "=== Copying system libraries ==="
# Copy required shared libraries
LIBS=(
    "/usr/lib/x86_64-linux-gnu/libhidapi-hidraw.so"*
    "/usr/lib/x86_64-linux-gnu/libhidapi-libusb.so"*
    "/usr/lib/x86_64-linux-gnu/libusb-1.0.so"*
)

for lib in "${LIBS[@]}"; do
    if [ -f "$lib" ]; then
        cp -L "$lib" "${APPDIR}/usr/lib/" 2>/dev/null || true
    fi
done

# Bundle libpython so the AppImage runs on systems without matching system Python.
#
# Two cases by how the bundled python3 binary is linked:
#   1. DYNAMIC (GitHub Actions toolcache Python, custom builds): libpython
#      shows up in `ldd python3` and MUST be bundled — otherwise the AppImage
#      breaks on any host without a matching libpythonX.Y.so. This is the
#      bug fixed in v1.7.1 (CI builds were dynamic + libpython unbundled).
#   2. STATIC (Ubuntu distro python3): libpython is compiled into the binary,
#      so `ldd` shows nothing and there's nothing to bundle. Fine to skip.
echo "=== Bundling libpython ==="
LIBPYTHON_PATH=$(ldd "$(which python3)" 2>/dev/null | grep -oP '/[^ ]*libpython[^ ]+\.so[^ ]*' | head -1)
if [ -n "${LIBPYTHON_PATH}" ] && [ -f "${LIBPYTHON_PATH}" ]; then
    echo "Found dynamic libpython at: ${LIBPYTHON_PATH}"
    cp -L "${LIBPYTHON_PATH}" "${APPDIR}/usr/lib/"
else
    echo "No dynamic libpython detected (python3 appears statically linked). Skipping bundle."
fi

echo "=== Setting up AppImage structure ==="
# Copy AppRun
cp "${SCRIPT_DIR}/AppRun" "${APPDIR}/"
chmod +x "${APPDIR}/AppRun"

# Copy desktop file
cp "${SCRIPT_DIR}/g13-linux.desktop" "${APPDIR}/"
cp "${SCRIPT_DIR}/g13-linux.desktop" "${APPDIR}/usr/share/applications/"

# Copy/create icon
if [ -f "${PROJECT_ROOT}/g13-linux.svg" ]; then
    # Convert SVG to PNG for AppImage
    if command -v rsvg-convert &> /dev/null; then
        rsvg-convert -w 256 -h 256 "${PROJECT_ROOT}/g13-linux.svg" -o "${APPDIR}/g13-linux.png"
    elif command -v convert &> /dev/null; then
        convert -background none -resize 256x256 "${PROJECT_ROOT}/g13-linux.svg" "${APPDIR}/g13-linux.png"
    else
        # Create a simple placeholder icon
        echo "Warning: No SVG converter found, creating placeholder icon"
        ${PYTHON} -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), (40, 40, 45, 255))
draw = ImageDraw.Draw(img)
draw.rounded_rectangle([20, 20, 236, 236], radius=20, fill=(60, 60, 65), outline=(0, 200, 100), width=4)
draw.text((80, 100), 'G13', fill=(0, 200, 100))
img.save('${APPDIR}/g13-linux.png')
"
    fi
else
    # Create icon from Python
    ${PYTHON} -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGBA', (256, 256), (40, 40, 45, 255))
draw = ImageDraw.Draw(img)
draw.rounded_rectangle([20, 20, 236, 236], radius=20, fill=(50, 50, 55), outline=(0, 180, 80), width=4)
draw.text((60, 90), 'G13', fill=(0, 200, 100))
draw.text((50, 140), 'Linux', fill=(0, 160, 80))
img.save('${APPDIR}/g13-linux.png')
"
fi

cp "${APPDIR}/g13-linux.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/"

# Symlink icon for AppImage
ln -sf usr/share/icons/hicolor/256x256/apps/g13-linux.png "${APPDIR}/.DirIcon"

echo "=== Downloading appimagetool ==="
APPIMAGETOOL="${BUILD_DIR}/appimagetool"
if [ ! -f "${APPIMAGETOOL}" ]; then
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O "${APPIMAGETOOL}"
    chmod +x "${APPIMAGETOOL}"
fi

echo "=== Building AppImage ==="
cd "${BUILD_DIR}"

# Get version from package
VERSION=$(${PYTHON} -c "import g13_linux; print(g13_linux.__version__)")
OUTPUT="${PROJECT_ROOT}/dist/G13_Linux-${VERSION}-x86_64.AppImage"

mkdir -p "${PROJECT_ROOT}/dist"

ARCH=x86_64 "${APPIMAGETOOL}" --appimage-extract-and-run "${APPDIR}" "${OUTPUT}"

echo ""
echo "=== Build complete ==="
echo "AppImage: ${OUTPUT}"
echo ""
echo "To run: chmod +x ${OUTPUT} && ${OUTPUT}"

deactivate
