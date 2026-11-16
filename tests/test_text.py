import curses
import unittest

from fakescreen import makeApp, attach, press, click, tk

_YELLOW = 1 << 28		# fake colour pair marker


def makeText(content='', **kw):
	root, scr = makeApp(40, 12)
	t = tk.Text(root, width=20, height=5, **kw)
	t.pack()
	if content:
		t.insert('1.0', content)
	attach(root)
	t.focus_set()
	return root, scr, t


class TextIndexTest(unittest.TestCase):

	def test_end_semantics(self):
		root, scr, t = makeText('abc\ndef')
		self.assertEqual(t.get('1.0', 'end'), 'abc\ndef\n')
		self.assertEqual(t.get('1.0', 'end-1c'), 'abc\ndef')
		self.assertEqual(t.index('end'), '3.0')
		self.assertEqual(t.index('end-1c'), '2.3')

	def test_modifiers(self):
		root, scr, t = makeText('hello world\nsecond line')
		self.assertEqual(t.index('1.0+7c'), '1.7')
		self.assertEqual(t.index('1.10+3c'), '2.1')		# crosses the newline
		self.assertEqual(t.index('2.3 linestart'), '2.0')
		self.assertEqual(t.index('1.2 lineend'), '1.11')
		self.assertEqual(t.index('1.8 wordstart'), '1.6')
		self.assertEqual(t.index('1.0 wordend'), '1.5')
		self.assertEqual(t.index('1.4 +1 lines'), '2.4')
		self.assertEqual(t.get('1.0', '1.0 lineend'), 'hello world')

	def test_display_lines(self):
		root, scr, t = makeText('hello world\nsecond line\nab')
		self.assertEqual(t.index('1.4 +1 displaylines'), '2.4')
		self.assertEqual(t.index('2.4 - 1 displaylines'), '1.4')
		self.assertEqual(t.index('2.9 +1 display lines'), '3.2')
		self.assertEqual(t.index('1.4 -1 displaylines'), '1.4')
		root, scr, t = makeText('a' * 30 + '\nxy', wrap='char')
		self.assertEqual(t.index('1.3 +1 displaylines'), '1.23')	# wrapped row
		self.assertEqual(t.index('1.23 +1 displaylines'), '2.2')

	def test_insert_mark_and_tags(self):
		root, scr, t = makeText()
		t.insert('end', 'ab', ('bold',), 'cd')
		self.assertEqual(t.get('1.0', 'end-1c'), 'abcd')
		self.assertEqual(t.tag_ranges('bold'), ('1.0', '1.2'))
		self.assertEqual(t.index('insert'), '1.4')
		t.mark_set('m', '1.1')
		t.insert('1.0', 'X')
		self.assertEqual(t.index('m'), '1.2')
		self.assertEqual(t.tag_ranges('bold'), ('1.1', '1.3'))

	def test_delete_single_char_joins_lines(self):
		root, scr, t = makeText('ab\ncd')
		t.delete('1.2')
		self.assertEqual(t.get('1.0', 'end-1c'), 'abcd')
		t.delete('1.0', 'end')
		self.assertEqual(t.get('1.0', 'end'), '\n')

	def test_search_and_compare(self):
		root, scr, t = makeText('one two three\nfour two')
		self.assertEqual(t.search('two', '1.0'), '1.4')
		self.assertEqual(t.search('two', '1.5'), '2.5')
		self.assertEqual(t.search('TWO', '1.0', nocase=True), '1.4')
		self.assertTrue(t.compare('1.0', '<', 'end'))

	def test_bad_index_raises_tclerror(self):
		root, scr, t = makeText('x')
		with self.assertRaises(tk.TclError):
			t.index('nonsense')


class TextEditTest(unittest.TestCase):

	def test_typing_and_backspace(self):
		root, scr, t = makeText()
		press(root, 'hi', 10, 'yo', curses.KEY_BACKSPACE)
		self.assertEqual(t.get('1.0', 'end-1c'), 'hi\ny')
		press(root, curses.KEY_HOME, curses.KEY_BACKSPACE)
		self.assertEqual(t.get('1.0', 'end-1c'), 'hiy')

	def test_shift_selection_and_replace(self):
		root, scr, t = makeText('abcdef')
		t.mark_set('insert', '1.0')
		press(root, curses.KEY_SRIGHT, curses.KEY_SRIGHT)
		self.assertEqual(t.selGet(), 'ab')
		self.assertEqual(t.tag_ranges('sel'), ('1.0', '1.2'))
		press(root, 'Z')
		self.assertEqual(t.get('1.0', 'end-1c'), 'Zcdef')

	def test_undo_redo(self):
		root, scr, t = makeText(undo=True)
		press(root, 'one ', 'two')
		self.assertEqual(t.get('1.0', 'end-1c'), 'one two')
		t.edit_undo()
		self.assertEqual(t.get('1.0', 'end-1c'), 'one ')
		t.edit_undo()
		self.assertEqual(t.get('1.0', 'end-1c'), '')
		t.edit_redo()
		self.assertEqual(t.get('1.0', 'end-1c'), 'one ')

	def test_disabled_ignores_insert(self):
		root, scr, t = makeText('x')
		t.configure(state='disabled')
		t.insert('end', 'y')
		t.delete('1.0', 'end')
		self.assertEqual(t.get('1.0', 'end-1c'), 'x')

	def test_modified_event(self):
		root, scr, t = makeText()
		got = []
		t.bind('<<Modified>>', lambda e: got.append(1))
		t.insert('1.0', 'x')
		self.assertEqual(got, [])	# queued like in Tk ...
		root.update()			# ... delivered by the event loop
		self.assertEqual(got, [1])
		self.assertTrue(t.edit_modified())


class TextRenderTest(unittest.TestCase):

	def test_word_wrap(self):
		root, scr, t = makeText('aaaa bbbb cccc dddd eeee ffff', wrap='word')
		y, x = t._y + 1, t._x + 1
		self.assertEqual(scr.row(y)[x:x + 20].rstrip(), 'aaaa bbbb cccc dddd')
		self.assertEqual(scr.row(y + 1)[x:x + 20].rstrip(), 'eeee ffff')

	def test_formatCharsNotSent(self):
		# U+FEFF (a BOM in a file) has no width for ncurses but one cell
		# in GNU screen: sending it shifts the line and leaves stale cells
		root, scr, t = makeText('﻿ab​c')
		sent = []
		orig = scr.addstr
		def addstr(y, x, s, attr=0):
			sent.append(s)
			orig(y, x, s, attr)
		scr.addstr = addstr
		root._update(force=True)
		self.assertTrue(any('abc' in s for s in sent))
		self.assertFalse(any('﻿' in s or '​' in s for s in sent))

	def test_down_moves_by_display_line(self):
		root, scr, t = makeText('x' * 30, wrap='char')
		t.mark_set('insert', '1.2')
		press(root, curses.KEY_DOWN)		# 20 columns per display line
		self.assertEqual(t.index('insert'), '1.22')

	def test_tag_colours_do_not_corrupt_attr(self):
		root, scr, t = makeText('hello')
		t.tag_configure('hl', background='yellow')
		t.tag_add('hl', '1.0', '1.2')
		root._update(force=True)
		# with colours disabled (fake screen) a tag must not add A_REVERSE
		y, x = t._y + 1, t._x + 1
		self.assertEqual(scr.attrs[y][x] & curses.A_REVERSE, 0)

	def test_tag_configure_query_like_tkinter(self):
		root, scr, t = makeText('hello')
		t.tag_configure('hl', background='yellow')
		cfg = t.tag_config('hl')
		for n, a, b, c, d in cfg.values():	# 5-tuples like tkinter
			pass
		self.assertEqual(cfg['background'],
			('background', '', '', '', 'yellow'))
		self.assertEqual(cfg['foreground'][4], '')
		self.assertEqual(t.tag_configure('hl', 'bg')[4], 'yellow')

	def _markBackground(self, root):
		"""Make the yellow background visible in the fake screen attrs."""
		root._colors.getAttr = lambda fg='', bg='', **kw: \
			_YELLOW if bg == 'yellow' else 0

	def _yellowCols(self, scr, t, row):
		y = t._y + 1 + row
		return [x - t._x - 1 for x in range(t._x + 1, t._x + 21)
			if scr.attrs[y][x] & _YELLOW]

	def test_tag_background_on_newline_fills_line(self):
		# like Tk: a tag covering the newline paints up to the right edge
		root, scr, t = makeText('ab\ncd\nef')
		self._markBackground(root)
		t.tag_configure('hl', background='yellow')
		t.tag_add('hl', '2.0', '3.0')
		root._update(force=True)
		self.assertEqual(self._yellowCols(scr, t, 0), [])
		self.assertEqual(self._yellowCols(scr, t, 1), list(range(20)))
		self.assertEqual(self._yellowCols(scr, t, 2), [])

	def test_tag_background_without_newline_does_not_fill(self):
		root, scr, t = makeText('abcd')
		self._markBackground(root)
		t.tag_configure('hl', background='yellow')
		t.tag_add('hl', '1.0', '1.2')
		root._update(force=True)
		self.assertEqual(self._yellowCols(scr, t, 0), [0, 1])

	def test_underline_on_newline_does_not_fill(self):
		root, scr, t = makeText('ab\ncd')
		t.tag_configure('ul', underline=1)
		t.tag_add('ul', '1.0', '2.0')
		root._update(force=True)
		y, x = t._y + 1, t._x + 1
		self.assertEqual(scr.attrs[y][x + 5] & curses.A_UNDERLINE, 0)

	def test_tag_background_fills_empty_and_tab_lines(self):
		root, scr, t = makeText('a\tb\n\nc')
		self._markBackground(root)
		t.tag_configure('hl', background='yellow')
		t.tag_add('hl', '1.0', 'end')
		root._update(force=True)
		for row in range(3):
			self.assertEqual(self._yellowCols(scr, t, row), list(range(20)))

	def test_tag_background_fills_wrapped_lines(self):
		root, scr, t = makeText('aaaa bbbb cccc dddd eeee ffff\nx',
			wrap='word')
		self._markBackground(root)
		t.tag_configure('hl', background='yellow')
		t.tag_add('hl', '1.0', '2.0')
		root._update(force=True)
		self.assertEqual(self._yellowCols(scr, t, 0), list(range(20)))
		self.assertEqual(self._yellowCols(scr, t, 1), list(range(20)))
		self.assertEqual(self._yellowCols(scr, t, 2), [])

	def test_tag_background_fills_left_margin(self):
		# like Tk: the margin takes the background of the first character
		root, scr, t = makeText('ab\ncd\nef')
		self._markBackground(root)
		t.tag_configure('ind', lmargin1=3)
		t.tag_configure('hl', background='yellow')
		t.tag_add('ind', '1.0', 'end')
		t.tag_add('hl', '2.0', '3.0')
		root._update(force=True)
		self.assertEqual(self._yellowCols(scr, t, 0), [])
		self.assertEqual(self._yellowCols(scr, t, 1), list(range(20)))
		self.assertEqual(self._yellowCols(scr, t, 2), [])

	def test_lmargincolor_fills_left_margin(self):
		root, scr, t = makeText('ab\ncd')
		self._markBackground(root)
		t.tag_configure('ind', lmargin1=3, lmargincolor='yellow')
		t.tag_add('ind', '2.0', 'end')
		root._update(force=True)
		self.assertEqual(self._yellowCols(scr, t, 0), [])
		self.assertEqual(self._yellowCols(scr, t, 1), [0, 1, 2])

	def test_selection_on_newline_fills_line(self):
		root, scr, t = makeText('ab\ncd')
		t.tag_add('sel', '1.0', '2.0')
		root._update(force=True)
		y, x = t._y + 1, t._x + 1
		self.assertTrue(scr.attrs[y][x + 19] & curses.A_REVERSE)
		self.assertFalse(scr.attrs[y + 1][x + 19] & curses.A_REVERSE)

	def test_cursor_hidden_when_scrolled_away(self):
		root, scr, t = makeText('\n'.join(str(i) for i in range(30)))
		t.mark_set('insert', '1.0')
		t.see('1.0')
		root._update(force=True)
		self.assertIsNotNone(t._cursorPos())
		t.yview('moveto', 1.0)
		root._update(force=True)
		self.assertIsNone(t._cursorPos())

	def test_yscrollcommand(self):
		root, scr = makeApp(40, 12)
		sb = tk.Scrollbar(root)
		t  = tk.Text(root, width=20, height=5, yscrollcommand=sb.set)
		sb.configure(command=t.yview)
		t.insert('1.0', '\n'.join(str(i) for i in range(20)))
		sb.pack(side=tk.RIGHT, fill=tk.Y)
		t.pack(side=tk.LEFT)
		attach(root)
		self.assertEqual(sb.get(), (0.0, 0.25))
		sb._command('scroll', 1, 'pages')
		root._update()
		self.assertGreater(sb.get()[0], 0.0)

	def test_mouse_drag_selects(self):
		root, scr, t = makeText('hello world')
		x0, y0 = t._x + 1, t._y + 1
		click(root, x0, y0, 'press')
		root._onMouse(x0 + 5, y0, curses.REPORT_MOUSE_POSITION)
		click(root, x0 + 5, y0, 'release')
		self.assertEqual(t.selGet(), 'hello')
		click(root, x0 + 8, y0, 'double')
		self.assertEqual(t.selGet(), 'world')


class TextFlairRegressionTest(unittest.TestCase):
	"""Behaviour that tkinter applications (flair's input editor) rely on."""

	def test_current_mark_follows_press_before_bindings(self):
		root, scr, t = makeText('line1\nline2\nline3')
		seen = []
		t.bind('<Button-1>', lambda e: seen.append(t.index('current')))
		click(root, t._x + 2, t._y + 2, 'press')
		click(root, t._x + 2, t._y + 2, 'release')
		bd = t._border()
		self.assertEqual(seen, [f'{3 - bd}.{2 - bd}'])

	def test_text_anchor_mark(self):
		root, scr, t = makeText('hello world')
		name = t.tk.call('::tk::TextAnchor', t._w)
		self.assertTrue(name)
		t.mark_set(name, '1.2')
		self.assertEqual(t.index(name), '1.2')
		t.mark_unset(name)
		self.assertNotIn(name, t.mark_names())

	def test_redraw_does_not_call_overridden_xview(self):
		class MyText(tk.Text):
			calls = 0
			def xview(self, *args):
				MyText.calls += 1
				return super().xview(*args)
		root, scr = makeApp(40, 12)
		sb = tk.Scrollbar(root, orient='horizontal')
		t  = MyText(root, width=20, height=5, wrap='none', xscrollcommand=sb.set)
		t.pack()
		sb.pack(fill='x')
		attach(root)
		t.insert('1.0', 'x' * 60)
		root.update()
		t.xview_moveto(0.5)
		root.update()
		self.assertEqual(MyText.calls, 0)

	def test_widget_placed_inside_text(self):
		root, scr, t = makeText('abc')
		lb = tk.Listbox(t, height=3)
		lb.insert('end', 'one', 'two', 'three')
		lb.place(x=2, y=1, width=8, height=3)
		root.update()
		self.assertTrue(lb.winfo_ismapped())
		bd = t._border()			# place() is relative to the inner edge
		self.assertEqual((lb._x, lb._y), (t._x + bd + 2, t._y + bd + 1))
		self.assertIn('one', scr.row(lb._y + lb._border()))
		lb.place_forget()
		root.update()
		self.assertFalse(lb.winfo_ismapped())


if __name__ == '__main__':
	unittest.main()


class TextElideDumpTest(unittest.TestCase):
	"""elide=True hides text; dump() reports text/tag runs like Tk."""

	def test_elided_line_is_not_displayed(self):
		root, scr, t = makeText('first\n12345\nsecond')
		t.tag_add('id', '2.0', '3.0')		# whole line incl. newline
		t.tag_configure('id', elide=True)
		root._update(force=True)
		text = scr.text()
		self.assertIn('first', text)
		self.assertIn('second', text)
		self.assertNotIn('12345', text)
		self.assertEqual(t.get('2.0', '2.end'), '12345')	# still there

	def test_partial_elide_and_cursor_skip(self):
		root, scr, t = makeText('abXXcd')
		t.tag_add('h', '1.2', '1.4')
		t.tag_configure('h', elide=1)
		root._update(force=True)
		self.assertIn('abcd', scr.text())
		t.mark_set('insert', '1.2')
		t._cur = t._skipElided(t._cur, True)
		self.assertEqual(t.index('insert'), '1.4')

	def test_dump_text_and_tags(self):
		root, scr, t = makeText('hello world\nline two')
		t.tag_add('b', '1.2', '1.5')
		self.assertEqual(t.dump('1.0', '1.end', text=1, tag=1), [
			('text', 'he', '1.0'), ('tagon', 'b', '1.2'),
			('text', 'llo', '1.2'), ('tagoff', 'b', '1.5'),
			('text', ' world', '1.5')])


class TextTabsTest(unittest.TestCase):

	def row(self, scr, t, i=0):
		y, x = t._y + 1 + i, t._x + 1
		return scr.row(y)[x:x + t._textW()].rstrip()

	def test_default_tabs_every_8_cells(self):
		root, scr, t = makeText('a\tb\tc', wrap='none')
		self.assertEqual(self.row(scr, t), 'a       b       c')

	def test_left_and_right_stops(self):
		root, scr, t = makeText('', wrap='none',
			tabs=('6', 'right', '7', 'left'))
		t.insert('1.0', 'x\tab\tcd\tef')
		root._update(force=True)
		# 'ab' right aligned on 6, 'cd' on the left stop 7 (min 1 space),
		# the repeated right stop 8 is already passed: one space
		self.assertEqual(self.row(scr, t), 'x   ab cd ef')

	def test_tab_at_least_one_space(self):
		root, scr, t = makeText('', wrap='none', tabs='3')
		t.insert('1.0', 'abcd\te')
		root._update(force=True)
		self.assertEqual(self.row(scr, t), 'abcd e')

	def test_wordprocessor_uses_next_stop(self):
		root, scr, t = makeText('', wrap='none', tabs='4 8 12',
			tabstyle='wordprocessor')
		t.insert('1.0', 'abcdef\tg')
		root._update(force=True)
		self.assertEqual(self.row(scr, t), 'abcdef  g')

	def test_cursor_and_mouse_across_tab(self):
		root, scr, t = makeText('a\tb', wrap='none')
		t.mark_set('insert', '1.2')
		root._update(force=True)
		self.assertEqual(t._cursorPos(), (t._y + 1, t._x + 1 + 8))
		click(root, t._x + 1 + 8, t._y + 1)
		self.assertEqual(t.index('insert'), '1.2')
		click(root, t._x + 1 + 4, t._y + 1)	# inside the tab
		self.assertEqual(t.index('insert'), '1.1')

	def test_wrap_counts_tab_width(self):
		root, scr, t = makeText('ab\tcdefghijklmn', wrap='char')
		# 2 + 6 (tab) + 12 = 20 cells fits; one more char wraps
		self.assertEqual(len(t._displayLines()), 1)
		t.insert('end-1c', 'q')
		self.assertEqual(len(t._displayLines()), 2)

	def test_xview_follows_row_edits(self):
		# the row widths are cached and patched on single row edits
		root, scr, t = makeText('ab\tc\nxyz', wrap='none')	# widths 9, 3
		root._update(force=True)
		self.assertEqual(t.xview(), (0.0, 1.0))
		t.insert('2.3', 'x' * 30)		# longest row: 33
		self.assertEqual(t.xview(), (0.0, 20 / 33))
		t.delete('2.3', '2.end')
		self.assertEqual(t.xview(), (0.0, 1.0))
		t.insert('1.0', '\t\t\t')		# 24 + 9
		self.assertEqual(t.xview(), (0.0, 20 / 33))
		t.tag_configure('h', elide=True)
		t.tag_add('h', '1.0', '1.3')
		self.assertEqual(t.xview(), (0.0, 1.0))

	def test_row_width_matches_layout(self):
		# _rowWidth computes the width without the per column layout
		lines = ['x\tab\tcd\tef', '\t1.25\tq', 'abcdefghij\tk\tl\tm\tn',
			'\t\t\t\t\t\t', 'no tabs', 'h1\th2\t3.5\t.\tc']
		for tabs in (None, ('6', 'right', '7', 'left'),
				('4', 'center', '9', 'numeric', '12'), ('3',)):
			kw = {'tabs': tabs} if tabs else {}
			root, scr, t = makeText('\n'.join(lines), wrap='none', **kw)
			t.tag_configure('h', elide=True)
			t.tag_add('h', '6.0', '6.3', '3.2', '3.5')
			for r, l in enumerate(t._buf):
				self.assertEqual(t._rowWidth(r, None),
					t._segWidth((r, 0, len(l)), None), (tabs, l))

	def test_row_margins_match_lookup(self):
		root, scr, t = makeText('\n'.join(f'r{i}\tx' for i in range(8)),
			wrap='none')
		t.tag_configure('a', lmargin1=2)
		t.tag_configure('b', lmargin1=5)	# higher priority
		t.tag_configure('h', elide=True)
		t.tag_add('a', '1.0', '6.0')
		t.tag_add('b', '2.1', '4.0', '7.0', '7.2')
		t.tag_add('h', '3.0', '3.1', '5.0', '5.2')
		mfn = t._margins()
		self.assertEqual(t._rowMargins(),
			[mfn(r, 0) for r in range(len(t._buf))])
		self.assertEqual(t._contentWidth(),
			max(t._segWidth((r, 0, len(l)), mfn)
				for r, l in enumerate(t._buf)))

	def test_pixel_mode_stops(self):
		from tktext import _core
		_core.setPixelMode(8, 16)
		try:
			root, scr, t = makeText('', wrap='none', tabs=('80', 'left'))
			t.insert('1.0', 'a\tb')
			root._update(force=True)
			self.assertEqual(t.bbox('1.2')[0] - t.bbox('1.0')[0], 80)
		finally:
			_core.setPixelMode(1, 1)


class TextMarginTest(unittest.TestCase):
	"""Tag options lmargin1 / lmargin2 indent the display lines."""

	def row(self, scr, t, i=0):
		y, x = t._y + 1 + i, t._x + 1
		return scr.row(y)[x:x + t._textW()].rstrip()

	def test_lmargin1_indents_first_line(self):
		root, scr, t = makeText('top\ncard\nend')
		t.tag_configure('indent2', lmargin1=4)
		t.tag_add('indent2', '2.0', '3.0')
		root._update(force=True)
		self.assertEqual(self.row(scr, t, 0), 'top')
		self.assertEqual(self.row(scr, t, 1), '    card')
		self.assertEqual(self.row(scr, t, 2), 'end')
		self.assertEqual(t.bbox('2.0')[0], 1 + 4)
		self.assertEqual(t._posFromXY(1 + 5, 1 + 1), (1, 1))
		self.assertEqual(t._posFromXY(1, 1 + 1), (1, 0))	# in the margin

	def test_lmargin2_and_wrapping(self):
		root, scr, t = makeText('aaaaaaaaaabbbbbbbbbbcccccc', wrap='char')
		t.tag_configure('m', lmargin1=2, lmargin2=6)
		t.tag_add('m', '1.0', 'end')
		root._update(force=True)
		w = t._textW()
		self.assertEqual(self.row(scr, t, 0), '  ' + 'aaaaaaaaaabbbbbbbbbbcccccc'[:w - 2])
		self.assertTrue(self.row(scr, t, 1).startswith('      '))

	def test_tab_stops_ignore_margin(self):
		# like Tk the tab stops are fixed from the text area edge
		root, scr, t = makeText('a\tb\nab\tc', wrap='none')
		t.tag_configure('ind', lmargin1=3)
		t.tag_add('ind', '2.0', '3.0')
		root._update(force=True)
		self.assertEqual(self.row(scr, t, 0), 'a       b')
		self.assertEqual(self.row(scr, t, 1), '   ab   c')
		self.assertEqual(t.bbox('2.3')[0], 1 + 8)
		self.assertEqual(t._rowWidth(1, t._margins()), 9)

	def test_margin_after_elided_prefix(self):
		# flair InputPage: {elided id}{indented text}
		root, scr, t = makeText('12345card')
		t.tag_configure('id', elide=True)
		t.tag_add('id', '1.0', '1.5')
		t.tag_configure('indent1', lmargin1=3)
		t.tag_add('indent1', '1.5', '1.end')
		root._update(force=True)
		self.assertEqual(self.row(scr, t, 0), '   card')

	def test_pixel_mode_millimetres(self):
		tk._core.setPixelMode(8, 16)
		try:
			root, scr, t = makeText('card')
			t.tag_configure('indent1', lmargin1='2 m')	# 7.56 px -> 1 cell
			t.tag_add('indent1', '1.0', '1.end')
			root._update(force=True)
			row = scr.row(t._y)[t._x:]
			self.assertEqual(row[:5], ' card')
		finally:
			tk._core.setPixelMode(1, 1)

	def test_tag_range_change_updates_margin(self):
		root, scr, t = makeText('one\ntwo')
		t.tag_configure('i', lmargin1=3)
		root._update(force=True)
		self.assertEqual(self.row(scr, t, 1), 'two')
		t.tag_add('i', '2.0', '2.end')
		root._update(force=True)
		self.assertEqual(self.row(scr, t, 1), '   two')
		t.tag_remove('i', '1.0', 'end')
		root._update(force=True)
		self.assertEqual(self.row(scr, t, 1), 'two')


class TextTagRangeTest(unittest.TestCase):
	"""Tag ranges are kept sorted, disjoint and merged (searched with bisect)."""

	def test_insert_at_boundaries_is_untagged(self):
		root, scr, t = makeText('abcdef')
		t.tag_add('x', '1.2', '1.4')
		t.insert('1.2', 'L')			# before the start
		t.insert('1.5', 'R')			# at the end
		self.assertEqual(t.tag_ranges('x'), ('1.3', '1.5'))
		t.insert('1.4', 'M')			# inside: the range grows
		self.assertEqual(t.tag_ranges('x'), ('1.3', '1.6'))
		t.insert('1.0', 'a\nb')			# shifts the row
		self.assertEqual(t.tag_ranges('x'), ('2.4', '2.7'))

	def test_insert_with_taglist_inside_range_splits_it(self):
		# like Tk: a tagList gives exactly those tags, even inside a range
		root, scr, t = makeText('')
		t.insert('1.0', 'abcdef', 'x')
		t.insert('1.2', 'ZZ', 'y')
		self.assertEqual(t.tag_ranges('x'), ('1.0', '1.2', '1.4', '1.8'))
		self.assertEqual(t.tag_ranges('y'), ('1.2', '1.4'))
		t.insert('1.1', 'Q', '')		# empty tagList: untagged
		self.assertEqual(t.tag_ranges('x'), ('1.0', '1.1', '1.2', '1.3', '1.5', '1.9'))

	def test_insert_segments_before_touching_range(self):
		# flair InputPage redraws a card in front of the next card's id:
		# the segments after the first must not join the touching range
		root, scr, t = makeText('')
		t.insert('1.0', 'ab\ncd\n', 'x')
		t.tk.call(t._w, 'insert', '1.0', 'id\n', 'x', 'body\n', '', 'more', 'y')
		self.assertEqual(t.tag_ranges('x'), ('1.0', '2.0', '3.4', '5.0'))
		self.assertEqual(t.tag_ranges('y'), ('3.0', '3.4'))

	def test_insert_segments_with_newlines_and_tag_tuples(self):
		root, scr, t = makeText('')
		t.insert('1.0', 'a\nbc', ('x', 'y'), 'd', '', 'e\n\nfg', 'y')
		self.assertEqual(t.get('1.0', 'end-1c'), 'a\nbcde\n\nfg')
		self.assertEqual(t.tag_ranges('x'), ('1.0', '2.2'))
		self.assertEqual(t.tag_ranges('y'), ('1.0', '2.2', '2.3', '4.2'))

	def test_insert_segments_is_one_undo_step(self):
		root, scr, t = makeText('', undo=True)
		t.insert('1.0', 'base')
		t.edit_separator()
		t.insert('end', 'a', 'x', 'b\nc', 'y')
		self.assertEqual(t.get('1.0', 'end-1c'), 'baseab\nc')
		t.edit_undo()
		self.assertEqual(t.get('1.0', 'end-1c'), 'base')

	def test_append_elided_segments_is_linear(self):
		# flair's CardWidget.create: one insert per card with an elided
		# id line; the elide map was rebuilt for every segment
		import time
		root, scr, t = makeText()
		t.tag_configure('id', elide=True)
		start = time.time()
		y = 1
		for i in range(3000):
			t.insert(f'{y}.0', f'{i}\n', 'id', ' CARD\t', 'card',
				'\tname:\t', '', 'value\t', 'value', '\n\tx:\t', '',
				'1.0\t', 'value', '\n', '')
			y += 3
		root.update()
		self.assertLess(time.time() - start, 3.0)
		self.assertEqual(len(t.tag_ranges('id')), 2 * 3000)
		self.assertEqual(len(t.tag_ranges('value')), 2 * 2 * 3000)
		self.assertEqual(t.tag_ranges('card')[:2], ('2.0', '2.6'))

	def test_delete_merges_touching_ranges(self):
		root, scr, t = makeText('aaXbb')
		t.tag_add('x', '1.0', '1.2')
		t.tag_add('x', '1.3', '1.5')
		t.delete('1.2')
		self.assertEqual(t.tag_ranges('x'), ('1.0', '1.4'))
		self.assertEqual(t.tag_nextrange('x', '1.0'), ('1.0', '1.4'))

	def test_add_merges_overlapping_and_touching(self):
		root, scr, t = makeText('0123456789')
		t.tag_add('x', '1.1', '1.2', '1.4', '1.5', '1.7', '1.8')
		self.assertEqual(t.tag_ranges('x'),
			('1.1', '1.2', '1.4', '1.5', '1.7', '1.8'))
		t.tag_add('x', '1.2', '1.4')		# touches both neighbours
		self.assertEqual(t.tag_ranges('x'), ('1.1', '1.5', '1.7', '1.8'))
		t.tag_add('x', '1.0', '1.9')
		self.assertEqual(t.tag_ranges('x'), ('1.0', '1.9'))

	def test_remove_split_and_reversed(self):
		root, scr, t = makeText('0123456789')
		t.tag_add('x', '1.0', '1.9')
		t.tag_remove('x', '1.6', '1.3')		# reversed: nothing (Tk)
		self.assertEqual(t.tag_ranges('x'), ('1.0', '1.9'))
		t.tag_remove('x', '1.3', '1.6')
		self.assertEqual(t.tag_ranges('x'), ('1.0', '1.3', '1.6', '1.9'))

	def test_next_prev_range_and_names(self):
		root, scr, t = makeText('0123456789')
		t.tag_add('x', '1.2', '1.4', '1.6', '1.8')
		self.assertEqual(t.tag_nextrange('x', '1.2'), ('1.2', '1.4'))
		self.assertEqual(t.tag_nextrange('x', '1.3'), ('1.6', '1.8'))
		self.assertEqual(t.tag_nextrange('x', '1.3', '1.6'), ())
		self.assertEqual(t.tag_prevrange('x', '1.6'), ('1.2', '1.4'))
		self.assertEqual(t.tag_prevrange('x', '1.7'), ('1.6', '1.8'))
		self.assertEqual(t.tag_prevrange('x', '1.7', '1.7'), ())
		self.assertIn('x', t.tag_names('1.3'))
		self.assertNotIn('x', t.tag_names('1.4'))

	def test_char_offsets(self):
		root, scr, t = makeText('ab\n\ncd')
		self.assertEqual(t.index('1.1+3c'), '3.0')
		self.assertEqual(t.index('3.0-2c'), '1.2')
		self.assertEqual(t.index('end-2c'), '3.1')
		self.assertEqual(t.index('end+5c'), '4.0')
		self.assertEqual(t.index('1.1-9c'), '1.0')

	def test_append_many_cards_is_linear(self):
		# flair's InputEditor: every card is appended with one insert
		# and several tag_add; this used to be quadratic
		import time
		root, scr, t = makeText()
		start = time.time()
		y = 1
		for i in range(3000):
			t.insert(f'{y}.0', f'{i}\n\tCARD\tname:\tvalue\n\tx:\t1.0\n')
			t.tag_add('id', f'{y}.0', f'{y + 1}.0')
			t.tag_add('card', f'{y + 1}.1', f'{y + 1}.5')
			t.tag_add('value', f'{y + 1}.12', f'{y + 1}.17')
			t.tag_add('value', f'{y + 2}.4', f'{y + 2}.7')
			t.tag_add('indent', f'{y + 1}.0', f'{y + 3}.0')
			y += 3
		self.assertLess(time.time() - start, 3.0)
		self.assertEqual(len(t.tag_ranges('value')), 2 * 2 * 3000)
		indent = t.tag_ranges('indent')
		self.assertEqual(len(indent), 2 * 3000)
		self.assertEqual(indent[:4], ('2.0', '4.0', '5.0', '7.0'))
		self.assertEqual(t.tag_nextrange('id', f'{y - 3}.0'),
			(f'{y - 3}.0', f'{y - 2}.0'))


class TextIncrementalLayoutTest(unittest.TestCase):
	"""Edits inside one line patch the layout caches (display lines,
	elide map, margins) instead of recomputing them: the result must be
	the same as a full recompute."""

	def fullLayout(self, t):
		for attr in ('_elideCacheKey', '_marginCacheKey', '_xsCacheKey'):
			if hasattr(t, attr):
				delattr(t, attr)
		t._dlCache = {}
		return t._displayLines(), dict(t._elideMap())

	def checkEdits(self, wrap):
		root, scr, t = makeText(wrap=wrap)
		t.tag_configure('id', elide=True)
		t.tag_configure('text', lmargin1=3, lmargin2=5)
		t.tag_configure('v', foreground='red')
		y = 1
		for i in range(20):
			t.insert(f'{y}.0', f'{i}\n\tCARD\tname value words\nplain line {i}\n')
			t.tag_add('id', f'{y}.0', f'{y + 1}.0')
			t.tag_add('text', f'{y + 1}.0', f'{y + 2}.0')
			t.tag_add('v', f'{y + 1}.7', f'{y + 1}.11')
			y += 3
		root._update()
		edits = [('insert', '2.3', 'abc'), ('insert', '5.0', 'x' * 30),
			('delete', '5.2', '5.9'), ('insert', '3.4', '\t'),
			('delete', '1.0', '1.1'), ('insert', '8.end', ' tail'),
			('delete', '9.0', '9.end')]
		for op, idx, arg in edits:
			t._displayLines(); t._elideMap(); t._segMargin((1, 0, 0))
			if op == 'insert':
				t.insert(idx, arg)
			else:
				t.delete(idx, arg)
			patched = (list(t._displayLines()), dict(t._elideMap()))
			self.assertEqual(patched, self.fullLayout(t), (op, idx, arg))
			root._update()

	def test_patch_nowrap(self):
		self.checkEdits('none')

	def test_patch_char_wrap(self):
		self.checkEdits('char')

	def test_patch_word_wrap(self):
		self.checkEdits('word')

	def test_tag_add_on_elide_tag_invalidates(self):
		root, scr, t = makeText('aaa\nbbb\nccc')
		t.tag_configure('h', elide=True)
		self.assertEqual([s[0] for s in t._displayLines()], [0, 1, 2])
		t.tag_add('h', '2.0', '3.0')		# no text edit
		self.assertEqual([s[0] for s in t._displayLines()], [0, 2])
		t.tag_remove('h', '2.0', '3.0')
		self.assertEqual([s[0] for s in t._displayLines()], [0, 1, 2])

	def test_tag_add_on_margin_tag_invalidates(self):
		root, scr, t = makeText('abc\ndef')
		t.tag_configure('m', lmargin1=4)
		root._update()
		self.assertEqual(scr.find('def')[1], scr.find('abc')[1])
		t.tag_add('m', '2.0', '2.end')
		root._update()
		self.assertEqual(scr.find('def')[1], scr.find('abc')[1] + 4)

	def test_same_line_edit_keeps_later_ranges(self):
		root, scr, t = makeText('ab cd\nef gh\nij')
		t.tag_add('x', '1.3', '1.5', '2.0', '2.2', '3.0', '3.1')
		t.insert('1.1', 'ZZ')
		self.assertEqual(t.tag_ranges('x'),
			('1.5', '1.7', '2.0', '2.2', '3.0', '3.1'))
		t.delete('1.0', '1.4')
		self.assertEqual(t.tag_ranges('x'),
			('1.1', '1.3', '2.0', '2.2', '3.0', '3.1'))
		t.delete('1.3', '2.0')			# joins the lines
		self.assertEqual(t.tag_ranges('x'),
			('1.1', '1.5', '2.0', '2.1'))


class TextManyTagsSpeedTest(unittest.TestCase):

	def test_typing_with_many_tags_is_fast(self):
		# flair: one tag per card, elided ids, margins; typing used to
		# rescan every tag and relayout the whole text on each key
		import time
		root, scr = makeApp(100, 30)
		t = tk.Text(root, wrap='none')
		t.pack(fill='both', expand=1)
		t.tag_configure('id', elide=True)
		t.tag_configure('text', lmargin1=4)
		t.tag_configure('v', foreground='blue')
		y = 1
		for i in range(3000):
			t.insert(f'{y}.0', f'{i}\n\tCARD\tname:\tvalue\n\tx:\t1.0\n')
			t.tag_add('id', f'{y}.0', f'{y + 1}.0')
			t.tag_add(f'card{i}', f'{y}.0', f'{y + 3}.0')
			t.tag_add('v', f'{y + 1}.12', f'{y + 1}.17')
			t.tag_add('text', f'{y + 1}.0', f'{y + 3}.0')
			y += 3
		attach(root)
		t.focus_set()
		t.mark_set('insert', '4500.3')
		t.see('insert')
		root._update()
		start = time.time()
		for ch in 'abcdefghijklmnopqrst':
			press(root, ch)
		self.assertLess((time.time() - start) / 20, 0.05)
		self.assertIn('abcdefghijklmnopqrst', t.get('4500.0', '4500.end'))
