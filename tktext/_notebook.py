import curses
from ._core import Widget, _addStr, _fillRect, _pad
from ._events import KEY_LEFT, KEY_RIGHT


class Notebook(Widget):
	"""Tabbed container widget.  Mirrors ttk.Notebook."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'padding': 0,
		})
		kwargs.setdefault('relief',      'flat')
		kwargs.setdefault('borderwidth', 0)
		if kwargs:
			self.configure(**kwargs)

		self._tabs   = []	# list of {'widget': w, 'text': str, 'state': str}
		self._selIdx = 0

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def add(self, child: Widget, **kwargs):
		"""Append *child* as a new tab."""
		text  = str(kwargs.get('text',  f'Tab {len(self._tabs) + 1}'))
		state = str(kwargs.get('state', 'normal'))
		self._tabs.append({'widget': child, 'text': text, 'state': state})
		if len(self._tabs) == 1:
			self._selIdx = 0
		self._markDirty()

	def insert(self, pos, child: Widget, **kwargs):
		text  = str(kwargs.get('text',  f'Tab {len(self._tabs) + 1}'))
		state = str(kwargs.get('state', 'normal'))
		idx   = len(self._tabs) if pos == 'end' else int(pos)
		self._tabs.insert(idx, {'widget': child, 'text': text, 'state': state})
		if self._selIdx >= len(self._tabs):
			self._selIdx = len(self._tabs) - 1
		self._markDirty()

	def select(self, tabId=None):
		"""Select tab, or return the currently-selected tab widget."""
		if tabId is None:
			return self._tabs[self._selIdx]['widget'] if self._tabs else None
		idx = self._resolveTabId(tabId)
		if idx is not None:
			self._selIdx = idx
			self._markDirty()

	def forget(self, tabId):
		idx = self._resolveTabId(tabId)
		if idx is not None:
			self._tabs[idx]['widget']._doLayout(0, 0, 0, 0)
			self._tabs.pop(idx)
			self._selIdx = max(0, min(self._selIdx, len(self._tabs) - 1))
			self._markDirty()

	def hide(self, tabId):
		idx = self._resolveTabId(tabId)
		if idx is not None:
			self._tabs[idx]['state'] = 'hidden'
			if idx == self._selIdx:
				for i, t in enumerate(self._tabs):
					if t['state'] == 'normal':
						self._selIdx = i
						break
			self._markDirty()

	def tab(self, tabId, option=None, **kwargs):
		"""Get/set tab options (text, state, …)."""
		idx = self._resolveTabId(tabId)
		if idx is None:
			return None
		if kwargs:
			self._tabs[idx].update(kwargs)
			self._markDirty()
			return
		if option is not None:
			return self._tabs[idx].get(option)
		return dict(self._tabs[idx])

	def tabs(self) -> list:
		return [t['widget'] for t in self._tabs]

	def index(self, tabId) -> int:
		if tabId == 'end':
			return len(self._tabs)
		idx = self._resolveTabId(tabId)
		return idx if idx is not None else 0

	def enable_traversal(self):
		pass	# keyboard traversal is always enabled

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _resolveTabId(self, tabId):
		if tabId == 'current':
			return self._selIdx
		if isinstance(tabId, int) and 0 <= tabId < len(self._tabs):
			return tabId
		for i, t in enumerate(self._tabs):
			if t['widget'] is tabId:
				return i
		return None

	def _tabBarH(self) -> int:
		return 1

	def _contentRect(self):
		"""Return (x, y, w, h) of the area below the tab bar."""
		pad  = int(self._opts.get('padding') or 0)
		tabH = self._tabBarH()
		return (self._x + pad,
			self._y + tabH + pad,
			max(1, self._w - 2*pad),
			max(1, self._h - tabH - 2*pad))

	def _preferredSize(self):
		ow = int(self._opts.get('width')  or 40)
		oh = int(self._opts.get('height') or 10)
		return (max(ow, 10), max(oh, 4))

	# ------------------------------------------------------------------
	# Layout
	# ------------------------------------------------------------------

	def _layoutChildren(self):
		if not self._tabs:
			return
		cx, cy, cw, ch = self._contentRect()
		for i, t in enumerate(self._tabs):
			w = t['widget']
			if i == self._selIdx and t['state'] != 'hidden':
				w._doLayout(cx, cy, cw, ch)
				if hasattr(w, '_layoutChildren'):
					w._layoutChildren()
			else:
				w._doLayout(0, 0, 0, 0)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return
		attr = self._getAttr()
		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		# Tab bar
		tabY = self._y
		x    = self._x
		for i, t in enumerate(self._tabs):
			if t['state'] == 'hidden':
				continue
			label = f' {t["text"]} '
			isSel = (i == self._selIdx)
			tattr = attr | curses.A_REVERSE if isSel else attr | curses.A_BOLD
			if x + len(label) <= self._x + self._w:
				_addStr(scr, tabY, x, label, tattr)
			x += len(label)
		# fill rest of tab row
		rest = self._x + self._w - x
		if rest > 0:
			_addStr(scr, tabY, x, '─' * rest, attr)

		# Active tab content
		if self._tabs and self._selIdx < len(self._tabs):
			w = self._tabs[self._selIdx]['widget']
			if w._w > 0 and w._h > 0:
				w.render(scr)

	def _renderChildren(self, scr):
		# Children are rendered by render() directly; suppress default walk
		pass

	# ------------------------------------------------------------------
	# Focus / hit-test
	# ------------------------------------------------------------------

	def _isFocusable(self):
		return True

	def _getAllFocusable(self):
		result = [self] if self._isFocusable() else []
		if self._tabs and self._selIdx < len(self._tabs):
			result.extend(self._tabs[self._selIdx]['widget']._getAllFocusable())
		return result

	def _findAt(self, mx, my):
		if not self._hitTest(mx, my):
			return None
		if self._tabs and self._selIdx < len(self._tabs):
			hit = self._tabs[self._selIdx]['widget']._findAt(mx, my)
			if hit:
				return hit
		return self

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _handleKey(self, key):
		if key == KEY_LEFT and self._selIdx > 0:
			self._selIdx -= 1
			self._markDirty()
			return True
		if key == KEY_RIGHT and self._selIdx < len(self._tabs) - 1:
			self._selIdx += 1
			self._markDirty()
			return True
		return super()._handleKey(key)

	def _handleMouse(self, mx, my, bstate):
		if not (bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED)):
			return False
		tabY = self._y
		if my == tabY:
			x = self._x
			for i, t in enumerate(self._tabs):
				if t['state'] == 'hidden':
					continue
				label = f' {t["text"]} '
				if x <= mx < x + len(label):
					self._selIdx = i
					self._markDirty()
					return True
				x += len(label)
		return False
