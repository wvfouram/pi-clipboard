#!/bin/bash
# Installer for Clipboard (Windows 11 style) on Raspberry Pi
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
if [ "$(id -u)" = "0" ]; then
  echo "Run this as your normal user (not with sudo). It will ask for sudo when needed."
  exit 1
fi

echo "==> Installing packages"
sudo apt-get update || echo "   (apt update had errors, continuing)"
if ! sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 wl-clipboard xdg-utils; then
  for p in python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 wl-clipboard xdg-utils; do
    sudo apt-get install -y "$p" || echo "   (could not install $p)"
  done
fi
sudo apt-get install -y fonts-open-sans || echo "   (Open Sans font not available, using system font)"
for p in wtype; do
  sudo apt-get install -y "$p" || echo "   ($p not available, skipping)"
done

echo "==> Installing app"
sudo install -d /opt/pi-clipboard
sudo install -m 644 "$SRC/pi_clipboard.py" /opt/pi-clipboard/pi_clipboard.py
printf '#!/bin/sh\nexec /usr/bin/python3 /opt/pi-clipboard/pi_clipboard.py "$@"\n' | sudo tee /usr/local/bin/pi-clipboard >/dev/null
sudo chmod 755 /usr/local/bin/pi-clipboard

echo "==> Adding menu entry and icon"
sudo install -D -m 644 "$SRC/pi-clipboard.svg" /usr/share/icons/hicolor/scalable/apps/pi-clipboard.svg
sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
sudo tee /usr/share/applications/pi-clipboard.desktop >/dev/null <<'DESK'
[Desktop Entry]
Type=Application
Name=Clipboard
GenericName=Clipboard history
Comment=Clipboard history (Super+V)
Exec=pi-clipboard 
Icon=pi-clipboard
Terminal=false
Categories=Utility;GTK;
StartupWMClass=pi-clipboard
StartupNotify=true
DESK
sudo update-desktop-database -q /usr/share/applications 2>/dev/null || true

echo "==> Setting up Super+V and starting clipboard history"
sudo install -m 644 "$SRC/keybind.py" /opt/pi-clipboard/keybind.py
python3 /opt/pi-clipboard/keybind.py add W-v pi-clipboard
mkdir -p "$HOME/.config/autostart"
printf '[Desktop Entry]\nType=Application\nName=Clipboard history\nExec=pi-clipboard --daemon\nNoDisplay=true\n' > "$HOME/.config/autostart/pi-clipboard.desktop"
pkill -f /opt/pi-clipboard/pi_clipboard.py 2>/dev/null || true
if [ -n "$WAYLAND_DISPLAY" ] || [ -n "$DISPLAY" ]; then
  (setsid pi-clipboard --daemon >/dev/null 2>&1 &)
fi

echo
echo "Done. Copy something, then press Super+V."
