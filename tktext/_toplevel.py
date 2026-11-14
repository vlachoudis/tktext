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

"""Toplevel windows and the window-manager (wm_*) API.

The terminal is the "display": windows are drawn on top of each other in
stacking order.

* a normal Toplevel (not transient, not override-redirect) is maximised:
  it covers the whole terminal with its own title bar (and menubar) on
  row 0, like the root window;
* a transient Toplevel (a dialog) gets its requested size, centred over
  its master, framed with a double-line border carrying the title;
* an override-redirect Toplevel (popups, balloons, drop-down lists) is
  placed exactly where wm_geometry() puts it, without decoration.

Pixel geometries given to wm_geometry() are interpreted as characters and
clamped to the terminal; sizes larger than the terminal are ignored.
"""

import re

from ._core import _drawBorder, _fillRect, _addStr, _initArgs
from ._frame import Frame


_GEOMETRY = re.compile(r'^\s*(?:=?(\d+)x(\d+))?(?:([+-])(-?\d+)([+-])(-?\d+))?\s*$')


def _parseGeometry(spec):
	"""Return (w, h, x, y) from 'WxH+X+Y' (missing parts are None)."""
	m = _GEOMETRY.match(str(spec))
	if not m:
		return None
	w, h, sx, x, sy, y = m.groups()
	w = int(w) if w else None
	h = int(h) if h else None
	if x is not None:
		x = int(x) if sx == '+' else -int(x) - 1
		y = int(y) if sy == '+' else -int(y) - 1
	return (w, h, x, y)


class Wm:
	"""Window-manager methods shared by Tk and Toplevel (tkinter.Wm)."""

	def _wmInit(self):
		self._title		= ''
		self._wmState		= 'normal'
		self._transientFor	= None
		self._override		= False
		self._geomReq		= None	# (w, h, x, y) requested by wm_geometry
		self._ownMenuBar	= None
		self._protocols		= {}
		self._wmAttributes	= {}
		self._needFocus		= True	# focus moves in when first mapped
		self._lastFocus		= None	# focus to restore when re-activated

	# ------------------------------------------------------------------

	def wm_title(self, string=None):
		if string is None:
			return self._title
		self._title = str(string)
		self._markDirty()

	title = wm_title

	def wm_geometry(self, newGeometry=None):
		"""Geometry 'WxH+X+Y' (pixels in pixel mode)."""
		from . import _core
		px, py = _core.PX, _core.PY
		if newGeometry is None:
			return (f'{self._width * px}x{self._height * py}'
				f'+{self._x * px}+{self._y * py}')
		geom = _parseGeometry(newGeometry)
		if geom is not None:
			w, h, x, y = geom
			self._geomReq = (
				None if w is None else max(1, round(w / px)),
				None if h is None else max(1, round(h / py)),
				None if x is None else int(x / px),
				None if y is None else int(y / py))
			self._markDirty()
		return ''

	geometry = wm_geometry

	def wm_transient(self, master=None):
		if master is None:
			return self._transientFor or ''
		self._transientFor = master
		self._markDirty()

	transient = wm_transient

	def wm_overrideredirect(self, boolean=None):
		if boolean is None:
			return self._override
		self._override = bool(boolean) and boolean not in ('0', 'false')
		self._markDirty()

	overrideredirect = wm_overrideredirect

	def wm_withdraw(self):
		self._setWmState('withdrawn')

	def wm_deiconify(self):
		self._setWmState('normal')

	def wm_iconify(self):
		self._setWmState('iconic')

	withdraw	= wm_withdraw
	deiconify	= wm_deiconify
	iconify		= wm_iconify

	def wm_state(self, newstate=None):
		if newstate is None:
			return self._wmState
		self._setWmState('normal' if newstate == 'zoomed' else str(newstate))

	state = wm_state

	def _setWmState(self, state):
		if state == self._wmState:
			return
		self._wmState = state
		app = self._getApp()
		if state == 'normal':
			self._needFocus = True
			if app is not None:
				app._raiseWindow(self)
			self._dispatchStructure('<Map>')
		else:
			self._dispatchStructure('<Unmap>')
		self._markDirty()

	def _dispatchStructure(self, sequence):
		from ._events import Event
		evt		= Event()
		evt.widget	= self
		evt.type	= sequence.strip('<>')
		self._dispatch(sequence, evt)

	def wm_protocol(self, name=None, func=None):
		if name is None:
			return tuple(self._protocols.keys())
		if func is None:
			return self._protocols.get(name, '')
		self._protocols[name] = func

	protocol = wm_protocol

	def wm_attributes(self, *args, **kw):
		if kw:
			self._wmAttributes.update(kw)
			return ''
		if not args:
			return tuple(x for k, v in self._wmAttributes.items()
				for x in (f'-{k}', v))
		if len(args) == 1:
			return self._wmAttributes.get(str(args[0]).lstrip('-'), '')
		for i in range(0, len(args) - 1, 2):
			self._wmAttributes[str(args[i]).lstrip('-')] = args[i + 1]
		return ''

	attributes = wm_attributes

	def _wmIgnore(self, *args, **kw):
		return ''

	wm_resizable	= resizable	= _wmIgnore
	wm_minsize	= minsize	= _wmIgnore
	wm_maxsize	= maxsize	= _wmIgnore
	wm_iconbitmap	= iconbitmap	= _wmIgnore
	wm_iconphoto	= iconphoto	= _wmIgnore
	wm_iconname	= iconname	= _wmIgnore
	wm_iconmask	= iconmask	= _wmIgnore
	wm_iconposition	= iconposition	= _wmIgnore
	wm_iconwindow	= iconwindow	= _wmIgnore
	wm_group	= group		= _wmIgnore
	wm_client	= client	= _wmIgnore
	wm_colormapwindows = colormapwindows = _wmIgnore
	wm_command	= command	= _wmIgnore
	wm_focusmodel	= focusmodel	= _wmIgnore
	wm_positionfrom	= positionfrom	= _wmIgnore
	wm_sizefrom	= sizefrom	= _wmIgnore
	wm_aspect	= aspect	= _wmIgnore
	wm_grid		= _wmIgnore
	wm_manage	= _wmIgnore
	wm_forget	= _wmIgnore

	def wm_frame(self):
		return self._w

	frame = wm_frame

	# ------------------------------------------------------------------
	# Placement helpers
	# ------------------------------------------------------------------

	def _placeWindow(self, how='', master=None):
		"""::tk::PlaceWindow: centring is the default anyway."""
		self._geomReq = None
		self._markDirty()

	def _isMaximised(self) -> bool:
		return not self._override and self._transientFor is None


class Toplevel(Wm, Frame):
	"""A separate window (mirrors tkinter.Toplevel)."""

	_isToplevel = True

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		self._wmInit()
		for key in ('screen', 'use', 'container', 'colormap', 'visual'):
			kwargs.pop(key, None)
		super().__init__(parent)
		self._opts['takefocus'] = False
		app = self._getApp()
		if app is not None:
			app._toplevels.append(self)
			self._title = app._title
		if kwargs:
			Toplevel.configure(self, **kwargs)

	def configure(self, cnf=None, **kwargs):
		if isinstance(cnf, str) or not (cnf or kwargs):
			return super().configure(cnf)
		kwargs.update(cnf or {})
		if 'menu' in kwargs:
			self._ownMenuBar = kwargs.pop('menu') or None
			self._markDirty()
			if not kwargs:
				return None
		kwargs.pop('class_', None)
		return super().configure(**kwargs) if kwargs else None

	config = configure

	def cget(self, key):
		if key == 'menu':
			return self._ownMenuBar or ''
		return super().cget(key)

	def destroy(self):
		app = self._getApp()
		super().destroy()
		if app is not None:
			if self in app._toplevels:
				app._toplevels.remove(self)
			if app._grab is not None and (app._grab is self or
					self._isAncestorOf(app._grab)):
				app._grab = None
			app._dirty = True

	def lift(self, aboveThis=None):
		app = self._getApp()
		if app is not None:
			app._raiseWindow(self)

	tkraise = wm_lift = lift

	def lower(self, belowThis=None):
		app = self._getApp()
		if app is not None and self in app._toplevels:
			app._toplevels.remove(self)
			app._toplevels.insert(0, self)
			app._dirty = True

	wm_lower = lower

	# ------------------------------------------------------------------
	# Geometry
	# ------------------------------------------------------------------

	def _viewable(self) -> bool:
		"""Mapped by the window manager (not withdrawn or iconified)."""
		return not self._destroyed and self._wmState == 'normal'

	def _decoration(self):
		"""Return (top, side) rows/columns used by the frame decoration."""
		if self._override:
			return (0, 0)
		if self._isMaximised():
			return (1, 0)
		return (1, 1)

	def _layoutWindow(self, screenW, screenH):
		"""Compute the window rectangle on a screenW x screenH terminal."""
		if not self._viewable():
			self._unmapTree()
			return
		top, side = self._decoration()
		if self._isMaximised():
			x, y, w, h = 0, 0, screenW, screenH
		else:
			pw, ph	= Frame._preferredSize(self)
			w	= pw + 2 * side
			h	= ph + top + side
			x = y	= None
			req	= self._geomReq
			if req is not None:
				rw, rh, rx, ry = req
				if rw is not None and rw + 2 * side <= screenW:
					w = rw + 2 * side
				if rh is not None and rh + top + side <= screenH:
					h = rh + top + side
				if rx is not None:
					x = rx if rx >= 0 else screenW + rx + 1 - w
					y = ry if ry >= 0 else screenH + ry + 1 - h
			w = max(1, min(w, screenW))
			h = max(1, min(h, screenH))
			if x is None:
				x, y = self._centre(w, h, screenW, screenH)
			x = max(0, min(x, screenW - w))
			y = max(0, min(y, screenH - h))
		self._doLayout(x, y, w, h)
		self._layoutChildren()

	def _centre(self, w, h, screenW, screenH):
		master = self._transientFor
		if master is not None and not getattr(master, '_destroyed', True):
			top = master.winfo_toplevel() if hasattr(master, 'winfo_toplevel') else None
			if top is not None and top._isMapped():
				return (top._x + (top._width - w) // 2,
					top._y + (top._height - h) // 2)
		return ((screenW - w) // 2, (screenH - h) // 2)

	def _innerGeom(self):
		from ._frame import _InnerGeom
		top, side = self._decoration()
		bd = self._border()
		return _InnerGeom(self._x + side + bd, self._y + top + bd,
			max(0, self._width - 2 * (side + bd)),
			max(0, self._height - top - side - 2 * bd))

	def _preferredSize(self):
		w, h = Frame._preferredSize(self)
		top, side = self._decoration()
		return (w + 2 * side, h + top + side)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return
		app	= self._getApp()
		attr	= self._getAttr()
		_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)
		top, side = self._decoration()
		if app is not None and self._isMaximised():
			app._drawTitleBar(scr, self)
		elif side:
			active = app is not None and app._activeWindow() is self
			if app is None:
				battr = attr
			elif active:
				battr = self._roleAttr('frame.active')
			else:
				battr = app._colors.getAttr('', self._color('bg'))
			_drawBorder(scr, self._y, self._x, self._height, self._width,
				'double' if active else 'single', battr)
			title = f' {self._title} '
			if self._width > 4:
				title = title[:self._width - 4]
				_addStr(scr, self._y, self._x + (self._width - len(title)) // 2,
					title, battr)
		bd = self._border()
		relief = self._opts.get('relief', 'flat')
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y + top, self._x + side,
				self._height - top - side, self._width - 2 * side, relief, attr)
		self._renderChildren(scr)
