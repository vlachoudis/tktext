import curses
import sys
import time

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
		self._colors		= ColorManager()
		self._scr		= None
		self._focusWidget	= None
		self._dragWidget	= None	# widget that owns the current mouse drag
		self._quit		= False
		self._dirty		= True
		self._afterCallbacks	= []	# list of (fire_time, handle, func, args)
		self._afterSerial	= 0	# incrementing ID for after handles
		self._vars		= {}
		self._postedMenus	= []	# stack of currently visible Menu overlays
		self._postedDialogs	= []	# stack of active modal dialogs

		# Register as the global app so messagebox/filedialog can find us
		import tktext._dialog as _dlg
		_dlg._currentApp = self

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
			# Compute getch() timeout from pending after-callbacks
			if self._afterCallbacks:
				now  = time.monotonic()
				next_fire = min(item[0] for item in self._afterCallbacks)
				ms   = max(0, int((next_fire - now) * 1000))
			else:
				ms = -1	# block indefinitely
			stdscr.timeout(ms)

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

			elif key != -1:
				self._onKey(key)

			self._fireAfterCallbacks()

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
		# Menus take priority over the focused widget
		if self._postedMenus:
			if self._postedMenus[-1]._handleKey(key):
				self._dirty = True
				return
		fw = self._focusWidget
		if fw and fw._handleKey(key):
			self._dirty = True
			return
		# Bubble up through all ancestors including root
		if fw:
			p = fw._parent
			while p:
				if p._handleKey(key):
					self._dirty = True
					return
				p = p._parent

	def _onMouse(self, mx, my, bstate):
		release = bool(bstate & (curses.BUTTON1_RELEASED | curses.BUTTON1_CLICKED))
		press   = bool(bstate & curses.BUTTON1_PRESSED)

		# Route to posted menus first
		if self._postedMenus:
			for menu in reversed(self._postedMenus):
				mw = menu._menuWidth()
				mh = menu._menuHeight()
				px = menu._postX
				py = menu._postY
				if px + mw > self._w:
					px = max(0, self._w - mw)
				if py + mh > self._h:
					py = max(0, self._h - mh)
				if px <= mx < px + mw and py <= my < py + mh:
					menu._handleMouse(mx, my, bstate)
					self._dirty = True
					return
			# Click outside all menus
			if press:
				for m in list(self._postedMenus):
					m.unpost()
				self._dirty = True
				# fall through to handle click on widget beneath

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

		clicked = bool(bstate & curses.BUTTON1_CLICKED)
		if (press or clicked) and target._isFocusable():
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

		# Render posted menus on top of everything
		for menu in self._postedMenus:
			menu.render(scr)

		# Render modal dialogs on top of menus
		for dlg in self._postedDialogs:
			dlg.render(scr)

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

	def after(self, ms: int, func=None, *args):
		"""Schedule *func* to be called after *ms* milliseconds."""
		if func is None:
			return None
		self._afterSerial += 1
		handle    = self._afterSerial
		fire_time = time.monotonic() + ms / 1000.0
		self._afterCallbacks.append((fire_time, handle, func, args))
		return handle

	def after_cancel(self, handle):
		"""Cancel a previously scheduled after() callback."""
		self._afterCallbacks = [
			item for item in self._afterCallbacks if item[1] != handle
		]

	def after_idle(self, func, *args):
		"""Schedule *func* for the next idle iteration."""
		return self.after(0, func, *args)

	def _fireAfterCallbacks(self):
		now       = time.monotonic()
		remaining = []
		fired     = []
		for item in self._afterCallbacks:
			if item[0] <= now:
				fired.append(item)
			else:
				remaining.append(item)
		self._afterCallbacks = remaining
		for _, _, func, args in fired:
			try:
				func(*args)
			except Exception:
				pass

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
