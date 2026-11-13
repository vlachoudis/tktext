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

import curses
from ._core import Widget, _addStr, _fillRect, _pad, _clip, _int, _initArgs
from ._events import (KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_HOME, KEY_END,
	KEY_PPAGE, KEY_NPAGE, B1_PRESS, B1_RELEASE, B1_CLICK, MOTION, isWheel)


def _float(v, default):
	try:
		return float(v)
	except (TypeError, ValueError):
		return default


class Scale(Widget):
	"""Horizontal or vertical slider widget.  Mirrors tkinter.Scale."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'from_':        0.0,
			'to':           100.0,
			'orient':       'vertical',
			'variable':     None,
			'command':      None,
			'resolution':   1.0,
			'length':       20,
			'showvalue':    1,
			'label':        '',
			'tickinterval': 0,
			'digits':       0,
			'troughcolor':  '',
			'sliderlength': 1,
			'bigincrement': 0,
		})
		kwargs.setdefault('relief',      'flat')
		kwargs.setdefault('borderwidth', 0)
		self._value    = 0.0
		self._dragging = False
		if kwargs:
			Scale.configure(self, **kwargs)

		var = self._opts.get('variable')
		if var is not None:
			self._value = self._clamp(_float(var.get(), self._lo()))
		else:
			self._value = self._clamp(self._lo())

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def get(self) -> float:
		self._syncFromVar()
		res = self._res()
		if res >= 1 and float(res).is_integer() and float(self._value).is_integer():
			return int(self._value)
		return self._value

	def set(self, value):
		new = self._clamp(_float(value, self._value))
		var = self._opts.get('variable')
		if var is not None:
			try:
				var.set(new)
			except (TypeError, ValueError):
				var.set(int(new))
		changed     = new != self._value
		self._value = new
		self._markDirty()
		return changed

	def coords(self, value=None):
		tx, ty, tlen = self._trackRect()
		frac = self._frac(self._value if value is None else _float(value, 0))
		pos  = int(round(frac * (tlen - 1)))
		if self._horizontal():
			return (tx + pos - self._x, ty - self._y)
		return (tx - self._x, ty + pos - self._y)

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _lo(self) -> float:
		return _float(self._opts.get('from_'), 0.0)

	def _hi(self) -> float:
		return _float(self._opts.get('to'), 100.0)

	def _res(self) -> float:
		return _float(self._opts.get('resolution'), 1.0)

	def _horizontal(self) -> bool:
		return str(self._opts.get('orient', 'vertical')).startswith('h')

	def _syncFromVar(self):
		var = self._opts.get('variable')
		if var is not None:
			try:
				v = float(var.get())
			except (TypeError, ValueError):
				return
			self._value = self._clamp(v)

	def _clamp(self, v: float) -> float:
		lo, hi = sorted((self._lo(), self._hi()))
		res = self._res()
		if res > 0:
			v = round((v - self._lo()) / res) * res + self._lo()
			v = round(v, 10)
		return max(lo, min(hi, v))

	def _frac(self, v=None) -> float:
		lo, hi = self._lo(), self._hi()
		if hi == lo:
			return 0.0
		v = self._value if v is None else v
		return max(0.0, min(1.0, (v - lo) / (hi - lo)))

	def _fracToValue(self, frac: float) -> float:
		lo, hi = self._lo(), self._hi()
		return self._clamp(lo + frac * (hi - lo))

	def _callCommand(self):
		cmd = self._opts.get('command')
		if callable(cmd):
			cmd(self._formatValue())

	def _setFromUser(self, value):
		if self.set(value):
			self._callCommand()

	def _step(self, delta):
		res = self._res() or 1
		direction = 1 if self._hi() >= self._lo() else -1
		self._setFromUser(self._value + delta * res * direction)

	def _formatValue(self) -> str:
		digits = _int(self._opts.get('digits'))
		if digits:
			return f'{self._value:.{digits}f}'
		res = self._res()
		if res >= 1 and float(res).is_integer():
			return str(int(round(self._value)))
		decimals = max(0, len(f'{res:g}'.split('.')[-1])) if '.' in f'{res:g}' else 0
		return f'{self._value:.{decimals}f}'

	def _valueWidth(self) -> int:
		return max(len(self._formatValue()),
			len(f'{self._lo():g}'), len(f'{self._hi():g}'))

	def _trackRect(self):
		"""Return (tx, ty, track_length) of the slider track."""
		label   = 1 if self._opts.get('label') else 0
		showval = bool(_int(self._opts.get('showvalue'), 1))
		if self._horizontal():
			valW = self._valueWidth() + 1 if showval else 0
			return (self._x, self._y + label, max(2, self._width - valW))
		valW = self._valueWidth() + 1 if showval else 0
		return (self._x + valW, self._y + label, max(2, self._height - label))

	def _preferredSize(self):
		length  = max(4, _int(self._opts.get('length'), 20))
		label   = 1 if self._opts.get('label') else 0
		showval = bool(_int(self._opts.get('showvalue'), 1))
		valW    = self._valueWidth() + 1 if showval else 0
		if self._horizontal():
			w = max(length + valW, len(str(self._opts.get('label') or '')))
			return (w, 1 + label)
		return (max(1 + valW, len(str(self._opts.get('label') or ''))), length + label)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return
		self._syncFromVar()
		label   = self._opts.get('label') or ''
		showval = bool(_int(self._opts.get('showvalue'), 1))
		disabled = self._opts.get('state') == 'disabled'
		attr    = self._disabledAttr() if disabled else self._getAttr()
		fattr   = self._focusAttr() if self._focused else attr | curses.A_BOLD
		trough  = self._optColor('troughcolor')
		tattr   = self._getAttr(bg=trough) if trough else attr

		_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)

		if label:
			_addStr(scr, self._y, self._x, _pad(str(label), self._width), attr)

		tx, ty, tlen = self._trackRect()
		thumbI = min(tlen - 1, int(round(self._frac() * (tlen - 1))))
		valStr = self._formatValue()

		if self._horizontal():
			_addStr(scr, ty, tx, '─' * tlen, tattr)
			_addStr(scr, ty, tx + thumbI, '█', fattr)
			if showval:
				_addStr(scr, ty, tx + tlen + 1,
					_clip(valStr, self._x + self._width - tx - tlen - 1), attr)
		else:
			for i in range(tlen):
				_addStr(scr, ty + i, tx, '│', tattr)
			_addStr(scr, ty + thumbI, tx, '█', fattr)
			if showval:
				_addStr(scr, ty + thumbI, self._x,
					valStr.rjust(self._valueWidth()), attr)

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _handleKey(self, key):
		if self._opts.get('state') == 'disabled':
			return False
		self._syncFromVar()
		big = _float(self._opts.get('bigincrement'), 0) or \
			abs(self._hi() - self._lo()) / 10 or 1
		if self._horizontal():
			dec, inc = KEY_LEFT, KEY_RIGHT
		else:
			dec, inc = KEY_UP, KEY_DOWN
		if key == dec:
			self._step(-1)
		elif key == inc:
			self._step(+1)
		elif key == KEY_PPAGE:
			self._setFromUser(self._value - big * (1 if self._hi() >= self._lo() else -1))
		elif key == KEY_NPAGE:
			self._setFromUser(self._value + big * (1 if self._hi() >= self._lo() else -1))
		elif key == KEY_HOME:
			self._setFromUser(self._lo())
		elif key == KEY_END:
			self._setFromUser(self._hi())
		else:
			return False
		return True

	def _handleMouse(self, mx, my, bstate):
		if self._opts.get('state') == 'disabled':
			return False
		wheel = isWheel(bstate)
		if wheel:
			self._step(-wheel if self._horizontal() else wheel)
			return True
		press   = bool(bstate & B1_PRESS) and not (bstate & MOTION)
		release = bool(bstate & (B1_RELEASE | B1_CLICK))
		motion  = bool(bstate & MOTION) or bool(bstate & B1_PRESS)

		if press:
			self._dragging = True
		if not (self._dragging or bstate & B1_CLICK):
			return False
		if press or motion or release:
			tx, ty, tlen = self._trackRect()
			if tlen > 1:
				pos  = (mx - tx) if self._horizontal() else (my - ty)
				frac = max(0.0, min(1.0, pos / (tlen - 1)))
				self._setFromUser(self._fracToValue(frac))
		if release:
			self._dragging = False
		return True
