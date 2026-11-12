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
from ._entry import Entry
from ._core import _addStr, _fillRect, _drawBorder, _pad, _int, _initArgs
from ._events import (KEY_UP, KEY_DOWN, KEY_HOME, KEY_END, KEY_PPAGE,
	KEY_NPAGE, KEY_ENTER, KEY_ESC, KEY_SPACE, KEY_TAB,
	B1_PRESS, B1_RELEASE, B1_CLICK, MOTION, isWheel)


class Combobox(Entry):
	"""Entry widget with a dropdown value list.  Mirrors ttk.Combobox.

	Editing, selection and the textvariable are inherited from Entry;
	with state='readonly' the text can only be chosen from the list."""

	_BUTTON = ' ▼ '

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'values':		(),
			'postcommand':		None,
			'height':		10,
		})
		kwargs.setdefault('width', 15)
		self._open     = False	# dropdown visible?
		self._ddIdx    = 0	# highlighted row in dropdown
		self._ddScroll = 0	# first visible row in dropdown
		self._dropdown = None	# _ComboDropdown overlay while open
		if kwargs:
			Combobox.configure(self, **kwargs)

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def set(self, value):
		"""Set the text (works also in readonly state)."""
		self._setBuf(str(value))
		self._cur = len(self._getBuf())
		self._sel = None
		self._scrollToCursor()

	def current(self, idx=None):
		"""Get or set the current selection index in the values list."""
		vals = self._values()
		if idx is None:
			cur = self.get()
			return vals.index(cur) if cur in vals else -1
		idx = int(idx)
		if not 0 <= idx < len(vals):
			raise IndexError(f'index {idx} out of range')
		self.set(vals[idx])
		return None

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _values(self):
		vals = self._opts.get('values') or ()
		if isinstance(vals, str):
			vals = vals.split()
		return [str(v) for v in vals]

	def _visW(self) -> int:
		return max(1, self._width - 2*self._border() - len(self._BUTTON))

	def _ddRows(self) -> int:
		return max(1, min(len(self._values()), _int(self._opts.get('height'), 10) or 10))

	def _preferredSize(self):
		bd = self._cfgBorder()
		ow = _int(self._opts.get('width'), 15) or 15
		return (ow + 2*bd + len(self._BUTTON), 1 + 2*bd)

	def _ensureDdVisible(self):
		rows = self._ddRows()
		if self._ddIdx < self._ddScroll:
			self._ddScroll = self._ddIdx
		elif self._ddIdx >= self._ddScroll + rows:
			self._ddScroll = self._ddIdx - rows + 1
		self._ddScroll = max(0, min(self._ddScroll, max(0, len(self._values()) - rows)))

	def _openDropdown(self):
		cmd = self._opts.get('postcommand')
		if callable(cmd):
			cmd()
		vals = self._values()
		if not vals:
			return
		self._ddIdx    = max(0, self.current())
		self._ddScroll = 0
		self._ensureDdVisible()
		self._open     = True
		app            = self._getApp()
		if app is not None:
			self._dropdown = _ComboDropdown(self)
			app._postedMenus.append(self._dropdown)
		self._markDirty()

	def _closeDropdown(self, selectIdx: int = -1):
		if self._open:
			app = self._getApp()
			if app is not None and self._dropdown in app._postedMenus:
				app._postedMenus.remove(self._dropdown)
		self._open     = False
		self._dropdown = None
		vals = self._values()
		if 0 <= selectIdx < len(vals):
			self.set(vals[selectIdx])
			self._fireVirtual('<<ComboboxSelected>>')
		self._markDirty()

	def _ddRect(self):
		"""Return (x, y, w, h) of the dropdown overlay."""
		ddH  = self._ddRows() + 2
		app  = self._getApp()
		scrH = app._height if app else 24
		below = self._y + self._height
		ddY  = below if below + ddH <= scrH or self._y - ddH < 0 else self._y - ddH
		return (self._x, ddY, self._width, ddH)

	# ------------------------------------------------------------------
	# Rendering (widget body only; dropdown is rendered as an overlay)
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return
		super().render(scr)
		bd    = self._border()
		by    = self._y + bd + (self._height - 2*bd - 1) // 2
		battr = self._getAttr() | curses.A_REVERSE
		_addStr(scr, by, self._x + self._width - bd - len(self._BUTTON), self._BUTTON, battr)

	def _renderDropdown(self, scr):
		vals = self._values()
		ddX, ddY, ddW, ddH = self._ddRect()
		lattr = self._getAttr()
		sattr = lattr | curses.A_REVERSE
		_fillRect(scr, ddY, ddX, ddH, ddW, attr=lattr)
		_drawBorder(scr, ddY, ddX, ddH, ddW, 'single', lattr)
		rows = ddH - 2
		for i in range(rows):
			idx = self._ddScroll + i
			if idx >= len(vals):
				break
			_addStr(scr, ddY + 1 + i, ddX + 1, _pad(vals[idx], ddW - 2),
				sattr if idx == self._ddIdx else lattr)
		if len(vals) > rows:
			thumb = int(self._ddScroll * rows / len(vals))
			_addStr(scr, ddY + 1 + thumb, ddX + ddW - 1, '█', lattr)

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _isFocusable(self):
		return self._opts.get('state', 'normal') in ('normal', 'readonly')

	def _dropdownKey(self, key):
		n = len(self._values())
		rows = self._ddRows()
		if key == KEY_DOWN:
			self._ddIdx = min(n - 1, self._ddIdx + 1)
		elif key == KEY_UP:
			self._ddIdx = max(0, self._ddIdx - 1)
		elif key == KEY_NPAGE:
			self._ddIdx = min(n - 1, self._ddIdx + rows)
		elif key == KEY_PPAGE:
			self._ddIdx = max(0, self._ddIdx - rows)
		elif key == KEY_HOME:
			self._ddIdx = 0
		elif key == KEY_END:
			self._ddIdx = n - 1
		elif key in (KEY_ENTER, KEY_SPACE, KEY_TAB):
			self._closeDropdown(self._ddIdx)
			return True
		elif key == KEY_ESC:
			self._closeDropdown()
			return True
		elif isinstance(key, int) and 32 < key < 127:
			ch   = chr(key).lower()
			vals = self._values()
			for j in list(range(self._ddIdx + 1, n)) + list(range(0, self._ddIdx + 1)):
				if vals[j][:1].lower() == ch:
					self._ddIdx = j
					break
		self._ensureDdVisible()
		self._markDirty()
		return True

	def _handleKey(self, key):
		if self._open:
			return self._dropdownKey(key)
		state = self._opts.get('state', 'normal')
		if state == 'disabled':
			return False
		if key == KEY_DOWN or (state == 'readonly' and key in (KEY_ENTER, KEY_SPACE)):
			self._openDropdown()
			return True
		if key == KEY_UP:
			return True
		return super()._handleKey(key)

	def _handleDropdownMouse(self, mx, my, bstate):
		"""Called by _ComboDropdown for events inside the dropdown."""
		wheel = isWheel(bstate)
		if wheel:
			self._ddScroll += 3 * wheel
			rows = self._ddRows()
			self._ddScroll = max(0, min(self._ddScroll, max(0, len(self._values()) - rows)))
			self._markDirty()
			return True
		_, ddY, _, ddH = self._ddRect()
		row = my - ddY - 1
		if 0 <= row < ddH - 2 and self._ddScroll + row < len(self._values()):
			self._ddIdx = self._ddScroll + row
			if bstate & (B1_RELEASE | B1_CLICK):
				self._closeDropdown(self._ddIdx)
		self._markDirty()
		return True

	def _handleMouse(self, mx, my, bstate):
		state = self._opts.get('state', 'normal')
		if state == 'disabled':
			return False
		wheel = isWheel(bstate)
		if wheel and not self._open:
			vals = self._values()
			if vals:
				cur = self.current()
				nxt = max(0, min(len(vals) - 1, cur + wheel))
				if nxt != cur:
					self.set(vals[nxt])
					self._fireVirtual('<<ComboboxSelected>>')
			return True
		pressed = bool(bstate & (B1_PRESS | B1_CLICK)) and not (bstate & MOTION)
		btnX    = self._x + self._width - self._border() - len(self._BUTTON)
		if pressed and not self._mouseDown and (mx >= btnX or state == 'readonly'):
			if self._open:
				self._closeDropdown()
			else:
				self._openDropdown()
			return True
		if state == 'readonly':
			return True
		return super()._handleMouse(mx, my, bstate)


# ---------------------------------------------------------------------------
# Dropdown overlay — registered in app._postedMenus while open
# ---------------------------------------------------------------------------

class _ComboDropdown:
	"""Thin proxy posted to _postedMenus to catch input for the dropdown."""

	def __init__(self, cb: Combobox):
		self._cb     = cb
		self._posted = True

	def _menuWidth(self) -> int:
		return self._cb._ddRect()[2]

	def _menuHeight(self) -> int:
		return self._cb._ddRect()[3]

	@property
	def _postX(self) -> int:
		return self._cb._ddRect()[0]

	@property
	def _postY(self) -> int:
		return self._cb._ddRect()[1]

	def render(self, scr):
		self._cb._renderDropdown(scr)

	def unpost(self):
		self._posted = False
		self._cb._closeDropdown()

	def _handleMouse(self, mx, my, bstate):
		return self._cb._handleDropdownMouse(mx, my, bstate)

	def _handleKey(self, key):
		return self._cb._dropdownKey(key)
