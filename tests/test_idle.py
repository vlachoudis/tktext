"""tkinter features used by idlelib: widget command redirection (rename +
createcommand), Tcl word breaks, binding scripts, None arguments, Text
index arithmetic at the end and the <3> button shorthand."""
import unittest

from fakescreen import makeApp, attach, press, tk
from tktext._events import KeyEvent, KEY_BACKSPACE


class RedirectorTest(unittest.TestCase):
	"""idlelib.redirector.WidgetRedirector: the Text command is renamed
	and replaced by a Python command that sees every insert/delete."""

	def setUp(self):
		self.root, self.scr = makeApp()
		self.text = tk.Text(self.root)
		self.text.pack()
		attach(self.root)
		self.text.focus_set()
		self.seen = []
		t     = self.text
		w     = t._w
		orig  = w + '_orig'
		t.tk.call('rename', w, orig)

		def dispatch(op, *args):
			self.seen.append((op,) + args)
			return t.tk.call((orig, op) + args)

		t.tk.createcommand(w, dispatch)
		# WidgetRedirector.register(): the instance attribute masks the method
		t.insert = lambda *args: dispatch('insert', *args)
		t.delete = lambda *args: dispatch('delete', *args)

	def test_typing_goes_through_the_command(self):
		press(self.root, 'ab', 10)
		self.assertEqual([s[0] for s in self.seen], ['insert'] * 3)
		self.assertEqual(self.seen[0], ('insert', 'insert', 'a'))
		self.assertEqual(self.text.get('1.0', 'end-1c'), 'ab\n')

	def test_queries_go_through_the_command(self):
		# like tkinter: idlelib's dispatch returns "" on a TclError, so
		# search.find() works without a selection
		t = self.text
		t.tk.deletecommand(t._w)

		def dispatch(op, *args):
			self.seen.append((op,) + args)
			try:
				return t.tk.call((t._w + '_orig', op) + args)
			except tk.TclError:
				return ''

		t.tk.createcommand(t._w, dispatch)
		t.insert('1.0', 'hello')
		self.seen.clear()
		self.assertEqual(t.get('sel.first', 'sel.last'), '')
		self.assertEqual(t.index('sel.first'), '')
		self.assertEqual(t.get('1.0', '1.2'), 'he')
		self.assertTrue(t.compare('1.0', '<', '1.2'))
		self.assertEqual([s[0] for s in self.seen],
			['get', 'index', 'get', 'compare'])

	def test_backspace_and_selection_go_through_the_command(self):
		press(self.root, 'abc')
		self.seen.clear()
		press(self.root, KEY_BACKSPACE)
		self.assertEqual(self.seen, [('delete', 'insert-1c')])
		self.text.tag_add('sel', '1.0', '1.2')
		self.seen.clear()
		press(self.root, 'x')
		self.assertEqual(self.seen, [('delete', 'sel.first', 'sel.last'),
			('insert', 'insert', 'x')])
		self.assertEqual(self.text.get('1.0', 'end-1c'), 'x')

	def test_original_command_uses_the_class_methods(self):
		# the masked instance attribute would recurse forever
		self.text.insert('1.0', 'hello')
		self.assertEqual(self.text.get('1.0', 'end-1c'), 'hello')

	def test_widget_path_is_hidden_after_rename_and_restored(self):
		t = self.text
		t.tk.deletecommand(t._w)
		with self.assertRaises(tk.TclError):
			t.tk.call(t._w, 'index', 'end')
		t.tk.call('rename', t._w + '_orig', t._w)
		self.assertEqual(str(t.tk.call(t._w, 'index', 'end')), '2.0')
		with self.assertRaises(tk.TclError):
			t.tk.call(t._w + '_orig', 'index', 'end')


class TclCompatTest(unittest.TestCase):

	def test_set_and_word_breaks(self):
		root, scr = makeApp()
		tcl = root.tk
		self.assertEqual(tcl.call('set', 'v', 'x'), 'x')
		self.assertEqual(tcl.call('set', 'v'), 'x')
		self.assertEqual(tcl.call('tcl_wordBreakAfter', 'a b', 0), 1)
		self.assertEqual(tcl.call('tcl_wordBreakAfter', 'ab cd', 2), 3)
		self.assertEqual(tcl.call('tcl_wordBreakAfter', 'abc', 0), -1)
		self.assertEqual(tcl.call('tcl_wordBreakBefore', 'ab cd', 4), 3)

	def test_none_arguments_are_dropped(self):
		root, scr = makeApp()
		self.assertEqual(root.tk.call('set', 'w', 'y', None), 'y')
		t = tk.Text(root)
		t.insert('1.0', 'abc', None)
		t.tag_add('x', '1.1', None)
		self.assertEqual([str(i) for i in t.tag_ranges('x')], ['1.1', '1.2'])

	def test_windowingsystem(self):
		root, scr = makeApp()
		self.assertEqual(root._windowingsystem, 'x11')

	def test_simpledialog_private_helpers(self):
		from tktext.simpledialog import _setup_dialog, _place_window
		root, scr = makeApp()
		top = tk.Toplevel(root)
		_setup_dialog(top)
		_place_window(top, root)


class BindingScriptTest(unittest.TestCase):

	def test_query_returns_a_string_and_scripts_are_ignored(self):
		# idlelib: 'catch {%W delete sel.first sel.last}\n' + bind_class(...)
		root, scr = makeApp()
		e = tk.Entry(root)
		self.assertEqual(e.bind('<<Paste>>'), '')
		e.bind('<<Paste>>', lambda ev: None)
		script = e.bind('<<Paste>>')
		self.assertIsInstance(script, str)
		self.assertTrue(script)
		self.assertEqual(root.bind_class('Text', '<<Paste>>', 'catch {}\n' + script), '')
		self.assertEqual(e.bind('<<Paste>>'), script)


class TextEndTest(unittest.TestCase):

	def test_lines_past_the_end_and_dlineinfo(self):
		root, scr = makeApp()
		t = tk.Text(root)
		t.pack()
		t.insert('1.0', 'a\nb')
		attach(root)
		self.assertEqual(t.index('1.0+1line'), '2.0')
		self.assertEqual(t.index('2.1+1line'), '3.0')
		self.assertEqual(t.index('2.0+5lines'), '3.0')
		self.assertEqual(t.index('2.1-1line'), '1.1')
		self.assertIsNotNone(t.dlineinfo('2.0'))
		self.assertIsNone(t.dlineinfo('end'))


class ButtonShorthandTest(unittest.TestCase):

	def test_digit_key_does_not_match_button_shorthand(self):
		pats = KeyEvent(ord('3')).patterns()
		self.assertNotIn('<3>', pats)
		self.assertIn('<Key-3>', pats)
		self.assertIn('3', pats)
		self.assertIn('<7>', KeyEvent(ord('7')).patterns())

	def test_typing_3_does_not_fire_button_3(self):
		root, scr = makeApp()
		e = tk.Entry(root)
		e.pack()
		attach(root)
		e.focus_set()
		fired = []
		e.bind('<3>', lambda ev: fired.append(ev))
		press(root, '3')
		self.assertEqual(fired, [])
		self.assertEqual(e.get(), '3')


class EventTypeTest(unittest.TestCase):
	"""idlelib configdialog: event.type.name of a tkinter.EventType"""

	def test_type_is_an_event_type(self):
		e = tk.Event()
		e.type = 'KeyRelease'
		self.assertIs(e.type, tk.EventType.KeyRelease)
		self.assertEqual(e.type.name, 'KeyRelease')
		self.assertEqual(e.type, 'KeyRelease')		# still a str internally
		self.assertEqual(str(e.type), 'KeyRelease')
		for seq, name in (('<Control-Key-x>', 'KeyPress'), ('<3>', 'ButtonPress'),
				('<B1-Motion>', 'Motion'), ('<<Paste>>', 'VirtualEvent'),
				('<Double-Button-1>', 'ButtonPress')):
			e.type = seq
			self.assertEqual(e.type.name, name, seq)

	def test_bound_events_carry_the_enum(self):
		root, scr = makeApp()
		lb = tk.Listbox(root)
		lb.pack()
		lb.insert('end', 'a', 'b')
		attach(root)
		lb.focus_set()
		names = []
		lb.bind('<KeyRelease-Down>', lambda ev: names.append(ev.type.name))
		lb.bind('<Key>', lambda ev: names.append(ev.type.name))
		press(root, 258)
		self.assertEqual(names, ['KeyPress', 'KeyRelease'])


class TclGlobalsTest(unittest.TestCase):
	"""idlelib help_about: root.getvar('tk_patchLevel'), info_patchlevel()"""

	def test_standard_globals(self):
		root, scr = makeApp()
		self.assertEqual(root.getvar('tk_patchLevel'), '8.6.18')
		self.assertEqual(root.tk.getvar('tcl_version'), '8.6')
		self.assertEqual(root.tk.call('set', 'tk_version'), '8.6')
		self.assertEqual(root.tk.call('info', 'patchlevel'), root.getvar('tcl_patchLevel'))

	def test_globals_are_per_interpreter(self):
		a, scr = makeApp()
		a.setvar('tk_strictMotif', 1)
		b, scr = makeApp()
		self.assertEqual(b.getvar('tk_strictMotif'), 0)

	def test_root_delegates_to_the_interpreter(self):
		root, scr = makeApp()
		self.assertEqual(root.globalgetvar('tk_patchLevel'), '8.6.18')
		with self.assertRaises(AttributeError):
			root.noSuchAttribute
		self.assertFalse(hasattr(root, '_noSuchPrivate'))

	def test_patchlevel_str(self):
		root, scr = makeApp()
		self.assertEqual(str(root.info_patchlevel()), '8.6.18')
		self.assertEqual(root.info_patchlevel()[:3], (8, 6, 18))


if __name__ == '__main__':
	unittest.main()
