import curses
import sys
import time
import traceback

from ._colors import ColorManager
from ._core import Widget, _fillRect, _addStr, _pad, _mouseEventNames, \
	_newMouseEvent, _newKeyEvent
from ._frame import Frame
from ._layout import doPackLayout, doGridLayout, doPlaceLayout
from ._events import KEY_TAB, KEY_BTAB, KEY_ENTER, Event, MOTION, \
	B1_PRESS, B1_RELEASE, B1_CLICK, B1_DCLICK, B3_ANY, isWheel


class Tk(Frame):
	"""Root window.  Acts as the main frame and owns the event loop."""

	_isRoot = True

	def __init__(self, screenName=None, baseName=None, className='Tk',
			useTk=True, sync=False, use=None, **kwargs):
		self._title		= 'tktext'
		self._colors		= ColorManager()
		self._scr		= None
		self._focusWidget	= None
		self._dragWidget	= None	# widget that owns the current mouse drag
		self._menuGrab		= False	# a mouse press started inside a menu
		self._focusLost		= False	# focused widget was destroyed
		self._quit		= False
		self._dirty		= True
		self._running		= False
		self._afterCallbacks	= []	# list of (fire_time, handle, func, args)
		self._afterSerial	= 0	# incrementing ID for after handles
		self._vars		= {}
		self._postedMenus	= []	# stack of currently visible Menu overlays
		self._postedDialogs	= []	# stack of active modal dialogs
		self._menuBar		= None	# Menu set with configure(menu=...)
		self._menuBarPos	= []	# [(x0, x1, itemIndex), …] on row 0
		self._menuBarActive	= -1
		self._protocols		= {}
		self._errors		= []	# formatted tracebacks of callback errors
		self._reporting		= False
		self._clipboard		= ''
		self._allBindings	= Widget()	# bind_all() table
		super().__init__(parent=None)
		self._opts['takefocus'] = False
		self._w			= 80	# real size known once attached
		self._h			= 24
		if kwargs:
			self.configure(**kwargs)

		# Register as the global app so messagebox/filedialog can find us
		import tktext._dialog as _dlg
		_dlg._currentApp = self

	# ------------------------------------------------------------------
	# Configuration (menu=…)
	# ------------------------------------------------------------------

	def configure(self, cnf=None, **kwargs):
		if cnf:
			kwargs.update(cnf)
		if 'menu' in kwargs:
			self._menuBar = kwargs.pop('menu')
			self._dirty   = True
			if not kwargs:
				return None
		return super().configure(**kwargs)

	config = configure

	# ------------------------------------------------------------------
	# Title / window-manager compatibility
	# ------------------------------------------------------------------

	def title(self, s=None):
		if s is None:
			return self._title
		self._title = str(s)
		self._dirty = True

	setTitle	= title		# camelCase alias
	wm_title	= title

	def geometry(self, geomstr=None):
		"""Terminal apps cannot be resized; returns the current size."""
		return f'{self._w}x{self._h}+0+0'

	wm_geometry = geometry

	def resizable(self, width=None, height=None):
		pass

	def minsize(self, width=None, height=None):
		pass

	def maxsize(self, width=None, height=None):
		pass

	def protocol(self, name=None, func=None):
		"""Register a window-manager protocol handler.  WM_DELETE_WINDOW
		is called on Ctrl-C (SIGINT) instead of quitting."""
		if func is None:
			return self._protocols.get(name)
		self._protocols[name] = func

	wm_protocol = protocol

	def iconbitmap(self, *a, **kw):
		pass

	def iconphoto(self, *a, **kw):
		pass

	def attributes(self, *a, **kw):
		return None

	wm_attributes = attributes

	def withdraw(self):
		pass

	def deiconify(self):
		pass

	def iconify(self):
		pass

	def option_add(self, *a, **kw):
		pass

	def bell(self):
		try:
			curses.beep()
		except curses.error:
			pass

	# Clipboard (process local)
	def clipboard_clear(self):
		self._clipboard = ''

	def clipboard_append(self, text):
		self._clipboard += str(text)

	def clipboard_get(self):
		return self._clipboard

	clipboardClear	= clipboard_clear
	clipboardAppend	= clipboard_append
	clipboardGet	= clipboard_get

	# ------------------------------------------------------------------
	# Event loop
	# ------------------------------------------------------------------

	def mainloop(self, n=0):
		"""Start the curses event loop.  Blocks until quit()."""
		self._quit = False
		if self._running:
			# Nested mainloop (e.g. called from a callback)
			while not self._quit:
				self._processOneEvent()
			self._quit = False
			return
		try:
			curses.wrapper(self._run)
		finally:
			self._scr	= None
			self._running	= False
			self._postedMenus.clear()
			self._postedDialogs.clear()
			if self._errors:
				sys.stderr.write('tktext: exceptions raised in callbacks:\n')
				for tb in self._errors:
					sys.stderr.write(tb)
				self._errors.clear()

	mainLoop = mainloop	# camelCase alias

	def quit(self):
		"""Schedule exit from mainloop."""
		self._quit = True

	def destroy(self):
		"""Destroy all widgets and leave the main loop."""
		self._quit = True
		for child in list(self._children):
			child.destroy()
		self._focusWidget = None
		import tktext._dialog as _dlg
		if _dlg._currentApp is self:
			_dlg._currentApp = None

	def _run(self, stdscr):
		self._attach(stdscr)
		while not self._quit:
			self._processOneEvent()

	def _attach(self, scr, initCurses=True):
		"""Bind the application to a curses (or fake) screen."""
		self._scr	= scr
		self._running	= True
		if initCurses:
			self._colors.init()
			try:
				curses.cbreak()
				curses.noecho()
			except curses.error:
				pass
			if hasattr(curses, 'set_escdelay'):
				try:
					curses.set_escdelay(25)
				except curses.error:
					pass
			try:
				curses.mousemask(curses.ALL_MOUSE_EVENTS |
					curses.REPORT_MOUSE_POSITION)
			except curses.error:
				pass
		scr.keypad(True)
		scr.nodelay(False)
		self._setCursor(0)
		self._h, self._w = scr.getmaxyx()
		self._layout()
		# Set initial focus to first focusable widget
		if self._focusWidget is None:
			focusable = self._getAllFocusable()
			if focusable:
				self._setFocus(focusable[0])
		self._update(force=True)

	def _nextTimeout(self) -> int:
		if not self._afterCallbacks:
			return -1	# block indefinitely
		now  = time.monotonic()
		nxt  = min(item[0] for item in self._afterCallbacks)
		return max(0, int((nxt - now) * 1000 + 0.999))

	def _processOneEvent(self):
		"""Wait for one input event (or timer), handle it, then redraw."""
		scr = self._scr
		if scr is None:
			return
		scr.timeout(self._nextTimeout())
		try:
			key = scr.getch()
		except KeyboardInterrupt:
			key = -1
			self._onInterrupt()
		try:
			if key != -1:
				self._handleInput(key)
			self._fireAfterCallbacks()
		except Exception:
			self._reportException()
		if self._dirty:
			self._update()

	def _onInterrupt(self):
		handler = self._protocols.get('WM_DELETE_WINDOW')
		if callable(handler):
			try:
				handler()
			except Exception:
				self._reportException()
		else:
			self._quit = True
		for d in self._postedDialogs:
			d._dismiss(None)

	def _handleInput(self, key):
		"""Dispatch one raw curses key code (including KEY_MOUSE/KEY_RESIZE)."""
		if key == curses.KEY_RESIZE:
			try:
				curses.update_lines_cols()
			except (curses.error, AttributeError):
				pass
			self._h, self._w = self._scr.getmaxyx()
			try:
				self._scr.clear()
			except curses.error:
				pass
			self._dirty = True
		elif key == curses.KEY_MOUSE:
			try:
				_, mx, my, _, bstate = curses.getmouse()
			except curses.error:
				return
			self._onMouse(mx, my, bstate)
		else:
			self._onKey(key)

	# ------------------------------------------------------------------
	# Errors in callbacks
	# ------------------------------------------------------------------

	def report_callback_exception(self, exc, val, tb):
		"""Called for exceptions raised in callbacks (tkinter API).

		The traceback is kept and printed when mainloop ends; a modal
		error box tells the user what happened."""
		text = ''.join(traceback.format_exception(exc, val, tb))
		self._errors.append(text)
		if self._reporting or self._scr is None:
			return
		self._reporting = True
		try:
			from ._dialog import _MsgDialog
			_MsgDialog(self, 'Exception in callback',
				f'{exc.__name__}: {val}', [('OK', 'ok')], 'error').run()
		except Exception:
			pass
		finally:
			self._reporting = False

	reportCallbackException = report_callback_exception

	def _reportException(self):
		exc, val, tb = sys.exc_info()
		if exc is None:
			return
		if issubclass(exc, (SystemExit, KeyboardInterrupt)):
			raise val
		self.report_callback_exception(exc, val, tb)

	# ------------------------------------------------------------------
	# Focus management
	# ------------------------------------------------------------------

	def _setFocus(self, widget):
		if widget is self:
			widget = None
		old = self._focusWidget
		if old is widget:
			return
		self._focusWidget = widget
		if old is not None:
			old._focused = False
			old._dispatch('<FocusOut>', _FocusEvent(old, 'FocusOut'))
		if widget is not None:
			widget._focused = True
			widget._dispatch('<FocusIn>', _FocusEvent(widget, 'FocusIn'))
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

	def _validateFocus(self):
		"""Drop focus from widgets that were destroyed or became hidden."""
		fw = self._focusWidget
		if fw is None:
			if self._focusLost:
				self._focusLost = False
				focusable = self._getAllFocusable()
				if focusable:
					self._setFocus(focusable[0])
			return
		if fw._destroyed or fw._getApp() is not self or \
				fw not in self._getAllFocusable():
			fw._focused	  = False
			self._focusWidget = None
			focusable = self._getAllFocusable()
			if focusable:
				self._setFocus(focusable[0])

	# ------------------------------------------------------------------
	# Input dispatch
	# ------------------------------------------------------------------

	_KEY_NORMALISE = {
		127:			curses.KEY_BACKSPACE,
		8:			curses.KEY_BACKSPACE,
		13:			KEY_ENTER,
		curses.KEY_ENTER:	KEY_ENTER,
	}

	def _onKey(self, key):
		key = self._KEY_NORMALISE.get(key, key)
		self._dirty = True

		# Modal dialogs grab the keyboard
		if self._postedDialogs:
			self._postedDialogs[-1]._handleKey(key)
			return

		# Posted menus grab the keyboard
		if self._postedMenus:
			self._postedMenus[-1]._handleKey(key)
			return

		if self._menuBar is not None and key == curses.KEY_F10:
			self._openMenuBar(0)
			return

		fw  = self._focusWidget or self
		evt = _newKeyEvent(fw, key)
		pat = evt.patterns()

		# 1. bindings on the widget itself
		_, res = fw._dispatchFirst(pat, evt)
		if res == 'break':
			return

		# 2. class behaviour
		consumed = fw is not self and fw._handleKey(key)

		# 3. unconsumed: bubble the bindings up through the ancestors
		#    (the first ancestor with a matching binding handles it; like
		#    tkinter only 'break' suppresses the default Tab traversal)
		if not consumed:
			p = fw._parent
			while p is not None:
				matched, res = p._dispatchFirst(pat, evt)
				if matched:
					consumed = res == 'break'
					break
				p = p._parent

		# 4. application wide bindings and focus traversal
		if not consumed:
			matched, res = self._allBindings._dispatchFirst(pat, evt)
			if res != 'break':
				if key == KEY_TAB:
					self._focusNext()
				elif key == KEY_BTAB:
					self._focusPrev()

		# 5. key release (terminals have no real release events)
		if not fw._destroyed:
			evt.type = 'KeyRelease'
			fw._dispatchFirst([f'<KeyRelease-{evt.keysym}>',
				'<KeyRelease>'], evt)

	def _menuRect(self, menu):
		mw = menu._menuWidth()
		mh = menu._menuHeight()
		px = menu._postX
		py = menu._postY
		if px + mw > self._w:
			px = max(0, self._w - mw)
		if py + mh > self._h:
			py = max(0, self._h - mh)
		return px, py, mw, mh

	def _menuAt(self, mx, my):
		for menu in reversed(self._postedMenus):
			px, py, mw, mh = self._menuRect(menu)
			if px <= mx < px + mw and py <= my < py + mh:
				return menu
		return None

	def _onMouse(self, mx, my, bstate):
		self._dirty = True
		press   = bool(bstate & B1_PRESS) and not (bstate & MOTION)
		release = bool(bstate & B1_RELEASE)
		clicked = bool(bstate & (B1_CLICK | B1_DCLICK))
		anyDown = press or clicked or bool(bstate & B3_ANY) or \
			bool(bstate & (curses.BUTTON2_PRESSED | curses.BUTTON2_CLICKED))

		# Modal dialogs grab the mouse
		if self._postedDialogs:
			self._postedDialogs[-1]._handleMouse(mx, my, bstate)
			return

		# Menubar on the title row
		if self._menuBar is not None and my == 0 and not isWheel(bstate):
			idx = self._menuBarIndexAt(mx)
			if idx >= 0 and (anyDown or (self._postedMenus and
					self._menuBarActive >= 0 and idx != self._menuBarActive)):
				if anyDown and self._menuBarActive == idx and self._postedMenus:
					self._closeMenus()
				else:
					self._openMenuBar(idx)
				self._menuGrab = press
				return

		# Posted menus (and combobox drop-downs)
		if self._postedMenus:
			if release or clicked:
				self._dragWidget = None
			menu = self._menuAt(mx, my)
			if menu is not None:
				if press:
					self._menuGrab = True
				if release:
					self._menuGrab = False
				menu._handleMouse(mx, my, bstate)
				return
			if self._menuGrab:
				# drag that started in a menu: swallow until release
				if release or clicked:
					self._menuGrab = False
					self._closeMenus()
				return
			if anyDown:
				self._closeMenus()
				# fall through: the click still lands on the widget beneath
			elif not isWheel(bstate):
				return
		elif self._menuGrab:
			if release or clicked:
				self._menuGrab = False
			return

		dragging = self._dragWidget is not None
		if dragging:
			target = self._dragWidget
			if target._destroyed:
				self._dragWidget = None
				return
		else:
			if release and not clicked:
				# release whose press we never delivered (e.g. the press
				# closed a menu or a dialog): drop it
				return
			target = self._findAt(mx, my)
			if target is None:
				return
			if press:
				self._dragWidget = target

		if (press or clicked) and not dragging:
			if target._isFocusable():
				self._setFocus(target)

		evt	= _newMouseEvent(target, mx, my, bstate)
		broken	= False
		for alts in _mouseEventNames(bstate, dragging):
			_, res = target._dispatchFirst(alts, evt)
			if res == 'break':
				broken = True
			self._allBindings._dispatchFirst(alts, evt)

		if not broken and not target._destroyed:
			target._handleMouse(mx, my, bstate)

		if release or clicked:
			self._dragWidget = None

	def _closeMenus(self):
		for m in list(self._postedMenus):
			m.unpost()
		self._menuBarActive = -1
		self._dirty = True

	# ------------------------------------------------------------------
	# Menubar (root.configure(menu=menubar))
	# ------------------------------------------------------------------

	def _menuBarIndexAt(self, mx):
		for x0, x1, idx in self._menuBarPos:
			if x0 <= mx < x1:
				return idx
		return -1

	def _menuBarCascades(self):
		bar = self._menuBar
		if bar is None:
			return []
		return [i for i, it in enumerate(bar._items)
			if it['type'] == 'cascade' and it.get('menu') is not None
			and it.get('state', 'normal') != 'disabled']

	def _openMenuBar(self, idx):
		"""Open the cascade of menubar item *idx* (index into _items)."""
		bar = self._menuBar
		if bar is None:
			return
		cascades = self._menuBarCascades()
		if not cascades:
			return
		if idx not in cascades:
			idx = cascades[0]
		self._closeMenus()
		self._computeMenuBarPos()
		x = 0
		for x0, _, i in self._menuBarPos:
			if i == idx:
				x = x0
		sub = bar._items[idx]['menu']
		sub._fromMenuBar = True
		sub.post(x, 1)
		self._menuBarActive = idx
		self._dirty = True

	def _menuBarStep(self, delta):
		cascades = self._menuBarCascades()
		if not cascades:
			return
		cur = self._menuBarActive if self._menuBarActive in cascades else cascades[0]
		pos = (cascades.index(cur) + delta) % len(cascades)
		self._openMenuBar(cascades[pos])

	def _computeMenuBarPos(self):
		self._menuBarPos = []
		bar = self._menuBar
		if bar is None:
			return
		x = 0
		for i, item in enumerate(bar._items):
			if item['type'] == 'separator':
				continue
			label = f' {item.get("label", "")} '
			self._menuBarPos.append((x, x + len(label), i))
			x += len(label)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def _setCursor(self, visible):
		try:
			curses.curs_set(visible)
		except curses.error:
			pass

	def _layout(self):
		self._doLayout(0, 0, self._w, self._h)
		self._layoutChildren()
		self._validateFocus()
		self._preRender()

	def _update(self, force=False):
		"""Process pending layout and redraw."""
		if self._scr is None:
			return
		if self._dirty or force:
			self._dirty = False
			self._layout()
			self._redraw()

	def update(self):
		self._update(force=True)

	def updateIdletasks(self):
		self._update()

	update_idletasks = updateIdletasks

	def _redraw(self):
		scr = self._scr
		if scr is None:
			return
		scr.erase()
		attr = self._getAttr()
		_fillRect(scr, 0, 0, self._h, self._w, attr=attr)

		self._drawTitleBar(scr)
		self._renderChildren(scr)

		# Render posted menus on top of everything
		for menu in list(self._postedMenus):
			menu.render(scr)

		# Render modal dialogs on top of menus
		for dlg in list(self._postedDialogs):
			dlg.render(scr)

		# Draw cursor on focused widget if it exposes a cursor position
		fw  = self._focusWidget
		pos = None
		if fw is not None and not self._postedMenus and \
				not self._postedDialogs and hasattr(fw, '_cursorPos'):
			pos = fw._cursorPos()
			if pos is not None:
				cy, cx = pos
				if not (fw._x <= cx < fw._x + fw._w and
						fw._y <= cy < fw._y + fw._h and
						0 <= cy < self._h and 0 <= cx < self._w):
					pos = None
		if pos is not None:
			self._setCursor(1)
			try:
				scr.move(pos[0], pos[1])
			except curses.error:
				pass
		else:
			self._setCursor(0)

		scr.refresh()

	def _drawTitleBar(self, scr):
		barAttr = self._colors.getAttr('black', 'white')
		_addStr(scr, 0, 0, ' ' * self._w, barAttr)
		title  = f' {self._title} '
		startX = 0
		if self._menuBar is not None:
			self._computeMenuBarPos()
			bar = self._menuBar
			for x0, x1, idx in self._menuBarPos:
				item  = bar._items[idx]
				label = f' {item.get("label", "")} '
				a     = barAttr
				if item.get('state', 'normal') == 'disabled':
					a = self._colors.getAttr('gray', 'white')
				elif idx == self._menuBarActive and self._postedMenus:
					a = self._colors.getAttr('white', 'black', bold=True)
				_addStr(scr, 0, x0, label, a)
				startX = x1
			titleX = max(startX + 1, self._w - len(title))
		else:
			titleX = max(0, (self._w - len(title)) // 2)
		if titleX < self._w:
			_addStr(scr, 0, titleX, _pad(title, min(len(title), self._w - titleX)),
				self._colors.getAttr('black', 'white', bold=True))
		if not self._postedMenus:
			self._menuBarActive = -1

	# ------------------------------------------------------------------
	# Layout override (account for title bar row)
	# ------------------------------------------------------------------

	def _layoutChildren(self):
		# Reserve row 0 for the title bar
		packed, gridded, placed = self._managed()
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
	# Timers
	# ------------------------------------------------------------------

	def _after(self, ms, func=None, *args):
		"""Schedule *func* to be called after *ms* milliseconds."""
		if func is None:
			time.sleep(max(0, int(ms)) / 1000.0)
			return None
		self._afterSerial += 1
		handle    = f'after#{self._afterSerial}'
		fireTime  = time.monotonic() + max(0, int(ms)) / 1000.0
		self._afterCallbacks.append((fireTime, handle, func, args))
		return handle

	def _afterCancel(self, handle):
		"""Cancel a previously scheduled after() callback."""
		self._afterCallbacks = [
			item for item in self._afterCallbacks if item[1] != handle
		]

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
		fired.sort(key=lambda item: item[0])
		for _, _, func, args in fired:
			try:
				func(*args)
			except Exception:
				self._reportException()
		if fired:
			self._dirty = True


# ---------------------------------------------------------------------------
# Inner geometry proxy (skips the title bar row)
# ---------------------------------------------------------------------------

class _TkInner:
	def __init__(self, tk):
		self._x = tk._x
		self._y = tk._y + 1		# skip title bar
		self._w = tk._w
		self._h = max(0, tk._h - 1)


# ---------------------------------------------------------------------------
# Minimal focus event
# ---------------------------------------------------------------------------

class _FocusEvent(Event):
	def __init__(self, widget, kind='Focus'):
		super().__init__()
		self.widget = widget
		self.type   = kind
