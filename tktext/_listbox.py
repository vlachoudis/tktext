import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad, _int
from ._events import (KEY_UP, KEY_DOWN, KEY_HOME, KEY_END, KEY_PPAGE,
	KEY_NPAGE, KEY_ENTER, KEY_SPACE, KEY_SHIFT_UP, KEY_SHIFT_DOWN,
	B1_PRESS, B1_RELEASE, B1_CLICK, B1_DCLICK, MOTION, isWheel)


class _ScrollMixin:
	"""Shared helpers for widgets with a vertical scroll offset.

	The widget provides _totalRows(), _visRows(), and the attribute
	_scrollY.  A linked scrollbar is driven through 'yscrollcommand'; when
	no command is configured a one-column scrollbar is drawn inside the
	widget's right border."""

	def _clampScroll(self):
		maxScroll    = max(0, self._totalRows() - self._visRows())
		self._scrollY = max(0, min(self._scrollY, maxScroll))

	def _yFractions(self):
		total = self._totalRows()
		if total <= 0:
			return (0.0, 1.0)
		first = self._scrollY / total
		last  = min(1.0, (self._scrollY + self._visRows()) / total)
		return (first, last)

	def _notifyYScroll(self):
		cmd = self._opts.get('yscrollcommand')
		if callable(cmd):
			frac = self._yFractions()
			if getattr(self, '_lastYScroll', None) != frac:
				self._lastYScroll = frac
				cmd(*frac)

	def _showInternalBar(self) -> bool:
		return (not callable(self._opts.get('yscrollcommand')) and
			self._totalRows() > self._visRows() and self._w > 2)

	def yview(self, *args):
		"""Query ((first, last)) or change the vertical view."""
		if not args:
			return self._yFractions()
		if args[0] == 'moveto':
			self._scrollY = int(round(float(args[1]) * self._totalRows()))
		elif args[0] == 'scroll':
			n    = int(args[1])
			unit = args[2] if len(args) > 2 else 'units'
			if str(unit).startswith('page'):
				n *= max(1, self._visRows() - 1)
			self._scrollY += n
		else:
			self._scrollY = self._indexForYview(args[0])
		self._clampScroll()
		self._markDirty()
		return None

	def _indexForYview(self, idx):
		return _int(idx)

	def yview_moveto(self, fraction):
		self.yview('moveto', fraction)

	def yview_scroll(self, number, what):
		self.yview('scroll', number, what)

	yviewMoveto = yview_moveto
	yviewScroll = yview_scroll

	def _drawInternalBar(self, scr, x, y, h, attr):
		total = self._totalRows()
		vis   = self._visRows()
		if total <= 0 or h <= 0:
			return
		thumbStart = int(self._scrollY * h / total)
		thumbSize  = max(1, int(round(vis * h / total)))
		thumbStart = min(thumbStart, h - thumbSize)
		for i in range(h):
			ch = '█' if thumbStart <= i < thumbStart + thumbSize else '│'
			_addStr(scr, y + i, x, ch, attr)

	def _barClick(self, row, h, press):
		"""Handle a press on the internal scrollbar at *row*."""
		total = self._totalRows()
		vis   = self._visRows()
		thumbStart = int(self._scrollY * h / max(1, total))
		thumbSize  = max(1, int(round(vis * h / max(1, total))))
		if row < thumbStart:
			self._scrollY -= vis
		elif row >= thumbStart + thumbSize:
			self._scrollY += vis
		elif press:
			self._sbDrag = (row, self._scrollY)
		self._clampScroll()
		self._markDirty()

	def _barDrag(self, row, h):
		anchorRow, anchorScroll = self._sbDrag
		total = self._totalRows()
		self._scrollY = anchorScroll + int(round((row - anchorRow) * total / max(1, h)))
		self._clampScroll()
		self._markDirty()


class Listbox(_ScrollMixin, Widget):
	"""Scrollable list widget.  Mirrors tkinter.Listbox."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'selectmode':		'browse',
			'selectbackground':	'',
			'selectforeground':	'',
			'activestyle':		'underline',
			'exportselection':	True,
			'listvariable':		None,
			'yscrollcommand':	None,
			'xscrollcommand':	None,
		})
		kwargs.setdefault('relief', 'sunken')
		kwargs.setdefault('borderwidth', 1)
		kwargs.setdefault('width', 20)
		kwargs.setdefault('height', 10)

		self._items    = []		# list of str
		self._itemCfg  = {}		# index -> {'fg':…, 'bg':…}
		self._sel      = set()		# set of selected indices
		self._active   = 0		# active (cursor) index
		self._scrollY  = 0		# first visible item index
		self._anchor   = 0		# anchor for extended selection
		self._sbDrag   = None		# internal scrollbar drag state

		if kwargs:
			self.configure(**kwargs)

	def configure(self, cnf=None, **kwargs):
		if cnf:
			kwargs.update(cnf)
		lv = kwargs.get('listvariable')
		res = super().configure(**kwargs)
		if lv is not None and hasattr(lv, 'get'):
			self._loadListVariable()
		return res

	config = configure

	# ------------------------------------------------------------------
	# listvariable support
	# ------------------------------------------------------------------

	def _loadListVariable(self):
		lv = self._opts.get('listvariable')
		if lv is None or not hasattr(lv, 'get'):
			return
		val = lv.get()
		if isinstance(val, (list, tuple)):
			self._items = [str(v) for v in val]
		elif val:
			self._items = str(val).split()
		else:
			self._items = []

	def _storeListVariable(self):
		lv = self._opts.get('listvariable')
		if lv is not None and hasattr(lv, 'set'):
			try:
				lv.set(tuple(self._items))
			except (TypeError, ValueError):
				pass

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def insert(self, idx, *elements):
		"""Insert *elements* at *idx* ('end' or integer)."""
		if idx in ('end', 'END'):
			pos = len(self._items)
		else:
			pos = max(0, min(self._resolveIdx(idx), len(self._items)))
		n = len(elements)
		for i, elem in enumerate(elements):
			self._items.insert(pos + i, str(elem))

		# Shift indices after the insertion point
		self._sel     = {(s + n if s >= pos else s) for s in self._sel}
		self._itemCfg = {(k + n if k >= pos else k): v for k, v in self._itemCfg.items()}
		if self._active >= pos and len(self._items) > n:
			self._active += n
		self._storeListVariable()
		self._markDirty()

	def delete(self, first, last=None):
		"""Delete items from *first* to *last* inclusive."""
		if not self._items:
			return
		first = self._resolveIdx(first)
		last  = self._resolveIdx(last) if last is not None else first
		first = max(0, first)
		last  = min(last, len(self._items) - 1)
		if first > last:
			return
		n = last - first + 1
		del self._items[first:last+1]

		def shift(i):
			return i - n if i > last else i
		self._sel     = {shift(s) for s in self._sel if not first <= s <= last}
		self._itemCfg = {shift(k): v for k, v in self._itemCfg.items()
			if not first <= k <= last}
		if self._active > last:
			self._active -= n
		elif self._active >= first:
			self._active = first
		self._active = max(0, min(self._active, len(self._items) - 1))
		self._storeListVariable()
		self._markDirty()

	def get(self, first, last=None):
		"""Return item(s) at *first* [through *last*]."""
		first = self._resolveIdx(first)
		if last is None:
			if 0 <= first < len(self._items):
				return self._items[first]
			return ''
		last = self._resolveIdx(last)
		return tuple(self._items[max(0, first):last+1])

	def size(self):
		"""Return number of items."""
		return len(self._items)

	def curselection(self):
		"""Return tuple of currently selected indices."""
		return tuple(sorted(self._sel))

	def _range(self, first, last):
		first = self._resolveIdx(first)
		last  = self._resolveIdx(last) if last is not None else first
		if first > last:
			first, last = last, first
		return range(max(0, first), min(last, len(self._items) - 1) + 1)

	def selectionSet(self, first, last=None):
		"""Select items from *first* to *last*."""
		self._sel.update(self._range(first, last))
		self._markDirty()

	def selectionClear(self, first=None, last=None):
		"""Deselect items."""
		if first is None:
			self._sel.clear()
		else:
			for i in self._range(first, last):
				self._sel.discard(i)
		self._markDirty()

	def selectionIncludes(self, idx):
		return self._resolveIdx(idx) in self._sel

	def selectionAnchor(self, idx):
		self._anchor = self._resolveIdx(idx)

	selection_set		= selectionSet
	select_set		= selectionSet
	selection_clear		= selectionClear
	select_clear		= selectionClear
	selection_includes	= selectionIncludes
	select_includes		= selectionIncludes
	selection_anchor	= selectionAnchor
	select_anchor		= selectionAnchor

	def activate(self, idx):
		"""Set active item."""
		if self._items:
			self._active = max(0, min(self._resolveIdx(idx), len(self._items) - 1))
		self._markDirty()

	def index(self, idx):
		"""Return numeric index for *idx*."""
		if idx in ('end', 'END'):
			return len(self._items)
		return self._resolveIdx(idx)

	def see(self, idx):
		"""Scroll so that item at *idx* is visible."""
		self._ensureVisible(self._resolveIdx(idx))
		self._markDirty()

	def nearest(self, y):
		"""Return index of the item nearest to widget-relative *y*."""
		i = self._scrollY + (int(y) - self._border())
		return max(0, min(i, len(self._items) - 1))

	def bbox(self, idx):
		"""Return (x, y, width, height) of item *idx* relative to the widget."""
		bd = self._border()
		i  = self._resolveIdx(idx) - self._scrollY
		if 0 <= i < self._visRows() and self._resolveIdx(idx) < len(self._items):
			return (bd, bd + i, self._w - 2*bd, 1)
		return None

	def itemconfigure(self, idx, cnf=None, **kwargs):
		if cnf:
			kwargs.update(cnf)
		i = self._resolveIdx(idx)
		cfg = self._itemCfg.setdefault(i, {})
		for k, v in kwargs.items():
			k = {'background': 'bg', 'foreground': 'fg'}.get(k, k)
			cfg[k] = v
		self._markDirty()

	def itemcget(self, idx, option):
		option = {'background': 'bg', 'foreground': 'fg'}.get(option, option)
		return self._itemCfg.get(self._resolveIdx(idx), {}).get(option, '')

	itemconfig = itemconfigure

	def xview(self, *args):
		if not args:
			return (0.0, 1.0)
		return None

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _resolveIdx(self, idx):
		if isinstance(idx, int):
			return idx
		s = str(idx)
		if s in ('end', 'END'):
			return max(0, len(self._items) - 1)
		if s == 'active':
			return self._active
		if s == 'anchor':
			return self._anchor
		if s.startswith('@'):
			try:
				_, y = s[1:].split(',')
				return self.nearest(int(y))
			except ValueError:
				return 0
		try:
			return int(s)
		except (TypeError, ValueError):
			return 0

	_indexForYview = _resolveIdx

	def _visRows(self) -> int:
		return max(1, self._h - 2*self._border())

	def _totalRows(self) -> int:
		return len(self._items)

	def _preferredSize(self):
		bd = self._cfgBorder()
		ow = _int(self._opts.get('width'), 20)
		oh = _int(self._opts.get('height'), 10)
		if ow <= 0:
			ow = max((len(s) for s in self._items), default=1)
		if oh <= 0:
			oh = max(1, len(self._items))
		return (ow + 2*bd, oh + 2*bd)

	def _preRender(self):
		self._clampScroll()
		if self._items:
			self._active = max(0, min(self._active, len(self._items) - 1))
		self._notifyYScroll()

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return

		bd     = self._border()
		attr   = self._getAttr()
		relief = self._opts.get('relief', 'sunken')
		disabled = self._opts.get('state') == 'disabled'
		if disabled:
			attr = self._getAttr(fg='gray')

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		showBar = self._showInternalBar()
		visH    = self._visRows()
		visW    = max(1, self._w - 2*bd - (1 if showBar else 0))
		bx      = self._x + bd
		by      = self._y + bd

		sfg = self._opts.get('selectforeground') or ''
		sbg = self._opts.get('selectbackground') or ''
		for i in range(visH):
			itemIdx = self._scrollY + i
			if itemIdx >= len(self._items):
				break
			text       = _pad(self._items[itemIdx], visW)
			isSelected = itemIdx in self._sel
			isActive   = itemIdx == self._active and self._focused

			cfg = self._itemCfg.get(itemIdx)
			if isSelected:
				rowAttr = self._getAttr(fg=sfg, bg=sbg, reverse=not (sfg or sbg))
			elif cfg and (cfg.get('fg') or cfg.get('bg')):
				rowAttr = self._getAttr(fg=cfg.get('fg'), bg=cfg.get('bg'))
			else:
				rowAttr = attr
			if isActive:
				style = self._opts.get('activestyle', 'underline')
				if style == 'underline':
					rowAttr |= curses.A_UNDERLINE
				elif style == 'dotbox':
					rowAttr |= curses.A_BOLD
				if not isSelected and style != 'none':
					rowAttr |= curses.A_BOLD

			_addStr(scr, by + i, bx, text, rowAttr)

		if showBar:
			self._drawInternalBar(scr, self._x + self._w - bd - 1, by, visH, attr)

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _fireSelect(self):
		self._fireVirtual('<<ListboxSelect>>', index=self._active)

	def _handleKey(self, key):
		if self._opts.get('state') == 'disabled' or not self._items:
			return False

		mode   = self._opts.get('selectmode', 'browse')
		visH   = self._visRows()
		prev   = self._active
		extend = key in (KEY_SHIFT_UP, KEY_SHIFT_DOWN)
		if extend:
			key = KEY_UP if key == KEY_SHIFT_UP else KEY_DOWN

		if key == KEY_UP:
			self._active = max(0, self._active - 1)
		elif key == KEY_DOWN:
			self._active = min(len(self._items) - 1, self._active + 1)
		elif key == KEY_HOME:
			self._active = 0
		elif key == KEY_END:
			self._active = len(self._items) - 1
		elif key == KEY_PPAGE:
			self._active = max(0, self._active - visH)
		elif key == KEY_NPAGE:
			self._active = min(len(self._items) - 1, self._active + visH)
		elif key == KEY_SPACE:
			self._clickSelect(self._active, mode)
			self._fireSelect()
			self._markDirty()
			return True
		elif key == KEY_ENTER:
			if mode in ('browse', 'single') or not self._sel:
				self._clickSelect(self._active, 'browse')
				self._fireSelect()
			self._markDirty()
			return True
		else:
			return False

		self._ensureVisible(self._active)
		if self._active != prev:
			if mode == 'browse' or (mode == 'extended' and not extend):
				self._sel    = {self._active}
				self._anchor = self._active
				self._fireSelect()
			elif mode == 'extended':
				lo, hi    = sorted((self._anchor, self._active))
				self._sel = set(range(lo, hi + 1))
				self._fireSelect()
		self._markDirty()
		return True

	def _clickSelect(self, idx, mode):
		if mode in ('single', 'browse'):
			self._sel = {idx}
		elif mode == 'multiple':
			if idx in self._sel:
				self._sel.discard(idx)
			else:
				self._sel.add(idx)
		elif mode == 'extended':
			self._sel = {idx}
		self._anchor = idx

	def _ensureVisible(self, idx):
		visH = self._visRows()
		if idx < self._scrollY:
			self._scrollY = idx
		elif idx >= self._scrollY + visH:
			self._scrollY = idx - visH + 1
		self._clampScroll()

	def _handleMouse(self, mx, my, bstate):
		if self._opts.get('state') == 'disabled':
			return False
		bd    = self._border()
		visH  = self._visRows()
		by    = self._y + bd
		barX  = self._x + self._w - bd - 1

		wheel = isWheel(bstate)
		if wheel:
			self._scrollY += 3 * wheel
			self._clampScroll()
			self._markDirty()
			return True

		press   = bool(bstate & B1_PRESS) and not (bstate & MOTION)
		release = bool(bstate & (B1_RELEASE | B1_CLICK))
		clicked = bool(bstate & (B1_CLICK | B1_DCLICK))
		motion  = bool(bstate & MOTION) or (bool(bstate & B1_PRESS) and
			self._sbDrag is not None)

		# Scrollbar drag in progress — continue regardless of mx
		if self._sbDrag is not None:
			if motion or release:
				self._barDrag(my - by, visH)
			if release:
				self._sbDrag = None
			return True

		if self._showInternalBar() and mx == barX and by <= my < by + visH:
			if press or clicked:
				self._barClick(my - by, visH, press)
			return True

		i = self._scrollY + (my - by)
		if not (0 <= i < len(self._items)):
			return False
		mode = self._opts.get('selectmode', 'browse')
		if press or (clicked and not bstate & B1_DCLICK):
			self._active = i
			self._clickSelect(i, mode)
			self._fireSelect()
			self._markDirty()
		elif motion and mode in ('browse', 'extended') and self._dragging():
			# drag-select
			self._active = i
			if mode == 'browse':
				self._sel = {i}
			else:
				lo, hi    = sorted((self._anchor, i))
				self._sel = set(range(lo, hi + 1))
			self._ensureVisible(i)
			self._fireSelect()
			self._markDirty()
		return True
