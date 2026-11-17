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

from ._entry import Entry
from ._core import _addStr, _int, _initArgs
from ._events import (KEY_UP, KEY_DOWN, KEY_PPAGE, KEY_NPAGE,
	B1_PRESS, B1_CLICK, MOTION, isWheel)


def _float(v, default):
	try:
		return float(v)
	except (TypeError, ValueError):
		return default


class Spinbox(Entry):
	"""Single-line entry with ▲▼ increment/decrement buttons.
	Mirrors tkinter.Spinbox / tkinter.ttk.Spinbox.

	Editing, selection and the textvariable are inherited from Entry."""

	_BUTTONS = ' ▲▼'

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'from_':		0.0,
			'to':			0.0,
			'increment':		1.0,
			'values':		(),
			'command':		None,
			'wrap':			False,
			'format':		'',
			'validate':		'none',
			'validatecommand':	None,
			'buttonbackground':	'',
		})
		kwargs.setdefault('width', 10)
		if kwargs:
			Spinbox.configure(self, **kwargs)

		tv = self._opts.get('textvariable')
		if tv is None or str(tv.get()) == '':
			vals = self._values()
			if vals:
				init = vals[0]
			else:
				init = self._format(_float(self._opts.get('from_'), 0.0))
			self._setBuf(init)
		self._cur = len(self._getBuf())

	# ------------------------------------------------------------------
	# Public API (Entry provides get/insert/delete/icursor/selection…)
	# ------------------------------------------------------------------

	def set(self, value):
		"""Set the text (ttk.Spinbox API)."""
		self._setBuf(str(value))
		self._cur = len(self._getBuf())
		self._scrollToCursor()

	def invoke(self, element: str = 'buttonup'):
		"""Programmatically press the up or down button."""
		self._increment(+1 if element == 'buttonup' else -1)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _values(self):
		vals = self._opts.get('values') or ()
		if isinstance(vals, str):
			vals = vals.split()
		return [str(v) for v in vals]

	def _format(self, v):
		fmt = self._opts.get('format') or ''
		if fmt:
			try:
				return fmt % v
			except (TypeError, ValueError):
				pass
		inc = _float(self._opts.get('increment'), 1.0)
		if float(v).is_integer() and float(inc).is_integer():
			return str(int(v))
		return f'{v:g}'

	def _increment(self, direction: int):
		"""Up/Down, the arrows and invoke() generate <<Increment>> or
		<<Decrement>>; like ttk its class behaviour spins the value"""
		self.event_generate('<<Increment>>' if direction > 0 else '<<Decrement>>')

	def _handleVirtual(self, sequence):
		if sequence in ('<<Increment>>', '<<Decrement>>'):
			if self._opts.get('state') == 'disabled':
				return False
			self._spin(+1 if sequence == '<<Increment>>' else -1)
			return True
		return super()._handleVirtual(sequence)

	def _spin(self, direction: int):
		vals = self._values()
		if vals:
			n = len(vals)
			cur = self.get()
			idx = vals.index(cur) if cur in vals else (-1 if direction > 0 else n)
			nxt = idx + direction
			if self._opts.get('wrap'):
				nxt %= n
			else:
				nxt = max(0, min(n - 1, nxt))
			self.set(vals[nxt])
		else:
			lo  = _float(self._opts.get('from_'), 0.0)
			hi  = _float(self._opts.get('to'), 0.0)
			inc = _float(self._opts.get('increment'), 1.0) or 1.0
			v   = _float(self.get(), lo)
			v  += direction * inc
			if hi > lo:
				if self._opts.get('wrap'):
					if v > hi:
						v = lo
					elif v < lo:
						v = hi
				else:
					v = max(lo, min(hi, v))
			self.set(self._format(v))
		cmd = self._opts.get('command')
		if callable(cmd):
			cmd()

	def _visW(self) -> int:
		return max(1, self._width - 2*self._border() - len(self._BUTTONS))

	def _preferredSize(self):
		bd = self._cfgBorder()
		ow = _int(self._opts.get('width'), 10) or 10
		return (ow + 2*bd + len(self._BUTTONS), 1 + 2*bd)

	def _buttonX(self) -> int:
		return self._x + self._width - self._border() - len(self._BUTTONS)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return
		super().render(scr)
		bd    = self._border()
		attr  = self._getAttr()
		by    = self._y + bd + (self._height - 2*bd - 1) // 2
		battr = self._focusAttr() if self._focused else attr
		_addStr(scr, by, self._buttonX(), self._BUTTONS, battr)

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _handleKey(self, key):
		if self._opts.get('state') == 'disabled':
			return False
		if key in (KEY_UP, KEY_PPAGE):
			self._increment(+1)
			return True
		if key in (KEY_DOWN, KEY_NPAGE):
			self._increment(-1)
			return True
		return super()._handleKey(key)

	def _handleMouse(self, mx, my, bstate):
		if self._opts.get('state') == 'disabled':
			return False
		wheel = isWheel(bstate)
		if wheel:
			self._increment(-wheel)
			return True
		btnX = self._buttonX()
		if mx >= btnX and not self._mouseDown:
			if bstate & (B1_PRESS | B1_CLICK) and not (bstate & MOTION):
				col = mx - btnX
				if col >= 1:
					self._increment(+1 if col == 1 else -1)
			return True
		return super()._handleMouse(mx, my, bstate)
