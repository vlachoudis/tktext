import curses
from ._core import Widget, _addStr, _fillRect, _drawBorder, _clip, _pad
from ._events import (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_PPAGE, KEY_NPAGE,
	KEY_ENTER, KEY_CR, KEY_SPACE)


class Treeview(Widget):
	"""Hierarchical tree / table widget.  Mirrors tkinter.ttk.Treeview."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'columns':	(),
			'show':		'tree headings',
			'selectmode':	'browse',
			'displaycolumns':'#all',
			'height':	10,
		})
		kwargs.setdefault('relief', 'sunken')
		kwargs.setdefault('borderwidth', 1)
		if kwargs:
			self.configure(**kwargs)

		# Items: iid -> dict with keys:
		#   text, values, open, tags, parent, children
		self._items = {'': {
			'text': '', 'values': [], 'open': True,
			'tags': [], 'parent': None, 'children': [],
		}}
		self._iidCounter = 0

		# Column config: col_id -> {width, minwidth, stretch, heading, anchor}
		self._colCfg  = {}
		self._headCfg = {}	# col_id -> {text, anchor, command}

		# Set up '#0' (tree column) defaults
		self._colCfg['#0'] = {'width': 20, 'minwidth': 10, 'stretch': True,
			'anchor': 'w'}
		self._headCfg['#0'] = {'text': '', 'anchor': 'w', 'command': None}

		# Set up extra columns from 'columns' option
		for col in (kwargs.get('columns') or ()):
			cid = str(col)
			self._colCfg[cid]  = {'width': 15, 'minwidth': 10, 'stretch': True,
				'anchor': 'w'}
			self._headCfg[cid] = {'text': cid, 'anchor': 'w', 'command': None}

		# View state
		self._sel       = []		# list of selected iids
		self._focusIid  = ''		# iid of focused row
		self._scrollY   = 0		# first visible row index (in flat list)
		self._flatCache = None		# cached flat list of (iid, depth)
		self._tagCfg    = {}		# tag -> {fg, bg, font}

	# ------------------------------------------------------------------
	# Column / heading configuration
	# ------------------------------------------------------------------

	def column(self, col, option=None, **kwargs):
		"""Configure or query column *col*."""
		cid = str(col)
		if cid not in self._colCfg:
			self._colCfg[cid] = {'width': 15, 'minwidth': 10,
				'stretch': True, 'anchor': 'w'}
		if option:
			return self._colCfg[cid].get(option)
		self._colCfg[cid].update(kwargs)
		self._markDirty()

	def heading(self, col, option=None, **kwargs):
		"""Configure or query column heading *col*."""
		cid = str(col)
		if cid not in self._headCfg:
			self._headCfg[cid] = {'text': cid, 'anchor': 'w', 'command': None}
		if option:
			return self._headCfg[cid].get(option)
		self._headCfg[cid].update(kwargs)
		self._markDirty()

	# ------------------------------------------------------------------
	# Tag configuration
	# ------------------------------------------------------------------

	def tagConfigure(self, name, **kwargs):
		self._tagCfg[name] = kwargs
		self._markDirty()

	tag_configure = tagConfigure

	def tagCget(self, name, option):
		return self._tagCfg.get(name, {}).get(option)

	tag_cget = tagCget

	# ------------------------------------------------------------------
	# Item manipulation
	# ------------------------------------------------------------------

	def insert(self, parent, index, iid=None, **kwargs):
		"""Insert a new item.  Return the item's iid."""
		if iid is None:
			self._iidCounter += 1
			iid = f'I{self._iidCounter:04d}'
		iid = str(iid)
		parent = str(parent)

		if parent not in self._items:
			raise ValueError(f'Parent item {parent!r} not found')
		if iid in self._items:
			raise ValueError(f'Item {iid!r} already exists')

		self._items[iid] = {
			'text':     str(kwargs.get('text', '')),
			'values':   list(kwargs.get('values', [])),
			'open':     bool(kwargs.get('open', False)),
			'tags':     list(kwargs.get('tags', [])),
			'parent':   parent,
			'children': [],
		}

		siblings = self._items[parent]['children']
		if index == 'end' or index == 'END':
			siblings.append(iid)
		else:
			idx = max(0, min(int(index), len(siblings)))
			siblings.insert(idx, iid)

		self._flatCache = None
		self._markDirty()
		return iid

	def delete(self, *items):
		"""Delete items (and their subtrees)."""
		for iid in items:
			iid = str(iid)
			if iid not in self._items or iid == '':
				continue
			self._deleteSubtree(iid)
		self._flatCache = None
		self._markDirty()

	def _deleteSubtree(self, iid):
		item = self._items.get(iid)
		if not item:
			return
		for child in list(item['children']):
			self._deleteSubtree(child)
		parent = item['parent']
		if parent and parent in self._items:
			siblings = self._items[parent]['children']
			if iid in siblings:
				siblings.remove(iid)
		del self._items[iid]
		if iid in self._sel:
			self._sel.remove(iid)
		if self._focusIid == iid:
			self._focusIid = ''

	def detach(self, *items):
		"""Remove items from tree without deleting them."""
		for iid in items:
			iid = str(iid)
			item = self._items.get(iid)
			if item:
				p = item['parent']
				if p and p in self._items:
					sib = self._items[p]['children']
					if iid in sib:
						sib.remove(iid)
				item['parent'] = None
		self._flatCache = None
		self._markDirty()

	def reattach(self, item, parent, index):
		"""Reattach a detached item."""
		item   = str(item)
		parent = str(parent)
		if item not in self._items or parent not in self._items:
			return
		self._items[item]['parent'] = parent
		siblings = self._items[parent]['children']
		if item not in siblings:
			if index == 'end':
				siblings.append(item)
			else:
				siblings.insert(int(index), item)
		self._flatCache = None
		self._markDirty()

	def move(self, item, parent, index):
		self.detach(item)
		self.reattach(item, parent, index)

	def item(self, iid, option=None, **kwargs):
		"""Get or set item options."""
		iid = str(iid)
		if iid not in self._items:
			raise ValueError(f'Item {iid!r} not found')
		node = self._items[iid]
		if option is not None:
			return node.get(option)
		if kwargs:
			for k, v in kwargs.items():
				if k == 'values':
					node['values'] = list(v)
				elif k == 'tags':
					node['tags'] = list(v)
				else:
					node[k] = v
			self._flatCache = None
			self._markDirty()
		return dict(node)

	def set(self, item, column=None, value=None):
		"""Get or set the value of *column* in *item*."""
		item = str(item)
		node = self._items.get(item)
		if node is None:
			return
		cols = list(self._opts.get('columns') or [])
		if column is None:
			# Return all values as dict
			return {str(c): (node['values'][i] if i < len(node['values']) else '')
				for i, c in enumerate(cols)}
		if value is None:
			cid = str(column)
			if cid in cols:
				idx = cols.index(cid)
				vals = node['values']
				return vals[idx] if idx < len(vals) else ''
			return ''
		# Set
		cid  = str(column)
		if cid in cols:
			idx = cols.index(cid)
			vals = node['values']
			while len(vals) <= idx:
				vals.append('')
			vals[idx] = value
			self._markDirty()

	def getChildren(self, item=''):
		"""Return tuple of children iids of *item*."""
		item = str(item)
		node = self._items.get(item)
		return tuple(node['children']) if node else ()

	get_children = getChildren

	def getParent(self, item):
		"""Return parent iid of *item*."""
		item = str(item)
		node = self._items.get(item)
		return node['parent'] if node else ''

	get_parent = getParent

	def index(self, item):
		"""Return integer index of *item* among its siblings."""
		item = str(item)
		node = self._items.get(item)
		if not node:
			return 0
		parent = node['parent']
		if parent is None:
			return 0
		siblings = self._items[parent]['children']
		return siblings.index(item) if item in siblings else 0

	def prev(self, item):
		"""Return the iid preceding *item* among its siblings."""
		item = str(item)
		node = self._items.get(item)
		if not node:
			return ''
		parent = node['parent']
		if parent is None:
			return ''
		siblings = self._items[parent]['children']
		idx = siblings.index(item) if item in siblings else 0
		return siblings[idx - 1] if idx > 0 else ''

	def next(self, item):
		"""Return the iid following *item* among its siblings."""
		item = str(item)
		node = self._items.get(item)
		if not node:
			return ''
		parent = node['parent']
		if parent is None:
			return ''
		siblings = self._items[parent]['children']
		idx = siblings.index(item) if item in siblings else -1
		return siblings[idx + 1] if idx < len(siblings) - 1 else ''

	def exists(self, item):
		return str(item) in self._items

	# Selection

	def selection(self):
		"""Return tuple of selected iids."""
		return tuple(self._sel)

	def selectionSet(self, *items):
		"""Set selection to *items*."""
		self._sel = [str(i) for i in items if str(i) in self._items]
		self._markDirty()

	selection_set = selectionSet

	def selectionAdd(self, *items):
		for i in items:
			iid = str(i)
			if iid not in self._sel and iid in self._items:
				self._sel.append(iid)
		self._markDirty()

	selection_add = selectionAdd

	def selectionRemove(self, *items):
		for i in items:
			iid = str(i)
			if iid in self._sel:
				self._sel.remove(iid)
		self._markDirty()

	selection_remove = selectionRemove

	def selectionToggle(self, *items):
		for i in items:
			iid = str(i)
			if iid in self._sel:
				self._sel.remove(iid)
			elif iid in self._items:
				self._sel.append(iid)
		self._markDirty()

	selection_toggle = selectionToggle

	def focus(self, item=None):
		"""Get or set focused item."""
		if item is None:
			return self._focusIid
		self._focusIid = str(item)
		self._markDirty()

	def see(self, item):
		"""Scroll so that *item* is visible."""
		flat = self._getFlat()
		for i, (iid, _) in enumerate(flat):
			if iid == str(item):
				bd   = int(self._opts.get('borderwidth') or 0)
				show = self._opts.get('show', 'tree headings')
				hasHead = 'headings' in show
				visH = max(1, self._h - 2*bd - (1 if hasHead else 0))
				if i < self._scrollY:
					self._scrollY = i
				elif i >= self._scrollY + visH:
					self._scrollY = i - visH + 1
				self._markDirty()
				return

	def open(self, item, value=None):
		"""Get or set open state of *item*."""
		iid = str(item)
		node = self._items.get(iid)
		if node is None:
			return False
		if value is None:
			return node['open']
		node['open'] = bool(value)
		self._flatCache = None
		self._markDirty()

	# ------------------------------------------------------------------
	# Flat list (visible rows in tree order)
	# ------------------------------------------------------------------

	def _getFlat(self):
		if self._flatCache is None:
			result = []
			self._buildFlat('', 0, result)
			# Remove root itself
			self._flatCache = result
		return self._flatCache

	def _buildFlat(self, iid, depth, result):
		node = self._items.get(iid)
		if node is None:
			return
		if iid != '':
			result.append((iid, depth))
		if node['open'] or iid == '':
			for child in node['children']:
				self._buildFlat(child, depth + (0 if iid == '' else 1), result)

	# ------------------------------------------------------------------
	# Preferred size / layout
	# ------------------------------------------------------------------

	def _preferredSize(self):
		bd  = int(self._opts.get('borderwidth') or 0)
		ow  = int(self._opts.get('width') or 0)
		oh  = int(self._opts.get('height') or 10)
		if not ow:
			ow = sum(c.get('width', 15) for c in self._colCfg.values()) + 2
		return (ow + 2*bd, oh + 2*bd)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def _colList(self):
		"""Return ordered list of visible column ids."""
		show = self._opts.get('show', 'tree headings')
		cols = []
		if 'tree' in show:
			cols.append('#0')
		extra = list(self._opts.get('columns') or [])
		disp  = self._opts.get('displaycolumns', '#all')
		if disp == '#all':
			cols.extend(str(c) for c in extra)
		else:
			cols.extend(str(c) for c in disp if str(c) in [str(e) for e in extra])
		return cols

	def _colWidths(self, totalW):
		"""Return list of (col_id, width) for visible columns."""
		cols   = self._colList()
		widths = []
		for cid in cols:
			cfg = self._colCfg.get(cid, {})
			widths.append(cfg.get('width', 15))
		# Distribute remaining space to stretch columns
		used    = sum(widths)
		extra   = totalW - used
		stretch = [i for i, cid in enumerate(cols)
			if self._colCfg.get(cid, {}).get('stretch', True)]
		if stretch and extra > 0:
			per = extra // len(stretch)
			for i in stretch:
				widths[i] += per
		return list(zip(cols, widths))

	def _getItemAttr(self, iid):
		"""Return curses attr for item, considering tags."""
		node = self._items.get(str(iid), {})
		for tag in reversed(node.get('tags', [])):
			cfg = self._tagCfg.get(tag, {})
			if cfg:
				fg = cfg.get('foreground', '') or cfg.get('fg', '')
				bg = cfg.get('background', '') or cfg.get('bg', '')
				if fg or bg:
					return self._getAttr(fg=fg, bg=bg)
		return self._getAttr()

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return

		bd     = int(self._opts.get('borderwidth') or 0)
		show   = self._opts.get('show', 'tree headings')
		hasHead = 'headings' in show
		relief = self._opts.get('relief', 'sunken')
		attr   = self._getAttr()

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)
		if bd > 0:
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		innerX  = self._x + bd
		innerY  = self._y + bd
		innerW  = max(1, self._w - 2*bd)
		innerH  = max(1, self._h - 2*bd)

		colInfo = self._colWidths(innerW)
		headRow = innerY
		dataY   = innerY + (1 if hasHead else 0)
		visH    = innerH - (1 if hasHead else 0)

		# ---- heading row ----
		if hasHead:
			x = innerX
			headAttr = self._getAttr(bold=True) | curses.A_BOLD
			for cid, cw in colInfo:
				hcfg = self._headCfg.get(cid, {})
				htxt = str(hcfg.get('text', cid))
				_addStr(scr, headRow, x, _pad(htxt, cw), headAttr)
				x += cw

		# ---- data rows ----
		flat = self._getFlat()
		total = len(flat)

		for rowIdx in range(visH):
			flatIdx = self._scrollY + rowIdx
			screenY = dataY + rowIdx

			if flatIdx >= total:
				_addStr(scr, screenY, innerX, ' ' * innerW, attr)
				continue

			iid, depth = flat[flatIdx]
			node = self._items.get(iid, {})
			isSelected = iid in self._sel
			isFocused  = iid == self._focusIid and self._focused

			if isSelected:
				rowAttr = attr | curses.A_REVERSE
			elif isFocused:
				rowAttr = attr | curses.A_BOLD
			else:
				rowAttr = self._getItemAttr(iid)

			x = innerX
			for i, (cid, cw) in enumerate(colInfo):
				if cid == '#0':
					# tree column: indent + expand indicator + text
					indent  = '  ' * depth
					hasKids = bool(node.get('children'))
					if hasKids:
						marker = '▼ ' if node.get('open') else '▶ '
					else:
						marker = '  '
					cellText = indent + marker + str(node.get('text', ''))
				else:
					cols = list(self._opts.get('columns') or [])
					cidx = cols.index(cid) if cid in cols else -1
					vals = node.get('values', [])
					cellText = str(vals[cidx]) if 0 <= cidx < len(vals) else ''

				_addStr(scr, screenY, x, _pad(cellText, cw), rowAttr)
				x += cw

		# Scrollbar
		if total > visH and innerX + innerW - 1 >= innerX:
			barX = innerX + innerW - 1
			thumbStart = int(self._scrollY * visH / total) if total else 0
			thumbSize  = max(1, int(visH * visH / total))
			for i in range(visH):
				ch = '#' if thumbStart <= i < thumbStart + thumbSize else '|'
				try:
					scr.addch(dataY + i, barX, ch, attr)
				except curses.error:
					pass

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _isFocusable(self):
		return self._opts.get('state', 'normal') == 'normal'

	def _currentFlatIndex(self):
		flat = self._getFlat()
		for i, (iid, _) in enumerate(flat):
			if iid == self._focusIid:
				return i
		return 0

	def _handleKey(self, key):
		flat = self._getFlat()
		if not flat:
			return super()._handleKey(key)

		bd      = int(self._opts.get('borderwidth') or 0)
		show    = self._opts.get('show', 'tree headings')
		hasHead = 'headings' in show
		visH    = max(1, self._h - 2*bd - (1 if hasHead else 0))
		ci      = self._currentFlatIndex()

		if key == KEY_UP:
			ci = max(0, ci - 1)
		elif key == KEY_DOWN:
			ci = min(len(flat) - 1, ci + 1)
		elif key == KEY_HOME:
			ci = 0
		elif key == KEY_END:
			ci = max(0, len(flat) - 1)
		elif key == KEY_PPAGE:
			ci = max(0, ci - visH)
		elif key == KEY_NPAGE:
			ci = min(len(flat) - 1, ci + visH)
		elif key == KEY_RIGHT:
			iid  = flat[ci][0]
			node = self._items.get(iid, {})
			if node.get('children') and not node.get('open'):
				node['open'] = True
				self._flatCache = None
			elif node.get('children') and node.get('open'):
				ci = min(len(flat) - 1, ci + 1)
		elif key == KEY_LEFT:
			iid  = flat[ci][0]
			node = self._items.get(iid, {})
			if node.get('open') and node.get('children'):
				node['open'] = False
				self._flatCache = None
			else:
				parent = node.get('parent', '')
				if parent:
					for j, (piid, _) in enumerate(self._getFlat()):
						if piid == parent:
							ci = j
							break
		elif key in (KEY_ENTER, KEY_CR, KEY_SPACE):
			iid  = flat[ci][0]
			node = self._items.get(iid, {})
			if node.get('children'):
				node['open'] = not node.get('open', False)
				self._flatCache = None
			self._dispatch('<<TreeviewSelect>>', _TVEvent(self, iid))
		else:
			return super()._handleKey(key)

		if 0 <= ci < len(self._getFlat()):
			newIid = self._getFlat()[ci][0]
			self._focusIid = newIid
			mode = self._opts.get('selectmode', 'browse')
			if mode in ('browse', 'extended'):
				self._sel = [newIid]
			self._ensureVisible(ci)
			self._dispatch('<<TreeviewSelect>>', _TVEvent(self, newIid))
			self._markDirty()
		return True

	def _ensureVisible(self, flatIdx):
		bd      = int(self._opts.get('borderwidth') or 0)
		show    = self._opts.get('show', 'tree headings')
		hasHead = 'headings' in show
		visH    = max(1, self._h - 2*bd - (1 if hasHead else 0))
		if flatIdx < self._scrollY:
			self._scrollY = flatIdx
		elif flatIdx >= self._scrollY + visH:
			self._scrollY = flatIdx - visH + 1

	def _handleMouse(self, mx, my, bstate):
		bd      = int(self._opts.get('borderwidth') or 0)
		show    = self._opts.get('show', 'tree headings')
		hasHead = 'headings' in show
		dataY   = self._y + bd + (1 if hasHead else 0)
		flatIdx = self._scrollY + (my - dataY)
		flat    = self._getFlat()

		if 0 <= flatIdx < len(flat):
			iid  = flat[flatIdx][0]
			node = self._items.get(iid, {})
			self._focusIid = iid
			mode = self._opts.get('selectmode', 'browse')
			if mode in ('browse', 'extended'):
				self._sel = [iid]
			elif mode == 'none':
				pass
			# Toggle on double-click (simulate with single click on marker column)
			if bstate & curses.BUTTON1_CLICKED:
				indent = 2 * flat[flatIdx][1]
				markerX = self._x + bd + indent
				if mx in (markerX, markerX + 1) and node.get('children'):
					node['open'] = not node.get('open', False)
					self._flatCache = None
			self._dispatch('<<TreeviewSelect>>', _TVEvent(self, iid))
			self._markDirty()
		return False


class _TVEvent:
	def __init__(self, widget, iid):
		self.widget = widget
		self.iid    = iid
		self.type   = 'TreeviewSelect'
		self.char   = ''
		self.keysym = ''
