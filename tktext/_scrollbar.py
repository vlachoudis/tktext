import curses
from ._core import Widget, _addStr, _fillRect


class Scrollbar(Widget):
	"""Dummy Scrollbar — API-compatible with tkinter.Scrollbar.

	Listbox, Text and Treeview have built-in scrollbars; this widget
	exists so code that creates a Scrollbar next to those widgets does
	not crash.  The visual indicator still shows the current thumb
	position reported via set().
	"""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent)
		self._opts.update({
			'orient':  'vertical',
			'command': None,
		})
		kwargs.setdefault('relief',      'flat')
		kwargs.setdefault('borderwidth', 0)
		if kwargs:
			self.configure(**kwargs)
		self._first = 0.0
		self._last  = 1.0

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def set(self, first: float, last: float):
		"""Called by the linked widget to report its scroll position."""
		self._first = float(first)
		self._last  = float(last)
		self._markDirty()

	def get(self) -> tuple:
		return (self._first, self._last)

	# ------------------------------------------------------------------

	def _isFocusable(self):
		return False

	def _preferredSize(self):
		orient = self._opts.get('orient', 'vertical')
		if orient == 'horizontal':
			return (int(self._opts.get('width') or 10), 1)
		return (1, int(self._opts.get('height') or 10))

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return
		attr   = self._getAttr()
		orient = self._opts.get('orient', 'vertical')

		if orient == 'vertical':
			total     = self._h
			thumbStart = int(self._first * total)
			thumbEnd   = max(thumbStart + 1, int(self._last * total))
			for i in range(total):
				ch = '#' if thumbStart <= i < thumbEnd else '|'
				try:
					scr.addch(self._y + i, self._x, ch, attr)
				except curses.error:
					pass
		else:
			total     = self._w
			thumbStart = int(self._first * total)
			thumbEnd   = max(thumbStart + 1, int(self._last * total))
			row = ''.join('#' if thumbStart <= i < thumbEnd else '-'
				for i in range(total))
			_addStr(scr, self._y, self._x, row, attr)
