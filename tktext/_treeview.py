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

import curses
from . import _core
from ._core import TclError, Widget, _addStr, _fillRect, _drawBorder, _pad, _int, _initArgs, _cellsX, _cellX, _cellY, _pxBox
from ._listbox import _ScrollMixin
from ._events import (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_PPAGE, KEY_NPAGE, KEY_ENTER, KEY_SPACE,
	B1_PRESS, B1_RELEASE, B1_CLICK, B1_DCLICK, MOTION, isWheel)


def _flatten(items):
	"""Accept f(a, b) as well as f((a, b)) like tkinter."""
	out = []
	for it in items:
		if isinstance(it, (tuple, list)):
			out.extend(str(i) for i in it)
		elif it is not None:
			out.append(str(it))
	return out


def _asList(v):
	if v is None or v == '':
		return []
	if isinstance(v, str):
		return v.split()
	return list(v)


class Treeview(_ScrollMixin, Widget):
	"""Hierarchical tree / table widget.  Mirrors tkinter.ttk.Treeview."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'columns':		(),
			'show':			'tree headings',
			'selectmode':		'extended',
			'displaycolumns':	('#all',),
			'height':		10,
			'yscrollcommand':	None,
			'xscrollcommand':	None,
		})
		kwargs.setdefault('relief', 'sunken')
		kwargs.setdefault('borderwidth', 1)

		# Items: iid -> dict with keys:
		#   text, values, open, tags, parent, children
		self._treeItems = {'': {
			'text': '', 'values': [], 'open': True,
			'tags': [], 'parent': None, 'children': [], 'image': '',
		}}
		self._iidCounter = 0

		# Column config: col_id -> {width, minwidth, stretch, anchor}
		self._colCfg  = {'#0': {'width': 20, 'minwidth': 4, 'stretch': True,
			'anchor': 'w', 'id': '#0'}}
		self._headCfg = {'#0': {'text': '', 'anchor': 'w', 'command': None,
			'image': ''}}

		# View state
		self._sel       = []		# list of selected iids
		self._focusIid  = ''		# iid of focused row
		self._scrollY   = 0		# first visible row index (in flat list)
		self._flatCache = None		# cached flat list of (iid, depth)
		self._tagCfg    = {}		# tag -> {foreground, background, font}
		self._tagBinds  = {}		# tag -> {sequence: [callable]}
		self._sbDrag    = None

		if kwargs:
			Treeview.configure(self, **kwargs)

	def configure(self, cnf=None, **kwargs):
		if cnf:
			kwargs.update(cnf)
		if 'columns' in kwargs:
			cols = kwargs['columns']
			if isinstance(cols, str):
				cols = cols.split()
			kwargs['columns'] = tuple(str(c) for c in (cols or ()))
			for cid in kwargs['columns']:
				self._colCfg.setdefault(cid, {'width': 15, 'minwidth': 4,
					'stretch': True, 'anchor': 'w', 'id': cid})
				self._headCfg.setdefault(cid, {'text': '', 'anchor': 'w',
					'command': None, 'image': ''})
		return super().configure(**kwargs)

	config = configure

	# ------------------------------------------------------------------
	# Column / heading configuration
	# ------------------------------------------------------------------

	def _colId(self, col):
		if isinstance(col, int):
			cols = list(self._opts.get('columns') or ())
			return cols[col] if 0 <= col < len(cols) else str(col)
		s = str(col)
		if s.startswith('#') and s[1:].isdigit() and s != '#0':
			n    = int(s[1:]) - 1
			disp = self._colList()
			disp = [c for c in disp if c != '#0']
			return disp[n] if 0 <= n < len(disp) else s
		return s

	def column(self, col, option=None, **kwargs):
		"""Configure or query column *col*."""
		cid = self._colId(col)
		cfg = self._colCfg.setdefault(cid, {'width': 15, 'minwidth': 4,
			'stretch': True, 'anchor': 'w', 'id': cid})
		if option:
			return self._colReport(cfg).get(option)
		if not kwargs:
			return self._colReport(cfg)
		for k, v in kwargs.items():
			if k in ('width', 'minwidth'):
				try:
					v = _cellsX(v)
				except (TclError, ValueError, TypeError):
					v = cfg.get(k, 0)
			cfg[k] = v
		self._markDirty()
		return None

	@staticmethod
	def _colReport(cfg: dict) -> dict:
		"""Column options as reported to the program: widths are kept
		in cells but tkinter programs see pixels"""
		result = dict(cfg)
		for k in ('width', 'minwidth'):
			if isinstance(result.get(k), int):
				result[k] *= _core.PX
		return result

	def heading(self, col, option=None, **kwargs):
		"""Configure or query column heading *col*."""
		cid = self._colId(col)
		cfg = self._headCfg.setdefault(cid, {'text': '', 'anchor': 'w',
			'command': None, 'image': ''})
		if option:
			return cfg.get(option)
		if not kwargs:
			return dict(cfg)
		cfg.update(kwargs)
		self._markDirty()
		return None

	# ------------------------------------------------------------------
	# Tag configuration
	# ------------------------------------------------------------------

	def tagConfigure(self, name, option=None, **kwargs):
		cfg = self._tagCfg.setdefault(name, {})
		if option is not None:
			return cfg.get(option)
		if not kwargs:
			return dict(cfg)
		for k, v in kwargs.items():
			k = {'fg': 'foreground', 'bg': 'background'}.get(k, k)
			cfg[k] = v
		self._markDirty()
		return None

	def tagCget(self, name, option):
		option = {'fg': 'foreground', 'bg': 'background'}.get(option, option)
		return self._tagCfg.get(name, {}).get(option)

	def _tagNames(self):
		names = set(self._tagCfg)
		for n in self._treeItems.values():
			names.update(n.get('tags') or ())
		return tuple(sorted(names))

	def _tagAdd(self, tag, items):
		"""Tk 8.6.9+ '$tv tag add tag items'."""
		for iid in items:
			node = self._treeItems.get(str(iid))
			if node is not None and tag not in node['tags']:
				node['tags'] = list(node['tags']) + [tag]
		self._markDirty()

	def _tagRemove(self, tag, items=None):
		"""'$tv tag remove tag ?items?' (all items when omitted)."""
		targets = self._treeItems.keys() if items is None else [str(i) for i in items]
		for iid in targets:
			node = self._treeItems.get(iid)
			if node is not None and tag in node['tags']:
				node['tags'] = [t for t in node['tags'] if t != tag]
		self._markDirty()

	def tagHas(self, tagname, item=None):
		if item is None:
			return tuple(iid for iid, n in self._treeItems.items()
				if iid and tagname in n['tags'])
		return tagname in self._treeItems.get(str(item), {}).get('tags', [])

	def tagBind(self, tagname, sequence=None, callback=None):
		self._tagBinds.setdefault(tagname, {}).setdefault(sequence, []).append(callback)

	tag_configure	= tagConfigure
	tag_cget	= tagCget
	tag_has		= tagHas
	tag_bind	= tagBind

	# ------------------------------------------------------------------
	# Item manipulation
	# ------------------------------------------------------------------

	def insert(self, parent, index, iid=None, **kwargs):
		"""Insert a new item.  Return the item's iid."""
		if iid is None and kwargs.get('id') not in (None, ''):
			iid = kwargs.pop('id')		# tkinter passes -id too
		kwargs.pop('id', None)
		if iid is None:
			while True:
				self._iidCounter += 1
				iid = f'I{self._iidCounter:03X}'
				if iid not in self._treeItems:
					break
		iid    = str(iid)
		parent = str(parent)

		if parent not in self._treeItems:
			raise TclError(f'Item {parent} not found')
		if iid in self._treeItems:
			raise TclError(f'Item {iid} already exists')

		self._treeItems[iid] = {
			'text':     str(kwargs.get('text', '')),
			'values':   _asList(kwargs.get('values')),
			'open':     bool(kwargs.get('open', False)),
			'tags':     _asList(kwargs.get('tags')),
			'image':    kwargs.get('image', ''),
			'parent':   parent,
			'children': [],
		}

		siblings = self._treeItems[parent]['children']
		if index in ('end', 'END'):
			siblings.append(iid)
		else:
			siblings.insert(max(0, min(_int(index), len(siblings))), iid)

		self._flatCache = None
		self._markDirty()
		return iid

	def delete(self, *items):
		"""Delete items (and their subtrees)."""
		changed = False
		for iid in _flatten(items):
			if iid in self._treeItems and iid != '':
				changed |= iid in self._sel
				self._deleteSubtree(iid)
		self._flatCache = None
		self._markDirty()
		if changed:
			self._fireVirtual('<<TreeviewSelect>>')

	def _deleteSubtree(self, iid):
		item = self._treeItems.get(iid)
		if not item:
			return
		for child in list(item['children']):
			self._deleteSubtree(child)
		parent = item['parent']
		if parent is not None and parent in self._treeItems:
			siblings = self._treeItems[parent]['children']
			if iid in siblings:
				siblings.remove(iid)
		del self._treeItems[iid]
		if iid in self._sel:
			self._sel.remove(iid)
		if self._focusIid == iid:
			self._focusIid = ''

	def detach(self, *items):
		"""Remove items from tree without deleting them."""
		for iid in _flatten(items):
			item = self._treeItems.get(iid)
			if item and iid != '':
				p = item['parent']
				if p is not None and p in self._treeItems:
					sib = self._treeItems[p]['children']
					if iid in sib:
						sib.remove(iid)
				item['parent'] = None
		self._flatCache = None
		self._markDirty()

	def reattach(self, item, parent, index):
		"""Reattach (move) *item* under *parent* at *index*."""
		item   = str(item)
		parent = str(parent)
		if item not in self._treeItems or parent not in self._treeItems:
			raise TclError(f'Item {item} not found')
		old = self._treeItems[item]['parent']
		if old is not None and old in self._treeItems:
			sib = self._treeItems[old]['children']
			if item in sib:
				sib.remove(item)
		self._treeItems[item]['parent'] = parent
		siblings = self._treeItems[parent]['children']
		if index in ('end', 'END'):
			siblings.append(item)
		else:
			siblings.insert(max(0, min(_int(index), len(siblings))), item)
		self._flatCache = None
		self._markDirty()

	move = reattach

	def item(self, iid, option=None, **kwargs):
		"""Get or set item options."""
		iid = str(iid)
		if iid not in self._treeItems:
			raise TclError(f'Item {iid} not found')
		node = self._treeItems[iid]
		if option is not None:
			if option in ('values', 'tags'):
				return tuple(node[option])
			return node.get(option)
		if kwargs:
			for k, v in kwargs.items():
				if k in ('values', 'tags'):
					node[k] = _asList(v)
				elif k == 'open':
					node[k] = bool(v)
				elif k == 'text':
					node[k] = str(v)
				else:
					node[k] = v
			self._flatCache = None
			self._markDirty()
			return None
		return {'text': node['text'], 'image': node.get('image', ''),
			'values': tuple(node['values']), 'open': node['open'],
			'tags': tuple(node['tags'])}

	def set(self, item, column=None, value=None):
		"""Get or set the value of *column* in *item*."""
		item = str(item)
		node = self._treeItems.get(item)
		if node is None:
			raise TclError(f'Item {item} not found')
		cols = list(self._opts.get('columns') or [])
		if column is None:
			return {c: (node['values'][i] if i < len(node['values']) else '')
				for i, c in enumerate(cols)}
		cid = self._colId(column)
		if cid not in cols:
			raise TclError(f'Invalid column index {column}')
		idx  = cols.index(cid)
		vals = node['values']
		if value is None:
			return vals[idx] if idx < len(vals) else ''
		while len(vals) <= idx:
			vals.append('')
		vals[idx] = value
		self._markDirty()
		return None

	def getChildren(self, item=''):
		"""Return tuple of children iids of *item*."""
		node = self._treeItems.get(str(item) if item is not None else '')
		return tuple(node['children']) if node else ()

	def setChildren(self, item, *newchildren):
		item = str(item)
		for c in list(self.getChildren(item)):
			self.detach(c)
		for c in _flatten(newchildren):
			self.reattach(c, item, 'end')

	def getParent(self, item):
		"""Return parent iid of *item*."""
		node = self._treeItems.get(str(item))
		return (node['parent'] or '') if node else ''

	get_children	= getChildren
	set_children	= setChildren
	get_parent	= getParent
	parent		= getParent

	def index(self, item):
		"""Return integer index of *item* among its siblings."""
		node = self._treeItems.get(str(item))
		if not node or node['parent'] is None:
			return 0
		siblings = self._treeItems[node['parent']]['children']
		return siblings.index(str(item)) if str(item) in siblings else 0

	def prev(self, item):
		"""Return the iid preceding *item* among its siblings."""
		node = self._treeItems.get(str(item))
		if not node or node['parent'] is None:
			return ''
		siblings = self._treeItems[node['parent']]['children']
		idx = siblings.index(str(item))
		return siblings[idx - 1] if idx > 0 else ''

	def next(self, item):
		"""Return the iid following *item* among its siblings."""
		node = self._treeItems.get(str(item))
		if not node or node['parent'] is None:
			return ''
		siblings = self._treeItems[node['parent']]['children']
		idx = siblings.index(str(item))
		return siblings[idx + 1] if idx < len(siblings) - 1 else ''

	def exists(self, item):
		return str(item) in self._treeItems

	# Selection

	def selection(self, *args):
		"""Return tuple of selected iids."""
		if args:		# old-style selection('set', items)
			op, items = args[0], args[1:]
			getattr(self, f'selection_{op}')(*items)
			return None
		return tuple(self._sel)

	def _setSelection(self, newSel):
		newSel = [i for i in newSel if i in self._treeItems and i != '']
		if newSel != self._sel:
			self._sel = newSel
			self._markDirty()
			self._fireVirtual('<<TreeviewSelect>>')

	def selectionSet(self, *items):
		"""Set selection to *items*."""
		self._setSelection(_flatten(items))

	def selectionAdd(self, *items):
		self._setSelection(self._sel + [i for i in _flatten(items) if i not in self._sel])

	def selectionRemove(self, *items):
		rm = set(_flatten(items))
		self._setSelection([i for i in self._sel if i not in rm])

	def selectionToggle(self, *items):
		sel = list(self._sel)
		for i in _flatten(items):
			if i in sel:
				sel.remove(i)
			else:
				sel.append(i)
		self._setSelection(sel)

	selection_set		= selectionSet
	selection_add		= selectionAdd
	selection_remove	= selectionRemove
	selection_toggle	= selectionToggle

	def focus(self, item=None):
		"""Get or set the focused item (tkinter semantics).  Use
		focus_set() to give the widget keyboard focus."""
		if item is None:
			return self._focusIid
		self._focusIid = str(item)
		self._markDirty()
		return None

	def see(self, item):
		"""Open the ancestors of *item* and scroll it into view."""
		iid  = str(item)
		node = self._treeItems.get(iid)
		if node is None:
			return
		p = node['parent']
		while p:
			self._treeItems[p]['open'] = True
			p = self._treeItems[p]['parent']
		self._flatCache = None
		for i, (fid, _) in enumerate(self._getFlat()):
			if fid == iid:
				self._ensureVisible(i)
				break
		self._markDirty()

	def open(self, item, value=None):
		"""Get or set open state of *item*."""
		node = self._treeItems.get(str(item))
		if node is None:
			return False
		if value is None:
			return node['open']
		node['open'] = bool(value)
		self._flatCache = None
		self._markDirty()
		return None

	# ------------------------------------------------------------------
	# Flat list (visible rows in tree order)
	# ------------------------------------------------------------------

	def _getFlat(self):
		if self._flatCache is None:
			result = []
			self._buildFlat('', -1, result)
			self._flatCache = result
		return self._flatCache

	def _buildFlat(self, iid, depth, result):
		node = self._treeItems.get(iid)
		if node is None:
			return
		if iid != '':
			result.append((iid, depth))
		if node['open'] or iid == '':
			for child in node['children']:
				self._buildFlat(child, depth + 1, result)

	# ------------------------------------------------------------------
	# Geometry helpers
	# ------------------------------------------------------------------

	def _hasHead(self) -> bool:
		return 'headings' in str(self._opts.get('show', 'tree headings'))

	def _visRows(self) -> int:
		return max(0, self._height - 2*self._border() - (1 if self._hasHead() else 0))

	def _totalRows(self) -> int:
		return len(self._getFlat())

	def _dataY(self) -> int:
		return self._y + self._border() + (1 if self._hasHead() else 0)

	def _innerW(self) -> int:
		w = max(1, self._width - 2*self._border())
		return w - 1 if self._showInternalBar() else w

	def _preferredSize(self):
		bd = self._cfgBorder()
		ow = _int(self._opts.get('width'))
		oh = _int(self._opts.get('height'), 10) or 10
		if not ow:
			ow = sum(self._colCfg.get(c, {}).get('width', 15) for c in self._colList())
		return (max(1, ow) + 2*bd, oh + 2*bd + (1 if self._hasHead() else 0))

	def _colList(self):
		"""Return ordered list of visible column ids."""
		show = str(self._opts.get('show', 'tree headings'))
		cols = ['#0'] if 'tree' in show else []
		extra = [str(c) for c in (self._opts.get('columns') or [])]
		disp  = self._opts.get('displaycolumns', '#all')
		if disp in ('#all', ('#all',), None):
			cols.extend(extra)
		else:
			if isinstance(disp, str):
				disp = disp.split()
			cols.extend(self._colId(c) for c in disp if self._colId(c) in extra)
		return cols

	def _colWidths(self, totalW):
		"""Return list of (col_id, width) for visible columns."""
		cols   = self._colList()
		widths = [max(0, _int(self._colCfg.get(c, {}).get('width', 15), 15)) for c in cols]
		extra  = totalW - sum(widths)
		stretch = [i for i, cid in enumerate(cols)
			if self._colCfg.get(cid, {}).get('stretch', True)]
		if stretch and extra > 0:
			per = extra // len(stretch)
			for i in stretch:
				widths[i] += per
			widths[stretch[-1]] += extra - per * len(stretch)
		return list(zip(cols, widths))

	def _preRender(self):
		self._clampScroll()
		self._notifyYScroll()

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def _getItemAttr(self, iid):
		"""Return curses attr for item, considering tags."""
		node  = self._treeItems.get(str(iid), {})
		fg = bg = ''
		bold = False
		for tag in node.get('tags', []):
			cfg = self._tagCfg.get(tag, {})
			fg  = cfg.get('foreground') or fg
			bg  = cfg.get('background') or bg
			bold = bold or 'bold' in str(cfg.get('font') or '').lower()
		return self._getAttr(fg=fg, bg=bg, bold=bold)

	def render(self, scr):
		if not self._isMapped():
			return

		bd      = self._border()
		relief  = self._opts.get('relief', 'sunken')
		attr    = self._getAttr()

		_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._height, self._width, relief, attr)

		innerX  = self._x + bd
		innerW  = self._innerW()
		colInfo = self._colWidths(innerW)
		dataY   = self._dataY()
		visH    = self._visRows()

		def cells(texts, y, a, anchors):
			x = innerX
			for (_, cw), text, anc in zip(colInfo, texts, anchors):
				w = min(cw, innerX + innerW - x)
				if w <= 0:
					break
				align = 'right' if anc in ('e', 'ne', 'se') else \
					'center' if anc in ('center', 'n', 's') else 'left'
				cell = _pad(text, max(0, w - 1), align) + ' ' if w > 1 else text[:w]
				_addStr(scr, y, x, _pad(cell, w), a)
				x += cw

		# ---- heading row ----
		if self._hasHead():
			texts   = [str(self._headCfg.get(c, {}).get('text', '')) for c, _ in colInfo]
			anchors = [self._headCfg.get(c, {}).get('anchor', 'w') for c, _ in colInfo]
			cells(texts, self._y + bd, self._getAttr(bold=True) | curses.A_UNDERLINE, anchors)

		# ---- data rows ----
		flat    = self._getFlat()
		cols    = [str(c) for c in (self._opts.get('columns') or [])]
		anchors = [self._colCfg.get(c, {}).get('anchor', 'w') for c, _ in colInfo]
		for rowIdx in range(visH):
			flatIdx = self._scrollY + rowIdx
			if flatIdx >= len(flat):
				break
			iid, depth = flat[flatIdx]
			node = self._treeItems.get(iid, {})
			if iid in self._sel:
				rowAttr = self._selectAttr()
			else:
				rowAttr = self._getItemAttr(iid)
			if iid == self._focusIid and self._focused:
				rowAttr |= curses.A_BOLD

			texts = []
			for cid, _ in colInfo:
				if cid == '#0':
					if node.get('children'):
						marker = '▼ ' if node.get('open') else '▶ '
					else:
						marker = '  '
					texts.append('  ' * depth + marker + str(node.get('text', '')))
				else:
					cidx = cols.index(cid) if cid in cols else -1
					vals = node.get('values', [])
					texts.append(str(vals[cidx]) if 0 <= cidx < len(vals) else '')
			cells(texts, dataY + rowIdx, rowAttr, anchors)

		if self._showInternalBar():
			self._drawInternalBar(scr, self._x + self._width - bd - 1, dataY, visH, attr)

	# ------------------------------------------------------------------
	# Identification
	# ------------------------------------------------------------------

	def identifyRow(self, y):
		"""Return the iid of the row at widget-relative *y* ('' if none)."""
		y = _cellY(y)
		i = self._scrollY + (y + self._y - self._dataY())
		flat = self._getFlat()
		return flat[i][0] if 0 <= i < len(flat) and y + self._y >= self._dataY() else ''

	def identifyColumn(self, x):
		"""Return '#n' for the column at widget-relative *x*."""
		x  = _cellX(x)
		cx = self._border()
		for cid, cw in self._colWidths(self._innerW()):
			if cx <= int(x) < cx + cw:
				if cid == '#0':
					return '#0'
				disp = [c for c, _ in self._colWidths(self._innerW()) if c != '#0']
				return f'#{disp.index(cid) + 1}'
			cx += cw
		return ''

	def identifyRegion(self, x, y):
		if self._hasHead() and _cellY(y) == self._border():
			return 'heading'
		row = self.identifyRow(y)
		if not row:
			return 'nothing'
		if self.identifyColumn(x) == '#0':
			depth = dict(self._getFlat()).get(row, 0)
			mx    = self._border() + 2 * depth
			if mx <= _cellX(x) < mx + 2 and self._treeItems[row]['children']:
				return 'tree'
		return 'cell'

	def identify(self, component, x, y):
		if component == 'row':
			return self.identifyRow(y)
		if component == 'column':
			return self.identifyColumn(x)
		if component == 'region':
			return self.identifyRegion(x, y)
		if component == 'item':
			return self.identifyRow(y)
		return ''

	def bbox(self, item, column=None):
		flat = self._getFlat()
		for i, (iid, _) in enumerate(flat):
			if iid == str(item):
				row = i - self._scrollY
				if not 0 <= row < self._visRows():
					return ''
				y = self._dataY() - self._y + row
				if column is None:
					return _pxBox((self._border(), y, self._innerW(), 1))
				cx = self._border()
				cid = self._colId(column)
				for c, cw in self._colWidths(self._innerW()):
					if c == cid:
						return _pxBox((cx, y, cw, 1))
					cx += cw
				return ''
		return ''

	def xview(self, *args):
		"""Horizontal scrolling of a tree is not supported."""
		if not args:
			return (0.0, 1.0)
		return None

	def xview_moveto(self, fraction):
		pass

	def xview_scroll(self, number, what):
		pass

	def identify_element(self, x, y):
		return ''

	identify_row	= identifyRow
	identify_column	= identifyColumn
	identify_region	= identifyRegion

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _currentFlatIndex(self):
		for i, (iid, _) in enumerate(self._getFlat()):
			if iid == self._focusIid:
				return i
		return 0

	def _toggle(self, iid):
		node = self._treeItems.get(iid)
		if not node or not node['children']:
			return
		node['open'] = not node['open']
		self._flatCache = None
		self._focusIid  = iid
		self._fireVirtual('<<TreeviewOpen>>' if node['open'] else '<<TreeviewClose>>',
			iid=iid)
		self._markDirty()

	def _selectRow(self, iid):
		self._focusIid = iid
		mode = self._opts.get('selectmode', 'extended')
		if mode != 'none':
			self._setSelection([iid])
		self._markDirty()

	def _handleKey(self, key):
		flat = self._getFlat()
		if not flat:
			return False

		visH = self._visRows()
		ci   = self._currentFlatIndex()

		if key == KEY_UP:
			ci = max(0, ci - 1)
		elif key == KEY_DOWN:
			ci = min(len(flat) - 1, ci + 1)
		elif key == KEY_HOME:
			ci = 0
		elif key == KEY_END:
			ci = len(flat) - 1
		elif key == KEY_PPAGE:
			ci = max(0, ci - visH)
		elif key == KEY_NPAGE:
			ci = min(len(flat) - 1, ci + visH)
		elif key == KEY_RIGHT:
			iid  = flat[ci][0]
			node = self._treeItems[iid]
			if node['children'] and not node['open']:
				self._toggle(iid)
				return True
			if node['children']:
				ci = min(len(flat) - 1, ci + 1)
		elif key == KEY_LEFT:
			iid  = flat[ci][0]
			node = self._treeItems[iid]
			if node['open'] and node['children']:
				self._toggle(iid)
				return True
			parent = node['parent']
			if parent:
				ci = next(j for j, (p, _) in enumerate(flat) if p == parent)
		elif key in (KEY_ENTER, KEY_SPACE):
			iid = flat[ci][0]
			if key == KEY_SPACE or not self._treeItems[iid]['children']:
				self._selectRow(iid)
			else:
				self._toggle(iid)
			return True
		else:
			return False

		flat = self._getFlat()
		if 0 <= ci < len(flat):
			self._selectRow(flat[ci][0])
			self._ensureVisible(ci)
		return True

	def _ensureVisible(self, flatIdx):
		visH = self._visRows()
		if flatIdx < self._scrollY:
			self._scrollY = flatIdx
		elif flatIdx >= self._scrollY + visH:
			self._scrollY = flatIdx - visH + 1
		self._clampScroll()

	def _dragLost(self):
		self._sbDrag = None

	def _handleMouse(self, mx, my, bstate):
		wheel = isWheel(bstate)
		if wheel:
			self._scrollY += 3 * wheel
			self._clampScroll()
			self._markDirty()
			return True

		press   = bool(bstate & B1_PRESS) and not (bstate & MOTION)
		release = bool(bstate & (B1_RELEASE | B1_CLICK))
		clicked = bool(bstate & B1_CLICK)
		dclick  = bool(bstate & B1_DCLICK)
		bd      = self._border()
		dataY   = self._dataY()
		visH    = self._visRows()

		# internal scrollbar
		if self._sbDrag is not None:
			if bstate & MOTION or release:
				self._barDrag(my - dataY, visH)
			if release:
				self._sbDrag = None
			return True
		if self._showInternalBar() and mx == self._x + self._width - bd - 1 and \
				dataY <= my < dataY + visH:
			if press or clicked:
				self._barClick(my - dataY, visH, press)
			return True

		if not (press or clicked or dclick):
			return False

		# heading click → command
		if self._hasHead() and my == self._y + bd:
			col = self.identifyColumn(mx - self._x)
			if col and (release or clicked):
				cid = self._colId(col) if col != '#0' else '#0'
				cmd = self._headCfg.get(cid, {}).get('command')
				if callable(cmd):
					cmd()
			return True

		flatIdx = self._scrollY + (my - dataY)
		flat    = self._getFlat()
		if not (0 <= flatIdx < len(flat)):
			return False
		iid, depth = flat[flatIdx]
		if dclick:
			self._toggle(iid)
			return True
		markerX = self._x + bd + 2 * depth
		if '#0' in self._colList()[:1] and markerX <= mx < markerX + 2 and \
				self._treeItems[iid]['children']:
			self._toggle(iid)
		self._selectRow(iid)
		return True
