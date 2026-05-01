from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad
from ._events import KEY_ENTER, KEY_CR, KEY_SPACE


class Button(Widget):
	"""Clickable button widget.  Mirrors tkinter.Button."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'text':			'',
			'textvariable':		None,
			'command':		None,
			'anchor':		'center',
			'justify':		'center',
			'activebackground':	'',
			'activeforeground':	'',
			'disabledforeground':	'gray',
			'overrelief':		'',
			'underline':		-1,
			'default':		'normal',
			'compound':		'none',
			'image':		None,
		})
		kwargs.setdefault('relief', 'raised')
		kwargs.setdefault('borderwidth', 1)
		if kwargs:
			self.configure(**kwargs)

	# ------------------------------------------------------------------

	def invoke(self):
		"""Call the button's command callback."""
		if self._opts.get('state') == 'disabled':
			return
		cmd = self._opts.get('command')
		if callable(cmd):
			cmd()

	def flash(self):
		"""Visual flash (no-op in terminal version)."""
		pass

	# ------------------------------------------------------------------

	def _getText(self):
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return str(tv.get())
		return str(self._opts.get('text') or '')

	def _preferredSize(self):
		bd   = int(self._opts.get('borderwidth') or 0)
		ow   = int(self._opts.get('width') or 0)
		oh   = int(self._opts.get('height') or 0)
		padx = int(self._opts.get('padx') or 1)
		pady = int(self._opts.get('pady') or 0)
		text = self._getText()
		lines = text.split('\n') if text else ['']
		textW = max(len(l) for l in lines)
		textH = len(lines)
		w = max(ow, textW) + 2*bd + 2*padx
		h = max(oh, textH) + 2*bd + 2*pady
		return (max(w, 3), max(h, 1))

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return

		state   = self._opts.get('state', 'normal')
		focused = self._focused
		bd      = int(self._opts.get('borderwidth') or 0)
		padx    = int(self._opts.get('padx') or 1)
		pady    = int(self._opts.get('pady') or 0)

		# Choose colours
		if state == 'disabled':
			attr = self._getAttr(fg='gray')
		elif focused:
			afg = self._opts.get('activeforeground') or ''
			abg = self._opts.get('activebackground') or ''
			attr = self._getAttr(fg=afg, bg=abg, reverse=not (afg or abg))
		else:
			attr = self._getAttr()

		# Background
		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		# Border
		relief = self._opts.get('relief', 'raised')
		if bd > 0:
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		# Content area
		cx = self._x + bd + padx
		cy = self._y + bd + pady
		cw = max(1, self._w - 2*bd - 2*padx)
		ch = max(1, self._h - 2*bd - 2*pady)

		text   = self._getText()
		lines  = text.split('\n')
		anchor = self._opts.get('anchor', 'center') or 'center'

		startRow = max(0, (ch - len(lines)) // 2)

		for i, line in enumerate(lines):
			row = cy + startRow + i
			if row < self._y or row >= self._y + self._h:
				continue
			_addStr(scr, row, cx, _pad(line, cw, 'center'), attr)

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _isFocusable(self):
		return self._opts.get('state', 'normal') == 'normal'

	def _handleKey(self, key):
		if key in (KEY_ENTER, KEY_CR, KEY_SPACE):
			self.invoke()
			self._markDirty()
			return True
		return super()._handleKey(key)

	def _handleMouse(self, mx, my, bstate):
		import curses
		if bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
			self.invoke()
			self._markDirty()
			return True
		return False
