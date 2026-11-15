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

import os
import sys
import signal
import time
import atexit
import curses
import shutil
import traceback
import weakref

from ._colors import ColorManager
from ._raster import RasterRenderer
from . import _colors, _termbg
from ._core import Widget, _fillRect, _addStr, _pad, _mouseEventNames, \
	_newMouseEvent, _newKeyEvent
from ._frame import Frame
from ._toplevel import Wm
from . import _core
from ._layout import doPackLayout, doGridLayout, doPlaceLayout
from ._events import KEY_TAB, KEY_BTAB, KEY_ENTER, KEY_CTRL_C, KEY_CTRL_Z, \
	Event, MOTION, B1_PRESS, B1_RELEASE, B1_CLICK, B1_DCLICK, B3_ANY, isWheel, \
	B23_PRESS, B23_RELEASE, \
	decodeEscape, decodeExtended, isModified, ModKey, STATE_CONTROL


# Written after curses.mousemask(), which enables only the press/release
# tracking (?1000): ?1002 also reports the motion with a button held
# (<B1-Motion>), the last ?100x set wins.  xterm XTSHIFTESCAPE (CSI > Ps s):
# 1 = send Shift-click to the application, 0 = Shift overrides mouse
# reporting (the default)
_MOUSE_MODES_ON		= b'\x1b[?1002h\x1b[>1s'
_MOUSE_MODES_OFF	= b'\x1b[>0s\x1b[?1002l'


def _termWrite(data: bytes):
	"""Write a control sequence straight to the terminal (fd 1;
	sys.stdout is captured while curses owns the screen)."""
	try:
		if os.isatty(1):
			os.write(1, data)
	except OSError:
		pass


class Tk(Wm, Frame):
	"""Root window.  Acts as the main frame and owns the event loop."""

	_isRoot		= True
	_isToplevel	= True

	def __init__(self, screenName=None, baseName=None, className='Tk',
			useTk=True, sync=False, use=None, **kwargs):
		self._wmInit()
		self._title		= 'tktext'
		self._colors		= ColorManager()
		self._raster		= RasterRenderer(self._colors)
		self._rasterWidgets	= weakref.WeakSet()	# widgets with a rasterImage
		self._scr		= None
		self._focusWidget	= None
		self._dragWidget	= None	# widget that owns the current mouse drag
		self._btnDrag		= None	# (widget, 2|3) of a middle/right button drag
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
		self._menuBarPos	= []	# [(x0, x1, itemIndex), …] on row 0
		self._menuBarActive	= -1
		self._errors		= []	# formatted tracebacks of callback errors
		self._reporting		= False
		self._clipboard		= {}	# type: data
		self._allBindings	= Widget()	# bind_all() table
		self._classBindings	= {}	# bind_class(): class name -> table
		self._virtualEvents	= {}	# event_add(): <<virtual>> -> [sequences]
		self._optionDb		= {}	# option_add() database: pattern -> value
		self._optionCache	= {}
		self._eventQueue	= []	# queued virtual events (widget, name, evt)
		self._toplevels		= []	# Toplevel windows in stacking order
		self._grab		= None	# widget holding the grab
		self._mouseXY		= (0, 0)
		self._hover		= None	# widget under the pointer (Enter/Leave)
		self._ownScreen		= False	# screen started by _startScreen()
		self._loopDepth		= 0
		self._savedExcepthook	= None
		super().__init__(parent=None)
		self._opts['takefocus'] = False
		# real size known once attached; layouts done before that (e.g.
		# update_idletasks() before mainloop) use the terminal size
		size			= shutil.get_terminal_size((80, 24))
		self._width		= size.columns
		self._height		= size.lines
		if _core._defaultRoot is None or _core._defaultRoot._destroyed:
			_core._defaultRoot = self
			import tktext
			tktext._default_root = self
		if kwargs:
			Tk.configure(self, **kwargs)

		# Register as the global app so messagebox/filedialog can find us
		import tktext._dialog as _dlg
		_dlg._currentApp = self

	# ------------------------------------------------------------------
	# Configuration (menu=…)
	# ------------------------------------------------------------------

	def configure(self, cnf=None, **kwargs):
		if isinstance(cnf, str) or not (cnf or kwargs):
			return super().configure(cnf)
		kwargs.update(cnf or {})
		if 'menu' in kwargs:
			self._ownMenuBar = kwargs.pop('menu') or None
			self._dirty      = True
			if not kwargs:
				return None
		kwargs.pop('class_', None)
		return super().configure(**kwargs) if kwargs else None

	config = configure

	# ------------------------------------------------------------------
	# Window manager: the root is always maximised
	# ------------------------------------------------------------------

	setTitle = Wm.wm_title		# camelCase alias

	@property
	def _menuBar(self):
		owner = self._barOwner()
		return owner._ownMenuBar if owner is not None else None

	def _isMaximised(self) -> bool:
		return True

	def _viewable(self) -> bool:
		return self._wmState == 'normal' and not self._destroyed

	def loadtk(self):
		pass

	def readprofile(self, baseName, className):
		pass

	def bell(self, displayof=0):
		try:
			curses.beep()
		except curses.error:
			pass


	# ------------------------------------------------------------------
	# Event loop
	# ------------------------------------------------------------------

	def mainloop(self, n=0):
		"""Run the curses event loop until quit().

		The terminal is taken over on first use (here, or earlier by a
		modal wait_window()/wait_variable()) and restored when the
		outermost mainloop returns."""
		outer = self._loopDepth == 0
		if self._scr is None:
			self._startScreen()
		self._quit = False
		self._loopDepth += 1
		try:
			while not self._quit and self._scr is not None:
				self._processOneEvent()
		finally:
			self._loopDepth -= 1
			if outer and self._ownScreen:
				self._stopScreen()
		self._quit = False

	mainLoop = mainloop	# camelCase alias

	def _startScreen(self):
		"""Initialise curses on the real terminal (tkinter starts the
		display when Tk() is created, so modal loops may run before
		mainloop()).  Restored by _stopScreen(), at exit, or before an
		uncaught exception is printed."""
		if self._scr is not None:
			return
		self._adaptTheme()		# asks the terminal: before initscr()
		scr = curses.initscr()
		self._ownScreen = True
		self._captureOutput()
		atexit.register(self._stopScreen)
		self._savedExcepthook = sys.excepthook
		def hook(exc, val, tb, app=self, prev=sys.excepthook):
			app._stopScreen()
			prev(exc, val, tb)
		sys.excepthook = hook
		try:
			self._attach(scr)
		except BaseException:
			self._stopScreen()
			raise

	@staticmethod
	def _adaptTheme():
		"""Adapt the theme roles to the background the widgets are drawn
		on: Tk's light gray in pixel mode with 'tk' colours, otherwise the
		terminal's own background."""
		if _core.PX != 1 and _colors.colorMode() == 'tk':
			kind = 'light'
		else:
			kind = 'dark' if _termbg.isDarkTerminal() else 'light'
		_colors.setBackground(kind)

	def _stopScreen(self):
		if not self._ownScreen:
			return
		self._ownScreen = False
		scr = self._scr
		self._scr	= None
		self._running	= False
		self._postedMenus.clear()
		self._postedDialogs.clear()
		_termWrite(_MOUSE_MODES_OFF)
		try:
			if scr is not None:
				scr.keypad(False)
			curses.echo()
			curses.noraw()
			curses.nocbreak()
			curses.endwin()
		except curses.error:
			pass
		self._releaseOutput()
		if self._savedExcepthook is not None:
			sys.excepthook = self._savedExcepthook
			self._savedExcepthook = None
		if self._errors:
			sys.stderr.write('tktext: exceptions raised in callbacks:\n')
			for tb in self._errors:
				sys.stderr.write(tb)
			self._errors.clear()

	def _captureOutput(self):
		"""While curses owns the terminal, anything printed (print(),
		logging, warnings, C-level stderr) would be written over the
		screen and scroll it.  Keep it and print it after endwin()."""
		import io
		import tempfile
		self._savedStreams = (sys.stdout, sys.stderr)
		self._capturedOut  = io.StringIO()
		self._capturedErr  = io.StringIO()
		sys.stdout = self._capturedOut
		sys.stderr = self._capturedErr
		self._savedFd2 = None
		try:
			self._stderrFile = tempfile.TemporaryFile()
			self._savedFd2   = os.dup(2)
			os.dup2(self._stderrFile.fileno(), 2)
		except OSError:
			self._savedFd2 = None

	def _releaseOutput(self):
		streams = getattr(self, '_savedStreams', None)
		if streams is None:
			return
		self._savedStreams = None
		sys.stdout, sys.stderr = streams
		if self._savedFd2 is not None:
			try:
				os.dup2(self._savedFd2, 2)
				os.close(self._savedFd2)
				self._stderrFile.seek(0)
				data = self._stderrFile.read().decode('utf-8', 'replace')
				self._stderrFile.close()
				if data:
					sys.stderr.write(data)
			except OSError:
				pass
			self._savedFd2 = None
		for text, stream in ((self._capturedOut.getvalue(), sys.stdout),
				(self._capturedErr.getvalue(), sys.stderr)):
			if text:
				stream.write(text)
				stream.flush()

	def _ensureScreen(self):
		"""Make sure a screen exists for a modal loop; False if impossible."""
		if self._scr is None:
			try:
				self._startScreen()
			except curses.error:
				return False
		return True

	def quit(self):
		"""Schedule exit from mainloop."""
		self._quit = True

	def destroy(self):
		"""Destroy all widgets and leave the main loop."""
		self._quit = True
		self._dispatchStructure('<Destroy>')
		for child in list(self._children):
			child.destroy()
		self._toplevels.clear()
		self._focusWidget = None
		self._destroyed   = True
		import tktext._dialog as _dlg
		if _dlg._currentApp is self:
			_dlg._currentApp = None
		if _core._defaultRoot is self:
			_core._defaultRoot = None
			import tktext
			tktext._default_root = None

	def _attach(self, scr, initCurses=True):
		"""Bind the application to a curses (or fake) screen."""
		self._scr		= scr
		self._running		= True
		self._pendingKeys	= []	# read ahead while decoding escapes
		self._lfIsCtrlJ		= False	# nonl(): Enter is CR, Ctrl-J is LF
		# how long a clicked Button stays pressed (no delay on a fake screen)
		self._pressDelay	= 0.1 if initCurses else 0.0
		if initCurses:
			self._colors.init()
			# raw instead of cbreak: Ctrl-C, Ctrl-Z, Ctrl-\\ (ISIG) and
			# Ctrl-S / Ctrl-Q (IXON) reach the application as keys instead
			# of signals / tty flow control (endwin() restores the tty)
			try:
				curses.raw()
				curses.noecho()
			except curses.error:
				pass
			# no CR->LF input translation: Enter sends CR, Ctrl-J sends LF
			try:
				curses.nonl()
				self._lfIsCtrlJ = True
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
			# drag motion and Shift-click reported to the application
			_termWrite(_MOUSE_MODES_ON)
			self._raster.start(scr, _termWrite)
		scr.keypad(True)
		scr.nodelay(False)
		self._setCursor(0)
		self._height, self._width = scr.getmaxyx()
		self._update(force=True)

	def _nextTimeout(self) -> int:
		if self._eventQueue:
			return 0
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
		try:
			key = self._readKey(scr)
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

	def _readKey(self, scr):
		"""Return the next key, decoding the modified special keys the
		terminfo entry does not know (e.g. Super-Right = ESC [1;9C under
		TERM=screen arrives as six separate characters)."""
		pending = getattr(self, '_pendingKeys', None)
		if pending:
			return pending.pop(0)
		scr.timeout(self._nextTimeout())
		key = scr.getch()
		if key == 27:
			return self._readEscape(scr)
		if key == 10 and self._lfIsCtrlJ:
			return ModKey(ord('j'), STATE_CONTROL)
		if key > 0x1ff:
			try:
				name = curses.keyname(key).decode()
			except (curses.error, ValueError, AttributeError):
				return key
			ext = decodeExtended(name)
			if ext is not None:
				return ext
		return key

	def _readEscape(self, scr):
		"""ESC was read: collect a following CSI/SS3 sequence that is
		already buffered.  Returns the decoded key, -1 for an unknown
		sequence (swallowed instead of typed) or 27 for a lone Escape."""
		seq = ''
		scr.timeout(0)
		try:
			while len(seq) < 16:
				try:
					ch = scr.getch()
				except KeyboardInterrupt:	# fake screen: queue empty
					ch = -1
				if ch == -1:
					break
				if not seq and ch == ord(']'):
					return self._readOsc(scr)
				if not seq and ch not in (ord('['), ord('O')):
					self._pendingKeys.append(ch)
					break
				if not 0 <= ch < 128:
					self._pendingKeys.append(ch)
					break
				seq += chr(ch)
				# final byte of the sequence
				if len(seq) > 1 and 0x40 <= ch <= 0x7e:
					break
				if len(seq) > 2 and ch == ord('$'):	# rxvt Shift-<n>~
					break
		finally:
			scr.timeout(self._nextTimeout())
		if not seq:
			return 27
		if len(seq) == 1:			# ESC [ / ESC O typed by hand
			self._pendingKeys.append(ord(seq))
			return 27
		key = decodeEscape(seq)
		return -1 if key is None else key

	def _readOsc(self, scr):
		"""ESC ] was read: swallow an OSC string 'ESC ] <digits> ; ...'
		ended by BEL or ST (ESC \\), a reply of the terminal arriving after
		_termbg stopped waiting for it.  Alt-] typed by hand is not
		followed by '<digits>;' and is returned as ESC, ']'."""
		def getch():
			try:
				return scr.getch()
			except KeyboardInterrupt:	# fake screen: queue empty
				return -1
		prefix = [ord(']')]
		while True:				# '<digits>;' already buffered
			ch = getch()
			if ch == ord(';') and len(prefix) > 1:
				break
			if ch == -1 or not ord('0') <= ch <= ord('9'):
				if ch != -1:
					prefix.append(ch)
				self._pendingKeys.extend(prefix)
				return 27
			prefix.append(ch)
		scr.timeout(50)				# the rest of the reply
		for _ in range(512):
			ch = getch()
			if ch in (-1, 7):		# timeout or BEL
				break
			if ch == 27:			# ST = ESC \
				scr.timeout(0)
				ch = getch()
				if ch not in (-1, ord('\\')):
					self._pendingKeys.append(ch)
				break
		return -1

	def _suspend(self):
		"""Ctrl-Z without a binding: stop the process like the shell job
		control would, and restore the screen when it is continued."""
		if not self._ownScreen or not hasattr(signal, 'SIGTSTP'):
			return
		_termWrite(_MOUSE_MODES_OFF)
		try:
			curses.endwin()
		except curses.error:
			pass
		os.kill(os.getpid(), signal.SIGTSTP)
		# continued (SIGCONT): refresh() returns curses to program mode
		self._scr.refresh()
		_termWrite(_MOUSE_MODES_ON)
		self._update(force=True)

	def _onInterrupt(self):
		"""Ctrl-C: dismiss dialogs, else 'close' the active window (calls
		its WM_DELETE_WINDOW handler like the window manager would)."""
		if self._postedDialogs:
			for d in self._postedDialogs:
				d._dismiss(None)
			return
		self._closeMenus()
		win = self._activeWindow() or self
		handler = win._protocols.get('WM_DELETE_WINDOW')
		try:
			if callable(handler):
				_core._callback(win, handler)
			elif win is self:
				self._quit = True
			else:
				win.destroy()
		except Exception:
			self._reportException()

	def _handleInput(self, key):
		"""Dispatch one raw curses key code (including KEY_MOUSE/KEY_RESIZE)."""
		if key == curses.KEY_RESIZE:
			try:
				curses.update_lines_cols()
			except (curses.error, AttributeError):
				pass
			self._height, self._width = self._scr.getmaxyx()
			try:
				self._scr.clear()
			except curses.error:
				pass
			self._raster.invalidate()
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
	# Windows
	# ------------------------------------------------------------------

	def _windows(self):
		"""Viewable windows (root and Toplevels), bottom to top."""
		wins = [self] if self._viewable() else []
		wins.extend(t for t in self._toplevels if t._viewable())
		return wins

	def _grabWindow(self):
		g = self._grab
		if g is None:
			return None
		if g._destroyed or g._getApp() is not self:
			self._grab = None
			return None
		return g

	def _activeWindow(self):
		"""The window that owns the keyboard: the grab window, else the
		topmost decorated window."""
		g = self._grabWindow()
		if g is not None:
			return g.winfo_toplevel()
		for w in reversed(self._windows()):
			if not w._override:
				return w
		return None

	def _barOwner(self):
		"""Topmost maximised window: its title/menubar occupy row 0."""
		for w in reversed(self._windows()):
			if w._isMaximised():
				return w
		return None

	def _windowAt(self, mx, my):
		for w in reversed(self._windows()):
			if w._isMapped() and w._hitTest(mx, my):
				return w
		return None

	def _raiseWindow(self, win):
		"""Raise *win* to the top; its transient windows stay above it
		(like a window manager keeps dialogs above their master)."""
		if win is self or win not in self._toplevels:
			return
		order = [win] + self._transientsOf(win)
		rest  = [t for t in self._toplevels if t not in order]
		if rest + order != self._toplevels:
			self._toplevels = rest + order
			self._dirty     = True

	def _transientsOf(self, win):
		"""Toplevels transient for *win* (recursively), in stacking order."""
		result = []
		for t in self._toplevels:
			master = t._transientFor
			if t is win or master is None or getattr(master, '_destroyed', True):
				continue
			top = master.winfo_toplevel() if hasattr(master, 'winfo_toplevel') else None
			if top is win:
				result.append(t)
				result.extend(x for x in self._transientsOf(t) if x not in result)
		return result

	# ------------------------------------------------------------------
	# Focus management
	# ------------------------------------------------------------------

	def _setFocus(self, widget):
		if widget is self:
			widget = None
		self._autoFocus = None		# an explicit focus change wins
		old = self._focusWidget
		if old is widget:
			return
		self._focusWidget = widget
		if old is not None:
			old._focused = False
			old._focusChanged(False)
			self._eventQueue.append((old, '<FocusOut>', _FocusEvent(old, 'FocusOut')))
		if widget is not None:
			widget._focused = True
			top = widget.winfo_toplevel()
			top._lastFocus = widget
			widget._focusChanged(True)
			self._eventQueue.append((widget, '<FocusIn>', _FocusEvent(widget, 'FocusIn')))
		self._dirty = True

	def _focusWindow(self):
		"""Window whose widgets take part in Tab traversal."""
		fw = self._focusWidget
		if fw is not None and not fw._destroyed and fw._getApp() is self:
			return fw.winfo_toplevel()
		return self._activeWindow()

	def _focusables(self, win=None):
		win = win if win is not None else self._focusWindow()
		if win is None:
			return []
		return win._getAllFocusable()

	def _focusNext(self):
		focusable = self._focusables()
		if not focusable:
			return
		if self._focusWidget in focusable:
			idx = (focusable.index(self._focusWidget) + 1) % len(focusable)
		else:
			idx = 0
		self._setFocus(focusable[idx])

	def _focusPrev(self):
		focusable = self._focusables()
		if not focusable:
			return
		if self._focusWidget in focusable:
			idx = (focusable.index(self._focusWidget) - 1) % len(focusable)
		else:
			idx = len(focusable) - 1
		self._setFocus(focusable[idx])

	def _focusInto(self, win):
		"""Move the focus into window *win* (last focus or first widget)."""
		last = win._lastFocus
		if last is not None and not last._destroyed and \
				last._isMapped() and win._isAncestorOf(last):
			self._setFocus(last)
			return
		focusable = win._getAllFocusable()
		if focusable:
			self._setFocus(focusable[0])
		elif win is not self:
			self._setFocus(win)

	def _validateFocus(self):
		"""Keep the focus on a live, visible widget of an active window:
		newly mapped windows take the focus; a grab confines it."""
		for win in self._windows():
			if win._needFocus and win._isMapped():
				win._needFocus = False
				if not win._override and win is not self:
					self._focusInto(win)
		# a widget that lost the focus only because it was unmapped for a
		# while (e.g. its page was rebuilt) gets it back when it reappears,
		# unless the focus was moved explicitly in between
		auto = getattr(self, '_autoFocus', None)
		if auto is not None:
			chosen, pending = auto
			if self._focusWidget is not chosen or pending._destroyed:
				self._autoFocus = None
			elif pending._isMapped() and \
					pending.winfo_toplevel() is self._activeWindow():
				self._setFocus(pending)
		fw   = self._focusWidget
		grab = self._grabWindow()
		ok   = fw is not None and not fw._destroyed and \
			fw._getApp() is self and fw._isMapped()
		if ok:
			top = fw.winfo_toplevel()
			ok  = top._viewable() and (top is self or top in self._toplevels)
			# the keyboard belongs to the topmost window (popups aside)
			active = self._activeWindow()
			if ok and active is not None and top is not active and \
					not top._override:
				ok = False
		if ok and grab is not None:
			ok = grab._isAncestorOf(fw)
		if ok:
			self._focusLost = False
			return
		hidden = fw is not None and not fw._destroyed and not fw._isMapped()
		if fw is not None:
			fw._focused	  = False
			self._focusWidget = None
		self._focusLost = False
		win = self._activeWindow()
		if win is not None:
			if hidden and win._lastFocus is fw:
				win._lastFocus = None	# do not pick the hidden one again
			self._focusInto(win)
			if hidden:
				self._autoFocus = (self._focusWidget, fw)

	# ------------------------------------------------------------------
	# Input dispatch
	# ------------------------------------------------------------------

	def _optionLookup(self, className, name, option):
		"""Value of *option* for a widget of class *className* / name
		*name* from the option database (patterns '*Class.option',
		'*name.option', '*option'; the most specific, latest one wins)."""
		key = (className, name, option)
		if key in self._optionCache:
			return self._optionCache[key]
		best, bestScore = None, -1
		opt = option.lower()
		for i, (pattern, value) in enumerate(self._optionDb.items()):
			parts = pattern.replace('.', '*').split('*')
			if parts[-1].lower() != opt:
				continue
			owner = parts[-2] if len(parts) >= 2 else ''
			if owner == '':
				score = 1
			elif owner in (className, name):
				score = 2
			else:
				continue
			if score >= bestScore:
				best, bestScore = value, score
		self._optionCache[key] = best
		return best

	def _dispatchClass(self, widget, patterns, evt):
		"""Fire the bind_class() handlers of *widget*'s class."""
		table = self._classBindings.get(widget.winfo_class())
		if table is None:
			return None
		_, res = table._dispatchFirst(patterns, evt)
		return res

	def _fireVirtualFor(self, widget, patterns):
		"""Fire the virtual events (event_add) whose sequences match a key
		press.  Only virtual events somebody bound are generated; then the
		key is considered handled."""
		table = self._classBindings.get(widget.winfo_class())
		top   = widget.winfo_toplevel()
		for virt, seqs in self._virtualEvents.items():
			if not any(p in seqs for p in patterns):
				continue
			if widget._hasBinding(virt) or self._allBindings._hasBinding(virt) \
					or (table is not None and table._hasBinding(virt)) \
					or (top is not None and top._hasBinding(virt)):
				widget.event_generate(virt)
				return 'break'
		return None

	_KEY_NORMALISE = {
		127:			curses.KEY_BACKSPACE,
		8:			curses.KEY_BACKSPACE,
		13:			KEY_ENTER,
		curses.KEY_ENTER:	KEY_ENTER,
	}

	def _onKey(self, key):
		key = self._KEY_NORMALISE.get(key, key)
		self._dirty = True

		# Modal dialogs and posted menus grab the keyboard, Ctrl-C cancels
		if self._postedDialogs or self._postedMenus:
			if key == KEY_CTRL_C:
				self._onInterrupt()
			elif self._postedDialogs:
				self._postedDialogs[-1]._handleKey(key)
			else:
				self._postedMenus[-1]._handleKey(key)
			return

		if self._menuBar is not None and key == curses.KEY_F10:
			self._openMenuBar(0)
			return

		fw  = self._focusWidget or self._activeWindow() or self
		evt = _newKeyEvent(fw, key)
		pat = evt.patterns()

		# 1. bindings on the widget itself, then on its class
		bound, res = fw._dispatchFirst(pat, evt)
		if res == 'break':
			return
		res = self._dispatchClass(fw, pat, evt)
		if res == 'break':
			return
		bound = bound or res is not None
		if self._fireVirtualFor(fw, pat) == 'break':
			return

		# 2. class behaviour
		consumed = fw is not self and not isModified(key) and \
			fw._handleKey(key)

		# 3. unconsumed: bubble the bindings up through the ancestors
		#    (the first ancestor with a matching binding handles it; like
		#    tkinter only 'break' suppresses the default Tab traversal)
		if not consumed:
			p = fw._parent
			while p is not None:
				matched, res = p._dispatchFirst(pat, evt)
				if matched:
					consumed = res == 'break'
					bound    = True
					break
				p = p._parent

		# 4. application wide bindings and focus traversal
		if not consumed:
			matched, res = self._allBindings._dispatchFirst(pat, evt)
			bound = bound or matched
			if res != 'break':
				if key == KEY_TAB:
					self._focusNext()
				elif key == KEY_BTAB:
					self._focusPrev()
				# raw tty: unbound Ctrl-C / Ctrl-Z act like the signals
				elif bound:
					pass
				elif key == KEY_CTRL_C:
					self._onInterrupt()
				elif key == KEY_CTRL_Z:
					self._suspend()

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
		if px + mw > self._width:
			px = max(0, self._width - mw)
		if py + mh > self._height:
			py = max(0, self._height - mh)
		return px, py, mw, mh

	def _menuAt(self, mx, my):
		for menu in reversed(self._postedMenus):
			px, py, mw, mh = self._menuRect(menu)
			if px <= mx < px + mw and py <= my < py + mh:
				return menu
		return None

	def _onMouse(self, mx, my, bstate):
		self._dirty = True
		btnDrag     = self._btnDrag
		if bstate & (B23_RELEASE | B23_PRESS | B1_PRESS) and not bstate & MOTION:
			self._btnDrag = None	# a release (or a new press) ends it
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

		lastXY        = self._mouseXY
		self._mouseXY = (mx, my)

		# Button 2/3 drags: curses reports the motion without the button,
		# like Tk the motion and the release go to the widget of the press
		if btnDrag is not None and self._dragWidget is None:
			owner, num = btnDrag
			if owner._destroyed:
				self._btnDrag = None
			elif bstate & MOTION and not (bstate & (B1_PRESS | B1_RELEASE | B1_CLICK)):
				self._dispatchMouse(owner, mx, my, MOTION, num)
				return
			elif bstate & B23_RELEASE:
				self._dispatchMouse(owner, mx, my, bstate, False)
				return
		if self._dragWidget is None and self._grabRedirect(mx, my, bstate, anyDown):
			return
		dragging = self._dragWidget is not None
		if dragging and (press or clicked) and self._staleDrag(mx, my):
			self._dragLost()
			dragging = False
		if dragging:
			target = self._dragWidget
			if target._destroyed:
				self._dragWidget = None
				return
			if release and (mx, my) != lastXY:
				# curses drops a motion followed quickly by the release
				self._dispatchMouse(target, mx, my, MOTION, True)
				if target._destroyed or self._dragWidget is not target:
					return
		else:
			win = self._windowAt(mx, my)
			if win is None:
				return
			target = win._findAt(mx, my) or win
			self._trackHover(target, mx, my)
			if release and not clicked:
				# release whose press we never delivered (e.g. the press
				# closed a menu or a dialog): drop it
				return
			if anyDown and not win._override:
				self._raiseWindow(win)
			if press:
				self._dragWidget = target

		if (press or clicked) and not dragging:
			# tkinter: clicking buttons/labels does not move the focus
			if target._isFocusable() and (target._clickFocus or _core.PX == 1):
				self._setFocus(target)

		if not dragging:
			# Tk re-picks the 'current' item/mark before delivering a
			# press or a motion without buttons held
			target._pointerAt(mx, my)

		self._dispatchMouse(target, mx, my, bstate, dragging)

		if release or clicked:
			self._dragWidget = None
		if bstate & B23_PRESS and not bstate & MOTION and \
				self._dragWidget is None and not target._destroyed:
			self._btnDrag = (target, 2 if bstate & curses.BUTTON2_PRESSED else 3)

	def _dispatchMouse(self, target, mx, my, bstate, dragging):
		"""Fire the bindings of a mouse event on *target*, then its class
		behaviour unless a binding returned 'break'."""
		held	= dragging if dragging is not True and dragging else 0
		evt	= _newMouseEvent(target, mx, my, bstate, held)
		broken	= False
		for alts in _mouseEventNames(bstate, dragging):
			_, res = target._dispatchFirst(alts, evt)
			if res != 'break':
				res = self._dispatchClass(target, alts, evt)
			if res == 'break':
				broken = True
			elif not target._destroyed:
				# like the toplevel bindtag of tkinter
				top = target.winfo_toplevel()
				if top is not target:
					top._dispatchFirst(alts, evt)
			self._allBindings._dispatchFirst(alts, evt)

		if not broken and not target._destroyed:
			target._handleMouse(mx, my, bstate)

	def _grabRedirect(self, mx, my, bstate, anyDown) -> bool:
		"""Tk grab semantics: a mouse event outside the grab window's tree
		is reported to the grab window itself (x/y relative to it, thus
		out of its bounds) and never reaches the widget beneath.  A drop
		down (tkExtra.Combobox) closes itself on such a click.  Returns
		True when the event was consumed by the grab."""
		grab = self._grabWindow()
		if grab is None:
			return False
		win = self._windowAt(mx, my)
		if win is not None:
			target = win._findAt(mx, my) or win
			if grab._isAncestorOf(target) or \
					(win._override and not grab.winfo_toplevel()._override):
				return False
		if anyDown and not grab.winfo_toplevel()._override:
			self.bell()		# a modal dialog refuses the click
		evt = _newMouseEvent(grab, mx, my, bstate)
		for alts in _mouseEventNames(bstate, False):
			_, res = grab._dispatchFirst(alts, evt)
			if res != 'break':
				res = self._dispatchClass(grab, alts, evt)
			if res != 'break' and not grab._destroyed:
				top = grab.winfo_toplevel()
				if top is not grab:
					top._dispatchFirst(alts, evt)
			self._allBindings._dispatchFirst(alts, evt)
			if grab._destroyed:
				break
		return True

	def _staleDrag(self, mx, my) -> bool:
		"""A button press arrived while a drag is active: True when the
		release that should have ended the drag was lost (terminals drop
		it, e.g. when the button is let go outside the window or input
		arrives while the program is busy).  Some terminals re-send the
		press on motion, so only a press out of the drag widget's reach
		counts: one that a grab excludes or that lands on another window."""
		drag = self._dragWidget
		if drag._destroyed:
			return False		# dropped by the drag branch below
		top  = drag.winfo_toplevel()
		grab = self._grabWindow()
		if grab is not None and not grab.winfo_toplevel()._isAncestorOf(drag):
			return True
		win = self._windowAt(mx, my)
		return win is not None and win is not top

	def _dragLost(self):
		"""End the current drag whose release never arrived."""
		drag             = self._dragWidget
		self._dragWidget = None
		if not drag._destroyed:
			drag._dragLost()

	def _trackHover(self, target, mx, my):
		"""Fire <Leave>/<Enter> when the pointer moves to another widget."""
		old = self._hover
		if old is target:
			return
		self._hover = target
		for widget, kind in ((old, 'Leave'), (target, 'Enter')):
			if widget is None or widget._destroyed:
				continue
			evt		= _newMouseEvent(widget, mx, my, 0)
			evt.type	= kind
			widget._dispatchFirst([f'<{kind}>', f'<Any-{kind}>'], evt)

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
		return [i for i, it in enumerate(bar._menuItems)
			if it['type'] == 'cascade' and it.get('menu') is not None
			and it.get('state', 'normal') != 'disabled']

	def _openMenuBar(self, idx):
		"""Open the cascade of menubar item *idx* (index into _menuItems)."""
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
		sub = bar._menuItems[idx]['menu']
		sub._fromMenuBar = True
		sub._post(x, 1)
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
		for i, item in enumerate(bar._menuItems):
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
		self._doLayout(0, 0, self._width, self._height)
		if self._viewable():
			self._layoutChildren()
		else:
			for c in self._children:
				if c._geoManager is not None:
					c._unmapTree()
		for top in list(self._toplevels):
			top._layoutWindow(self._width, self._height)
		self._validateFocus()
		self._preRender()
		for top in self._toplevels:
			if top._isMapped():
				top._preRender()
		self._fireStructureEvents()

	_STRUCTURE = ('<Configure>', '<Map>', '<Unmap>', '<Visibility>', '<Expose>')

	def _fireStructureEvents(self):
		"""Fire <Configure> on geometry changes and <Map>/<Unmap> when a
		widget appears/disappears, for widgets that bind them."""
		pending = []
		stack   = [self]
		while stack:
			w = stack.pop()
			stack.extend(w._children)
			if not w._bindings or not any(e in w._bindings for e in self._STRUCTURE):
				continue
			geom = (w._x, w._y, w._width, w._height) if w._isMapped() else None
			if geom != w._lastGeom:
				pending.append((w, geom, w._lastGeom))
				w._lastGeom = geom
		for w, geom, last in pending:
			if w._destroyed:
				continue
			if geom is not None:
				# like winfo_*: pixels in pixel mode
				w._fireStructure('<Configure>', x=w.winfo_x(), y=w.winfo_y(),
					width=w.winfo_width(), height=w.winfo_height())
			if (geom is None) != (last is None):
				if geom is None:
					w._fireStructure('<Unmap>')
				else:
					w._fireStructure('<Map>')
					w._fireStructure('<Visibility>')
					w._fireStructure('<Expose>')

	def _update(self, force=False):
		"""Process pending layout and redraw.  Layout runs without a
		screen too, so that winfo_* answer before mainloop()."""
		if self._dirty or force:
			for _ in range(4):
				self._dirty = False
				self._layout()
				if not self._dirty:
					break
			if self._scr is not None:
				self._redraw()

	def update(self):
		"""Process pending events (queued virtual events, due timers) and
		redraw, like tkinter's update()."""
		self._fireAfterCallbacks()
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
		_fillRect(scr, 0, 0, self._height, self._width, attr=attr)
		self._raster.beginFrame(sum(1 for w in self._rasterWidgets if w._isMapped()))

		if self._viewable():
			self._drawTitleBar(scr, self)
			self._renderChildren(scr)
		for top in list(self._toplevels):
			if top._isMapped():
				top.render(scr)

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
				if not (fw._x <= cx < fw._x + fw._width and
						fw._y <= cy < fw._y + fw._height and
						0 <= cy < self._height and 0 <= cx < self._width):
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
		self._raster.flush(scr)

	def _drawTitleBar(self, scr, owner=None):
		"""Draw the title (and menubar) of the maximised window *owner*
		on row 0.  Only the topmost maximised window shows it."""
		owner = owner if owner is not None else self
		if owner is not self._barOwner():
			return
		barAttr = self._colors.roleAttr('titlebar')
		_addStr(scr, 0, 0, ' ' * self._width, barAttr)
		title  = f' {owner._title} '
		startX = 0
		if self._menuBar is not None:
			self._computeMenuBarPos()
			bar = self._menuBar
			for x0, x1, idx in self._menuBarPos:
				item  = bar._menuItems[idx]
				label = f' {item.get("label", "")} '
				a     = barAttr
				if item.get('state', 'normal') == 'disabled':
					a = self._colors.roleAttr('titlebar.disabled')
				elif idx == self._menuBarActive and self._postedMenus:
					a = self._colors.roleAttr('menubar.active')
				_addStr(scr, 0, x0, label, a)
				startX = x1
			titleX = max(startX + 1, self._width - len(title))
		else:
			titleX = max(0, (self._width - len(title)) // 2)
		if titleX < self._width:
			_addStr(scr, 0, titleX, _pad(title, min(len(title), self._width - titleX)),
				self._colors.roleAttr('titlebar.title'))
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
		return (self._width, self._height)

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

	def _fireQueuedEvents(self):
		"""Deliver queued virtual and focus events (in order, new ones
		included).  Like Tk, focus_set() only queues <FocusIn>/<FocusOut>,
		so their bindings never run inside the caller."""
		count = 0
		while self._eventQueue and count < 1000:
			widget, name, evt = self._eventQueue.pop(0)
			count += 1
			if widget._destroyed:
				continue
			try:
				if name in ('<FocusIn>', '<FocusOut>'):
					widget._dispatch(name, evt)
				else:
					widget._dispatchVirtual(name, evt)
			except Exception:
				self._reportException()
			self._dirty = True

	def _fireAfterCallbacks(self):
		self._fireQueuedEvents()
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
				_core._callback(self, func, *args)
			except Exception:
				self._reportException()
			self._fireQueuedEvents()
		if fired:
			self._dirty = True


# ---------------------------------------------------------------------------
# Inner geometry proxy (skips the title bar row)
# ---------------------------------------------------------------------------

class _TkInner:
	def __init__(self, tk):
		self._x = tk._x
		self._y = tk._y + 1		# skip title bar
		self._width = tk._width
		self._height = max(0, tk._height - 1)


# ---------------------------------------------------------------------------
# Minimal focus event
# ---------------------------------------------------------------------------

class _FocusEvent(Event):
	def __init__(self, widget, kind='Focus'):
		super().__init__()
		self.widget = widget
		self.type   = kind
