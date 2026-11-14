import unittest

from fakescreen import makeApp, attach, press, click, tk


class KeyEventTest(unittest.TestCase):

	def test_keysym_and_char(self):
		evt = tk.Event()
		from tktext._events import KeyEvent
		e = KeyEvent(ord('q'))
		self.assertEqual((e.keysym, e.char), ('q', 'q'))
		self.assertEqual(KeyEvent(ord('.')).keysym, 'period')
		self.assertIn('<Control-s>', KeyEvent(19).patterns())
		self.assertIn('<Return>', KeyEvent(10).patterns())
		self.assertIn('q', KeyEvent(ord('q')).patterns())
		del evt

	def test_widget_binding_runs_before_class_and_can_break(self):
		root, scr = makeApp()
		e = tk.Entry(root); e.pack()
		attach(root)
		e.focus_set()
		seen = []
		e.bind('<Key>', lambda ev: seen.append(ev.char))
		press(root, 'ab')
		self.assertEqual(seen, ['a', 'b'])
		self.assertEqual(e.get(), 'ab')
		e.bind('<x>', lambda ev: 'break')
		press(root, 'x')
		self.assertEqual(e.get(), 'ab')

	def test_return_binding_fires_once(self):
		root, scr = makeApp()
		e = tk.Entry(root); e.pack()
		attach(root)
		e.focus_set()
		count = []
		e.bind('<Return>', lambda ev: count.append(1))
		press(root, 10)
		self.assertEqual(len(count), 1)

	def test_unconsumed_key_bubbles_to_root(self):
		root, scr = makeApp()
		b = tk.Button(root, text='b'); b.pack()
		attach(root)
		got = []
		root.bind('<Key>', lambda ev: got.append(ev.keysym))
		press(root, 'q')
		self.assertEqual(got, ['q'])

	def test_control_binding(self):
		root, scr = makeApp()
		tk.Button(root, text='b').pack()
		attach(root)
		got = []
		root.bind('<Control-s>', lambda ev: got.append('save'))
		press(root, 19)
		self.assertEqual(got, ['save'])

	def test_tab_traversal_and_override(self):
		root, scr = makeApp()
		a = tk.Button(root, text='a'); a.pack()
		b = tk.Button(root, text='b'); b.pack()
		attach(root)
		self.assertIs(root.focus_get(), a)
		press(root, 9)
		self.assertIs(root.focus_get(), b)
		press(root, 353)
		self.assertIs(root.focus_get(), a)
		a.bind('<Tab>', lambda ev: 'break')
		press(root, 9)
		self.assertIs(root.focus_get(), a)

	def test_event_generate_virtual(self):
		root, scr = makeApp()
		f = tk.Frame(root)
		got = []
		f.bind('<<Custom>>', lambda ev: got.append(ev.widget))
		f.event_generate('<<Custom>>')
		self.assertEqual(got, [f])


class MouseTest(unittest.TestCase):

	def _button(self):
		root, scr = makeApp(30, 6)
		hits = []
		b = tk.Button(root, text='OK', command=lambda: hits.append(1)); b.pack()
		attach(root)
		return root, b, hits

	def test_click_invokes_once(self):
		root, b, hits = self._button()
		click(root, b._x + 1, b._y + 1)
		self.assertEqual(hits, [1])

	def test_press_release_invokes_on_release(self):
		root, b, hits = self._button()
		click(root, b._x + 1, b._y + 1, 'press')
		self.assertEqual(hits, [])
		click(root, b._x + 1, b._y + 1, 'release')
		self.assertEqual(hits, [1])

	def test_release_outside_cancels(self):
		root, b, hits = self._button()
		click(root, b._x + 1, b._y + 1, 'press')
		click(root, 0, 5, 'release')
		self.assertEqual(hits, [])
		self.assertIsNone(root._dragWidget)

	def test_orphan_release_is_dropped(self):
		root, b, hits = self._button()
		click(root, b._x + 1, b._y + 1, 'release')
		self.assertEqual(hits, [])

	def _lostReleaseDialog(self):
		"""A press in a Text whose release never arrives, then a modal
		transient dialog with a button (flair's quit dialog)."""
		root, scr = makeApp(60, 20)
		t = tk.Text(root); t.pack(fill='both', expand=True)
		attach(root)
		click(root, t._x + 2, t._y + 2, 'press')	# release is lost
		self.assertIs(root._dragWidget, t)
		hits = []
		dlg  = tk.Toplevel(root)
		dlg.transient(root)
		b = tk.Button(dlg, text='Discard', command=lambda: hits.append(1))
		b.pack()
		dlg.grab_set()
		root.update()
		return root, t, b, hits

	def test_lost_release_click_reaches_grab_dialog(self):
		root, t, b, hits = self._lostReleaseDialog()
		click(root, b._x + 1, b._y)
		self.assertEqual(hits, [1])
		self.assertFalse(t._mouseDown)

	def test_lost_release_press_release_reaches_grab_dialog(self):
		root, t, b, hits = self._lostReleaseDialog()
		click(root, b._x + 1, b._y, 'press')
		click(root, b._x + 1, b._y, 'release')
		self.assertEqual(hits, [1])

	def test_resent_press_keeps_drag_in_same_window(self):
		# terminals that re-send BUTTON1_PRESSED on motion keep the drag
		root, scr = makeApp(60, 20)
		t = tk.Text(root); t.pack(fill='both', expand=True)
		t.insert('1.0', 'hello world\n')
		attach(root)
		click(root, t._x, t._y, 'press')
		click(root, t._x + 5, t._y, 'press')
		self.assertIs(root._dragWidget, t)
		click(root, t._x + 5, t._y, 'release')
		self.assertTrue(t.tag_ranges('sel'))

	def test_user_button_binding_on_class_widget(self):
		root, scr = makeApp(30, 12)
		lb = tk.Listbox(root, height=3); lb.pack()
		lb.insert('end', 'a', 'b')
		attach(root)
		got = []
		lb.bind('<Button-1>', lambda ev: got.append((ev.x, ev.y)))
		lb.bind('<Double-Button-1>', lambda ev: got.append('double'))
		click(root, lb._x + 2, lb._y + 1)
		click(root, lb._x + 2, lb._y + 1, 'double')
		self.assertEqual(got, [(2, 1), 'double'])

	def test_mouse_state_is_tk_modifiers(self):
		# the raw curses bstate must not leak into event.state:
		# BUTTON1_CLICKED (0x4) would read as Control, RELEASED (0x1)
		# as Shift (flair's InputEditor toggled the card selection)
		root, scr = makeApp(30, 12)
		t = tk.Text(root); t.pack(fill='both', expand=True)
		t.insert('1.0', 'hello world\n')
		attach(root)
		got = []
		t.bind('<Button-1>',        lambda ev: got.append(('press', ev.state)))
		t.bind('<ButtonRelease-1>', lambda ev: got.append(('release', ev.state)))
		t.bind('<B1-Motion>',       lambda ev: got.append(('motion', ev.state)))
		click(root, t._x + 1, t._y)
		click(root, t._x + 1, t._y, 'press')
		click(root, t._x + 3, t._y, 'motion')
		click(root, t._x + 3, t._y, 'release')
		# a CLICKED report: no modifier bits on either event
		self.assertEqual(got[:2], [('press', 0), ('release', got[1][1])])
		self.assertEqual(got[1][1] & 0xff, 0)
		self.assertEqual(got[2:], [('press', 0), ('motion', 0x100),
			('release', 0x100)])

	def test_release_moved_reports_motion(self):
		# curses drops the motion reported just before a quick release:
		# a drag release at a new position delivers <B1-Motion> first
		# (flair InputEditor tab markers are placed labels inside a Text)
		root, scr = makeApp(30, 12)
		t   = tk.Text(root); t.pack(fill='both', expand=True)
		lbl = tk.Label(t, text='V')
		lbl.place(x=4, y=0)
		attach(root)
		got = []
		lbl.bind('<B1-Motion>',       lambda ev: got.append(('motion', ev.x_root)))
		lbl.bind('<ButtonRelease-1>', lambda ev: got.append(('release', ev.x_root)))
		x, y = lbl._x, lbl._y
		click(root, x, y, 'press')
		click(root, x + 2, y, 'motion')
		click(root, x + 5, y, 'release')
		self.assertEqual(got, [('motion', x + 2), ('motion', x + 5),
			('release', x + 5)])
		# released where the last motion was: no extra motion
		del got[:]
		click(root, x, y, 'press')
		click(root, x + 1, y, 'motion')
		click(root, x + 1, y, 'release')
		self.assertEqual(got, [('motion', x + 1), ('release', x + 1)])

	def test_mouse_state_modifiers(self):
		import curses
		from tktext._events import mouseState
		self.assertEqual(mouseState(curses.BUTTON1_CLICKED), 0)
		self.assertEqual(mouseState(curses.BUTTON1_RELEASED), 0)
		self.assertEqual(mouseState(curses.BUTTON1_PRESSED |
			curses.BUTTON_CTRL), 0x4)
		self.assertEqual(mouseState(curses.BUTTON1_PRESSED |
			curses.BUTTON_SHIFT), 0x1)


	def test_modified_click_bindings(self):
		"""<Shift-Button-1>/<Control-1> fire for modified clicks, and a
		plain <Button-1> still catches them when they are not bound."""
		import curses
		root, scr = makeApp(30, 20)
		for cls in (tk.Text, tk.Listbox, tk.Canvas):
			w = cls(root, width=10, height=2)
			w.pack()
		attach(root)
		for w in root.winfo_children():
			seen = []
			w.bind('<Button-1>', lambda e: seen.append(('B1', e.state & 0xff)))
			w.bind('<Shift-Button-1>', lambda e: seen.append(('S', e.state & 0xff)))
			w.bind('<Control-1>', lambda e: seen.append(('C', e.state & 0xff)))
			w.bind('<Shift-ButtonRelease-1>', lambda e: seen.append(('SR', 0)))
			x, y = w._x + 1, w._y + 1
			root._onMouse(x, y, curses.BUTTON1_PRESSED)
			root._onMouse(x, y, curses.BUTTON1_RELEASED)
			root._onMouse(x, y, curses.BUTTON1_PRESSED | curses.BUTTON_SHIFT)
			root._onMouse(x, y, curses.BUTTON1_RELEASED | curses.BUTTON_SHIFT)
			root._onMouse(x, y, curses.BUTTON1_PRESSED | curses.BUTTON_CTRL)
			root._onMouse(x, y, curses.BUTTON1_RELEASED | curses.BUTTON_CTRL)
			root._onMouse(x, y, curses.BUTTON1_PRESSED |
				curses.BUTTON_CTRL | curses.BUTTON_SHIFT)
			root._onMouse(x, y, curses.BUTTON1_RELEASED)
			self.assertEqual(seen, [('B1', 0), ('S', 1), ('SR', 0), ('C', 4),
				('C', 5)], w.winfo_class())

	def test_modifier_prefixes(self):
		from tktext._core import _modifierPrefixes
		self.assertEqual(_modifierPrefixes(0), [])
		self.assertEqual(_modifierPrefixes(1), ['Shift-'])
		p = _modifierPrefixes(5)
		self.assertEqual(p[:2], ['Control-Shift-', 'Shift-Control-'])
		self.assertEqual(p[2:], ['Control-', 'Shift-'])


class FocusEventTest(unittest.TestCase):

	def test_focus_events_are_queued(self):
		root, scr = makeApp()
		a = tk.Entry(root)
		b = tk.Entry(root)
		a.pack()
		b.pack()
		attach(root)
		a.focus_set()
		root.update()
		seen = []
		a.bind('<FocusOut>', lambda ev: seen.append('out'))
		b.bind('<FocusIn>',  lambda ev: seen.append('in'))
		b.focus_set()
		self.assertEqual(seen, [])
		self.assertIs(root.focus_get(), b)
		root.update()
		self.assertEqual(seen, ['out', 'in'])

	def test_focusout_destroying_popup_is_not_reentrant(self):
		# flair PopupListbox.destroy(): focus_set() of the previous widget
		# must not run the popup's <FocusOut> (which destroys it again)
		root, scr = makeApp()
		e = tk.Entry(root)
		e.pack()
		attach(root)
		e.focus_set()
		shown = {}

		def destroy(event=None):
			if shown.get('top') is not None:
				e.focus_set()
				tk.Toplevel.destroy(shown['top'])
				shown['top'] = None
		top = tk.Toplevel(root)
		lb  = tk.Listbox(top)
		lb.pack()
		lb.bind('<FocusOut>', destroy)
		shown['top'] = top
		lb.focus_set()
		root.update()
		destroy()
		root.update()
		self.assertIsNone(shown['top'])
		self.assertTrue(top._destroyed)


class AppLoopTest(unittest.TestCase):

	def test_after_callback_redraws(self):
		root, scr = makeApp(30, 5)
		var = tk.StringVar(value='before')
		tk.Label(root, textvariable=var).pack()
		attach(root)
		root.after(0, lambda: var.set('after!'))
		root._fireAfterCallbacks()
		root._update()
		self.assertIsNotNone(scr.find('after!'))

	def test_after_cancel(self):
		root, scr = makeApp()
		got = []
		h = root.after(0, lambda: got.append(1))
		root.after_cancel(h)
		root._fireAfterCallbacks()
		self.assertEqual(got, [])

	def test_widget_after(self):
		root, scr = makeApp()
		lbl = tk.Label(root)
		got = []
		lbl.after(0, got.append, 5)
		root._fireAfterCallbacks()
		self.assertEqual(got, [5])

	def test_callback_exception_is_reported_not_fatal(self):
		root, scr = makeApp(40, 12)
		b = tk.Button(root, text='boom', command=lambda: 1 / 0); b.pack()
		attach(root)
		# 1st Enter presses the button (raises), 2nd dismisses the dialog
		scr.keys = [10, 10]
		root._processOneEvent()
		self.assertEqual(len(root._errors), 1)
		self.assertIn('ZeroDivisionError', root._errors[0])
		self.assertFalse(root._postedDialogs)
		root._errors.clear()

	def test_variable_traces(self):
		v = tk.StringVar()
		got = []
		name = v.trace_add('write', lambda *a: got.append(a[2]))
		v.trace('w', lambda *a: got.append('legacy'))
		v.set('x')
		self.assertEqual(got, ['write', 'legacy'])
		v.trace_remove('write', name)
		v.set('y')
		self.assertEqual(got, ['write', 'legacy', 'legacy'])
		self.assertEqual(tk.IntVar(value='7').get(), 7)
		self.assertTrue(tk.BooleanVar(value='true').get())


if __name__ == '__main__':
	unittest.main()


class EventAttributesTest(unittest.TestCase):

	def test_time_and_tkinter_attributes(self):
		root, scr = makeApp()
		e = tk.Entry(root)
		e.pack()
		attach(root)
		e.focus_set()
		got = []
		e.bind('<Key>', lambda ev: got.append(ev))
		press(root, 'a', 'b')
		self.assertEqual(len(got), 2)
		first, second = got
		for ev in got:
			for name in ('time', 'serial', 'send_event', 'keysym_num',
					'focus', 'width', 'height', 'delta', 'num'):
				self.assertTrue(hasattr(ev, name), name)
			self.assertIsInstance(ev.time, int)
		self.assertGreaterEqual((second.time - first.time) & 0xFFFFFFFF, 0)
		self.assertGreater(second.serial, first.serial)
		self.assertEqual(first.keysym_num, ord('a'))


class ModifiedKeyTest(unittest.TestCase):
	"""Escape sequences of modified special keys the terminfo entry does
	not decode (TERM=screen) arrive as single characters."""

	@staticmethod
	def feed(root, scr, data):
		scr.keys.extend(ord(c) for c in data)
		while scr.keys or root._pendingKeys:
			root._processOneEvent()

	def test_decode(self):
		import curses
		from tktext._events import decodeEscape, decodeExtended, \
			STATE_MOD4, STATE_CONTROL, KEY_SHIFT_RIGHT
		k = decodeEscape('[1;9C')
		self.assertEqual((int(k), k.state), (curses.KEY_RIGHT, STATE_MOD4))
		self.assertEqual(decodeEscape('[1;2C'), KEY_SHIFT_RIGHT)
		self.assertEqual(decodeEscape('[C'), curses.KEY_RIGHT)
		self.assertEqual(decodeEscape('[3;5~').state, STATE_CONTROL)
		self.assertIsNone(decodeEscape('[?1;2c'))
		self.assertEqual(decodeExtended('kRIT5').state, STATE_CONTROL)
		self.assertIsNone(decodeExtended('kRIT'))

	def test_decode_other_keys(self):
		"""xterm modifyOtherKeys (formatOtherKeys 0 and 1) and kitty."""
		from tktext._events import decodeEscape, STATE_CONTROL, STATE_SHIFT
		k = decodeEscape('[13;5u')
		self.assertEqual((int(k), k.state), (10, STATE_CONTROL))
		k = decodeEscape('[27;5;13~')
		self.assertEqual((int(k), k.state), (10, STATE_CONTROL))
		k = decodeEscape('[13;2u')
		self.assertEqual((int(k), k.state), (10, STATE_SHIFT))
		k = decodeEscape('[13:13;5:1u')			# kitty sub-parameters
		self.assertEqual((int(k), k.state), (10, STATE_CONTROL))
		self.assertEqual(decodeEscape('[97;5u'), 1)	# Control-a
		k = decodeEscape('[65;6u')			# Control-Shift-a
		self.assertEqual((int(k), k.state), (65, STATE_CONTROL | STATE_SHIFT))
		self.assertEqual(decodeEscape('[9;2u'), 353)	# Shift-Tab
		self.assertEqual(decodeEscape('[33;2u'), 33)	# '!'
		self.assertIsNone(decodeEscape('[5000;5u'))

	def test_decode_rxvt_keys(self):
		"""rxvt: ESC [a..d Shift-arrows, ESC Oa..d Control-arrows,
		ESC [<n>$ / ^ / @ Shift / Control / Control-Shift keys."""
		import curses
		from tktext._events import decodeEscape, STATE_CONTROL, \
			STATE_SHIFT, KEY_SHIFT_UP, KEY_SHIFT_DOWN, KEY_SHIFT_PPAGE
		self.assertEqual(decodeEscape('[a'), KEY_SHIFT_UP)
		self.assertEqual(decodeEscape('[b'), KEY_SHIFT_DOWN)
		k = decodeEscape('Oa')
		self.assertEqual((int(k), k.state), (curses.KEY_UP, STATE_CONTROL))
		self.assertEqual(decodeEscape('[5$'), KEY_SHIFT_PPAGE)
		k = decodeEscape('[3^')
		self.assertEqual((int(k), k.state), (curses.KEY_DC, STATE_CONTROL))
		k = decodeEscape('[3@')
		self.assertEqual(k.state, STATE_CONTROL | STATE_SHIFT)
		self.assertIsNone(decodeEscape('[99$'))

	def test_rxvt_shift_tilde_ends_sequence(self):
		# '$' is not a CSI final byte: the key after it must not be eaten
		root, scr = makeApp()
		t = tk.Text(root)
		t.pack()
		attach(root)
		t.focus_set()
		seen = []
		t.bind('<Key>', lambda e: seen.append((e.keysym, e.state)) or 'break')
		self.feed(root, scr, '\x1b[5$x\x1b[b')
		self.assertEqual(seen, [('Prior', 1), ('x', 0), ('Down', 1)])

	def test_uppercase_letter_has_shift_state(self):
		# like Tk: 'J' is reported with the Shift bit (flair: Shift-j
		# extends the card selection)
		from tktext._events import KeyEvent, STATE_SHIFT
		self.assertEqual(KeyEvent(ord('J')).state, STATE_SHIFT)
		self.assertEqual(KeyEvent(ord('j')).state, 0)
		self.assertEqual(KeyEvent(ord('!')).state, 0)

	def test_control_return_binding(self):
		root, scr = makeApp()
		t = tk.Text(root)
		t.pack()
		attach(root)
		t.focus_set()
		seen = []
		t.bind('<Control-Key-Return>', lambda e: seen.append(('C', e.state)))
		t.bind('<Shift-Key-Return>', lambda e: seen.append(('S', e.state)) or 'break')
		self.feed(root, scr, '\x1b[13;5u\x1b[13;2u\x1b[27;5;13~')
		self.assertEqual(seen, [('C', 4), ('S', 1), ('C', 4)])
		self.assertEqual(t.get('1.0', 'end'), '\n')	# no newline inserted

	def test_control_shift_letter_matches_control_binding(self):
		root, scr = makeApp()
		e = tk.Entry(root)
		e.pack()
		attach(root)
		e.focus_set()
		seen = []
		e.bind('<Control-Key-A>', lambda ev: seen.append(ev.keysym))
		self.feed(root, scr, 'x\x1b[65;6u')
		self.assertEqual(seen, ['A'])
		self.assertEqual(e.get(), 'x')

	def test_super_right_binding_on_toplevel(self):
		root, scr = makeApp()
		lb = tk.Listbox(root)
		lb.pack()
		for i in range(5):
			lb.insert('end', f'card{i}')
		attach(root)
		lb.focus_set()
		lb.selection_set(1)
		lb.activate(1)
		seen = []
		root.bind('<Mod4-Right>', lambda e: seen.append(e.state) or 'break')
		self.feed(root, scr, '\x1b[1;9C')
		self.assertEqual(seen, [0x40])
		self.assertEqual(lb.curselection(), (1,))

	def test_unbound_modified_key_is_swallowed(self):
		root, scr = makeApp()
		e = tk.Entry(root)
		e.pack()
		attach(root)
		e.focus_set()
		self.feed(root, scr, 'a\x1b[1;5Cb\x1b[1;9D')
		self.assertEqual(e.get(), 'ab')

	def test_lone_escape_and_escape_letter(self):
		root, scr = makeApp()
		e = tk.Entry(root)
		e.pack()
		attach(root)
		e.focus_set()
		seen = []
		e.bind('<Escape>', lambda ev: seen.append(1))
		self.feed(root, scr, '\x1bx\x1b[')
		self.assertEqual(seen, [1, 1])
		self.assertEqual(e.get(), 'x[')
