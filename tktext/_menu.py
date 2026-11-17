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
from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad, _sameValue, _initArgs, _cellX, _cellY
from ._events import (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_HOME, KEY_END,
	KEY_ENTER, KEY_CR, KEY_ESC, KEY_SPACE, MOTION, B1_PRESS, B1_RELEASE,
	B1_CLICK, B1_DCLICK, isWheel)


_ITEM_DEFAULTS = {
	'label':	'',
	'command':	None,
	'state':	'normal',
	'accelerator':	'',
	'underline':	-1,
	'menu':		None,
	'variable':	None,
	'value':	None,
	'onvalue':	1,
	'offvalue':	0,
	'columnbreak':	0,
}


class Menu(Widget):
	"""Popup / menubar menu widget.  Mirrors tkinter.Menu.

	Not laid out via pack/grid/place — overlays the screen when posted.
	A Menu given to root.configure(menu=…) is drawn as a menubar on the
	title row.
	"""

	def _showsFocus(self) -> bool: return True

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'activeforeground':	'',
			'activebackground':	'',
			'disabledforeground':	'',
			'tearoff':		0,
			'postcommand':		None,
			'takefocus':		False,
		})
		kwargs.setdefault('relief', 'single')
		kwargs.setdefault('borderwidth', 1)
		if kwargs:
			Menu.configure(self, **kwargs)

		self._menuItems   = []	# list of item dicts
		self._active      = -1	# highlighted row index
		self._posted      = False
		self._postX       = 0
		self._postY       = 0
		self._parentMenu  = None	# set when used as cascade submenu
		self._fromMenuBar = False	# posted as a menubar drop-down

	# ------------------------------------------------------------------
	# Focus override — menus don't participate in tab focus
	# ------------------------------------------------------------------

	def _isFocusable(self) -> bool:
		return False

	# ------------------------------------------------------------------
	# Item addition
	# ------------------------------------------------------------------

	def _makeItem(self, itemType, kwargs):
		item = dict(_ITEM_DEFAULTS)
		item.update(kwargs)
		item['type'] = itemType
		if itemType == 'radiobutton' and item['value'] is None:
			item['value'] = item['label']
		sub = item.get('menu')
		if itemType == 'cascade' and sub is not None:
			sub._parentMenu = self
		return item

	def add(self, itemType: str, cnf=None, **kwargs):
		"""Add an item of *itemType* ('command', 'separator', etc.)."""
		if cnf:
			kwargs.update(cnf)
		self._menuItems.append(self._makeItem(itemType, kwargs))
		self._markDirty()

	def add_command(self, cnf=None, **kwargs):
		self.add('command', cnf, **kwargs)

	def add_separator(self, cnf=None, **kwargs):
		self.add('separator', cnf, **kwargs)

	def add_cascade(self, cnf=None, **kwargs):
		self.add('cascade', cnf, **kwargs)

	def add_checkbutton(self, cnf=None, **kwargs):
		self.add('checkbutton', cnf, **kwargs)

	def add_radiobutton(self, cnf=None, **kwargs):
		self.add('radiobutton', cnf, **kwargs)

	# camelCase aliases
	addCommand     = add_command
	addSeparator   = add_separator
	addCascade     = add_cascade
	addCheckbutton = add_checkbutton
	addRadiobutton = add_radiobutton

	# ------------------------------------------------------------------
	# Item modification / query
	# ------------------------------------------------------------------

	def delete(self, index1: object, index2: object = None):
		"""Delete items from index1 to index2 (inclusive)."""
		i1 = self._resolveIndex(index1)
		if i1 < 0 or i1 >= len(self._menuItems):
			return
		i2 = i1 if index2 is None else min(self._resolveIndex(index2),
			len(self._menuItems) - 1)
		del self._menuItems[i1:i2 + 1]
		if self._active >= len(self._menuItems):
			self._active = self._firstSelectable()
		self._markDirty()

	def insert(self, idx: object, itemType: str, cnf=None, **kwargs):
		"""Insert a new item before position *idx*."""
		if cnf:
			kwargs.update(cnf)
		i = self._resolveIndex(idx)
		if i < 0:
			i = len(self._menuItems)
		self._menuItems.insert(i, self._makeItem(itemType, kwargs))
		self._markDirty()

	def insert_command(self, index, cnf=None, **kw):
		self.insert(index, 'command', cnf, **kw)

	def insert_separator(self, index, cnf=None, **kw):
		self.insert(index, 'separator', cnf, **kw)

	def insert_cascade(self, index, cnf=None, **kw):
		self.insert(index, 'cascade', cnf, **kw)

	def insert_checkbutton(self, index, cnf=None, **kw):
		self.insert(index, 'checkbutton', cnf, **kw)

	def insert_radiobutton(self, index, cnf=None, **kw):
		self.insert(index, 'radiobutton', cnf, **kw)

	def entryconfig(self, index: object, cnf=None, **kwargs):
		"""Configure item at *index*."""
		if cnf:
			kwargs.update(cnf)
		i = self._resolveIndex(index)
		if 0 <= i < len(self._menuItems):
			if not kwargs:
				return dict(self._menuItems[i])
			self._menuItems[i].update(kwargs)
			sub = kwargs.get('menu')
			if sub is not None:
				sub._parentMenu = self
			self._markDirty()
		return None

	entryconfigure = entryconfig
	entry_config   = entryconfig
	entryConfig    = entryconfig

	def entrycget(self, index: object, option: str):
		"""Return value of *option* for item at *index*."""
		i = self._resolveIndex(index)
		if 0 <= i < len(self._menuItems):
			return self._menuItems[i].get(option)
		return None

	entryCget = entrycget

	def yposition(self, index):
		"""Y coordinate of the top of entry *index* (screen units)."""
		from . import _core
		i = self._resolveIndex(index)
		cells, _ = self._layout()
		row = cells[i][1] if 0 <= i < len(cells) else 0
		return (row + self._border()) * _core.PY

	def xposition(self, index):
		"""X coordinate of the left of entry *index* (screen units)."""
		from . import _core
		i = self._resolveIndex(index)
		cells, _ = self._layout()
		x = cells[i][0] if 0 <= i < len(cells) else 0
		return (x + self._border()) * _core.PX

	def index(self, index: object):
		"""Return integer index for *index* (None for 'none')."""
		i = self._resolveIndex(index)
		return None if i < 0 else i

	def type(self, index: object) -> str:
		"""Return type string for item at *index*."""
		i = self._resolveIndex(index)
		if 0 <= i < len(self._menuItems):
			return self._menuItems[i]['type']
		return ''

	# ------------------------------------------------------------------
	# Post / unpost
	# ------------------------------------------------------------------

	def post(self, x: int, y: int):
		"""Display menu at screen position (x, y) — screen units like in
		tkinter (pixels in pixel mode, e.g. event.x_root/winfo_rootx())."""
		self._post(_cellX(x), _cellY(y))

	def _post(self, x: int, y: int):
		"""Display menu at screen cell (x, y) (internal callers)."""
		cmd = self._opts.get('postcommand')
		if callable(cmd):
			cmd()
		self._postX  = int(x)
		self._postY  = int(y)
		self._posted = True
		if not (0 <= self._active < len(self._menuItems)) or \
				not self._selectable(self._active):
			self._active = self._firstSelectable()
		app = self._getApp()
		if app is not None and hasattr(app, '_postedMenus'):
			if self in app._postedMenus:
				app._postedMenus.remove(self)
			app._postedMenus.append(self)
		self._markDirty()

	def unpost(self):
		"""Hide this menu (and any open submenus)."""
		# Close any open cascades first
		for item in self._menuItems:
			sub = item.get('menu')
			if sub is not None and sub._posted:
				sub.unpost()
		self._posted      = False
		self._fromMenuBar = False
		app = self._getApp()
		if app is not None and hasattr(app, '_postedMenus'):
			if self in app._postedMenus:
				app._postedMenus.remove(self)
		self._markDirty()

	def tk_popup(self, x: int, y: int, entry: object = None):
		"""Post menu at (x, y). Mirrors tkinter.Menu.tk_popup."""
		self.post(x, y)
		if entry not in (None, ''):
			i = self._resolveIndex(entry)
			if self._selectable(i):
				self._active = i

	tkPopup = tk_popup

	def activate(self, index):
		i = self._resolveIndex(index)
		self._active = i if self._selectable(i) else -1
		self._markDirty()

	def invoke(self, index: object):
		"""Invoke the item at *index*."""
		i = self._resolveIndex(index)
		if not (0 <= i < len(self._menuItems)):
			return None
		item  = self._menuItems[i]
		itype = item['type']
		if item.get('state', 'normal') == 'disabled' or itype == 'separator':
			return None

		if itype == 'cascade':
			self._openCascade(i)
			return None
		if itype == 'checkbutton':
			v = item.get('variable')
			if v is not None:
				if _sameValue(v.get(), item.get('onvalue', 1)):
					v.set(item.get('offvalue', 0))
				else:
					v.set(item.get('onvalue', 1))
		elif itype == 'radiobutton':
			v = item.get('variable')
			if v is not None:
				v.set(item.get('value'))
		self._closeAll()
		cmd = item.get('command')
		if callable(cmd):
			return cmd()
		return None

	def _openCascade(self, i):
		item = self._menuItems[i]
		sub  = item.get('menu')
		if sub is None:
			return
		# close sibling cascades
		for j, other in enumerate(self._menuItems):
			o = other.get('menu')
			if j != i and o is not None and o._posted:
				o.unpost()
		px, py, _, _ = self._screenRect()
		bd        = self._border()
		cells, cw = self._layout()
		x, row, c = cells[i]
		subX      = px + bd + x + cw[c] + bd
		app       = self._getApp()
		if app is not None and subX + sub._menuWidth() > app._width:
			subX = max(0, px + x - sub._menuWidth())
		sub._parentMenu = self
		sub._post(subX, py + bd + row - sub._border())
		self._active = i

	# ------------------------------------------------------------------
	# Geometry helpers
	# ------------------------------------------------------------------

	@staticmethod
	def _itemWidth(item) -> int:
		"""Cells needed by *item* inside the borders."""
		itype = item['type']
		if itype == 'separator':
			return 0
		label  = str(item.get('label', ''))
		accel  = str(item.get('accelerator', '') or '')
		prefix = 4 if itype in ('checkbutton', 'radiobutton') else 0
		suffix = 2 if itype == 'cascade' else 0	# ' ▶'
		accelW = len(accel) + 2 if accel else 0
		return prefix + len(label) + accelW + suffix + 2

	def _layout(self):
		"""Column layout like Tk: an item with columnbreak starts a new column.
		Return (cells, widths): cells[i] = (x, row, column) relative to the
		inside of the border, widths[c] the width of column c."""
		cells  = []
		widths = [0]
		x      = 0
		row    = 0
		for i, item in enumerate(self._menuItems):
			if i > 0 and item.get('columnbreak'):
				x  += max(widths[-1], 4)
				row = 0
				widths.append(0)
			cells.append((x, row, len(widths)-1))
			widths[-1] = max(widths[-1], self._itemWidth(item))
			row += 1
		widths = [max(w, 4) for w in widths]
		return cells, widths

	def _menuWidth(self) -> int:
		"""Return total menu width including borders."""
		return sum(self._layout()[1]) + 2*self._border()

	def _menuHeight(self) -> int:
		"""Return total menu height including borders."""
		rows = max((r+1 for _, r, _ in self._layout()[0]), default=0)
		return rows + 2*self._border()

	def _itemAt(self, cx, cy) -> int:
		"""Index of the item at screen cell (cx, cy), -1 if none.
		cx=None matches any column (tkinter '@y' form on one column)."""
		px, py, _, _ = self._screenRect()
		bd        = self._border()
		cells, cw = self._layout()
		for i, (x, row, c) in enumerate(cells):
			if row != cy - py - bd:
				continue
			if cx is None or x <= cx - px - bd < x + cw[c]:
				return i
		return -1

	def _screenRect(self):
		"""Return (x, y, w, h) where the menu is drawn (clamped to screen)."""
		mw  = self._menuWidth()
		mh  = self._menuHeight()
		px  = self._postX
		py  = self._postY
		app = self._getApp()
		if app is not None:
			if px + mw > app._width:
				px = max(0, app._width - mw)
			if py + mh > app._height:
				py = max(0, app._height - mh)
		return px, py, mw, mh

	# ------------------------------------------------------------------
	# Index resolution
	# ------------------------------------------------------------------

	def _resolveIndex(self, idx: object) -> int:
		if idx in ('end', 'last'):
			return len(self._menuItems) - 1
		if idx == 'active':
			return self._active
		if idx in ('none', None, ''):
			return -1
		if isinstance(idx, int):
			return idx if idx >= 0 else -1
		if isinstance(idx, str):
			if idx.isdigit():
				return int(idx)
			if idx.startswith('@'):
				try:
					xy = [int(float(v)) for v in idx[1:].split(',')]
				except ValueError:
					return -1
				px, py, _, _ = self._screenRect()
				if len(xy) == 1:
					return self._itemAt(None, py + _cellY(xy[0]))
				return self._itemAt(px + _cellX(xy[0]), py + _cellY(xy[1]))
			for i, item in enumerate(self._menuItems):
				if item.get('label') == idx:
					return i
			# tkinter also accepts a glob-style pattern; use prefix match
			for i, item in enumerate(self._menuItems):
				if str(item.get('label', '')).startswith(idx):
					return i
		return -1

	# ------------------------------------------------------------------
	# Navigation helpers
	# ------------------------------------------------------------------

	def _selectable(self, i) -> bool:
		if not (0 <= i < len(self._menuItems)):
			return False
		item = self._menuItems[i]
		return item['type'] != 'separator' and item.get('state', 'normal') != 'disabled'

	def _firstSelectable(self) -> int:
		for i in range(len(self._menuItems)):
			if self._selectable(i):
				return i
		return -1

	def _step(self, current: int, delta: int) -> int:
		n = len(self._menuItems)
		if n == 0:
			return -1
		i = current
		for _ in range(n):
			i = (i + delta) % n
			if self._selectable(i):
				return i
		return current

	def _stepColumn(self, current: int, delta: int) -> int:
		"""Selectable item of the next column (delta=±1) nearest to the row
		of *current*; -1 when there is no such column."""
		cells, cw = self._layout()
		if not (0 <= current < len(cells)):
			return -1
		_, row, c = cells[current]
		c += delta
		while 0 <= c < len(cw):
			best = [i for i, (_, _, ci) in enumerate(cells)
				if ci == c and self._selectable(i)]
			if best:
				return min(best, key=lambda i: (abs(cells[i][1]-row), cells[i][1]))
			c += delta
		return -1

	def _nextSelectable(self, current: int) -> int:
		return self._step(current, +1)

	def _prevSelectable(self, current: int) -> int:
		return self._step(current, -1)

	def _closeAll(self):
		"""Close this menu, its ancestors and every other posted menu."""
		m = self
		while m is not None:
			m.unpost()
			m = m._parentMenu
		app = self._getApp()
		if app is not None and hasattr(app, '_closeMenus'):
			app._closeMenus()

	def _inMenuBarChain(self) -> bool:
		m = self
		while m is not None:
			if m._fromMenuBar:
				return True
			m = m._parentMenu
		return False

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._posted:
			return

		px, py, mw, mh = self._screenRect()
		bd        = self._border()
		attr      = self._getAttr()
		cells, cw = self._layout()

		_fillRect(scr, py, px, mh, mw, attr=attr)
		if bd > 0:
			relief = self._opts.get('relief', 'single')
			_drawBorder(scr, py, px, mh, mw,
				relief if relief in ('single', 'double') else 'single', attr)

		actA = self._focusAttr()

		for i, item in enumerate(self._menuItems):
			x, row, c = cells[i]
			iy     = py + bd + row
			ix     = px + bd + x
			innerW = cw[c]
			itype  = item['type']

			if itype == 'separator':
				_addStr(scr, iy, ix, '─' * innerW, attr)
				continue

			if item.get('state', 'normal') == 'disabled':
				rowAttr = self._disabledAttr()
			elif i == self._active:
				rowAttr = actA
			else:
				rowAttr = attr

			label = ' ' + str(item.get('label', ''))
			accel = str(item.get('accelerator', '') or '')

			if itype == 'checkbutton':
				v       = item.get('variable')
				checked = v is not None and _sameValue(v.get(), item.get('onvalue', 1))
				label   = ' ' + ('[X] ' if checked else '[ ] ') + label[1:]
			elif itype == 'radiobutton':
				v      = item.get('variable')
				sel    = v is not None and _sameValue(v.get(), item.get('value'))
				label  = ' ' + ('(*) ' if sel else '( ) ') + label[1:]

			right = (accel + ' ') if accel else ''
			if itype == 'cascade':
				right += '▶'
			gap = max(1, innerW - len(label) - len(right))
			row = label + ' ' * gap + right if right else label

			_addStr(scr, iy, ix, _pad(row, innerW, 'left'), rowAttr)

			ul = item.get('underline', -1)
			if isinstance(ul, int) and 0 <= ul < len(str(item.get('label', ''))):
				off = 1 + (4 if itype in ('checkbutton', 'radiobutton') else 0) + ul
				if off < innerW:
					_addStr(scr, iy, ix + off, row[off], rowAttr | curses.A_UNDERLINE)

	# ------------------------------------------------------------------
	# Key input — a posted menu grabs the keyboard
	# ------------------------------------------------------------------

	def _handleKey(self, key: int) -> bool:
		if not self._posted:
			return False
		app = self._getApp()

		if key in (KEY_UP, KEY_DOWN):
			self._active = self._step(self._active, -1 if key == KEY_UP else 1)
		elif key == KEY_HOME:
			self._active = self._firstSelectable()
		elif key == KEY_END:
			self._active = self._step(len(self._menuItems), -1)
		elif key in (KEY_ENTER, KEY_CR, KEY_SPACE):
			if self._selectable(self._active):
				self.invoke(self._active)
		elif key == KEY_RIGHT:
			if self._selectable(self._active) and \
					self._menuItems[self._active]['type'] == 'cascade':
				self._openCascade(self._active)
			elif (i := self._stepColumn(self._active, +1)) >= 0:
				self._active = i
			elif self._inMenuBarChain() and app is not None:
				app._menuBarStep(+1)
		elif key == KEY_LEFT:
			parent = self._parentMenu
			if (i := self._stepColumn(self._active, -1)) >= 0:
				self._active = i
			elif parent is not None and parent._posted:
				self.unpost()
			elif self._fromMenuBar and app is not None:
				app._menuBarStep(-1)
			else:
				self.unpost()
		elif key == KEY_ESC:
			parent = self._parentMenu
			if parent is not None and parent._posted:
				self.unpost()
			elif app is not None and hasattr(app, '_closeMenus'):
				app._closeMenus()
			else:
				self.unpost()
		elif isinstance(key, int) and 32 < key < 127:
			self._selectByLetter(chr(key).lower())
		self._markDirty()
		return True

	def _selectByLetter(self, ch):
		"""Activate the item whose underlined (or first) letter is *ch*."""
		matches = []
		for i, item in enumerate(self._menuItems):
			if not self._selectable(i):
				continue
			label = str(item.get('label', ''))
			ul    = item.get('underline', -1)
			if isinstance(ul, int) and 0 <= ul < len(label):
				letter = label[ul].lower()
			else:
				letter = label[:1].lower()
			if letter == ch:
				matches.append(i)
		if len(matches) == 1:
			self.invoke(matches[0])
		elif matches:
			after = [i for i in matches if i > self._active]
			self._active = after[0] if after else matches[0]

	# ------------------------------------------------------------------
	# Mouse input
	# ------------------------------------------------------------------

	def _handleMouse(self, mx: int, my: int, bstate: int):
		wheel = isWheel(bstate)
		if wheel:
			self._active = self._step(self._active, wheel)
			self._markDirty()
			return True

		row = self._itemAt(mx, my)
		if row < 0:
			return True
		if self._selectable(row):
			self._active = row
		self._markDirty()

		item	= self._menuItems[row]
		press	= bool(bstate & B1_PRESS) and not (bstate & MOTION)
		release	= bool(bstate & (B1_RELEASE | B1_CLICK | B1_DCLICK))
		if not self._selectable(row):
			return True
		if item['type'] == 'cascade':
			sub = item.get('menu')
			if press or release or (bstate & MOTION and sub is not None
					and not sub._posted):
				self._openCascade(row)
		elif release:
			self.invoke(row)
		return True


# ---------------------------------------------------------------------------
# OptionMenu
# ---------------------------------------------------------------------------

class OptionMenu(Widget):
	"""Option-menu (drop-down choice) widget.  Mirrors tkinter.OptionMenu."""

	def __init__(self, parent=None, variable=None, value=None, *values, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'activeforeground':	'',
			'activebackground':	'',
			'disabledforeground':	'',
			'command':		None,
		})
		kwargs.setdefault('relief', 'raised')
		kwargs.setdefault('borderwidth', 1)
		self._variable = variable
		self._menu     = Menu(parent)
		if kwargs:
			OptionMenu.configure(self, **kwargs)

		if value is not None:
			for v in [value] + list(values):
				self._menu.add_command(label=str(v), command=self._makeSetter(v))

		# Set default if variable is empty
		if variable is not None and hasattr(variable, 'get') and value is not None:
			try:
				cur = variable.get()
			except (TypeError, ValueError):
				cur = None
			if cur in (None, ''):
				variable.set(value)

	def _makeSetter(self, v):
		def _set():
			if self._variable is not None:
				self._variable.set(v)
			cmd = self._opts.get('command')
			if callable(cmd):
				cmd(v)
			self._markDirty()
		return _set

	@property
	def menu(self):
		return self._menu

	def cget(self, key):
		if key == 'menu':
			return self._menu
		return super().cget(key)

	def __getitem__(self, key):
		return self.cget(key)

	@property
	def _values(self):
		return [str(it.get('label', '')) for it in self._menu._menuItems
			if it['type'] != 'separator']

	# ------------------------------------------------------------------

	def _getCurrentLabel(self) -> str:
		if self._variable is not None and hasattr(self._variable, 'get'):
			return str(self._variable.get())
		return ''

	def _preferredSize(self):
		bd   = self._cfgBorder()
		padx = int(self._opts.get('padx') or 0)
		pady = int(self._opts.get('pady') or 0)
		labels = self._values + [self._getCurrentLabel()]
		maxLabelW = max((len(v) for v in labels), default=4)
		ow = int(self._opts.get('width') or 0)
		w = max(ow, maxLabelW) + 2*bd + 2*padx + 2	# 2 for ' ▼'
		h = 1 + 2*bd + 2*pady
		return (max(w, 6), max(h, 1))

	def render(self, scr):
		if not self._isMapped():
			return

		state   = self._opts.get('state', 'normal')
		bd      = self._border()
		relief  = self._opts.get('relief', 'raised')

		if state == 'disabled':
			attr = self._disabledAttr()
		elif self._focused:
			attr = self._focusAttr()
		else:
			attr = self._getAttr()

		_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)
		if bd > 0:
			_drawBorder(scr, self._y, self._x, self._height, self._width, relief,
				self._borderAttr(attr))

		cw    = max(1, self._width - 2*bd)
		label = _pad(self._getCurrentLabel(), max(0, cw - 2)) + ' ▼'
		cy    = self._y + bd + (self._height - 2*bd - 1) // 2
		_addStr(scr, cy, self._x + bd, _pad(label, cw, 'left'), attr)

	# ------------------------------------------------------------------
	# Focus / input
	# ------------------------------------------------------------------

	def _isFocusable(self) -> bool:
		return self._opts.get('state', 'normal') == 'normal'

	def _openMenu(self):
		app   = self._getApp()
		menuH = self._menu._menuHeight()
		openY = self._y + self._height
		if app is not None and openY + menuH > app._height:
			openY = max(0, self._y - menuH)
		cur = self._getCurrentLabel()
		for i, it in enumerate(self._menu._menuItems):
			if str(it.get('label', '')) == cur:
				self._menu._active = i
		self._menu._post(self._x, openY)
		self._markDirty()

	def _stepValue(self, delta: int):
		"""Cycle through values without opening menu."""
		items = [it for it in self._menu._menuItems
			if it['type'] != 'separator' and it.get('state') != 'disabled']
		if not items:
			return
		labels = [str(it.get('label', '')) for it in items]
		cur    = self._getCurrentLabel()
		idx    = labels.index(cur) if cur in labels else -delta
		idx    = (idx + delta) % len(items)
		cmd    = items[idx].get('command')
		if callable(cmd):
			cmd()
		elif self._variable is not None:
			self._variable.set(labels[idx])
		self._markDirty()

	def _handleKey(self, key: int) -> bool:
		if self._opts.get('state') == 'disabled':
			return False
		if key in (KEY_ENTER, KEY_CR, KEY_SPACE):
			self._openMenu()
			return True
		if key == KEY_UP:
			self._stepValue(-1)
			return True
		if key == KEY_DOWN:
			self._stepValue(1)
			return True
		return False

	def _handleMouse(self, mx: int, my: int, bstate: int) -> bool:
		if self._opts.get('state') == 'disabled':
			return False
		if bstate & (B1_PRESS | B1_CLICK) and not (bstate & MOTION):
			if not self._menu._posted:
				self._openMenu()
			return True
		return False
