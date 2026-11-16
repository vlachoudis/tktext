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

from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad, _sameValue, _int, _initArgs
from ._layout import _truthy
from ._events import KEY_ENTER, KEY_SPACE, B1_RELEASE, B1_CLICK, MOTION


# Default variable when none provided
class _BoolVar:
	def __init__(self):
		self._val = 0
	def get(self):
		return self._val
	def set(self, v):
		self._val = v


class Checkbutton(Widget):
	"""Toggle button widget.  Mirrors tkinter.Checkbutton."""

	_clickFocus = False	# tkinter: clicking does not take the focus

	def _showsFocus(self) -> bool: return True

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
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
			'disabledforeground':	'',
			'selectcolor':		'',
		})
		kwargs.setdefault('relief', 'flat')
		kwargs.setdefault('borderwidth', 0)
		if kwargs:
			Checkbutton.configure(self, **kwargs)

		# Ensure a variable exists
		if self._opts.get('variable') is None:
			self._opts['variable'] = self._defaultVar()

	# ------------------------------------------------------------------
	# Variable access helpers
	# ------------------------------------------------------------------

	def _defaultVar(self):
		return _BoolVar()

	def _getVar(self):
		v = self._opts.get('variable')
		if v is None:
			v = self._defaultVar()
			self._opts['variable'] = v
		return v

	def _isChecked(self) -> bool:
		try:
			cur = self._getVar().get()
		except (TypeError, ValueError):
			return False
		return _sameValue(cur, self._opts.get('onvalue', 1))

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def invoke(self):
		"""Toggle the checkbutton and call its command."""
		if self._opts.get('state') == 'disabled':
			return None
		if self._isChecked():
			self._getVar().set(self._opts.get('offvalue', 0))
		else:
			self._getVar().set(self._opts.get('onvalue', 1))
		self._markDirty()
		cmd = self._opts.get('command')
		if callable(cmd):
			return cmd()
		return None

	def select(self):
		"""Set checkbutton to on state."""
		self._getVar().set(self._opts.get('onvalue', 1))
		self._markDirty()

	def deselect(self):
		"""Set checkbutton to off state."""
		self._getVar().set(self._opts.get('offvalue', 0))
		self._markDirty()

	def toggle(self):
		"""Toggle the checkbutton without calling the command."""
		if self._isChecked():
			self.deselect()
		else:
			self.select()

	# ------------------------------------------------------------------

	def _getText(self) -> str:
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return self._withImage(str(tv.get()))
		return self._withImage(str(self._opts.get('text') or ''))

	def _showIndicator(self) -> bool:
		return _truthy(self._opts.get('indicatoron', True))

	def _indicator(self) -> str:
		if not self._showIndicator():
			return ''
		return '[X] ' if self._isChecked() else '[ ] '

	def _preferredSize(self):
		bd    = self._cfgBorder()
		padx  = _int(self._opts.get('padx'))
		lines = self._getText().expandtabs(8).split('\n')
		textW = max(len(l) for l in lines)
		w     = max(_int(self._opts.get('width')), len(self._indicator()) + textW) + 2*bd + 2*padx
		h     = len(lines) + 2*bd
		return (max(w, 1), max(h, 1))

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return

		state   = self._opts.get('state', 'normal')
		bd      = self._border()
		padx    = _int(self._opts.get('padx'))
		relief  = self._opts.get('relief', 'flat')

		if state == 'disabled':
			attr = self._disabledAttr()
		elif self._focused:
			attr = self._focusAttr()
		elif not self._showIndicator() and self._isChecked():
			# indicatoron=False: a selected button is shown pressed
			sc   = self._optColor('selectcolor')
			attr = self._getAttr(bg=sc) if sc else self._roleAttr('select')
		else:
			attr = self._getAttr()

		_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)

		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._height, self._width, relief,
				self._borderAttr(attr))

		cw    = max(0, self._width - 2*bd - 2*padx)
		lines = self._getText().expandtabs(8).split('\n')
		ind   = self._indicator()
		for i, line in enumerate(lines):
			if i >= self._height - 2*bd:
				break
			pfx = ind if i == 0 else ' ' * len(ind)
			_addStr(scr, self._y + bd + i, self._x + bd + padx,
				_pad(pfx + line, cw, 'left'), attr)

	# ------------------------------------------------------------------
	# Focus / input
	# ------------------------------------------------------------------

	def _handleKey(self, key: int) -> bool:
		if self._opts.get('state') == 'disabled':
			return False
		if key in (KEY_ENTER, KEY_SPACE):
			self.invoke()
			return True
		return False

	def _handleMouse(self, mx: int, my: int, bstate: int) -> bool:
		if self._opts.get('state') == 'disabled':
			return False
		if bstate & (B1_RELEASE | B1_CLICK) and not (bstate & MOTION):
			if self._hitTest(mx, my):
				self.invoke()
			return True
		return False
