from ._core import Widget, _fillRect, _drawBorder, _drawText, _int
from ._events import KEY_ENTER, KEY_SPACE, B1_RELEASE, B1_CLICK, MOTION


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
			'padx':			1,
		})
		kwargs.setdefault('relief', 'raised')
		kwargs.setdefault('borderwidth', 1)
		if kwargs:
			self.configure(**kwargs)

	# ------------------------------------------------------------------

	def invoke(self):
		"""Call the button's command callback and return its result."""
		if self._opts.get('state') == 'disabled':
			return None
		cmd = self._opts.get('command')
		if callable(cmd):
			return cmd()
		return None

	def flash(self):
		"""Visual flash (no-op in terminal version)."""
		pass

	# ------------------------------------------------------------------

	def _getText(self):
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return str(tv.get())
		text = self._opts.get('text')
		return '' if text is None else str(text)

	def _preferredSize(self):
		bd    = self._cfgBorder()
		ow    = _int(self._opts.get('width'))
		oh    = _int(self._opts.get('height'))
		padx  = max(0, _int(self._opts.get('padx')))
		pady  = max(0, _int(self._opts.get('pady')))
		lines = self._getText().split('\n')
		textW = max(len(l) for l in lines)
		textH = len(lines)
		w = (ow if ow > 0 else textW) + 2*bd + 2*padx
		h = (oh if oh > 0 else textH) + 2*bd + 2*pady
		return (max(w, 1), max(h, 1))

	def render(self, scr):
		if not self._isMapped():
			return

		state   = self._opts.get('state', 'normal')
		bd      = self._border()
		padx    = max(0, _int(self._opts.get('padx')))
		pady    = max(0, _int(self._opts.get('pady')))

		# Choose colours
		if state == 'disabled':
			attr = self._getAttr(fg=self._opts.get('disabledforeground') or 'gray')
		elif self._focused:
			afg  = self._opts.get('activeforeground') or ''
			abg  = self._opts.get('activebackground') or ''
			attr = self._getAttr(fg=afg, bg=abg, reverse=not (afg or abg))
		else:
			attr = self._getAttr()

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		relief = self._opts.get('relief', 'raised')
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		# Shrink padding first when the button is squeezed
		innerW = self._w - 2*bd
		innerH = self._h - 2*bd
		padx   = min(padx, max(0, (innerW - 1) // 2))
		pady   = min(pady, max(0, (innerH - 1) // 2))
		_drawText(scr,
			self._x + bd + padx, self._y + bd + pady,
			innerW - 2*padx, innerH - 2*pady,
			self._getText(),
			self._opts.get('anchor') or 'center',
			self._opts.get('justify') or 'center',
			attr)

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _handleKey(self, key):
		if self._opts.get('state') == 'disabled':
			return False
		if key in (KEY_ENTER, KEY_SPACE):
			self.invoke()
			self._markDirty()
			return True
		return False

	def _handleMouse(self, mx, my, bstate):
		if self._opts.get('state') == 'disabled':
			return False
		# Like tkinter: the command fires when the button is released
		# over the widget that received the press.
		if bstate & (B1_RELEASE | B1_CLICK) and not (bstate & MOTION):
			if self._hitTest(mx, my):
				self.invoke()
				self._markDirty()
			return True
		return False
