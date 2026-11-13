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

import itertools as _itertools
import curses
from . import _colors, _sysclip
from ._events import Event, KeyEvent, MouseEvent, B1_PRESS, B1_RELEASE, \
	B1_CLICK, B1_DCLICK, B3_ANY, MOTION, isWheel, keysymOf, \
	STATE_BUTTON1, STATE_SHIFT, STATE_CONTROL, STATE_ALT, mouseState


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
	lines	= text.expandtabs(8).split('\n')
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


def _pixels(value) -> float:
	"""Convert a Tk screen distance ('10', '2c', '1i', 12) to a number."""
	if isinstance(value, (int, float)):
		return value
	s = str(value).strip()
	scale = {'c': 37.8, 'm': 3.78, 'i': 96.0, 'p': 1.33}
	try:
		if s and s[-1] in scale:
			return float(s[:-1]) * scale[s[-1]]
		return float(s)
	except ValueError:
		raise TclError(f'bad screen distance "{value}"')


def _cellX(value) -> int:
	"""Widget relative x in screen units (pixels in pixel mode) -> cell."""
	return int(float(value)) // PX


def _cellY(value) -> int:
	return int(float(value)) // PY


def _pxBox(box):
	"""(x, y, w, h) in cells -> screen units."""
	if not box:
		return box
	x, y, w, h = box[:4]
	return (x * PX, y * PY, w * PX, h * PY) + tuple(box[4:])


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
# tkinter compatibility helpers
# ---------------------------------------------------------------------------

_defaultRoot = None		# first Tk() created (tkinter._default_root)

# Pixel mode.  Native tktext programs use character cells everywhere
# (scale 1).  When tktext stands in for tkinter (install()) programs speak
# pixels: one cell is then PX x PY pixels of a virtual display.  Pixel
# distances given to tktext are converted to cells on input, and winfo_*,
# event coordinates and geometry strings are reported back in pixels.
PX = 1
PY = 1


def setPixelMode(px=8, py=16):
	"""Interpret screen distances as pixels of a px x py cell."""
	global PX, PY
	PX = px
	PY = py


def _cellsX(value, pad=False) -> int:
	"""Horizontal screen distance (pixels in pixel mode) -> cells.
	Paddings round down (so small gaps vanish), sizes to nearest."""
	if PX == 1 and isinstance(value, int):
		return value
	p = _pixels(value) / PX
	return int(p) if pad else int(p + 0.5)


def _cellsY(value, pad=False) -> int:
	if PY == 1 and isinstance(value, int):
		return value
	p = _pixels(value) / PY
	return int(p) if pad else int(p + 0.5)


def _scalePad(value, conv):
	"""Convert a pad value (n, (a, b) or 'a b') with *conv*."""
	if value is None or value == '':
		return 0
	if isinstance(value, (tuple, list)):
		return tuple(conv(v, True) for v in value)
	if isinstance(value, str) and len(value.split()) > 1:
		return tuple(conv(v, True) for v in value.split())
	return conv(value, True)


_GEO_OPTIONS = {
	'pack':  ('after', 'anchor', 'before', 'expand', 'fill', 'in',
		  'ipadx', 'ipady', 'padx', 'pady', 'side'),
	'grid':  ('column', 'columnspan', 'in', 'ipadx', 'ipady', 'padx',
		  'pady', 'row', 'rowspan', 'sticky'),
	'place': ('anchor', 'bordermode', 'height', 'in', 'relheight',
		  'relwidth', 'relx', 'rely', 'width', 'x', 'y'),
}


def _expandGeoOpts(manager, kwargs):
	"""Expand unique abbreviations of pack/grid/place options in place,
	as Tk does (e.g. grid(stick='nsew') means sticky='nsew')."""
	names = _GEO_OPTIONS[manager]
	for key in list(kwargs):
		name = key.rstrip('_')
		if name in names:
			continue
		match = [n for n in names if n.startswith(name)]
		if name and len(match) == 1 and match[0] not in kwargs:
			kwargs[match[0]] = kwargs.pop(key)


def _scaleGeoOpts(opts):
	"""Convert pack/grid/place options from pixels to cells in place."""
	if PX == 1 and PY == 1:
		return opts
	for key, conv in (('padx', _cellsX), ('ipadx', _cellsX),
			('pady', _cellsY), ('ipady', _cellsY)):
		if key in opts:
			opts[key] = _scalePad(opts[key], conv)
	for key, conv in (('x', _cellsX), ('width', _cellsX),
			('y', _cellsY), ('height', _cellsY)):
		if opts.get(key) not in (None, ''):
			opts[key] = conv(opts[key])
	return opts


def _initArgs(parent, cnf, kwargs):
	"""Normalise tkinter style constructor arguments.

	Accepts Widget(master, cnf, **kw), master= as keyword, and falls back
	to the default root when no parent is given.  Returns (parent, kwargs).
	"""
	if 'master' in kwargs:
		parent = kwargs.pop('master')
	if cnf:
		kwargs = {**cnf, **kwargs}
	if parent is None:
		parent = _defaultRoot
	return parent, kwargs


def _callback(widget, func, *args):
	"""Invoke a user callback through tktext.CallWrapper (tkinter routes
	every Tcl->Python call through tkinter.CallWrapper; applications such
	as flair replace it to install their own exception reporting)."""
	import tktext
	return tktext.CallWrapper(func, None, widget)(*args)


# ---------------------------------------------------------------------------
# Widget base class
# ---------------------------------------------------------------------------

class Widget:
	"""Base class for all tktext widgets."""

	_isRoot		= False
	_isToplevel	= False
	_override	= False
	_widgetCount	= 0
	_lastGeom	= None		# geometry of the last <Configure>
	_clickFocus	= True		# a mouse press gives the keyboard focus
	_propagate	= True		# pack_propagate / grid_propagate
	_rendersChildren = False	# containers draw their children in render()

	def __init__(self, parent=None, cnf=None, **kwargs):
		if type(self) is not Widget and not self._isRoot:
			parent, kwargs = _initArgs(parent, cnf, kwargs)
		self._parent	= parent
		self.master	= parent
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
		self._width = 0
		self._height = 0
		# Geometry manager info
		self._geoManager	= None
		self._geoInfo		= {}
		# Event bindings: event_str -> [(funcid, callable), ...]
		self._bindings	= {}
		self._focused	= False
		self._destroyed	= False
		Widget._widgetCount += 1
		self._name	= f'!{type(self).__name__.lower()}{Widget._widgetCount}'

		if 'name' in kwargs:
			self._name = str(kwargs.pop('name'))
		if parent is not None:
			parent._addChild(self)

		if kwargs:
			Widget.configure(self, **kwargs)

	# ------------------------------------------------------------------
	# tkinter attributes: _w (path name), children, tk (interpreter)
	# ------------------------------------------------------------------

	@property
	def _w(self):
		return str(self)

	@property
	def children(self):
		return {c._name: c for c in self._children}

	@property
	def tk(self):
		"""The (emulated) Tcl interpreter of this widget's application."""
		app = self._getApp()
		if app is None:
			from ._tcl import tcl
			return tcl
		shim = app.__dict__.get('_tcl')
		if shim is None:
			from ._tcl import TclShim
			shim = app._tcl = TclShim(app)
		return shim

	@property
	def widgetName(self):
		return self.winfo_class().lower()

	def __repr__(self):
		return f'<{type(self).__module__}.{type(self).__name__} object {self}>'

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
		if 'name' in kwargs:
			self._name = str(kwargs.pop('name'))
		if PX != 1 or PY != 1:
			self._scaleOptions(kwargs)
		self._opts.update(kwargs)
		self._markDirty()
		return None

	# options holding screen distances: name -> converter (pixel mode)
	_PIXEL_OPTIONS = {
		'padx':		lambda v: _scalePad(v, _cellsX),
		'pady':		lambda v: _scalePad(v, _cellsY),
		'wraplength':	_cellsX,
		'length':	_cellsX,
		'sliderlength':	_cellsX,
		'indent':	_cellsX,
		'spacing1':	lambda v: _cellsY(v, True),
		'spacing2':	lambda v: _cellsY(v, True),
		'spacing3':	lambda v: _cellsY(v, True),
	}
	_pixelSize	= False		# width/height are screen distances
	_keepBorder	= False		# draw the border in pixel mode too

	def _scaleOptions(self, kwargs):
		for key, conv in self._PIXEL_OPTIONS.items():
			if key in kwargs and kwargs[key] not in (None, ''):
				try:
					kwargs[key] = conv(kwargs[key])
				except (TclError, ValueError, TypeError):
					pass
		if self._pixelSize:
			for key, conv in (('width', _cellsX), ('height', _cellsY)):
				if kwargs.get(key) not in (None, ''):
					try:
						kwargs[key] = conv(kwargs[key])
					except (TclError, ValueError, TypeError):
						pass

	config = configure

	def cget(self, key):
		"""Return the current value of option *key*."""
		key = self._OPTION_ALIASES.get(key, key)
		if key == 'from':
			key = 'from_'
		value = self._opts.get(key)
		if not value and key in ('bg', 'fg'):
			return self._color(key)
		return '' if value is None and key not in self._opts else value

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
			if _callback(self, h, evtObj) == 'break':
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
			app = self._getApp()
			if kw.get('when') in ('tail', 'head', 'mark') and app is not None:
				app._eventQueue.append((self, sequence, evt))
				return
			self._dispatchVirtual(sequence, evt)
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
		"""Fire a virtual event like '<<ListboxSelect>>' on this widget.
		Like Tk the event is queued and delivered from the event loop
		(after the current callback returns)."""
		evt		= Event()
		evt.widget	= self
		evt.type	= 'VirtualEvent'
		for k, v in attrs.items():
			setattr(evt, k, v)
		app = self._getApp()
		if app is None:
			return self._dispatchVirtual(name, evt)
		app._eventQueue.append((self, name, evt))
		app._dirty = True
		return None

	def _dispatchVirtual(self, sequence, evt):
		"""Virtual event: widget, class, toplevel then 'all' bindings
		(the tkinter bindtags order); 'break' stops."""
		if self._dispatch(sequence, evt) == 'break':
			return 'break'
		app = self._getApp()
		if app is None:
			return None
		table = app._classBindings.get(self.winfo_class())
		if table is not None and table._dispatch(sequence, evt) == 'break':
			return 'break'
		if self._handleVirtual(sequence):
			self._markDirty()
		top = self.winfo_toplevel()
		if top is not None and top is not self and \
				top._dispatch(sequence, evt) == 'break':
			return 'break'
		return app._allBindings._dispatch(sequence, evt)

	# ------------------------------------------------------------------
	# Geometry managers
	# ------------------------------------------------------------------

	def _container(self):
		"""The widget whose _children list holds this widget (its geometry
		master after pack/grid/place(in_=…), else its parent)."""
		m = self.__dict__.get('_geoMaster')
		return m if m is not None and not m._destroyed else self._parent

	def _geoPlace(self, manager, kwargs):
		"""Handle the in_/before/after options and Tk's packing order: a
		widget that starts being managed goes to the end of the order."""
		_expandGeoOpts(manager, kwargs)
		master = kwargs.pop('in_', None) or kwargs.pop('in', None)
		before = kwargs.pop('before', None)
		after  = kwargs.pop('after', None)
		cont   = self._container()
		if master is not None and master is not cont and master is not self:
			if cont is not None and self in cont._children:
				cont._children.remove(self)
			master._children.append(self)
			self._geoMaster = master
			cont = master
		if cont is None:
			return
		sibling = before if before is not None else after
		if sibling is not None and sibling in cont._children and sibling is not self:
			cont._children.remove(self)
			i = cont._children.index(sibling)
			cont._children.insert(i if before is not None else i + 1, self)
		elif self._geoManager != manager and self in cont._children and \
				manager == 'pack':
			cont._children.remove(self)
			cont._children.append(self)

	def _setManager(self, manager, opts):
		self._geoManager	= manager
		self._geoInfo		= opts
		cont = self._container()
		if cont is not None:
			cont._markDirty()
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
			if not c._isToplevel:
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
		self._geoPlace('pack', kwargs)
		opts.update(_scaleGeoOpts(kwargs))
		self._setManager('pack', opts)

	def packConfigure(self, **kwargs):
		if self._geoManager == 'pack':
			self._geoPlace('pack', kwargs)
			self._geoInfo.update(_scaleGeoOpts(kwargs))
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
		self._geoPlace('grid', kwargs)
		opts.update(_scaleGeoOpts(kwargs))
		if opts['row'] is None:
			# tkinter: the first row after the last one used in the master
			cont = self._container()
			used = [c._geoInfo.get('row', 0) + c._geoInfo.get('rowspan', 1)
				for c in (cont._children if cont else [])
				if c is not self and c._geoManager == 'grid']
			opts['row'] = max(used) if used else 0
		opts['row']		= _int(opts['row'])
		opts['column']		= _int(opts['column'])
		opts['rowspan']		= max(1, _int(opts['rowspan'], 1))
		opts['columnspan']	= max(1, _int(opts['columnspan'], 1))
		self._setManager('grid', opts)

	def gridConfigure(self, **kwargs):
		if self._geoManager == 'grid':
			self._geoPlace('grid', kwargs)
			self._geoInfo.update(_scaleGeoOpts(kwargs))
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
		self._geoPlace('place', kwargs)
		opts.update(_scaleGeoOpts(kwargs))
		self._setManager('place', opts)

	def placeConfigure(self, **kwargs):
		if self._geoManager == 'place':
			self._geoPlace('place', kwargs)
			self._geoInfo.update(_scaleGeoOpts(kwargs))
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
		p = self._container()
		if p is not None and self in p._children:
			p._children.remove(self)
			p._children.append(self)
			self._markDirty()

	def lower(self, belowThis=None):
		p = self._container()
		if p is not None and self in p._children:
			p._children.remove(self)
			p._children.insert(0, self)
			self._markDirty()

	tkraise = lift

	# ------------------------------------------------------------------
	# Focus
	# ------------------------------------------------------------------

	def focusSet(self):
		"""Give keyboard focus to this widget.  Like Tk the request is
		remembered by the widget's toplevel even if another window is
		active now (the focus moves here when that window is activated)."""
		app = self._getApp()
		if app:
			top = self.winfoToplevel()
			if top is not None:
				top._lastFocus = self
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

	def winfoWidth(self):	return self._width * PX if self._width > 0 else 1
	def winfoHeight(self):	return self._height * PY if self._height > 0 else 1
	def winfoRootx(self):	return self._x * PX
	def winfoRooty(self):	return self._y * PY
	def winfoIsmapped(self):return self._isMapped()
	def winfoChildren(self):return [c for c in self._children if not c._destroyed]
	def winfoExists(self):	return not self._destroyed
	def winfoReqwidth(self):return self._preferredSize()[0] * PX
	def winfoReqheight(self):return self._preferredSize()[1] * PY
	def winfoName(self):	return self._name
	def winfoId(self):	return id(self)
	def winfoManager(self):	return self._geoManager or ''
	def winfoDepth(self):	return 24
	def winfoCells(self):	return 256
	def winfoGeometry(self):
		return f'{self.winfoWidth()}x{self.winfoHeight()}+{self.winfoX()}+{self.winfoY()}'

	def winfoX(self):
		if self._isToplevel or self._parent is None:
			return self._x * PX
		return (self._x - self._parent._x) * PX

	def winfoY(self):
		if self._isToplevel or self._parent is None:
			return self._y * PY
		return (self._y - self._parent._y) * PY

	def winfoViewable(self):
		if not self._isMapped():
			return False
		top = self.winfoToplevel()
		return top is None or top._viewable()

	def winfoParent(self):
		"""Path name of the parent (like tkinter)."""
		return str(self._parent) if self._parent is not None else ''

	def winfoToplevel(self):
		w = self
		while w is not None:
			if w._isToplevel:
				return w
			w = w._parent
		return self._getApp()

	def winfoClass(self):
		"""Tk class name: the tktext widget class, not the user subclass
		(like tkinter, where subclasses keep the class of their base)."""
		cls = self._opts.get('class_')
		if cls:
			return cls
		for k in type(self).__mro__:
			if k.__module__.startswith('tktext.') and not k.__name__.startswith('_'):
				return k.__name__
		return type(self).__name__

	def winfoScreenwidth(self):
		app = self._getApp()
		return (app._width if app else 80) * PX

	def winfoScreenheight(self):
		app = self._getApp()
		return (app._height if app else 24) * PY

	def winfoScreenmmwidth(self):
		return int(self.winfoScreenwidth() / PX * 2)

	def winfoScreenmmheight(self):
		return int(self.winfoScreenheight() / PY * 4)

	def winfoVrootwidth(self):
		return self.winfoScreenwidth()

	def winfoVrootheight(self):
		return self.winfoScreenheight()

	def winfoPointerxy(self):
		app = self._getApp()
		mx, my = app._mouseXY if app else (0, 0)
		return (mx * PX, my * PY)

	def winfoPointerx(self):	return self.winfoPointerxy()[0]
	def winfoPointery(self):	return self.winfoPointerxy()[1]

	def winfoContaining(self, rootX, rootY, displayof=0):
		app = self._getApp()
		if app is None:
			return None
		x = int(rootX) // PX
		y = int(rootY) // PY
		win = app._windowAt(x, y)
		return win._findAt(x, y) if win is not None else None

	def winfoFpixels(self, number):
		return float(_pixels(number))

	def winfoPixels(self, number):
		return int(_pixels(number))

	def winfoRgb(self, color):
		from ._colors import ColorManager
		rgb = ColorManager.toRGB(color)
		if rgb is None:
			raise TclError(f'unknown color name "{color}"')
		return tuple(v * 257 for v in rgb)

	def winfoVisual(self):		return 'truecolor'
	def winfoScreenvisual(self):	return 'truecolor'
	def winfoServer(self):		return 'tktext'
	def winfoInterps(self, displayof=0): return ('tktext',)
	def winfoWindowingsystem(self):	return 'x11'

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
	winfo_screenmmwidth	= winfoScreenmmwidth
	winfo_screenmmheight	= winfoScreenmmheight
	winfo_vrootwidth	= winfoVrootwidth
	winfo_vrootheight	= winfoVrootheight
	winfo_name		= winfoName
	winfo_id		= winfoId
	winfo_manager		= winfoManager
	winfo_depth		= winfoDepth
	winfo_screendepth	= winfoDepth
	winfo_cells		= winfoCells
	winfo_screencells	= winfoCells
	winfo_geometry		= winfoGeometry
	winfo_pointerxy		= winfoPointerxy
	winfo_pointerx		= winfoPointerx
	winfo_pointery		= winfoPointery
	winfo_containing	= winfoContaining
	winfo_fpixels		= winfoFpixels
	winfo_pixels		= winfoPixels
	winfo_rgb		= winfoRgb
	winfo_visual		= winfoVisual
	winfo_screenvisual	= winfoScreenvisual
	winfo_server		= winfoServer
	winfo_interps		= winfoInterps
	winfo_vrootx		= lambda self: 0
	winfo_vrooty		= lambda self: 0
	winfo_screen		= lambda self: ':0'
	winfo_atom		= lambda self, name, displayof=0: hash(name) & 0xffff
	winfo_pathname		= lambda self, id, displayof=0: str(self)

	# ------------------------------------------------------------------
	# Misc (tkinter.Misc) — names, class bindings, options, grabs
	# ------------------------------------------------------------------

	def nametowidget(self, name):
		"""Return the widget with path name *name*."""
		from ._tcl import _nameToWidget
		if isinstance(name, Widget):
			return name
		name = str(name)
		if not name.startswith('.'):
			name = f'{self}.{name}' if str(self) != '.' else f'.{name}'
		return _nameToWidget(name, self._getApp())

	_nametowidget = nametowidget

	def _root(self):
		return self._getApp()

	def _classTable(self, className, create=False):
		app = self._getApp()
		if app is None:
			return None
		table = app._classBindings.get(className)
		if table is None and create:
			table = app._classBindings[className] = Widget()
		return table

	def bind_class(self, className, sequence=None, func=None, add=None):
		"""Bind *sequence* for every widget of Tk class *className*
		(runs after the widget's own bindings, before its class
		behaviour).  className 'all' is bind_all()."""
		if className == 'all':
			return self.bind_all(sequence, func, add)
		table = self._classTable(className, create=True)
		if table is None:
			return None
		return Widget.bind(table, sequence, func, add)

	def unbind_class(self, className, sequence):
		table = self._classTable(className)
		if table is not None:
			table._bindings.pop(sequence, None)

	def bindtags(self, tagList=None):
		if tagList is None:
			return (str(self), self.winfo_class(), str(self.winfo_toplevel()), 'all')
		self._bindtags = tuple(tagList)

	def event_add(self, virtual, *sequences):
		app = self._getApp()
		if app is not None:
			app._virtualEvents.setdefault(virtual, [])
			for seq in sequences:
				if seq not in app._virtualEvents[virtual]:
					app._virtualEvents[virtual].append(seq)

	def event_delete(self, virtual, *sequences):
		app = self._getApp()
		if app is None or virtual not in app._virtualEvents:
			return
		if not sequences:
			del app._virtualEvents[virtual]
			return
		app._virtualEvents[virtual] = [s for s in app._virtualEvents[virtual]
			if s not in sequences]

	def event_info(self, virtual=None):
		app = self._getApp()
		if app is None:
			return ()
		if virtual is None:
			return tuple(app._virtualEvents.keys())
		return tuple(app._virtualEvents.get(virtual, ()))

	# option database (stored; patterns are matched on the last name only)
	def option_add(self, pattern, value, priority=None):
		app = self._getApp()
		if app is not None:
			app._optionDb.pop(str(pattern), None)
			app._optionDb[str(pattern)] = value
			app._optionCache.clear()
			app._dirty = True

	def option_clear(self):
		app = self._getApp()
		if app is not None:
			app._optionDb.clear()
			app._optionCache.clear()

	def option_get(self, name, className):
		app = self._getApp()
		if app is None:
			return ''
		return app._optionLookup(self.winfo_class(), self._name, name) or ''

	def option_readfile(self, fileName, priority=None):
		pass

	# Tcl variables / commands
	def register(self, func, subst=None, needcleanup=1):
		"""Register *func* as a Tcl command; returns its name."""
		Widget._funcSerial += 1
		name = f'{id(func)}{getattr(func, "__name__", "func")}{Widget._funcSerial}'
		self.tk.createcommand(name, func)
		return name

	_register = register

	def deletecommand(self, name):
		self.tk.deletecommand(name)

	def getvar(self, name='PY_VAR'):
		return self.tk.getvar(name)

	def setvar(self, name='PY_VAR', value='1'):
		self.tk.setvar(name, value)

	def getboolean(self, s):
		return self.tk.getboolean(s)

	def getint(self, s):
		return self.tk.getint(s)

	def getdouble(self, s):
		return self.tk.getdouble(s)

	def image_names(self):
		from ._image import image_names
		return image_names()

	def image_types(self):
		from ._image import image_types
		return image_types()

	# clipboard / selection (process local clipboard of the app), like Tk
	# one buffer per type (format); STRING and UTF8_STRING are the same
	@staticmethod
	def _clipboardType(kw):
		kind = kw.get('type') or 'STRING'
		return 'STRING' if kind in ('UTF8_STRING', 'TEXT') else kind

	def clipboard_get(self, **kw):
		app  = self._getApp()
		data = app._clipboard if app is not None else {}
		kind = self._clipboardType(kw)
		if kind in ('STRING', 'TARGETS') and app is not None and app._ownScreen:
			# another program copied: its text replaces our typed buffers
			text = _sysclip.paste()
			if text is not None and text != data.get('STRING', ''):
				data.clear()
				if text:
					data['STRING'] = text
		if kind == 'TARGETS' and data:
			extra = ('UTF8_STRING',) if 'STRING' in data else ()
			return ('TARGETS',) + tuple(data) + extra
		if kind not in data:
			raise TclError(f'CLIPBOARD selection doesn\'t exist or form "{kind}" not defined')
		return data[kind]

	def clipboard_clear(self, **kw):
		app = self._getApp()
		if app is not None:
			app._clipboard.clear()

	def clipboard_append(self, string, **kw):
		app = self._getApp()
		if app is not None:
			kind = self._clipboardType(kw)
			if isinstance(string, (bytes, bytearray)):
				string = string.decode('latin-1')
			app._clipboard[kind] = app._clipboard.get(kind, '') + str(string)
			if kind == 'STRING' and app._ownScreen:
				_sysclip.copy(app._clipboard[kind])

	clipboardGet	= clipboard_get
	clipboardClear	= clipboard_clear
	clipboardAppend	= clipboard_append

	def selection_get(self, **kw):
		if kw.get('selection') == 'CLIPBOARD' or not hasattr(self, '_selectedText'):
			return self.clipboard_get(**kw)
		text = self._selectedText()
		if not text:
			raise TclError('PRIMARY selection doesn\'t exist or form "STRING" not defined')
		return text

	def selection_clear(self, **kw):
		pass

	def selection_own(self, **kw):
		pass

	def selection_own_get(self, **kw):
		return None

	def selection_handle(self, command, **kw):
		pass

	# grabs
	def grab_set(self):
		"""Confine mouse and keyboard to this widget's window."""
		app = self._getApp()
		if app is not None:
			app._grab  = self
			app._dirty = True

	grab_set_global = grab_set

	def grab_release(self):
		app = self._getApp()
		if app is not None and app._grab is self:
			app._grab  = None
			app._dirty = True

	def grab_current(self):
		app = self._getApp()
		return app._grabWindow() if app is not None else None

	def grab_status(self):
		app = self._getApp()
		if app is not None and app._grab is self:
			return 'local'
		return None

	# modal waits: run the event loop until the condition holds
	def _waitUntil(self, done):
		app = self._getApp()
		if app is None or app._quit:
			return
		if not app._ensureScreen():
			return
		app._update(force=True)
		while not done() and not app._quit and app._scr is not None:
			app._processOneEvent()

	def wait_window(self, window=None):
		window = self if window is None else window
		self._waitUntil(lambda: window._destroyed)

	def wait_visibility(self, window=None):
		window = self if window is None else window
		app = self._getApp()
		if app is not None:
			app._update(force=True)

	def wait_variable(self, name='PY_VAR'):
		var = name
		if not hasattr(var, 'trace_add'):
			return
		changed = []
		cb = var.trace_add('write', lambda *a: changed.append(1))
		try:
			self._waitUntil(lambda: changed or self._destroyed)
		finally:
			var.trace_remove('write', cb)

	waitvar = wait_variable

	# focus helpers
	def focus_lastfor(self):
		top = self.winfo_toplevel()
		return top._lastFocus if top is not None else None

	def tk_focusNext(self):
		app = self._getApp()
		if app is None:
			return None
		lst = app._focusables(self.winfo_toplevel())
		if not lst:
			return None
		i = lst.index(self) + 1 if self in lst else 0
		return lst[i % len(lst)]

	def tk_focusPrev(self):
		app = self._getApp()
		if app is None:
			return None
		lst = app._focusables(self.winfo_toplevel())
		if not lst:
			return None
		i = lst.index(self) - 1 if self in lst else -1
		return lst[i % len(lst)]

	def tk_focusFollowsMouse(self):
		pass

	def tk_setPalette(self, *args, **kw):
		"""Set default colours (tkinter: background=…, foreground=…)."""
		if len(args) == 1:
			kw['background'] = args[0]
		elif args:
			kw.update(zip(args[0::2], args[1::2]))
		for key in ('background', 'foreground'):
			if kw.get(key):
				self.option_add(f'*{key}', kw[key])
		_colors.addDefaultColors(kw.get('background'), kw.get('foreground'))

	def tk_bisque(self):
		pass

	def tk_strictMotif(self, boolean=None):
		return 0

	def bell(self, displayof=0):
		try:
			curses.beep()
		except curses.error:
			pass

	# geometry propagation
	def pack_propagate(self, flag=None):
		if flag is None:
			return self._propagate
		self._propagate = bool(flag) and flag not in ('0', 'false')
		self._markDirty()

	propagate	= pack_propagate
	grid_propagate	= pack_propagate

	def slaves(self):
		return [c for c in self._children if c._geoManager is not None]

	pack_slaves	= lambda self: [c for c in self._children if c._geoManager == 'pack']
	place_slaves	= lambda self: [c for c in self._children if c._geoManager == 'place']

	def grid_slaves(self, row=None, column=None):
		result = []
		for c in reversed(self._children):
			if c._geoManager != 'grid':
				continue
			o = c._geoInfo
			if row is not None and o['row'] != row:
				continue
			if column is not None and o['column'] != column:
				continue
			result.append(c)
		return result

	def grid_anchor(self, anchor=None):
		pass

	# grid configuration on any widget (only containers lay out a grid)
	def _gridTable(self, rows):
		name = '_rowCfg' if rows else '_colCfg'
		if name not in self.__dict__:
			setattr(self, name, {})
		return getattr(self, name)

	def columnconfigure(self, index, cnf=None, **kw):
		if cnf:
			kw.update(cnf)
		table = self._gridTable(False)
		if not kw:
			return dict(table.get(_int(index), {}))
		table.setdefault(_int(index), {}).update(kw)
		self._markDirty()

	def rowconfigure(self, index, cnf=None, **kw):
		if cnf:
			kw.update(cnf)
		table = self._gridTable(True)
		if not kw:
			return dict(table.get(_int(index), {}))
		table.setdefault(_int(index), {}).update(kw)
		self._markDirty()

	grid_columnconfigure	= lambda self, *a, **kw: self.columnconfigure(*a, **kw)
	grid_rowconfigure	= lambda self, *a, **kw: self.rowconfigure(*a, **kw)

	def grid_size(self):
		gridded = [c._geoInfo for c in self._children if c._geoManager == 'grid']
		if not gridded:
			return (0, 0)
		return (max(o['column'] + o.get('columnspan', 1) for o in gridded),
			max(o['row'] + o.get('rowspan', 1) for o in gridded))

	size = grid_size

	def grid_bbox(self, column=None, row=None, col2=None, row2=None):
		"""Bounding box (x, y, w, h) of grid cells, from the slaves' layout."""
		boxes = []
		for c in self._children:
			if c._geoManager != 'grid' or not c._isMapped():
				continue
			o = c._geoInfo
			if column is not None and not (int(column) <= o['column'] <=
					int(col2 if col2 is not None else column)):
				continue
			if row is not None and not (int(row) <= o['row'] <=
					int(row2 if row2 is not None else row)):
				continue
			boxes.append((c._x, c._y, c._x + c._width, c._y + c._height))
		if not boxes:
			return (0, 0, 0, 0)
		x0 = min(b[0] for b in boxes) - self._x
		y0 = min(b[1] for b in boxes) - self._y
		return _pxBox((x0, y0, max(b[2] for b in boxes) - self._x - x0,
			max(b[3] for b in boxes) - self._y - y0))

	bbox = grid_bbox

	def grid_location(self, x, y):
		return (0, 0)

	# ttk widget state (ttk.Widget.state / instate)
	def state(self, statespec=None):
		flags = set(self.__dict__.get('_ttkState', ()))
		if self._opts.get('state') == 'disabled':
			flags.add('disabled')
		if statespec is None:
			return tuple(sorted(flags))
		old = tuple(sorted(flags))
		for spec in (statespec.split() if isinstance(statespec, str) else statespec):
			if spec.startswith('!'):
				flags.discard(spec[1:])
			else:
				flags.add(spec)
		self._ttkState = flags - {'disabled'}
		if 'disabled' in flags:
			if self._opts.get('state') != 'disabled':
				self.configure(state='disabled')
		elif self._opts.get('state') == 'disabled':
			self.configure(state='normal')
		return old

	def instate(self, statespec, callback=None, *args, **kw):
		flags = set(self.state())
		ok = all((s[1:] not in flags) if s.startswith('!') else (s in flags)
			for s in (statespec.split() if isinstance(statespec, str) else statespec))
		if ok and callback is not None:
			return callback(*args, **kw)
		return ok

	def identify(self, x, y):
		return ''

	def validate(self):
		return True

	# tk busy (Tk 8.6.x): the terminal has no cursor to change
	def busy_hold(self, **kw):
		pass

	busy = tk_busy_hold = busy_hold

	def busy_forget(self):
		pass

	tk_busy_forget = busy_forget

	def busy_status(self):
		return False

	tk_busy_status = busy_status

	def busy_current(self, pattern=None):
		return []

	tk_busy_current = busy_current

	def busy_configure(self, cnf=None, **kw):
		return {}

	busy_config = tk_busy_configure = tk_busy_config = busy_configure

	def busy_cget(self, option):
		return ''

	tk_busy_cget = busy_cget

	def _fireStructure(self, sequence, **attrs):
		evt		= Event()
		evt.widget	= self
		evt.type	= sequence.strip('<>')
		for k, v in attrs.items():
			setattr(evt, k, v)
		return self._dispatch(sequence, evt)

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
		if self._destroyed:
			return
		app = self._getApp()
		for child in list(self._children):
			child.destroy()
		self._children.clear()
		if self._bindings.get('<Destroy>'):
			self._fireStructure('<Destroy>')
		if app is not None and not self._isRoot:
			if app._focusWidget is self:
				app._focusWidget = None
				app._focusLost   = True
			if app._dragWidget is self:
				app._dragWidget = None
			if app._grab is self:
				app._grab = None
			if app._hover is self:
				app._hover = None
			app._dirty = True
		cont = self._container()
		for holder in {id(c): c for c in (cont, self._parent) if c is not None}.values():
			if self in holder._children:
				holder._children.remove(self)
				holder._childDestroyed(self)
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

	def _withImage(self, text) -> str:
		"""Text to show for a widget with text and/or image=.  An image
		alone becomes a one-cell glyph; with compound= the text keeps a
		blank where the image would be (pixel mode), so that adjacent
		icon+text buttons stay apart."""
		if not self._opts.get('image'):
			return text
		if not text:
			# an icon with its own glyph always shows it
			glyph = self._imageGlyph()
			if glyph:
				return glyph
			# otherwise its alt text (or a placeholder) only if it can be
			# clicked; decorative icons stay blank
			from ._image import IMAGE_GLYPH, _imageByName
			if self._opts.get('command') or any(self._bindings.get(e) for e in
					('<Button-1>', '<ButtonRelease-1>', '<1>', '<ButtonPress-1>')):
				img = _imageByName(self._opts.get('image'))
				if img is None:
					img = self._opts.get('image')
				# a large picture goes with a text label elsewhere (ribbon
				# buttons): only small (toolbar) icons are named
				if PX != 1 and _int(getattr(img, 'height', lambda: 0)()) > 24:
					return ' '
				if self._labelledByNeighbour():
					return ' '
				alt = getattr(img, 'alt', '')
				return f' {alt} ' if alt else IMAGE_GLYPH
			return ' '
		comp = str(self._opts.get('compound') or 'none')
		glyph = self._imageGlyph()
		if glyph:
			if comp in ('left', 'top'):
				return f'{glyph} {text}'
			if comp in ('right', 'bottom'):
				return f'{text} {glyph}'
		if PX == 1:
			return text
		if comp == 'left':
			return ' ' + text
		if comp == 'right':
			return text + ' '
		return ' ' + text + ' '

	def _imageGlyph(self) -> str:
		"""The one-cell glyph of the image= option ('' if none)."""
		from ._image import _imageByName
		img = _imageByName(self._opts.get('image'))
		if img is None:
			img = self._opts.get('image')
		return str(getattr(img, 'glyph', '') or '')

	def _labelledByNeighbour(self) -> bool:
		"""An icon followed (same grid row, next column, or the next
		left-packed sibling) by a widget showing text: an icon + label
		pair, so the icon need not be named."""
		cont = self._container()
		if cont is None or self._geoManager not in ('grid', 'pack'):
			return False
		info = self._geoInfo
		sibs = [c for c in cont._children if c._geoManager == self._geoManager]
		if self._geoManager == 'grid':
			nxt = [c for c in sibs if c._geoInfo.get('row') == info.get('row')
				and c._geoInfo.get('column') == info.get('column', 0) + 1]
		else:
			if info.get('side', 'top') != 'left' or self not in sibs:
				return False
			i   = sibs.index(self)
			nxt = sibs[i + 1:i + 2]
		return any(any(ch.isalnum() for ch in str(c._opts.get('text') or ''))
			for c in nxt)

	def _isMapped(self) -> bool:
		return self._width > 0 and self._height > 0 and not self._destroyed

	def _cfgBorder(self) -> int:
		"""Configured border width (used for size requests).  In pixel
		mode a Tk border (a few pixels of 3D relief) is not worth a whole
		cell: only the line-art reliefs and widgets that need their frame
		(LabelFrame caption) keep it."""
		bd = max(0, _int(self._opts.get('borderwidth')))
		if bd and (PX != 1 or PY != 1) and not self._keepBorder and \
				self._opts.get('relief') not in ('single', 'double'):
			return 0
		return min(bd, 1) if PX != 1 else bd

	def _border(self) -> int:
		"""Border width actually drawn: a widget squeezed below its border
		size drops the border instead of drawing content over it."""
		bd = self._cfgBorder()
		if bd and self._width > 0 and self._height > 0:
			bd = max(0, min(bd, (self._height - 1) // 2, (self._width - 1) // 2))
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
		self._width = w
		self._height = h

	def _getAttr(self, fg=None, bg=None, **kw):
		app = self._getApp()
		if app is None:
			return 0
		f = fg if fg else self._color('fg')
		b = bg if bg else self._color('bg')
		return app._colors.getAttr(f, b, **kw)

	# pixel mode: classes drawn with the 'tk.field' theme role (white
	# fields), the others use 'tk.window'
	# theme role of the default field colours ('entry' for Entry and its
	# subclasses); used natively and in pixel mode with terminal colours
	_fieldRole = None

	_FIELD_CLASSES = frozenset(('Entry', 'Text', 'Listbox', 'Spinbox',
		'Combobox', 'Treeview'))

	# Tk option database names of the colour options
	_DB_NAMES = {
		'selectbackground':	'selectBackground',
		'selectforeground':	'selectForeground',
		'activebackground':	'activeBackground',
		'activeforeground':	'activeForeground',
		'disabledforeground':	'disabledForeground',
		'readonlybackground':	'readonlyBackground',
		'insertbackground':	'insertBackground',
		'highlightcolor':	'highlightColor',
		'troughcolor':		'troughColor',
		'selectcolor':		'selectColor',
	}

	# classes of composite widgets (a Frame created with class_=…) whose
	# Label/Entry children are drawn as fields, e.g. a combobox built as
	# Frame(class_='Combobox') + Label + arrow button
	_FIELD_CONTAINERS = frozenset(('Combobox',))

	def _activeFieldRole(self):
		"""The field theme role used for the default colours, or None."""
		if not (PX == 1 or _colors.colorMode() == 'terminal'):
			return None
		role = self._fieldRole
		if role is None and self.winfo_class() in ('Label', 'Entry'):
			parent = self._parent
			if parent is not None and \
			   parent.winfo_class() in self._FIELD_CONTAINERS:
				role = 'entry'
		return role

	def _dbColor(self, app, key):
		return app._optionLookup(self.winfo_class(), self._name,
			'background' if key == 'bg' else 'foreground')

	def _color(self, key):
		"""Resolve colour option *key* ('fg' or 'bg'): explicit option,
		then the option database, then (pixel mode) the theme.  For a
		field, a palette default colour in the database (e.g. Tk's white
		'*Entry.background') gives way to the field role, otherwise the
		terminal colour mode would erase the field."""
		value = self._opts.get(key)
		if value:
			return value
		app = self._getApp()
		if app is None:
			return ''
		value = self._dbColor(app, key)
		role  = self._activeFieldRole()
		if role:
			# the role applies when the background is a default one;
			# the foreground follows the background
			if self._opts.get('bg'):
				useRole = False
			else:
				bg      = value if key == 'bg' else self._dbColor(app, 'bg')
				useRole = not bg or _colors.isDefaultColor(bg)
			if useRole and key == 'fg' and value:
				useRole = _colors.isDefaultColor(value, True)
			if useRole:
				fg, bg, _ = _colors.getTheme(role)
				return bg if key == 'bg' else fg
		if value:
			return value
		if PX == 1:
			return ''
		role = 'tk.field' if self.winfo_class() in self._FIELD_CLASSES else 'tk.window'
		fg, bg, _ = _colors.getTheme(role)
		return bg if key == 'bg' else fg

	def _optColor(self, option):
		"""Colour option *option* ('selectbackground' …): the widget's
		option, else the option database ('*selectBackground'), else ''."""
		value = self._opts.get(option)
		if value:
			return value
		app = self._getApp()
		if app is None:
			return ''
		return app._optionLookup(self.winfo_class(), self._name,
			self._DB_NAMES.get(option, option)) or ''

	def _roleAttr(self, role, **kw):
		"""Attribute of theme *role*, inheriting the widget's colours."""
		app = self._getApp()
		if app is None:
			return 0
		return app._colors.roleAttr(role, self._color('fg'), self._color('bg'), **kw)

	def _borderAttr(self, attr):
		"""Attribute of the border around content drawn with *attr*: the
		'border' role on the widget's background when *attr* is the
		normal one; focused, selected, disabled … borders keep *attr*."""
		if attr != self._getAttr():
			return attr
		return self._roleAttr('border')

	def _disabledAttr(self, **kw):
		"""Disabled text: disabledforeground or the 'disabled' role."""
		dfg = self._optColor('disabledforeground')
		if dfg:
			return self._getAttr(fg=dfg, **kw)
		return self._roleAttr('disabled', **kw)

	def _pairAttr(self, fgOpt, bgOpt, role, **kw):
		fg = self._optColor(fgOpt)
		bg = self._optColor(bgOpt)
		if fg or bg:
			return self._getAttr(fg=fg, bg=bg, **kw)
		return self._roleAttr(role, **kw)

	def _selectAttr(self, **kw):
		"""Selected text: select{fore,back}ground or the 'select' role."""
		return self._pairAttr('selectforeground', 'selectbackground', 'select', **kw)

	def _focusAttr(self, **kw):
		"""Active/focused element: active{fore,back}ground or the 'focus' role."""
		return self._pairAttr('activeforeground', 'activebackground', 'focus', **kw)

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
		return (self._x <= mx < self._x + self._width and
			self._y <= my < self._y + self._height)

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

	def _layoutChildren(self):
		"""Tk allows place() inside any widget (e.g. a popup list placed
		over a Text).  Containers override this; for the other widgets
		lay out the placed children inside the border."""
		placed = [(c, c._geoInfo) for c in self._children if c._geoManager == 'place']
		if not placed:
			return
		from ._layout import doPlaceLayout
		from ._frame import _InnerGeom
		bd = self._border()
		doPlaceLayout(_InnerGeom(self._x + bd, self._y + bd,
			max(0, self._width - 2*bd), max(0, self._height - 2*bd)), placed)

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
				child._renderWithSlaves(scr)

	def _renderWithSlaves(self, scr):
		"""Draw the widget, then the widgets placed inside it when the
		widget is not a container that draws its own children."""
		self.render(scr)
		if not self._rendersChildren:
			self._renderChildren(scr)

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

	def _handleVirtual(self, sequence):
		"""Class behaviour for a virtual event generated on the widget
		(Tk's class bindings, e.g. Listbox <<PrevLine>>).  Return True
		if handled."""
		return False

	def _pointerAt(self, mx, my):
		"""The pointer is at screen (mx, my) before the bindings run
		(Text moves its 'current' mark there, like Tk)."""
		pass

	# Helpers for subclasses
	def _wheel(self, bstate) -> int:
		return isWheel(bstate)

	def _dragging(self) -> bool:
		"""True while this widget owns a button-1 drag."""
		app = self._getApp()
		return app is not None and app._dragWidget is self

	def _dragLost(self):
		"""The release ending this widget's drag never arrived (the
		terminal dropped it): forget any half-finished drag state."""
		pass


# modifier prefixes of mouse bindings: Tk state bit → spellings
_MOUSE_MOD_NAMES = (
	(STATE_CONTROL,	('Control',)),
	(STATE_ALT,	('Alt', 'Mod1')),
	(STATE_SHIFT,	('Shift',)),
)


def _modifierPrefixes(state) -> list:
	"""Return the 'Mod-…-' binding prefixes matching the modifier *state*,
	most specific first: like Tk a binding may leave out modifiers that
	are held (Shift-click fires <Button-1> when <Shift-1> is not bound),
	but a binding asking for a modifier that is not held never matches."""
	held = [(bit, names) for bit, names in _MOUSE_MOD_NAMES if state & bit]
	result = []
	for n in range(len(held), 0, -1):
		for subset in _itertools.combinations(held, n):
			for combo in _itertools.product(*(names for _, names in subset)):
				for perm in _itertools.permutations(combo):
					result.append('-'.join(perm) + '-')
	return result


def _mouseEventNames(bstate, dragging) -> list:
	"""Return the binding names (in firing order) for a curses bstate.

	Each entry is a list of alternatives, most specific first; with
	Shift/Control/Alt held the modified spellings (<Shift-Button-1>,
	<Control-B1-Motion> …) come before the plain ones.
	"""
	names    = _mouseEventNamesPlain(bstate, dragging)
	prefixes = _modifierPrefixes(mouseState(bstate))
	if not prefixes:
		return names
	return [[f'<{p}{a[1:]}' for p in prefixes for a in alts] + alts
		for alts in names]


def _mouseEventNamesPlain(bstate, dragging) -> list:
	"""_mouseEventNames() without the modifier prefixes."""
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
	evt.x		= (mx - widget._x) * PX
	evt.y		= (my - widget._y) * PY
	evt.x_root	= mx * PX
	evt.y_root	= my * PY
	if evt.type == 'Motion' and widget._dragging():
		evt.state |= STATE_BUTTON1	# <B1-Motion>
	return evt


def _newKeyEvent(widget, key):
	evt		= KeyEvent(key)
	evt.widget	= widget
	return evt
