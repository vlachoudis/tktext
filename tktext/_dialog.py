"""Blocking modal dialog base class, message box, and file picker."""
import curses
import os

from ._core import _addStr, _fillRect, _drawBorder, _pad, _clip
from ._events import (KEY_ENTER, KEY_CR, KEY_ESC, KEY_LEFT, KEY_RIGHT,
	KEY_TAB, KEY_BTAB, KEY_UP, KEY_DOWN, KEY_HOME, KEY_END,
	KEY_BACKSPACE, KEY_PPAGE, KEY_NPAGE)

# ---------------------------------------------------------------------------
# Module-level app registry (set by Tk.__init__)
# ---------------------------------------------------------------------------

_currentApp = None


def _getApp():
	return _currentApp


# ---------------------------------------------------------------------------
# Base dialog
# ---------------------------------------------------------------------------

class _Dialog:
	"""Base class for blocking modal overlays."""

	def __init__(self, app):
		self._app    = app
		self._done   = False
		self._result = None

	def _dismiss(self, result):
		self._result = result
		self._done   = True

	def run(self):
		"""Block until dismissed; return result."""
		app = self._app
		if app is None or app._scr is None:
			return self._fallback()

		savedDrag      = app._dragWidget
		app._dragWidget = None
		app._postedDialogs.append(self)

		while not self._done:
			app._doLayout(0, 0, app._w, app._h)
			app._layoutChildren()
			app._redraw()
			try:
				key = app._scr.getch()
			except KeyboardInterrupt:
				self._dismiss(None)
				break
			if key == curses.KEY_RESIZE:
				app._h, app._w = app._scr.getmaxyx()
			elif key == curses.KEY_MOUSE:
				try:
					_, mx, my, _, bstate = curses.getmouse()
					self._handleMouse(mx, my, bstate)
				except curses.error:
					pass
			elif key != -1:
				self._handleKey(key)

		app._postedDialogs.remove(self)
		app._dragWidget = savedDrag
		app._dirty      = True
		return self._result

	def _fallback(self):
		"""Called when no curses screen is available (e.g. during startup)."""
		return self._result

	def render(self, scr):
		pass

	def _handleKey(self, key):
		pass

	def _handleMouse(self, mx, my, bstate):
		pass


# ---------------------------------------------------------------------------
# Message box dialog
# ---------------------------------------------------------------------------

class _MsgDialog(_Dialog):
	"""Modal dialog with title, multi-line message, and labelled buttons."""

	def __init__(self, app, title: str, message: str,
			buttons: list, icon: str = ''):
		super().__init__(app)
		self._title   = title
		self._message = message
		self._buttons = buttons	# list of (label, return_value)
		self._icon    = icon	# 'info', 'warning', 'error', 'question'
		self._btnIdx  = 0

	def _size(self):
		lines   = self._message.split('\n')
		msgW    = max((len(l) for l in lines), default=0) + 6
		btnW    = sum(len(b[0]) + 4 for b in self._buttons) + len(self._buttons) + 2
		w       = max(len(self._title) + 6, msgW, btnW, 24)
		h       = len(lines) + 6
		return (w, h)

	def _pos(self):
		app  = self._app
		w, h = self._size()
		return (max(0, (app._w - w) // 2), max(0, (app._h - h) // 2))

	def render(self, scr):
		app      = self._app
		w, h     = self._size()
		x, y     = self._pos()
		attr     = app._colors.getAttr('white', 'blue')
		titleA   = app._colors.getAttr('yellow', 'blue', bold=True)
		selA     = app._colors.getAttr('black',  'white', bold=True)
		iconMap  = {'info': 'ℹ', 'warning': '⚠', 'error': '✗', 'question': '?'}

		_fillRect(scr, y, x, h, w, attr=attr)
		_drawBorder(scr, y, x, h, w, 'double', attr)
		_addStr(scr, y + 1, x + 1, _pad(f' {self._title} ', w - 2, 'center'), titleA)
		_addStr(scr, y + 2, x + 1, '─' * (w - 2), attr)

		iconCh = iconMap.get(self._icon, ' ')
		lines  = self._message.split('\n')
		for i, line in enumerate(lines):
			pfx = f'{iconCh} ' if i == 0 else '  '
			_addStr(scr, y + 3 + i, x + 2, pfx + _clip(line, w - 6), attr)

		_addStr(scr, y + h - 3, x + 1, '─' * (w - 2), attr)

		btnRow = y + h - 2
		total  = sum(len(b[0]) + 4 for b in self._buttons) + len(self._buttons) - 1
		bx     = x + max(1, (w - total) // 2)
		for i, (label, _) in enumerate(self._buttons):
			battr = selA if i == self._btnIdx else attr
			btn   = f'[ {label} ]'
			_addStr(scr, btnRow, bx, btn, battr)
			bx += len(btn) + 1

	def _handleKey(self, key):
		if key in (KEY_LEFT, KEY_BTAB):
			self._btnIdx = (self._btnIdx - 1) % len(self._buttons)
		elif key in (KEY_RIGHT, KEY_TAB):
			self._btnIdx = (self._btnIdx + 1) % len(self._buttons)
		elif key in (KEY_ENTER, KEY_CR):
			self._dismiss(self._buttons[self._btnIdx][1])
		elif key == KEY_ESC:
			self._dismiss(self._buttons[-1][1])

	def _handleMouse(self, mx, my, bstate):
		if not (bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED)):
			return
		w, h   = self._size()
		x, y   = self._pos()
		btnRow = y + h - 2
		if my != btnRow:
			return
		total  = sum(len(b[0]) + 4 for b in self._buttons) + len(self._buttons) - 1
		bx     = x + max(1, (w - total) // 2)
		for i, (label, val) in enumerate(self._buttons):
			btn = f'[ {label} ]'
			if bx <= mx < bx + len(btn):
				self._dismiss(val)
				return
			bx += len(btn) + 1

	def _fallback(self):
		# No curses: print and return default (first button value)
		print(f'\n[{self._title}] {self._message}')
		return self._buttons[0][1]


# ---------------------------------------------------------------------------
# File picker dialog
# ---------------------------------------------------------------------------

class _FileDialog(_Dialog):
	"""Simple interactive file-browser dialog."""

	def __init__(self, app, title: str, mode: str = 'open',
			initialdir: str = None, initialfile: str = '',
			filetypes=None, defaultextension: str = '',
			multiple: bool = False):
		super().__init__(app)
		self._title      = title
		self._mode       = mode		# 'open', 'save', 'dir'
		self._curDir     = os.path.abspath(initialdir or os.getcwd())
		self._filename   = initialfile or ''
		self._filetypes  = filetypes or [('All Files', '*.*')]
		self._defExt     = defaultextension
		self._multiple   = multiple
		self._entries    = []		# (name, is_dir)
		self._listIdx    = 0
		self._listScroll = 0
		self._listH      = 10
		self._focus      = 'list'	# 'list' | 'entry' | 'ok' | 'cancel'
		self._refreshEntries()

	def _refreshEntries(self):
		try:
			items = []
			parent = os.path.dirname(self._curDir)
			if parent != self._curDir:
				items.append(('..', True))
			for name in sorted(os.listdir(self._curDir),
					key=lambda n: (not os.path.isdir(os.path.join(self._curDir, n)), n.lower())):
				items.append((name, os.path.isdir(os.path.join(self._curDir, name))))
			self._entries    = items
			self._listIdx    = 0
			self._listScroll = 0
		except (PermissionError, OSError):
			self._entries = [('..', True)]

	def _size(self):
		app = self._app
		w   = min(60, max(42, app._w - 4))
		h   = min(22, max(16, app._h - 4))
		return (w, h)

	def _pos(self):
		app  = self._app
		w, h = self._size()
		return (max(0, (app._w - w) // 2), max(0, (app._h - h) // 2))

	def render(self, scr):
		app      = self._app
		w, h     = self._size()
		x, y     = self._pos()
		attr     = app._colors.getAttr('white', 'blue')
		titleA   = app._colors.getAttr('yellow', 'blue', bold=True)
		selA     = app._colors.getAttr('black',  'cyan')
		focA     = app._colors.getAttr('black',  'white', bold=True)
		dirA     = app._colors.getAttr('cyan',   'blue',  bold=True)
		btnA     = app._colors.getAttr('black',  'white', bold=True)

		_fillRect(scr, y, x, h, w, attr=attr)
		_drawBorder(scr, y, x, h, w, 'double', attr)
		_addStr(scr, y + 1, x + 1, _pad(f' {self._title} ', w - 2, 'center'), titleA)
		_addStr(scr, y + 2, x + 1, '─' * (w - 2), attr)

		# Current directory
		dirStr = _clip(self._curDir, w - 4)
		_addStr(scr, y + 3, x + 2, dirStr.ljust(w - 4), attr | curses.A_BOLD)
		_addStr(scr, y + 4, x + 1, '─' * (w - 2), attr)

		# File list
		listY       = y + 5
		self._listH = h - 10
		listW       = w - 4
		for i in range(self._listH):
			eidx = self._listScroll + i
			row  = listY + i
			if eidx >= len(self._entries):
				_addStr(scr, row, x + 2, ' ' * listW, attr)
				continue
			name, is_dir = self._entries[eidx]
			disp  = _pad((name + '/') if is_dir else name, listW)
			if eidx == self._listIdx and self._focus == 'list':
				iattr = selA
			elif is_dir:
				iattr = dirA
			else:
				iattr = attr
			_addStr(scr, row, x + 2, disp, iattr)

		sepY = listY + self._listH
		_addStr(scr, sepY, x + 1, '─' * (w - 2), attr)

		# Filename entry
		entryY = sepY + 1
		_addStr(scr, entryY, x + 2, 'File: ', attr)
		entryX = x + 8
		entryW = w - 10
		fnDisp = _pad(self._filename[-entryW:], entryW)
		eattr  = focA if self._focus == 'entry' else attr
		_addStr(scr, entryY, entryX, fnDisp, eattr)

		_addStr(scr, entryY + 1, x + 1, '─' * (w - 2), attr)

		# Buttons
		btnY   = entryY + 2
		okLbl  = '[ OK ]'
		caLbl  = '[ Cancel ]'
		okX    = x + w - len(caLbl) - len(okLbl) - 4
		caX    = x + w - len(caLbl) - 2
		_addStr(scr, btnY, okX, okLbl, btnA if self._focus == 'ok'     else attr)
		_addStr(scr, btnY, caX, caLbl, btnA if self._focus == 'cancel' else attr)

	def _handleKey(self, key):
		if key == KEY_ESC:
			self._dismiss(None)
			return
		if key == KEY_TAB:
			order = ['list', 'entry', 'ok', 'cancel']
			self._focus = order[(order.index(self._focus) + 1) % len(order)]
			return
		if key == KEY_BTAB:
			order = ['list', 'entry', 'ok', 'cancel']
			self._focus = order[(order.index(self._focus) - 1) % len(order)]
			return

		if self._focus == 'list':
			if key == KEY_UP:
				self._listIdx = max(0, self._listIdx - 1)
				if self._listIdx < self._listScroll:
					self._listScroll -= 1
			elif key == KEY_DOWN:
				self._listIdx = min(len(self._entries) - 1, self._listIdx + 1)
				if self._listIdx >= self._listScroll + self._listH:
					self._listScroll += 1
			elif key == KEY_PPAGE:
				self._listIdx = max(0, self._listIdx - self._listH)
				self._listScroll = max(0, self._listScroll - self._listH)
			elif key == KEY_NPAGE:
				self._listIdx = min(len(self._entries) - 1,
					self._listIdx + self._listH)
				if self._listIdx >= self._listScroll + self._listH:
					self._listScroll = self._listIdx - self._listH + 1
			elif key == KEY_HOME:
				self._listIdx = 0; self._listScroll = 0
			elif key == KEY_END:
				self._listIdx = max(0, len(self._entries) - 1)
				self._listScroll = max(0, self._listIdx - self._listH + 1)
			elif key in (KEY_ENTER, KEY_CR):
				self._activateEntry(self._listIdx)

		elif self._focus == 'entry':
			if key in (KEY_ENTER, KEY_CR):
				self._confirmOk()
			elif key in (KEY_BACKSPACE, 127):
				self._filename = self._filename[:-1]
			elif 32 <= key <= 126:
				self._filename += chr(key)

		elif self._focus in ('ok', 'cancel'):
			if key in (KEY_ENTER, KEY_CR):
				if self._focus == 'ok':
					self._confirmOk()
				else:
					self._dismiss(None)

	def _activateEntry(self, idx: int):
		if idx >= len(self._entries):
			return
		name, is_dir = self._entries[idx]
		if is_dir:
			newDir = (os.path.dirname(self._curDir) if name == '..'
				else os.path.join(self._curDir, name))
			self._curDir = os.path.abspath(newDir)
			self._refreshEntries()
			self._filename = ''
		else:
			self._filename = name
			self._focus    = 'entry'

	def _confirmOk(self):
		if self._mode == 'dir':
			if self._listIdx < len(self._entries):
				name, is_dir = self._entries[self._listIdx]
				if is_dir and name != '..':
					self._dismiss(os.path.join(self._curDir, name))
					return
			self._dismiss(self._curDir)
			return
		fn = self._filename.strip()
		if not fn:
			# no filename typed — use selected entry if it's a file
			if self._listIdx < len(self._entries):
				name, is_dir = self._entries[self._listIdx]
				if not is_dir:
					fn = name
		if not fn:
			return
		if not os.path.isabs(fn):
			fn = os.path.join(self._curDir, fn)
		if self._defExt and not os.path.splitext(fn)[1]:
			fn += self._defExt
		self._dismiss(fn)

	def _handleMouse(self, mx, my, bstate):
		if not (bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED)):
			return
		w, h    = self._size()
		x, y    = self._pos()
		listY   = y + 5
		sepY    = listY + self._listH
		entryY  = sepY + 1
		btnY    = entryY + 2

		if listY <= my < listY + self._listH and x <= mx < x + w:
			self._focus   = 'list'
			self._listIdx = min(len(self._entries) - 1,
				self._listScroll + (my - listY))
			if bstate & curses.BUTTON1_CLICKED:
				self._activateEntry(self._listIdx)

		elif my == entryY and x + 8 <= mx < x + w - 2:
			self._focus = 'entry'

		elif my == btnY:
			okLbl = '[ OK ]'
			caLbl = '[ Cancel ]'
			okX   = x + w - len(caLbl) - len(okLbl) - 4
			caX   = x + w - len(caLbl) - 2
			if okX <= mx < okX + len(okLbl):
				self._confirmOk()
			elif caX <= mx < caX + len(caLbl):
				self._dismiss(None)

	def _fallback(self):
		# No curses screen: use input() as a minimal fallback
		try:
			fn = input(f'{self._title} [{self._curDir}]: ').strip()
			if fn and not os.path.isabs(fn):
				fn = os.path.join(self._curDir, fn)
			return fn or None
		except (EOFError, KeyboardInterrupt):
			return None
