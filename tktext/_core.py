import curses
from ._events import Event, KeyEvent, MouseEvent, B1_PRESS, B1_RELEASE, \
	B1_CLICK, B1_DCLICK, B3_ANY, MOTION, isWheel, keysymOf


class TclError(ValueError):
	"""Raised for invalid widget operations (mirrors tkinter.TclError)."""
	pass


# ---------------------------------------------------------------------------
# Low-level curses drawing helpers
#
# All helpers clip to the physical screen: curses.addstr() would otherwise
# wrap long strings onto the following line or raise on the last cell.
# ---------------------------------------------------------------------------

def _addStr(scr, y, x, s, attr=0):
	if not s:
		return
	try:
		sh, sw = scr.getmaxyx()
	except Exception:
		sh, sw = 9999, 9999
	if y < 0 or y >= sh or x >= sw:
		return
	if x < 0:
		s = s[-x:]
		x = 0
	s = s[:sw - x]
	if not s:
		return
	try:
		scr.addstr(y, x, s, attr)
	except curses.error:
		pass		# writing the bottom-right cell raises after drawing


def _addCh(scr, y, x, ch, attr=0):
	_addStr(scr, y, x, ch, attr)


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
	tl, tr, bl, br, hz, vt = _BORDER_CHARS.get(relief, _BORDER_ASCII)
	if w == 1:
		for i in range(h):
			_addStr(scr, y + i, x, vt, attr)
		return
	# top
	_addStr(scr, y, x, tl + hz * max(0, w - 2) + tr, attr)
	# sides
	for i in range(1, h - 1):
		_addStr(scr, y + i, x, vt, attr)
		_addStr(scr, y + i, x + w - 1, vt, attr)
	# bottom
	if h > 1:
		_addStr(scr, y + h - 1, x, bl + hz * max(0, w - 2) + br, attr)


def _clip(s, width):
	"""Clip string to width characters."""
	if width <= 0:
		return ''
	if len(s) > width:
		return s[:width]
	return s


def _pad(s, width, align='left'):
	"""Pad or clip string to exactly width characters."""
	if width <= 0:
		return ''
	s = _clip(s, width)
	if align == 'left':
		return s.ljust(width)
	elif align == 'right':
		return s.rjust(width)
	else:
		return s.center(width)


_ANCHOR_MAP = {
	'nw':		('left',   'top'),
	'n':		('center', 'top'),
	'ne':		('right',  'top'),
	'w':		('left',   'mid'),
	'center':	('center', 'mid'),
	'e':		('right',  'mid'),
	'sw':		('left',   'bot'),
	's':		('center', 'bot'),
	'se':		('right',  'bot'),
}


def _drawText(scr, x, y, w, h, text, anchor='center', justify='left', attr=0):
	"""Draw a (multi-line) text block inside the rectangle x,y,w,h.

	*anchor* positions the whole block, *justify* aligns the lines inside
	the block — the same semantics as tkinter's Label.
	"""
	if w <= 0 or h <= 0:
		return
	lines	= text.split('\n')
	blockW	= min(w, max(len(l) for l in lines))
	halign, valign = _ANCHOR_MAP.get(anchor or 'center', ('center', 'mid'))
	if valign == 'top':
		top = 0
	elif valign == 'bot':
		top = max(0, h - len(lines))
	else:
		top = max(0, (h - len(lines)) // 2)
	if halign == 'left':
		left = 0
	elif halign == 'right':
		left = w - blockW
	else:
		left = (w - blockW) // 2
	if justify not in ('left', 'right', 'center'):
		justify = 'left'
	for i, line in enumerate(lines):
		if top + i >= h:
			break
		_addStr(scr, y + top + i, x + left, _pad(line, blockW, justify), attr)


def _sameValue(a, b) -> bool:
	"""Compare variable values like Tcl does (string representation)."""
	if a == b:
		return True
	try:
		return str(a) == str(b)
	except Exception:
		return False


def _int(v, default=0) -> int:
	try:
		return int(v)
	except (TypeError, ValueError):
		return default


# ---------------------------------------------------------------------------
# Widget base class
# ---------------------------------------------------------------------------

class Widget:
	"""Base class for all tktext widgets."""

	_isRoot		= False
	_widgetCount	= 0

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
		# Event bindings: event_str -> [(funcid, callable), ...]
		self._bindings	= {}
		self._focused	= False
		self._destroyed	= False
		Widget._widgetCount += 1
		self._name	= f'!{type(self).__name__.lower()}{Widget._widgetCount}'

		if parent is not None:
			parent._addChild(self)

		if kwargs:
			self.configure(**kwargs)

	def __str__(self):
		names = []
		w = self
		while w is not None and not w._isRoot:
			names.append(w._name)
			w = w._parent
		return '.' + '.'.join(reversed(names)) if names else '.'

	# ------------------------------------------------------------------
	# Child management
	# ------------------------------------------------------------------

	def _addChild(self, child):
		self._children.append(child)

	# ------------------------------------------------------------------
	# Configuration
	# ------------------------------------------------------------------

	_OPTION_ALIASES = {
		'bd':			'borderwidth',
		'background':		'bg',
		'foreground':		'fg',
	}

	def configure(self, cnf=None, **kwargs):
		"""Set widget options.  Mirrors tkinter's configure/config.

		Called without arguments it returns a dict of all options.
		"""
		if cnf:
			kwargs.update(cnf)
		if not kwargs:
			return dict(self._opts)
		for alias, name in self._OPTION_ALIASES.items():
			if alias in kwargs:
				kwargs[name] = kwargs.pop(alias)
		if 'from' in kwargs:
			kwargs['from_'] = kwargs.pop('from')
		self._opts.update(kwargs)
		self._markDirty()
		return None

	config = configure

	def cget(self, key):
		"""Return the current value of option *key*."""
		key = self._OPTION_ALIASES.get(key, key)
		if key == 'from':
			key = 'from_'
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

	_funcSerial = 0

	def bind(self, event=None, callback=None, add=None):
		"""Bind *event* string to *callback*.

		If *add* is truthy the callback is appended; otherwise it replaces
		any existing binding for that event string.  Returns a funcid
		that can be passed to unbind().
		"""
		if event is None:
			return list(self._bindings.keys())
		if callback is None:
			return [f for _, f in self._bindings.get(event, [])]
		if not add or event not in self._bindings:
			self._bindings[event] = []
		Widget._funcSerial += 1
		funcid = f'{id(callback)}_{Widget._funcSerial}'
		self._bindings[event].append((funcid, callback))
		return funcid

	def unbind(self, event, funcid=None):
		if funcid is None:
			self._bindings.pop(event, None)
			return
		lst = self._bindings.get(event, [])
		self._bindings[event] = [(i, f) for i, f in lst if i != funcid]

	def bind_all(self, event=None, callback=None, add=None):
		"""Bind *event* at application level (fires for every widget)."""
		app = self._getApp()
		if app is None:
			return None
		return Widget.bind(app._allBindings, event, callback, add)

	def unbind_all(self, event):
		app = self._getApp()
		if app is not None:
			app._allBindings._bindings.pop(event, None)

	bindAll		= bind_all
	unbindAll	= unbind_all

	def _hasBinding(self, evtStr) -> bool:
		return bool(self._bindings.get(evtStr))

	def _dispatch(self, evtStr, evtObj):
		"""Call all handlers registered for *evtStr*.  Return 'break' to stop."""
		for _, h in list(self._bindings.get(evtStr, [])):
			if h(evtObj) == 'break':
				return 'break'
		return None

	def _dispatchFirst(self, patterns, evtObj):
		"""Fire only the most specific of *patterns* that is bound
		(tkinter semantics).  Return (matched, result)."""
		for p in patterns:
			if self._bindings.get(p):
				return True, self._dispatch(p, evtObj)
		return False, None

	def event_generate(self, sequence, **kw):
		"""Generate *sequence* on this widget (virtual or real event)."""
		evt		= Event()
		evt.widget	= self
		evt.type	= 'VirtualEvent' if sequence.startswith('<<') else sequence
		for k, v in kw.items():
			setattr(evt, k, v)
		if sequence.startswith('<<'):
			self._dispatch(sequence, evt)
			app = self._getApp()
			if app is not None and app._allBindings is not None:
				app._allBindings._dispatch(sequence, evt)
			return
		app = self._getApp()
		if sequence.startswith('<Key') and app is not None:
			keysym = sequence.strip('<>').split('-')[-1]
			for code in range(1, 512):
				if keysymOf(code) == keysym:
					if app._focusWidget is not self:
						app._setFocus(self)
					app._onKey(code)
					return
		self._dispatch(sequence, evt)

	eventGenerate = event_generate

	def _fireVirtual(self, name, **attrs):
		"""Fire a virtual event like '<<ListboxSelect>>' on this widget."""
		evt		= Event()
		evt.widget	= self
		evt.type	= 'VirtualEvent'
		for k, v in attrs.items():
			setattr(evt, k, v)
		return self._dispatch(name, evt)

	# ------------------------------------------------------------------
	# Geometry managers
	# ------------------------------------------------------------------

	def _setManager(self, manager, opts):
		self._geoManager	= manager
		self._geoInfo		= opts
		if self._parent is not None:
			self._parent._markDirty()
		self._markDirty()

	def _forget(self):
		self._geoManager = None
		self._geoInfo	 = {}
		self._unmapTree()
		self._markDirty()

	def _unmapTree(self):
		"""Zero the geometry of this widget and all its descendants so that
		stale rectangles never take part in hit-testing or drawing."""
		self._doLayout(0, 0, 0, 0)
		for c in self._children:
			c._unmapTree()

	def pack(self, cnf=None, **kwargs):
		"""Register widget with the pack geometry manager."""
		if cnf:
			kwargs.update(cnf)
		opts = {
			'side': 'top', 'fill': 'none', 'expand': False,
			'padx': 0, 'pady': 0, 'ipadx': 0, 'ipady': 0,
			'anchor': 'center',
		}
		if self._geoManager == 'pack':
			opts.update(self._geoInfo)
		opts.update(kwargs)
		self._setManager('pack', opts)

	def packConfigure(self, **kwargs):
		if self._geoManager == 'pack':
			self._geoInfo.update(kwargs)
			self._markDirty()
		else:
			self.pack(**kwargs)

	def packForget(self):
		self._forget()

	def packInfo(self):
		return dict(self._geoInfo) if self._geoManager == 'pack' else {}

	def grid(self, cnf=None, **kwargs):
		"""Register widget with the grid geometry manager."""
		if cnf:
			kwargs.update(cnf)
		opts = {
			'row': None, 'column': 0, 'rowspan': 1, 'columnspan': 1,
			'sticky': '', 'padx': 0, 'pady': 0, 'ipadx': 0, 'ipady': 0,
		}
		if self._geoManager == 'grid':
			opts.update(self._geoInfo)
		elif getattr(self, '_savedGridInfo', None):
			opts.update(self._savedGridInfo)
		opts.update(kwargs)
		if opts['row'] is None:
			# tkinter: the first row after the last one used in the master
			used = [c._geoInfo.get('row', 0) + c._geoInfo.get('rowspan', 1)
				for c in (self._parent._children if self._parent else [])
				if c is not self and c._geoManager == 'grid']
			opts['row'] = max(used) if used else 0
		opts['row']		= _int(opts['row'])
		opts['column']		= _int(opts['column'])
		opts['rowspan']		= max(1, _int(opts['rowspan'], 1))
		opts['columnspan']	= max(1, _int(opts['columnspan'], 1))
		self._setManager('grid', opts)

	def gridConfigure(self, **kwargs):
		if self._geoManager == 'grid':
			self._geoInfo.update(kwargs)
			self._markDirty()
		else:
			self.grid(**kwargs)

	def gridForget(self):
		self._savedGridInfo = None
		self._forget()

	def gridRemove(self):
		"""Like gridForget but remembers the grid options."""
		if self._geoManager == 'grid':
			self._savedGridInfo = dict(self._geoInfo)
		self._forget()

	def gridInfo(self):
		return dict(self._geoInfo) if self._geoManager == 'grid' else {}

	def place(self, cnf=None, **kwargs):
		"""Register widget with the place geometry manager."""
		if cnf:
			kwargs.update(cnf)
		opts = {
			'x': 0, 'y': 0, 'width': None, 'height': None,
			'relx': 0.0, 'rely': 0.0, 'relwidth': None, 'relheight': None,
			'anchor': 'nw',
		}
		if self._geoManager == 'place':
			opts.update(self._geoInfo)
		opts.update(kwargs)
		self._setManager('place', opts)

	def placeConfigure(self, **kwargs):
		if self._geoManager == 'place':
			self._geoInfo.update(kwargs)
			self._markDirty()
		else:
			self.place(**kwargs)

	def placeForget(self):
		self._forget()

	def placeInfo(self):
		return dict(self._geoInfo) if self._geoManager == 'place' else {}

	def forget(self):
		self._forget()

	# tkinter-compatible snake_case aliases
	pack_configure	= packConfigure
	pack_forget	= packForget
	pack_info	= packInfo
	grid_configure	= gridConfigure
	grid_forget	= gridForget
	grid_remove	= gridRemove
	grid_info	= gridInfo
	place_configure	= placeConfigure
	place_forget	= placeForget
	place_info	= placeInfo

	def lift(self, aboveThis=None):
		"""Raise this widget above its siblings (drawn last, hit first)."""
		p = self._parent
		if p is not None and self in p._children:
			p._children.remove(self)
			p._children.append(self)
			self._markDirty()

	def lower(self, belowThis=None):
		p = self._parent
		if p is not None and self in p._children:
			p._children.remove(self)
			p._children.insert(0, self)
			self._markDirty()

	tkraise = lift

	# ------------------------------------------------------------------
	# Focus
	# ------------------------------------------------------------------

	def focusSet(self):
		"""Give keyboard focus to this widget."""
		app = self._getApp()
		if app:
			app._setFocus(self)

	def focus(self):
		self.focusSet()

	def focusForce(self):
		self.focusSet()

	def focusGet(self):
		app = self._getApp()
		return app._focusWidget if app else None

	focus_set	= focusSet
	focus_force	= focusForce
	focus_get	= focusGet
	focus_displayof	= focusGet

	# ------------------------------------------------------------------
	# Geometry inquiry
	# ------------------------------------------------------------------

	def winfoWidth(self):	return self._w
	def winfoHeight(self):	return self._h
	def winfoX(self):	return self._x - (self._parent._x if self._parent else 0)
	def winfoY(self):	return self._y - (self._parent._y if self._parent else 0)
	def winfoRootx(self):	return self._x
	def winfoRooty(self):	return self._y
	def winfoIsmapped(self):return self._isMapped()
	def winfoViewable(self):return self._isMapped()
	def winfoChildren(self):return list(self._children)
	def winfoParent(self):	return self._parent
	def winfoExists(self):	return not self._destroyed
	def winfoReqwidth(self):return self._preferredSize()[0]
	def winfoReqheight(self):return self._preferredSize()[1]
	def winfoToplevel(self):return self._getApp()
	def winfoClass(self):	return type(self).__name__

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
	winfo_viewable		= winfoViewable
	winfo_children		= winfoChildren
	winfo_parent		= winfoParent
	winfo_exists		= winfoExists
	winfo_reqwidth		= winfoReqwidth
	winfo_reqheight		= winfoReqheight
	winfo_toplevel		= winfoToplevel
	winfo_class		= winfoClass
	winfo_screenwidth	= winfoScreenwidth
	winfo_screenheight	= winfoScreenheight

	# ------------------------------------------------------------------
	# Timers / application helpers available on every widget
	# ------------------------------------------------------------------

	def after(self, ms, func=None, *args):
		app = self._getApp()
		return app._after(ms, func, *args) if app else None

	def afterIdle(self, func, *args):
		return self.after(0, func, *args)

	def afterCancel(self, handle):
		app = self._getApp()
		if app:
			app._afterCancel(handle)

	after_idle	= afterIdle
	after_cancel	= afterCancel

	def update(self):
		app = self._getApp()
		if app:
			app._update()

	updateIdletasks		= update
	update_idletasks	= update

	def quit(self):
		app = self._getApp()
		if app:
			app._quit = True

	def mainloop(self, n=0):
		app = self._getApp()
		if app:
			app.mainloop(n)

	mainLoop = mainloop

	# ------------------------------------------------------------------
	# Lifetime
	# ------------------------------------------------------------------

	def destroy(self):
		app = self._getApp()
		for child in list(self._children):
			child.destroy()
		self._children.clear()
		if app is not None and not self._isRoot:
			if app._focusWidget is self:
				app._focusWidget = None
				app._focusLost   = True
			if app._dragWidget is self:
				app._dragWidget = None
			app._dirty = True
		if self._parent and self in self._parent._children:
			self._parent._children.remove(self)
			self._parent._childDestroyed(self)
		self._parent	= None
		self._destroyed	= True
		self._doLayout(0, 0, 0, 0)

	def _childDestroyed(self, child):
		"""Hook for containers that keep extra references to children."""
		pass

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

	def _isMapped(self) -> bool:
		return self._w > 0 and self._h > 0 and not self._destroyed

	def _cfgBorder(self) -> int:
		"""Configured border width (used for size requests)."""
		return max(0, _int(self._opts.get('borderwidth')))

	def _border(self) -> int:
		"""Border width actually drawn: a widget squeezed below its border
		size drops the border instead of drawing content over it."""
		bd = self._cfgBorder()
		if bd and self._w > 0 and self._h > 0:
			bd = max(0, min(bd, (self._h - 1) // 2, (self._w - 1) // 2))
		return bd

	def _preferredSize(self):
		"""Return (w, h) minimum size in terminal characters."""
		w  = _int(self._opts.get('width'))
		h  = _int(self._opts.get('height'))
		bd = self._cfgBorder()
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
		f = fg if fg else (self._opts.get('fg') or '')
		b = bg if bg else (self._opts.get('bg') or '')
		return app._colors.getAttr(f, b, **kw)

	def _isFocusable(self):
		tf = self._opts.get('takefocus', True)
		return (tf not in (False, 0, '0', '') and
			self._opts.get('state', 'normal') == 'normal')

	def _getAllFocusable(self):
		if not self._isMapped():
			return []
		result = []
		if self._isFocusable():
			result.append(self)
		for c in self._children:
			if c._geoManager is not None:
				result.extend(c._getAllFocusable())
		return result

	def _isAncestorOf(self, widget) -> bool:
		w = widget
		while w is not None:
			if w is self:
				return True
			w = w._parent
		return False

	def _hitTest(self, mx, my):
		return (self._x <= mx < self._x + self._w and
			self._y <= my < self._y + self._h)

	def _findAt(self, mx, my):
		"""Return deepest widget at screen position (mx, my)."""
		if not self._isMapped() or not self._hitTest(mx, my):
			return None
		for child in reversed(self._children):
			if child._geoManager is None:
				continue
			hit = child._findAt(mx, my)
			if hit:
				return hit
		return self

	def _preRender(self):
		"""Called after layout, before drawing: clamp scroll offsets,
		notify scroll commands …  Containers recurse into children."""
		for c in self._children:
			if c._geoManager is not None:
				c._preRender()

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		"""Draw this widget onto *scr*.  Override in subclasses."""
		pass

	def _renderChildren(self, scr):
		for child in self._children:
			if child._geoManager is not None and child._isMapped():
				child.render(scr)

	# ------------------------------------------------------------------
	# Input dispatch
	#
	# The application first fires the user bindings (see Tk._onKey and
	# Tk._onMouse), then calls these methods for the class behaviour.
	# ------------------------------------------------------------------

	def _handleKey(self, key):
		"""Default class behaviour for a key.  Return True if consumed."""
		return False

	def _handleMouse(self, mx, my, bstate):
		"""Default class behaviour for a mouse event.  Return True if consumed."""
		return False

	# Helpers for subclasses
	def _wheel(self, bstate) -> int:
		return isWheel(bstate)

	def _dragging(self) -> bool:
		"""True while this widget owns a button-1 drag."""
		app = self._getApp()
		return app is not None and app._dragWidget is self


def _mouseEventNames(bstate, dragging) -> list:
	"""Return the binding names (in firing order) for a curses bstate.

	Each entry is a list of alternatives, most specific first.
	"""
	names = []
	wheel = isWheel(bstate)
	if wheel < 0:
		names.append(['<Button-4>', '<ButtonPress-4>', '<4>', '<MouseWheel>'])
	elif wheel > 0:
		names.append(['<Button-5>', '<ButtonPress-5>', '<5>', '<MouseWheel>'])
	if bstate & MOTION and not (bstate & (B1_RELEASE | B1_CLICK | B1_DCLICK)):
		if dragging:
			names.append(['<B1-Motion>', '<Motion>'])
		else:
			names.append(['<Motion>'])
		return names
	if bstate & B1_DCLICK:
		names.append(['<Double-Button-1>', '<Double-1>', '<Double-ButtonPress-1>'])
	if bstate & (B1_PRESS | B1_CLICK):
		if bstate & B1_PRESS and dragging:
			names.append(['<B1-Motion>', '<Motion>'])
		else:
			names.append(['<Button-1>', '<ButtonPress-1>', '<1>', '<Button>'])
	if bstate & (B1_RELEASE | B1_CLICK):
		names.append(['<ButtonRelease-1>', '<ButtonRelease>'])
	if bstate & B3_ANY and not (bstate & curses.BUTTON3_RELEASED):
		names.append(['<Button-3>', '<ButtonPress-3>', '<3>', '<Button>'])
	if bstate & (curses.BUTTON2_PRESSED | curses.BUTTON2_CLICKED):
		names.append(['<Button-2>', '<ButtonPress-2>', '<2>', '<Button>'])
	return names


def _newMouseEvent(widget, mx, my, bstate):
	evt		= MouseEvent(mx, my, bstate)
	evt.widget	= widget
	evt.x		= mx - widget._x
	evt.y		= my - widget._y
	return evt


def _newKeyEvent(widget, key):
	evt		= KeyEvent(key)
	evt.widget	= widget
	return evt
