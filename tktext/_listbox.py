import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _pad
from ._events import (KEY_UP, KEY_DOWN, KEY_HOME, KEY_END,
	KEY_PPAGE, KEY_NPAGE, KEY_ENTER, KEY_CR, KEY_SPACE)


class Listbox(Widget):
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
		})
		kwargs.setdefault('relief', 'sunken')
		kwargs.setdefault('borderwidth', 1)
		kwargs.setdefault('width', 20)
		kwargs.setdefault('height', 10)
		if kwargs:
			self.configure(**kwargs)

		self._items    = []		# list of str
		self._sel      = set()		# set of selected indices
		self._active   = 0		# active (cursor) index
		self._scrollY  = 0		# first visible item index
		self._anchor   = 0		# anchor for extended selection
		# Scrollbar drag state
		self._sbDrag            = False
		self._sbDragAnchorRow   = 0	# scrollbar row where drag started
		self._sbDragAnchorScroll= 0	# _scrollY at drag start

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def insert(self, idx, *elements):
		"""Insert *elements* at *idx* ('end' or integer)."""
		if idx == 'end' or idx == 'END':
			pos = len(self._items)
		elif idx == 'active':
			pos = self._active
		else:
			pos = max(0, min(int(idx), len(self._items)))

		for i, elem in enumerate(elements):
			self._items.insert(pos + i, str(elem))

		# Adjust indices
		oldSel = sorted(self._sel)
		self._sel = {(s + len(elements) if s >= pos else s) for s in oldSel}
		if self._active >= pos:
			self._active = min(self._active + len(elements), len(self._items) - 1)
		self._markDirty()

	def delete(self, first, last=None):
		"""Delete items from *first* to *last* inclusive."""
		first = self._resolveIdx(first)
		last  = self._resolveIdx(last) if last is not None else first
		first = max(0, min(first, len(self._items) - 1))
		last  = max(0, min(last,  len(self._items) - 1))
		if first > last:
			return
		del self._items[first:last+1]
		removed = set(range(first, last + 1))
		newSel = set()
		for s in self._sel:
			if s in removed:
				continue
			elif s > last:
				newSel.add(s - (last - first + 1))
			else:
				newSel.add(s)
		self._sel = newSel
		self._active = max(0, min(self._active, len(self._items) - 1))
		self._scrollY = max(0, min(self._scrollY, max(0, len(self._items) - 1)))
		self._markDirty()

	def get(self, first, last=None):
		"""Return item(s) at *first* [through *last*]."""
		first = self._resolveIdx(first)
		if last is None:
			if 0 <= first < len(self._items):
				return self._items[first]
			return ''
		last = self._resolveIdx(last)
		return tuple(self._items[first:last+1])

	def size(self):
		"""Return number of items."""
		return len(self._items)

	def curselection(self):
		"""Return tuple of currently selected indices."""
		return tuple(sorted(self._sel))

	def selection_set(self, first, last=None):	# noqa: N802
		self.selectionSet(first, last)

	def selectionSet(self, first, last=None):
		"""Select items from *first* to *last*."""
		first = self._resolveIdx(first)
		last  = self._resolveIdx(last) if last is not None else first
		for i in range(first, last + 1):
			if 0 <= i < len(self._items):
				self._sel.add(i)
		self._markDirty()

	def selection_clear(self, first, last=None):	# noqa: N802
		self.selectionClear(first, last)

	def selectionClear(self, first=None, last=None):
		"""Deselect items."""
		if first is None:
			self._sel.clear()
		else:
			first = self._resolveIdx(first)
			last  = self._resolveIdx(last) if last is not None else first
			for i in range(first, last + 1):
				self._sel.discard(i)
		self._markDirty()

	def selection_includes(self, idx):	# noqa: N802
		return self.selectionIncludes(idx)

	def selectionIncludes(self, idx):
		return self._resolveIdx(idx) in self._sel

	def activate(self, idx):
		"""Set active item."""
		self._active = max(0, min(self._resolveIdx(idx), len(self._items)-1))
		self._markDirty()

	def index(self, idx):
		"""Return numeric index for *idx*."""
		return self._resolveIdx(idx)

	def see(self, idx):
		"""Scroll so that item at *idx* is visible."""
		i = self._resolveIdx(idx)
		bd   = int(self._opts.get('borderwidth') or 0)
		visH = max(1, self._h - 2*bd)
		if i < self._scrollY:
			self._scrollY = i
		elif i >= self._scrollY + visH:
			self._scrollY = i - visH + 1
		self._markDirty()

	def nearest(self, y):
		"""Return index of item nearest screen y-coordinate."""
		bd = int(self._opts.get('borderwidth') or 0)
		i  = self._scrollY + (y - self._y - bd)
		return max(0, min(i, len(self._items) - 1))

	def bbox(self, idx):
		"""Return (x, y, width, height) bounding box of item *idx*."""
		bd   = int(self._opts.get('borderwidth') or 0)
		i    = self._resolveIdx(idx) - self._scrollY
		visH = max(1, self._h - 2*bd)
		if 0 <= i < visH:
			return (self._x + bd, self._y + bd + i, self._w - 2*bd, 1)
		return None

	def xview(self, *args):
		pass

	def yview(self, *args):
		if not args:
			return
		bd   = int(self._opts.get('borderwidth') or 0)
		visH = max(1, self._h - 2*bd)
		if args[0] == 'moveto':
			frac = float(args[1])
			self._scrollY = int(frac * len(self._items))
		elif args[0] == 'scroll':
			n    = int(args[1])
			unit = args[2] if len(args) > 2 else 'units'
			if unit == 'pages':
				n *= visH
			self._scrollY = max(0, self._scrollY + n)
		self._markDirty()

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _resolveIdx(self, idx):
		if idx == 'end' or idx == 'END':
			return max(0, len(self._items) - 1)
		if idx == 'active':
			return self._active
		if idx == 'anchor':
			return self._anchor
		try:
			return int(idx)
		except (TypeError, ValueError):
			return 0

	def _preferredSize(self):
		bd  = int(self._opts.get('borderwidth') or 0)
		ow  = int(self._opts.get('width') or 20)
		oh  = int(self._opts.get('height') or 10)
		return (ow + 2*bd, oh + 2*bd)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return

		bd     = int(self._opts.get('borderwidth') or 0)
		attr   = self._getAttr()
		relief = self._opts.get('relief', 'sunken')

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)
		if bd > 0:
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		visH = max(1, self._h - 2*bd)
		visW = max(1, self._w - 2*bd - 1)	# -1 for scrollbar
		bx   = self._x + bd
		by   = self._y + bd

		for i in range(visH):
			itemIdx = self._scrollY + i
			sy      = by + i

			if itemIdx >= len(self._items):
				_addStr(scr, sy, bx, ' ' * visW, attr)
				continue

			text = _pad(self._items[itemIdx], visW)
			isSelected = itemIdx in self._sel
			isActive   = itemIdx == self._active and self._focused

			if isSelected:
				sfg = self._opts.get('selectforeground') or ''
				sbg = self._opts.get('selectbackground') or ''
				rowAttr = self._getAttr(fg=sfg, bg=sbg, reverse=not (sfg or sbg))
			elif isActive:
				rowAttr = attr | curses.A_BOLD
			else:
				rowAttr = attr

			_addStr(scr, sy, bx, text, rowAttr)

		# Scrollbar
		total = len(self._items)
		barX  = self._x + self._w - bd
		if total > visH and barX < self._x + self._w:
			thumbStart = int(self._scrollY * visH / total) if total else 0
			thumbSize  = max(1, int(visH * visH / total))
			for i in range(visH):
				ch = '#' if thumbStart <= i < thumbStart + thumbSize else '|'
				try:
					scr.addch(by + i, barX, ch, attr)
				except curses.error:
					pass

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _isFocusable(self):
		return self._opts.get('state', 'normal') == 'normal'

	def _handleKey(self, key):
		if not self._items:
			return super()._handleKey(key)

		mode  = self._opts.get('selectmode', 'browse')
		bd    = int(self._opts.get('borderwidth') or 0)
		visH  = max(1, self._h - 2*bd)
		prevActive = self._active

		if key == KEY_UP:
			self._active = max(0, self._active - 1)
		elif key == KEY_DOWN:
			self._active = min(len(self._items) - 1, self._active + 1)
		elif key == KEY_HOME:
			self._active = 0
		elif key == KEY_END:
			self._active = max(0, len(self._items) - 1)
		elif key == KEY_PPAGE:
			self._active = max(0, self._active - visH)
		elif key == KEY_NPAGE:
			self._active = min(len(self._items) - 1, self._active + visH)
		elif key in (KEY_ENTER, KEY_CR, KEY_SPACE):
			self._toggleOrSelect(self._active, mode)
			self._markDirty()
			self._dispatch('<Double-Button-1>', _LBEvent(self, self._active))
			return True
		else:
			return super()._handleKey(key)

		if self._active != prevActive:
			self._ensureVisible(self._active)
			if mode == 'browse':
				self._sel = {self._active}
			self._dispatch('<ListboxSelect>', _LBEvent(self, self._active))
			self._markDirty()
		return True

	def _toggleOrSelect(self, idx, mode):
		if mode in ('single', 'browse'):
			self._sel = {idx}
		elif mode == 'multiple':
			if idx in self._sel:
				self._sel.discard(idx)
			else:
				self._sel.add(idx)
		elif mode == 'extended':
			if idx in self._sel:
				self._sel.discard(idx)
			else:
				self._sel.add(idx)

	def _ensureVisible(self, idx):
		bd   = int(self._opts.get('borderwidth') or 0)
		visH = max(1, self._h - 2*bd)
		if idx < self._scrollY:
			self._scrollY = idx
		elif idx >= self._scrollY + visH:
			self._scrollY = idx - visH + 1

	def _handleMouse(self, mx, my, bstate):
		bd    = int(self._opts.get('borderwidth') or 0)
		visH  = max(1, self._h - 2*bd)
		by    = self._y + bd
		total = len(self._items)
		barX  = self._x + self._w - bd

		# Scroll wheel anywhere on the widget
		if bstate & curses.BUTTON4_PRESSED:
			self._scrollY = max(0, self._scrollY - 3)
			self._markDirty()
			return True
		if bstate & curses.BUTTON5_PRESSED:
			self._scrollY = min(max(0, total - visH), self._scrollY + 3)
			self._markDirty()
			return True

		release = bool(bstate & (curses.BUTTON1_RELEASED | curses.BUTTON1_CLICKED))
		press   = bool(bstate & curses.BUTTON1_PRESSED)

		# Scrollbar drag in progress — continue regardless of mx
		if self._sbDrag:
			if release:
				self._sbDrag = False
			else:
				row   = my - by
				delta = row - self._sbDragAnchorRow
				self._scrollY = max(0, min(
					max(0, total - visH),
					self._sbDragAnchorScroll + round(delta * total / visH),
				))
				self._markDirty()
			return True

		# Scrollbar click: press on thumb starts drag; above/below pages
		if total > visH and barX < self._x + self._w and mx == barX:
			row        = my - by
			thumbStart = int(self._scrollY * visH / total)
			thumbSize  = max(1, int(visH * visH / total))
			if 0 <= row < visH:
				if thumbStart <= row < thumbStart + thumbSize:
					if press:
						self._sbDrag             = True
						self._sbDragAnchorRow    = row
						self._sbDragAnchorScroll = self._scrollY
				elif row < thumbStart:
					self._scrollY = max(0, self._scrollY - visH)
					self._markDirty()
				else:
					self._scrollY = min(max(0, total - visH), self._scrollY + visH)
					self._markDirty()
			return True

		# Normal item click
		i = self._scrollY + (my - self._y - bd)
		if 0 <= i < len(self._items):
			mode = self._opts.get('selectmode', 'browse')
			self._active = i
			self._toggleOrSelect(i, mode)
			self._dispatch('<ListboxSelect>', _LBEvent(self, i))
			self._markDirty()
		return False


class _LBEvent:
	def __init__(self, widget, index):
		self.widget = widget
		self.index  = index
		self.type   = 'ListboxSelect'
		self.char   = ''
		self.keysym = ''
