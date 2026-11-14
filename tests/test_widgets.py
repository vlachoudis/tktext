import curses
import os
import tempfile
import unittest

from fakescreen import makeApp, attach, press, click, FakeScreen, tk
import tktext.messagebox as messagebox
import tktext.filedialog as filedialog
from tktext import ttk
import tktext


class LabelButtonTest(unittest.TestCase):

	def test_label_anchor(self):
		root, scr = makeApp(20, 4)
		tk.Label(root, text='hi', anchor='center').pack(fill=tk.X)
		tk.Label(root, text='hi', anchor='e').pack(fill=tk.X)
		attach(root)
		self.assertEqual(scr.row(1).index('hi'), 9)
		self.assertEqual(scr.row(2).index('hi'), 18)

	def test_button_padx_zero_respected(self):
		root, scr = makeApp(20, 4)
		b = tk.Button(root, text='Quit', borderwidth=0, padx=0)
		self.assertEqual(b._preferredSize(), (4, 1))

	def test_textvariable_label(self):
		root, scr = makeApp(20, 4)
		v = tk.StringVar(value='one')
		tk.Label(root, textvariable=v).pack()
		attach(root)
		v.set('two')
		root._update(force=True)
		self.assertIsNotNone(scr.find('two'))


class CheckRadioTest(unittest.TestCase):

	def test_checkbutton_with_stringvar(self):
		root, scr = makeApp(30, 5)
		v = tk.StringVar(value='no')
		c = tk.Checkbutton(root, text='x', variable=v, onvalue='yes', offvalue='no')
		c.pack()
		attach(root)
		self.assertFalse(c._isChecked())
		press(root, 32)
		self.assertEqual(v.get(), 'yes')
		self.assertIsNotNone(scr.find('[X] x'))

	def test_checkbutton_intvar_compares_as_string(self):
		root, scr = makeApp(30, 5)
		v = tk.IntVar(value=1)
		c = tk.Checkbutton(root, variable=v)
		self.assertTrue(c._isChecked())

	def test_checkbutton_indicatoron_false(self):
		# tkExtra.Combobox arrow: a button-like checkbutton without indicator
		root, scr = makeApp(30, 5)
		v = tk.IntVar(value=0)
		c = tk.Checkbutton(root, text='▼', variable=v, indicatoron=False, padx=0)
		c.pack()
		r = tk.Radiobutton(root, text='r', value=1, indicatoron=0)
		r.pack()
		self.assertEqual(c._preferredSize(), (1, 1))
		self.assertEqual(r._preferredSize(), (1, 1))
		attach(root)
		self.assertNotIn('[', scr.text())
		self.assertNotIn('(', scr.text())
		click(root, c._x, c._y)
		self.assertEqual(v.get(), 1)
		self.assertNotIn('[X]', scr.text())

	def test_radiobutton_group(self):
		root, scr = makeApp(30, 6)
		v = tk.IntVar(value=2)
		r1 = tk.Radiobutton(root, text='a', variable=v, value=1); r1.pack()
		r2 = tk.Radiobutton(root, text='b', variable=v, value=2); r2.pack()
		attach(root)
		self.assertTrue(r2._isSelected())
		click(root, r1._x, r1._y)
		self.assertEqual(v.get(), 1)
		r1.focus_set()
		press(root, curses.KEY_DOWN)
		self.assertEqual(v.get(), 2)


class EntryTest(unittest.TestCase):

	def test_typing_and_variable(self):
		root, scr = makeApp(30, 5)
		v = tk.StringVar()
		e = tk.Entry(root, textvariable=v); e.pack()
		attach(root)
		press(root, 'hello', curses.KEY_LEFT, curses.KEY_BACKSPACE)
		self.assertEqual(v.get(), 'helo')
		v.set('x')
		root._update(force=True)
		self.assertEqual(e._cursorPos()[1], e._x + 1 + 1)	# cursor clamped

	def test_readonly(self):
		root, scr = makeApp(30, 5)
		e = tk.Entry(root); e.pack()
		e.insert(0, 'abc')
		e.configure(state='readonly')
		attach(root)
		self.assertIs(root.focus_get(), e)
		press(root, 'z')
		e.insert('end', 'q')
		self.assertEqual(e.get(), 'abc')

	def test_insert_delete_index(self):
		root, scr = makeApp(30, 5)
		e = tk.Entry(root)
		e.insert('end', 'world')
		e.insert(0, 'hello ')
		self.assertEqual(e.get(), 'hello world')
		e.delete(0, 6)
		self.assertEqual(e.get(), 'world')
		self.assertEqual(e.index('end'), 5)


class ListboxTest(unittest.TestCase):

	def test_select_and_scroll(self):
		root, scr = makeApp(30, 8)
		lb = tk.Listbox(root, height=3); lb.pack()
		lb.insert('end', *[f'item{i}' for i in range(10)])
		attach(root)
		got = []
		lb.bind('<<ListboxSelect>>', lambda e: got.append(lb.curselection()))
		press(root, curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN)
		self.assertEqual(lb.curselection(), (3,))
		self.assertEqual(got[-1], (3,))
		self.assertEqual(lb.yview()[0], 0.1)
		lb.delete(0, 'end')
		root._update(force=True)
		self.assertEqual(lb.size(), 0)
		self.assertEqual(lb._scrollY, 0)

	def test_get_curselection(self):
		# get(curselection()) works in tkinter: Tcl reads (2,) as index 2
		root, scr = makeApp(30, 8)
		lb = tk.Listbox(root, height=3); lb.pack()
		lb.insert('end', 'a', 'b', 'c')
		lb.selection_set(2)
		self.assertEqual(lb.get(lb.curselection()), 'c')
		self.assertEqual(lb.get([1]), 'b')

	def test_scrollbar_inside_border(self):
		root, scr = makeApp(30, 8)
		lb = tk.Listbox(root, height=3, width=10); lb.pack()
		lb.insert('end', *range(10))
		attach(root)
		y = lb._y + 1
		# border stays intact; the bar is one column inside it
		self.assertEqual(scr.row(y)[lb._x + lb._width - 1], '|')
		self.assertIn(scr.row(y)[lb._x + lb._width - 2], '█│')

	def test_wheel(self):
		root, scr = makeApp(30, 8)
		lb = tk.Listbox(root, height=3); lb.pack()
		lb.insert('end', *range(10))
		attach(root)
		click(root, lb._x + 2, lb._y + 1, 'wheeldown')
		self.assertEqual(lb._scrollY, 3)


class TreeviewTest(unittest.TestCase):

	def _tree(self):
		root, scr = makeApp(40, 12)
		tv = tk.Treeview(root, columns=('size',), height=5)
		tv.heading('#0', text='Name')
		tv.heading('size', text='Size')
		tv.column('#0', width=10)
		tv.column('size', width=6)
		d = tv.insert('', 'end', text='dir', values=('-',), tags='folder')
		tv.insert(d, 'end', text='file', values=('1K',))
		tv.pack()
		attach(root)
		return root, scr, tv, d

	def test_tags_string_and_set(self):
		root, scr, tv, d = self._tree()
		self.assertEqual(tv.item(d, 'tags'), ('folder',))
		self.assertEqual(tv.set(d, 'size'), '-')
		self.assertEqual(tv.column('size')['width'], 6)

	def test_open_and_select_with_keys(self):
		root, scr, tv, d = self._tree()
		opened = []
		tv.bind('<<TreeviewOpen>>', lambda e: opened.append(tv.focus()))
		press(root, curses.KEY_DOWN, curses.KEY_RIGHT, curses.KEY_DOWN)
		self.assertEqual(opened, [d])
		self.assertEqual(len(tv.selection()), 1)
		self.assertEqual(tv.item(tv.selection()[0], 'text'), 'file')

	def test_cells_clipped_to_widget(self):
		root, scr = makeApp(30, 8)
		tv = tk.Treeview(root, columns=('a', 'b'), width=12, height=3)
		tv.insert('', 'end', text='x' * 40, values=('y' * 40, 'z' * 40))
		tv.pack(side=tk.LEFT)
		marker = tk.Label(root, text='M'); marker.pack(side=tk.LEFT)
		attach(root)
		self.assertIsNotNone(scr.find('M'))

	def test_identify_and_heading_command(self):
		root, scr, tv, d = self._tree()
		hit = []
		tv.heading('size', command=lambda: hit.append(1))
		click(root, tv._x + 12, tv._y + 1)
		self.assertEqual(hit, [1])
		self.assertEqual(tv.identify_row(2), d)
		self.assertEqual(tv.identify_column(12), '#1')


class NotebookTest(unittest.TestCase):

	def test_tab_change_moves_focus_and_fires(self):
		root, scr = makeApp(40, 10)
		nb = tk.Notebook(root); nb.pack(fill=tk.BOTH, expand=True)
		p1 = tk.Frame(nb); e1 = tk.Entry(p1); e1.pack()
		p2 = tk.Frame(nb); e2 = tk.Entry(p2); e2.pack()
		nb.add(p1, text='One')
		nb.add(p2, text='Two')
		attach(root)
		root.update()		# deliver the event queued by the first add()
		got = []
		nb.bind('<<NotebookTabChanged>>', lambda e: got.append(nb.index('current')))
		e1.focus_set()
		nb.select(1)
		root.update()		# virtual events are queued like in Tk
		self.assertEqual(got, [1])
		self.assertIsNot(root.focus_get(), e1)
		self.assertFalse(e1._isMapped())
		self.assertTrue(e2._isMapped())
		self.assertIs(nb.select(), p2)


class ScaleSpinComboTest(unittest.TestCase):

	def test_scale_to_zero_and_variable(self):
		root, scr = makeApp(40, 5)
		v = tk.DoubleVar(value=-5)
		s = tk.Scale(root, from_=-10, to=0, variable=v, orient='horizontal')
		s.pack()
		attach(root)
		self.assertEqual(s.get(), -5)
		v.set(-2)
		self.assertEqual(s.get(), -2)
		press(root, curses.KEY_END)
		self.assertEqual(v.get(), 0)

	def test_spinbox(self):
		root, scr = makeApp(40, 5)
		v = tk.StringVar()
		sp = tk.Spinbox(root, from_=0, to=10, increment=5, textvariable=v)
		sp.pack()
		attach(root)
		self.assertEqual(sp.get(), '0')
		press(root, curses.KEY_UP, curses.KEY_UP, curses.KEY_UP)
		self.assertEqual(v.get(), '10')
		v.set('3')
		press(root, curses.KEY_BACKSPACE, '7')
		self.assertEqual(sp.get(), '7')

	def test_combobox_readonly_dropdown(self):
		root, scr = makeApp(40, 12)
		cb = ttk.Combobox(root, values=('a', 'b', 'c'), state='readonly')
		cb.current(0)
		cb.pack()
		attach(root)
		got = []
		cb.bind('<<ComboboxSelected>>', lambda e: got.append(cb.get()))
		press(root, curses.KEY_DOWN)
		self.assertTrue(root._postedMenus)
		press(root, curses.KEY_DOWN, 10)
		self.assertEqual(got, ['b'])
		self.assertFalse(root._postedMenus)
		press(root, 'z')
		self.assertEqual(cb.get(), 'b')

	def test_combobox_mouse_select(self):
		root, scr = makeApp(40, 12)
		cb = tk.Combobox(root, values=('a', 'b', 'c'))
		cb.pack()
		attach(root)
		click(root, cb._x + cb._width - 2, cb._y + 1)		# the ▼ button
		x, y, w, h = cb._ddRect()
		click(root, x + 2, y + 3)
		self.assertEqual(cb.get(), 'c')


class MenuTest(unittest.TestCase):

	def test_popup_keyboard(self):
		root, scr = makeApp(40, 12)
		b = tk.Button(root, text='x'); b.pack()
		got = []
		m = tk.Menu(root)
		m.add_command(label='Open', command=lambda: got.append('open'))
		m.add_separator()
		m.add_command(label='Quit', underline=0, command=lambda: got.append('quit'))
		attach(root)
		m.post(2, 2)
		press(root, curses.KEY_DOWN, 10)
		self.assertEqual(got, ['quit'])
		self.assertFalse(root._postedMenus)
		m.post(2, 2)
		press(root, 'o')
		self.assertEqual(got, ['quit', 'open'])

	def test_click_outside_closes_with_clicked_event(self):
		root, scr = makeApp(40, 12)
		m = tk.Menu(root); m.add_command(label='A')
		attach(root)
		m.post(5, 5)
		click(root, 30, 10)
		self.assertFalse(root._postedMenus)

	def test_menu_click_does_not_reach_widget_below(self):
		root, scr = makeApp(40, 12)
		hits = []
		b = tk.Button(root, text='under', command=lambda: hits.append('btn'))
		b.pack()
		m = tk.Menu(root)
		m.add_command(label='Item', command=lambda: hits.append('menu'))
		attach(root)
		m.post(b._x, b._y)
		x, y = b._x + 2, b._y + 1
		click(root, x, y, 'press')
		click(root, x, y, 'release')
		self.assertEqual(hits, ['menu'])

	def test_menubar(self):
		root, scr = makeApp(40, 12)
		got = []
		bar  = tk.Menu(root)
		file = tk.Menu(bar)
		file.add_command(label='New', command=lambda: got.append('new'))
		bar.add_cascade(label='File', menu=file)
		edit = tk.Menu(bar)
		edit.add_command(label='Copy', command=lambda: got.append('copy'))
		bar.add_cascade(label='Edit', menu=edit)
		root.config(menu=bar)
		tk.Button(root, text='x').pack()
		attach(root)
		self.assertTrue(scr.row(0).startswith(' File  Edit '))
		press(root, curses.KEY_F10)
		self.assertIs(root._postedMenus[-1], file)
		press(root, curses.KEY_RIGHT, 10)
		self.assertEqual(got, ['copy'])
		click(root, 2, 0)
		self.assertIs(root._postedMenus[-1], file)
		click(root, 3, 2)
		self.assertEqual(got, ['copy', 'new'])

	def test_cascade(self):
		root, scr = makeApp(60, 12)
		got = []
		m = tk.Menu(root)
		sub = tk.Menu(m)
		sub.add_command(label='Red', command=lambda: got.append('red'))
		m.add_cascade(label='Colour', menu=sub)
		attach(root)
		m.post(0, 2)
		press(root, curses.KEY_RIGHT)
		self.assertIs(root._postedMenus[-1], sub)
		press(root, curses.KEY_LEFT)
		self.assertIs(root._postedMenus[-1], m)
		press(root, curses.KEY_RIGHT, 10)
		self.assertEqual(got, ['red'])
		self.assertFalse(root._postedMenus)

	def test_optionmenu_command(self):
		root, scr = makeApp(40, 12)
		v = tk.StringVar(value='a')
		got = []
		om = tk.OptionMenu(root, v, 'a', 'b', command=got.append)
		om.pack()
		attach(root)
		press(root, curses.KEY_DOWN)
		self.assertEqual((v.get(), got), ('b', ['b']))
		om['menu'].add_command(label='z', command=tk._setit(v, 'z'))
		om['menu'].invoke('z')
		self.assertEqual(v.get(), 'z')


class DialogTest(unittest.TestCase):

	def test_askyesno_keyboard(self):
		root, scr = makeApp(60, 16)
		tk.Button(root, text='x').pack()
		attach(root)
		scr.keys = [curses.KEY_RIGHT, 10]
		self.assertFalse(messagebox.askyesno('Q', 'Sure?'))
		scr.keys = [ord('y')]
		self.assertTrue(messagebox.askyesno('Q', 'Sure?'))
		self.assertFalse(root._postedDialogs)

	def test_timers_run_while_dialog_open(self):
		root, scr = makeApp(60, 16)
		attach(root)
		got = []
		root.after(0, lambda: got.append('tick'))
		scr.keys = [-1, 10]
		messagebox.showinfo('t', 'm')
		self.assertEqual(got, ['tick'])

	def test_filedialog_filters_and_opens(self):
		root, scr = makeApp(70, 24)
		attach(root)
		with tempfile.TemporaryDirectory() as d:
			open(os.path.join(d, 'a.txt'), 'w').close()
			open(os.path.join(d, 'b.py'), 'w').close()
			dlg = filedialog._FileDialog(root, 'Open', initialdir=d,
				filetypes=[('Text', '*.txt')])
			names = [n for n, _ in dlg._entries]
			self.assertIn('a.txt', names)
			self.assertNotIn('b.py', names)
			scr.keys = [curses.KEY_DOWN, 10]
			self.assertEqual(dlg.run(), os.path.join(d, 'a.txt'))


class RobustnessTest(unittest.TestCase):

	def _demo(self):
		import demo
		return demo.buildDemo()

	def test_demo_renders_at_many_sizes(self):
		for w, h in ((120, 40), (80, 24), (40, 10), (10, 3), (1, 1)):
			root = self._demo()
			root._attach(FakeScreen(w, h), initCurses=False)

	def test_resize(self):
		root = self._demo()
		scr  = FakeScreen(120, 40)
		root._attach(scr, initCurses=False)
		scr.resize(60, 15)
		root._handleInput(curses.KEY_RESIZE)
		root._update()
		self.assertEqual((root._width, root._height), (60, 15))

	def test_demo_tab_through_everything(self):
		root = self._demo()
		scr  = FakeScreen(120, 40)
		root._attach(scr, initCurses=False)
		seen = set()
		for _ in range(40):
			press(root, 9)
			seen.add(type(root.focus_get()).__name__)
		self.assertTrue({'Listbox', 'Notebook', 'Entry', 'Checkbutton',
			'Radiobutton', 'OptionMenu', 'Button'} <= seen)

	def test_destroyed_focus_widget(self):
		root, scr = makeApp(40, 8)
		a = tk.Entry(root); a.pack()
		b = tk.Entry(root); b.pack()
		attach(root)
		a.destroy()
		root._update(force=True)
		self.assertIs(root.focus_get(), b)


class ListboxSubclassTest(unittest.TestCase):

	def test_subclass_private_attributes_do_not_clash(self):
		# flair's SearchListbox keeps its own self._items/_pos
		class SearchListbox(tk.Listbox):
			def __init__(self, master, **kw):
				super().__init__(master, **kw)
				self._items = []
				self._pos   = []
			def insert(self, index, *elements):
				del self._items[:]
				return tk.Listbox.insert(self, index, *elements)
		root, scr = makeApp()
		lb = SearchListbox(root)
		for it in ('a', 'b', 'c'):
			lb.insert('end', it)
		self.assertEqual(lb.get(0, 'end'), ('a', 'b', 'c'))

	def test_prev_next_line_virtual_events(self):
		root, scr = makeApp()
		lb = tk.Listbox(root)
		lb.insert('end', 'a', 'b', 'c')
		lb.pack()
		attach(root)
		lb.activate(1)
		lb.selection_set(1)
		lb.event_generate('<<NextLine>>')
		self.assertEqual(lb.curselection(), (2,))
		lb.event_generate('<<PrevLine>>')
		lb.event_generate('<<PrevLine>>')
		self.assertEqual(lb.curselection(), (0,))
		self.assertEqual(lb.index('active'), 0)


class _RecColors:
	"""ColorManager stand-in: each (fg, bg) pair gets its own pair number,
	so the colours of a drawn cell can be read back from the attribute."""

	def __init__(self, real):
		self._real  = real
		self._pairs = []

	def __getattr__(self, name):
		return getattr(self._real, name)

	def getAttr(self, fg='', bg='', bold=False, reverse=False,
			underline=False, dim=False, blink=False):
		key = (fg or '', bg or '')
		if key not in self._pairs:
			self._pairs.append(key)
		attr = (self._pairs.index(key) + 1) << 8
		if bold:
			attr |= curses.A_BOLD
		if reverse:
			attr |= curses.A_REVERSE
		if underline:
			attr |= curses.A_UNDERLINE
		return attr

	def roleAttr(self, role, fg=None, bg=None, **kw):
		# the real roleAttr, routed through the recording getAttr
		return type(self._real).roleAttr(self, role, fg, bg, **kw)

	def colors(self, attr):
		"""(fg, bg) of a recorded attribute."""
		return self._pairs[((attr >> 8) & 0xff) - 1]


class ThemeTest(unittest.TestCase):

	def setUp(self):
		tktext._colors.resetTheme()

	def tearDown(self):
		tktext._colors.resetTheme()

	def app(self, w=40, h=10):
		root, scr   = makeApp(w, h)
		root._colors = _RecColors(root._colors)
		return root, scr

	def cell(self, root, scr, text):
		y, x = scr.find(text)
		a    = scr.attrs[y][x]
		return root._colors.colors(a), a

	def test_unknown_role_rejected(self):
		with self.assertRaises(ValueError):
			tktext.setTheme(nosuchrole=('red', ''))
		with self.assertRaises(ValueError):
			tktext.setTheme(select=('red', '', 'sparkle'))

	def test_get_and_reset(self):
		tktext.setTheme(disabled='red')
		self.assertEqual(tktext.getTheme('disabled'), ('red', '', ''))
		tktext.resetTheme()
		self.assertEqual(tktext.getTheme('disabled'), ('gray', '', ''))

	def test_disabled_role_and_option(self):
		root, scr = self.app()
		tk.Label(root, text='aaa', state='disabled').pack()
		tk.Label(root, text='bbb', state='disabled', disabledforeground='green').pack()
		attach(root)
		self.assertEqual(self.cell(root, scr, 'aaa')[0][0], 'gray')
		tktext.setTheme(disabled=('red', ''))
		root._update(force=True)
		self.assertEqual(self.cell(root, scr, 'aaa')[0][0], 'red')
		self.assertEqual(self.cell(root, scr, 'bbb')[0][0], 'green')	# option wins

	def test_select_role(self):
		root, scr = self.app()
		lb = tk.Listbox(root)
		lb.insert('end', 'one', 'two')
		lb.pack()
		lb.selection_set(0)
		attach(root)
		_, a = self.cell(root, scr, 'one')
		self.assertTrue(a & curses.A_REVERSE)		# default: reverse video
		tktext.setTheme(select=('white', 'blue'))
		root._update(force=True)
		(fg, bg), a = self.cell(root, scr, 'one')
		self.assertEqual((fg, bg), ('white', 'blue'))
		self.assertFalse(a & curses.A_REVERSE)

	def test_option_database_select_colours(self):
		root, scr = self.app(40, 12)
		root.option_add('*Listbox.selectBackground', 'green')
		root.option_add('*selectForeground', 'yellow')
		lb = tk.Listbox(root, height=2)
		lb.insert('end', 'item')
		lb.pack()
		lb.selection_set(0)
		e = tk.Entry(root)
		e.insert(0, 'qqq')
		e.pack()
		e.selection_range(0, 'end')
		attach(root)
		self.assertEqual(self.cell(root, scr, 'item')[0], ('yellow', 'green'))
		fg, bg = self.cell(root, scr, 'qqq')[0]
		self.assertEqual(fg, 'yellow')
		self.assertNotEqual(bg, 'green')		# *Listbox.… only

	def test_option_database_active_colours(self):
		root, scr = self.app()
		root.option_add('*activeBackground', 'red')
		b = tk.Button(root, text='press')
		b.pack()
		attach(root)
		b.focus_set()
		root._update(force=True)
		self.assertEqual(self.cell(root, scr, 'press')[0][1], 'red')

	def test_titlebar_role(self):
		root, scr = self.app()
		root.title('Main')
		attach(root)
		tktext.setTheme({'titlebar.title': ('white', 'red', 'bold')})
		root._update(force=True)
		(fg, bg), a = self.cell(root, scr, 'Main')
		self.assertEqual((fg, bg), ('white', 'red'))
		self.assertTrue(a & curses.A_BOLD)

	def test_dialog_role(self):
		root, scr = self.app(60, 16)
		attach(root)
		tktext.setTheme(dialog=('black', 'green'))
		seen = []
		getch = scr.getch
		def snapshot():
			if scr.find('Hello'):
				seen.append(self.cell(root, scr, 'Hello')[0])
			return getch()
		scr.getch = snapshot
		scr.keys  = [-1, 10]
		messagebox.showinfo('t', 'Hello')
		self.assertIn(('black', 'green'), seen)


if __name__ == '__main__':
	unittest.main()
