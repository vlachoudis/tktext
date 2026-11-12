from ._core import Widget, _fillRect, _drawBorder, _drawText, _int


class Label(Widget):
	"""Read-only text display widget.  Mirrors tkinter.Label."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'text':		'',
			'textvariable':	None,
			'image':	None,
			'anchor':	'center',
			'justify':	'center',
			'wraplength':	0,
			'font':		None,
			'compound':	'none',
			'underline':	-1,
			'takefocus':	False,
		})
		if kwargs:
			self.configure(**kwargs)

	# ------------------------------------------------------------------

	def _getText(self):
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return str(tv.get())
		text = self._opts.get('text')
		return '' if text is None else str(text)

	def _wrappedText(self):
		text = self._getText()
		wl   = _int(self._opts.get('wraplength'))
		if wl <= 0:
			return text
		import textwrap
		lines = []
		for para in text.split('\n'):
			lines.extend(textwrap.wrap(para, wl) or [''])
		return '\n'.join(lines)

	def _preferredSize(self):
		bd    = self._cfgBorder()
		ow    = _int(self._opts.get('width'))
		oh    = _int(self._opts.get('height'))
		padx  = _int(self._opts.get('padx'))
		pady  = _int(self._opts.get('pady'))
		lines = self._wrappedText().split('\n')
		textW = max(len(l) for l in lines)
		textH = len(lines)
		w = (ow if ow > 0 else textW) + 2*bd + 2*padx
		h = (oh if oh > 0 else textH) + 2*bd + 2*pady
		return (max(w, 1), max(h, 1))

	def _contentAttr(self):
		if self._opts.get('state') == 'disabled':
			return self._getAttr(fg=self._opts.get('disabledforeground') or 'gray')
		return self._getAttr()

	def render(self, scr):
		if not self._isMapped():
			return
		bd    = self._border()
		padx  = _int(self._opts.get('padx'))
		pady  = _int(self._opts.get('pady'))
		attr  = self._contentAttr()

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		relief = self._opts.get('relief', 'flat')
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		_drawText(scr,
			self._x + bd + padx, self._y + bd + pady,
			self._w - 2*bd - 2*padx, self._h - 2*bd - 2*pady,
			self._wrappedText(),
			self._opts.get('anchor') or 'center',
			self._opts.get('justify') or 'center',
			attr)
