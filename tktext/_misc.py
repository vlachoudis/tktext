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

"""Small extra widgets: Separator and Progressbar (ttk)."""
from ._core import Widget, _addStr, _fillRect, _int, _initArgs


class Separator(Widget):
	"""Horizontal or vertical line.  Mirrors ttk.Separator."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'orient':	'horizontal',
			'takefocus':	False,
		})
		if kwargs:
			Separator.configure(self, **kwargs)

	def _horizontal(self) -> bool:
		return str(self._opts.get('orient', 'horizontal')).startswith('h')

	def _preferredSize(self):
		return (1, 1)

	def render(self, scr):
		if not self._isMapped():
			return
		attr = self._getAttr()
		if self._horizontal():
			for i in range(self._height):
				_addStr(scr, self._y + i, self._x, '─' * self._width, attr)
		else:
			for i in range(self._height):
				_addStr(scr, self._y + i, self._x, '│' * self._width, attr)


class Progressbar(Widget):
	"""Progress indicator.  Mirrors ttk.Progressbar
	(mode 'determinate' or 'indeterminate')."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'orient':	'horizontal',
			'length':	20,
			'mode':		'determinate',
			'maximum':	100.0,
			'value':	0.0,
			'variable':	None,
			'phase':	0,
			'takefocus':	False,
		})
		self._timer = None
		if kwargs:
			Progressbar.configure(self, **kwargs)

	def _horizontal(self) -> bool:
		return str(self._opts.get('orient', 'horizontal')).startswith('h')

	def _value(self) -> float:
		var = self._opts.get('variable')
		if var is not None:
			try:
				return float(var.get())
			except (TypeError, ValueError):
				return 0.0
		try:
			return float(self._opts.get('value') or 0)
		except (TypeError, ValueError):
			return 0.0

	def __getitem__(self, key):
		if key == 'value':
			return self._value()
		return super().__getitem__(key)

	def step(self, amount=1.0):
		maximum = float(self._opts.get('maximum') or 100)
		v = self._value() + float(amount)
		if v >= maximum:
			v -= maximum
		var = self._opts.get('variable')
		if var is not None:
			var.set(v)
		self._opts['value'] = v
		self._opts['phase'] = _int(self._opts.get('phase')) + 1
		self._markDirty()

	def start(self, interval=50):
		self.stop()

		def tick():
			self.step()
			self._timer = self.after(interval, tick)
		self._timer = self.after(interval, tick)

	def stop(self):
		if self._timer is not None:
			self.after_cancel(self._timer)
			self._timer = None

	def _preferredSize(self):
		length = max(3, _int(self._opts.get('length'), 20))
		return (length, 1) if self._horizontal() else (1, length)

	def render(self, scr):
		if not self._isMapped():
			return
		attr    = self._getAttr()
		n       = self._width if self._horizontal() else self._height
		maximum = float(self._opts.get('maximum') or 100) or 100.0
		if self._opts.get('mode') == 'indeterminate':
			block = max(1, n // 5)
			pos   = _int(self._opts.get('phase')) % max(1, 2 * (n - block))
			if pos > n - block:
				pos = 2 * (n - block) - pos
			cells = ['█' if pos <= i < pos + block else '░' for i in range(n)]
		else:
			filled = int(round(max(0.0, min(1.0, self._value() / maximum)) * n))
			cells  = ['█' if i < filled else '░' for i in range(n)]
		if self._horizontal():
			_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)
			_addStr(scr, self._y + (self._height - 1) // 2, self._x, ''.join(cells), attr)
		else:
			for i, ch in enumerate(reversed(cells)):
				_addStr(scr, self._y + i, self._x, ch * self._width, attr)
