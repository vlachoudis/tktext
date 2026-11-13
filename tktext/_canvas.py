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

"""Canvas: structured graphics on a character grid.

Mirrors the item API of tkinter.Canvas (create_*, coords, itemconfigure,
tags, find_*, bbox, move, delete, tag_bind, xview/yview …).  Coordinates
are character cells.  Rendering is necessarily approximate:

* text		drawn at its anchor point;
* rectangle	filled with the fill colour (background), outlined with
		box-drawing characters when it is at least 2x2 cells;
* line		horizontal/vertical runs drawn with ─ │, others with ·;
* oval/arc/polygon	their bounding box drawn as a filled rectangle;
* window	the embedded widget is laid out over its box;
* image/bitmap	a single placeholder glyph.
"""

import math

from ._core import Widget, _addStr, _fillRect, _int, _initArgs, \
	_callback, _newMouseEvent, _pixels
from . import _core


class _Item:
	__slots__ = ('id', 'type', 'coords', 'opts', 'tags')

	def __init__(self, iid, kind, coords, opts):
		self.id		= iid
		self.type	= kind
		self.coords	= coords
		self.opts	= opts
		tags		= opts.pop('tags', ()) or ()
		if isinstance(tags, str):
			tags = tags.split()
		self.tags	= list(tags)


def _flatCoords(args):
	out = []
	for a in args:
		if isinstance(a, (tuple, list)):
			out.extend(_flatCoords(a))
		else:
			out.append(float(_pixels(a)))
	return out


class Canvas(Widget):
	"""tkinter.Canvas on a character grid.

	Item coordinates are canvas units: pixels in pixel mode (one cell is
	_core.PX x _core.PY units), cells otherwise.
	"""
	_rendersChildren = True

	_clickFocus = False	# tkinter: clicking does not take the focus

	_pixelSize = True

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		self._canvasItems	= {}	# id -> _Item, insertion order = display list
		self._nextId	= 1
		self._tagBinds	= {}	# (tagOrId, sequence) -> [funcs]
		self._xOrigin	= 0
		self._yOrigin	= 0
		self._current	= None
		super().__init__(parent)
		self._opts.update({
			'width':		10,
			'height':		3,
			'scrollregion':		'',
			'xscrollcommand':	None,
			'yscrollcommand':	None,
			'confine':		True,
			'takefocus':		False,
			'highlightthickness':	0,
			'closeenough':		1.0,
		})
		if kwargs:
			Canvas.configure(self, **kwargs)

	# ------------------------------------------------------------------
	# Item creation
	# ------------------------------------------------------------------

	def _create(self, kind, args, kw):
		if args and isinstance(args[-1], dict):
			kw = {**args[-1], **kw}
			args = args[:-1]
		iid = self._nextId
		self._nextId += 1
		self._canvasItems[iid] = _Item(iid, kind, _flatCoords(args), dict(kw))
		if kind == 'window' and kw.get('window') is not None:
			win = kw['window']
			win._geoManager = 'canvas'
			win._geoInfo    = {}
		self._markDirty()
		return iid

	def create_arc(self, *args, **kw):	return self._create('arc', args, kw)
	def create_bitmap(self, *args, **kw):	return self._create('bitmap', args, kw)
	def create_image(self, *args, **kw):	return self._create('image', args, kw)
	def create_line(self, *args, **kw):	return self._create('line', args, kw)
	def create_oval(self, *args, **kw):	return self._create('oval', args, kw)
	def create_polygon(self, *args, **kw):	return self._create('polygon', args, kw)
	def create_rectangle(self, *args, **kw):return self._create('rectangle', args, kw)
	def create_text(self, *args, **kw):	return self._create('text', args, kw)
	def create_window(self, *args, **kw):	return self._create('window', args, kw)

	# ------------------------------------------------------------------
	# Item selection
	# ------------------------------------------------------------------

	def _find(self, tagOrId):
		"""Return the list of items matching a tag or id."""
		if tagOrId is None or tagOrId == '':
			return []
		if isinstance(tagOrId, int) or (isinstance(tagOrId, str) and tagOrId.isdigit()):
			it = self._canvasItems.get(int(tagOrId))
			return [it] if it else []
		if isinstance(tagOrId, (tuple, list)):
			result = []
			for t in tagOrId:
				result.extend(i for i in self._find(t) if i not in result)
			return result
		tag = str(tagOrId)
		if tag == 'all':
			return list(self._canvasItems.values())
		if tag == 'current':
			return [self._canvasItems[self._current]] if self._current in self._canvasItems else []
		return [it for it in self._canvasItems.values() if tag in it.tags]

	def find_all(self):
		return tuple(self._canvasItems.keys())

	def find_withtag(self, tagOrId):
		return tuple(it.id for it in self._find(tagOrId))

	def find_overlapping(self, x1, y1, x2, y2):
		result = []
		for it in self._canvasItems.values():
			bx = self._itemBox(it)
			if bx and bx[0] <= x2 and bx[2] >= x1 and bx[1] <= y2 and bx[3] >= y1:
				result.append(it.id)
		return tuple(result)

	def find_enclosed(self, x1, y1, x2, y2):
		result = []
		for it in self._canvasItems.values():
			bx = self._itemBox(it)
			if bx and bx[0] >= x1 and bx[2] <= x2 and bx[1] >= y1 and bx[3] <= y2:
				result.append(it.id)
		return tuple(result)

	def find_closest(self, x, y, halo=None, start=None):
		best, bestD = None, None
		for it in self._canvasItems.values():
			bx = self._itemBox(it)
			if not bx:
				continue
			dx = max(bx[0] - x, 0, x - bx[2])
			dy = max(bx[1] - y, 0, y - bx[3])
			d  = dx * dx + dy * dy
			if bestD is None or d <= bestD:
				best, bestD = it.id, d
		return (best,) if best is not None else ()

	def find_above(self, tagOrId):
		items = self._find(tagOrId)
		ids   = list(self._canvasItems.keys())
		if not items:
			return ()
		i = ids.index(items[-1].id)
		return (ids[i + 1],) if i + 1 < len(ids) else ()

	def find_below(self, tagOrId):
		items = self._find(tagOrId)
		ids   = list(self._canvasItems.keys())
		if not items:
			return ()
		i = ids.index(items[0].id)
		return (ids[i - 1],) if i > 0 else ()

	def find(self, *args):
		kind = args[0]
		return getattr(self, f'find_{kind}')(*args[1:])

	# ------------------------------------------------------------------
	# Item operations
	# ------------------------------------------------------------------

	def coords(self, tagOrId, *args):
		items = self._find(tagOrId)
		if not items:
			return []
		if not args:
			return list(items[0].coords)
		items[0].coords = _flatCoords(args)
		self._markDirty()
		return None

	def itemconfigure(self, tagOrId, cnf=None, **kw):
		if cnf:
			kw.update(cnf)
		items = self._find(tagOrId)
		if not kw:
			return {k: (k, '', '', '', v) for k, v in items[0].opts.items()} if items else {}
		for it in items:
			if 'tags' in kw:
				tags = kw['tags'] or ()
				it.tags = tags.split() if isinstance(tags, str) else list(tags)
			it.opts.update({k: v for k, v in kw.items() if k != 'tags'})
		self._markDirty()
		return None

	itemconfig = itemconfigure

	def itemcget(self, tagOrId, option):
		items = self._find(tagOrId)
		if not items:
			return ''
		if option == 'tags':
			return ' '.join(items[0].tags)
		return items[0].opts.get(option, '')

	def type(self, tagOrId):
		items = self._find(tagOrId)
		return items[0].type if items else None

	def gettags(self, tagOrId):
		items = self._find(tagOrId)
		return tuple(items[0].tags) if items else ()

	def addtag_withtag(self, newtag, tagOrId):
		for it in self._find(tagOrId):
			if newtag not in it.tags:
				it.tags.append(newtag)

	def addtag_all(self, newtag):
		self.addtag_withtag(newtag, 'all')

	def addtag(self, newtag, how, *args):
		if how == 'withtag':
			self.addtag_withtag(newtag, args[0])
		elif how == 'all':
			self.addtag_all(newtag)
		else:
			for iid in getattr(self, f'find_{how}')(*args):
				self.addtag_withtag(newtag, iid)

	def dtag(self, tagOrId, tagToDelete=None):
		tag = tagOrId if tagToDelete is None else tagToDelete
		for it in self._find(tagOrId):
			if tag in it.tags:
				it.tags.remove(tag)

	def delete(self, *tagsOrIds):
		for t in tagsOrIds:
			for it in self._find(t):
				win = it.opts.get('window') if it.type == 'window' else None
				if win is not None and not win._destroyed:
					win._geoManager = None
					win._unmapTree()
				self._canvasItems.pop(it.id, None)
		self._markDirty()

	def move(self, tagOrId, dx, dy):
		for it in self._find(tagOrId):
			c = it.coords
			for i in range(0, len(c) - 1, 2):
				c[i]     += float(dx)
				c[i + 1] += float(dy)
		self._markDirty()

	def moveto(self, tagOrId, x='', y=''):
		box = self.bbox(tagOrId)
		if not box:
			return
		dx = float(x) - box[0] if x != '' else 0
		dy = float(y) - box[1] if y != '' else 0
		self.move(tagOrId, dx, dy)

	def scale(self, tagOrId, xOrigin, yOrigin, xScale, yScale):
		xo, yo, xs, ys = (float(v) for v in (xOrigin, yOrigin, xScale, yScale))
		for it in self._find(tagOrId):
			c = it.coords
			for i in range(0, len(c) - 1, 2):
				c[i]     = xo + (c[i] - xo) * xs
				c[i + 1] = yo + (c[i + 1] - yo) * ys
		self._markDirty()

	def tag_raise(self, tagOrId, aboveThis=None):
		for it in self._find(tagOrId):
			self._canvasItems.pop(it.id)
			self._canvasItems[it.id] = it
		self._markDirty()

	def tag_lower(self, tagOrId, belowThis=None):
		lower = self._find(tagOrId)
		rest  = [it for it in self._canvasItems.values() if it not in lower]
		self._canvasItems = {it.id: it for it in lower + rest}
		self._markDirty()

	lift = tkraise = tag_raise
	lower = tag_lower

	def bbox(self, *tagsOrIds):
		boxes = []
		for t in tagsOrIds or ('all',):
			for it in self._find(t):
				b = self._itemBox(it)
				if b:
					boxes.append(b)
		if not boxes:
			return None
		return (int(min(b[0] for b in boxes)), int(min(b[1] for b in boxes)),
			int(math.ceil(max(b[2] for b in boxes))),
			int(math.ceil(max(b[3] for b in boxes))))

	def _itemBox(self, it):
		c = it.coords
		if not c:
			return None
		if it.type == 'text':
			x, y = c[0], c[1]
			text = str(it.opts.get('text', ''))
			lines = text.split('\n') or ['']
			w = max(len(l) for l in lines) * _core.PX
			h = len(lines) * _core.PY
			x0, y0 = self._anchored(x, y, w, h, it.opts.get('anchor', 'center'))
			return (x0, y0, x0 + w, y0 + h)
		if len(c) < 4:
			return (c[0], c[1], c[0] + _core.PX, c[1] + _core.PY)
		xs = c[0::2]
		ys = c[1::2]
		return (min(xs), min(ys), max(xs), max(ys))

	@staticmethod
	def _anchored(x, y, w, h, anchor):
		anchor = str(anchor or 'center')
		if anchor == 'center':
			anchor = ''
		if 'w' in anchor:
			x0 = x
		elif 'e' in anchor:
			x0 = x - w
		else:
			x0 = x - w // 2
		if 'n' in anchor:
			y0 = y
		elif 's' in anchor:
			y0 = y - h
		else:
			y0 = y - h // 2
		return int(round(x0)), int(round(y0))

	# text item editing (minimal)
	def insert(self, tagOrId, index, string):
		for it in self._find(tagOrId):
			if it.type == 'text':
				t = str(it.opts.get('text', ''))
				i = len(t) if index == 'end' else int(index)
				it.opts['text'] = t[:i] + str(string) + t[i:]
		self._markDirty()

	def dchars(self, tagOrId, first, last=None):
		for it in self._find(tagOrId):
			if it.type == 'text':
				t = str(it.opts.get('text', ''))
				f = len(t) if first == 'end' else int(first)
				l = f if last is None else (len(t) - 1 if last == 'end' else int(last))
				it.opts['text'] = t[:f] + t[l + 1:]
		self._markDirty()

	def focus(self, *args):
		if not args:
			return self.focus_set()
		return ''

	def icursor(self, *args):
		pass

	def index(self, tagOrId, index):
		return 0

	def select_clear(self):
		pass

	# ------------------------------------------------------------------
	# Tag bindings
	# ------------------------------------------------------------------

	def tag_bind(self, tagOrId, sequence=None, func=None, add=None):
		key = (str(tagOrId), sequence)
		if func is None:
			return self._tagBinds.get(key, [])
		if not add:
			self._tagBinds[key] = []
		self._tagBinds.setdefault(key, []).append(func)
		Widget._funcSerial += 1
		return f'tag{Widget._funcSerial}'

	def tag_unbind(self, tagOrId, sequence, funcid=None):
		self._tagBinds.pop((str(tagOrId), sequence), None)

	def _itemAt(self, cx, cy):
		for it in reversed(list(self._canvasItems.values())):
			b = self._itemBox(it)
			if b and b[0] <= cx < max(b[2], b[0] + _core.PX) and \
					b[1] <= cy < max(b[3], b[1] + _core.PY):
				return it
		return None

	def _handleMouse(self, mx, my, bstate):
		from ._core import _mouseEventNames
		cx = (mx - self._x) * _core.PX + self._xOrigin
		cy = (my - self._y) * _core.PY + self._yOrigin
		it = self._itemAt(cx, cy)
		self._current = it.id if it else None
		if it is None:
			return False
		evt   = _newMouseEvent(self, mx, my, bstate)
		fired = False
		for alts in _mouseEventNames(bstate, self._dragging()):
			for seq in alts:
				for tag in [str(it.id)] + it.tags:
					for func in self._tagBinds.get((tag, seq), []):
						fired = True
						if _callback(self, func, evt) == 'break':
							return True
				if fired:
					break
		return fired

	# ------------------------------------------------------------------
	# Coordinates and scrolling
	# ------------------------------------------------------------------

	def canvasx(self, screenx, gridspacing=None):
		return float(screenx) + self._xOrigin

	def canvasy(self, screeny, gridspacing=None):
		return float(screeny) + self._yOrigin

	def _region(self):
		sr = self._opts.get('scrollregion')
		if sr:
			from ._tcl import _splitlist
			v = [float(x) for x in _splitlist(sr)] if isinstance(sr, str) else \
				[float(x) for x in sr]
			if len(v) == 4:
				return v
		return [0, 0, max(1, self._width) * _core.PX, max(1, self._height) * _core.PY]

	def _view(self, args, horizontal):
		x0, y0, x1, y1 = self._region()
		lo, hi = (x0, x1) if horizontal else (y0, y1)
		size   = max(1, (self._width * _core.PX if horizontal else
			self._height * _core.PY))
		span   = max(1.0, hi - lo)
		origin = self._xOrigin if horizontal else self._yOrigin
		if not args:
			first = (origin - lo) / span
			return (max(0.0, first), min(1.0, first + size / span))
		if args[0] == 'moveto':
			origin = lo + float(args[1]) * span
		elif args[0] == 'scroll':
			n = int(args[1])
			unit    = _core.PX if horizontal else _core.PY
			origin += n * (size if str(args[2]).startswith('p') else unit)
		origin = max(lo, min(origin, hi - size))
		origin = int(max(lo, origin))
		if horizontal:
			self._xOrigin = origin
		else:
			self._yOrigin = origin
		self._markDirty()
		return None

	def xview(self, *args):
		return self._view(args, True)

	def yview(self, *args):
		return self._view(args, False)

	def xview_moveto(self, fraction):
		self._view(('moveto', fraction), True)

	def yview_moveto(self, fraction):
		self._view(('moveto', fraction), False)

	def xview_scroll(self, number, what):
		self._view(('scroll', number, what), True)

	def yview_scroll(self, number, what):
		self._view(('scroll', number, what), False)

	def scan_mark(self, x, y):
		self._scanMark = (x, y, self._xOrigin, self._yOrigin)

	def scan_dragto(self, x, y, gain=10):
		mx, my, ox, oy = getattr(self, '_scanMark', (x, y, self._xOrigin, self._yOrigin))
		self._xOrigin = int(ox - (x - mx))
		self._yOrigin = int(oy - (y - my))
		self._markDirty()

	def postscript(self, cnf={}, **kw):
		return ''

	def _preRender(self):
		for cmd, horiz in (('xscrollcommand', True), ('yscrollcommand', False)):
			f = self._opts.get(cmd)
			if callable(f):
				first, last = self._view((), horiz)
				f(first, last)
		super()._preRender()

	# ------------------------------------------------------------------
	# Layout and rendering
	# ------------------------------------------------------------------

	def _preferredSize(self):
		bd = self._cfgBorder()
		return (max(1, _int(self._opts.get('width'))) + 2 * bd,
			max(1, _int(self._opts.get('height'))) + 2 * bd)

	def _layoutChildren(self):
		for it in self._canvasItems.values():
			if it.type != 'window':
				continue
			win = it.opts.get('window')
			if win is None or win._destroyed:
				continue
			if it.opts.get('state') == 'hidden':
				win._unmapTree()
				continue
			pw, ph = win._preferredSize()
			w = int(_pixels(it.opts.get('width') or 0) / _core.PX + 0.5) or pw
			h = int(_pixels(it.opts.get('height') or 0) / _core.PY + 0.5) or ph
			x, y = self._cell(it.coords[0], it.coords[1])
			x, y = self._anchored(x, y, w, h, it.opts.get('anchor', 'center'))
			# clip to the canvas
			if x >= self._x + self._width or y >= self._y + self._height or \
					x + w <= self._x or y + h <= self._y:
				win._unmapTree()
				continue
			x1 = min(x + w, self._x + self._width)
			y1 = min(y + h, self._y + self._height)
			x  = max(x, self._x)
			y  = max(y, self._y)
			win._doLayout(x, y, x1 - x, y1 - y)
			if hasattr(win, '_layoutChildren'):
				win._layoutChildren()

	def _cell(self, cx, cy):
		"""Canvas units -> screen cell."""
		return (self._x + int((cx - self._xOrigin) // _core.PX),
			self._y + int((cy - self._yOrigin) // _core.PY))

	def _put(self, scr, x, y, text, attr):
		"""Write text clipped to the canvas rectangle."""
		if y < self._y or y >= self._y + self._height:
			return
		left  = self._x
		right = self._x + self._width
		if x < left:
			text = text[left - x:]
			x    = left
		text = text[:max(0, right - x)]
		if text:
			_addStr(scr, y, x, text, attr)

	def render(self, scr):
		if not self._isMapped():
			return
		app  = self._getApp()
		bg   = self._color('bg')
		attr = self._getAttr()
		_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)
		for it in list(self._canvasItems.values()):
			if it.opts.get('state') == 'hidden' or not it.coords:
				continue
			try:
				self._renderItem(scr, app, it, bg)
			except (ValueError, TypeError, IndexError):
				pass
		self._renderChildren(scr)

	def _attrFor(self, app, fg, bg, **kw):
		if app is None:
			return 0
		return app._colors.getAttr(fg or self._color('fg'), bg or '', **kw)

	def _renderItem(self, scr, app, it, bg):
		o = it.opts
		c = it.coords
		if it.type == 'text':
			text  = str(o.get('text', ''))
			lines = text.split('\n')
			w     = max(len(l) for l in lines)
			x, y  = self._cell(c[0], c[1])
			x0, y0 = self._anchored(x, y, w, len(lines), o.get('anchor', 'center'))
			attr  = self._attrFor(app, o.get('fill') or ('black' if bg else ''),
				self._fillAt(c[0], c[1], it) or bg)
			for i, line in enumerate(lines):
				self._put(scr, x0, y0 + i, line, attr)
		elif it.type in ('rectangle', 'oval', 'arc', 'polygon'):
			xs, ys = c[0::2], c[1::2]
			x0, y0 = self._cell(min(xs), min(ys))
			x1, y1 = self._cell(max(xs), max(ys))
			w, h   = max(1, x1 - x0), max(1, y1 - y0)
			fill   = o.get('fill', '' if it.type != 'polygon' else 'black')
			if fill:
				attr = self._attrFor(app, '', fill)
				for j in range(h):
					self._put(scr, x0, y0 + j, ' ' * w, attr)
			outline = o.get('outline', 'black')
			if outline and w >= 2 and h >= 2 and it.type == 'rectangle' and \
					_int(o.get('width', 1), 1) > 0:
				self._box(scr, x0, y0, w, h, self._attrFor(app, outline, fill or bg))
		elif it.type == 'line':
			attr = self._attrFor(app, o.get('fill', 'black'), bg)
			pts  = list(zip(c[0::2], c[1::2]))
			for (ax, ay), (bx, by) in zip(pts, pts[1:]):
				self._line(scr, ax, ay, bx, by, attr)
		elif it.type in ('image', 'bitmap'):
			if o.get('image') or o.get('bitmap'):
				x, y = self._cell(c[0], c[1])
				from ._image import IMAGE_GLYPH
				self._put(scr, x, y, IMAGE_GLYPH, self._attrFor(app, '', bg))

	def _fillAt(self, cx, cy, upto):
		"""Background colour of the topmost filled shape under (cx, cy)
		drawn before *upto* (so that text on a rectangle keeps its fill)."""
		fill = ''
		for it in self._canvasItems.values():
			if it is upto:
				break
			if it.type in ('rectangle', 'oval', 'polygon') and it.opts.get('fill') \
					and it.opts.get('state') != 'hidden':
				b = self._itemBox(it)
				if b and b[0] <= cx <= b[2] and b[1] <= cy <= b[3]:
					fill = it.opts['fill']
		return fill

	def _box(self, scr, x, y, w, h, attr):
		self._put(scr, x, y, '┌' + '─' * (w - 2) + '┐', attr)
		for j in range(1, h - 1):
			self._put(scr, x, y + j, '│', attr)
			self._put(scr, x + w - 1, y + j, '│', attr)
		self._put(scr, x, y + h - 1, '└' + '─' * (w - 2) + '┘', attr)

	def _line(self, scr, ax, ay, bx, by, attr):
		x0, y0 = self._cell(ax, ay)
		x1, y1 = self._cell(bx, by)
		if y0 == y1:
			lo, hi = sorted((x0, x1))
			self._put(scr, lo, y0, '─' * max(1, hi - lo), attr)
		elif x0 == x1:
			lo, hi = sorted((y0, y1))
			for y in range(lo, max(lo + 1, hi)):
				self._put(scr, x0, y, '│', attr)
		else:
			n = max(abs(x1 - x0), abs(y1 - y0))
			for i in range(n + 1):
				self._put(scr, x0 + round((x1 - x0) * i / n),
					y0 + round((y1 - y0) * i / n), '·', attr)
