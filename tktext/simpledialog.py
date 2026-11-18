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

"""simpledialog — askstring/askinteger/askfloat (mirrors tkinter.simpledialog)."""

from ._core import _addStr, _fillRect, _drawBorder, _pad, _clip
from ._dialog import _Dialog, _getApp, _released
from ._events import (KEY_ENTER, KEY_CR, KEY_ESC, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_BACKSPACE, KEY_TAB, KEY_BTAB)
import curses


class _InputDialog(_Dialog):
	"""Modal one-line input box with OK / Cancel."""

	def __init__(self, app, title, prompt, initial='', convert=str,
			minvalue=None, maxvalue=None):
		super().__init__(app)
		self._title	= str(title or '')
		self._prompt	= str(prompt or '')
		self._value	= str(initial if initial is not None else '')
		self._cursor	= len(self._value)
		self._convert	= convert
		self._min	= minvalue
		self._max	= maxvalue
		self._error	= ''
		self._btnIdx	= -1		# -1: entry has focus, 0 OK, 1 Cancel

	def _size(self):
		app = self._app
		w   = max(40, len(self._title) + 6, len(self._prompt) + 4)
		return (min(w, app._width), min(8, app._height))

	def _pos(self):
		w, h = self._size()
		return ((self._app._width - w) // 2, (self._app._height - h) // 2)

	def render(self, scr):
		app	= self._app
		w, h	= self._size()
		x, y	= self._pos()
		attr	= app._colors.roleAttr('dialog')
		titleA	= app._colors.roleAttr('dialog.title')
		fieldA	= app._colors.roleAttr('dialog.field')
		selA	= app._colors.roleAttr('dialog.focus')
		_fillRect(scr, y, x, h, w, attr=attr)
		_drawBorder(scr, y, x, h, w, 'double', attr)
		_addStr(scr, y + 1, x + 1, _pad(f' {self._title} ', w - 2, 'center'), titleA)
		_addStr(scr, y + 2, x + 2, _clip(self._error or self._prompt, w - 4),
			app._colors.roleAttr('dialog.error') if self._error else attr)
		fw	= w - 4
		start	= max(0, self._cursor - fw + 1)
		_addStr(scr, y + 3, x + 2, _pad(self._value[start:], fw), fieldA)
		self._cursorXY = (y + 3, x + 2 + self._cursor - start)
		bx = x + (w - 20) // 2
		for i, label in enumerate(('[ OK ]', '[ Cancel ]')):
			_addStr(scr, y + h - 2, bx, label, selA if i == self._btnIdx else attr)
			bx += len(label) + 2
		if self._btnIdx < 0:
			try:
				curses.curs_set(1)
				scr.move(*self._cursorXY)
			except curses.error:
				pass

	def _accept(self):
		try:
			value = self._convert(self._value)
		except ValueError:
			self._error = 'Illegal value'
			return
		if self._min is not None and value < self._min:
			self._error = f'Minimum value is {self._min}'
			return
		if self._max is not None and value > self._max:
			self._error = f'Maximum value is {self._max}'
			return
		self._dismiss(value)

	def _handleKey(self, key):
		if key == KEY_ESC:
			self._dismiss(None)
		elif key in (KEY_ENTER, KEY_CR):
			if self._btnIdx == 1:
				self._dismiss(None)
			else:
				self._accept()
		elif key == KEY_TAB:
			self._btnIdx = (self._btnIdx + 2) % 3 - 1
		elif key == KEY_BTAB:
			self._btnIdx = (self._btnIdx + 1) % 3 - 1
		elif self._btnIdx >= 0:
			if key == ord(' '):
				self._handleKey(KEY_ENTER)
		elif key == KEY_LEFT:
			self._cursor = max(0, self._cursor - 1)
		elif key == KEY_RIGHT:
			self._cursor = min(len(self._value), self._cursor + 1)
		elif key == KEY_HOME:
			self._cursor = 0
		elif key == KEY_END:
			self._cursor = len(self._value)
		elif key == KEY_BACKSPACE:
			if self._cursor > 0:
				v = self._value
				self._value  = v[:self._cursor - 1] + v[self._cursor:]
				self._cursor -= 1
		elif key == curses.KEY_DC:
			v = self._value
			self._value = v[:self._cursor] + v[self._cursor + 1:]
		elif isinstance(key, int) and 32 <= key < 0x110000 and key != 127:
			v = self._value
			self._value   = v[:self._cursor] + chr(key) + v[self._cursor:]
			self._cursor += 1
			self._error   = ''

	def _handleMouse(self, mx, my, bstate):
		if not _released(bstate):
			return
		w, h = self._size()
		x, y = self._pos()
		if my == y + h - 2:
			bx = x + (w - 20) // 2
			if bx <= mx < bx + 6:
				self._accept()
			elif bx + 8 <= mx < bx + 18:
				self._dismiss(None)
		elif my == y + 3:
			self._btnIdx = -1


def _ask(title, prompt, convert, initialvalue=None, minvalue=None,
		maxvalue=None, parent=None, **kw):
	app = _getApp(parent)
	if app is None:
		return None
	return _InputDialog(app, title, prompt, initialvalue, convert,
		minvalue, maxvalue).run()


def askstring(title, prompt, **kw):
	return _ask(title, prompt, str, **kw)


def askinteger(title, prompt, **kw):
	return _ask(title, prompt, int, **kw)


def askfloat(title, prompt, **kw):
	return _ask(title, prompt, float, **kw)


# tkinter's private helpers, imported by applications (e.g. idlelib)
def _setup_dialog(w) -> None:
	"""A terminal has no window manager types: nothing to set"""
	return None


def _place_window(w, parent=None) -> None:
	"""Centre w on parent (or the screen) like ::tk::PlaceWindow"""
	w.tk.call('::tk::PlaceWindow', w, 'widget', parent)
