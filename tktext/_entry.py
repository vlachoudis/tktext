import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _clip
from ._events import (KEY_LEFT, KEY_RIGHT, KEY_HOME, KEY_END,
	KEY_BACKSPACE, KEY_DC, KEY_ENTER, KEY_CR,
	KEY_SHIFT_LEFT, KEY_SHIFT_RIGHT, KEY_SHIFT_HOME, KEY_SHIFT_END)

_SHIFT_MAP = {
	KEY_SHIFT_LEFT:  KEY_LEFT,
	KEY_SHIFT_RIGHT: KEY_RIGHT,
	KEY_SHIFT_HOME:  KEY_HOME,
	KEY_SHIFT_END:   KEY_END,
}


class Entry(Widget):
	"""Single-line text entry widget.  Mirrors tkinter.Entry."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'textvariable':		None,
			'show':			'',
			'justify':		'left',
			'selectbackground':	'',
			'selectforeground':	'',
			'exportselection':	True,
			'insertbackground':	'',
			'insertwidth':		1,
			'disabledforeground':	'gray',
			'readonlybackground':	'',
		})
		kwargs.setdefault('relief', 'sunken')
		kwargs.setdefault('borderwidth', 1)
		kwargs.setdefault('width', 20)
		if kwargs:
			self.configure(**kwargs)

		self._buf		= ''
		self._cur		= 0	# cursor column index
		self._scrollX		= 0	# horizontal scroll offset
		self._sel		= None	# None or (start, end) with start < end
		self._selAnchor		= None
		self._mouseDown		= False

	# ------------------------------------------------------------------
	# Buffer access (routes through textvariable when set)
	# ------------------------------------------------------------------

	def _getBuf(self) -> str:
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return str(tv.get())
		return self._buf

	def _setBuf(self, s: str):
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'set'):
			tv.set(s)
		else:
			self._buf = s

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def get(self) -> str:
		"""Return current entry contents."""
		return self._getBuf()

	def insert(self, idx: object, s: str):
		"""Insert *s* at position *idx* ('end' or int)."""
		if self._opts.get('state') == 'disabled':
			return
		buf = self._getBuf()
		pos = self._resolveIdx(idx, buf)
		new = buf[:pos] + s + buf[pos:]
		self._setBuf(new)
		self._cur = pos + len(s)
		self._clampCur()
		self._scrollToCursor()
		self._markDirty()

	def delete(self, first: object, last: object = None):
		"""Delete characters from *first* to *last* (exclusive)."""
		if self._opts.get('state') == 'disabled':
			return
		buf  = self._getBuf()
		pos1 = self._resolveIdx(first, buf)
		if last is None:
			pos2 = pos1 + 1
		else:
			pos2 = self._resolveIdx(last, buf)
		pos1 = max(0, min(pos1, len(buf)))
		pos2 = max(0, min(pos2, len(buf)))
		if pos1 > pos2:
			pos1, pos2 = pos2, pos1
		self._setBuf(buf[:pos1] + buf[pos2:])
		self._cur = pos1
		self._sel = None
		self._clampCur()
		self._scrollToCursor()
		self._markDirty()

	def icursor(self, idx: object):
		"""Set insertion cursor to *idx*."""
		buf = self._getBuf()
		self._cur = self._resolveIdx(idx, buf)
		self._clampCur()
		self._scrollToCursor()
		self._markDirty()

	def index(self, idx: object) -> int:
		"""Return integer index for *idx*."""
		buf = self._getBuf()
		return self._resolveIdx(idx, buf)

	def selectionRange(self, start: int, end: int):
		"""Select from *start* to *end*."""
		buf = self._getBuf()
		s   = max(0, min(start, len(buf)))
		e   = max(0, min(end, len(buf)))
		if s > e:
			s, e = e, s
		self._sel = (s, e) if s != e else None
		self._markDirty()

	selection_range = selectionRange

	def selectionClear(self):
		"""Clear selection."""
		self._sel = None
		self._markDirty()

	selection_clear = selectionClear

	def selectionPresent(self) -> bool:
		"""Return True if any text is selected."""
		return self._sel is not None

	selection_present = selectionPresent

	def selectionFrom(self, idx: int):
		"""Set selection anchor to *idx*."""
		self._selAnchor = idx
		if self._sel is None:
			self._sel = (idx, idx) if False else None

	selection_from = selectionFrom

	def selectionTo(self, idx: int):
		"""Extend selection to *idx* from current anchor."""
		if self._selAnchor is None:
			self._selAnchor = idx
		a = self._selAnchor
		b = idx
		if a <= b:
			self._sel = (a, b) if a != b else None
		else:
			self._sel = (b, a) if a != b else None
		self._markDirty()

	selection_to = selectionTo

	def xview(self, *args):
		"""Scroll view (simplified)."""
		if not args:
			return
		if args[0] == 'moveto':
			buf = self._getBuf()
			frac = float(args[1])
			self._scrollX = int(frac * max(1, len(buf)))
			self._markDirty()
		elif args[0] == 'scroll':
			n = int(args[1])
			self._scrollX = max(0, self._scrollX + n)
			self._markDirty()

	# ------------------------------------------------------------------
	# Preferred size / cursor position
	# ------------------------------------------------------------------

	def _preferredSize(self):
		bd  = int(self._opts.get('borderwidth') or 0)
		ow  = int(self._opts.get('width') or 20)
		return (ow + 2*bd, 1 + 2*bd)

	def _cursorPos(self):
		"""Return screen (y, x) for the cursor block."""
		bd = int(self._opts.get('borderwidth') or 0)
		return (self._y + bd, self._x + bd + self._cur - self._scrollX)

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _resolveIdx(self, idx, buf: str) -> int:
		if idx == 'end' or idx == 'END':
			return len(buf)
		if idx == 'insert':
			return self._cur
		if idx == 'anchor':
			return self._selAnchor or 0
		if idx == 'sel.first':
			return self._sel[0] if self._sel else 0
		if idx == 'sel.last':
			return self._sel[1] if self._sel else 0
		try:
			return int(idx)
		except (TypeError, ValueError):
			return 0

	def _clampCur(self):
		buf = self._getBuf()
		self._cur = max(0, min(self._cur, len(buf)))

	def _scrollToCursor(self):
		if self._w <= 0:
			return
		bd   = int(self._opts.get('borderwidth') or 0)
		visW = max(1, self._w - 2*bd)
		if self._cur < self._scrollX:
			self._scrollX = self._cur
		elif self._cur >= self._scrollX + visW:
			self._scrollX = self._cur - visW + 1

	def _deleteSelection(self) -> bool:
		"""Delete selected text; return True if anything was deleted."""
		if self._sel is None:
			return False
		s, e = self._sel
		buf  = self._getBuf()
		self._setBuf(buf[:s] + buf[e:])
		self._cur       = s
		self._sel       = None
		self._selAnchor = None
		return True

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return

		state  = self._opts.get('state', 'normal')
		focused = self._focused
		bd     = int(self._opts.get('borderwidth') or 0)
		relief = self._opts.get('relief', 'sunken')

		if state == 'disabled':
			attr = self._getAttr(fg='gray')
		else:
			attr = self._getAttr()

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)
		if bd > 0:
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		visW = max(1, self._w - 2*bd)
		buf  = self._getBuf()
		show = self._opts.get('show') or ''
		if show:
			disp = show * len(buf)
		else:
			disp = buf

		screenY = self._y + bd
		screenX = self._x + bd

		selAttr = attr | curses.A_REVERSE
		sfg     = self._opts.get('selectforeground') or ''
		sbg     = self._opts.get('selectbackground') or ''
		if sfg or sbg:
			selAttr = self._getAttr(fg=sfg, bg=sbg)

		for j in range(visW):
			col   = self._scrollX + j
			inSel = (self._sel is not None and
				self._sel[0] <= col < self._sel[1])
			if col < len(disp):
				ch    = disp[col]
				cAttr = selAttr if inSel else attr
			else:
				ch    = ' '
				cAttr = selAttr if inSel else attr
			try:
				scr.addch(screenY, screenX + j, ch, cAttr)
			except curses.error:
				pass

	# ------------------------------------------------------------------
	# Focus
	# ------------------------------------------------------------------

	def _isFocusable(self) -> bool:
		return self._opts.get('state', 'normal') == 'normal'

	# ------------------------------------------------------------------
	# Keyboard input
	# ------------------------------------------------------------------

	def _handleKey(self, key: int) -> bool:
		if self._opts.get('state') == 'disabled':
			return False

		buf   = self._getBuf()
		c     = self._cur

		# Ctrl+A — select all
		if key == 1:
			self._selAnchor = 0
			self._sel       = (0, len(buf)) if buf else None
			self._markDirty()
			return True

		# Shift+movement — extend selection
		extendSel = key in _SHIFT_MAP
		if extendSel:
			if self._selAnchor is None:
				self._selAnchor = c
			key = _SHIFT_MAP[key]

		if key == KEY_LEFT:
			if not extendSel and self._sel:
				c = self._sel[0]	# collapse to start
				self._sel       = None
				self._selAnchor = None
			elif c > 0:
				c -= 1
		elif key == KEY_RIGHT:
			if not extendSel and self._sel:
				c = self._sel[1]	# collapse to end
				self._sel       = None
				self._selAnchor = None
			elif c < len(buf):
				c += 1
		elif key == KEY_HOME:
			c = 0
		elif key == KEY_END:
			c = len(buf)
		elif key in (KEY_BACKSPACE, 127):
			if not self._deleteSelection():
				if c > 0:
					self._setBuf(buf[:c-1] + buf[c:])
					c -= 1
			else:
				buf = self._getBuf()
				c   = self._cur
		elif key == KEY_DC:
			if not self._deleteSelection():
				if c < len(buf):
					self._setBuf(buf[:c] + buf[c+1:])
			else:
				c = self._cur
		elif key in (KEY_ENTER, KEY_CR):
			self._dispatch('<Return>', _make_key_event(key, self))
			self._markDirty()
			return True
		elif 32 <= key <= 126:
			self._deleteSelection()
			buf = self._getBuf()
			c   = self._cur
			ch  = chr(key)
			self._setBuf(buf[:c] + ch + buf[c:])
			c += 1
		else:
			return super()._handleKey(key)

		# Update selection for shift+movement
		if extendSel:
			a = self._selAnchor
			if a == c:
				self._sel = None
			elif a < c:
				self._sel = (a, c)
			else:
				self._sel = (c, a)
		elif key in (KEY_LEFT, KEY_RIGHT, KEY_HOME, KEY_END):
			if not extendSel:
				self._sel       = None
				self._selAnchor = None

		self._cur = c
		self._clampCur()
		self._scrollToCursor()
		self._markDirty()
		return True

	# ------------------------------------------------------------------
	# Mouse input
	# ------------------------------------------------------------------

	def _handleMouse(self, mx: int, my: int, bstate: int) -> bool:
		bd = int(self._opts.get('borderwidth') or 0)

		release = bool(bstate & (curses.BUTTON1_RELEASED | curses.BUTTON1_CLICKED))
		press   = bool(bstate & curses.BUTTON1_PRESSED)

		if release:
			self._mouseDown = False

		onBorder = (mx < self._x + bd or mx >= self._x + self._w - bd or
			my < self._y + bd or my >= self._y + self._h - bd)
		if onBorder:
			if release and self._selAnchor is not None:
				mx = max(self._x + bd, min(mx, self._x + self._w - bd - 1))
			else:
				return False

		col = self._scrollX + (mx - self._x - bd)
		buf = self._getBuf()
		col = max(0, min(col, len(buf)))

		if press and not self._mouseDown:
			self._mouseDown = True
			self._sel       = None
			self._selAnchor = col
			self._cur       = col
		elif self._mouseDown:
			if self._selAnchor is not None:
				a = self._selAnchor
				if a != col:
					if a < col:
						self._sel = (a, col)
					else:
						self._sel = (col, a)
				else:
					self._sel = None
			if release:
				self._selAnchor = None

		self._cur = col
		self._clampCur()
		self._scrollToCursor()
		self._markDirty()
		return True


# ---------------------------------------------------------------------------
# Helper: minimal key event object
# ---------------------------------------------------------------------------

class _EntryKeyEvent:
	def __init__(self, key, widget):
		self.widget  = widget
		self.keycode = key
		self.keysym  = 'Return'
		self.char    = ''
		self.type    = 'KeyPress'


def _make_key_event(key, widget):
	return _EntryKeyEvent(key, widget)
