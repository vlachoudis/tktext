import curses
from ._events import KeyEvent, MouseEvent


# ---------------------------------------------------------------------------
# Low-level curses drawing helpers
# ---------------------------------------------------------------------------

def _addStr(scr, y, x, s, attr=0):
	try:
		scr.addstr(y, x, s, attr)
	except curses.error:
		pass


def _addCh(scr, y, x, ch, attr=0):
	try:
		scr.addch(y, x, ch, attr)
	except curses.error:
		pass


def _fillRect(scr, y, x, h, w, ch=' ', attr=0):
	if w <= 0 or h <= 0:
		return
	row = ch * w
	for i in range(h):
		_addStr(scr, y + i, x, row, attr)


# tl, tr, bl, br, hz, vt
_BORDER_CHARS = {
	'single':	('┌', '┐', '└', '┘', '─', '│'),
	'double':	('╔', '╗', '╚', '╝', '═', '║'),
}
_BORDER_ASCII	= ('+', '+', '+', '+', '-', '|')


def _drawBorder(scr, y, x, h, w, relief='solid', attr=0):
	"""Draw a border inside the given rectangle.

	relief values that select Unicode line art: 'single', 'double'.
	All other non-flat values use ASCII +/-/|.
	"""
	if h < 1 or w < 1:
		return
	_, sw = scr.getmaxyx()
	tl, tr, bl, br, hz, vt = _BORDER_CHARS.get(relief, _BORDER_ASCII)
	# top
	_addStr(scr, y, x, tl + hz * max(0, w - 2) + tr, attr)
	# sides
	for i in range(1, h - 1):
		_addCh(scr, y + i, x, vt, attr)
		if x + w - 1 < sw:
			_addCh(scr, y + i, x + w - 1, vt, attr)
	# bottom
	if h > 1:
		_addStr(scr, y + h - 1, x, bl + hz * max(0, w - 2) + br, attr)


def _clip(s, width):
	"""Clip string to width characters."""
	if len(s) > width:
		return s[:width]
	return s


def _pad(s, width, align='left'):
	"""Pad or clip string to exactly width characters."""
	s = _clip(s, width)
	if align == 'left':
		return s.ljust(width)
	elif align == 'right':
		return s.rjust(width)
	else:
		return s.center(width)


# ---------------------------------------------------------------------------
# Widget base class
# ---------------------------------------------------------------------------

class Widget:
	"""Base class for all tktext widgets."""

	_isRoot = False

	def __init__(self, parent=None, **kwargs):
		self._parent	= parent
		self._children	= []
		self._opts	= {
			'width':	0,
			'height':	0,
			'bg':		'',
			'fg':		'',
			'relief':	'flat',
			'borderwidth':	0,
			'bd':		0,
			'padx':		0,
			'pady':		0,
			'state':	'normal',
			'takefocus':	True,
			'cursor':	'',
		}
		# Absolute screen geometry (set by layout managers)
		self._x = 0
		self._y = 0
		self._w = 0
		self._h = 0
		# Geometry manager info
		self._geoManager	= None
		self._geoInfo		= {}
		# Event bindings: event_str -> [callable, ...]
		self._bindings = {}
		self._focused = False

		if parent is not None:
			parent._addChild(self)

		if kwargs:
			self.configure(**kwargs)

	# ------------------------------------------------------------------
	# Child management
	# ------------------------------------------------------------------

	def _addChild(self, child):
		self._children.append(child)

	# ------------------------------------------------------------------
	# Configuration
	# ------------------------------------------------------------------

	def configure(self, cnf=None, **kwargs):
		"""Set widget options.  Mirrors tkinter's configure/config."""
		if cnf:
			kwargs.update(cnf)
		if 'bd' in kwargs:
			kwargs['borderwidth'] = kwargs.pop('bd')
		self._opts.update(kwargs)
		return self

	config = configure

	def cget(self, key):
		"""Return the current value of option *key*."""
		return self._opts.get(key)

	def keys(self):
		return list(self._opts.keys())

	def __setitem__(self, key, value):
		self.configure(**{key: value})

	def __getitem__(self, key):
		return self.cget(key)

	# ------------------------------------------------------------------
	# Event binding
	# ------------------------------------------------------------------

	def bind(self, event, callback=None, add=None):
		"""Bind *event* string to *callback*.

		If *add* is truthy the callback is appended; otherwise it replaces
		any existing binding for that event string.
		"""
		if callback is None:
			return list(self._bindings.get(event, []))
		if not add or event not in self._bindings:
			self._bindings[event] = []
		self._bindings[event].append(callback)

	def unbind(self, event, funcid=None):
		self._bindings.pop(event, None)

	def _dispatch(self, evtStr, evtObj):
		"""Call all handlers registered for *evtStr*.  Return 'break' to stop."""
		for h in self._bindings.get(evtStr, []):
			if h(evtObj) == 'break':
				return 'break'
		return None

	# ------------------------------------------------------------------
	# Geometry managers
	# ------------------------------------------------------------------

	def pack(self, **kwargs):
		"""Register widget with the pack geometry manager."""
		opts = {
			'side': 'top', 'fill': 'none', 'expand': False,
			'padx': 0, 'pady': 0, 'ipadx': 0, 'ipady': 0,
			'anchor': 'center',
		}
		opts.update(kwargs)
		self._geoManager = 'pack'
		self._geoInfo = opts
		if self._parent is not None:
			self._parent._markDirty()

	def packConfigure(self, **kwargs):
		if self._geoManager == 'pack':
			self._geoInfo.update(kwargs)
			if self._parent is not None:
				self._parent._markDirty()

	def packForget(self):
		self._geoManager = None
		self._geoInfo = {}
		if self._parent is not None:
			self._parent._markDirty()

	def packInfo(self):
		return dict(self._geoInfo) if self._geoManager == 'pack' else {}

	def grid(self, **kwargs):
		"""Register widget with the grid geometry manager."""
		opts = {
			'row': 0, 'column': 0, 'rowspan': 1, 'columnspan': 1,
			'sticky': '', 'padx': 0, 'pady': 0, 'ipadx': 0, 'ipady': 0,
		}
		opts.update(kwargs)
		self._geoManager = 'grid'
		self._geoInfo = opts
		if self._parent is not None:
			self._parent._markDirty()

	def gridConfigure(self, **kwargs):
		if self._geoManager == 'grid':
			self._geoInfo.update(kwargs)
			if self._parent is not None:
				self._parent._markDirty()

	def gridForget(self):
		self._geoManager = None
		self._geoInfo = {}
		if self._parent is not None:
			self._parent._markDirty()

	def gridInfo(self):
		return dict(self._geoInfo) if self._geoManager == 'grid' else {}

	def place(self, **kwargs):
		"""Register widget with the place geometry manager."""
		opts = {
			'x': 0, 'y': 0, 'width': None, 'height': None,
			'relx': 0.0, 'rely': 0.0, 'relwidth': None, 'relheight': None,
			'anchor': 'nw',
		}
		opts.update(kwargs)
		self._geoManager = 'place'
		self._geoInfo = opts
		if self._parent is not None:
			self._parent._markDirty()

	def placeForget(self):
		self._geoManager = None
		self._geoInfo = {}
		if self._parent is not None:
			self._parent._markDirty()

	def placeInfo(self):
		return dict(self._geoInfo) if self._geoManager == 'place' else {}

	# ------------------------------------------------------------------
	# Focus
	# ------------------------------------------------------------------

	def focus(self):
		"""Give keyboard focus to this widget."""
		app = self._getApp()
		if app:
			app._setFocus(self)

	def focusSet(self):
		self.focus()

	def focusForce(self):
		self.focus()

	def focusGet(self):
		app = self._getApp()
		return app._focusWidget if app else None

	# ------------------------------------------------------------------
	# Geometry inquiry
	# ------------------------------------------------------------------

	def winfoWidth(self):	return self._w
	def winfoHeight(self):	return self._h
	def winfoX(self):	return self._x
	def winfoY(self):	return self._y
	def winfoRootx(self):	return self._x
	def winfoRooty(self):	return self._y
	def winfoIsmapped(self):return self._geoManager is not None
	def winfoChildren(self):return list(self._children)
	def winfoParent(self):	return self._parent

	def winfoScreenwidth(self):
		app = self._getApp()
		return app._w if app else 80

	def winfoScreenheight(self):
		app = self._getApp()
		return app._h if app else 24

	# Provide snake_case aliases for compatibility
	winfo_width		= winfoWidth
	winfo_height		= winfoHeight
	winfo_x			= winfoX
	winfo_y			= winfoY
	winfo_rootx		= winfoRootx
	winfo_rooty		= winfoRooty
	winfo_ismapped		= winfoIsmapped
	winfo_children		= winfoChildren
	winfo_parent		= winfoParent
	winfo_screenwidth	= winfoScreenwidth
	winfo_screenheight	= winfoScreenheight

	# ------------------------------------------------------------------
	# Lifetime
	# ------------------------------------------------------------------

	def destroy(self):
		for child in list(self._children):
			child.destroy()
		self._children.clear()
		if self._parent and self in self._parent._children:
			self._parent._children.remove(self)
		self._parent = None

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _getApp(self):
		w = self
		while w is not None:
			if w._isRoot:
				return w
			w = w._parent
		return None

	def _preferredSize(self):
		"""Return (w, h) minimum size in terminal characters."""
		w = int(self._opts.get('width') or 0)
		h = int(self._opts.get('height') or 0)
		bd = int(self._opts.get('borderwidth') or 0)
		return (max(w, 1) + 2 * bd, max(h, 1) + 2 * bd)

	def _markDirty(self):
		app = self._getApp()
		if app:
			app._dirty = True

	def _doLayout(self, x, y, w, h):
		self._x = x
		self._y = y
		self._w = w
		self._h = h

	def _getAttr(self, fg=None, bg=None, **kw):
		app = self._getApp()
		if app is None:
			return 0
		f = fg if fg is not None else (self._opts.get('fg') or '')
		b = bg if bg is not None else (self._opts.get('bg') or '')
		return app._colors.getAttr(f, b, **kw)

	def _isFocusable(self):
		return (self._opts.get('takefocus', True) is True and
			self._opts.get('state', 'normal') == 'normal')

	def _getAllFocusable(self):
		result = []
		if self._isFocusable():
			result.append(self)
		for c in self._children:
			result.extend(c._getAllFocusable())
		return result

	def _hitTest(self, mx, my):
		return (self._x <= mx < self._x + self._w and
			self._y <= my < self._y + self._h)

	def _findAt(self, mx, my):
		"""Return deepest widget at screen position (mx, my)."""
		if not self._hitTest(mx, my):
			return None
		for child in reversed(self._children):
			hit = child._findAt(mx, my)
			if hit:
				return hit
		return self

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		"""Draw this widget onto *scr*.  Override in subclasses."""
		pass

	def _renderChildren(self, scr):
		for child in self._children:
			if child._geoManager is not None and child._w > 0 and child._h > 0:
				child.render(scr)

	# ------------------------------------------------------------------
	# Input dispatch
	# ------------------------------------------------------------------

	def _handleKey(self, key):
		"""Handle raw curses key.  Return True if consumed."""
		evt = KeyEvent(key)
		evt.widget = self
		if self._dispatch(f'<{evt.keysym}>', evt) == 'break':
			return True
		return self._dispatch('<Key>', evt) == 'break'

	def _handleMouse(self, mx, my, bstate):
		"""Handle a mouse event.  Return True if consumed."""
		evt = MouseEvent(mx, my, bstate)
		evt.widget = self
		if bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED |
				curses.BUTTON1_RELEASED):
			if self._dispatch('<Button-1>', evt) == 'break':
				return True
			self._dispatch('<ButtonRelease-1>', evt)
		if bstate & curses.BUTTON3_CLICKED:
			self._dispatch('<Button-3>', evt)
		return False
