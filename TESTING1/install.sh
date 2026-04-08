#!/bin/bash
# DrowsiGuard V1 — Installation Script for Jetson Nano A02
# Run: sudo bash install.sh

set -e

echo "=================================="
echo "DrowsiGuard V1 — Installer"
echo "=================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. System dependencies
echo "[1/5] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3-pip python3-dev v4l-utils

# 2. Python dependencies
echo "[2/5] Installing Python dependencies..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"

# 3. Create directories
echo "[3/5] Creating directories..."
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/storage"
mkdir -p "$SCRIPT_DIR/sounds"
mkdir -p "$SCRIPT_DIR/_backup"

# 4. Install systemd service
echo "[4/5] Installing systemd service..."
cp "$SCRIPT_DIR/drowsiguard.service" /etc/systemd/system/drowsiguard.service
systemctl daemon-reload
systemctl enable drowsiguard.service
echo "  Service installed and enabled (will start on next boot)"

# 5. Verify
echo "[5/5] Running environment check..."
python3 "$SCRIPT_DIR/tests/test_environment.py"

echo ""
echo "=================================="
echo "Installation complete!"
echo "  Start now:   sudo systemctl start drowsiguard"
echo "  View logs:   journalctl -u drowsiguard -f"
echo "  Run tests:   python3 tests/test_camera.py"
echo "               sudo python3 tests/test_rfid.py"
echo "=================================="
