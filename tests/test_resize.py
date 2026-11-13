"""Keyboard resizing: Treeview column widths in pixel mode and flair's
tkResize (F8 resize mode) running on tktext."""
import os
import subprocess
import sys
import unittest

from fakescreen import makeApp
from tktext import _core, ttk

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS     = os.path.join(ROOT, 'tests')
FLAIRLIB  = os.path.join(ROOT, 'flair', 'lib')


class TreeviewColumnPixelsTest(unittest.TestCase):

	def tearDown(self):
		_core.setPixelMode(1, 1)

	def test_column_width_reported_in_pixels(self):
		_core.setPixelMode(8, 16)
		root, scr = makeApp()
		tv = ttk.Treeview(root, columns=('a',))
		tv.column('a', width=80, minwidth=16)
		self.assertEqual(tv.column('a', 'width'), 80)
		self.assertEqual(tv.column('a')['minwidth'], 16)
		self.assertEqual(tv._colCfg['a']['width'], 10)		# cells inside
		tv.column('a', width=tv.column('a', 'width') + 8)
		self.assertEqual(tv.column('a', 'width'), 88)

	def test_column_width_native_cells(self):
		root, scr = makeApp()
		tv = ttk.Treeview(root, columns=('a',))
		tv.column('a', width=7)
		self.assertEqual(tv.column('a', 'width'), 7)


# Runs in a subprocess: install() replaces tkinter for the whole process
_SCRIPT = r'''
import sys, curses
sys.path[:0] = [ROOT, TESTS, FLAIRLIB]
import tktext; tktext.install()
import tkinter as tk
from tkinter import ttk
from fakescreen import makeApp, attach, press
import tkExtra, tkResize

F8 = curses.KEY_F8
root, scr = makeApp(100, 30)
root.geometry('800x480')
tkResize.bindResize(root)

# --- tk.PanedWindow: F8, Right x2, Escape restores, focus comes back
pw = tk.PanedWindow(root, orient=tk.HORIZONTAL)
pw.pack(fill=tk.BOTH, expand=True)
left  = tk.Frame(pw); pw.add(left, width=200)
right = tk.Frame(pw); pw.add(right)
ent   = tk.Entry(left); ent.pack()
attach(root)
ent.focus_set(); root.update()
x0 = pw.sash_coord(0)[0]
press(root, F8, curses.KEY_RIGHT, curses.KEY_RIGHT)
assert tkResize.ResizeMode.active is not None
assert pw.sash_coord(0)[0] == x0 + 16, (x0, pw.sash_coord(0))
press(root, 27)
assert pw.sash_coord(0)[0] == x0
assert tkResize.ResizeMode.active is None
assert root.focus_get() is ent, root.focus_get()

# Return keeps the new position; Shift+Right is a big step
press(root, F8, tktext._events.KEY_SHIFT_RIGHT, 10)
assert pw.sash_coord(0)[0] == x0 + 8*tkResize.BIGSTEP, pw.sash_coord(0)
assert root.focus_get() is ent

# vim keys: h/l move like Left/Right, L is a big step, Escape restores
x1 = pw.sash_coord(0)[0]
press(root, F8, ord('l'), ord('l'), ord('h'))
assert pw.sash_coord(0)[0] == x1 + 8, (x1, pw.sash_coord(0))
press(root, ord('L'))
assert pw.sash_coord(0)[0] == x1 + 8 + 8*tkResize.BIGSTEP, pw.sash_coord(0)
press(root, 27)
assert pw.sash_coord(0)[0] == x1 and root.focus_get() is ent

# --- MultiListbox inside the right pane: following columns shift along
mlb = tkExtra.MultiListbox(right, (("A", 8, None), ("B", 8, None), ("C", 8, None)))
mlb.pack(fill=tk.BOTH, expand=True)
root.update()
mlb._lists[1].focus_set(); root.update()
before = [mlb.paneframe.sash_coord(i)[0] for i in range(2)]
dividers = tkResize.resizeTargets(mlb._lists[1])
assert dividers[0].name == "column B", dividers
press(root, F8, curses.KEY_RIGHT, 10)
after = [mlb.paneframe.sash_coord(i)[0] for i in range(2)]
assert after == [before[0], before[1] + 8], (before, after)
# the outer PanedWindow comes after the columns; the inner pane is skipped
assert isinstance(dividers[-1], tkResize.PanedDivider) and dividers[-1].widget is pw
assert all(d.widget is not mlb.paneframe for d in dividers)

# --- Tab cycles to the next divider (column C has no right border: A)
press(root, F8, 9, curses.KEY_LEFT, 10)
assert mlb.paneframe.sash_coord(0)[0] == before[0] - 8

# --- Treeview: column widths, Tab walks the columns
top = tk.Toplevel(root)
tkResize.bindResize(top)
tv  = ttk.Treeview(top, columns=("size", "date"))
tv.heading("size", text="Size")
tv.column("#0", width=160); tv.column("size", width=80); tv.column("date", width=80)
tv.pack(fill=tk.BOTH, expand=True)
root.update()
tv.focus_set(); root.update()
# Right on #0 (size gives the width), Tab to size, Left x2 (date takes it)
press(root, F8, curses.KEY_RIGHT, 9, curses.KEY_LEFT, curses.KEY_LEFT, 10)
widths = [tv.column(c, "width") for c in ("#0", "size", "date")]
assert widths == [168, 56, 96], widths
# Escape restores both columns
press(root, F8, curses.KEY_RIGHT, 27)
assert [tv.column(c, "width") for c in ("#0", "size", "date")] == widths
top.destroy(); root.update()

# --- Treeview without headings (flair PlotPage tree: show="tree" and a
#     hidden fixed column): the arrows move the PanedWindow sash
for w in root.winfo_children(): w.destroy()
pw2 = tk.PanedWindow(root, orient=tk.HORIZONTAL)
pw2.pack(fill=tk.BOTH, expand=True)
fr2 = ttk.Frame(pw2); pw2.add(fr2, width=240)
tv2 = ttk.Treeview(fr2, show="tree", columns=("plot",))
tv2.column("plot", width=24, stretch=tk.NO)
tv2.pack(fill=tk.BOTH, expand=True)
pw2.add(tk.Frame(pw2))
root.update(); tv2.focus_set(); root.update()
x2 = pw2.sash_coord(0)[0]
press(root, F8, curses.KEY_RIGHT, curses.KEY_RIGHT, 10)
assert pw2.sash_coord(0)[0] == x2 + 16, (x2, pw2.sash_coord(0))

# --- nested tkExtra.PanedWindows: Up/Down move the vertical, Left/Right
#     the horizontal; the relative one keeps the new fraction
for w in root.winfo_children(): w.destroy()
hs = tkExtra.PanedWindow(root, tk.HORIZONTAL, relative=True)
hs.pack(fill=tk.BOTH, expand=True)
hs.addFrame()
vs = tkExtra.PanedWindow(hs, tk.VERTICAL)
hs.add(vs)
top2 = vs.addFrame(); vs.addFrame()
hs.split(0.5); vs.split(160)
e2 = tk.Entry(top2); e2.pack()
root.update(); e2.focus_set(); root.update()
h0, v0 = hs.split(), vs.split()
assert tkResize.resizeFocus(e2, 0, 1)
root.update()
assert vs.split() == v0 + 16 and hs.split() == h0, (v0, vs.split(), h0, hs.split())
assert tkResize.resizeFocus(e2, -1, 0)
root.update()
assert hs.split() < h0 and vs.split() == v0 + 16, (h0, hs.split())

# --- InputPage tabs: the tab of the edited field, all tabs when not editing
import types
sys.path.insert(0, FLAIRLIB.rsplit("/", 1)[0])
import InputPage
F  = InputPage.InputEditorFrame
for w in root.winfo_children(): w.destroy()
ed = tk.Text(root); ed.pack(); root.update()
ed.insert("1.0", " #define\t\tname\t\tvalue\t\n\tlbl:\t5\t\t7\t\n")
ed._tabs = [90, 240, 390, 540]; ed.edit = None
ed.setTabs = lambda: None; ed.edit_range = lambda i: ()
fr = types.SimpleNamespace(editor=ed, tabs=[0]*4, placeTabs=lambda: None)
for m in ("moveTab", "editTabIndex"):
	setattr(fr, m, getattr(F, m).__get__(fr))
names = [d.name for d in F.resizeDividers(fr, ed)]
assert names[0] == "all tabs", names
ed.edit = 0
for idx, tab in (("1.3", 0), ("1.10", 1), ("1.16", 2), ("2.6", 1), ("2.9", 2)):
	ed.mark_set("insert", idx)
	assert F.editTabIndex(fr) == tab, (idx, F.editTabIndex(fr), tab)
ed.mark_set("insert", "1.16")
assert F.resizeDividers(fr, ed)[0].name == "tab 3"
ed.edit = None
allTabs = F.resizeDividers(fr, ed)[0]
allTabs.move(8)
assert ed._tabs == [98, 256, 414, 572], ed._tabs
allTabs.move(-200)		# would hide columns: refused
assert ed._tabs == [98, 256, 414, 572], ed._tabs

# --- no divider: F8 does nothing and the focus stays
for w in root.winfo_children(): w.destroy()
e3 = tk.Entry(root); e3.pack(); root.update(); e3.focus_set(); root.update()
press(root, F8)
assert tkResize.ResizeMode.active is None and root.focus_get() is e3
print("RESIZE-OK")
'''


@unittest.skipUnless(os.path.isfile(os.path.join(FLAIRLIB, 'tkResize.py')),
	'needs a flair checkout in flair/')
class FlairResizeTest(unittest.TestCase):

	def test_resize_mode(self):
		script = f'ROOT, TESTS, FLAIRLIB = {ROOT!r}, {TESTS!r}, {FLAIRLIB!r}\n' + _SCRIPT
		out = subprocess.run([sys.executable, '-c', script],
			capture_output=True, text=True, timeout=60)
		self.assertIn('RESIZE-OK', out.stdout, out.stdout + out.stderr)


if __name__ == '__main__':
	unittest.main()
