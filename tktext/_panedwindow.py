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

"""PanedWindow: children side by side (or stacked) with draggable sashes.

Mirrors tkinter.PanedWindow (add/forget/panes/paneconfigure/sash_place)
and ttk.Panedwindow (add/insert/forget/panes/pane/sashpos).  Each sash is
one character cell ('│' horizontal, '─' vertical) and can be dragged with
the mouse.
"""
from ._core import Widget, _addStr, _int, _initArgs, _cellsX, _cellsY, TclError
from . import _core
from ._events import B1_PRESS, MOTION
from ._frame import Frame


class PanedWindow(Frame):
	"""tkinter.PanedWindow."""

	_GEO = 'panedwindow'

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		self._panes	= []	# children in order
		self._sashPos	= {}	# sash index -> user position (offset in cells)
		self._dragSash	= None
		super().__init__(parent)
		self._opts.update({
			'orient':	'horizontal',
			'sashwidth':	1,
			'showhandle':	False,
			'sashrelief':	'flat',
			'opaqueresize':	True,
		})
		if kwargs:
			PanedWindow.configure(self, **kwargs)

	def _horizontal(self) -> bool:
		return str(self._opts.get('orient', 'horizontal')).startswith('h')

	# ------------------------------------------------------------------
	# Pane management
	# ------------------------------------------------------------------

	def add(self, child, **kw):
		if child in self._panes:
			self._panes.remove(child)
		pos = len(self._panes)
		if 'before' in kw and kw['before'] in self._panes:
			pos = self._panes.index(kw.pop('before'))
		elif 'after' in kw and kw['after'] in self._panes:
			pos = self._panes.index(kw.pop('after')) + 1
		self._panes.insert(pos, child)
		info = {'weight': 0, 'minsize': 0, 'stretch': 'last', 'sticky': 'nsew'}
		info.update(kw)
		child._setManager(self._GEO, info)
		self._markDirty()

	def insert(self, pos, child, **kw):
		if pos == 'end':
			return self.add(child, **kw)
		if isinstance(pos, Widget):
			pos = self._panes.index(pos)
		if child in self._panes:
			self._panes.remove(child)
		self._panes.insert(int(pos), child)
		info = {'weight': 0, 'minsize': 0, 'stretch': 'last', 'sticky': 'nsew'}
		info.update(kw)
		child._setManager(self._GEO, info)
		self._markDirty()

	def _pane(self, child):
		"""Pane widget from a widget, its path name or its index"""
		if isinstance(child, int):
			return self._panes[child]
		if isinstance(child, str):
			for p in self._panes:
				if str(p) == child: return p
		return child

	def forget(self, child):
		child = self._pane(child)
		if child in self._panes:
			self._panes.remove(child)
			child._forget()
			self._sashPos.clear()
			self._markDirty()

	remove = forget

	def _childDestroyed(self, child):
		if child in self._panes:
			self._panes.remove(child)
			self._sashPos.clear()

	def panes(self):
		return [str(p) for p in self._panes]

	def paneconfigure(self, child, cnf=None, **kw):
		if cnf:
			kw.update(cnf)
		child = self._pane(child)
		if child not in self._panes:
			raise TclError(f'{child} not managed by {self}')
		if not kw:
			return dict(child._geoInfo)
		child._geoInfo.update(kw)
		self._markDirty()

	paneconfig = paneconfigure

	def panecget(self, child, option):
		return self._pane(child)._geoInfo.get(option, '')

	def pane(self, pane, option=None, **kw):
		"""ttk: query or modify the options of *pane*."""
		pane = self._pane(pane)
		if option is not None:
			return pane._geoInfo.get(option, '')
		if kw:
			pane._geoInfo.update(kw)
			self._markDirty()
			return None
		return dict(pane._geoInfo)

	# ------------------------------------------------------------------
	# Sashes
	# ------------------------------------------------------------------

	def _sashCells(self):
		"""Return the offsets (along the paned axis, relative to the inner
		area) of each sash, computed by the last layout."""
		return getattr(self, '_sashes', [])

	def _unit(self):
		return _core.PX if self._horizontal() else _core.PY

	def _sashOffset(self, index) -> int:
		"""Offset of sash *index* along the paned axis (cells, relative to
		the inner area).  Like Tk a sash exists between every two panes
		even before the first layout (e.g. a notebook page never shown):
		then it is the placed position or follows the requested sizes."""
		panes = [c for c in self._panes if not c._destroyed]
		if not 0 <= index < len(panes) - 1:
			raise TclError(f'invalid sash index {index}')
		offs = self._sashCells()
		if index < len(offs):
			return offs[index]
		if index in self._sashPos:
			return self._sashPos[index]
		return sum(self._paneReq(c)[0] for c in panes[:index + 1]) + index

	def sash_coord(self, index):
		off = self._sashOffset(int(index))
		if self._horizontal():
			return (off * _core.PX, 0)
		return (0, off * _core.PY)

	def sash_place(self, index, x, y):
		pos = x if self._horizontal() else y
		self._sashPos[int(index)] = int(int(pos) / self._unit())
		self._markDirty()

	def sashpos(self, index, newpos=None):
		"""ttk: query or set the position of sash *index*."""
		if newpos is not None:
			self._sashPos[int(index)] = int(int(newpos) / self._unit())
			self._markDirty()
		offs = self._sashCells()
		return offs[index] * self._unit() if 0 <= index < len(offs) else 0

	def sash(self, *args):
		if args and args[0] == 'place':
			return self.sash_place(*args[1:])
		if args and args[0] == 'coord':
			return self.sash_coord(*args[1:])
		return None

	def identify(self, x, y):
		axis = int(x) if self._horizontal() else int(y)
		for i, off in enumerate(self._sashCells()):
			if off == axis:
				return (i, 'sash')
		return ''

	def proxy_coord(self):
		return (0, 0)

	def proxy_forget(self):
		pass

	def proxy_place(self, x, y):
		pass

	# ------------------------------------------------------------------
	# Layout
	# ------------------------------------------------------------------

	@staticmethod
	def _hidden(child):
		hide = child._geoInfo.get('hide', False)
		if isinstance(hide, str):
			return hide.lower() in ('1', 'true', 'yes', 'on')
		return bool(hide)

	def _visiblePanes(self):
		"""Panes shown: like Tk a hidden pane takes no space and no sash"""
		return [c for c in self._panes if not c._destroyed and not self._hidden(c)]

	def _paneReq(self, child):
		# like Tk an explicit pane width/height replaces the requested size
		w, h = child._preferredSize()
		info = child._geoInfo
		if info.get('width'):
			w = _cellsX(info['width'])
		if info.get('height'):
			h = _cellsY(info['height'])
		return (w, h) if self._horizontal() else (h, w)

	def _preferredSize(self):
		panes = self._visiblePanes()
		if not panes:
			return super()._preferredSize()
		along  = sum(self._paneReq(c)[0] for c in panes) + len(panes) - 1
		across = max(self._paneReq(c)[1] for c in panes)
		bd     = self._cfgBorder()
		ow     = _int(self._opts.get('width'))
		oh     = _int(self._opts.get('height'))
		if self._horizontal():
			w, h = along, across
		else:
			w, h = across, along
		if not self._propagate:
			w, h = ow or w, oh or h
		return (max(w, ow if not self._propagate else 0) + 2 * bd,
			max(h, oh if not self._propagate else 0) + 2 * bd)

	def _layoutChildren(self):
		super()._layoutChildren()
		for c in self._panes:
			if not c._destroyed and self._hidden(c):
				c._unmapTree()
		panes = self._visiblePanes()
		inner = self._innerGeom()
		horiz = self._horizontal()
		total = inner._width if horiz else inner._height
		cross = inner._height if horiz else inner._width
		n     = len(panes)
		self._sashes = []
		if n == 0 or total <= 0 or cross <= 0:
			for c in panes:
				c._unmapTree()
			return
		avail = max(0, total - (n - 1))
		sizes = [self._paneReq(c)[0] for c in panes]
		# distribute extra (or missing) space by weight; tk default: last
		extra   = avail - sum(sizes)
		weights = [_int(c._geoInfo.get('weight')) for c in panes]
		if not any(weights):
			weights = [0] * n
			for i, c in enumerate(panes):
				if str(c._geoInfo.get('stretch', 'last')) in ('always', 'first' if i == 0 else 'x'):
					weights[i] = 1
			if not any(weights):
				weights[-1] = 1
		if extra > 0:
			wsum = sum(weights)
			for i in range(n):
				add = extra * weights[i] // wsum
				sizes[i] += add
			sizes[weights.index(max(weights))] += avail - sum(sizes)
		elif extra < 0:
			# shrink from the last panes first, keeping minsize
			short = -extra
			for i in reversed(range(n)):
				minsize = panes[i]._geoInfo.get('minsize') or 0
				minsize = _cellsX(minsize) if horiz else _cellsY(minsize)
				take    = min(short, max(0, sizes[i] - max(1, minsize)))
				sizes[i] -= take
				short    -= take
			if short > 0:
				sizes = [max(0, s - short // n) for s in sizes]
		# user positioned sashes
		pos = 0
		for i in range(n - 1):
			if i in self._sashPos:
				want  = max(pos, min(self._sashPos[i], avail + i - 1))
				delta = want - (pos + sizes[i])
				sizes[i] += delta
				sizes[i + 1] -= delta
				if sizes[i + 1] < 0:
					sizes[i] += sizes[i + 1]
					sizes[i + 1] = 0
			pos += sizes[i] + 1
		pos = 0
		for i, c in enumerate(panes):
			size = max(0, sizes[i])
			if horiz:
				c._doLayout(inner._x + pos, inner._y, size, cross)
			else:
				c._doLayout(inner._x, inner._y + pos, cross, size)
			if size <= 0:
				c._unmapTree()
			elif hasattr(c, '_layoutChildren'):
				c._layoutChildren()
			pos += size
			if i < n - 1:
				self._sashes.append(pos)
				pos += 1

	# ------------------------------------------------------------------
	# Rendering / mouse
	# ------------------------------------------------------------------

	def render(self, scr):
		super().render(scr)
		if not self._isMapped():
			return
		inner = self._innerGeom()
		attr  = self._getAttr()
		for off in self._sashCells():
			if self._horizontal():
				for j in range(inner._height):
					_addStr(scr, inner._y + j, inner._x + off, '│', attr)
			else:
				_addStr(scr, inner._y + off, inner._x, '─' * inner._width, attr)

	def _dragLost(self):
		self._dragSash = None

	def _handleMouse(self, mx, my, bstate):
		inner = self._innerGeom()
		axis  = (mx - inner._x) if self._horizontal() else (my - inner._y)
		if bstate & B1_PRESS and not bstate & MOTION:
			self._dragSash = None
			for i, off in enumerate(self._sashCells()):
				if off == axis:
					self._dragSash = i
			return self._dragSash is not None
		if self._dragSash is not None and self._dragging():
			self._sashPos[self._dragSash] = axis
			for i, off in enumerate(self._sashCells()):
				self._sashPos.setdefault(i, off)
			self._markDirty()
			return True
		if not self._dragging():
			self._dragSash = None
		return False

	# focus/hit testing: panes are managed children
	def _getAllFocusable(self):
		return super()._getAllFocusable()


class Panedwindow(PanedWindow):
	"""ttk.Panedwindow: vertical by default."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		kwargs.setdefault('orient', 'vertical')
		super().__init__(parent, **kwargs)
