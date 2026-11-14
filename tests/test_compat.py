"""tkinter compatibility layer: install(), Toplevel, pixel mode, Canvas,
PanedWindow, option database, class bindings, queued virtual events."""
import os
import subprocess
import sys
import unittest

from fakescreen import makeApp, attach, press, click
import tktext as tk
from tktext import _core

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class InstallTest(unittest.TestCase):
	"""install() replaces tkinter (run in a subprocess: it is global)."""

	def test_tkinter_modules_are_tktext(self):
		script = '\n'.join([
			'import sys; sys.path.insert(0, %r)' % ROOT,
			'import tktext; tktext.install(block=("geoviewer",))',
			'import tkinter as tk, tkinter.ttk as ttk, tkinter.font as tkFont',
			'from tkinter import messagebox, filedialog, colorchooser, dnd',
			'import tkinter.simpledialog, tkinter.constants',
			'assert tk is tktext and ttk.Treeview and tkFont.Font',
			'assert tk.TclError is tktext.TclError and tk.END == "end"',
			'assert tkinter.constants.LEFT == "left" and ttk.INSERT == "insert"',
			'for name in ("geoviewer", "PIL.ImageTk"):',
			'	try:',
			'		__import__(name)',
			'	except ImportError as ex:',
			'		assert "graphical display" in str(ex), ex',
			'	else:',
			'		raise AssertionError(name)',
			'from tktext import _core',
			'assert (_core.PX, _core.PY) == (8, 16)',
			'print("INSTALL-OK")'])
		out = subprocess.run([sys.executable, '-c', script],
			capture_output=True, text=True, timeout=30)
		self.assertIn('INSTALL-OK', out.stdout, out.stderr)


class ConstructorTest(unittest.TestCase):

	def test_cnf_dict_and_master_keyword(self):
		root, scr = makeApp()
		f = tk.Frame(root)
		lbl = tk.Label(f, {'text': 'cnf'}, fg='red')
		self.assertEqual(lbl.cget('text'), 'cnf')
		self.assertEqual(lbl.cget('fg'), 'red')
		b = tk.Button(master=f, text='kw')
		self.assertIs(b.master, f)
		self.assertIn(b, f.winfo_children())

	def test_default_root(self):
		root, scr = makeApp()
		top = tk.Toplevel()		# no master: tkinter's default root
		self.assertIs(top._getApp(), tk._default_root)

	def test_init_does_not_call_overridden_configure(self):
		root, scr = makeApp()

		class Combo(tk.Frame):
			def __init__(self, master, **kw):
				super().__init__(master, padx=0)
				self.inner = tk.Entry(self)

			def configure(self, **kw):
				self.inner.configure(**kw)	# needs self.inner

		Combo(root)		# must not raise AttributeError

	def test_name_and_paths(self):
		root, scr = makeApp()
		f = tk.Frame(root, name='box')
		e = tk.Entry(f, name='entry')
		self.assertEqual(str(e), '.box.entry')
		self.assertEqual(e._w, '.box.entry')
		self.assertIs(root.nametowidget('.box.entry'), e)
		self.assertIs(f.nametowidget('entry'), e)
		self.assertEqual(e.winfo_parent(), '.box')

	def test_winfo_class_of_subclass(self):
		root, scr = makeApp()

		class MyEntry(tk.Entry):
			pass

		self.assertEqual(MyEntry(root).winfo_class(), 'Entry')


class ToplevelTest(unittest.TestCase):

	def test_maximised_transient_and_override(self):
		root, scr = makeApp(60, 20)
		root.withdraw()
		main = tk.Toplevel(root)
		main.title('Main')
		tk.Label(main, text='main window').pack()
		dlg = tk.Toplevel(main)
		dlg.transient(main)
		dlg.title('Dialog')
		tk.Entry(dlg, width=10).pack()
		pop = tk.Toplevel(root)
		pop.overrideredirect(1)
		pop.wm_geometry('+3+4')
		tk.Label(pop, text='popup').pack()
		attach(root)
		self.assertEqual((main._x, main._y, main._width, main._height), (0, 0, 60, 20))
		self.assertEqual(scr.row(0).strip(), 'Main')		# title bar
		self.assertIsNotNone(scr.find('Dialog'))		# dialog frame title
		self.assertEqual((pop._x, pop._y), (3, 4))
		self.assertEqual(scr.find('popup'), (4, 3))
		# the new dialog took the keyboard focus
		self.assertTrue(dlg._isAncestorOf(root.focus_get()))

	def test_focus_stays_in_topmost_window(self):
		root, scr = makeApp(60, 20)
		e1 = tk.Entry(root)
		e1.pack()
		dlg = tk.Toplevel(root)
		dlg.transient(root)
		e2 = tk.Entry(dlg)
		e2.pack()
		attach(root)
		e1.focus_set()			# a widget under the dialog ...
		root._update(force=True)
		self.assertIs(root.focus_get(), e2)	# ... cannot get the keys
		dlg.destroy()
		root._update(force=True)
		self.assertIs(root.focus_get(), e1)

	def test_grab_blocks_other_windows(self):
		root, scr = makeApp(60, 20)
		got = []
		b = tk.Button(root, text='under', command=lambda: got.append(1))
		b.pack(side='bottom')
		dlg = tk.Toplevel(root)
		dlg.transient(root)
		tk.Label(dlg, text='modal').pack()
		attach(root)
		dlg.grab_set()
		y, x = scr.find('under')
		click(root, x + 1, y)
		self.assertEqual(got, [])
		dlg.grab_release()
		click(root, x + 1, y)
		self.assertEqual(got, [1])

	def test_grab_reports_outside_click_to_grab_window(self):
		# Tk: a click outside the grab tree goes to the grab window with
		# coordinates out of its bounds (drop downs close on it)
		root, scr = makeApp(60, 20)
		got    = []
		events = []
		b = tk.Button(root, text='under', command=lambda: got.append(1))
		b.pack(side='bottom')
		pop = tk.Toplevel(root)
		pop.overrideredirect(1)
		pop.geometry('10x3+2+2')
		tk.Label(pop, text='list').pack()
		pop.bind('<Button-1>', lambda e: events.append((e.widget, e.x, e.y)))
		attach(root)
		pop.grab_set()
		y, x = scr.find('under')
		click(root, x + 1, y)
		self.assertEqual(got, [])		# never reaches the widget beneath
		self.assertEqual(len(events), 1)
		w, ex, ey = events[0]
		self.assertIs(w, pop)
		self.assertTrue(ex >= pop.winfo_width() or ey >= pop.winfo_height())

	def test_wait_window_returns_when_destroyed(self):
		root, scr = makeApp(40, 12)
		dlg = tk.Toplevel(root)
		attach(root)
		root.after(0, dlg.destroy)
		dlg.wait_window()
		self.assertTrue(dlg._destroyed)

	def test_protocol_on_interrupt(self):
		root, scr = makeApp(40, 12)
		closed = []
		dlg = tk.Toplevel(root)
		dlg.protocol('WM_DELETE_WINDOW', lambda: closed.append(1))
		attach(root)
		root._onInterrupt()			# Ctrl-C closes the active window
		self.assertEqual(closed, [1])


class PixelModeTest(unittest.TestCase):

	def setUp(self):
		_core.setPixelMode(8, 16)

	def tearDown(self):
		_core.setPixelMode(1, 1)

	def test_distances_are_pixels(self):
		root, scr = makeApp(40, 12)
		f = tk.Frame(root, width=160, height=48)	# 20 x 3 cells
		f.pack(padx=16, pady=16)			# 2 cells, 1 line
		attach(root)
		self.assertEqual((f._width, f._height), (20, 3))
		self.assertEqual(f.winfo_width(), 160)
		self.assertEqual(f.winfo_height(), 48)
		self.assertEqual(f.winfo_rooty(), (1 + 1) * 16)	# title row + pady

	def test_event_coordinates_and_geometry(self):
		root, scr = makeApp(40, 12)
		lb = tk.Listbox(root, height=5)
		for i in range(5):
			lb.insert('end', f'item {i}')
		lb.pack(anchor='nw')
		attach(root)
		self.assertEqual(lb.nearest(2 * 16 + 3), 2)	# y in pixels
		top = tk.Toplevel(root)
		top.overrideredirect(1)
		top.geometry('80x32+16+32')
		tk.Label(top, text='x').pack()
		root._update(force=True)
		self.assertEqual((top._x, top._y, top._width, top._height), (2, 2, 10, 2))
		self.assertEqual(top.geometry(), '80x32+16+32')

	def test_tk_default_colours_and_option_db(self):
		root, scr = makeApp(40, 12)
		e = tk.Entry(root)
		l = tk.Label(root, text='x')
		self.assertEqual(e.cget('background'), 'white')
		self.assertEqual(l.cget('background'), '#d9d9d9')
		root.option_add('*Entry.background', 'yellow')
		root.option_add('*foreground', 'blue')
		self.assertEqual(e.cget('background'), 'yellow')
		self.assertEqual(l.cget('foreground'), 'blue')
		l.configure(fg='red')
		self.assertEqual(l.cget('foreground'), 'red')

	def test_image_and_button_look(self):
		root, scr = makeApp(40, 12)
		img = tk.PhotoImage(width=16, height=16)
		self.assertEqual((img.width(), img.height()), (16, 16))
		tk.Button(root, text='OK').pack()
		tk.Button(root, image=img, command=lambda: None).pack()
		tk.Label(root, text='Tab', image=img, compound='left').pack()
		attach(root)
		self.assertIsNotNone(scr.find('[OK]'))
		self.assertIsNotNone(scr.find('[▪]'))
		self.assertIsNotNone(scr.find('· Tab'))

	def test_compound_placeholder_glyph_aligns(self):
		root, scr = makeApp(40, 12)
		plain = tk.PhotoImage(width=16, height=16)
		cut   = tk.PhotoImage(width=16, height=16)
		empty = tk.PhotoImage(width=16, height=16)
		cut.glyph   = '✂'
		empty.glyph = ' '
		for img, text in ((plain, 'Cut'), (cut, 'Copy'), (empty, 'Blank')):
			tk.Label(root, text=text, image=img, compound='left',
					anchor='w').pack(fill='x')
		tk.Button(root, text='Go', image=plain, compound='left').pack()
		attach(root)
		self.assertIsNotNone(scr.find('· Cut'))
		self.assertIsNotNone(scr.find('✂ Copy'))
		self.assertIsNotNone(scr.find('  Blank'))
		self.assertIsNotNone(scr.find('[· Go]'))
		self.assertEqual(scr.find('Cut')[1], scr.find('Copy')[1])
		self.assertEqual(scr.find('Cut')[1], scr.find('Blank')[1])


class GeometryOptionsTest(unittest.TestCase):

	def test_pack_in_before_after_and_order(self):
		root, scr = makeApp(40, 12)
		a = tk.Label(root, text='A')
		b = tk.Label(root, text='B')
		c = tk.Label(root, text='C')
		host = tk.Frame(root)
		for w in (a, b):
			w.pack(side='top')
		c.pack(side='top', before=a)
		host.pack(side='top')
		attach(root)
		self.assertLess(scr.find('C')[0], scr.find('A')[0])
		# re-packing a forgotten widget puts it at the end
		c.pack_forget()
		c.pack(side='top')
		root._update(force=True)
		self.assertGreater(scr.find('C')[0], scr.find('B')[0])
		# in_ packs into another master
		d = tk.Label(root, text='D')
		d.pack(in_=host)
		root._update(force=True)
		self.assertIn(d, host._children)
		self.assertTrue(d._isMapped())


class EventCompatTest(unittest.TestCase):

	def test_bind_class(self):
		root, scr = makeApp()
		e = tk.Entry(root)
		e.pack()
		attach(root)
		e.focus_set()
		got = []
		root.bind_class('Entry', '<Control-a>', lambda ev: got.append(ev.widget) or 'break')
		press(root, 1)				# Ctrl-A
		self.assertEqual(got, [e])

	def test_virtual_events_are_queued(self):
		root, scr = makeApp()
		lb = tk.Listbox(root)
		lb.insert('end', 'a', 'b')
		lb.pack()
		attach(root)
		lb.focus_set()
		got = []
		lb.bind('<<ListboxSelect>>', lambda e: got.append(lb.curselection()))
		lb._fireVirtual('<<ListboxSelect>>')
		self.assertEqual(got, [])
		root.update()
		self.assertEqual(len(got), 1)

	def test_event_add_maps_keys_to_virtual(self):
		root, scr = makeApp()
		e = tk.Entry(root)
		e.pack()
		attach(root)
		e.focus_set()
		got = []
		root.event_add('<<Hello>>', '<Control-Key-g>')
		e.bind('<<Hello>>', lambda ev: got.append(1))
		press(root, 7)				# Ctrl-G
		self.assertEqual(got, [1])

	def test_call_wrapper_is_used(self):
		root, scr = makeApp()
		calls = []

		class Wrapper(tk.CallWrapper):
			def __call__(self, *args):
				calls.append(self.func)
				return super().__call__(*args)

		saved = tk.CallWrapper
		tk.CallWrapper = Wrapper
		try:
			func = lambda: None
			b = tk.Button(root, text='x', command=func)
			b.invoke()
		finally:
			tk.CallWrapper = saved
		self.assertEqual(calls, [func])

	def test_configure_and_map_events(self):
		root, scr = makeApp(40, 12)
		f = tk.Frame(root, width=10, height=2)
		got = []
		f.bind('<Configure>', lambda e: got.append((e.width, e.height)))
		f.bind('<Map>', lambda e: got.append('map'))
		f.pack()
		attach(root)
		self.assertIn((10, 2), got)
		self.assertIn('map', got)


class WidgetCompatTest(unittest.TestCase):

	def test_canvas_items(self):
		root, scr = makeApp(40, 12)
		c = tk.Canvas(root, width=30, height=6, bg='')
		c.pack()
		r = c.create_rectangle(1, 1, 10, 4, fill='', outline='black')
		t = c.create_text(2, 2, text='hi', anchor='nw', tags=('lbl',))
		attach(root)
		self.assertIsNotNone(scr.find('hi'))
		self.assertIsNotNone(scr.find('┌'))
		self.assertEqual(c.find_withtag('lbl'), (t,))
		self.assertIn(r, c.find_overlapping(0, 0, 3, 3))
		c.coords(t, 5, 3)
		self.assertEqual(c.coords(t), [5.0, 3.0])
		got = []
		c.tag_bind('lbl', '<Button-1>', lambda e: got.append(1))
		root._update(force=True)
		y, x = scr.find('hi')
		click(root, x, y)
		self.assertEqual(got, [1])

	def test_paned_window(self):
		root, scr = makeApp(40, 8)
		pw = tk.PanedWindow(root, orient='horizontal')
		pw.pack(fill='both', expand=True)
		left  = tk.Label(pw, text='LEFT')
		right = tk.Label(pw, text='RIGHT')
		pw.add(left)
		pw.add(right)
		attach(root)
		self.assertEqual(len(pw.panes()), 2)
		self.assertLess(left._x + left._width, right._x)
		pw.sash_place(0, 20, 0)
		root._update(force=True)
		self.assertEqual(left._width, 20)

	def test_paned_window_sash_coord_before_layout(self):
		# flair saves the sash of notebook pages that were never shown
		root, scr = makeApp(40, 8)
		pw = tk.PanedWindow(root, orient='horizontal')
		pw.add(tk.Label(pw, text='LEFT'))
		pw.add(tk.Label(pw, text='RIGHT'))
		self.assertEqual(pw.sash_coord(0), (4, 0))
		pw.sash_place(0, 12, 0)
		self.assertEqual(pw.sash_coord(0), (12, 0))
		with self.assertRaises(tk.TclError):
			pw.sash_coord(1)

	def test_paned_window_pane_width_overrides_request(self):
		# flair restores its splitters with add(frame, width=saved):
		# like Tk the pane width replaces the (larger) requested width
		root, scr = makeApp(60, 8)
		pw = tk.PanedWindow(root, orient='horizontal')
		pw.pack(fill='both', expand=True)
		left  = tk.Label(pw, text='A very long label that requests a lot')
		right = tk.Label(pw, text='RIGHT')
		pw.add(left, width=10)
		pw.add(right)
		attach(root)
		self.assertEqual(left._width, 10)
		self.assertEqual(pw.sash_coord(0), (10, 0))

	def test_toplevel_tcl_shim(self):
		root, scr = makeApp()
		top = tk.Toplevel(root)
		root.tk.call('wm', 'title', top._w, 'Shim')
		self.assertEqual(top.title(), 'Shim')
		img = tk.PhotoImage(width=4, height=3)
		self.assertEqual(root.tk.call('image', 'width', str(img)), 4)
		self.assertEqual(root.tk.splitlist('a {b c} d'), ('a', 'b c', 'd'))
		self.assertEqual(root.tk.eval('info patchlevel')[:3], '8.6')
		with self.assertRaises(tk.TclError):
			root.tk.call('nosuchcommand')

	def test_font_measure(self):
		from tktext import font
		f = font.Font(family='Sans', size=10, weight='bold')
		self.assertEqual(f.measure('hello'), 5)
		self.assertEqual(f.metrics('linespace'), 1)
		self.assertTrue(font.isBold(('Sans', 10, 'bold')))
		self.assertIn('TkDefaultFont', font.names())

	def test_ttk_style_defaults(self):
		from tktext import ttk
		s = ttk.Style()
		self.assertEqual(s.lookup('TEntry', 'fieldbackground'), '#ffffff')
		s.configure('My.TLabel', foreground='red')
		self.assertEqual(s.lookup('My.TLabel', 'foreground'), 'red')

	def test_ttk_state(self):
		root, scr = makeApp()
		b = tk.Button(root, text='x')
		b.state(['disabled'])
		self.assertEqual(b.cget('state'), 'disabled')
		self.assertTrue(b.instate(['disabled']))
		b.state(['!disabled'])
		self.assertEqual(b.cget('state'), 'normal')


if __name__ == '__main__':
	unittest.main()


class ColorResolveTest(unittest.TestCase):
	"""Pale X11 tints stay pale on 8/16 colour terminals."""

	def resolve(self, name, nColors):
		from tktext._colors import ColorManager
		cm = ColorManager()
		cm._nColors = nColors
		return cm._resolve(name)

	def test_light_yellow_is_not_bright_yellow(self):
		self.assertEqual(self.resolve('LightYellow', 8), 7)
		self.assertEqual(self.resolve('LightYellow', 16), 7)
		self.assertEqual(self.resolve('LightYellow', 256), 230)

	def test_pale_tints_map_to_light_gray(self):
		for name in ('LightCyan', 'LightBlue', 'MistyRose', 'Honeydew'):
			self.assertEqual(self.resolve(name, 16), 7, name)

	def test_ansi_names_unchanged(self):
		self.assertEqual(self.resolve('yellow', 16), 3)
		self.assertEqual(self.resolve('brightyellow', 16), 11)
		self.assertEqual(self.resolve('lightred', 16), 9)
		self.assertEqual(self.resolve('lightmagenta', 8), 5)
		self.assertEqual(self.resolve('#ffffff', 16), 15)


class ColorModeTest(unittest.TestCase):
	"""'terminal' colour mode maps the Tk palette defaults to -1."""

	def setUp(self):
		from tktext import _colors
		self.colors = _colors
		self.saved  = _colors.colorMode()
		_colors.setColorMode('terminal')
		_colors.resetDefaultColors()
		self.cm     = _colors.ColorManager()

	def tearDown(self):
		self.colors.setColorMode(self.saved)
		self.colors.resetDefaultColors()

	def test_tk_defaults_map_to_terminal(self):
		self.assertEqual(self.cm.mapDefaults('black', '#d9d9d9'), ('', ''))
		self.assertEqual(self.cm.mapDefaults('#000000', 'white'), ('', ''))
		self.assertEqual(self.cm.mapDefaults('black', ''), ('', ''))

	def test_explicit_colours_kept(self):
		self.assertEqual(self.cm.mapDefaults('black', 'yellow'), ('black', 'yellow'))
		self.assertEqual(self.cm.mapDefaults('red', '#d9d9d9'), ('red', ''))
		self.assertEqual(self.cm.mapDefaults('#ffffff', '#4a6984'),
			('#ffffff', '#4a6984'))

	def test_set_palette_registers(self):
		root, _ = makeApp()
		self.assertEqual(self.cm.mapDefaults('#eeeeee', '#333333'),
			('#eeeeee', '#333333'))
		root.tk_setPalette(background='#333333', foreground='#eeeeee')
		self.assertEqual(self.cm.mapDefaults('#eeeeee', '#333333'), ('', ''))
		root.destroy()

	def test_style_configure_registers(self):
		from tktext import ttk
		ttk.Style().configure('.', background='#123456')
		self.assertEqual(self.cm.mapDefaults('black', '#123456'), ('', ''))

	def test_pair_built_from_mapped_colours(self):
		# regression: the pair cached under the mapped key ('red', '') was
		# initialised with the original background (white field -> white)
		from unittest import mock
		pairs = {}
		with mock.patch.object(self.colors.curses, 'init_pair',
				side_effect=lambda n, f, b: pairs.__setitem__(n, (f, b))), \
				mock.patch.object(self.colors.curses, 'color_pair',
				side_effect=lambda n: n << 8):
			self.cm._ready   = True
			self.cm._nColors = 256
			a = self.cm.getAttr('red', '#ffffff')
			b = self.cm.getAttr('red', '')
		self.assertEqual(a, b)
		self.assertEqual(pairs[a >> 8][1], -1)

	def test_tk_mode_unchanged(self):
		self.colors.setColorMode('tk')
		self.assertEqual(self.cm.mapDefaults('black', '#d9d9d9'),
			('black', '#d9d9d9'))

	def test_install_env(self):
		script = '\n'.join([
			'import sys; sys.path.insert(0, %r)' % ROOT,
			'import tktext; tktext.install()',
			'from tktext import _colors',
			'print("MODE", _colors.colorMode())'])
		for env, mode in ((None, 'terminal'), ('tk', 'tk')):
			e = dict(os.environ)
			e.pop('TKTEXT_COLORS', None)
			if env:
				e['TKTEXT_COLORS'] = env
			out = subprocess.run([sys.executable, '-c', script], env=e,
				capture_output=True, text=True, timeout=30)
			self.assertIn('MODE ' + mode, out.stdout, out.stderr)


class TerminalBackgroundParseTest(unittest.TestCase):

	def setUp(self):
		from tktext import _termbg, _colors
		self.bg     = _termbg
		self.colors = _colors
		self.env    = {k: os.environ.get(k) for k in ('TKTEXT_BACKGROUND', 'TERM', 'COLORFGBG')}

	def tearDown(self):
		for k, v in self.env.items():
			if v is None:
				os.environ.pop(k, None)
			else:
				os.environ[k] = v
		self.bg.setOverride('auto')
		self.colors.setBackground(None)
		self.colors.resetTheme()

	def test_osc_reply(self):
		p = self.bg.parseOscReply
		self.assertEqual(p(b'\x1b]11;rgb:ffff/ffff/ffff\x1b\\'), (255, 255, 255))
		self.assertEqual(p(b'\x1b]11;rgb:00/00/00\x07'), (0, 0, 0))
		self.assertEqual(p(b'junk\x1b]11;rgb:1e1e/1e1e/2e2e\x1b\\\x1b[?62c'), (30, 30, 46))
		self.assertEqual(p(b'\x1b]11;rgb:f/8/0\x07'), (255, 136, 0))
		self.assertIsNone(p(b'\x1b[?62;22c'))
		self.assertIsNone(p(b''))

	def test_colorfgbg(self):
		p = self.bg.parseColorFgBg
		self.assertFalse(self.bg.isDark(p('0;15')))
		self.assertTrue(self.bg.isDark(p('15;0')))
		self.assertFalse(self.bg.isDark(p('0;default;7')))
		self.assertIsNone(p('default;default'))
		self.assertIsNone(p(''))

	def test_override_and_linux_console(self):
		os.environ.pop('TKTEXT_BACKGROUND', None)
		os.environ['TERM'] = 'linux'
		self.assertEqual(self.bg.detect(), (0, 0, 0))
		self.bg.setOverride('light')
		self.assertEqual(self.bg.detect(), (255, 255, 255))
		os.environ['TKTEXT_BACKGROUND'] = '#202020'		# env wins
		self.assertEqual(self.bg.detect(), (32, 32, 32))
		os.environ['TKTEXT_BACKGROUND'] = 'nonsense'		# ignored
		self.assertEqual(self.bg.detect(), (255, 255, 255))
		with self.assertRaises(ValueError):
			self.bg.setOverride('purple')

	def test_theme_follows_background_but_keeps_user_roles(self):
		c = self.colors
		c.setTheme({'scrollbar.slider': ('', 'red')})
		c.setBackground('dark')
		self.assertEqual(c.getTheme('scrollbar.trough'), ('', '#4e4e4e', ''))
		self.assertEqual(c.getTheme('scrollbar.slider'), ('', 'red', ''))	# user's
		c.setBackground('light')
		self.assertEqual(c.getTheme('scrollbar.trough'), ('', '#c3c3c3', ''))
		self.assertEqual(c.getTheme('frame.active'), ('blue', '', 'bold'))
		c.resetTheme()					# keeps the background
		self.assertEqual(c.getBackground(), 'light')
		self.assertEqual(c.getTheme('frame.active'), ('blue', '', 'bold'))
		self.assertEqual(c.getTheme('scrollbar.slider'), ('', '#8c8c8c', ''))

	def test_entry_background_follows_terminal(self):
		c         = self.colors
		root, scr = makeApp()
		e         = tk.Entry(root)
		s         = tk.Spinbox(root)
		l         = tk.Label(root)
		c.setBackground('dark')
		self.assertEqual(e._color('bg'), '#3a3a3a')
		self.assertEqual(s._color('bg'), '#3a3a3a')
		self.assertEqual(l._color('bg'), '')
		c.setBackground('light')
		self.assertEqual(e._color('bg'), '#e4e4e4')
		e.configure(bg='yellow')				# own option wins
		self.assertEqual(e._color('bg'), 'yellow')
		root.option_add('*Spinbox.background', 'cyan')		# then the database
		self.assertEqual(s._color('bg'), 'cyan')
		c.setTheme(entry=('', 'blue'))
		self.assertEqual(tk.Entry(root)._color('bg'), 'blue')
		root.destroy()


class MenuPixelTest(unittest.TestCase):
	"""Menu.post/tk_popup take screen coordinates like tkinter."""

	def tearDown(self):
		_core.setPixelMode(1, 1)

	def test_post_below_widget_in_pixel_mode(self):
		_core.setPixelMode(8, 16)
		root, scr = makeApp(60, 20)
		b = tk.Button(root, text='Menu')
		b.pack(pady=32)
		m = tk.Menu(root, tearoff=0)
		m.add_command(label='Item')
		attach(root)
		m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
		root._update(force=True)
		self.assertEqual((m._postX, m._postY), (b._x, b._y + b._height))


class ImageAltTest(unittest.TestCase):
	"""Clickable icon-only widgets show the image's alt text."""

	def test_alt_text(self):
		root, scr = makeApp(40, 8)
		img = tk.PhotoImage(width=16, height=16)
		img.alt = 'save'
		tk.Button(root, image=img, command=lambda: None).pack()
		tk.Label(root, image=img).pack()		# decorative: blank
		attach(root)
		self.assertIsNotNone(scr.find(' save '))
		self.assertEqual(scr.text().count('save'), 1)
		self.assertEqual(img.zoom(2).alt, 'save')

	def test_alt_from_file_name(self):
		import tempfile
		gif = b'GIF89a\x10\x00\x10\x00\x00\x00\x00;'
		with tempfile.NamedTemporaryFile(suffix='.gif', prefix='undo_') as f:
			f.write(gif)
			f.flush()
			img = tk.PhotoImage(file=f.name)
		self.assertTrue(img.alt.startswith('undo_'))
		self.assertEqual((img.width(), img.height()), (16, 16))

	def test_icon_with_label_neighbour_is_not_named(self):
		root, scr = makeApp(40, 8)
		img = tk.PhotoImage(width=16, height=16)
		img.alt = 'newicon'
		f = tk.Frame(root)
		f.pack()
		tk.Button(f, image=img, command=lambda: None).grid(row=0, column=0)
		tk.Label(f, text='New').grid(row=0, column=1)
		tk.Button(f, image=img, command=lambda: None).grid(row=1, column=0)
		tk.Label(f, text='▾').grid(row=1, column=1)	# a symbol is no label
		attach(root)
		self.assertEqual(scr.text().count('newicon'), 1)

	def test_icon_glyph(self):
		_core.setPixelMode(8, 16)
		try:
			root, scr = makeApp(40, 8)
			big       = tk.PhotoImage(width=32, height=32)
			big.alt   = 'saveflair32'
			big.glyph = '⤓'
			small       = tk.PhotoImage(width=16, height=16)
			small.alt   = 'TRC'
			small.glyph = '△'
			var = tk.IntVar(root)
			tk.Button(root, image=big, command=lambda: None).pack()
			cb = tk.Checkbutton(root, image=small, variable=var, indicatoron=0)
			cb.pack()
			attach(root)
			text = scr.text()
			self.assertIsNotNone(scr.find('┌─⤓─┐'))	# 32x32: a 5x2 box
			y, x = scr.find('┌─⤓─┐')
			self.assertIsNotNone(scr.find('└───┘'))
			self.assertEqual(scr.find('└───┘'), (y + 1, x))
			self.assertIn('△', text)
			self.assertNotIn('saveflair32', text)
			self.assertNotIn('TRC', text)
			self.assertEqual(cb._width, 2)		# small glyph: two cells
		finally:
			_core.setPixelMode(1, 1)

	def test_framed_icon_glyph_is_not_padded(self):
		_core.setPixelMode(8, 16)
		try:
			root, scr = makeApp(40, 8)
			img       = tk.PhotoImage(width=16, height=16)
			img.glyph = '+'
			tk.Button(root, image=img, command=lambda: None).pack()
			tk.Label(root, image=img, relief='single', borderwidth=1).pack()
			attach(root)
			self.assertIsNotNone(scr.find('[+]'))	# brackets frame it
			self.assertIsNotNone(scr.find('│+│'))	# a drawn border
		finally:
			_core.setPixelMode(1, 1)


class FocusCompatTest(unittest.TestCase):

	def test_click_on_button_keeps_focus_in_pixel_mode(self):
		_core.setPixelMode(8, 16)
		try:
			root, scr = makeApp(40, 10)
			e = tk.Entry(root)
			e.pack()
			b = tk.Button(root, text='Push')
			b.pack()
			attach(root)
			e.focus_set()
			y, x = scr.find('Push')
			click(root, x + 1, y)
			self.assertIs(root.focus_get(), e)
		finally:
			_core.setPixelMode(1, 1)

	def test_focus_returns_after_temporary_unmap(self):
		root, scr = makeApp(40, 10)
		other = tk.Entry(root)
		other.pack()
		page = tk.Frame(root)
		page.pack()
		t = tk.Text(page, width=10, height=2)
		t.pack()
		attach(root)
		t.focus_set()
		page.pack_forget()			# page rebuilt ...
		root._update(force=True)
		self.assertIsNot(root.focus_get(), t)
		page.pack()				# ... and shown again
		root._update(force=True)
		self.assertIs(root.focus_get(), t)

	def test_focus_set_while_dialog_open_is_remembered(self):
		root, scr = makeApp(40, 10)
		e = tk.Entry(root)
		e.pack()
		dlg = tk.Toplevel(root)
		dlg.transient(root)
		tk.Entry(dlg).pack()
		attach(root)
		e.focus_set()				# while the dialog is active
		root._update(force=True)
		self.assertTrue(dlg._isAncestorOf(root.focus_get()))
		dlg.destroy()
		root._update(force=True)
		self.assertIs(root.focus_get(), e)


class ClipboardTest(unittest.TestCase):
	"""One buffer per type like Tk (flair keeps text and pickled cards)."""

	def test_typed_buffers(self):
		root, scr = makeApp(40, 12)
		root.clipboard_clear()
		root.clipboard_append('CARD text')
		root.clipboard_append(b'8c0a', type='application/x-card')
		self.assertEqual(root.clipboard_get(), 'CARD text')
		self.assertEqual(root.selection_get(selection='CLIPBOARD',
			type='UTF8_STRING'), 'CARD text')
		self.assertEqual(root.selection_get(selection='CLIPBOARD',
			type='application/x-card'), '8c0a')
		targets = root.selection_get(selection='CLIPBOARD', type='TARGETS')
		self.assertIn('application/x-card', targets)
		self.assertIn('STRING', targets)
		root.clipboard_clear()
		self.assertRaises(tk.TclError, root.clipboard_get)
		self.assertRaises(tk.TclError, root.clipboard_get, type='TARGETS')


class RawKeysTest(unittest.TestCase):
	"""Raw tty: Ctrl-C / Ctrl-Z are keys; unbound Ctrl-C closes the window."""

	def test_bound_and_unbound(self):
		root, scr = makeApp(40, 12)
		e = tk.Entry(root)
		e.pack()
		attach(root)
		e.focus_set()
		got = []
		e.bind('<Control-c>', lambda ev: got.append('copy'))
		e.bind('<Control-z>', lambda ev: got.append('undo'))
		root._handleInput(3)
		root._handleInput(26)
		self.assertEqual(got, ['copy', 'undo'])
		self.assertFalse(root._quit)
		e.unbind('<Control-c>')
		root._handleInput(3)
		self.assertTrue(root._quit)


class SystemClipboardTest(unittest.TestCase):
	"""The STRING format follows the system clipboard (_sysclip)."""

	def setUp(self):
		from tktext import _sysclip
		self.sysclip = _sysclip
		self.saved   = (_sysclip.copy, _sysclip.paste)
		self.system  = ['']
		_sysclip.copy  = lambda text: self.system.__setitem__(0, text) or True
		_sysclip.paste = lambda: self.system[0]
		self.root, scr  = makeApp(40, 12)
		self.root._ownScreen = True	# as if on a real terminal

	def tearDown(self):
		self.root._ownScreen = False
		self.sysclip.copy, self.sysclip.paste = self.saved

	def test_copy_reaches_system(self):
		root = self.root
		root.clipboard_clear()
		root.clipboard_append('TITLE')
		root.clipboard_append(b'8c0a', type='application/x-card')
		self.assertEqual(self.system[0], 'TITLE')
		# still our own text: the typed buffer is kept
		self.assertIn('application/x-card',
			root.selection_get(selection='CLIPBOARD', type='TARGETS'))

	def test_foreign_text_replaces_buffers(self):
		root = self.root
		root.clipboard_clear()
		root.clipboard_append('TITLE')
		root.clipboard_append(b'8c0a', type='application/x-card')
		self.system[0] = 'from outside'
		targets = root.selection_get(selection='CLIPBOARD', type='TARGETS')
		self.assertNotIn('application/x-card', targets)
		self.assertEqual(root.clipboard_get(), 'from outside')

	def test_osc52(self):
		seq = self.sysclip.osc52('hi', term='xterm', screen=False)
		self.assertEqual(seq, b'\x1b]52;c;aGk=\x07')
		seq = self.sysclip.osc52('hi', term='screen-256color', screen=True)
		self.assertEqual(seq, b'\x1bP\x1b]52;c;aGk=\x07\x1b\\')
