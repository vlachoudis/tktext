import curses
import sys

from ._colors import ColorManager
from ._core import Widget, _fillRect
from ._frame import Frame
from ._layout import doPackLayout, doGridLayout, doPlaceLayout
from ._events import KEY_TAB, KEY_BTAB


class Tk(Frame):
	"""Root window.  Acts as the main frame and owns the event loop."""

	_isRoot = True

	def __init__(self, **kwargs):
		# No parent for the root
		super().__init__(parent=None, **kwargs)
		self._title		= 'tktext'
		self._colors	= ColorManager()
		self._scr		= None
		self._focusWidget	= None
		self._dragWidget	= None	# widget that owns the current mouse drag
		self._quit		= False
		self._dirty		= True
		self._afterCallbacks	= []	# list of (delay_ms, func) – simplified
		self._vars		= {}

	# ------------------------------------------------------------------
	# Title
	# ------------------------------------------------------------------

	def title(self, s=None):
		if s is None:
			return self._title
		self._title = s

	setTitle = title	# camelCase alias

	# ------------------------------------------------------------------
	# Event loop
	# ------------------------------------------------------------------

	def mainloop(self, n=0):
		"""Start the curses event loop.  Blocks until quit()."""
		curses.wrapper(self._run)

	mainLoop = mainloop	# camelCase alias

	def quit(self):
		"""Schedule exit from mainloop."""
		self._quit = True

	def _run(self, stdscr):
		self._scr = stdscr
		self._colors.init()

		curses.cbreak()
		curses.noecho()
		stdscr.keypad(True)
		stdscr.nodelay(False)
		curses.curs_set(0)

		try:
			curses.mousemask(
				curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION
			)
		except curses.error:
			pass

		self._h, self._w = stdscr.getmaxyx()
		self._doLayout(0, 0, self._w, self._h)
		self._layoutChildren()

		# Set initial focus to first focusable widget
		focusable = self._getAllFocusable()
		if focusable:
			self._setFocus(focusable[0])

		self._redraw()

		while not self._quit:
			try:
				key = stdscr.getch()
			except KeyboardInterrupt:
				break

			if key == curses.KEY_RESIZE:
				self._h, self._w = stdscr.getmaxyx()
				self._dirty = True

			elif key == curses.KEY_MOUSE:
				try:
					_, mx, my, _, bstate = curses.getmouse()
					self._onMouse(mx, my, bstate)
				except curses.error:
					pass

			elif key == KEY_TAB:
				self._focusNext()

			elif key == KEY_BTAB:
				self._focusPrev()

			else:
				self._onKey(key)

			if self._dirty:
				self._doLayout(0, 0, self._w, self._h)
				self._layoutChildren()
				self._redraw()
				self._dirty = False

	# ------------------------------------------------------------------
	# Focus management
	# ------------------------------------------------------------------

	def _setFocus(self, widget):
		if self._focusWidget and self._focusWidget is not widget:
			self._focusWidget._focused = False
			self._focusWidget._dispatch('<FocusOut>',
				_FocusEvent(self._focusWidget))
		self._focusWidget = widget
		if widget:
			widget._focused = True
			widget._dispatch('<FocusIn>', _FocusEvent(widget))
		self._dirty = True

	def _focusNext(self):
		focusable = self._getAllFocusable()
		if not focusable:
			return
		if self._focusWidget in focusable:
			idx = (focusable.index(self._focusWidget) + 1) % len(focusable)
		else:
			idx = 0
		self._setFocus(focusable[idx])

	def _focusPrev(self):
		focusable = self._getAllFocusable()
		if not focusable:
			return
		if self._focusWidget in focusable:
			idx = (focusable.index(self._focusWidget) - 1) % len(focusable)
		else:
			idx = len(focusable) - 1
		self._setFocus(focusable[idx])

	# ------------------------------------------------------------------
	# Input dispatch
	# ------------------------------------------------------------------

	def _onKey(self, key):
		fw = self._focusWidget
		if fw and fw._handleKey(key):
			self._dirty = True
			return
		# Bubble up (not common but handle it)
		if fw:
			p = fw._parent
			while p and not p._isRoot:
				if p._handleKey(key):
					self._dirty = True
					return
				p = p._parent

	def _onMouse(self, mx, my, bstate):
		release = bool(bstate & (curses.BUTTON1_RELEASED | curses.BUTTON1_CLICKED))
		press   = bool(bstate & curses.BUTTON1_PRESSED)

		# During a drag, keep routing to the widget that received the press
		if self._dragWidget is not None:
			target = self._dragWidget
			if release:
				self._dragWidget = None
		else:
			target = self._findAt(mx, my)
			if target is None:
				return
			if press:
				self._dragWidget = target

		if press and target._isFocusable():
			self._setFocus(target)

		target._handleMouse(mx, my, bstate)
		self._dirty = True

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def _redraw(self):
		scr = self._scr
		if scr is None:
			return
		scr.erase()
		attr = self._colors.getAttr('white', 'black')
		_fillRect(scr, 0, 0, self._h, self._w, attr=attr)

		# Title bar
		title = f' {self._title} '
		title_x = max(0, (self._w - len(title)) // 2)
		try:
			scr.addstr(0, 0, ' ' * self._w, self._colors.getAttr('black', 'white', bold=True))
			scr.addstr(0, title_x, title, self._colors.getAttr('black', 'white', bold=True))
		except curses.error:
			pass

		self._renderChildren(scr)

		# Draw cursor on focused widget if it exposes a cursor position
		fw = self._focusWidget
		if fw and hasattr(fw, '_cursorPos'):
			cy, cx = fw._cursorPos()
			if 0 <= cy < self._h and 0 <= cx < self._w:
				curses.curs_set(1)
				try:
					scr.move(cy, cx)
				except curses.error:
					pass
			else:
				curses.curs_set(0)
		else:
			curses.curs_set(0)

		scr.refresh()

	# ------------------------------------------------------------------
	# Layout override (account for title bar row)
	# ------------------------------------------------------------------

	def _layoutChildren(self):
		# Reserve row 0 for the title bar
		packed  = [(c, c._geoInfo) for c in self._children if c._geoManager == 'pack']
		gridded = [(c, c._geoInfo) for c in self._children if c._geoManager == 'grid']
		placed  = [(c, c._geoInfo) for c in self._children if c._geoManager == 'place']

		inner = _TkInner(self)

		if packed:
			doPackLayout(inner, packed)
		if gridded:
			doGridLayout(inner, gridded, self._rowCfg, self._colCfg)
		if placed:
			doPlaceLayout(inner, placed)

	def _preferredSize(self):
		return (self._w, self._h)

	# ------------------------------------------------------------------
	# Miscellaneous helpers
	# ------------------------------------------------------------------

	def update(self):
		"""Process pending layout/redraw (simplified)."""
		if self._dirty and self._scr:
			self._doLayout(0, 0, self._w, self._h)
			self._layoutChildren()
			self._redraw()
			self._dirty = False

	def updateIdletasks(self):
		self.update()

	update_idletasks = updateIdletasks

	def after(self, ms, func=None, *args):
		"""Simplified after: just call immediately (no real scheduler here)."""
		if func:
			func(*args)

	def geometry(self, geomstr=None):
		"""No-op for terminal apps; present for API compatibility."""
		pass

	def resizable(self, width=None, height=None):
		pass

	def minsize(self, width=None, height=None):
		pass

	def maxsize(self, width=None, height=None):
		pass

	def protocol(self, name, func=None):
		pass

	def iconbitmap(self, *a, **kw):
		pass


# ---------------------------------------------------------------------------
# Inner geometry proxy (skips the title bar row)
# ---------------------------------------------------------------------------

class _TkInner:
	def __init__(self, tk):
		self._x = tk._x
		self._y = tk._y + 1		# skip title bar
		self._w = tk._w
		self._h = max(1, tk._h - 1)


# ---------------------------------------------------------------------------
# Minimal focus event
# ---------------------------------------------------------------------------

class _FocusEvent:
	def __init__(self, widget):
		self.widget = widget
		self.type = 'Focus'
		self.char = ''
		self.keysym = ''
