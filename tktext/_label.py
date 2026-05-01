from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad


_ANCHOR_MAP = {
	'nw': ('left',  'top'),
	'n':  ('center','top'),
	'ne': ('right', 'top'),
	'w':  ('left',  'mid'),
	'center': ('center', 'mid'),
	'e':  ('right', 'mid'),
	'sw': ('left',  'bot'),
	's':  ('center','bot'),
	'se': ('right', 'bot'),
}


class Label(Widget):
	"""Read-only text display widget.  Mirrors tkinter.Label."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'text':		'',
			'textvariable':	None,
			'image':	None,
			'anchor':	'w',
			'justify':	'left',
			'wraplength':	0,
			'font':		None,
			'compound':	'none',
		})
		if kwargs:
			self.configure(**kwargs)

	# ------------------------------------------------------------------

	def _getText(self):
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return str(tv.get())
		return str(self._opts.get('text') or '')

	def _preferredSize(self):
		bd  = int(self._opts.get('borderwidth') or 0)
		ow  = int(self._opts.get('width') or 0)
		oh  = int(self._opts.get('height') or 0)
		padx = int(self._opts.get('padx') or 0)
		pady = int(self._opts.get('pady') or 0)
		text = self._getText()
		lines = text.split('\n') if text else ['']
		textW = max(len(l) for l in lines)
		textH = len(lines)
		w = max(ow, textW) + 2*bd + 2*padx
		h = max(oh, textH) + 2*bd + 2*pady
		return (max(w, 1), max(h, 1))

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return
		bd    = int(self._opts.get('borderwidth') or 0)
		padx  = int(self._opts.get('padx') or 0)
		pady  = int(self._opts.get('pady') or 0)
		attr  = self._getAttr()
		text  = self._getText()

		# Background
		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		# Border
		relief = self._opts.get('relief', 'flat')
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		# Content area
		cx  = self._x + bd + padx
		cy  = self._y + bd + pady
		cw  = max(1, self._w - 2*bd - 2*padx)
		ch  = max(1, self._h - 2*bd - 2*pady)

		lines = text.split('\n')
		anchor = self._opts.get('anchor', 'w') or 'w'
		halign, valign = _ANCHOR_MAP.get(anchor, ('left', 'mid'))

		# Vertical offset
		if valign == 'top':
			startRow = 0
		elif valign == 'bot':
			startRow = max(0, ch - len(lines))
		else:
			startRow = max(0, (ch - len(lines)) // 2)

		justify = self._opts.get('justify', 'left') or 'left'
		jalign = justify if justify in ('left', 'right', 'center') else 'left'

		for i, line in enumerate(lines):
			row = cy + startRow + i
			if row < self._y or row >= self._y + self._h:
				continue
			_addStr(scr, row, cx, _pad(line, cw, jalign), attr)

	def _isFocusable(self):
		return False
