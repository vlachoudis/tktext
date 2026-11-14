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
# Date:   14-Nov-2026

from ._button import Button
from ._core   import _initArgs
from ._events import B1_PRESS, B1_CLICK, MOTION


class Menubutton(Button):
	"""Button posting its menu=… below it.  Mirrors tkinter.Menubutton
	and ttk.Menubutton (direction below/above/left/right/flush)."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'menu':		'',
			'direction':	'below',
			'indicatoron':	True,
		})
		if kwargs:
			Menubutton.configure(self, **kwargs)

	def _menu(self):
		menu = self._opts.get('menu')
		if isinstance(menu, str) and menu:
			try:
				menu = self.nametowidget(menu)
			except (KeyError, ValueError):
				return None
		return menu or None

	def _rawText(self):
		text = super()._rawText()
		ind  = self._opts.get('indicatoron')
		return f'{text} ▼' if ind not in (False, 0, '0', '') else text

	def _press(self):
		"""Post the menu next to the button (Tk menubutton activation)."""
		menu = self._menu()
		if menu is None:
			return
		if menu._posted:
			menu.unpost()
			return
		direction = str(self._opts.get('direction') or 'below')
		x, y = self._x, self._y + self._height
		if direction == 'above':
			y = max(0, self._y - menu._menuHeight())
		elif direction == 'left':
			x, y = max(0, self._x - menu._menuWidth()), self._y
		elif direction == 'right':
			x, y = self._x + self._width, self._y
		elif direction == 'flush':
			y = self._y
		app = self._getApp()
		if direction == 'below' and app is not None and \
				y + menu._menuHeight() > app._height:
			y = max(0, self._y - menu._menuHeight())
		menu._post(x, y)
		self._markDirty()

	def _handleMouse(self, mx, my, bstate):
		if self._opts.get('state') == 'disabled':
			return False
		# a menubutton posts its menu on the press
		if bstate & (B1_PRESS | B1_CLICK) and not (bstate & MOTION):
			self._press()
			return True
		return False
