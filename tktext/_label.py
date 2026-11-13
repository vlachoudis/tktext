#
# -*- coding: utf-8 -*-
#
# Copyright European Organization for Nuclear Research (CERN)
# All rights reserved
#
# Please look at the supplied documentation for the user's
# license
#
# Author: Vasilis.Vlachoudis@cern.ch
# Date:   12-Nov-2026

from ._core import Widget, _fillRect, _drawBorder, _drawText, _int, _initArgs, _cellsX


class Label(Widget):
	"""Read-only text display widget.  Mirrors tkinter.Label."""

	_clickFocus = False	# tkinter: clicking does not take the focus

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
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
			Label.configure(self, **kwargs)

	# ------------------------------------------------------------------

	def _getText(self):
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return self._withImage(str(tv.get()))
		text = self._opts.get('text')
		return self._withImage('' if text is None else str(text))

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
		lines = self._wrappedText().expandtabs(8).split('\n')
		textW = max(len(l) for l in lines)
		textH = len(lines)
		w = (ow if ow > 0 else textW) + 2*bd + 2*padx
		h = (oh if oh > 0 else textH) + 2*bd + 2*pady
		return (max(w, 1), max(h, 1))

	def _contentAttr(self):
		if self._opts.get('state') == 'disabled':
			return self._disabledAttr()
		return self._getAttr()

	def render(self, scr):
		if not self._isMapped():
			return
		bd    = self._border()
		padx  = _int(self._opts.get('padx'))
		pady  = _int(self._opts.get('pady'))
		attr  = self._contentAttr()

		_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)

		relief = self._opts.get('relief', 'flat')
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._height, self._width, relief, attr)

		_drawText(scr,
			self._x + bd + padx, self._y + bd + pady,
			self._width - 2*bd - 2*padx, self._height - 2*bd - 2*pady,
			self._wrappedText(),
			self._opts.get('anchor') or 'center',
			self._opts.get('justify') or 'center',
			attr)


class Message(Label):
	"""Multi-line text wrapped to a width (mirrors tkinter.Message).
	The wrap width is the 'width' option, or derived from 'aspect'
	(100 * width / height, default 150) like Tk."""

	_PIXEL_OPTIONS = {**Label._PIXEL_OPTIONS, 'width': _cellsX}

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		kwargs.setdefault('anchor',  'nw')
		kwargs.setdefault('justify', 'left')
		kwargs.setdefault('aspect',  150)
		super().__init__(parent, **kwargs)

	def _wrappedText(self):
		import math
		import textwrap
		text  = self._getText()
		width = _int(self._opts.get('width'))
		if width <= 0:
			aspect = max(1, _int(self._opts.get('aspect'), 150))
			# a cell is about twice as high as wide
			width  = int(math.sqrt(max(1, len(text)) * aspect / 50.0))
			width  = max(10, width)
		lines = []
		for para in text.split('\n'):
			lines.extend(textwrap.wrap(para, width) or [''])
		return '\n'.join(lines)

	def _preferredSize(self):
		saved = self._opts.get('width')
		self._opts['width'] = 0
		try:
			return super()._preferredSize()
		finally:
			self._opts['width'] = saved
