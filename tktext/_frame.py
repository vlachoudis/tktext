from ._core import Widget, _fillRect, _drawBorder
from ._layout import doPackLayout, doGridLayout, doPlaceLayout


class Frame(Widget):
	"""Container widget.  Supports pack, grid, and place geometry managers
	for its children.  Mirrors tkinter.Frame / tkinter.ttk.Frame."""

	def __init__(self, parent=None, **kwargs):
		super().__init__(parent, **kwargs)
		# Per-row / per-column configuration for grid manager
		self._rowCfg = {}
		self._colCfg = {}

	# ------------------------------------------------------------------
	# Grid configuration
	# ------------------------------------------------------------------

	def columnconfigure(self, col, **kwargs):
		"""Configure grid column *col*.  Accepts weight, minsize, pad."""
		self._colCfg.setdefault(col, {}).update(kwargs)
		self._markDirty()

	def rowconfigure(self, row, **kwargs):
		"""Configure grid row *row*.  Accepts weight, minsize, pad."""
		self._rowCfg.setdefault(row, {}).update(kwargs)
		self._markDirty()

	# camelCase aliases
	columnConfigure = columnconfigure
	rowConfigure    = rowconfigure

	def columnkeyword(self, col):
		return dict(self._colCfg.get(col, {}))

	def rowkeyword(self, row):
		return dict(self._rowCfg.get(row, {}))

	# ------------------------------------------------------------------
	# Layout
	# ------------------------------------------------------------------

	def _layoutChildren(self):
		"""Compute positions for all children managed by any geometry manager."""
		packed  = [(c, c._geoInfo) for c in self._children if c._geoManager == 'pack']
		gridded = [(c, c._geoInfo) for c in self._children if c._geoManager == 'grid']
		placed  = [(c, c._geoInfo) for c in self._children if c._geoManager == 'place']

		# Adjust content area for border
		bd = int(self._opts.get('borderwidth') or 0)
		inner = _InnerGeom(self, bd)

		if packed:
			doPackLayout(inner, packed)
		if gridded:
			doGridLayout(inner, gridded, self._rowCfg, self._colCfg)
		if placed:
			doPlaceLayout(inner, placed)

	def _preferredSize(self):
		bd = int(self._opts.get('borderwidth') or 0)
		ow = int(self._opts.get('width') or 0)
		oh = int(self._opts.get('height') or 0)
		if ow and oh:
			return (ow + 2*bd, oh + 2*bd)
		# Derive from children
		pw = ph = 0
		for c in self._children:
			if c._geoManager:
				cw, ch = c._preferredSize()
				pw = max(pw, cw)
				ph = max(ph, ch)
		return (max(pw, ow or 1) + 2*bd, max(ph, oh or 1) + 2*bd)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if self._w <= 0 or self._h <= 0:
			return
		attr = self._getAttr()
		bd   = int(self._opts.get('borderwidth') or 0)

		# Background fill
		bg = self._opts.get('bg') or ''
		if bg:
			_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)

		# Border
		relief = self._opts.get('relief', 'flat')
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		self._renderChildren(scr)


# ---------------------------------------------------------------------------
# Helper: an object that acts like a widget for layout purposes but exposes
# the inner (content) rectangle of a bordered frame.
# ---------------------------------------------------------------------------

class _InnerGeom:
	def __init__(self, frame, bd):
		self._x = frame._x + bd
		self._y = frame._y + bd
		self._w = max(1, frame._w - 2*bd)
		self._h = max(1, frame._h - 2*bd)
