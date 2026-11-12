from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad, _sameValue, _int
from ._events import KEY_ENTER, KEY_SPACE, B1_RELEASE, B1_CLICK, MOTION


# Default variable when none provided
class _BoolVar:
	def __init__(self):
		self._val = 0
	def get(self):
		return self._val
	def set(self, v):
		self._val = v


class Checkbutton(Widget):
	"""Toggle button widget.  Mirrors tkinter.Checkbutton."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'text':			'',
			'textvariable':		None,
			'variable':		None,
			'onvalue':		1,
			'offvalue':		0,
			'command':		None,
			'anchor':		'w',
			'justify':		'left',
			'indicatoron':		True,
			'activeforeground':	'',
			'activebackground':	'',
			'disabledforeground':	'gray',
			'selectcolor':		'',
		})
		kwargs.setdefault('relief', 'flat')
		kwargs.setdefault('borderwidth', 0)
		if kwargs:
			self.configure(**kwargs)

		# Ensure a variable exists
		if self._opts.get('variable') is None:
			self._opts['variable'] = self._defaultVar()

	# ------------------------------------------------------------------
	# Variable access helpers
	# ------------------------------------------------------------------

	def _defaultVar(self):
		return _BoolVar()

	def _getVar(self):
		v = self._opts.get('variable')
		if v is None:
			v = self._defaultVar()
			self._opts['variable'] = v
		return v

	def _isChecked(self) -> bool:
		try:
			cur = self._getVar().get()
		except (TypeError, ValueError):
			return False
		return _sameValue(cur, self._opts.get('onvalue', 1))

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def invoke(self):
		"""Toggle the checkbutton and call its command."""
		if self._opts.get('state') == 'disabled':
			return None
		if self._isChecked():
			self._getVar().set(self._opts.get('offvalue', 0))
		else:
			self._getVar().set(self._opts.get('onvalue', 1))
		self._markDirty()
		cmd = self._opts.get('command')
		if callable(cmd):
			return cmd()
		return None

	def select(self):
		"""Set checkbutton to on state."""
		self._getVar().set(self._opts.get('onvalue', 1))
		self._markDirty()

	def deselect(self):
		"""Set checkbutton to off state."""
		self._getVar().set(self._opts.get('offvalue', 0))
		self._markDirty()

	def toggle(self):
		"""Toggle the checkbutton without calling the command."""
		if self._isChecked():
			self.deselect()
		else:
			self.select()

	# ------------------------------------------------------------------

	def _getText(self) -> str:
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return str(tv.get())
		return str(self._opts.get('text') or '')

	def _indicator(self) -> str:
		return '[X] ' if self._isChecked() else '[ ] '

	def _preferredSize(self):
		bd    = self._cfgBorder()
		padx  = _int(self._opts.get('padx'))
		lines = self._getText().split('\n')
		textW = max(len(l) for l in lines)
		w     = max(_int(self._opts.get('width')), 4 + textW) + 2*bd + 2*padx
		h     = len(lines) + 2*bd
		return (max(w, 3), max(h, 1))

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return

		state   = self._opts.get('state', 'normal')
		bd      = self._border()
		padx    = _int(self._opts.get('padx'))
		relief  = self._opts.get('relief', 'flat')

		if state == 'disabled':
			attr = self._getAttr(fg=self._opts.get('disabledforeground') or 'gray')
		elif self._focused:
			afg = self._opts.get('activeforeground') or ''
			abg = self._opts.get('activebackground') or ''
			attr = self._getAttr(fg=afg, bg=abg, reverse=not (afg or abg))
		else:
			attr = self._getAttr()

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		cw    = max(0, self._w - 2*bd - 2*padx)
		lines = self._getText().split('\n')
		for i, line in enumerate(lines):
			if i >= self._h - 2*bd:
				break
			pfx = self._indicator() if i == 0 else '    '
			_addStr(scr, self._y + bd + i, self._x + bd + padx,
				_pad(pfx + line, cw, 'left'), attr)

	# ------------------------------------------------------------------
	# Focus / input
	# ------------------------------------------------------------------

	def _handleKey(self, key: int) -> bool:
		if self._opts.get('state') == 'disabled':
			return False
		if key in (KEY_ENTER, KEY_SPACE):
			self.invoke()
			return True
		return False

	def _handleMouse(self, mx: int, my: int, bstate: int) -> bool:
		if self._opts.get('state') == 'disabled':
			return False
		if bstate & (B1_RELEASE | B1_CLICK) and not (bstate & MOTION):
			if self._hitTest(mx, my):
				self.invoke()
			return True
		return False
