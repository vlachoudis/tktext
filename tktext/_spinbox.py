import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _clip
from ._events import (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_BACKSPACE, KEY_DC, KEY_ENTER, KEY_CR)


class Spinbox(Widget):
	"""Single-line entry with ▲▼ increment/decrement buttons.
	Mirrors tkinter.Spinbox / tkinter.ttk.Spinbox."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'from_':        0.0,
			'to':           float('inf'),
			'increment':    1.0,
			'values':       (),
			'textvariable': None,
			'command':      None,
			'wrap':         False,
			'format':       '',
			'justify':      'left',
			'show':         '',
			'validate':     'none',
			'validatecommand': None,
		})
		kwargs.setdefault('relief',      'sunken')
		kwargs.setdefault('borderwidth', 1)
		kwargs.setdefault('width',       10)
		if kwargs:
			self.configure(**kwargs)

		vals = self._opts.get('values')
		tv   = self._opts.get('textvariable')
		if tv is not None:
			initText = str(tv.get())
		elif vals:
			initText = str(list(vals)[0])
		else:
			initText = str(int(self._opts.get('from_') or 0))

		self._text   = initText
		self._cur    = len(self._text)
		self._scrollX = 0
		self._valIdx = 0

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def get(self) -> str:
		tv = self._opts.get('textvariable')
		return tv.get() if tv is not None else self._text

	def set(self, value: str):
		self._text = str(value)
		self._cur  = len(self._text)
		tv = self._opts.get('textvariable')
		if tv is not None:
			tv.set(value)
		self._scrollToCursor()
		self._markDirty()

	def invoke(self, element: str = 'buttonup'):
		"""Programmatically press the up or down button."""
		self._increment(+1 if element == 'buttonup' else -1)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _increment(self, direction: int):
		vals = list(self._opts.get('values') or [])
		if vals:
			n           = len(vals)
			try:
				cur = vals.index(self.get())
			except ValueError:
				cur = 0
			nxt = cur + direction
			if self._opts.get('wrap'):
				nxt %= n
			else:
				nxt = max(0, min(n - 1, nxt))
			self.set(str(vals[nxt]))
		else:
			try:
				v = float(self.get())
			except ValueError:
				v = float(self._opts.get('from_') or 0)
			inc = float(self._opts.get('increment') or 1)
			v  += direction * inc
			lo  = float(self._opts.get('from_') if self._opts.get('from_') is not None else float('-inf'))
			hi  = float(self._opts.get('to')    if self._opts.get('to')    is not None else float('inf'))
			if self._opts.get('wrap'):
				if v > hi:   v = lo
				elif v < lo: v = hi
			else:
				v = max(lo, min(hi, v))
			fmt = self._opts.get('format') or ''
			self.set(fmt % v if fmt else f'{v:g}')
		cmd = self._opts.get('command')
		if callable(cmd):
			cmd()

	def _visW(self) -> int:
		bd = int(self._opts.get('borderwidth') or 0)
		return max(1, self._w - 2*bd - 3)  # 3 for ' ▲▼'

	def _scrollToCursor(self):
		visW = self._visW()
		if self._cur < self._scrollX:
			self._scrollX = self._cur
		elif self._cur >= self._scrollX + visW:
			self._scrollX = self._cur - visW + 1

	def _preferredSize(self):
		bd = int(self._opts.get('borderwidth') or 0)
		ow = int(self._opts.get('width') or 10)
		return (ow + 2*bd + 3, 1 + 2*bd)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return
		bd    = int(self._opts.get('borderwidth') or 0)
		attr  = self._getAttr()
		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)
		if bd > 0:
			_drawBorder(scr, self._y, self._x, self._h, self._w,
				self._opts.get('relief', 'sunken'), attr)

		visW = self._visW()
		by   = self._y + bd + (self._h - 2*bd) // 2
		bx   = self._x + bd

		tv   = self._opts.get('textvariable')
		text = tv.get() if tv is not None else self._text
		show = self._opts.get('show') or ''
		disp = (show * len(text)) if show else text
		vis  = disp[self._scrollX:self._scrollX + visW]
		_addStr(scr, by, bx, vis.ljust(visW), attr)

		btnX  = self._x + self._w - bd - 3
		battr = attr | (curses.A_REVERSE if self._focused else 0)
		_addStr(scr, by, btnX, ' ▲▼', battr)

	def _cursorPos(self):
		bd = int(self._opts.get('borderwidth') or 0)
		cy = self._y + bd + (self._h - 2*bd) // 2
		cx = self._x + bd + (self._cur - self._scrollX)
		return (cy, cx)

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _isFocusable(self):
		return self._opts.get('state', 'normal') == 'normal'

	def _handleKey(self, key):
		if self._opts.get('state') == 'disabled':
			return False
		if key == KEY_UP:
			self._increment(+1)
			return True
		if key == KEY_DOWN:
			self._increment(-1)
			return True
		if key in (KEY_ENTER, KEY_CR):
			cmd = self._opts.get('command')
			if callable(cmd):
				cmd()
			self._dispatch('<Return>', type('E', (), {'widget': self, 'keysym': 'Return', 'char': '', 'type': 'KeyPress'})())
			return True

		tv   = self._opts.get('textvariable')
		text = self._text
		c    = self._cur
		if key == KEY_LEFT:
			self._cur = max(0, c - 1)
		elif key == KEY_RIGHT:
			self._cur = min(len(text), c + 1)
		elif key == KEY_HOME:
			self._cur = 0
		elif key == KEY_END:
			self._cur = len(text)
		elif key in (KEY_BACKSPACE, 127):
			if c > 0:
				self._text = text[:c-1] + text[c:]
				self._cur -= 1
				if tv: tv.set(self._text)
		elif key == KEY_DC:
			if c < len(text):
				self._text = text[:c] + text[c+1:]
				if tv: tv.set(self._text)
		elif 32 <= key <= 126:
			self._text = text[:c] + chr(key) + text[c:]
			self._cur += 1
			if tv: tv.set(self._text)
		else:
			return super()._handleKey(key)
		self._scrollToCursor()
		self._markDirty()
		return True

	def _handleMouse(self, mx, my, bstate):
		if not (bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED)):
			return False
		bd   = int(self._opts.get('borderwidth') or 0)
		btnX = self._x + self._w - bd - 3
		if mx >= btnX:
			col = mx - btnX
			self._increment(+1 if col <= 1 else -1)
		else:
			bx = self._x + bd
			self._cur = max(0, min(len(self._text), self._scrollX + (mx - bx)))
			self._scrollToCursor()
		self._markDirty()
		return True
