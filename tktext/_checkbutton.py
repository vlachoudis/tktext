import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad
from ._events import KEY_ENTER, KEY_CR, KEY_SPACE

# Default variable when none provided
class _BoolVar:
	def __init__(self):
		self._val = False
	def get(self):
		return self._val
	def set(self, v):
		self._val = bool(v)


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
		if not self._opts.get('variable'):
			self._opts['variable'] = _BoolVar()

	# ------------------------------------------------------------------
	# Variable access helpers
	# ------------------------------------------------------------------

	def _getVar(self):
		v = self._opts.get('variable')
		if v is None:
			v = _BoolVar()
			self._opts['variable'] = v
		return v

	def _isChecked(self) -> bool:
		v        = self._getVar()
		onvalue  = self._opts.get('onvalue', 1)
		return v.get() == onvalue

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def invoke(self):
		"""Toggle the checkbutton."""
		if self._opts.get('state') == 'disabled':
			return
		v        = self._getVar()
		onvalue  = self._opts.get('onvalue', 1)
		offvalue = self._opts.get('offvalue', 0)
		if v.get() == onvalue:
			v.set(offvalue)
		else:
			v.set(onvalue)
		cmd = self._opts.get('command')
		if callable(cmd):
			cmd()
		self._markDirty()

	def select(self):
		"""Set checkbutton to on state."""
		self._getVar().set(self._opts.get('onvalue', 1))
		self._markDirty()

	def deselect(self):
		"""Set checkbutton to off state."""
		self._getVar().set(self._opts.get('offvalue', 0))
		self._markDirty()

	def toggle(self):
		"""Toggle the checkbutton (same as invoke)."""
		self.invoke()

	# ------------------------------------------------------------------

	def _getText(self) -> str:
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return str(tv.get())
		return str(self._opts.get('text') or '')

	def _preferredSize(self):
		bd      = int(self._opts.get('borderwidth') or 0)
		padx    = int(self._opts.get('padx') or 0)
		text    = self._getText()
		lines   = text.split('\n') if text else ['']
		textW   = max(len(l) for l in lines)
		# indicator [X] is 4 chars, plus space, plus text
		w       = 4 + textW + 2*bd + 2*padx
		h       = len(lines) + 2*bd
		return (max(w, 5), max(h, 1))

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return

		state   = self._opts.get('state', 'normal')
		focused = self._focused
		bd      = int(self._opts.get('borderwidth') or 0)
		relief  = self._opts.get('relief', 'flat')

		if state == 'disabled':
			attr = self._getAttr(fg=self._opts.get('disabledforeground') or 'gray')
		elif focused:
			afg = self._opts.get('activeforeground') or ''
			abg = self._opts.get('activebackground') or ''
			attr = self._getAttr(fg=afg, bg=abg, reverse=not (afg or abg))
		else:
			attr = self._getAttr()

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		indicator = '[X]' if self._isChecked() else '[ ]'
		text      = self._getText()
		label     = indicator + ' ' + text

		cx  = self._x + bd
		cy  = self._y + bd
		cw  = max(1, self._w - 2*bd)

		_addStr(scr, cy, cx, _pad(label, cw, 'left'), attr)

	# ------------------------------------------------------------------
	# Focus / input
	# ------------------------------------------------------------------

	def _isFocusable(self) -> bool:
		return self._opts.get('state', 'normal') == 'normal'

	def _handleKey(self, key: int) -> bool:
		if key in (KEY_ENTER, KEY_CR, KEY_SPACE):
			self.invoke()
			return True
		return super()._handleKey(key)

	def _handleMouse(self, mx: int, my: int, bstate: int) -> bool:
		if bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
			self.invoke()
			return True
		return False
