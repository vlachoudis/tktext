import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _clip
from ._events import (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_PPAGE, KEY_NPAGE,
	KEY_BACKSPACE, KEY_DC, KEY_ENTER, KEY_CR, KEY_TAB, KEY_ESC,
	KEY_SHIFT_UP, KEY_SHIFT_DOWN, KEY_SHIFT_LEFT, KEY_SHIFT_RIGHT,
	KEY_SHIFT_HOME, KEY_SHIFT_END, KEY_SHIFT_PPAGE, KEY_SHIFT_NPAGE)

# Shift+key → plain movement key mapping
_SHIFT_MAP = {
	KEY_SHIFT_UP:    KEY_UP,
	KEY_SHIFT_DOWN:  KEY_DOWN,
	KEY_SHIFT_LEFT:  KEY_LEFT,
	KEY_SHIFT_RIGHT: KEY_RIGHT,
	KEY_SHIFT_HOME:  KEY_HOME,
	KEY_SHIFT_END:   KEY_END,
	KEY_SHIFT_PPAGE: KEY_PPAGE,
	KEY_SHIFT_NPAGE: KEY_NPAGE,
}

_MOVEMENT_KEYS = frozenset({
	KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_PPAGE, KEY_NPAGE,
})


class Text(Widget):
	"""Multi-line text editor widget.  Mirrors tkinter.Text.

	Index format: "line.col"  (line is 1-based, col is 0-based)
	Special indices: "insert", "end", "sel.first", "sel.last"
	"""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'wrap':			'word',
			'undo':			False,
			'autoseparators':	True,
			'maxundo':		-1,
			'insertbackground':	'',
			'insertwidth':		1,
			'selectbackground':	'',
			'selectforeground':	'',
			'inactiveselectbackground': '',
			'exportselection':	True,
			'spacing1':		0,
			'spacing2':		0,
			'spacing3':		0,
			'tabs':			(),
			'tabstyle':		'tabular',
		})
		kwargs.setdefault('relief', 'sunken')
		kwargs.setdefault('borderwidth', 1)
		kwargs.setdefault('width', 40)
		kwargs.setdefault('height', 10)
		if kwargs:
			self.configure(**kwargs)

		# Buffer: list of str (one per logical line)
		self._buf	= ['']
		# Cursor: (row, col) 0-based
		self._cur	= (0, 0)
		# Viewport scroll offset: (scroll_row, scroll_col)
		self._scroll	= (0, 0)
		# Selection: None or (start_row, start_col, end_row, end_col)
		self._sel	= None
		self._selAnchor	= None
		# Mouse drag state
		self._mouseDown	= False
		# Tag configuration: name -> attr
		self._tagCfg	= {}
		# Tag ranges: name -> [(r0,c0,r1,c1), ...]
		self._tagRanges	= {}
		# Marks: name -> (row, col)
		self._marks	= {'insert': (0, 0)}
		# Undo stack
		self._undoStack	= []
		self._redoStack	= []

	# ------------------------------------------------------------------
	# Index parsing / normalisation
	# ------------------------------------------------------------------

	def _parseIndex(self, idx):
		"""Convert any index form to (row, col) 0-based."""
		if idx == 'insert':
			return self._marks.get('insert', (0, 0))
		if idx == 'end':
			r = len(self._buf) - 1
			return (r, len(self._buf[r]))
		if idx == 'sel.first':
			if self._sel:
				return (self._sel[0], self._sel[1])
			return (0, 0)
		if idx == 'sel.last':
			if self._sel:
				return (self._sel[2], self._sel[3])
			return (0, 0)
		if isinstance(idx, str) and '.' in idx:
			parts = idx.split('.')
			try:
				r = int(parts[0]) - 1	# 1-based -> 0-based
				c = int(parts[1])
				r = max(0, min(r, len(self._buf) - 1))
				c = max(0, min(c, len(self._buf[r])))
				return (r, c)
			except ValueError:
				pass
		# Named marks
		if isinstance(idx, str) and idx in self._marks:
			return self._marks[idx]
		return (0, 0)

	def _toTkIndex(self, row, col):
		return f'{row + 1}.{col}'

	def _clampCur(self, r, c):
		r = max(0, min(r, len(self._buf) - 1))
		c = max(0, min(c, len(self._buf[r])))
		return (r, c)

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def insert(self, idx, chars, *tags):
		"""Insert *chars* at *idx*."""
		if self._opts.get('state') == 'disabled':
			return
		r, c = self._parseIndex(idx)
		r = max(0, min(r, len(self._buf) - 1))
		c = max(0, min(c, len(self._buf[r])))

		# Push undo
		if self._opts.get('undo'):
			self._undoStack.append(('insert', r, c, chars))
			self._redoStack.clear()

		lines = chars.split('\n')
		tail  = self._buf[r][c:]
		self._buf[r] = self._buf[r][:c] + lines[0]

		for i in range(1, len(lines)):
			self._buf.insert(r + i, lines[i])
		self._buf[r + len(lines) - 1] += tail

		newR = r + len(lines) - 1
		newC = len(lines[-1]) if len(lines) > 1 else c + len(lines[0])
		self._marks['insert'] = (newR, newC)
		self._cur = (newR, newC)
		self._scrollToCursor()
		self._markDirty()

	def delete(self, idx1, idx2=None):
		"""Delete text between *idx1* and *idx2* (or one char at *idx1*)."""
		if self._opts.get('state') == 'disabled':
			return
		r1, c1 = self._parseIndex(idx1)
		if idx2 is None:
			r2, c2 = r1, c1 + 1
		else:
			r2, c2 = self._parseIndex(idx2)

		r1, c1 = self._clampCur(r1, c1)
		r2, c2 = self._clampCur(r2, c2)

		# Normalise order
		if (r1, c1) > (r2, c2):
			r1, c1, r2, c2 = r2, c2, r1, c1

		if r1 == r2:
			self._buf[r1] = self._buf[r1][:c1] + self._buf[r1][c2:]
		else:
			joined = self._buf[r1][:c1] + self._buf[r2][c2:]
			self._buf[r1:r2+1] = [joined]

		if not self._buf:
			self._buf = ['']

		self._cur = self._clampCur(r1, c1)
		self._marks['insert'] = self._cur
		self._scrollToCursor()
		self._markDirty()

	def get(self, idx1, idx2=None):
		"""Return text between *idx1* and *idx2*."""
		r1, c1 = self._parseIndex(idx1)
		if idx2 is None:
			r2, c2 = r1, c1 + 1
		elif idx2 == 'end':
			r2 = len(self._buf) - 1
			c2 = len(self._buf[r2])
		else:
			r2, c2 = self._parseIndex(idx2)

		r1, c1 = self._clampCur(r1, c1)
		r2, c2 = self._clampCur(r2, c2)

		if r1 == r2:
			return self._buf[r1][c1:c2]
		parts = [self._buf[r1][c1:]]
		for r in range(r1 + 1, r2):
			parts.append(self._buf[r])
		parts.append(self._buf[r2][:c2])
		return '\n'.join(parts)

	def see(self, idx):
		"""Scroll so that *idx* is visible."""
		r, c = self._parseIndex(idx)
		self._scrollTo(r, c)
		self._markDirty()

	def markSet(self, name, idx):
		"""Set named mark to *idx*."""
		self._marks[name] = self._parseIndex(idx)
		if name == 'insert':
			self._cur = self._marks[name]

	mark_set = markSet

	def markNames(self):
		return list(self._marks.keys())

	mark_names = markNames

	# Tag API

	def tagConfigure(self, name, **kwargs):
		"""Configure appearance of tag *name*."""
		attr = 0
		app = self._getApp()
		if app:
			fg = kwargs.get('foreground', '') or kwargs.get('fg', '')
			bg = kwargs.get('background', '') or kwargs.get('bg', '')
			attr = app._colors.getAttr(fg, bg,
				bold      = 'bold' in str(kwargs.get('font', '')),
				underline = kwargs.get('underline', False),
				reverse   = bool(kwargs.get('background') or kwargs.get('bg')),
			)
		if 'reverse' in kwargs:
			if kwargs['reverse']:
				attr |= curses.A_REVERSE
		self._tagCfg[name] = attr

	tag_configure = tagConfigure
	tag_config    = tagConfigure

	def tagAdd(self, name, idx1, idx2):
		"""Apply tag *name* to range [*idx1*, *idx2*)."""
		r1, c1 = self._parseIndex(idx1)
		r2, c2 = self._parseIndex(idx2)
		self._tagRanges.setdefault(name, []).append((r1, c1, r2, c2))
		self._markDirty()

	tag_add = tagAdd

	def tagRemove(self, name, idx1, idx2):
		"""Remove tag from range."""
		if name in self._tagRanges:
			r1, c1 = self._parseIndex(idx1)
			r2, c2 = self._parseIndex(idx2)
			self._tagRanges[name] = [
				(a,b,c,d) for a,b,c,d in self._tagRanges[name]
				if not ((a,b) >= (r1,c1) and (c,d) <= (r2,c2))
			]
		self._markDirty()

	tag_remove = tagRemove

	def tagDelete(self, *names):
		for n in names:
			self._tagCfg.pop(n, None)
			self._tagRanges.pop(n, None)
		self._markDirty()

	tag_delete = tagDelete

	def tagRanges(self, name):
		return list(self._tagRanges.get(name, []))

	tag_ranges = tagRanges

	# Selection

	def tagAdd_sel(self, idx1, idx2):
		self.tagAdd('sel', idx1, idx2)

	def tag_add_sel(self, idx1, idx2):
		self.tagAdd('sel', idx1, idx2)

	def selGet(self):
		"""Return selected text or ''."""
		if self._sel:
			r1, c1, r2, c2 = self._sel
			return self.get(self._toTkIndex(r1, c1), self._toTkIndex(r2, c2))
		return ''

	# Undo / redo

	def editUndo(self):
		if self._undoStack:
			op = self._undoStack.pop()
			# simplified: just mark dirty
			self._markDirty()

	def editRedo(self):
		if self._redoStack:
			self._markDirty()

	edit_undo = editUndo
	edit_redo = editRedo

	def editSeparator(self):
		pass

	edit_separator = editSeparator

	# ------------------------------------------------------------------
	# Selection helpers
	# ------------------------------------------------------------------

	def _selNormalised(self):
		"""Return (r0,c0, r1,c1) with start <= end, or None."""
		if not self._sel:
			return None
		r0, c0, r1, c1 = self._sel
		if (r0, c0) > (r1, c1):
			return (r1, c1, r0, c0)
		return (r0, c0, r1, c1)

	def _deleteSelection(self):
		"""Delete selected text.  Return True if a selection existed."""
		s = self._selNormalised()
		if s is None:
			return False
		r1, c1, r2, c2 = s
		self._sel       = None
		self._selAnchor = None
		if r1 == r2:
			self._buf[r1] = self._buf[r1][:c1] + self._buf[r1][c2:]
		else:
			self._buf[r1:r2+1] = [self._buf[r1][:c1] + self._buf[r2][c2:]]
		if not self._buf:
			self._buf = ['']
		self._cur              = self._clampCur(r1, c1)
		self._marks['insert']  = self._cur
		return True

	# ------------------------------------------------------------------
	# Scrolling
	# ------------------------------------------------------------------

	def _scrollToCursor(self):
		r, c = self._cur
		self._scrollTo(r, c)

	def _scrollTo(self, r, c):
		bd   = int(self._opts.get('borderwidth') or 0)
		visH = max(1, self._h - 2*bd)
		visW = max(1, self._w - 2*bd)
		sy, sx = self._scroll

		if r < sy:
			sy = r
		elif r >= sy + visH:
			sy = r - visH + 1

		if c < sx:
			sx = c
		elif c >= sx + visW:
			sx = c - visW + 1

		self._scroll = (max(0, sy), max(0, sx))

	def xview(self, *args):
		pass

	def yview(self, *args):
		if not args:
			return
		if args[0] == 'moveto':
			frac = float(args[1])
			total = len(self._buf)
			self._scroll = (int(frac * total), self._scroll[1])
			self._markDirty()
		elif args[0] == 'scroll':
			n = int(args[1])
			unit = args[2] if len(args) > 2 else 'units'
			bd   = int(self._opts.get('borderwidth') or 0)
			visH = max(1, self._h - 2*bd)
			if unit == 'pages':
				n *= visH
			sy = max(0, self._scroll[0] + n)
			self._scroll = (sy, self._scroll[1])
			self._markDirty()

	# ------------------------------------------------------------------
	# Preferred size
	# ------------------------------------------------------------------

	def _preferredSize(self):
		bd  = int(self._opts.get('borderwidth') or 0)
		ow  = int(self._opts.get('width') or 40)
		oh  = int(self._opts.get('height') or 10)
		return (ow + 2*bd, oh + 2*bd)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def _attrForChar(self, row, col):
		"""Return combined curses attr for character at (row, col)."""
		attr = 0
		for name, ranges in self._tagRanges.items():
			tagAttr = self._tagCfg.get(name, 0)
			for r0, c0, r1, c1 in ranges:
				inRange = False
				if r0 == r1:
					inRange = (row == r0 and c0 <= col < c1)
				elif row == r0:
					inRange = col >= c0
				elif row == r1:
					inRange = col < c1
				elif r0 < row < r1:
					inRange = True
				if inRange:
					attr |= tagAttr
		# Selection highlight
		if self._sel:
			sr0, sc0, sr1, sc1 = self._sel
			if (sr0, sc0) > (sr1, sc1):
				sr0, sc0, sr1, sc1 = sr1, sc1, sr0, sc0
			inSel = False
			if sr0 == sr1:
				inSel = (row == sr0 and sc0 <= col < sc1)
			elif row == sr0:
				inSel = col >= sc0
			elif row == sr1:
				inSel = col < sc1
			elif sr0 < row < sr1:
				inSel = True
			if inSel:
				attr |= curses.A_REVERSE
		return attr

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return

		bd     = int(self._opts.get('borderwidth') or 0)
		attr   = self._getAttr()
		relief = self._opts.get('relief', 'sunken')

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)
		if bd > 0:
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		visH = max(1, self._h - 2*bd)
		visW = max(1, self._w - 2*bd)
		sy, sx = self._scroll
		cr, cc = self._cur

		for i in range(visH):
			bufRow = sy + i
			if bufRow >= len(self._buf):
				break
			line = self._buf[bufRow]
			screenY = self._y + bd + i
			screenX = self._x + bd

			for j in range(visW):
				bufCol = sx + j
				if bufCol < len(line):
					ch   = line[bufCol]
					cAttr = attr | self._attrForChar(bufRow, bufCol)
				else:
					ch    = ' '
					cAttr = attr
				try:
					scr.addch(screenY, screenX + j, ch, cAttr)
				except curses.error:
					pass

		# Scrollbar indicator (right edge)
		total = len(self._buf)
		if total > visH and self._w > bd + 1:
			barX = self._x + self._w - 1
			thumbPos = int(sy * visH / total) if total else 0
			thumbSize = max(1, int(visH * visH / total))
			for i in range(visH):
				ch = '#' if thumbPos <= i < thumbPos + thumbSize else '|'
				try:
					scr.addch(self._y + bd + i, barX, ch, attr)
				except curses.error:
					pass

	def _cursorPos(self):
		"""Return screen (y, x) of cursor for Tk to position the cursor block."""
		bd  = int(self._opts.get('borderwidth') or 0)
		cr, cc = self._cur
		sy, sx = self._scroll
		screenY = self._y + bd + (cr - sy)
		screenX = self._x + bd + (cc - sx)
		return (screenY, screenX)

	# ------------------------------------------------------------------
	# Keyboard input
	# ------------------------------------------------------------------

	def _isFocusable(self):
		return self._opts.get('state', 'normal') == 'normal'

	def _handleKey(self, key):
		if self._opts.get('state') == 'disabled':
			return False

		r, c = self._cur
		dirty = True

		# Ctrl+A — select all
		if key == 1:
			lastR = len(self._buf) - 1
			self._selAnchor = (0, 0)
			self._sel       = (0, 0, lastR, len(self._buf[lastR]))
			self._markDirty()
			return True

		# Determine whether this is a shift+movement (extends selection)
		extendSel = key in _SHIFT_MAP
		if extendSel:
			if self._selAnchor is None:
				self._selAnchor = (r, c)
			key = _SHIFT_MAP[key]

		line = self._buf[r]

		if key == KEY_UP:
			r = max(0, r - 1)
			c = min(c, len(self._buf[r]))
		elif key == KEY_DOWN:
			r = min(len(self._buf) - 1, r + 1)
			c = min(c, len(self._buf[r]))
		elif key == KEY_LEFT:
			if not extendSel and self._sel:
				r, c = self._selNormalised()[:2]	# collapse to start
			elif c > 0:
				c -= 1
			elif r > 0:
				r -= 1
				c = len(self._buf[r])
		elif key == KEY_RIGHT:
			if not extendSel and self._sel:
				s = self._selNormalised()
				r, c = s[2], s[3]			# collapse to end
			elif c < len(line):
				c += 1
			elif r < len(self._buf) - 1:
				r += 1
				c = 0
		elif key == KEY_HOME:
			c = 0
		elif key == KEY_END:
			c = len(self._buf[r])
		elif key == KEY_PPAGE:
			bd   = int(self._opts.get('borderwidth') or 0)
			visH = max(1, self._h - 2*bd)
			r = max(0, r - visH)
			c = min(c, len(self._buf[r]))
		elif key == KEY_NPAGE:
			bd   = int(self._opts.get('borderwidth') or 0)
			visH = max(1, self._h - 2*bd)
			r = min(len(self._buf) - 1, r + visH)
			c = min(c, len(self._buf[r]))
		elif key in (KEY_BACKSPACE, 127):
			if not self._deleteSelection():
				if c > 0:
					self._buf[r] = line[:c-1] + line[c:]
					c -= 1
				elif r > 0:
					prevLen = len(self._buf[r-1])
					self._buf[r-1] += self._buf[r]
					del self._buf[r]
					r -= 1
					c = prevLen
			else:
				r, c = self._cur
		elif key == KEY_DC:
			if not self._deleteSelection():
				if c < len(line):
					self._buf[r] = line[:c] + line[c+1:]
				elif r < len(self._buf) - 1:
					self._buf[r] = self._buf[r] + self._buf[r+1]
					del self._buf[r+1]
			else:
				r, c = self._cur
		elif key in (KEY_ENTER, KEY_CR):
			self._deleteSelection()
			r, c  = self._cur
			line  = self._buf[r]
			tail  = line[c:]
			self._buf[r] = line[:c]
			self._buf.insert(r+1, tail)
			r += 1
			c  = 0
		elif key == KEY_TAB:
			self._deleteSelection()
			r, c  = self._cur
			line  = self._buf[r]
			spaces = '    '
			self._buf[r] = line[:c] + spaces + line[c:]
			c += len(spaces)
		elif 32 <= key <= 126:
			self._deleteSelection()
			r, c  = self._cur
			line  = self._buf[r]
			ch    = chr(key)
			self._buf[r] = line[:c] + ch + line[c:]
			c += 1
		else:
			dirty = False
			return super()._handleKey(key)

		# Update selection state
		if extendSel:
			ar, ac = self._selAnchor
			if (ar, ac) == (r, c):
				self._sel = None
			else:
				self._sel = (ar, ac, r, c)
		elif key in _MOVEMENT_KEYS:
			self._sel       = None
			self._selAnchor = None

		self._cur = self._clampCur(r, c)
		self._marks['insert'] = self._cur
		self._scrollToCursor()
		if dirty:
			self._markDirty()
		return True

	def _handleMouse(self, mx, my, bstate):
		bd = int(self._opts.get('borderwidth') or 0)

		release = bool(bstate & (curses.BUTTON1_RELEASED | curses.BUTTON1_CLICKED))
		press   = bool(bstate & curses.BUTTON1_PRESSED)

		if release:
			self._mouseDown = False

		# Reject clicks that land on the border, but let drag-release through
		# so we always clear _mouseDown even if cursor is on the border.
		onBorder = (mx < self._x + bd or mx >= self._x + self._w - bd or
				my < self._y + bd or my >= self._y + self._h - bd)
		if onBorder:
			if release:
				# Finalise drag with clamped position
				if self._selAnchor is not None:
					# Clamp to nearest content cell
					my = max(self._y + bd, min(my, self._y + self._h - bd - 1))
					mx = max(self._x + bd, min(mx, self._x + self._w - bd - 1))
				else:
					return False
			else:
				return False

		sy, sx = self._scroll
		r = max(0, min(sy + (my - self._y - bd), len(self._buf) - 1))
		c = max(0, min(sx + (mx - self._x - bd), len(self._buf[r])))

		if press and not self._mouseDown:
			# Initial button-down: start drag
			self._mouseDown = True
			self._sel       = None
			self._selAnchor = (r, c)
		elif self._mouseDown:
			# Drag motion or repeated BUTTON1_PRESSED on motion events:
			# always extend selection from the original anchor
			if self._selAnchor is not None:
				if self._selAnchor != (r, c):
					self._sel = (self._selAnchor[0], self._selAnchor[1], r, c)
				else:
					self._sel = None
			if release:
				self._selAnchor = None

		self._cur             = (r, c)
		self._marks['insert'] = self._cur
		self._markDirty()
		return False
