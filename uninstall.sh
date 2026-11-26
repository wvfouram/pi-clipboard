#!/bin/bash
# Removes Clipboard.
SRC="$(cd "$(dirname "$0")" && pwd)"
if [ "$(id -u)" = "0" ]; then
  echo "Run this as your normal user (not with sudo)."
  exit 1
fi

echo "==> Removing Super+V"
pkill -f /opt/pi-clipboard/pi_clipboard.py 2>/dev/null || true
[ -f /opt/pi-clipboard/keybind.py ] && python3 /opt/pi-clipboard/keybind.py remove W-v pi-clipboard
rm -f "$HOME/.config/autostart/pi-clipboard.desktop"

sudo rm -rf /opt/pi-clipboard /usr/local/bin/pi-clipboard /usr/share/applications/pi-clipboard.desktop \
  /usr/share/icons/hicolor/scalable/apps/pi-clipboard.svg
sudo update-desktop-database -q /usr/share/applications 2>/dev/null || true
echo "Clipboard removed. Your settings are still in ~/.config/pi-clipboard (delete that folder to remove them)."
