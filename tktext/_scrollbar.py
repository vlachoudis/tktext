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

from ._core import Widget, _addStr, _initArgs
from . import _core
from ._events import B1_PRESS, B1_RELEASE, B1_CLICK, MOTION, isWheel


class Scrollbar(Widget):
	"""Scrollbar widget.  Mirrors tkinter.Scrollbar.

	Connect it like in tkinter::

		sb = Scrollbar(frame, command=lb.yview)
		lb.configure(yscrollcommand=sb.set)

	Clicking the arrows scrolls by one unit, clicking the trough scrolls
	by a page and dragging the thumb calls command('moveto', fraction).
	"""

	_clickFocus = False	# tkinter: clicking does not take the focus

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'orient':	'vertical',
			'command':	None,
			'takefocus':	False,
		})
		kwargs.setdefault('relief',      'flat')
		kwargs.setdefault('borderwidth', 0)
		if kwargs:
			Scrollbar.configure(self, **kwargs)
		self._first	= 0.0
		self._last	= 1.0
		self._drag	= None	# (anchorPos, anchorFirst) while dragging

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def set(self, first, last):
		"""Called by the linked widget to report its scroll position."""
		first = max(0.0, min(1.0, float(first)))
		last  = max(first, min(1.0, float(last)))
		if (first, last) != (self._first, self._last):
			self._first = first
			self._last  = last
			self._markDirty()

	def get(self) -> tuple:
		return (self._first, self._last)

	# ------------------------------------------------------------------

	def _vertical(self) -> bool:
		return str(self._opts.get('orient', 'vertical')).startswith('v')

	def _preferredSize(self):
		if self._vertical():
			return (1, max(3, int(self._opts.get('height') or 3)))
		return (max(3, int(self._opts.get('width') or 3)), 1)

	def _length(self) -> int:
		return self._height if self._vertical() else self._width

	def _thumb(self):
		"""Return (start, end) of the thumb in trough cells."""
		trough = max(1, self._length() - 2)
		start  = int(round(self._first * trough))
		end    = max(start + 1, int(round(self._last * trough)))
		return start, min(end, trough)

	def render(self, scr):
		if not self._isMapped():
			return
		attr   = self._getAttr()
		n      = self._length()
		if _core.PX != 1:
			# Tk look: grey trough, darker slider
			tattr = self._getAttr(bg=self._opts.get('troughcolor') or '#c3c3c3')
			sattr = self._getAttr(bg='#8c8c8c')
			ts, te = self._thumb() if n >= 3 else (0, 0)
			cells = []
			for i in range(n):
				if n >= 3 and i == 0:
					cells.append(('▲' if self._vertical() else '◀', tattr))
				elif n >= 3 and i == n - 1:
					cells.append(('▼' if self._vertical() else '▶', tattr))
				else:
					cells.append((' ', sattr if ts <= i - 1 < te else tattr))
			for i, (ch, a) in enumerate(cells):
				if self._vertical():
					_addStr(scr, self._y + i, self._x, ch, a)
				else:
					_addStr(scr, self._y, self._x + i, ch, a)
			return
		if n < 3:
			cells = ['#'] * n
		else:
			ts, te = self._thumb()
			trough = '│' if self._vertical() else '─'
			cells  = ['▲' if self._vertical() else '◀']
			cells += ['█' if ts <= i < te else trough for i in range(n - 2)]
			cells += ['▼' if self._vertical() else '▶']
		if self._vertical():
			for i, ch in enumerate(cells):
				_addStr(scr, self._y + i, self._x, ch, attr)
		else:
			_addStr(scr, self._y, self._x, ''.join(cells), attr)

	# ------------------------------------------------------------------

	def _command(self, *args):
		cmd = self._opts.get('command')
		if callable(cmd):
			cmd(*args)

	def _handleMouse(self, mx, my, bstate):
		wheel = isWheel(bstate)
		if wheel:
			self._command('scroll', 3 * wheel, 'units')
			return True
		n   = self._length()
		pos = (my - self._y) if self._vertical() else (mx - self._x)
		press   = bool(bstate & B1_PRESS) and not (bstate & MOTION)
		release = bool(bstate & (B1_RELEASE | B1_CLICK))
		motion  = bool(bstate & MOTION) or (bstate & B1_PRESS and self._drag)

		if self._drag is not None and (motion or release):
			anchorPos, anchorFirst = self._drag
			trough = max(1, n - 2)
			frac   = anchorFirst + (pos - anchorPos) / trough
			self._command('moveto', max(0.0, min(1.0, frac)))
			if release:
				self._drag = None
			return True

		if not (press or bstate & B1_CLICK):
			return False
		if n < 3:
			return True
		if pos <= 0:
			self._command('scroll', -1, 'units')
		elif pos >= n - 1:
			self._command('scroll', 1, 'units')
		else:
			ts, te = self._thumb()
			cell   = pos - 1
			if cell < ts:
				self._command('scroll', -1, 'pages')
			elif cell >= te:
				self._command('scroll', 1, 'pages')
			elif press:
				self._drag = (pos, self._first)
		return True
