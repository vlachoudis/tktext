import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad, _clip
from ._events import (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_BACKSPACE, KEY_DC, KEY_ENTER, KEY_CR, KEY_ESC)


class Combobox(Widget):
	"""Entry widget with a dropdown value list.  Mirrors ttk.Combobox."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'values':          (),
			'textvariable':    None,
			'justify':         'left',
			'postcommand':     None,
			'exportselection': True,
		})
		kwargs.setdefault('relief',      'sunken')
		kwargs.setdefault('borderwidth', 1)
		kwargs.setdefault('width',       15)
		if kwargs:
			self.configure(**kwargs)

		tv           = self._opts.get('textvariable')
		self._text   = str(tv.get()) if tv is not None else ''
		self._cur    = len(self._text)
		self._scrollX = 0
		self._open   = False	# dropdown visible?
		self._ddIdx  = 0	# highlighted row in dropdown
		self._ddScroll = 0	# first visible row in dropdown
		self._dropdown = None	# _ComboDropdown overlay while open

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def get(self) -> str:
		tv = self._opts.get('textvariable')
		return tv.get() if tv is not None else self._text

	def set(self, value: str):
		self._text = str(value)
		self._cur  = len(self._text)
		tv = self._opts.get('textvariable')
		if tv is not None:
			tv.set(value)
		self._scrollToCursor()
		self._markDirty()

	def current(self, idx: int = None):
		"""Get or set the current selection index in the values list."""
		vals = list(self._opts.get('values') or [])
		if idx is None:
			try:
				return vals.index(self.get())
			except ValueError:
				return -1
		if 0 <= idx < len(vals):
			self.set(str(vals[idx]))

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _visW(self) -> int:
		bd = int(self._opts.get('borderwidth') or 0)
		return max(1, self._w - 2*bd - 3)	# 3 = space + ▼ + space

	def _ddMaxH(self) -> int:
		return min(len(list(self._opts.get('values') or [])), 6)

	def _scrollToCursor(self):
		visW = self._visW()
		if self._cur < self._scrollX:
			self._scrollX = self._cur
		elif self._cur >= self._scrollX + visW:
			self._scrollX = self._cur - visW + 1

	def _openDropdown(self):
		cmd = self._opts.get('postcommand')
		if callable(cmd):
			cmd()
		vals = list(self._opts.get('values') or [])
		if not vals:
			return
		cur          = self.current()
		self._ddIdx  = max(0, cur)
		self._ddScroll = max(0, self._ddIdx - self._ddMaxH() + 1)
		self._open   = True
		app          = self._getApp()
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
		if selectIdx >= 0:
			vals = list(self._opts.get('values') or [])
			if 0 <= selectIdx < len(vals):
				self.set(str(vals[selectIdx]))
				self._dispatch('<<ComboboxSelected>>', _CBEvent(self))
		self._markDirty()

	def _preferredSize(self):
		bd = int(self._opts.get('borderwidth') or 0)
		ow = int(self._opts.get('width') or 15)
		return (ow + 2*bd + 3, 1 + 2*bd)

	# ------------------------------------------------------------------
	# Rendering (widget body only; dropdown is rendered as an overlay)
	# ------------------------------------------------------------------

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return
		bd   = int(self._opts.get('borderwidth') or 0)
		attr = self._getAttr()
		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)
		if bd > 0:
			_drawBorder(scr, self._y, self._x, self._h, self._w,
				self._opts.get('relief', 'sunken'), attr)

		visW = self._visW()
		by   = self._y + bd + (self._h - 2*bd) // 2
		bx   = self._x + bd
		tv   = self._opts.get('textvariable')
		text = tv.get() if tv is not None else self._text
		vis  = text[self._scrollX:self._scrollX + visW]
		_addStr(scr, by, bx, vis.ljust(visW), attr)

		btnX  = self._x + self._w - bd - 3
		battr = attr | curses.A_REVERSE
		_addStr(scr, by, btnX, ' ▼ ', battr)

	def _renderDropdown(self, scr):
		"""Render the dropdown list overlay (called by _ComboDropdown)."""
		vals  = list(self._opts.get('values') or [])
		ddH   = self._ddMaxH() + 2	# +2 for borders
		ddW   = self._w
		ddX   = self._x
		app   = self._getApp()
		scrH  = app._h if app else 24
		ddY   = (self._y + self._h if self._y + self._h + ddH <= scrH
			else max(0, self._y - ddH))

		lattr = self._getAttr()
		sattr = self._getAttr() | curses.A_REVERSE
		_fillRect(scr, ddY, ddX, ddH, ddW, attr=lattr)
		_drawBorder(scr, ddY, ddX, ddH, ddW, 'single', lattr)
		inner = ddH - 2
		for i in range(inner):
			idx = self._ddScroll + i
			if idx >= len(vals):
				break
			txt   = _pad(str(vals[idx]), ddW - 2)
			iattr = sattr if idx == self._ddIdx else lattr
			_addStr(scr, ddY + 1 + i, ddX + 1, txt, iattr)

	def _ddRect(self):
		"""Return (x, y, w, h) of the dropdown overlay."""
		ddH  = self._ddMaxH() + 2
		ddW  = self._w
		ddX  = self._x
		app  = self._getApp()
		scrH = app._h if app else 24
		ddY  = (self._y + self._h if self._y + self._h + ddH <= scrH
			else max(0, self._y - ddH))
		return (ddX, ddY, ddW, ddH)

	def _cursorPos(self):
		bd = int(self._opts.get('borderwidth') or 0)
		cy = self._y + bd + (self._h - 2*bd) // 2
		cx = self._x + bd + (self._cur - self._scrollX)
		return (cy, cx)

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _isFocusable(self):
		return self._opts.get('state', 'normal') in ('normal', 'readonly')

	def _handleDropdownMouse(self, mx, my, bstate):
		"""Called by _ComboDropdown when a click lands in the dropdown."""
		if not (bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED)):
			return False
		ddX, ddY, ddW, ddH = self._ddRect()
		row = my - ddY - 1
		if 0 <= row < ddH - 2:
			self._closeDropdown(self._ddScroll + row)
		else:
			self._closeDropdown()
		return True

	def _handleKey(self, key):
		if self._open:
			vals = list(self._opts.get('values') or [])
			n    = len(vals)
			vis  = self._ddMaxH()
			if key == KEY_DOWN:
				self._ddIdx = min(n - 1, self._ddIdx + 1)
				if self._ddIdx >= self._ddScroll + vis:
					self._ddScroll += 1
			elif key == KEY_UP:
				self._ddIdx = max(0, self._ddIdx - 1)
				if self._ddIdx < self._ddScroll:
					self._ddScroll -= 1
			elif key in (KEY_ENTER, KEY_CR):
				self._closeDropdown(self._ddIdx)
			elif key == KEY_ESC:
				self._closeDropdown()
			self._markDirty()
			return True

		if key == KEY_DOWN:
			vals = list(self._opts.get('values') or [])
			if self._opts.get('state') == 'readonly':
				self._openDropdown()
			elif vals:
				cur = self.current()
				if cur < len(vals) - 1:
					self.set(str(vals[cur + 1]))
					self._dispatch('<<ComboboxSelected>>', _CBEvent(self))
			return True
		if key == KEY_UP:
			vals = list(self._opts.get('values') or [])
			if vals:
				cur = self.current()
				if cur > 0:
					self.set(str(vals[cur - 1]))
					self._dispatch('<<ComboboxSelected>>', _CBEvent(self))
			return True

		if self._opts.get('state') == 'readonly':
			return super()._handleKey(key)

		# Text editing
		tv   = self._opts.get('textvariable')
		text = self._text
		c    = self._cur
		if key == KEY_LEFT:
			self._cur = max(0, c - 1)
		elif key == KEY_RIGHT:
			self._cur = min(len(text), c + 1)
		elif key == KEY_HOME:
			self._cur = 0
		elif key == KEY_END:
			self._cur = len(text)
		elif key in (KEY_BACKSPACE, 127):
			if c > 0:
				self._text = text[:c-1] + text[c:]
				self._cur -= 1
				if tv: tv.set(self._text)
		elif key == KEY_DC:
			if c < len(text):
				self._text = text[:c] + text[c+1:]
				if tv: tv.set(self._text)
		elif 32 <= key <= 126:
			self._text = text[:c] + chr(key) + text[c:]
			self._cur += 1
			if tv: tv.set(self._text)
		else:
			return super()._handleKey(key)
		self._scrollToCursor()
		self._markDirty()
		return True

	def _handleMouse(self, mx, my, bstate):
		if not (bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED)):
			return False
		bd   = int(self._opts.get('borderwidth') or 0)
		btnX = self._x + self._w - bd - 3
		if mx >= btnX:
			if self._open:
				self._closeDropdown()
			else:
				self._openDropdown()
			return True
		if self._opts.get('state') != 'readonly':
			bx        = self._x + bd
			self._cur = max(0, min(len(self._text), self._scrollX + (mx - bx)))
			self._scrollToCursor()
			self._markDirty()
		return True


# ---------------------------------------------------------------------------
# Dropdown overlay — registered in app._postedMenus while open
# ---------------------------------------------------------------------------

class _ComboDropdown:
	"""Thin proxy posted to _postedMenus to catch clicks in the dropdown."""

	def __init__(self, cb: Combobox):
		self._cb = cb

	def _menuWidth(self) -> int:
		return self._cb._w

	def _menuHeight(self) -> int:
		return self._cb._ddMaxH() + 2

	@property
	def _postX(self) -> int:
		return self._cb._x

	@property
	def _postY(self) -> int:
		app  = self._cb._getApp()
		scrH = app._h if app else 24
		ddH  = self._menuHeight()
		return (self._cb._y + self._cb._h
			if self._cb._y + self._cb._h + ddH <= scrH
			else max(0, self._cb._y - ddH))

	def render(self, scr):
		self._cb._renderDropdown(scr)

	def unpost(self):
		self._cb._closeDropdown()

	def _handleMouse(self, mx, my, bstate):
		return self._cb._handleDropdownMouse(mx, my, bstate)

	def _handleKey(self, key):
		return self._cb._handleKey(key)


class _CBEvent:
	def __init__(self, widget):
		self.widget  = widget
		self.type    = 'ComboboxSelected'
		self.char    = ''
		self.keysym  = ''
