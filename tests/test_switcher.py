"""Window switch of the maximised windows: ◀ ▶ ▾ on the title bar and
Ctrl-F6 / Ctrl-Shift-F6."""
import curses
import unittest

from fakescreen import makeApp, attach, click, press, tk
from tktext._events import ModKey, STATE_CONTROL, STATE_SHIFT, STATE_ALT, \
	KEY_ENTER, ctrlF6Step

CTRL_F6		= ModKey(curses.KEY_F1 + 5, STATE_CONTROL)
CTRL_SHIFT_F6	= ModKey(curses.KEY_F1 + 5, STATE_CONTROL | STATE_SHIFT)

# 60 columns: ◀ 48-50, ▶ 51-53, ▾ 54-56, ✕ 57-59
PREV	= 49
NEXT	= 52
LIST	= 55


class SwitcherTest(unittest.TestCase):

	def setUp(self):
		self.root, self.scr = makeApp(60, 20)
		self.root.title('Main')
		self.entry = tk.Entry(self.root)
		self.entry.pack()
		attach(self.root)

	def redraw(self):
		self.root.update()
		self.root._redraw()

	def toplevel(self, title):
		top = tk.Toplevel(self.root)
		top.title(title)
		entry = tk.Entry(top)
		entry.pack()
		self.redraw()
		return top, entry

	def front(self):
		"""Title shown on row 0."""
		return self.scr.row(0)[:48].strip()

	def test_no_buttons_with_one_window(self):
		self.redraw()
		self.assertNotIn('◀', self.scr.row(0))
		self.assertTrue(self.scr.row(0).endswith(' ✕ '))

	def test_buttons_left_of_close(self):
		self.toplevel('Help')
		self.assertTrue(self.scr.row(0).endswith(' ◀  ▶  ▾  ✕ '))

	def test_next_brings_back_the_root(self):
		top, entry = self.toplevel('Help')
		self.assertEqual(self.front(), 'Help')
		click(self.root, NEXT, 0)
		self.redraw()
		self.assertEqual(self.front(), 'Main')
		self.assertIs(self.root._activeWindow(), self.root)
		self.assertIs(self.root.focus_get(), self.entry)
		click(self.root, NEXT, 0)
		self.redraw()
		self.assertEqual(self.front(), 'Help')
		self.assertIs(self.root.focus_get(), entry)

	def test_cycle_three_windows(self):
		self.toplevel('One')
		self.toplevel('Two')
		seen = [self.front()]
		for _ in range(3):
			click(self.root, NEXT, 0)
			self.redraw()
			seen.append(self.front())
		self.assertEqual(seen, ['Two', 'One', 'Main', 'Two'])
		for _ in range(3):
			click(self.root, PREV, 0)
			self.redraw()
			seen.append(self.front())
		self.assertEqual(seen[4:], ['Main', 'One', 'Two'])

	def test_acts_on_release(self):
		self.toplevel('Help')
		click(self.root, NEXT, 0, 'press')
		self.redraw()
		self.assertEqual(self.front(), 'Help')
		click(self.root, NEXT, 0, 'release')
		self.redraw()
		self.assertEqual(self.front(), 'Main')

	def test_transient_follows_its_master(self):
		top, _ = self.toplevel('Help')
		dlg = tk.Toplevel(top)
		dlg.transient(top)
		tk.Label(dlg, text='dialog').pack()
		self.redraw()
		click(self.root, NEXT, 0)
		self.redraw()
		self.assertEqual(self.front(), 'Main')
		self.assertLess(self.root._stack.index(dlg), self.root._stack.index(self.root))
		click(self.root, NEXT, 0)
		self.redraw()
		self.assertEqual(self.root._stack[-1], dlg)
		self.assertIs(self.root._activeWindow(), dlg)

	def test_window_list(self):
		self.toplevel('One')
		self.toplevel('Two')
		click(self.root, LIST, 0)
		self.redraw()
		menu = self.root._switchMenu
		self.assertIn(menu, self.root._postedMenus)
		self.assertNotIn(menu, self.root.winfo_children())
		labels = [it['label'] for it in menu._menuItems]
		self.assertEqual(labels, ['• Two', '  One', '  Main'])
		press(self.root, curses.KEY_DOWN, curses.KEY_DOWN, KEY_ENTER)
		self.redraw()
		self.assertEqual(self.front(), 'Main')
		self.assertFalse(self.root._postedMenus)

	def test_window_list_deiconifies(self):
		top, _ = self.toplevel('Help')
		top.iconify()
		self.redraw()
		self.assertEqual(self.front(), 'Main')
		click(self.root, LIST, 0)
		labels = [it['label'] for it in self.root._switchMenu._menuItems]
		self.assertIn('  Help (iconified)', labels)
		self.root._switchMenu._menuItems[labels.index('  Help (iconified)')]['command']()
		self.redraw()
		self.assertEqual(top.state(), 'normal')
		self.assertEqual(self.front(), 'Help')

	def test_withdrawn_window_not_switchable(self):
		top, _ = self.toplevel('Help')
		top.withdraw()
		self.redraw()
		self.assertNotIn('◀', self.scr.row(0))

	def test_grab_blocks_the_switch(self):
		top, _ = self.toplevel('Help')
		dlg = tk.Toplevel(top)
		dlg.transient(top)
		tk.Label(dlg, text='modal dialog').pack()
		dlg.grab_set()
		self.redraw()
		click(self.root, NEXT, 0)
		press(self.root, CTRL_F6)
		self.redraw()
		self.assertEqual(self.front(), 'Help')

	def test_ctrl_f6(self):
		self.toplevel('One')
		self.toplevel('Two')
		press(self.root, CTRL_F6)
		self.redraw()
		self.assertEqual(self.front(), 'One')
		press(self.root, CTRL_SHIFT_F6)
		self.redraw()
		self.assertEqual(self.front(), 'Two')
		press(self.root, curses.KEY_F0 + 30)
		self.redraw()
		self.assertEqual(self.front(), 'One')

	def test_ctrl_f6_codes(self):
		self.assertEqual(ctrlF6Step(CTRL_F6), 1)
		self.assertEqual(ctrlF6Step(CTRL_SHIFT_F6), -1)
		self.assertEqual(ctrlF6Step(curses.KEY_F0 + 42), -1)
		self.assertEqual(ctrlF6Step(curses.KEY_F6), 0)
		self.assertEqual(ctrlF6Step(ModKey(curses.KEY_F1 + 5, STATE_ALT)), 0)

	def test_lift_and_lower(self):
		one, _ = self.toplevel('One')
		two, _ = self.toplevel('Two')
		one.lift()
		self.redraw()
		self.assertEqual(self.front(), 'One')
		one.lower()
		self.redraw()
		self.assertEqual(self.front(), 'Two')
		self.assertEqual(self.root._toplevels, [one, two])
		self.assertEqual(self.root._stack[0], one)

	def test_no_room_beside_the_menubar(self):
		bar = tk.Menu(self.root)
		for name in ('File', 'Edit', 'View', 'Insert', 'Tools', 'Window', 'Options', 'Help'):
			bar.add_cascade(label=name, menu=tk.Menu(bar))
		self.root.configure(menu=bar)
		self.root.lift()
		tk.Toplevel(self.root)
		self.root.lift()
		self.redraw()
		self.assertEqual(self.root._barOwner(), self.root)
		self.assertNotIn('◀', self.scr.row(0))


if __name__ == '__main__':
	unittest.main()
