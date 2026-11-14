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
# Date:   14-Nov-2026

"""Crude pixel images (rasters) drawn with half-block characters.

A widget may carry an RGB raster (``widget.rasterImage(data, w, h)``,
normally ``w x h = cols x 2*rows`` from ``widget.rasterSize()``).  Every
cell shows two vertical pixels as ``'▀'``: foreground = top pixel,
background = bottom pixel.

Graphics modes (``TKTEXT_GRAPHICS`` or ``install(graphics=…)``):

curses		colours are reduced to fit the colour pairs reserved for the
		rasters (Python curses passes the pair in 8 bits of the
		attribute, so there are at most 255 pairs for everything).
truecolor	the cells are written to curses as markers; after every
		refresh the visible markers (not covered by menus or dialogs)
		are overwritten straight on the terminal with 24-bit colours.
auto		truecolor when $COLORTERM says so, curses otherwise.
"""
import os
import curses
from collections import Counter

from ._colors import _rgb256, _BASIC_RGB

HALF		= '▀'
SHADES		= ' ░▒▓█'
RASTER_FIRST	= 160			# first colour pair reserved for rasters
MARKER_PAIR	= 255			# truecolor placeholder pair
RASTER_LAST	= MARKER_PAIR - 1	# last pair of the curses rasters

_CUBE		= (0, 95, 135, 175, 215, 255)
defaultMode	= 'curses'		# install(graphics=…), TKTEXT_GRAPHICS wins


def graphicsMode(mode=None) -> str:
	"""Resolve a graphics mode name ('curses', 'truecolor', 'auto')."""
	mode = (mode or os.environ.get('TKTEXT_GRAPHICS') or defaultMode).lower()
	if mode == 'auto':
		colorterm = os.environ.get('COLORTERM', '').lower()
		mode = 'truecolor' if colorterm in ('truecolor', '24bit') else 'curses'
	if mode not in ('curses', 'truecolor'):
		raise ValueError(f'unknown graphics mode {mode!r}')
	return mode


def indexRGB(index: int):
	"""RGB of a terminal colour index (16 basic, 6x6x6 cube, grey ramp)."""
	if index < 16:
		return _BASIC_RGB[index]
	if index < 232:
		i = index - 16
		return (_CUBE[i // 36], _CUBE[(i // 6) % 6], _CUBE[i % 6])
	v = 8 + 10 * (index - 232)
	return (v, v, v)


def _distance(a, b) -> int:
	return (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2


def quantize(cells, budget: int, rgbOf=indexRGB):
	"""Reduce the (top, bottom) colour combinations of *cells* to at most
	*budget*: the most frequent ones are kept, the others are replaced by
	the nearest kept combination.  @return (cells, combos) where combos is
	the list of distinct combinations used (index = order of first use)."""
	counts = Counter(cells)
	if len(counts) > budget > 0:
		kept    = [c for c, _ in counts.most_common(budget)]
		keptRGB = [(rgbOf(t), rgbOf(b)) for t, b in kept]
		remap   = {}
		for combo in counts:
			if combo in remap:
				continue
			t, b = rgbOf(combo[0]), rgbOf(combo[1])
			best = min(range(len(kept)), key=lambda i:
				_distance(t, keptRGB[i][0]) + _distance(b, keptRGB[i][1]))
			remap[combo] = kept[best]
		for c in kept:
			remap[c] = c
		cells = [remap[c] for c in cells]
	elif budget <= 0:
		cells = [(-1, -1)] * len(cells)
	combos = list(dict.fromkeys(cells))
	return cells, combos


class RasterRenderer:
	"""Draws the widget rasters of one application (owned by Tk)."""

	def __init__(self, colors, mode=None):
		self._colors	= colors
		self.mode	= graphicsMode(mode)
		self.active	= False		# truecolor only with a real terminal
		self.colored	= False		# colour pairs up to MARKER_PAIR usable
		self._drawn	= []		# truecolor: (y, x, rows) of this frame
		self._shadow	= {}		# truecolor: (y,x) -> (top,bot) shown
		self._pairDefs	= {}		# pair number -> (fg, bg) defined
		self._nextPair	= RASTER_FIRST
		self._budget	= RASTER_LAST - RASTER_FIRST + 1
		self._rgbCache	= {}
		self.write	= None		# truecolor output, bytes -> None

	# ------------------------------------------------------------------
	def start(self, scr, write) -> None:
		"""Enable the truecolor overlay on a real screen."""
		self.write   = write
		self.colored = self._colors._ready and \
				getattr(curses, 'COLOR_PAIRS', 0) > MARKER_PAIR
		self.active  = self.mode == 'truecolor' and self.colored
		if self.active:
			self._definePair(MARKER_PAIR, -1, -1)
			try:
				scr.idcok(False)	# no insert/delete char over the overlay
			except (curses.error, AttributeError):
				pass

	def invalidate(self) -> None:
		"""The terminal was cleared: re-emit every visible cell."""
		self._shadow.clear()

	def beginFrame(self, count: int) -> None:
		"""Start a redraw with *count* rasters sharing the colour pairs."""
		self._drawn.clear()
		self._nextPair	= RASTER_FIRST
		self._budget	= (RASTER_LAST - RASTER_FIRST + 1) // max(1, count)

	# ------------------------------------------------------------------
	def _definePair(self, pair, fg, bg) -> None:
		if self._pairDefs.get(pair) == (fg, bg):
			return
		try:
			curses.init_pair(pair, fg, bg)
			self._pairDefs[pair] = (fg, bg)
		except (curses.error, ValueError):
			pass

	def _pairAttr(self, pair) -> int:
		try:
			return curses.color_pair(pair)
		except curses.error:
			return 0

	def _colorIndex(self, rgb) -> int:
		"""Terminal colour index nearest to *rgb*."""
		idx = self._rgbCache.get(rgb)
		if idx is None:
			if self._colors._nColors >= 256:
				idx = _rgb256(*rgb)
			else:
				limit = 16 if self._colors._nColors >= 16 else 8
				idx = min(range(limit), key=lambda i: _distance(rgb, _BASIC_RGB[i]))
			self._rgbCache[rgb] = idx
		return idx

	# ------------------------------------------------------------------
	@staticmethod
	def sample(data, width, height, cols, rows):
		"""@return rows of (topRGB, bottomRGB) for a cols x rows area,
		sampling the width x height RGB *data* (nearest pixel, so a raster
		of a stale size still fills the widget)."""
		result = []
		ph = 2 * rows
		for cy in range(rows):
			yt = (2*cy) * height // ph
			yb = (2*cy+1) * height // ph
			ot = yt * width * 3
			ob = yb * width * 3
			row = []
			for cx in range(cols):
				px = cx * width // cols * 3
				row.append((tuple(data[ot+px:ot+px+3]), tuple(data[ob+px:ob+px+3])))
			result.append(row)
		return result

	def render(self, scr, widget, y, x, rows, cols) -> None:
		"""Draw the raster of *widget* on the rows x cols area at (y, x)."""
		data, width, height = widget._rasterData
		if rows <= 0 or cols <= 0 or not data or width <= 0 or height <= 0:
			return
		if len(data) < width * height * 3:
			return
		cache = widget._rasterCache
		key   = (id(data), width, height, rows, cols)
		if cache is None or cache[0] != key:
			cache = (key, self.sample(data, width, height, cols, rows), None)
			widget._rasterCache = cache
		rgbRows = cache[1]

		if self.active:
			attr = self._pairAttr(MARKER_PAIR)
			for cy, row in enumerate(rgbRows):
				_put(scr, y+cy, x, HALF * len(row), attr)
			self._drawn.append((y, x, rgbRows))
			return

		if not self.colored:
			for cy, row in enumerate(rgbRows):
				line = ''.join(SHADES[min(4, (sum(t)+sum(b)) * 5 // 1531)]
						for t, b in row)
				_put(scr, y+cy, x, line, 0)
			return

		# curses: quantize to the pair budget of this raster
		budget = min(self._budget, RASTER_LAST + 1 - self._nextPair)
		qkey   = (budget, self._colors._nColors)
		if cache[2] is None or cache[2][0] != qkey:
			flat  = [(self._colorIndex(t), self._colorIndex(b))
					for row in rgbRows for t, b in row]
			cells, combos = quantize(flat, budget)
			cache = (key, rgbRows, (qkey, cells, combos))
			widget._rasterCache = cache
		_, cells, combos = cache[2]
		attrs = {}
		for combo in combos:
			pair = self._nextPair
			self._nextPair += 1
			if combo == (-1, -1):
				attrs[combo] = 0
				continue
			self._definePair(pair, combo[0], combo[1])
			attrs[combo] = self._pairAttr(pair)
		i = 0
		for cy in range(len(rgbRows)):
			cx = 0
			while cx < cols:
				# runs of the same pair in one addstr
				combo = cells[i]
				n = 1
				while cx+n < cols and cells[i+n] == combo:
					n += 1
				_put(scr, y+cy, x+cx, HALF * n, attrs[combo])
				cx += n
				i  += n

	# ------------------------------------------------------------------
	def flush(self, scr) -> None:
		"""Truecolor: after scr.refresh() overwrite the visible marker
		cells whose colours differ from what the terminal shows."""
		if not self.active or self.write is None:
			return
		marker = self._pairAttr(MARKER_PAIR)
		shadow = {}
		out    = []
		for y0, x0, rows in self._drawn:
			for cy, row in enumerate(rows):
				y   = y0 + cy
				run = None	# x of the current run
				for cx, cell in enumerate(row):
					x = x0 + cx
					if not _isMarker(scr, y, x, marker):
						run = None
						continue
					shadow[(y, x)] = cell
					if self._shadow.get((y, x)) == cell:
						run = None
						continue
					if run is None or run != x:
						out.append(f'\033[{y+1};{x+1}H')
					t, b = cell
					out.append(f'\033[38;2;{t[0]};{t[1]};{t[2]};'
						f'48;2;{b[0]};{b[1]};{b[2]}m{HALF}')
					run = x + 1
		self._shadow = shadow
		if out:
			# DECSC/DECRC keep curses' cursor and rendition intact
			self.write(('\0337' + ''.join(out) + '\0338').encode('utf-8'))


def _put(scr, y, x, s, attr) -> None:
	try:
		sh, sw = scr.getmaxyx()
	except Exception:
		return
	if y < 0 or y >= sh or x >= sw:
		return
	s = s[:sw - x]
	if not s:
		return
	try:
		scr.addstr(y, x, s, attr)
	except curses.error:
		pass


def _isMarker(scr, y, x, marker) -> bool:
	"""True when the cell still holds the raster marker (nothing drawn on
	top of it in this frame)."""
	try:
		ch = scr.inch(y, x)
	except curses.error:
		return False
	return (ch & curses.A_ATTRIBUTES) == marker
