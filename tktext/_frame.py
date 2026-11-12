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

from ._core import Widget, _fillRect, _drawBorder, _addStr, _int, _cellsX, _cellsY, _initArgs
from ._layout import doPackLayout, doGridLayout, doPlaceLayout, \
	packPreferredSize, gridPreferredSize


class Frame(Widget):
	"""Container widget.  Supports pack, grid, and place geometry managers
	for its children.  Mirrors tkinter.Frame / tkinter.ttk.Frame."""

	_pixelSize = True

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		# Per-row / per-column configuration for grid manager
		self._rowCfg = {}
		self._colCfg = {}
		super().__init__(parent)
		self._opts.update({
			'text':		'',	# LabelFrame-style caption on the border
			'labelanchor':	'nw',
			'takefocus':	False,
		})
		if kwargs:
			Frame.configure(self, **kwargs)

	# ------------------------------------------------------------------
	# Grid configuration
	# ------------------------------------------------------------------

	def _configureIndex(self, table, index, kwargs):
		if isinstance(index, (tuple, list)):
			indices = index
		elif isinstance(index, str) and index == 'all':
			indices = range(64)
		else:
			indices = [index]
		if not kwargs:
			return dict(table.get(_int(indices[0]), {})) if indices else {}
		conv = _cellsX if table is self._colCfg else _cellsY
		for key in ('minsize', 'pad'):
			if key in kwargs:
				kwargs[key] = conv(kwargs[key], key == 'pad')
		for i in indices:
			table.setdefault(_int(i), {}).update(kwargs)
		self._markDirty()
		return None

	def columnconfigure(self, col, cnf=None, **kwargs):
		"""Configure grid column *col*.  Accepts weight, minsize, pad."""
		if cnf:
			kwargs.update(cnf)
		return self._configureIndex(self._colCfg, col, kwargs)

	def rowconfigure(self, row, cnf=None, **kwargs):
		"""Configure grid row *row*.  Accepts weight, minsize, pad."""
		if cnf:
			kwargs.update(cnf)
		return self._configureIndex(self._rowCfg, row, kwargs)

	# camelCase aliases
	columnConfigure		= columnconfigure
	rowConfigure		= rowconfigure
	grid_columnconfigure	= columnconfigure
	grid_rowconfigure	= rowconfigure

	def columnkeyword(self, col):
		return dict(self._colCfg.get(col, {}))

	def rowkeyword(self, row):
		return dict(self._rowCfg.get(row, {}))

	def gridSize(self):
		"""Return (columns, rows) of the grid."""
		gridded = [c._geoInfo for c in self._children if c._geoManager == 'grid']
		if not gridded:
			return (0, 0)
		return (max(o['column'] + o.get('columnspan', 1) for o in gridded),
			max(o['row'] + o.get('rowspan', 1) for o in gridded))

	grid_size = gridSize

	def gridSlaves(self, row=None, column=None):
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

	def packSlaves(self):
		return [c for c in self._children if c._geoManager == 'pack']

	grid_slaves	= gridSlaves
	pack_slaves	= packSlaves

	# ------------------------------------------------------------------
	# Layout
	# ------------------------------------------------------------------

	def _managed(self):
		packed  = [(c, c._geoInfo) for c in self._children if c._geoManager == 'pack']
		gridded = [(c, c._geoInfo) for c in self._children if c._geoManager == 'grid']
		placed  = [(c, c._geoInfo) for c in self._children if c._geoManager == 'place']
		return packed, gridded, placed

	def _innerGeom(self):
		bd = self._border()
		return _InnerGeom(self._x + bd, self._y + bd,
			max(0, self._width - 2*bd), max(0, self._height - 2*bd))

	def _layoutChildren(self):
		"""Compute positions for all children managed by any geometry manager."""
		packed, gridded, placed = self._managed()
		inner = self._innerGeom()

		if packed:
			doPackLayout(inner, packed)
		if gridded:
			doGridLayout(inner, gridded, self._rowCfg, self._colCfg)
		if placed:
			doPlaceLayout(inner, placed)

	def _preferredSize(self):
		bd = self._cfgBorder()
		ow = _int(self._opts.get('width'))
		oh = _int(self._opts.get('height'))
		packed, gridded, _ = self._managed()
		pw, ph = packPreferredSize(packed)
		gw, gh = gridPreferredSize(gridded, self._rowCfg, self._colCfg)
		cw = max(pw, gw)
		ch = max(ph, gh)
		# Like tkinter: with managed children the requested size follows
		# them (geometry propagation); otherwise width/height are used.
		if (not packed and not gridded) or not self._propagate:
			cw, ch = ow, oh
		return (max(cw, 1) + 2*bd, max(ch, 1) + 2*bd)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return
		attr = self._getAttr()
		bd   = self._border()

		# Background fill (Tk always paints a frame's background)
		if self._color('bg'):
			_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)

		# Border
		relief = self._opts.get('relief', 'flat')
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._height, self._width, relief, attr)

		text = str(self._opts.get('text') or '')
		if text and self._width > 4:
			label = f' {text} '[:self._width - 2]
			anchor = self._opts.get('labelanchor', 'nw')
			if 'e' in anchor:
				lx = self._x + self._width - 1 - len(label)
			elif anchor in ('n', 's'):
				lx = self._x + (self._width - len(label)) // 2
			else:
				lx = self._x + 1
			ly = self._y + self._height - 1 if anchor.startswith('s') else self._y
			_addStr(scr, ly, lx, label, attr)

		self._renderChildren(scr)


class LabelFrame(Frame):
	"""Frame with a caption drawn on its border.  Mirrors tkinter.LabelFrame."""

	_keepBorder = True

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		kwargs.setdefault('relief',      'single')
		kwargs.setdefault('borderwidth', 1)
		super().__init__(parent, **kwargs)

	def _preferredSize(self):
		w, h = super()._preferredSize()
		return (max(w, len(str(self._opts.get('text') or '')) + 4), h)


# ---------------------------------------------------------------------------
# Helper: an object that acts like a widget for layout purposes but exposes
# the inner (content) rectangle of a bordered frame.
# ---------------------------------------------------------------------------

class _InnerGeom:
	def __init__(self, x, y, w, h):
		self._x = x
		self._y = y
		self._width = w
		self._height = h
