#!/usr/bin/python3
# Clipboard history for Raspberry Pi, styled after the Windows 11 clipboard (Win+V).
import os
import sys
import re
import json
import math
import time
import shutil
import signal
import threading
import subprocess

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango, Gio, GObject  # noqa: E402,F401
import cairo  # noqa: E402

HOME = os.path.expanduser("~")
C_ACCENT = "#4CC2FF"
def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def _rr(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def _line(cr, *pts):
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    cr.stroke()


def draw_glyph(cr, name, s, col):
    """Monochrome line icons for buttons."""
    cr.save()
    cr.scale(s / 16.0, s / 16.0)
    cr.set_source_rgba(*col)
    cr.set_line_width(1.15)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    pi = math.pi
    L = lambda *p: _line(cr, *p)  # noqa: E731
    if name == "back":
        L((13.5, 8), (2.5, 8))
        L((7, 3.5), (2.5, 8), (7, 12.5))
    elif name == "forward":
        L((2.5, 8), (13.5, 8))
        L((9, 3.5), (13.5, 8), (9, 12.5))
    elif name == "up":
        L((8, 13.5), (8, 2.5))
        L((3.5, 7), (8, 2.5), (12.5, 7))
    elif name == "refresh":
        cr.arc(8, 8, 5.5, -pi * 0.35, pi * 1.55)
        cr.stroke()
        L((12.9, 1.8), (12.6, 4.9), (9.6, 4.6))
    elif name == "plus":
        L((8, 2.5), (8, 13.5))
        L((2.5, 8), (13.5, 8))
    elif name == "new":
        cr.set_source_rgba(*hexc(C_ACCENT))
        cr.arc(8, 8, 6.5, 0, 2 * pi)
        cr.stroke()
        L((8, 4.8), (8, 11.2))
        L((4.8, 8), (11.2, 8))
    elif name == "cut":
        cr.arc(4.5, 12, 2, 0, 2 * pi)
        cr.stroke()
        cr.arc(11.5, 12, 2, 0, 2 * pi)
        cr.stroke()
        L((5.8, 10.5), (11, 1.8))
        L((10.2, 10.5), (5, 1.8))
    elif name == "copy":
        _rr(cr, 5, 1.5, 9, 10.5, 1.5)
        cr.stroke()
        cr.move_to(3, 4.5)
        cr.line_to(3, 13)
        cr.arc_negative(4.5, 13, 1.5, pi, pi / 2)
        cr.line_to(11, 14.5)
        cr.stroke()
    elif name == "paste":
        _rr(cr, 2.5, 3, 11, 11.5, 1.5)
        cr.stroke()
        _rr(cr, 5.5, 1.5, 5, 3, 1)
        cr.stroke()
        L((5.5, 8), (10.5, 8))
        L((5.5, 11), (9, 11))
    elif name == "rename":
        _rr(cr, 1.5, 4.5, 13, 7, 1.3)
        cr.stroke()
        L((4, 8), (8, 8))
        L((10.5, 2.5), (10.5, 13.5))
        L((9, 2.5), (12, 2.5))
        L((9, 13.5), (12, 13.5))
    elif name == "delete" or name == "trash":
        L((2.5, 4), (13.5, 4))
        L((6, 4), (6.5, 2), (9.5, 2), (10, 4))
        cr.move_to(4, 4)
        cr.line_to(4.8, 14)
        cr.line_to(11.2, 14)
        cr.line_to(12, 4)
        cr.stroke()
        L((6.8, 6.8), (7, 11.5))
        L((9.2, 6.8), (9, 11.5))
    elif name == "sort":
        L((4.5, 2.5), (4.5, 13.5))
        L((2, 5), (4.5, 2.5), (7, 5))
        L((11.5, 2.5), (11.5, 13.5))
        L((9, 11), (11.5, 13.5), (14, 11))
    elif name == "view":
        for y in (3, 8, 13):
            L((2, y), (14, y))
    elif name == "more":
        for x in (3, 8, 13):
            cr.arc(x, 8, 1.1, 0, 2 * pi)
            cr.fill()
    elif name == "chevdown":
        L((4, 6), (8, 10), (12, 6))
    elif name == "chevright":
        L((6, 4), (10, 8), (6, 12))
    elif name == "close":
        L((3.5, 3.5), (12.5, 12.5))
        L((12.5, 3.5), (3.5, 12.5))
    elif name == "min":
        L((3, 8), (13, 8))
    elif name == "max":
        _rr(cr, 3, 3, 10, 10, 1.2)
        cr.stroke()
    elif name == "restore":
        _rr(cr, 3, 5, 8, 8, 1.2)
        cr.stroke()
        L((5, 3), (12, 3), (13, 4), (13, 11))
    elif name == "search":
        cr.arc(6.6, 6.6, 4.6, 0, 2 * pi)
        cr.stroke()
        L((10, 10), (14, 14))
    elif name == "pane":
        _rr(cr, 1.5, 2.5, 13, 11, 1.5)
        cr.stroke()
        L((10, 2.5), (10, 13.5))
    elif name == "terminal":
        _rr(cr, 1.5, 2.5, 13, 11, 1.5)
        cr.stroke()
        L((4, 6), (6.5, 8), (4, 10))
        L((8, 10.5), (11.5, 10.5))
    elif name == "properties":
        _rr(cr, 2.5, 1.5, 11, 13, 1.5)
        cr.stroke()
        for y in (5, 8, 11):
            cr.arc(5.2, y, 0.8, 0, 2 * pi)
            cr.fill()
            L((7.2, y), (11, y))
    elif name == "pin":
        cr.move_to(6, 2)
        cr.line_to(10, 2)
        cr.line_to(9.5, 6.5)
        cr.line_to(12, 9)
        cr.line_to(4, 9)
        cr.line_to(6.5, 6.5)
        cr.close_path()
        cr.stroke()
        L((8, 9), (8, 14))
    elif name == "pin-fill":
        cr.set_line_width(1.0)
        cr.translate(8, 8)
        cr.rotate(pi / 4)
        cr.translate(-8, -8)
        cr.move_to(6, 2)
        cr.line_to(10, 2)
        cr.line_to(9.5, 6.5)
        cr.line_to(12, 9)
        cr.line_to(4, 9)
        cr.line_to(6.5, 6.5)
        cr.close_path()
        cr.stroke()
        L((8, 9), (8, 14))
    elif name == "folder":
        cr.move_to(1.5, 4)
        cr.line_to(6, 4)
        cr.line_to(7.5, 5.5)
        cr.line_to(14.5, 5.5)
        cr.line_to(14.5, 13)
        cr.line_to(1.5, 13)
        cr.close_path()
        cr.stroke()
    elif name == "file":
        cr.move_to(3.5, 1.5)
        cr.line_to(9.5, 1.5)
        cr.line_to(12.5, 4.5)
        cr.line_to(12.5, 14.5)
        cr.line_to(3.5, 14.5)
        cr.close_path()
        cr.stroke()
        L((9.5, 1.5), (9.5, 4.5), (12.5, 4.5))
    elif name == "zip":
        _rr(cr, 2.5, 1.5, 11, 13, 1.5)
        cr.stroke()
        for y in (3, 5, 7):
            L((7, y), (9, y))
        _rr(cr, 6.5, 9, 3, 3.5, 0.6)
        cr.stroke()
    elif name == "extract":
        _rr(cr, 2.5, 6.5, 11, 8, 1.5)
        cr.stroke()
        L((8, 1.5), (8, 10))
        L((5.5, 7.5), (8, 10), (10.5, 7.5))
    elif name == "restoreitem":
        cr.arc(8.5, 8.5, 5, -pi * 0.9, pi * 0.6)
        cr.stroke()
        L((2, 3.5), (3.6, 6.6), (6.6, 5.4))
    elif name == "open":
        _rr(cr, 1.5, 1.5, 13, 13, 2)
        cr.stroke()
        L((7, 9), (12.5, 3.5))
        L((8.5, 3.5), (12.5, 3.5), (12.5, 7.5))
    elif name == "newtab":
        _rr(cr, 1.5, 3.5, 13, 10, 1.5)
        cr.stroke()
        L((1.5, 6), (8, 6))
        L((8, 3.5), (8, 6))
    elif name == "check":
        L((3, 8.5), (6.5, 12), (13, 4.5))
    elif name == "eject":
        cr.move_to(8, 3)
        cr.line_to(13, 9)
        cr.line_to(3, 9)
        cr.close_path()
        cr.stroke()
        L((3, 12.5), (13, 12.5))
    elif name == "details-view":
        for y in (3.5, 8, 12.5):
            _rr(cr, 1.5, y - 1.2, 2.4, 2.4, 0.5)
            cr.stroke()
            L((6, y), (14.5, y))
    elif name == "icons-view":
        for x in (2, 9):
            for y in (2, 9):
                _rr(cr, x, y, 5, 5, 1.2)
                cr.stroke()
    elif name == "selectall":
        _rr(cr, 2, 2, 12, 12, 1.5)
        cr.stroke()
        L((5, 8), (7.2, 10.2), (11, 6))
    elif name == "info":
        cr.arc(8, 8, 6, 0, 2 * pi)
        cr.stroke()
        L((8, 7), (8, 11.5))
        cr.arc(8, 4.8, 0.9, 0, 2 * pi)
        cr.fill()
    elif name == "share":
        cr.arc(4, 8, 1.8, 0, 2 * pi)
        cr.stroke()
        cr.arc(12, 3.8, 1.8, 0, 2 * pi)
        cr.stroke()
        cr.arc(12, 12.2, 1.8, 0, 2 * pi)
        cr.stroke()
        L((5.6, 7.1), (10.4, 4.7))
        L((5.6, 8.9), (10.4, 11.3))
    elif name == "network":
        _rr(cr, 5, 1.5, 6, 4.5, 1)
        cr.stroke()
        L((8, 6), (8, 9))
        L((3, 9), (13, 9))
        L((3, 9), (3, 11))
        L((13, 9), (13, 11))
        _rr(cr, 1, 11, 4, 3.5, 0.8)
        cr.stroke()
        _rr(cr, 11, 11, 4, 3.5, 0.8)
        cr.stroke()
    elif name == "link":
        cr.arc(5.5, 10.5, 3, pi * 0.25, pi * 1.75)
        cr.stroke()
        cr.arc(10.5, 5.5, 3, pi * 1.25, pi * 0.75)
        cr.stroke()
        L((6.5, 9.5), (9.5, 6.5))
    else:
        draw_glyph_extra(cr, name, L, pi)
    cr.restore()




# ----------------------------------------------------------------------------
# Shared Windows 11 dark style
# ----------------------------------------------------------------------------
BASE_CSS = """
* { font-family: "Segoe UI Variable Text", "Segoe UI", "Selawik", "Open Sans", "Noto Sans", sans-serif; }
window.fx, window.fx-dialog { background-color: #202020; color: #ffffff; font-size: 12px; }
.fx label { color: #ffffff; }
headerbar.fx-title { background: #202020; border: none; box-shadow: none; min-height: 40px; padding: 0; margin: 0; }
headerbar.fx-title:backdrop { background: #202020; }
.app-title { font-size: 12px; color: #ffffff; margin-left: 4px; }
.app-title:backdrop { color: rgba(255,255,255,0.55); }
button.wc { background: transparent; border: none; border-radius: 0; min-width: 46px; min-height: 32px; padding: 0; box-shadow: none; }
button.wc:hover { background-color: rgba(255,255,255,0.06); }
button.wc.close:hover { background-color: #C42B1C; }
.tabstrip { margin-top: 6px; margin-left: 6px; }
button.tab { outline-color: transparent; background: transparent; border: none; border-radius: 8px 8px 0 0; min-height: 34px;
   padding: 0 6px 0 12px; box-shadow: none; margin-right: 1px; }
button.tab:hover { background-color: rgba(255,255,255,0.04); }
button.tab.active { background-color: #2C2C2C; }
button.tab label { font-size: 12px; }
button.tab-x { background: transparent; border: none; border-radius: 4px; min-width: 24px; min-height: 24px; padding: 0; box-shadow: none; }
button.tab-x:hover { background-color: rgba(255,255,255,0.08); }
button.tab-new { background: transparent; border: none; border-radius: 4px; min-width: 32px; min-height: 28px; padding: 0;
   box-shadow: none; margin-top: 4px; margin-left: 2px; }
button.tab-new:hover { background-color: rgba(255,255,255,0.06); }
.bar { background-color: #2C2C2C; padding: 4px 8px; }
.bar-bottom { border-bottom: 1px solid rgba(255,255,255,0.06); }
button.tb, button.nb { background: transparent; border: none; border-radius: 4px; min-height: 32px; padding: 0 9px; box-shadow: none; color: #ffffff; }
button.nb { min-width: 34px; padding: 0; }
button.tb:hover, button.nb:hover { background-color: rgba(255,255,255,0.06); }
button.tb:active, button.nb:active { background-color: rgba(255,255,255,0.04); }
button.tb:disabled label { color: rgba(255,255,255,0.36); }
button.tb label { font-size: 12px; }
button.tb.on, button.nb.on { background-color: rgba(255,255,255,0.09); }
.vsep { background-color: rgba(255,255,255,0.08); min-width: 1px; margin: 6px 6px; }
.status { background-color: #202020; padding: 4px 12px; border-top: 1px solid rgba(255,255,255,0.06); }
.status label { font-size: 12px; color: rgba(255,255,255,0.786); }
.sec { color: rgba(255,255,255,0.786); }
.ter { color: rgba(255,255,255,0.545); }
.big-title { font-size: 20px; font-weight: 600; }
.sect-title { font-size: 14px; font-weight: 600; }
entry.field, entry.fx-search { background-color: rgba(255,255,255,0.06); color: #ffffff; border: 1px solid rgba(255,255,255,0.07);
   border-bottom: 1px solid rgba(255,255,255,0.54); border-radius: 4px; min-height: 30px; padding: 0 10px; box-shadow: none;
   font-size: 12px; caret-color: #ffffff; }
entry.field:focus, entry.fx-search:focus { background-color: #1c1c1c; border-bottom: 2px solid #4CC2FF; }
entry selection, textview text selection, entry selection:focus, textview text selection:focus { background-color: #0078D4; color: #ffffff; }
scrollbar { background: transparent; border: none; }
scrollbar slider { background-color: rgba(255,255,255,0.45); border-radius: 6px; min-width: 3px; min-height: 3px; border: none; }
scrollbar:hover slider { min-width: 6px; min-height: 6px; background-color: rgba(255,255,255,0.55); }
scrollbar trough { background: transparent; border: none; }
scale trough { background-color: rgba(255,255,255,0.3); border: none; border-radius: 2px; min-height: 4px; min-width: 4px; }
scale highlight { background-color: #4CC2FF; border: none; border-radius: 2px; min-height: 4px; min-width: 4px; }
scale slider { background-color: #4CC2FF; border: 5px solid #454545; border-radius: 50%; min-width: 12px; min-height: 12px; box-shadow: none; }
scale slider:hover { border-width: 4px; }
menu, .menu, .context-menu { background-color: #2C2C2C; color: #ffffff; border: 1px solid rgba(0,0,0,0.45); border-radius: 8px; padding: 4px; }
menu menuitem { padding: 6px 12px; border-radius: 4px; color: #ffffff; min-height: 18px; }
menu menuitem:hover { background-color: rgba(255,255,255,0.06); }
menu menuitem:disabled label { color: rgba(255,255,255,0.36); }
menu menuitem label { color: #ffffff; font-size: 12px; }
menu menuitem arrow { color: rgba(255,255,255,0.786); }
menu separator { background-color: rgba(255,255,255,0.08); margin: 4px 0; min-height: 1px; }
window.fx button, window.fx-dialog button { background-image: none; text-shadow: none; -gtk-icon-shadow: none; }
button.primary { background-color: #4CC2FF; color: #000000; border: none; border-radius: 4px; min-height: 30px; padding: 0 16px; box-shadow: none; }
button.primary label { color: #000000; }
button.primary:hover { background-color: #48B1E8; }
button.secondary { background-color: rgba(255,255,255,0.06); color: #ffffff; border: 1px solid rgba(255,255,255,0.09); border-radius: 4px; min-height: 30px; padding: 0 16px; box-shadow: none; }
button.secondary:hover { background-color: rgba(255,255,255,0.09); }
.dlg-body { background-color: #2B2B2B; padding: 24px; }
.dlg-foot { background-color: #202020; padding: 22px 24px; border-top: 1px solid rgba(0,0,0,0.3); }
.dlg-title { font-size: 20px; font-weight: 600; }
.fx-dialog label { color: #ffffff; }
.fx-dialog label.sec { color: rgba(255,255,255,0.786); }
.fx-dialog label.ter { color: rgba(255,255,255,0.545); }
checkbutton check { background-color: rgba(0,0,0,0.1); border: 1px solid rgba(255,255,255,0.6); border-radius: 4px; min-width: 18px; min-height: 18px; -gtk-icon-source: none; color: #000000; }
checkbutton check:checked { background-color: #4CC2FF; border-color: #4CC2FF; -gtk-icon-source: -gtk-icontheme("object-select-symbolic"); }
checkbutton label { color: #ffffff; font-size: 12px; margin-left: 6px; }
radiobutton radio { background-color: rgba(0,0,0,0.1); border: 1px solid rgba(255,255,255,0.6); border-radius: 50%; min-width: 18px; min-height: 18px; -gtk-icon-source: none; }
radiobutton radio:checked { background-color: #000000; border: 5px solid #4CC2FF; }
radiobutton label { color: #ffffff; font-size: 12px; margin-left: 6px; }
switch { background-color: transparent; border: 1px solid rgba(255,255,255,0.6); border-radius: 12px; min-width: 40px; min-height: 18px; }
switch:checked { background-color: #4CC2FF; border-color: #4CC2FF; }
switch slider { background-color: rgba(255,255,255,0.8); border-radius: 50%; min-width: 12px; min-height: 12px; margin: 3px; border: none; box-shadow: none; }
switch:checked slider { background-color: #000000; }
switch image { color: transparent; }
combobox button, combobox box { background-color: rgba(255,255,255,0.06); color: #ffffff; border: 1px solid rgba(255,255,255,0.07); border-radius: 4px; box-shadow: none; min-height: 30px; }
combobox button cellview, combobox button label, combobox arrow { color: #ffffff; }
spinbutton { background-color: rgba(255,255,255,0.06); color: #ffffff; border: 1px solid rgba(255,255,255,0.07); border-radius: 4px; box-shadow: none; }
spinbutton entry { background: transparent; border: none; box-shadow: none; color: #ffffff; }
spinbutton button { background: transparent; border: none; box-shadow: none; color: #ffffff; }
tooltip, tooltip.background { background-color: #2C2C2C; border: 1px solid rgba(0,0,0,0.4); border-radius: 4px; }
tooltip label { color: #ffffff; font-size: 12px; }
.set-group { background-color: rgba(255,255,255,0.05); border-radius: 4px; border: 1px solid rgba(0,0,0,0.2); padding: 12px 16px; }
.set-head { font-size: 13px; }
.set-desc { font-size: 12px; color: rgba(255,255,255,0.6); }
"""


def apply_css(extra=""):
    prov = Gtk.CssProvider()
    prov.load_from_data((BASE_CSS + extra).encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10)
    Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)


def draw_glyph_extra(cr, name, L, pi):
    if name == "save":
        _rr(cr, 2, 2, 12, 12, 1.5)
        cr.stroke()
        _rr(cr, 4.5, 2, 6, 4, 0.5)
        cr.stroke()
        _rr(cr, 4.5, 9, 7, 5, 0.5)
        cr.stroke()
    elif name == "undo":
        cr.move_to(3, 7)
        cr.curve_to(6, 3.5, 13, 4.5, 13, 10)
        cr.stroke()
        L((3, 3), (3, 7), (7, 7))
    elif name == "redo":
        cr.move_to(13, 7)
        cr.curve_to(10, 3.5, 3, 4.5, 3, 10)
        cr.stroke()
        L((13, 3), (13, 7), (9, 7))
    elif name == "replace":
        L((2, 5), (10, 5))
        L((7.5, 2.5), (10, 5), (7.5, 7.5))
        L((14, 11), (6, 11))
        L((8.5, 8.5), (6, 11), (8.5, 13.5))
    elif name == "zoomin":
        cr.arc(6.6, 6.6, 4.6, 0, 2 * pi)
        cr.stroke()
        L((10, 10), (14, 14))
        L((4.6, 6.6), (8.6, 6.6))
        L((6.6, 4.6), (6.6, 8.6))
    elif name == "zoomout":
        cr.arc(6.6, 6.6, 4.6, 0, 2 * pi)
        cr.stroke()
        L((10, 10), (14, 14))
        L((4.6, 6.6), (8.6, 6.6))
    elif name == "fit":
        L((2, 5.5), (2, 2), (5.5, 2))
        L((10.5, 2), (14, 2), (14, 5.5))
        L((14, 10.5), (14, 14), (10.5, 14))
        L((5.5, 14), (2, 14), (2, 10.5))
    elif name == "wrap":
        L((2, 3), (14, 3))
        cr.move_to(2, 8)
        cr.line_to(11.5, 8)
        cr.curve_to(15, 8, 15, 13, 11.5, 13)
        cr.line_to(8, 13)
        cr.stroke()
        L((9.5, 11.3), (8, 13), (9.5, 14.7))
        L((2, 13), (5, 13))
    elif name == "play":
        cr.move_to(4.5, 2.5)
        cr.line_to(13, 8)
        cr.line_to(4.5, 13.5)
        cr.close_path()
        cr.fill()
    elif name == "pause":
        _rr(cr, 3.5, 2.5, 3, 11, 0.8)
        cr.fill()
        _rr(cr, 9.5, 2.5, 3, 11, 0.8)
        cr.fill()
    elif name in ("next", "prev"):
        if name == "prev":
            cr.translate(16, 0)
            cr.scale(-1, 1)
        cr.move_to(3, 3)
        cr.line_to(10.5, 8)
        cr.line_to(3, 13)
        cr.close_path()
        cr.fill()
        _rr(cr, 11, 3, 2, 10, 0.6)
        cr.fill()
    elif name == "shuffle":
        L((2, 4), (5, 4), (11, 12), (14, 12))
        L((2, 12), (5, 12), (11, 4), (14, 4))
        L((12, 2), (14, 4), (12, 6))
        L((12, 10), (14, 12), (12, 14))
    elif name in ("repeat", "repeat1"):
        cr.move_to(3, 9)
        cr.line_to(3, 6)
        cr.arc(5, 6, 2, pi, 1.5 * pi)
        cr.line_to(13, 4)
        cr.stroke()
        L((11, 2), (13, 4), (11, 6))
        cr.move_to(13, 7)
        cr.line_to(13, 10)
        cr.arc(11, 10, 2, 0, 0.5 * pi)
        cr.line_to(3, 12)
        cr.stroke()
        L((5, 10), (3, 12), (5, 14))
        if name == "repeat1":
            cr.set_font_size(5)
            cr.move_to(6.8, 9.8)
            cr.show_text("1")
    elif name in ("volume", "mute"):
        cr.move_to(1.5, 6)
        cr.line_to(4.5, 6)
        cr.line_to(8, 2.5)
        cr.line_to(8, 13.5)
        cr.line_to(4.5, 10)
        cr.line_to(1.5, 10)
        cr.close_path()
        cr.stroke()
        if name == "mute":
            L((10.5, 6), (14.5, 10))
            L((14.5, 6), (10.5, 10))
        else:
            cr.arc(8, 8, 3.5, -pi / 3.5, pi / 3.5)
            cr.stroke()
            cr.arc(8, 8, 6.2, -pi / 3.5, pi / 3.5)
            cr.stroke()
    elif name == "fullscreen":
        L((2, 6), (2, 2), (6, 2))
        L((10, 2), (14, 2), (14, 6))
        L((14, 10), (14, 14), (10, 14))
        L((6, 14), (2, 14), (2, 10))
        L((2, 2), (6, 6))
        L((14, 14), (10, 10))
    elif name == "unfullscreen":
        L((6, 2), (6, 6), (2, 6))
        L((10, 2), (10, 6), (14, 6))
        L((10, 14), (10, 10), (14, 10))
        L((6, 14), (6, 10), (2, 10))
    elif name == "rotate":
        cr.arc(8, 9, 5, pi * 1.15, pi * 2.85)
        cr.stroke()
        L((2.5, 2.5), (3.4, 6.4), (7.2, 5.4))
    elif name == "heart":
        cr.move_to(8, 13.5)
        cr.curve_to(1, 8, 1.5, 2.5, 5, 2.5)
        cr.curve_to(6.5, 2.5, 7.5, 3.5, 8, 4.5)
        cr.curve_to(8.5, 3.5, 9.5, 2.5, 11, 2.5)
        cr.curve_to(14.5, 2.5, 15, 8, 8, 13.5)
        cr.stroke()
    elif name == "pen":
        L((2.5, 13.5), (3.2, 10.5), (11, 2.7), (13.3, 5), (5.5, 12.8), (2.5, 13.5))
        L((9.5, 4.2), (11.8, 6.5))
    elif name == "highlighter":
        L((3, 13.5), (13, 13.5))
        cr.move_to(5, 11)
        cr.line_to(11, 3)
        cr.line_to(13.5, 5)
        cr.line_to(7.5, 12.5)
        cr.line_to(5, 12.5)
        cr.close_path()
        cr.stroke()
    elif name == "eraser":
        cr.move_to(2.5, 10)
        cr.line_to(9, 3.5)
        cr.line_to(13.5, 8)
        cr.line_to(8, 13.5)
        cr.line_to(5.5, 13.5)
        cr.close_path()
        cr.stroke()
        L((6, 6.5), (10.5, 11))
        L((8, 13.5), (14, 13.5))
    elif name == "crop":
        L((4.5, 1.5), (4.5, 11.5), (14.5, 11.5))
        L((1.5, 4.5), (11.5, 4.5), (11.5, 14.5))
    elif name == "camera":
        _rr(cr, 1.5, 4, 13, 9.5, 1.6)
        cr.stroke()
        L((5, 4), (6, 2.5), (10, 2.5), (11, 4))
        cr.arc(8, 8.8, 2.6, 0, 2 * pi)
        cr.stroke()
    elif name == "timer":
        cr.arc(8, 9, 5.5, 0, 2 * pi)
        cr.stroke()
        L((8, 9), (8, 5.8))
        L((6.3, 1.8), (9.7, 1.8))
    elif name == "settings":
        n = 8
        cr.new_path()
        for i in range(n * 2):
            a = i * pi / n
            r = 6.6 if i % 2 == 0 else 5.0
            a1, a2 = a - pi / (n * 2.4), a + pi / (n * 2.4)
            cr.line_to(8 + r * math.cos(a1), 8 + r * math.sin(a1))
            cr.line_to(8 + r * math.cos(a2), 8 + r * math.sin(a2))
        cr.close_path()
        cr.stroke()
        cr.arc(8, 8, 2.2, 0, 2 * pi)
        cr.stroke()
    elif name == "history":
        cr.arc(8, 8, 6, pi * 1.05, pi * 2.85)
        cr.stroke()
        L((1.2, 6.2), (2.3, 8.6), (4.6, 7.3))
        L((8, 4.6), (8, 8.2), (10.5, 9.7))
    elif name == "image":
        _rr(cr, 1.5, 2.5, 13, 11, 1.5)
        cr.stroke()
        L((1.5, 11), (5.5, 7), (9, 10.5), (11, 8.5), (14.5, 12))
        cr.arc(10.5, 5.5, 1.2, 0, 2 * pi)
        cr.stroke()
    elif name == "music":
        cr.arc(4.5, 12, 2, 0, 2 * pi)
        cr.stroke()
        cr.arc(12, 10.5, 2, 0, 2 * pi)
        cr.stroke()
        L((6.5, 12), (6.5, 3.5), (14, 2), (14, 10.5))
    elif name == "video":
        _rr(cr, 1.5, 3.5, 9.5, 9, 1.5)
        cr.stroke()
        L((11, 6.5), (14.5, 4.5), (14.5, 11.5), (11, 9.5))
    elif name == "queue":
        for y in (3, 7):
            L((2, y), (14, y))
        L((2, 11), (8, 11))
        cr.move_to(10.5, 9)
        cr.line_to(14, 11.5)
        cr.line_to(10.5, 14)
        cr.close_path()
        cr.fill()
    elif name == "edit":
        L((2.5, 13.5), (3.2, 10.5), (11, 2.7), (13.3, 5), (5.5, 12.8), (2.5, 13.5))
    elif name == "slideshow":
        _rr(cr, 1.5, 2.5, 13, 9, 1.5)
        cr.stroke()
        cr.move_to(6.5, 5)
        cr.line_to(10, 7)
        cr.line_to(6.5, 9)
        cr.close_path()
        cr.fill()
        L((5, 14), (11, 14))
    elif name == "print":
        _rr(cr, 1.5, 6, 13, 6, 1.2)
        cr.stroke()
        L((4.5, 6), (4.5, 1.5), (11.5, 1.5), (11.5, 6))
        _rr(cr, 4.5, 9.5, 7, 5, 0.5)
        cr.stroke()
    elif name == "wallpaper":
        _rr(cr, 1.5, 2.5, 13, 9, 1.2)
        cr.stroke()
        L((1.5, 9.5), (5, 6), (8, 9), (10, 7), (14.5, 10.5))
        L((5.5, 14), (10.5, 14))
        L((8, 11.5), (8, 14))
    elif name == "list":
        for y in (3.5, 8, 12.5):
            cr.arc(2.5, y, 0.9, 0, 2 * pi)
            cr.fill()
            L((5.5, y), (14, y))
    elif name == "add":
        L((8, 2.5), (8, 13.5))
        L((2.5, 8), (13.5, 8))
    elif name == "split":
        _rr(cr, 1.5, 2.5, 13, 11, 1.5)
        cr.stroke()
        L((8, 2.5), (8, 13.5))
    elif name == "keyboard":
        _rr(cr, 1, 3.5, 14, 9, 1.5)
        cr.stroke()
        for x in (4, 6.7, 9.3, 12):
            cr.rectangle(x - 0.5, 6, 1, 1)
        cr.fill()
        L((4.5, 10), (11.5, 10))


class Icon(Gtk.DrawingArea):
    """Monochrome glyph icon."""

    def __init__(self, name, size=16, color=None):
        super().__init__()
        self.name = name
        self.size = size
        self.color = color
        self.set_size_request(size, size)
        self.set_valign(Gtk.Align.CENTER)
        self.connect("draw", self._draw)

    def set_icon(self, name):
        self.name = name
        self.queue_draw()

    def _draw(self, w, cr):
        col = self.color or (1, 1, 1, 1)
        p = self.get_parent()
        if not self.is_sensitive() or (p and not p.is_sensitive()):
            col = (1, 1, 1, 0.36)
        draw_glyph(cr, self.name, self.size, col)


class WinTitlebar(Gtk.HeaderBar):
    """Title bar with Windows 11 caption buttons. Pack your own widgets with pack_start()."""

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.get_style_context().add_class("fx-title")
        self.set_show_close_button(False)
        self.set_custom_title(Gtk.Box())
        wc = Gtk.Box(spacing=0)
        wc.set_valign(Gtk.Align.START)
        for name, cb, extra in (("min", lambda *_: window.iconify(), ""),
                                ("max", lambda *_: self.toggle_max(), ""),
                                ("close", lambda *_: window.close(), "close")):
            b = Gtk.Button()
            b.get_style_context().add_class("wc")
            if extra:
                b.get_style_context().add_class(extra)
            ic = Icon(name, 10)
            b.add(ic)
            b.connect("clicked", cb)
            if name == "max":
                self.max_icon = ic
            wc.pack_start(b, False, False, 0)
        self.pack_end(wc)
        window.connect("window-state-event", self._wstate)
        window.set_titlebar(self)

    def toggle_max(self):
        if self.win.is_maximized():
            self.win.unmaximize()
        else:
            self.win.maximize()

    def _wstate(self, w, ev):
        maxed = bool(ev.new_window_state & Gdk.WindowState.MAXIMIZED)
        self.max_icon.set_icon("restore" if maxed else "max")
        return False


def app_title(text, logo_draw):
    """Little logo + app name for the left of the title bar."""
    box = Gtk.Box(spacing=8)
    box.set_margin_start(14)
    da = Gtk.DrawingArea()
    da.set_size_request(16, 16)
    da.set_valign(Gtk.Align.CENTER)
    da.connect("draw", lambda w, cr: logo_draw(cr, 16))
    box.pack_start(da, False, False, 0)
    lb = Gtk.Label(label=text)
    lb.get_style_context().add_class("app-title")
    box.pack_start(lb, False, False, 0)
    return box, lb


class JsonSettings(dict):
    def __init__(self, app_dir, defaults):
        super().__init__(defaults)
        self.dir = os.path.join(HOME, ".config", app_dir)
        self.file = os.path.join(self.dir, "settings.json")
        try:
            with open(self.file) as f:
                self.update(json.load(f))
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = self.file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self, f, indent=1)
            os.replace(tmp, self.file)
        except OSError:
            pass


def vsep():
    s = Gtk.Box()
    s.get_style_context().add_class("vsep")
    return s


def logo_pixbuf(draw, size):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    draw(cairo.Context(surf), size)
    return Gdk.pixbuf_get_from_surface(surf, 0, 0, size, size)
def label(text="", cls=None, xalign=0.0, ellipsize=False, wrap=False, markup=False):
    lb = Gtk.Label()
    if markup:
        lb.set_markup(text)
    else:
        lb.set_text(text)
    lb.set_xalign(xalign)
    if cls:
        for c in cls.split():
            lb.get_style_context().add_class(c)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if wrap:
        lb.set_line_wrap(True)
        lb.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return lb


def add_cls(w, *cls):
    ctx = w.get_style_context()
    for c in cls:
        ctx.add_class(c)
    return w


def tb_button(icon, text, cb=None, chev=False, tip=None):
    b = Gtk.Button()
    add_cls(b, "tb")
    box = Gtk.Box(spacing=7)
    if icon:
        box.pack_start(Icon(icon), False, False, 0)
    if text:
        box.pack_start(Gtk.Label(label=text), False, False, 0)
    if chev:
        box.pack_start(Icon("chevdown", 10), False, False, 0)
    b.add(box)
    b.set_relief(Gtk.ReliefStyle.NONE)
    b.set_tooltip_text(tip or text or None)
    if cb:
        b.connect("clicked", lambda w: cb(w))
    return b


def icon_button(icon, cb, cls="nb", tip=None, size=16):
    b = Gtk.Button()
    add_cls(b, cls)
    b.add(Icon(icon, size))
    b.set_relief(Gtk.ReliefStyle.NONE)
    if tip:
        b.set_tooltip_text(tip)
    b.connect("clicked", lambda w: cb(w))
    return b


def build_menu(spec):
    """spec: list of None (separator) or dicts: label, cb, icon, place, accel, sensitive, checked, sub."""
    menu = Gtk.Menu()
    add_cls(menu, "context-menu")
    for it in spec:
        if it is None:
            menu.append(Gtk.SeparatorMenuItem())
            continue
        mi = Gtk.MenuItem()
        box = Gtk.Box(spacing=12)
        ic = None
        if it.get("checked"):
            ic = Icon("check", 16)
        elif it.get("pixbuf") is not None:
            ic = Gtk.Image.new_from_pixbuf(it["pixbuf"])
        elif it.get("icon"):
            ic = Icon(it["icon"], 16)
        if ic is None:
            ic = Gtk.Box()
            ic.set_size_request(16, 16)
        box.pack_start(ic, False, False, 0)
        lb = Gtk.Label(label=it["label"])
        lb.set_xalign(0)
        box.pack_start(lb, True, True, 0)
        if it.get("accel"):
            al = Gtk.Label(label=it["accel"])
            al.get_style_context().add_class("dim-label")
            al.set_opacity(0.55)
            al.set_margin_start(24)
            box.pack_end(al, False, False, 0)
        mi.add(box)
        mi.set_sensitive(it.get("sensitive", True))
        if it.get("sub") is not None:
            mi.set_submenu(build_menu(it["sub"]))
        elif it.get("cb"):
            cb = it["cb"]
            mi.connect("activate", lambda w, cb=cb: GLib.idle_add(cb))
        menu.append(mi)
    menu.show_all()
    return menu


def popup_menu(menu, widget, event=None):
    menu.attach_to_widget(widget, None)
    if event is not None:
        menu.popup_at_pointer(event)
    else:
        menu.popup_at_widget(widget, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, None)


# ----------------------------------------------------------------------------
# Windows 11 style dialogs
# ----------------------------------------------------------------------------
class WinDialog(Gtk.Window):
    def __init__(self, parent, title, body=None, primary="OK", secondary="Cancel", width=440, extra=None,
                 markup=False):
        super().__init__(transient_for=parent, modal=True)
        add_cls(self, "fx-dialog")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(width, -1)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_title(title)
        self.cb = None
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        add_cls(self.body, "dlg-body")
        self.body.pack_start(label(title, "dlg-title"), False, False, 0)
        if body:
            lb = label(body, wrap=True, markup=markup)
            lb.set_max_width_chars(60)
            self.body.pack_start(lb, False, False, 0)
        if extra:
            self.body.pack_start(extra, False, False, 0)
        outer.pack_start(self.body, True, True, 0)
        self.foot = Gtk.Box(spacing=8, homogeneous=True)
        add_cls(self.foot, "dlg-foot")
        self.primary_btn = None
        if primary:
            pb = Gtk.Button(label=primary)
            add_cls(pb, "primary")
            pb.connect("clicked", lambda *_: self.done(True))
            self.foot.pack_start(pb, True, True, 0)
            pb.set_can_default(True)
            self.set_default(pb)
            self.primary_btn = pb
        if secondary:
            sb = Gtk.Button(label=secondary)
            add_cls(sb, "secondary")
            sb.connect("clicked", lambda *_: self.done(False))
            self.foot.pack_start(sb, True, True, 0)
        if primary or secondary:
            outer.pack_start(self.foot, False, False, 0)
        self.add(outer)
        self.connect("key-press-event", self._key)

    def _key(self, w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.done(False)
            return True
        return False

    def done(self, ok):
        cb = self.cb
        self.cb = None
        self.hide()
        if cb:
            cb(ok)
        self.destroy()

    def ask(self, cb=None):
        self.cb = cb
        self.show_all()
        if self.primary_btn:
            self.primary_btn.grab_focus()


def info_dialog(parent, title, body):
    WinDialog(parent, title, body, primary="OK", secondary=None).ask()


def confirm(parent, title, body, yes, cb, no="Cancel"):
    WinDialog(parent, title, body, primary=yes, secondary=no).ask(cb)


def error_list_dialog(parent, title, errors):
    lines = []
    for p, msg in errors[:12]:
        lines.append(f"{os.path.basename(p) or p}: {msg}" if p else msg)
    if len(errors) > 12:
        lines.append(f"...and {len(errors) - 12} more")
    info_dialog(parent, title, "\n".join(lines))




# ----------------------------------------------------------------------------
# Clipboard history (Win+V)
# ----------------------------------------------------------------------------
import hashlib  # noqa: E402
import fcntl  # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # noqa: E402
except (ValueError, ImportError):
    GtkLayerShell = None

APP_ID = "io.github.piclipboard"
DATA = os.path.join(HOME, ".local", "share", "pi-clipboard")
HIST = os.path.join(DATA, "history.json")
LOCK = os.path.join(DATA, ".lock")
MAX_ITEMS = 25
MAX_TEXT = 256 * 1024
MAX_IMAGE = 12 * 1024 * 1024
DEFAULTS = {"enabled": True, "paste": True}
PANEL_W = 360
PANEL_H = 480

CSS = """
window.clip-bg { background-color: transparent; }
.clip { background-color: rgba(36,36,36,0.985); border: 1px solid rgba(255,255,255,0.09); border-radius: 8px;
   box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
.clip label { color: #ffffff; }
.clip button, .flyout button { background-image: none; text-shadow: none; -gtk-icon-shadow: none; color: #ffffff; }
.clip-title { font-size: 14px; font-weight: 600; }
button.link { background: transparent; border: none; box-shadow: none; padding: 2px 8px; border-radius: 4px; min-height: 24px; }
button.link label { color: #4CC2FF; font-size: 12px; }
button.link:hover { background-color: rgba(255,255,255,0.06); }
button.card { background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px;
   padding: 0; box-shadow: none; outline-color: transparent; }
button.card:hover { background-color: rgba(255,255,255,0.08); }
button.card.sel { border: 2px solid #4CC2FF; }
.card-text { font-size: 12.5px; }
.card-meta { font-size: 11px; color: rgba(255,255,255,0.55); }
button.mini { background: transparent; border: none; box-shadow: none; border-radius: 4px; min-width: 28px; min-height: 28px; padding: 0; }
button.mini:hover { background-color: rgba(255,255,255,0.08); }
.empty-title { font-size: 14px; font-weight: 600; }
.empty-note { font-size: 12px; color: rgba(255,255,255,0.6); }
.flyout { background-color: #2C2C2C; border: 1px solid rgba(0,0,0,0.5); border-radius: 8px; padding: 4px;
   box-shadow: 0 6px 16px rgba(0,0,0,0.45); }
button.fly { background: transparent; border: none; border-radius: 4px; padding: 0 12px; min-height: 34px; box-shadow: none; }
button.fly:hover { background-color: rgba(255,255,255,0.06); }
button.fly label { font-size: 12px; }
.clip-foot { border-top: 1px solid rgba(255,255,255,0.06); padding: 6px 10px; }
.clip-foot label { font-size: 12px; color: rgba(255,255,255,0.6); }
"""


def draw_logo(cr, s):
    cr.save()
    cr.scale(s / 16.0, s / 16.0)
    g = cairo.LinearGradient(0, 0, 16, 16)
    g.add_color_stop_rgb(0, 0.33, 0.80, 1.0)
    g.add_color_stop_rgb(1, 0.0, 0.42, 0.85)
    _rr(cr, 2.5, 2.2, 11, 13, 2)
    cr.set_source(g)
    cr.fill()
    cr.set_source_rgb(0.93, 0.95, 0.98)
    _rr(cr, 5.2, 1, 5.6, 3, 1)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.95)
    cr.set_line_width(1.1)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for y in (7, 9.5, 12):
        cr.move_to(5, y)
        cr.line_to(11 if y != 12 else 9, y)
        cr.stroke()
    cr.restore()


# ---------------------------------------------------------------- history store
class Store:
    """history.json: newest first. Each item: {id, kind: text|image, text?, file?, time, pinned}"""

    @staticmethod
    def _lock():
        os.makedirs(DATA, exist_ok=True)
        f = open(LOCK, "w")
        fcntl.flock(f, fcntl.LOCK_EX)
        return f

    @staticmethod
    def load():
        try:
            with open(HIST) as f:
                items = json.load(f)
            return [i for i in items if i.get("kind") in ("text", "image")]
        except (OSError, ValueError):
            return []

    @staticmethod
    def save(items):
        os.makedirs(DATA, exist_ok=True)
        tmp = HIST + ".tmp"
        with open(tmp, "w") as f:
            json.dump(items, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, HIST)
        # remove image files nothing points at any more
        used = {i.get("file") for i in items}
        for n in os.listdir(DATA):
            if n.startswith("img-") and os.path.join(DATA, n) not in used:
                try:
                    os.remove(os.path.join(DATA, n))
                except OSError:
                    pass

    @classmethod
    def add(cls, kind, data):
        lk = cls._lock()
        try:
            items = cls.load()
            h = hashlib.sha1(data).hexdigest()[:16]
            old = next((i for i in items if i["id"] == h), None)
            if old:
                items.remove(old)
                old["time"] = time.time()
                items.insert(0, old)
            else:
                it = {"id": h, "kind": kind, "time": time.time(), "pinned": False}
                if kind == "text":
                    it["text"] = data.decode("utf-8", "replace")
                else:
                    path = os.path.join(DATA, f"img-{h}.png")
                    with open(path, "wb") as f:
                        f.write(data)
                    os.chmod(path, 0o600)
                    it["file"] = path
                items.insert(0, it)
            keep, n = [], 0
            for i in items:
                if i.get("pinned"):
                    keep.append(i)
                elif n < MAX_ITEMS:
                    keep.append(i)
                    n += 1
            cls.save(keep)
        finally:
            lk.close()

    @classmethod
    def change(cls, fn):
        lk = cls._lock()
        try:
            items = fn(cls.load())
            cls.save(items)
            return items
        finally:
            lk.close()


def store_from_stdin(kind):
    """Called by wl-paste --watch for every new copy."""
    st = JsonSettings("pi-clipboard", DEFAULTS)
    data = sys.stdin.buffer.read(MAX_IMAGE + 1)
    if not st.get("enabled", True) or not data or len(data) > MAX_IMAGE:
        return
    # skip passwords copied from password managers
    try:
        types = subprocess.run(["wl-paste", "--list-types"], capture_output=True, text=True, timeout=2).stdout
        if "x-kde-passwordManagerHint" in types:
            return
    except (OSError, subprocess.SubprocessError):
        pass
    if kind == "text":
        if len(data) > MAX_TEXT or not data.strip():
            return
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return
    elif not data.startswith(b"\x89PNG"):
        return
    Store.add(kind, data)


def ago(ts):
    d = time.time() - ts
    if d < 60:
        return "Just now"
    if d < 3600:
        return f"{int(d // 60)} min ago"
    if d < 86400:
        return f"{int(d // 3600)} hr ago"
    return time.strftime("%b %d", time.localtime(ts))


# ---------------------------------------------------------------- popup
class ClipWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.app = app
        self.st = app.settings
        self.items = []
        self.cards = []
        self.sel = 0
        self.fly = None
        self.shown_at = 0
        self.set_title("Clipboard")
        self.set_application(app)
        add_cls(self, "clip-bg")
        self.set_app_paintable(True)
        vis = self.get_screen().get_rgba_visual()
        if vis:
            self.set_visual(vis)
        self.demo_bg = None
        if os.environ.get("PI_DEMO_BG"):
            try:
                self.demo_bg = GdkPixbuf.Pixbuf.new_from_file(os.environ["PI_DEMO_BG"])
            except GLib.Error:
                pass
        self.connect("draw", self._draw_bg)
        self.layer = bool(GtkLayerShell and os.environ.get("WAYLAND_DISPLAY") and GtkLayerShell.is_supported())
        if self.layer:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "pi-clipboard")
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            for e in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                GtkLayerShell.set_anchor(self, e, True)
            try:
                GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            except AttributeError:
                GtkLayerShell.set_keyboard_interactivity(self, True)
        else:
            self.set_decorated(False)
            self.set_skip_taskbar_hint(True)
            self.set_skip_pager_hint(True)
            self.set_keep_above(True)
            self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
            self.connect("focus-out-event", self._focus_out)
        self.connect("key-press-event", self._key)
        self.connect("delete-event", lambda *a: (self.hide_popup(), True)[1])

        self.overlay = Gtk.Overlay()
        self.add(self.overlay)
        self.sink = Gtk.EventBox()
        self.sink.set_visible_window(False)
        self.sink.connect("button-press-event", self._sink_press)
        self.overlay.add(self.sink)
        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        add_cls(self.panel, "clip")
        self.panel.set_size_request(PANEL_W, PANEL_H)
        self.panel.set_halign(Gtk.Align.CENTER)
        self.panel.set_valign(Gtk.Align.CENTER)
        self.sink.add(self.panel)

        head = Gtk.Box()
        head.set_margin_start(16)
        head.set_margin_end(10)
        head.set_margin_top(14)
        head.set_margin_bottom(8)
        head.pack_start(label("Clipboard", "clip-title"), False, False, 0)
        self.clear_btn = Gtk.Button()
        add_cls(self.clear_btn, "link")
        self.clear_btn.add(Gtk.Label(label="Clear all"))
        self.clear_btn.connect("clicked", lambda w: self.clear_all())
        head.pack_end(self.clear_btn, False, False, 0)
        self.panel.pack_start(head, False, False, 0)

        self.stack = Gtk.Stack()
        self.sw = Gtk.ScrolledWindow()
        self.sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.list.set_margin_start(12)
        self.list.set_margin_end(12)
        self.list.set_margin_bottom(12)
        self.sw.add(self.list)
        self.stack.add_named(self.sw, "list")
        self.empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.empty.set_valign(Gtk.Align.CENTER)
        self.empty.set_margin_start(24)
        self.empty.set_margin_end(24)
        self.empty_title = label("", "empty-title", xalign=0.5, wrap=True)
        self.empty_note = label("", "empty-note", xalign=0.5, wrap=True)
        self.empty_note.set_justify(Gtk.Justification.CENTER)
        self.empty.pack_start(self.empty_title, False, False, 0)
        self.empty.pack_start(self.empty_note, False, False, 0)
        self.turn_on = Gtk.Button(label="Turn on")
        add_cls(self.turn_on, "primary")
        self.turn_on.set_halign(Gtk.Align.CENTER)
        self.turn_on.set_margin_top(10)
        self.turn_on.connect("clicked", lambda w: self.set_enabled(True))
        self.empty.pack_start(self.turn_on, False, False, 0)
        self.stack.add_named(self.empty, "empty")
        self.panel.pack_start(self.stack, True, True, 0)

        foot = Gtk.Box(spacing=8)
        add_cls(foot, "clip-foot")
        foot.pack_start(label("Click an item to paste it", "empty-note"), False, False, 0)
        gear = Gtk.Button()
        add_cls(gear, "mini")
        gear.add(Icon("more", 16))
        gear.set_tooltip_text("Clipboard settings")
        gear.connect("clicked", lambda w: self.settings_fly(w))
        foot.pack_end(gear, False, False, 0)
        self.panel.pack_end(foot, False, False, 0)
        self.overlay.show_all()

    def _draw_bg(self, w, cr):
        if self.demo_bg is not None:
            a = w.get_allocation()
            Gdk.cairo_set_source_pixbuf(cr, self.demo_bg.scale_simple(a.width, a.height, GdkPixbuf.InterpType.BILINEAR), 0, 0)
            cr.paint()
            return False
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        return False

    # ---- content
    def refresh(self):
        self.close_fly()
        self.items = Store.load()
        for c in self.list.get_children():
            self.list.remove(c)
        self.cards = []
        if not self.st.get("enabled", True):
            self.empty_title.set_text("Clipboard history is off")
            self.empty_note.set_text("Turn it on to keep the last 25 things you copy, so you can paste them again later.")
            self.turn_on.show()
            self.stack.set_visible_child_name("empty")
            self.clear_btn.set_sensitive(False)
            return
        self.turn_on.hide()
        if not self.items:
            self.empty_title.set_text("Nothing copied yet")
            self.empty_note.set_text("Copy text or a picture and it will show up here. Press Super+V any time to paste it again.")
            self.stack.set_visible_child_name("empty")
            self.clear_btn.set_sensitive(False)
            return
        self.clear_btn.set_sensitive(any(not i.get("pinned") for i in self.items))
        for it in self.items:
            self.cards.append(self._card(it))
            self.list.pack_start(self.cards[-1], False, False, 0)
        self.list.show_all()
        self.stack.set_visible_child_name("list")
        self.sel = 0
        self._mark()

    def _card(self, it):
        b = Gtk.Button()
        add_cls(b, "card")
        row = Gtk.Box(spacing=4)
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        v.set_margin_start(12)
        v.set_margin_top(10)
        v.set_margin_bottom(10)
        if it["kind"] == "text":
            txt = it["text"].strip("\n")
            lines = txt.splitlines()
            short = "\n".join(lines[:4])[:400]
            lb = label(short, "card-text", wrap=True)
            lb.set_lines(4)
            lb.set_ellipsize(Pango.EllipsizeMode.END)
            lb.set_max_width_chars(36)
            v.pack_start(lb, False, False, 0)
            meta = ago(it["time"])
            if len(lines) > 4 or len(txt) > 400:
                meta += f"  |  {len(txt)} characters"
        else:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(it["file"], 280, 130, True)
                img = Gtk.Image.new_from_pixbuf(pb)
                img.set_halign(Gtk.Align.START)
                v.pack_start(img, False, False, 0)
                full = GdkPixbuf.Pixbuf.get_file_info(it["file"])
                meta = ago(it["time"]) + (f"  |  {full[1]} x {full[2]}" if full and full[0] else "")
            except (GLib.Error, TypeError):
                v.pack_start(label("(picture)", "card-text"), False, False, 0)
                meta = ago(it["time"])
        v.pack_start(label(meta, "card-meta"), False, False, 0)
        row.pack_start(v, True, True, 0)
        side = Gtk.Box()
        side.set_size_request(30, -1)
        if it.get("pinned"):
            pin = Icon("pin-fill", 14)
            pin.set_valign(Gtk.Align.END)
            pin.set_margin_bottom(10)
            pin.set_tooltip_text("Pinned")
            side.pack_start(pin, True, False, 0)
        row.pack_start(side, False, False, 0)
        b.add(row)
        b.connect("clicked", lambda w, it=it: self.choose(it))
        # the "..." button sits on top of the card (not inside it) so clicking it doesn't paste
        ov = Gtk.Overlay()
        ov.add(b)
        mb = Gtk.Button()
        add_cls(mb, "mini")
        mb.add(Icon("more", 16))
        mb.set_tooltip_text("More")
        mb.set_halign(Gtk.Align.END)
        mb.set_valign(Gtk.Align.START)
        mb.set_margin_top(5)
        mb.set_margin_end(5)
        mb.connect("clicked", lambda w, it=it: self.item_fly(w, it))
        ov.add_overlay(mb)
        ov.card = b
        return ov

    def _mark(self):
        for i, c in enumerate(self.cards):
            ctx = c.card.get_style_context()
            if i == self.sel:
                ctx.add_class("sel")
            else:
                ctx.remove_class("sel")
        if self.cards:
            c = self.cards[self.sel]

            def scroll():
                a = c.get_allocation()
                adj = self.sw.get_vadjustment()
                if a.y < adj.get_value():
                    adj.set_value(a.y)
                elif a.y + a.height > adj.get_value() + adj.get_page_size():
                    adj.set_value(a.y + a.height - adj.get_page_size())
                return False
            GLib.idle_add(scroll)

    # ---- actions
    def choose(self, it):
        self.hide_popup()
        if it["kind"] == "text":
            self.app.set_clipboard_text(it["text"])
        else:
            self.app.set_clipboard_image(it["file"])
        if self.st.get("paste", True):
            GLib.timeout_add(220, self.app.paste_keys)

    def delete(self, it):
        Store.change(lambda items: [i for i in items if i["id"] != it["id"]])
        self.refresh()

    def toggle_pin(self, it):
        def fn(items):
            for i in items:
                if i["id"] == it["id"]:
                    i["pinned"] = not i.get("pinned")
            return items
        Store.change(fn)
        self.refresh()

    def clear_all(self):
        Store.change(lambda items: [i for i in items if i.get("pinned")])
        self.refresh()

    def set_enabled(self, on):
        self.st["enabled"] = on
        self.st.save()
        if not on:
            Store.change(lambda items: [i for i in items if i.get("pinned")])
        self.refresh()

    # ---- flyouts
    def open_fly(self, widget, items):
        self.close_fly()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        add_cls(box, "flyout")
        box.set_size_request(190, -1)
        for ic, text, cb in items:
            b = Gtk.Button()
            add_cls(b, "fly")
            h = Gtk.Box(spacing=12)
            h.pack_start(Icon(ic, 16), False, False, 0)
            h.pack_start(label(text), True, True, 0)
            b.add(h)
            b.connect("clicked", lambda w, cb=cb: (self.close_fly(), cb()))
            box.pack_start(b, False, False, 0)
        box.set_halign(Gtk.Align.START)
        box.set_valign(Gtk.Align.START)
        self.overlay.add_overlay(box)
        box.show_all()
        _, nat = box.get_preferred_size()
        x, y = widget.translate_coordinates(self.overlay, 0, 0)
        a = widget.get_allocation()
        oh = self.overlay.get_allocated_height()
        fy = y + a.height + 4
        if fy + nat.height > oh - 8:
            fy = y - nat.height - 4
        box.set_margin_start(max(0, x + a.width - nat.width))
        box.set_margin_top(max(0, fy))
        self.fly = box

    def close_fly(self):
        if self.fly is not None:
            self.fly.destroy()
            self.fly = None
            return True
        return False

    def item_fly(self, w, it):
        self.open_fly(w, [("delete", "Delete", lambda: self.delete(it)),
                          ("pin", "Unpin" if it.get("pinned") else "Pin", lambda: self.toggle_pin(it))])

    def settings_fly(self, w):
        on = self.st.get("enabled", True)
        paste = self.st.get("paste", True)
        self.open_fly(w, [
            ("check" if paste else "blank", "Paste when I pick an item", lambda: self._set("paste", not paste)),
            ("check" if on else "blank", "Clipboard history on", lambda: self.set_enabled(not on)),
        ])

    def _set(self, k, v):
        self.st[k] = v
        self.st.save()

    # ---- show / hide
    def show_popup(self):
        self.refresh()
        self.shown_at = time.time()
        if not self.layer:
            disp = Gdk.Display.get_default()
            mon = disp.get_primary_monitor() or disp.get_monitor(0)
            geo = mon.get_workarea()
            self.move(geo.x, geo.y)
            self.resize(geo.width, geo.height)
        self.show()
        self.present()
        if self.cards:
            self.cards[0].card.grab_focus()

    def hide_popup(self):
        self.close_fly()
        self.hide()

    def toggle(self):
        if self.get_visible():
            self.hide_popup()
        else:
            self.show_popup()

    def _focus_out(self, *a):
        if time.time() - self.shown_at > 0.4 and not os.environ.get("PI_DEMO_BG"):
            self.hide_popup()
        return False

    def _sink_press(self, w, ev):
        if self.close_fly():
            return True
        # clicks inside a child that has its own window (lists, expanders) are inside the panel
        if ev.window != self.get_window():
            return False
        a = self.panel.get_allocation()
        if not (a.x <= ev.x <= a.x + a.width and a.y <= ev.y <= a.y + a.height):
            self.hide_popup()
            return True
        return False

    def _key(self, w, ev):
        k = ev.keyval
        if k == Gdk.KEY_Escape:
            if not self.close_fly():
                self.hide_popup()
            return True
        if not self.cards:
            return False
        if k in (Gdk.KEY_Down, Gdk.KEY_Up):
            self.sel = max(0, min(len(self.cards) - 1, self.sel + (1 if k == Gdk.KEY_Down else -1)))
            self._mark()
            self.cards[self.sel].card.grab_focus()
            return True
        if k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self.choose(self.items[self.sel])
            return True
        if k == Gdk.KEY_Delete:
            self.delete(self.items[self.sel])
            return True
        return False


# ---------------------------------------------------------------- app
class ClipApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.win = None
        self.watchers = []
        self.x11_last = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.settings = JsonSettings("pi-clipboard", DEFAULTS)
        apply_css(CSS)
        self.hold()
        self.start_watch()

    # ---- watching the clipboard
    def start_watch(self):
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
            me = shutil.which("pi-clipboard") or os.path.abspath(sys.argv[0])
            for kind, args in (("text", ["--type", "text"]), ("image", ["--type", "image/png"])):
                self._spawn_watcher(me, kind, args)
        else:
            cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            cb.connect("owner-change", self._x11_change)

    def _spawn_watcher(self, me, kind, args):
        cmd = ["wl-paste"] + args + ["--watch", me, "--store", kind] if me.endswith("pi-clipboard") else \
            ["wl-paste"] + args + ["--watch", sys.executable, me, "--store", kind]
        def die_with_parent():
            try:
                import ctypes
                ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)
            except (OSError, AttributeError):
                pass
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=die_with_parent)
        except OSError:
            return
        self.watchers.append(p)
        # restart the watcher if it ever stops
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, p.pid,
                             lambda pid, st: GLib.timeout_add_seconds(2, lambda: (self._spawn_watcher(me, kind, args), False)[1]))

    def _x11_change(self, cb, ev):
        if not self.settings.get("enabled", True):
            return
        cb.request_text(self._x11_text)

    def _x11_text(self, cb, text):
        if text:
            data = text.encode("utf-8")
            if data != self.x11_last and len(data) <= MAX_TEXT:
                self.x11_last = data
                Store.add("text", data)
            return
        cb.request_image(self._x11_image)

    def _x11_image(self, cb, pb):
        if pb is None:
            return
        ok, buf = pb.save_to_bufferv("png", [], [])
        if ok and buf != self.x11_last and len(buf) <= MAX_IMAGE:
            self.x11_last = bytes(buf)
            Store.add("image", bytes(buf))

    # ---- putting things back on the clipboard
    def set_clipboard_text(self, text):
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
            try:
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, start_new_session=True)
                p.stdin.write(text.encode("utf-8"))
                p.stdin.close()
                return
            except OSError:
                pass
        cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        cb.set_text(text, -1)
        cb.store()

    def set_clipboard_image(self, path):
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
            try:
                with open(path, "rb") as f:
                    subprocess.Popen(["wl-copy", "--type", "image/png"], stdin=f, start_new_session=True)
                return
            except OSError:
                pass
        try:
            cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            cb.set_image(GdkPixbuf.Pixbuf.new_from_file(path))
            cb.store()
        except GLib.Error:
            pass

    def paste_keys(self):
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wtype"):
            subprocess.Popen(["wtype", "-M", "ctrl", "v", "-m", "ctrl"], start_new_session=True)
        elif shutil.which("xdotool") and os.environ.get("DISPLAY"):
            subprocess.Popen(["xdotool", "key", "--clearmodifiers", "ctrl+v"], start_new_session=True)
        return False

    def do_command_line(self, cmd):
        args = cmd.get_arguments()[1:]
        if "--quit" in args:
            for p in self.watchers:
                try:
                    p.terminate()
                except OSError:
                    pass
            self.quit()
            return 0
        if self.win is None:
            self.win = ClipWindow(self)
        if "--daemon" in args or "--background" in args:
            return 0
        self.win.toggle()
        return 0


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--store":
        store_from_stdin(sys.argv[2])
        return 0
    GLib.set_prgname("pi-clipboard")
    GLib.set_application_name("Clipboard")
    app = ClipApp()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, lambda *a: (app.quit(), [p.terminate() for p in app.watchers]))
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
