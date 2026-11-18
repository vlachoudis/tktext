"""Window decorations: close button ✕ (the window manager's), Alt-F4 and
the reversed window titles."""
import curses
import unittest

from fakescreen import makeApp, attach, click, tk
from tktext._events import ModKey, STATE_ALT, STATE_CONTROL, isAltF4

ALT_F4 = ModKey(curses.KEY_F1 + 3, STATE_ALT)


class CloseButtonTest(unittest.TestCase):

	def setUp(self):
		self.root, self.scr = makeApp(60, 20)
		attach(self.root)

	def redraw(self):
		self.root.update()
		self.root._redraw()

	def test_title_bar_shows_the_close_button(self):
		self.redraw()
		self.assertTrue(self.scr.row(0).endswith(' ✕ '))

	def test_click_closes_a_maximised_toplevel(self):
		top = tk.Toplevel(self.root)
		top.title('Help')
		tk.Text(top).pack()
		self.redraw()
		self.assertIn('Help', self.scr.row(0))
		click(self.root, 58, 0, 'press')
		self.assertFalse(top._destroyed)	# acts on the release
		click(self.root, 58, 0, 'release')
		self.assertTrue(top._destroyed)

	def test_release_elsewhere_does_not_close(self):
		top = tk.Toplevel(self.root)
		self.redraw()
		click(self.root, 58, 0, 'press')
		click(self.root, 20, 5, 'release')
		self.assertFalse(top._destroyed)

	def test_framed_dialog_and_protocol_handler(self):
		dlg = tk.Toplevel(self.root)
		dlg.title('Dlg')
		dlg.transient(self.root)
		tk.Label(dlg, text='a dialog with some text').pack()
		called = []
		dlg.protocol('WM_DELETE_WINDOW', lambda: called.append(1))
		self.redraw()
		x, y = dlg._closeCell()
		self.assertEqual(self.scr.row(y)[x], '✕')
		click(self.root, x, y)
		self.assertEqual(called, [1])
		self.assertFalse(dlg._destroyed)	# the handler decides

	def test_root_close_quits(self):
		self.redraw()
		click(self.root, 58, 0)
		self.assertTrue(self.root._quit)

	def test_grab_blocks_other_windows(self):
		dlg = tk.Toplevel(self.root)
		dlg.transient(self.root)
		tk.Label(dlg, text='modal dialog box').pack()
		dlg.grab_set()
		self.redraw()
		click(self.root, 58, 0)
		self.assertFalse(self.root._quit)
		x, y = dlg._closeCell()
		click(self.root, x, y)
		self.assertTrue(dlg._destroyed)


class AltF4Test(unittest.TestCase):

	def test_alt_f4_codes(self):
		self.assertTrue(isAltF4(ALT_F4))
		self.assertTrue(isAltF4(curses.KEY_F0 + 52))
		self.assertFalse(isAltF4(curses.KEY_F1 + 3))
		self.assertFalse(isAltF4(ModKey(curses.KEY_F1 + 3, STATE_ALT | STATE_CONTROL)))

	def test_alt_f4_wins_over_application_bindings(self):
		root, scr = makeApp()
		top = tk.Toplevel(root)
		t = tk.Text(top)
		t.pack()
		attach(root)
		t.focus_set()
		seen = []
		t.bind('<Key>', lambda e: seen.append(e.keysym) or 'break')
		root._onKey(ALT_F4)
		root.update()
		self.assertTrue(top._destroyed)
		self.assertEqual(seen, [])


class TitleColourTest(unittest.TestCase):

	def test_titles_are_reversed(self):
		from tktext import _colors
		fg, bg, attrs = _colors.getTheme('titlebar.title')
		bfg, bbg, battrs = _colors.getTheme('titlebar')
		self.assertEqual((fg, bg), (bbg, bfg))		# title bar: colours swapped
		root, scr = makeApp(60, 20)
		dlg = tk.Toplevel(root)
		dlg.title('Dlg')
		dlg.transient(root)
		tk.Label(dlg, text='a dialog with some text').pack()
		attach(root)
		root._redraw()
		y, x = scr.find('Dlg')
		self.assertTrue(scr.attrs[y][x] & curses.A_REVERSE)	# dialog frame title
		self.assertFalse(scr.attrs[y][dlg._x + 1] & curses.A_REVERSE)


if __name__ == '__main__':
	unittest.main()
