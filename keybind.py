#!/usr/bin/python3
# Adds a keyboard shortcut to the desktop's keyboard config (labwc, wayfire, openbox), or removes it.
#   keybind.py add <labwc-key> <command> [--wayfire "<super> KEY_V"]
#   keybind.py remove <labwc-key> <command>
# Any old binding on the same key is saved and put back on remove.
import os
import re
import sys
import time
import shutil
import subprocess
import xml.dom.minidom

HOME = os.path.expanduser("~")


def bind_xml(key, cmd):
    return f'<keybind key="{key}"><action name="Execute" command="{cmd}" /></keybind>'


def key_re(key):
    return re.compile(r'[ \t]*<keybind\s+key="' + re.escape(key) + r'"[^>]*?(?:/>|>.*?</keybind>)[ \t]*\n?', re.S)


def edit_xml(path, fallback_src, root_tag, key, cmd, remove, saved):
    bx = bind_xml(key, cmd)
    if not os.path.exists(path):
        if remove:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if fallback_src and os.path.exists(fallback_src):
            shutil.copy(fallback_src, path)
        else:
            with open(path, "w") as f:
                f.write(f'<?xml version="1.0"?>\n<{root_tag}>\n  <keyboard>\n    <default />\n  </keyboard>\n</{root_tag}>\n')
    with open(path) as f:
        txt = f.read()
    if remove:
        new = txt.replace(bx, "")
        if os.path.exists(saved):
            with open(saved) as f:
                old = f.read().strip()
            os.remove(saved)
            if old:
                new = re.sub(r"(<keyboard\s*>(\s*<default\s*/>)?)", lambda m: m.group(1) + "\n    " + old, new, count=1)
        new = re.sub(r"\n[ \t]*\n[ \t]*\n", "\n\n", new)
    else:
        if bx in txt:
            print(f"  {path}: {key} already set")
            return
        shutil.copy(path, f"{path}.bak-{int(time.time())}")
        olds = [m.group(0).strip() for m in key_re(key).finditer(txt)]
        if olds and not os.path.exists(saved):
            os.makedirs(os.path.dirname(saved), exist_ok=True)
            with open(saved, "w") as f:
                f.write("\n    ".join(olds))
        new = key_re(key).sub("", txt)
        if re.search(r"<keyboard\s*>\s*<default\s*/>", new):
            new = re.sub(r"(<keyboard\s*>\s*<default\s*/>)", lambda m: m.group(1) + "\n    " + bx, new, count=1)
        elif re.search(r"<keyboard\s*>", new):
            new = re.sub(r"(<keyboard\s*>)", lambda m: m.group(1) + "\n    " + bx, new, count=1)
        elif re.search(r"<keyboard\s*/>", new):
            new = re.sub(r"<keyboard\s*/>", "<keyboard>\n    <default />\n    " + bx + "\n  </keyboard>", new, count=1)
        else:
            new = new.replace(f"</{root_tag}>", "  <keyboard>\n    <default />\n    " + bx + f"\n  </keyboard>\n</{root_tag}>")
    try:
        xml.dom.minidom.parseString(new)
    except Exception as e:
        print(f"  {path}: could not change it safely ({e}); left unchanged")
        return
    with open(path, "w") as f:
        f.write(new)
    print(f"  {path}: {'removed' if remove else 'added'} {key}")


def main():
    if len(sys.argv) < 4 or sys.argv[1] not in ("add", "remove"):
        print(__doc__ or "usage: keybind.py add|remove KEY COMMAND")
        return
    remove = sys.argv[1] == "remove"
    key, cmd = sys.argv[2], sys.argv[3]
    name = os.path.basename(cmd.split()[0])
    saved = os.path.join(HOME, ".config", name, f"oldkey-{re.sub(r'[^A-Za-z0-9]+', '_', key)}.xml")
    did = False
    if shutil.which("labwc") or os.path.exists(f"{HOME}/.config/labwc"):
        edit_xml(f"{HOME}/.config/labwc/rc.xml", "/etc/xdg/labwc/rc.xml", "labwc_config", key, cmd, remove, saved)
        if os.environ.get("LABWC_PID") and shutil.which("labwc"):
            subprocess.run(["labwc", "--reconfigure"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-HUP", "-x", "labwc"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        did = True
    ob = f"{HOME}/.config/openbox/lxde-pi-rc.xml"
    if os.path.exists(ob):
        edit_xml(ob, None, "openbox_config", key, cmd, remove, saved + ".ob")
        did = True
    if not did:
        print("  No supported desktop config found; open the app from the menu instead.")


if __name__ == "__main__":
    main()
