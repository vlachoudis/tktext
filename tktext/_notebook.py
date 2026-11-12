import curses
from ._core import TclError, Widget, _addStr, _fillRect, _int
from ._layout import _layoutWidget
from ._events import KEY_LEFT, KEY_RIGHT, B1_PRESS, B1_CLICK, MOTION


class Notebook(Widget):
	"""Tabbed container widget.  Mirrors ttk.Notebook."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'padding': 0,
		})
		kwargs.setdefault('relief',      'flat')
		kwargs.setdefault('borderwidth', 0)

		self._tabs   = []	# list of {'widget': w, 'text': str, 'state': str}
		self._selIdx = -1

		if kwargs:
			self.configure(**kwargs)

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def _tabEntry(self, child, kwargs):
		return {
			'widget':	child,
			'text':		str(kwargs.get('text', f'Tab {len(self._tabs) + 1}')),
			'state':	str(kwargs.get('state', 'normal')),
			'underline':	kwargs.get('underline', -1),
			'sticky':	kwargs.get('sticky', 'nsew'),
			'padding':	kwargs.get('padding', 0),
			'image':	kwargs.get('image', ''),
			'compound':	kwargs.get('compound', ''),
		}

	def add(self, child: Widget, **kwargs):
		"""Append *child* as a new tab (or update an existing tab)."""
		idx = self._resolveTabId(child)
		if idx is not None:
			self.tab(idx, **kwargs)
			if self._tabs[idx]['state'] == 'hidden':
				self._tabs[idx]['state'] = 'normal'
			return
		self._tabs.append(self._tabEntry(child, kwargs))
		if self._selIdx < 0:
			self._select(0)
		else:
			child._unmapTree()
		self._markDirty()

	def insert(self, pos, child: Widget, **kwargs):
		cur = self._tabs[self._selIdx]['widget'] if 0 <= self._selIdx < len(self._tabs) else None
		old = self._resolveTabId(child)
		if old is not None:
			entry = self._tabs.pop(old)
			entry.update({k: v for k, v in kwargs.items() if k in entry})
		else:
			entry = self._tabEntry(child, kwargs)
		idx = len(self._tabs) if pos in ('end', 'END') else self._resolveTabId(pos)
		if idx is None:
			idx = len(self._tabs)
		self._tabs.insert(idx, entry)
		if cur is not None:
			self._selIdx = self._resolveTabId(cur)
		elif self._selIdx < 0:
			self._select(0)
		self._markDirty()

	def select(self, tabId=None):
		"""Select tab, or return the currently-selected tab widget."""
		if tabId is None:
			if 0 <= self._selIdx < len(self._tabs):
				return self._tabs[self._selIdx]['widget']
			return ''
		idx = self._resolveTabId(tabId)
		if idx is not None:
			self._select(idx)

	def _select(self, idx):
		if not (0 <= idx < len(self._tabs)):
			return
		if self._tabs[idx]['state'] == 'disabled':
			return
		if self._tabs[idx]['state'] == 'hidden':
			self._tabs[idx]['state'] = 'normal'
		changed = idx != self._selIdx
		if 0 <= self._selIdx < len(self._tabs) and changed:
			self._tabs[self._selIdx]['widget']._unmapTree()
		self._selIdx = idx
		self._markDirty()
		if changed:
			self._fireVirtual('<<NotebookTabChanged>>')

	def forget(self, tabId=None):
		if tabId is None:		# Widget.forget() semantics
			return super().forget()
		idx = self._resolveTabId(tabId)
		if idx is None:
			return
		wasSel = idx == self._selIdx
		self._tabs[idx]['widget']._unmapTree()
		self._tabs.pop(idx)
		if idx < self._selIdx:
			self._selIdx -= 1
		elif wasSel:
			self._selIdx = min(idx, len(self._tabs) - 1)
		if wasSel and self._tabs:
			self._fireVirtual('<<NotebookTabChanged>>')
		self._markDirty()

	def hide(self, tabId):
		idx = self._resolveTabId(tabId)
		if idx is None:
			return
		self._tabs[idx]['state'] = 'hidden'
		self._tabs[idx]['widget']._unmapTree()
		if idx == self._selIdx:
			for i, t in enumerate(self._tabs):
				if t['state'] == 'normal':
					self._select(i)
					break
		self._markDirty()

	def tab(self, tabId, option=None, **kwargs):
		"""Get/set tab options (text, state, …)."""
		idx = self._resolveTabId(tabId)
		if idx is None:
			raise TclError(f'Invalid tab id {tabId!r}')
		entry = self._tabs[idx]
		if kwargs:
			for k, v in kwargs.items():
				entry[k] = str(v) if k in ('text', 'state') else v
			if entry['state'] == 'hidden' and idx == self._selIdx:
				self.hide(idx)
			self._markDirty()
			return None
		if option is not None:
			return entry.get(option)
		return {k: v for k, v in entry.items() if k != 'widget'}

	def tabs(self) -> tuple:
		return tuple(t['widget'] for t in self._tabs)

	def index(self, tabId) -> int:
		if tabId in ('end', 'END'):
			return len(self._tabs)
		idx = self._resolveTabId(tabId)
		if idx is None:
			raise TclError(f'Invalid tab id {tabId!r}')
		return idx

	def enable_traversal(self):
		pass	# keyboard traversal is always enabled

	enableTraversal = enable_traversal

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _resolveTabId(self, tabId):
		if tabId == 'current':
			return self._selIdx if 0 <= self._selIdx < len(self._tabs) else None
		if isinstance(tabId, int):
			return tabId if 0 <= tabId < len(self._tabs) else None
		for i, t in enumerate(self._tabs):
			if t['widget'] is tabId or str(t['widget']) == str(tabId):
				return i
		if isinstance(tabId, str) and tabId.isdigit():
			i = int(tabId)
			return i if 0 <= i < len(self._tabs) else None
		return None

	def _childDestroyed(self, child):
		idx = self._resolveTabId(child)
		if idx is not None:
			self.forget(idx)

	def _contentRect(self):
		"""Return (x, y, w, h) of the area below the tab bar."""
		pad = _int(self._opts.get('padding'))
		return (self._x + pad,
			self._y + 1 + pad,
			max(0, self._w - 2*pad),
			max(0, self._h - 1 - 2*pad))

	def _preferredSize(self):
		ow  = _int(self._opts.get('width'))
		oh  = _int(self._opts.get('height'))
		pad = _int(self._opts.get('padding'))
		pw = ph = 0
		for t in self._tabs:
			cw, ch = t['widget']._preferredSize()
			pw = max(pw, cw)
			ph = max(ph, ch)
		tabsW = sum(len(t['text']) + 2 for t in self._tabs if t['state'] != 'hidden')
		w = ow if ow > 0 else max(pw + 2*pad, tabsW, 10)
		h = oh if oh > 0 else max(ph + 2*pad + 1, 3)
		return (w, h)

	def _tabSpans(self):
		"""Return [(x0, x1, idx)] of visible tab labels (scrolled so that
		the selected tab is on screen)."""
		spans = []
		x     = 0
		for i, t in enumerate(self._tabs):
			if t['state'] == 'hidden':
				continue
			n = len(t['text']) + 2
			spans.append([x, x + n, i])
			x += n
		shift = 0
		for x0, x1, i in spans:
			if i == self._selIdx and x1 > self._w:
				shift = x1 - self._w
		return [(self._x + x0 - shift, self._x + x1 - shift, i) for x0, x1, i in spans]

	# ------------------------------------------------------------------
	# Layout
	# ------------------------------------------------------------------

	def _layoutChildren(self):
		if not (0 <= self._selIdx < len(self._tabs)):
			return
		cx, cy, cw, ch = self._contentRect()
		for i, t in enumerate(self._tabs):
			if i == self._selIdx and t['state'] != 'hidden':
				_layoutWidget(t['widget'], cx, cy, cw, ch)
			else:
				t['widget']._unmapTree()

	def _selectedWidget(self):
		if 0 <= self._selIdx < len(self._tabs) and \
				self._tabs[self._selIdx]['state'] != 'hidden':
			return self._tabs[self._selIdx]['widget']
		return None

	def _preRender(self):
		w = self._selectedWidget()
		if w is not None:
			w._preRender()

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return
		attr = self._getAttr()
		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		# Tab bar
		_addStr(scr, self._y, self._x, '─' * self._w, attr)
		for x0, x1, i in self._tabSpans():
			t     = self._tabs[i]
			label = f' {t["text"]} '
			if t['state'] == 'disabled':
				tattr = self._getAttr(fg='gray')
			elif i == self._selIdx:
				tattr = attr | curses.A_REVERSE
				if self._focused:
					tattr |= curses.A_BOLD | curses.A_UNDERLINE
			else:
				tattr = attr | curses.A_BOLD
			lo = max(x0, self._x)
			hi = min(x1, self._x + self._w)
			if hi > lo:
				_addStr(scr, self._y, lo, label[lo - x0:hi - x0], tattr)

		# Active tab content
		w = self._selectedWidget()
		if w is not None and w._isMapped():
			w.render(scr)

	def _renderChildren(self, scr):
		# Children are rendered by render() directly; suppress default walk
		pass

	# ------------------------------------------------------------------
	# Focus / hit-test
	# ------------------------------------------------------------------

	def _getAllFocusable(self):
		if not self._isMapped():
			return []
		result = [self] if self._isFocusable() else []
		w = self._selectedWidget()
		if w is not None:
			result.extend(w._getAllFocusable())
		return result

	def _findAt(self, mx, my):
		if not self._isMapped() or not self._hitTest(mx, my):
			return None
		w = self._selectedWidget()
		if w is not None:
			hit = w._findAt(mx, my)
			if hit:
				return hit
		return self

	# ------------------------------------------------------------------
	# Input
	# ------------------------------------------------------------------

	def _step(self, delta):
		n = len(self._tabs)
		i = self._selIdx
		for _ in range(n):
			i += delta
			if not (0 <= i < n):
				return False
			if self._tabs[i]['state'] == 'normal':
				self._select(i)
				return True
		return False

	def _handleKey(self, key):
		if key == KEY_LEFT:
			return self._step(-1)
		if key == KEY_RIGHT:
			return self._step(+1)
		return False

	def _handleMouse(self, mx, my, bstate):
		if not (bstate & (B1_PRESS | B1_CLICK)) or bstate & MOTION:
			return False
		if my != self._y:
			return False
		for x0, x1, i in self._tabSpans():
			if x0 <= mx < x1:
				self._select(i)
				return True
		return False
