import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad
from ._events import (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_ENTER, KEY_CR, KEY_ESC)


class Menu(Widget):
	"""Popup / menubar menu widget.  Mirrors tkinter.Menu.

	Not laid out via pack/grid/place — overlays the screen when posted.
	"""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'activeforeground':	'',
			'activebackground':	'',
			'disabledforeground':	'gray',
			'tearoff':		0,
		})
		kwargs.setdefault('relief', 'solid')
		kwargs.setdefault('borderwidth', 1)
		if kwargs:
			self.configure(**kwargs)

		self._items       = []	# list of item dicts
		self._active      = -1	# highlighted row index
		self._posted      = False
		self._postX       = 0
		self._postY       = 0
		self._parentMenu  = None	# set when used as cascade submenu

	# ------------------------------------------------------------------
	# Focus override — menus don't participate in tab focus
	# ------------------------------------------------------------------

	def _isFocusable(self) -> bool:
		return False

	# ------------------------------------------------------------------
	# Item addition
	# ------------------------------------------------------------------

	def add(self, itemType: str, **kwargs):
		"""Add an item of *itemType* ('command', 'separator', etc.)."""
		item = {
			'type':		itemType,
			'label':	kwargs.get('label', ''),
			'command':	kwargs.get('command', None),
			'state':	kwargs.get('state', 'normal'),
			'accelerator':	kwargs.get('accelerator', ''),
			'underline':	kwargs.get('underline', -1),
			'menu':		kwargs.get('menu', None),
			'variable':	kwargs.get('variable', None),
			'value':	kwargs.get('value', ''),
			'onvalue':	kwargs.get('onvalue', 1),
			'offvalue':	kwargs.get('offvalue', 0),
		}
		self._items.append(item)
		self._markDirty()

	def add_command(self, **kwargs):
		self.add('command', **kwargs)

	def add_separator(self, **kwargs):
		self.add('separator', **kwargs)

	def add_cascade(self, **kwargs):
		if 'menu' in kwargs and kwargs['menu'] is not None:
			kwargs['menu']._parentMenu = self
		self.add('cascade', **kwargs)

	def add_checkbutton(self, **kwargs):
		self.add('checkbutton', **kwargs)

	def add_radiobutton(self, **kwargs):
		self.add('radiobutton', **kwargs)

	# camelCase aliases
	addCommand    = add_command
	addSeparator  = add_separator
	addCascade    = add_cascade
	addCheckbutton = add_checkbutton
	addRadiobutton = add_radiobutton

	# ------------------------------------------------------------------
	# Item modification / query
	# ------------------------------------------------------------------

	def delete(self, index1: object, index2: object = None):
		"""Delete items from index1 to index2 (inclusive)."""
		i1 = self._resolveIndex(index1)
		if i1 < 0 or i1 >= len(self._items):
			return
		if index2 is None:
			del self._items[i1]
		else:
			i2 = self._resolveIndex(index2)
			i2 = min(i2, len(self._items) - 1)
			del self._items[i1:i2+1]
		self._markDirty()

	def insert(self, idx: object, itemType: str, **kwargs):
		"""Insert a new item before position *idx*."""
		i = self._resolveIndex(idx)
		item = {
			'type':		itemType,
			'label':	kwargs.get('label', ''),
			'command':	kwargs.get('command', None),
			'state':	kwargs.get('state', 'normal'),
			'accelerator':	kwargs.get('accelerator', ''),
			'underline':	kwargs.get('underline', -1),
			'menu':		kwargs.get('menu', None),
			'variable':	kwargs.get('variable', None),
			'value':	kwargs.get('value', ''),
			'onvalue':	kwargs.get('onvalue', 1),
			'offvalue':	kwargs.get('offvalue', 0),
		}
		self._items.insert(max(0, i), item)
		self._markDirty()

	def entryconfig(self, index: object, **kwargs):
		"""Configure item at *index*."""
		i = self._resolveIndex(index)
		if 0 <= i < len(self._items):
			self._items[i].update(kwargs)
			self._markDirty()

	entryconfigure = entryconfig
	entry_config   = entryconfig

	def entrycget(self, index: object, option: str):
		"""Return value of *option* for item at *index*."""
		i = self._resolveIndex(index)
		if 0 <= i < len(self._items):
			return self._items[i].get(option)
		return None

	def index(self, idx: object) -> int:
		"""Return integer index for *idx*."""
		return self._resolveIndex(idx)

	def type(self, idx: object) -> str:
		"""Return type string for item at *idx*."""
		i = self._resolveIndex(idx)
		if 0 <= i < len(self._items):
			return self._items[i]['type']
		return ''

	# ------------------------------------------------------------------
	# Post / unpost
	# ------------------------------------------------------------------

	def post(self, x: int, y: int):
		"""Display menu at screen position (x, y)."""
		self._postX  = x
		self._postY  = y
		self._posted = True
		self._active = self._firstSelectable()
		app = self._getApp()
		if app is not None and hasattr(app, '_postedMenus'):
			if self not in app._postedMenus:
				app._postedMenus.append(self)
		self._markDirty()

	def unpost(self):
		"""Hide this menu (and any open submenus)."""
		# Close any open cascades first
		for item in self._items:
			sub = item.get('menu')
			if sub is not None and sub._posted:
				sub.unpost()
		self._posted = False
		app = self._getApp()
		if app is not None and hasattr(app, '_postedMenus'):
			if self in app._postedMenus:
				app._postedMenus.remove(self)
		self._markDirty()

	def tk_popup(self, x: int, y: int, entry: int = 0):
		"""Post menu at (x, y). Mirrors tkinter.Menu.tk_popup."""
		self.post(x, y)

	def invoke(self, idx: object):
		"""Invoke the item at *idx*."""
		i = self._resolveIndex(idx)
		if not (0 <= i < len(self._items)):
			return
		item  = self._items[i]
		itype = item['type']
		state = item.get('state', 'normal')
		if state == 'disabled':
			return

		if itype == 'cascade':
			sub = item.get('menu')
			if sub is not None:
				# compute position of submenu (to the right of this menu)
				mw = self._menuWidth()
				mh = self._menuHeight()
				px = self._postX
				py = self._postY
				app = self._getApp()
				if app is not None:
					if px + mw > app._w:
						px = max(0, app._w - mw)
					if py + mh > app._h:
						py = max(0, app._h - mh)
				subX = px + mw
				subY = py + 1 + i	# border + item offset
				sub.post(subX, subY)
		elif itype == 'checkbutton':
			v        = item.get('variable')
			onvalue  = item.get('onvalue', 1)
			offvalue = item.get('offvalue', 0)
			if v is not None:
				if v.get() == onvalue:
					v.set(offvalue)
				else:
					v.set(onvalue)
			self._closeAll()
			cmd = item.get('command')
			if callable(cmd):
				cmd()
		elif itype == 'radiobutton':
			v     = item.get('variable')
			value = item.get('value', '')
			if v is not None:
				v.set(value)
			self._closeAll()
			cmd = item.get('command')
			if callable(cmd):
				cmd()
		else:
			# command
			cmd = item.get('command')
			self._closeAll()
			if callable(cmd):
				cmd()

	# ------------------------------------------------------------------
	# Geometry helpers
	# ------------------------------------------------------------------

	def _menuWidth(self) -> int:
		"""Return total menu width including borders."""
		bd  = int(self._opts.get('borderwidth') or 0)
		maxW = 0
		for item in self._items:
			if item['type'] == 'separator':
				continue
			label = item.get('label', '')
			accel = item.get('accelerator', '')
			itype = item['type']
			prefix = 0
			if itype in ('checkbutton', 'radiobutton'):
				prefix = 4
			suffix = 3 if itype == 'cascade' else 0	# ' ▶'
			accelW = len(accel) + 1 if accel else 0
			w = prefix + len(label) + accelW + 2 + suffix
			maxW = max(maxW, w)
		return max(maxW, 4) + 2*bd

	def _menuHeight(self) -> int:
		"""Return total menu height including borders."""
		bd = int(self._opts.get('borderwidth') or 0)
		return len(self._items) + 2*bd

	# ------------------------------------------------------------------
	# Index resolution
	# ------------------------------------------------------------------

	def _resolveIndex(self, idx: object) -> int:
		if idx in ('end', 'last'):
			return len(self._items) - 1
		if idx == 'active':
			return self._active
		if idx == 'none':
			return -1
		if isinstance(idx, int):
			return idx
		# string label match
		if isinstance(idx, str):
			for i, item in enumerate(self._items):
				if item.get('label') == idx:
					return i
		return -1

	# ------------------------------------------------------------------
	# Navigation helpers
	# ------------------------------------------------------------------

	def _firstSelectable(self) -> int:
		for i, item in enumerate(self._items):
			if item['type'] != 'separator' and item.get('state', 'normal') != 'disabled':
				return i
		return -1

	def _nextSelectable(self, current: int) -> int:
		n = len(self._items)
		if n == 0:
			return -1
		i = (current + 1) % n
		start = i
		while True:
			item = self._items[i]
			if item['type'] != 'separator' and item.get('state', 'normal') != 'disabled':
				return i
			i = (i + 1) % n
			if i == start:
				return current

	def _prevSelectable(self, current: int) -> int:
		n = len(self._items)
		if n == 0:
			return -1
		i = (current - 1) % n
		start = i
		while True:
			item = self._items[i]
			if item['type'] != 'separator' and item.get('state', 'normal') != 'disabled':
				return i
			i = (i - 1) % n
			if i == start:
				return current

	def _closeAll(self):
		"""Close this menu and all ancestors."""
		m = self
		while m is not None:
			m.unpost()
			m = m._parentMenu

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._posted:
			return
		if self._w < 0 or self._h < 0:
			return

		app = self._getApp()
		mw  = self._menuWidth()
		mh  = self._menuHeight()
		bd  = int(self._opts.get('borderwidth') or 0)
		px  = self._postX
		py  = self._postY

		# Clamp to screen
		if app is not None:
			if px + mw > app._w:
				px = max(0, app._w - mw)
			if py + mh > app._h:
				py = max(0, app._h - mh)

		innerW = max(1, mw - 2*bd)
		attr   = self._getAttr()

		_fillRect(scr, py, px, mh, mw, attr=attr)
		if bd > 0:
			_drawBorder(scr, py, px, mh, mw, 'single', attr)

		afg = self._opts.get('activeforeground') or ''
		abg = self._opts.get('activebackground') or ''

		for i, item in enumerate(self._items):
			iy    = py + bd + i
			ix    = px + bd
			itype = item['type']
			state = item.get('state', 'normal')

			if itype == 'separator':
				_addStr(scr, iy, ix, '─' * innerW, attr)
				continue

			active  = (i == self._active)
			disabled = (state == 'disabled')

			if disabled:
				rowAttr = self._getAttr(fg=self._opts.get('disabledforeground') or 'gray')
			elif active:
				rowAttr = self._getAttr(fg=afg, bg=abg, reverse=not (afg or abg))
			else:
				rowAttr = attr

			# Build label string
			label = item.get('label', '')
			accel = item.get('accelerator', '')

			if itype == 'checkbutton':
				v = item.get('variable')
				onvalue = item.get('onvalue', 1)
				checked = (v is not None and v.get() == onvalue)
				prefix  = '[X] ' if checked else '[ ] '
			elif itype == 'radiobutton':
				v     = item.get('variable')
				value = item.get('value', '')
				sel   = (v is not None and v.get() == value)
				prefix = '(*) ' if sel else '( ) '
			else:
				prefix = ''

			if itype == 'cascade':
				suffix = ' ▶'	# ' ▶'
			else:
				suffix = ''

			if accel:
				# right-pad label, right-align accelerator
				labelPart = prefix + label
				rightPart = accel + suffix
				gap       = max(1, innerW - len(labelPart) - len(rightPart))
				row       = labelPart + ' ' * gap + rightPart
			else:
				row = prefix + label + suffix

			_addStr(scr, iy, ix, _pad(row, innerW, 'left'), rowAttr)

		# Render open submenus
		for item in self._items:
			sub = item.get('menu')
			if sub is not None and sub._posted:
				sub.render(scr)

	# ------------------------------------------------------------------
	# Key input
	# ------------------------------------------------------------------

	def _handleKey(self, key: int) -> bool:
		if not self._posted:
			return False

		if key == KEY_UP:
			self._active = self._prevSelectable(self._active)
			self._markDirty()
			return True
		elif key == KEY_DOWN:
			self._active = self._nextSelectable(self._active)
			self._markDirty()
			return True
		elif key in (KEY_ENTER, KEY_CR):
			if self._active >= 0:
				self.invoke(self._active)
			self._markDirty()
			return True
		elif key == KEY_RIGHT:
			if self._active >= 0:
				item = self._items[self._active]
				if item['type'] == 'cascade' and item.get('menu'):
					self.invoke(self._active)
					self._markDirty()
					return True
		elif key in (KEY_ESC, KEY_LEFT):
			self.unpost()
			self._markDirty()
			return True
		return False

	# ------------------------------------------------------------------
	# Mouse input
	# ------------------------------------------------------------------

	def _handleMouse(self, mx: int, my: int, bstate: int):
		bd  = int(self._opts.get('borderwidth') or 0)
		app = self._getApp()
		mw  = self._menuWidth()
		mh  = self._menuHeight()
		px  = self._postX
		py  = self._postY

		if app is not None:
			if px + mw > app._w:
				px = max(0, app._w - mw)
			if py + mh > app._h:
				py = max(0, app._h - mh)

		# Map y to item index
		row = my - py - bd
		if 0 <= row < len(self._items):
			self._active = row
			self._markDirty()

			press   = bool(bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED))
			if press:
				if (0 <= row < len(self._items) and
						self._items[row]['type'] != 'separator'):
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
			'disabledforeground':	'gray',
		})
		kwargs.setdefault('relief', 'raised')
		kwargs.setdefault('borderwidth', 1)
		if kwargs:
			self.configure(**kwargs)

		# Import here to avoid circular import issues at module level
		self._variable = variable
		self._values   = []

		# Build internal menu
		self._menu = Menu(parent)

		if value is not None:
			allVals = [value] + list(values)
			for v in allVals:
				self._values.append(str(v))
				self._menu.add_command(
					label   = str(v),
					command = self._makeSetter(v),
				)

		# Set default if variable is empty
		if variable is not None and hasattr(variable, 'get'):
			if not variable.get() and value is not None:
				variable.set(value)
			elif variable.get() == '' and value is not None:
				variable.set(value)
			elif value is not None and variable._val is None:
				variable.set(value)

		self._menu._parentMenu = None

	def _makeSetter(self, v):
		def _set():
			if self._variable is not None:
				self._variable.set(v)
			self._markDirty()
		return _set

	@property
	def menu(self):
		return self._menu

	# ------------------------------------------------------------------

	def _getCurrentLabel(self) -> str:
		if self._variable is not None and hasattr(self._variable, 'get'):
			return str(self._variable.get())
		return ''

	def _preferredSize(self):
		bd   = int(self._opts.get('borderwidth') or 0)
		padx = int(self._opts.get('padx') or 0)
		pady = int(self._opts.get('pady') or 0)
		maxLabelW = max((len(v) for v in self._values), default=4)
		w = maxLabelW + 2*bd + 2*padx + 3	# 3 for ' ▼'
		h = 1 + 2*bd + 2*pady
		return (max(w, 6), max(h, 1))

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return

		state   = self._opts.get('state', 'normal')
		focused = self._focused
		bd      = int(self._opts.get('borderwidth') or 0)
		relief  = self._opts.get('relief', 'raised')

		if state == 'disabled':
			attr = self._getAttr(fg=self._opts.get('disabledforeground') or 'gray')
		elif focused:
			afg  = self._opts.get('activeforeground') or ''
			abg  = self._opts.get('activebackground') or ''
			attr = self._getAttr(fg=afg, bg=abg, reverse=not (afg or abg))
		else:
			attr = self._getAttr()

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)
		if bd > 0:
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		cw     = max(1, self._w - 2*bd)
		label  = self._getCurrentLabel() + ' ▼'	# ' ▼'
		cy     = self._y + bd
		cx     = self._x + bd
		_addStr(scr, cy, cx, _pad(label, cw, 'left'), attr)

	# ------------------------------------------------------------------
	# Focus / input
	# ------------------------------------------------------------------

	def _isFocusable(self) -> bool:
		return self._opts.get('state', 'normal') == 'normal'

	def _openMenu(self):
		app = self._getApp()
		# Prefer opening below; flip above if not enough room
		menuH = self._menu._menuHeight()
		openY = self._y + self._h
		if app is not None and openY + menuH > app._h:
			openY = max(0, self._y - menuH)
		self._menu.post(self._x, openY)
		self._markDirty()

	def _stepValue(self, delta: int):
		"""Cycle through values without opening menu."""
		if not self._values:
			return
		cur = self._getCurrentLabel()
		try:
			idx = self._values.index(cur)
		except ValueError:
			idx = 0
		idx = (idx + delta) % len(self._values)
		if self._variable is not None:
			self._variable.set(self._values[idx])
		self._markDirty()

	def _handleKey(self, key: int) -> bool:
		from ._events import KEY_UP, KEY_DOWN, KEY_SPACE
		if key in (KEY_ENTER, KEY_CR, KEY_SPACE):
			self._openMenu()
			return True
		if key == KEY_UP:
			self._stepValue(-1)
			return True
		if key == KEY_DOWN:
			self._stepValue(1)
			return True
		return super()._handleKey(key)

	def _handleMouse(self, mx: int, my: int, bstate: int) -> bool:
		if bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
			self._openMenu()
			return True
		return False
