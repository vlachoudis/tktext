import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad
from ._events import KEY_ENTER, KEY_CR, KEY_SPACE, KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN


# Default variable when none provided
class _StrVar:
	def __init__(self):
		self._val = ''
	def get(self):
		return self._val
	def set(self, v):
		self._val = str(v)


class Radiobutton(Widget):
	"""Radio button widget.  Mirrors tkinter.Radiobutton."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'text':			'',
			'textvariable':		None,
			'variable':		None,
			'value':		'',
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
			self._opts['variable'] = _StrVar()

	# ------------------------------------------------------------------
	# Variable access helpers
	# ------------------------------------------------------------------

	def _getVar(self):
		v = self._opts.get('variable')
		if v is None:
			v = _StrVar()
			self._opts['variable'] = v
		return v

	def _isSelected(self) -> bool:
		v     = self._getVar()
		value = self._opts.get('value', '')
		return v.get() == value

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def invoke(self):
		"""Select this radio button."""
		if self._opts.get('state') == 'disabled':
			return
		v     = self._getVar()
		value = self._opts.get('value', '')
		v.set(value)
		cmd = self._opts.get('command')
		if callable(cmd):
			cmd()
		self._markDirty()

	def select(self):
		"""Set variable to this button's value."""
		self._getVar().set(self._opts.get('value', ''))
		self._markDirty()

	def deselect(self):
		"""No-op — radio buttons cannot deselect themselves."""
		pass

	def toggle(self):
		"""Invoke (radio buttons don't toggle off)."""
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
		# indicator (*) is 4 chars, plus space, plus text
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

		indicator = '(*)' if self._isSelected() else '( )'
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
		if key in (KEY_LEFT, KEY_UP, KEY_RIGHT, KEY_DOWN):
			return self._moveFocus(backward=(key in (KEY_LEFT, KEY_UP)))
		return super()._handleKey(key)

	def _moveFocus(self, backward: bool) -> bool:
		app = self._getApp()
		if app is None:
			return False
		myVar = self._opts.get('variable')
		siblings = [w for w in app._getAllFocusable()
			if isinstance(w, Radiobutton) and w._opts.get('variable') is myVar]
		if len(siblings) < 2:
			return False
		try:
			idx = siblings.index(self)
		except ValueError:
			return False
		nxt = siblings[(idx - 1) % len(siblings) if backward else (idx + 1) % len(siblings)]
		app._setFocus(nxt)
		nxt.invoke()
		return True

	def _handleMouse(self, mx: int, my: int, bstate: int) -> bool:
		if bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
			self.invoke()
			return True
		return False
