"""tkinter API compatibility found by comparing with the Python 3.14
tkinter: configure() queries, option checks, Entry validation and bbox,
Tcl(), Menubutton, scrolledtext, dialogs, after(**kw), Text.count,
tkinter parameter names and the Tk patchlevel."""
import os
import subprocess
import sys
import unittest

from fakescreen import makeApp, press, click
import tktext as tk
from tktext import ttk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigureTest(unittest.TestCase):

	def test_query_one_option(self):
		root, _ = makeApp()
		b = tk.Button(root, text='OK')
		self.assertEqual(b.configure('text'), ('text', 'text', 'Text', '', 'OK'))
		self.assertEqual(b.config('-text')[-1], 'OK')
		self.assertEqual(b.configure('bd'), ('bd', '-borderwidth'))
		name, dbName, dbClass, default, value = b.configure('borderwidth')
		self.assertEqual((dbName, dbClass, value), ('borderWidth', 'BorderWidth', 1))
		self.assertEqual(b.configure('background')[:3],
			('background', 'background', 'Background'))

	def test_query_all_options(self):
		root, _ = makeApp()
		e = tk.Entry(root, width=12)
		cfg = e.configure()
		self.assertEqual(cfg['width'][-1], 12)
		self.assertEqual(cfg['bd'], ('bd', '-borderwidth'))
		self.assertIn('validatecommand', cfg)
		self.assertIn('highlightthickness', e.keys())
		self.assertEqual(sorted(e.keys()), e.keys())

	def test_unknown_option_raises(self):
		root, _ = makeApp()
		b = tk.Button(root)
		with self.assertRaises(tk.TclError) as ctx:
			b.configure(foobar=1)
		self.assertIn('unknown option "-foobar"', str(ctx.exception))
		with self.assertRaises(tk.TclError):
			tk.Label(root, nosuch=1)
		with self.assertRaises(tk.TclError):
			b.cget('nosuch')
		# a Tk option tktext does not draw is still accepted
		b.configure(highlightthickness=2, repeatdelay=300)
		self.assertEqual(b.cget('repeatdelay'), 300)
		self.assertEqual(ttk.Button(root, style='X.TButton').cget('style'), 'X.TButton')

	def test_trailing_underscore_options(self):
		"""tkinter strips a trailing '_' of any option name (to_=)."""
		root, _ = makeApp()
		s = tk.Spinbox(root, from_=1, to_=100)
		self.assertEqual(s.cget('to'), 100)
		self.assertEqual(s.cget('from'), 1)
		sc = tk.Scale(root, to_=50)
		self.assertEqual(sc.cget('to'), 50)
		with self.assertRaises(tk.TclError):
			tk.Label(root, nosuch_=1)

	def test_abbreviated_options(self):
		root, _ = makeApp()
		f = tk.Frame(root, border=3)
		self.assertEqual(f.cget('borderwidth'), 3)
		self.assertEqual(f.cget('border'), 3)
		with self.assertRaises(tk.TclError) as ctx:
			tk.Button(root, a=1)	# activebackground, activeforeground, anchor
		self.assertIn('ambiguous', str(ctx.exception))

	def test_class_option(self):
		root, _ = makeApp()
		f = tk.Frame(root, class_='MyFrame')
		self.assertEqual(f.winfo_class(), 'MyFrame')
		self.assertEqual(f.cget('class'), 'MyFrame')
		top = tk.Toplevel(root, class_='MyTop')
		self.assertIsNone(top.configure(class_='Other'))

	def test_tcl_configure_and_winfo(self):
		root, _ = makeApp()
		lbl = tk.Label(root, text='a')
		root.tk.call(lbl._w, 'configure', '-text', 'b')
		self.assertEqual(lbl.cget('text'), 'b')
		self.assertEqual(root.tk.call(lbl._w, 'cget', '-text'), 'b')
		self.assertEqual(root.tk.call(lbl._w, 'configure', '-text')[-1], 'b')
		self.assertEqual(root.tk.call('winfo', 'exists', lbl._w), 1)
		self.assertEqual(root.tk.call('winfo', 'class', lbl._w), 'Label')
		self.assertEqual(root.tk.call('winfo', 'exists', '.nosuch'), 0)


class EntryTest(unittest.TestCase):

	def test_bbox(self):
		root, _ = makeApp()
		e = tk.Entry(root, borderwidth=0)
		e.pack()
		e.insert(0, 'hello')
		root._update()
		self.assertEqual(e.bbox(1), (1, 0, 1, 1))
		self.assertEqual(ttk.Combobox(root).bbox(0)[2:], (0, 1))

	def test_key_validation(self):
		root, _ = makeApp()
		calls = []

		def digits(new, action, why):
			calls.append((new, action, why))
			return new.isdigit() or new == ''

		e = tk.Entry(root, validate='key')
		e.configure(validatecommand=(e.register(digits), '%P', '%d', '%V'))
		e.pack()
		root._update()
		e.focus_set()
		press(root, '12a3')
		self.assertEqual(e.get(), '123')
		self.assertIn(('12a', '1', 'key'), calls)
		e.insert('end', 'x')			# programmatic edits are validated too
		self.assertEqual(e.get(), '123')
		e.delete(0)
		self.assertEqual(e.get(), '23')
		self.assertEqual(calls[-1], ('23', '0', 'key'))

	def test_invalidcommand_and_focus(self):
		root, _ = makeApp()
		log = []
		e1 = tk.Entry(root, validate='focusout',
			validatecommand=lambda: log.append('vcmd') or False,
			invalidcommand=lambda: log.append('invalid'))
		e2 = tk.Entry(root)
		e1.pack()
		e2.pack()
		root._update()
		e1.focus_set()
		press(root, 'x')			# no key validation in focusout mode
		self.assertEqual(e1.get(), 'x')
		e2.focus_set()
		root._update()
		self.assertEqual(log, ['vcmd', 'invalid'])

	def test_validation_error_disables_it(self):
		root, _ = makeApp()
		e = tk.Entry(root, validate='all', validatecommand=lambda: 1 / 0)
		e.insert(0, 'abc')
		self.assertEqual(e.get(), 'abc')
		self.assertEqual(e.cget('validate'), 'none')

	def test_tkinter_parameter_names(self):
		root, _ = makeApp()
		e = tk.Entry(root)
		e.insert(index=0, string='abc')
		e.icursor(index=1)
		self.assertEqual(e.index(index='insert'), 1)
		t = tk.Text(root)
		t.insert(index='1.0', chars='hello')
		t.tag_add('t', '1.0', '1.2')
		self.assertEqual(t.tag_ranges(tagName='t')[0], '1.0')
		self.assertEqual(t.get(index1='1.0', index2='1.2'), 'he')
		t.mark_set(markName='m', index='1.3')
		self.assertEqual(t.index(index='m'), '1.3')
		lb = tk.Listbox(root)
		lb.insert('end', 'a')
		lb.see(index=0)
		self.assertEqual(lb.get(0), 'a')
		b = tk.Button(root)
		fid = b.bind(sequence='<Return>', func=lambda e: None)
		b.unbind(sequence='<Return>', funcid=fid)


class MiscTest(unittest.TestCase):

	def test_patchlevel(self):
		root, _ = makeApp()
		self.assertEqual(root.tk.call('info', 'patchlevel'), '8.6.18')
		info = root.info_patchlevel()
		self.assertEqual((info.major, info.minor, info.micro), (8, 6, 18))
		self.assertEqual(tk.TkVersion, 8.6)

	def test_after_kwargs_and_info(self):
		root, _ = makeApp()
		got = []
		aid = root.after(0, lambda a, b=0: got.append((a, b)), 1, b=2)
		self.assertIn(aid, root.after_info())
		self.assertEqual(root.after_info(aid)[1], 'timer')
		root.after_idle(lambda x=0: got.append(x), x=5)
		root._fireAfterCallbacks()
		self.assertEqual(got, [(1, 2), 5])
		with self.assertRaises(tk.TclError):
			root.after_info(aid)

	def test_text_count(self):
		root, _ = makeApp()
		t = tk.Text(root)
		t.insert('1.0', 'abc\ndef')
		self.assertEqual(t.count('1.0', '2.1'), (5,))
		self.assertEqual(t.count('1.0', '2.1', return_ints=True), 5)
		self.assertEqual(t.count('1.0', '2.1', 'lines', return_ints=True), 1)
		self.assertEqual(t.count('1.0', '2.1', 'chars', 'lines'), (5, 1))
		self.assertIsNone(t.count('1.0', '1.0'))

	def test_tcl_interpreter(self):
		interp = tk.Tcl()
		self.assertEqual(interp.splitlist('a {b c}'), ('a', 'b c'))
		self.assertEqual(interp.eval('info patchlevel'), '8.6.18')
		self.assertTrue(interp.getboolean('yes'))
		interp.loadtk()

	def test_mixin_names_and_eventtype(self):
		root, _ = makeApp()
		self.assertIsInstance(tk.Label(root), tk.Pack)
		self.assertEqual(tk.EventType.Activate, 'Activate')

	def test_photoimage_copy(self):
		img = tk.PhotoImage(width=10, height=6)
		self.assertEqual(img.zoom(2).width(), 20)
		self.assertEqual(img.subsample(2, 3).height(), 2)
		self.assertEqual(img.copy(from_coords=(2, 1)).width(), 8)
		dst = tk.PhotoImage(width=2, height=2)
		dst.copy_replace(img, to=(1, 1))
		self.assertEqual((dst.width(), dst.height()), (11, 7))


class WidgetModuleTest(unittest.TestCase):

	def test_menubutton_posts_menu(self):
		root, _ = makeApp()
		mb = tk.Menubutton(root, text='File')
		menu = tk.Menu(mb, tearoff=0)
		menu.add_command(label='Open')
		mb.configure(menu=menu)
		mb.pack()
		root._update()
		self.assertIn('▼', mb._rawText())
		click(root, mb._x, mb._y, 'press')
		self.assertTrue(menu._posted)
		self.assertEqual(menu._postY, mb._y + mb._height)
		self.assertIs(ttk.Menubutton, tk.Menubutton)

	def test_ttk_optionmenu_default(self):
		root, _ = makeApp()
		var = tk.StringVar(root)
		om  = ttk.OptionMenu(root, var, 'b', 'a', 'b', 'c')
		self.assertEqual(var.get(), 'b')
		self.assertEqual(om._values, ['a', 'b', 'c'])
		om.set_menu('c', 'x', 'c')
		self.assertEqual((var.get(), om._values), ('c', ['x', 'c']))

	def test_scrolledtext(self):
		from tktext.scrolledtext import ScrolledText
		root, _ = makeApp()
		st = ScrolledText(root, height=5)
		st.pack(fill='both', expand=True)
		st.insert('end', '\n'.join(str(i) for i in range(50)))
		root._update()
		self.assertEqual(st.frame.winfo_manager(), 'pack')
		self.assertEqual(str(st), str(st.frame))
		self.assertTrue(callable(st.vbar.cget('command')))

	def test_install_new_modules(self):
		script = '\n'.join([
			'import sys; sys.path.insert(0, %r)' % ROOT,
			'import tktext; tktext.install()',
			'import tkinter, tkinter.scrolledtext, tkinter.commondialog, tkinter.dialog',
			'from tkinter import filedialog, messagebox, colorchooser',
			'assert tkinter.scrolledtext.ScrolledText and tkinter.Menubutton',
			'assert issubclass(filedialog.Open, tkinter.commondialog.Dialog)',
			'assert issubclass(messagebox.Message, tkinter.commondialog.Dialog)',
			'assert filedialog.askopenfiles and filedialog.Directory and colorchooser.Chooser',
			'print("NEW-MODULES-OK")'])
		out = subprocess.run([sys.executable, '-c', script],
			capture_output=True, text=True, timeout=30)
		self.assertIn('NEW-MODULES-OK', out.stdout, out.stderr)

	def test_dnd_handler_never_starts(self):
		# flair's InputPage: subclass, then 'h if h.root else None'
		from tktext import dnd
		root, _ = makeApp()

		class Handler(dnd.DndHandler):
			def on_motion(self, event):
				super().on_motion(event)
				return 'break'

		h = Handler(tk.Label(root), tk.Event())
		self.assertIsNone(h.root)
		self.assertEqual(h.on_motion(tk.Event()), 'break')
		h.on_release(tk.Event())
		self.assertIsNone(dnd.dnd_start(root, tk.Event()))


if __name__ == '__main__':
	unittest.main()
