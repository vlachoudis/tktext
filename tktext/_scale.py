import curses
from ._core import Widget, _addStr, _fillRect, _pad, _clip
from ._events import KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_HOME, KEY_END


class Scale(Widget):
	"""Horizontal or vertical slider widget.  Mirrors tkinter.Scale."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'from_':        0.0,
			'to':           100.0,
			'orient':       'horizontal',
			'variable':     None,
			'command':      None,
			'resolution':   1.0,
			'length':       20,
			'showvalue':    1,
			'label':        '',
			'tickinterval': 0,
			'digits':       0,
			'troughcolor':  '',
			'sliderlength': 1,
		})
		kwargs.setdefault('relief',      'flat')
		kwargs.setdefault('borderwidth', 0)
		if kwargs:
			self.configure(**kwargs)

		var = self._opts.get('variable')
		try:
			self._value = float(var.get()) if var is not None else float(self._opts.get('from_') or 0)
		except (TypeError, ValueError):
			self._value = float(self._opts.get('from_') or 0)
		self._dragging = False

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def get(self) -> float:
		return self._value

	def set(self, value: float):
		self._value = self._clamp(float(value))
		var = self._opts.get('variable')
		if var is not None:
			var.set(self._value)
		self._markDirty()

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _clamp(self, v: float) -> float:
		lo  = float(self._opts.get('from_') or 0)
		hi  = float(self._opts.get('to')    or 100)
		res = float(self._opts.get('resolution') or 1)
		if res > 0:
			v = round(v / res) * res
		return max(lo, min(hi, v))

	def _frac(self) -> float:
		lo = float(self._opts.get('from_') or 0)
		hi = float(self._opts.get('to')    or 100)
		if hi == lo:
			return 0.0
		return (self._value - lo) / (hi - lo)

	def _fracToValue(self, frac: float) -> float:
		lo = float(self._opts.get('from_') or 0)
		hi = float(self._opts.get('to')    or 100)
		return self._clamp(lo + frac * (hi - lo))

	def _step(self, delta: int):
		res = float(self._opts.get('resolution') or 1)
		self.set(self._value + delta * res)
		cmd = self._opts.get('command')
		if callable(cmd):
			cmd(self._value)

	def _formatValue(self) -> str:
		digits = int(self._opts.get('digits') or 0)
		return f'{self._value:.{digits}f}' if digits else f'{self._value:g}'

	def _trackRect(self):
		"""Return (tx, ty, track_length) of the slider track."""
		orient  = self._opts.get('orient', 'horizontal')
		label   = self._opts.get('label') or ''
		showval = self._opts.get('showvalue', 1)
		if orient == 'horizontal':
			valW = max(6, len(self._formatValue()) + 2) if showval else 0
			tx   = self._x
			ty   = self._y + bool(label)
			tw   = max(2, self._w - valW - (1 if valW else 0))
			return (tx, ty, tw)
		else:
			tx = self._x
			ty = self._y + bool(label)
			th = max(2, self._h - bool(label))
			return (tx, ty, th)

	def _preferredSize(self):
		orient  = self._opts.get('orient', 'horizontal')
		length  = max(4, int(self._opts.get('length') or 20))
		label   = bool(self._opts.get('label'))
		showval = bool(self._opts.get('showvalue', 1))
		if orient == 'horizontal':
			return (length, 1 + label)
		else:
			valW = max(6, len(self._formatValue()) + 2) if showval else 0
			return (1 + valW + (1 if valW else 0), length + label)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return
		orient  = self._opts.get('orient', 'horizontal')
		label   = self._opts.get('label') or ''
		showval = self._opts.get('showvalue', 1)
		attr    = self._getAttr()
		fattr   = attr | curses.A_REVERSE if self._focused else attr | curses.A_BOLD

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		if label:
			_addStr(scr, self._y, self._x, _pad(str(label), self._w), attr)

		tx, ty, tlen = self._trackRect()
		frac         = self._frac()
		thumbI       = min(tlen - 1, int(frac * (tlen - 1)))

		if orient == 'horizontal':
			row = ''.join('●' if i == thumbI else '─' for i in range(tlen))
			_addStr(scr, ty, tx, row, attr)
			if showval:
				valStr = self._formatValue()
				_addStr(scr, ty, tx + tlen + 1, valStr, fattr)
		else:
			for i in range(tlen):
				ch    = '●' if i == thumbI else '│'
				cattr = fattr if i == thumbI else attr
				_addStr(scr, ty + i, tx, ch, cattr)
			if showval:
				valStr = self._formatValue()
				_addStr(scr, ty + thumbI, tx + 2,
					_clip(valStr, max(1, self._w - 2)), fattr)

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _isFocusable(self):
		return self._opts.get('state', 'normal') == 'normal'

	def _handleKey(self, key):
		orient = self._opts.get('orient', 'horizontal')
		lo     = float(self._opts.get('from_') or 0)
		hi     = float(self._opts.get('to')    or 100)
		if orient == 'horizontal':
			if key == KEY_LEFT:   self._step(-1); return True
			if key == KEY_RIGHT:  self._step(+1); return True
		else:
			if key == KEY_UP:     self._step(-1); return True
			if key == KEY_DOWN:   self._step(+1); return True
		if key == KEY_HOME:
			self.set(lo)
			cmd = self._opts.get('command')
			if callable(cmd): cmd(self._value)
			return True
		if key == KEY_END:
			self.set(hi)
			cmd = self._opts.get('command')
			if callable(cmd): cmd(self._value)
			return True
		return super()._handleKey(key)

	def _handleMouse(self, mx, my, bstate):
		press   = bool(bstate & curses.BUTTON1_PRESSED)
		clicked = bool(bstate & curses.BUTTON1_CLICKED)
		release = bool(bstate & curses.BUTTON1_RELEASED)

		if release:
			self._dragging = False
		if press and not self._dragging:
			self._dragging = True

		if self._dragging or press or clicked:
			tx, ty, tlen = self._trackRect()
			if tlen <= 1:
				return True
			orient = self._opts.get('orient', 'horizontal')
			frac   = ((mx - tx) / (tlen - 1) if orient == 'horizontal'
				else (my - ty) / (tlen - 1))
			frac   = max(0.0, min(1.0, frac))
			self.set(self._fracToValue(frac))
			cmd = self._opts.get('command')
			if callable(cmd):
				cmd(self._value)
			self._markDirty()
		return True
