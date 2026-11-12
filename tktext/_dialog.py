"""Blocking modal dialog base class, message box, and file picker."""
import curses
import fnmatch
import os
import textwrap

from ._core import _addStr, _fillRect, _drawBorder, _pad, _clip
from ._events import (KEY_ENTER, KEY_CR, KEY_ESC, KEY_LEFT, KEY_RIGHT,
	KEY_TAB, KEY_BTAB, KEY_UP, KEY_DOWN, KEY_HOME, KEY_END,
	KEY_BACKSPACE, KEY_PPAGE, KEY_NPAGE, KEY_SPACE, MOTION,
	B1_PRESS, B1_RELEASE, B1_CLICK, B1_DCLICK, isWheel)

# ---------------------------------------------------------------------------
# Module-level app registry (set by Tk.__init__)
# ---------------------------------------------------------------------------

_currentApp = None


def _getApp(parent=None):
	if parent is not None and hasattr(parent, '_getApp'):
		app = parent._getApp()
		if app is not None:
			return app
	return _currentApp


# ---------------------------------------------------------------------------
# Base dialog
# ---------------------------------------------------------------------------

class _Dialog:
	"""Base class for blocking modal overlays.

	run() spins the application's own event loop (so timers keep firing
	and the screen keeps redrawing) until the dialog is dismissed.  While
	a dialog is posted the application routes every key and mouse event
	to it.
	"""

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

		savedDrag	= app._dragWidget
		savedGrab	= app._menuGrab
		app._dragWidget	= None
		app._menuGrab	= False
		for m in list(app._postedMenus):
			m.unpost()
		app._postedDialogs.append(self)
		app._dirty	= True
		try:
			app._update()
			while not self._done and not app._quit and app._scr is not None:
				app._processOneEvent()
		finally:
			if self in app._postedDialogs:
				app._postedDialogs.remove(self)
			app._dragWidget	= savedDrag
			app._menuGrab	= savedGrab
			app._dirty	= True
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


def _released(bstate) -> bool:
	return bool(bstate & (B1_RELEASE | B1_CLICK | B1_DCLICK))


def _pressed(bstate) -> bool:
	return bool(bstate & B1_PRESS) and not (bstate & MOTION)


# ---------------------------------------------------------------------------
# Message box dialog
# ---------------------------------------------------------------------------

class _MsgDialog(_Dialog):
	"""Modal dialog with title, multi-line message, and labelled buttons."""

	_ICONS = {'info': 'i', 'warning': '!', 'error': 'X', 'question': '?'}

	def __init__(self, app, title: str, message: str,
			buttons: list, icon: str = '', default=None):
		super().__init__(app)
		self._title   = str(title)
		self._message = str(message)
		self._buttons = buttons	# list of (label, return_value)
		self._icon    = icon	# 'info', 'warning', 'error', 'question'
		self._btnIdx  = 0
		if default is not None:
			for i, (label, value) in enumerate(buttons):
				if default in (label, value) or str(default).lower() == label.lower():
					self._btnIdx = i

	def _lines(self):
		maxW  = max(10, self._app._w - 10)
		lines = []
		for para in self._message.split('\n'):
			lines.extend(textwrap.wrap(para, maxW) or [''])
		maxH  = max(1, self._app._h - 7)
		if len(lines) > maxH:
			lines = lines[:maxH - 1] + ['…']
		return lines

	def _btnTotal(self):
		return sum(len(b[0]) + 4 for b in self._buttons) + len(self._buttons) - 1

	def _size(self):
		lines = self._lines()
		msgW  = max((len(l) for l in lines), default=0) + 6
		w     = max(len(self._title) + 6, msgW, self._btnTotal() + 4, 24)
		w     = min(w, max(10, self._app._w))
		h     = min(len(lines) + 6, max(6, self._app._h))
		return (w, h)

	def _pos(self):
		app  = self._app
		w, h = self._size()
		return (max(0, (app._w - w) // 2), max(0, (app._h - h) // 2))

	def _buttonSpans(self):
		w, h  = self._size()
		x, y  = self._pos()
		bx    = x + max(1, (w - self._btnTotal()) // 2)
		spans = []
		for label, _ in self._buttons:
			btn = f'[ {label} ]'
			spans.append((bx, bx + len(btn), btn))
			bx += len(btn) + 1
		return y + h - 2, spans

	def render(self, scr):
		app      = self._app
		w, h     = self._size()
		x, y     = self._pos()
		attr     = app._colors.getAttr('white', 'blue')
		titleA   = app._colors.getAttr('yellow', 'blue', bold=True)
		selA     = app._colors.getAttr('black',  'white', bold=True)

		_fillRect(scr, y, x, h, w, attr=attr)
		_drawBorder(scr, y, x, h, w, 'double', attr)
		_addStr(scr, y + 1, x + 1, _pad(f' {self._title} ', w - 2, 'center'), titleA)
		_addStr(scr, y + 2, x + 1, '─' * (w - 2), attr)

		iconCh = self._ICONS.get(self._icon, ' ')
		for i, line in enumerate(self._lines()):
			if 3 + i >= h - 3:
				break
			pfx = f'{iconCh} ' if i == 0 else '  '
			_addStr(scr, y + 3 + i, x + 2, pfx + _clip(line, w - 6), attr)

		_addStr(scr, y + h - 3, x + 1, '─' * (w - 2), attr)

		btnRow, spans = self._buttonSpans()
		for i, (bx, _, btn) in enumerate(spans):
			_addStr(scr, btnRow, bx, btn, selA if i == self._btnIdx else attr)

	def _handleKey(self, key):
		n = len(self._buttons)
		if key in (KEY_LEFT, KEY_BTAB, KEY_UP):
			self._btnIdx = (self._btnIdx - 1) % n
		elif key in (KEY_RIGHT, KEY_TAB, KEY_DOWN):
			self._btnIdx = (self._btnIdx + 1) % n
		elif key in (KEY_ENTER, KEY_CR, KEY_SPACE):
			self._dismiss(self._buttons[self._btnIdx][1])
		elif key == KEY_ESC:
			self._dismiss(self._buttons[-1][1])
		elif isinstance(key, int) and 32 < key < 127:
			# first letter of a button label activates it (y/n/o/c …)
			ch = chr(key).lower()
			for label, value in self._buttons:
				if label[:1].lower() == ch:
					self._dismiss(value)
					return

	def _handleMouse(self, mx, my, bstate):
		btnRow, spans = self._buttonSpans()
		if my != btnRow:
			return
		for i, (x0, x1, _) in enumerate(spans):
			if x0 <= mx < x1:
				self._btnIdx = i
				if _released(bstate):
					self._dismiss(self._buttons[i][1])
				return

	def _fallback(self):
		# No curses: print and return default (first button value)
		print(f'\n[{self._title}] {self._message}')
		return self._buttons[self._btnIdx][1]


# ---------------------------------------------------------------------------
# File picker dialog
# ---------------------------------------------------------------------------

def _patterns(filetypes):
	"""Return the list of glob patterns of the first filetype entry."""
	if not filetypes:
		return ['*']
	ft = filetypes[0]
	if isinstance(ft, (tuple, list)) and len(ft) >= 2:
		pats = ft[1]
	else:
		pats = ft
	if isinstance(pats, str):
		pats = pats.split()
	out = []
	for p in pats:
		p = str(p)
		if p in ('*.*', '*', ''):
			return ['*']
		if p.startswith('.'):
			p = '*' + p
		out.append(p)
	return out or ['*']


class _FileDialog(_Dialog):
	"""Simple interactive file-browser dialog."""

	_ORDER = ['list', 'entry', 'ok', 'cancel']

	def __init__(self, app, title: str, mode: str = 'open',
			initialdir: str = None, initialfile: str = '',
			filetypes=None, defaultextension: str = '',
			multiple: bool = False):
		super().__init__(app)
		self._title      = title
		self._mode       = mode		# 'open', 'save', 'dir'
		startDir         = os.path.expanduser(initialdir or os.getcwd())
		if not os.path.isdir(startDir):
			startDir = os.getcwd()
		self._curDir     = os.path.abspath(startDir)
		self._filename   = initialfile or ''
		self._filetypes  = list(filetypes or [('All Files', '*')])
		self._patterns   = _patterns(self._filetypes)
		self._defExt     = defaultextension or ''
		self._multiple   = multiple
		self._entries    = []		# (name, isDir)
		self._listIdx    = 0
		self._listScroll = 0
		self._listH      = 10
		self._focus      = 'entry' if mode == 'save' else 'list'
		self._error      = ''
		self._refreshEntries()

	def _refreshEntries(self):
		items  = []
		parent = os.path.dirname(self._curDir)
		if parent != self._curDir:
			items.append(('..', True))
		try:
			names = os.listdir(self._curDir)
		except OSError as e:
			self._error = str(e)
			names = []
		dirs  = []
		files = []
		for name in names:
			full = os.path.join(self._curDir, name)
			if os.path.isdir(full):
				dirs.append(name)
			elif self._mode != 'dir' and any(fnmatch.fnmatch(name, p)
					for p in self._patterns):
				files.append(name)
		dirs.sort(key=str.lower)
		files.sort(key=str.lower)
		items += [(d, True) for d in dirs] + [(f, False) for f in files]
		self._entries    = items
		self._listIdx    = 0
		self._listScroll = 0

	def _size(self):
		app = self._app
		w   = min(70, max(30, app._w - 4))
		h   = min(24, max(12, app._h - 2))
		return (min(w, app._w), min(h, app._h))

	def _pos(self):
		app  = self._app
		w, h = self._size()
		return (max(0, (app._w - w) // 2), max(0, (app._h - h) // 2))

	def _geometry(self):
		w, h   = self._size()
		x, y   = self._pos()
		listY  = y + 5
		listH  = max(1, h - 10)
		sepY   = listY + listH
		entryY = sepY + 1
		btnY   = entryY + 2
		return x, y, w, h, listY, listH, entryY, btnY

	def _buttons(self):
		x, y, w, h, _, _, _, btnY = self._geometry()
		okLbl = '[ OK ]'
		caLbl = '[ Cancel ]'
		okX   = x + w - len(caLbl) - len(okLbl) - 4
		caX   = x + w - len(caLbl) - 2
		return btnY, (okX, okLbl), (caX, caLbl)

	def render(self, scr):
		app    = self._app
		x, y, w, h, listY, listH, entryY, _ = self._geometry()
		self._listH = listH
		attr   = app._colors.getAttr('white', 'blue')
		titleA = app._colors.getAttr('yellow', 'blue', bold=True)
		selA   = app._colors.getAttr('black',  'cyan')
		focA   = app._colors.getAttr('black',  'white', bold=True)
		dirA   = app._colors.getAttr('cyan',   'blue',  bold=True)

		_fillRect(scr, y, x, h, w, attr=attr)
		_drawBorder(scr, y, x, h, w, 'double', attr)
		_addStr(scr, y + 1, x + 1, _pad(f' {self._title} ', w - 2, 'center'), titleA)
		_addStr(scr, y + 2, x + 1, '─' * (w - 2), attr)

		# Current directory (show the tail when too long)
		dirStr = self._error or self._curDir
		if len(dirStr) > w - 4:
			dirStr = '…' + dirStr[-(w - 5):]
		_addStr(scr, y + 3, x + 2, dirStr.ljust(w - 4), attr | curses.A_BOLD)
		_addStr(scr, y + 4, x + 1, '─' * (w - 2), attr)

		# File list
		listW = w - 4
		self._clampScroll()
		for i in range(listH):
			eidx = self._listScroll + i
			row  = listY + i
			if eidx >= len(self._entries):
				_addStr(scr, row, x + 2, ' ' * listW, attr)
				continue
			name, isDir = self._entries[eidx]
			disp = _pad((name + '/') if isDir else name, listW)
			if eidx == self._listIdx:
				iattr = selA if self._focus == 'list' else attr | curses.A_REVERSE
			elif isDir:
				iattr = dirA
			else:
				iattr = attr
			_addStr(scr, row, x + 2, disp, iattr)

		_addStr(scr, listY + listH, x + 1, '─' * (w - 2), attr)

		# Filename entry
		label  = 'Dir:  ' if self._mode == 'dir' else 'File: '
		_addStr(scr, entryY, x + 2, label, attr)
		entryW = max(1, w - 10)
		fnDisp = _pad(self._filename[-(entryW - 1):] +
			('_' if self._focus == 'entry' else ''), entryW)
		_addStr(scr, entryY, x + 8, fnDisp,
			focA if self._focus == 'entry' else attr | curses.A_UNDERLINE)

		_addStr(scr, entryY + 1, x + 1, '─' * (w - 2), attr)

		# Buttons
		btnY, (okX, okLbl), (caX, caLbl) = self._buttons()
		_addStr(scr, btnY, okX, okLbl, focA if self._focus == 'ok' else attr)
		_addStr(scr, btnY, caX, caLbl, focA if self._focus == 'cancel' else attr)

	def _clampScroll(self):
		n = len(self._entries)
		self._listIdx = max(0, min(self._listIdx, n - 1))
		if self._listIdx < self._listScroll:
			self._listScroll = self._listIdx
		elif self._listIdx >= self._listScroll + self._listH:
			self._listScroll = self._listIdx - self._listH + 1
		self._listScroll = max(0, min(self._listScroll, max(0, n - self._listH)))

	def _handleKey(self, key):
		self._error = ''
		if key == KEY_ESC:
			self._dismiss(None)
			return
		if key in (KEY_TAB, KEY_BTAB):
			delta = 1 if key == KEY_TAB else -1
			i = self._ORDER.index(self._focus)
			self._focus = self._ORDER[(i + delta) % len(self._ORDER)]
			return

		if self._focus == 'list':
			n = len(self._entries)
			if key == KEY_UP:
				self._listIdx -= 1
			elif key == KEY_DOWN:
				self._listIdx += 1
			elif key == KEY_PPAGE:
				self._listIdx -= self._listH
			elif key == KEY_NPAGE:
				self._listIdx += self._listH
			elif key == KEY_HOME:
				self._listIdx = 0
			elif key == KEY_END:
				self._listIdx = n - 1
			elif key in (KEY_ENTER, KEY_CR):
				self._activateEntry(self._listIdx)
			elif key == KEY_BACKSPACE:
				self._goUp()
			elif isinstance(key, int) and 32 <= key <= 126:
				# start typing a file name
				self._focus    = 'entry'
				self._filename = chr(key)
			self._clampScroll()
			if self._mode != 'save' and 0 <= self._listIdx < n and \
					key in (KEY_UP, KEY_DOWN, KEY_PPAGE, KEY_NPAGE, KEY_HOME, KEY_END):
				name, isDir = self._entries[self._listIdx]
				if not isDir:
					self._filename = name

		elif self._focus == 'entry':
			if key in (KEY_ENTER, KEY_CR):
				self._confirmOk()
			elif key == KEY_BACKSPACE:
				self._filename = self._filename[:-1]
			elif key in (KEY_UP, KEY_DOWN):
				self._focus = 'list'
			elif isinstance(key, int) and 32 <= key <= 126:
				self._filename += chr(key)

		elif self._focus in ('ok', 'cancel'):
			if key in (KEY_LEFT, KEY_RIGHT):
				self._focus = 'cancel' if self._focus == 'ok' else 'ok'
			elif key in (KEY_ENTER, KEY_CR, KEY_SPACE):
				if self._focus == 'ok':
					self._confirmOk()
				else:
					self._dismiss(None)

	def _goUp(self):
		parent = os.path.dirname(self._curDir)
		if parent != self._curDir:
			old          = os.path.basename(self._curDir)
			self._curDir = parent
			self._refreshEntries()
			for i, (name, _) in enumerate(self._entries):
				if name == old:
					self._listIdx = i

	def _activateEntry(self, idx: int):
		if not (0 <= idx < len(self._entries)):
			return
		name, isDir = self._entries[idx]
		if isDir:
			if name == '..':
				self._goUp()
				return
			self._curDir = os.path.abspath(os.path.join(self._curDir, name))
			self._refreshEntries()
			if self._mode != 'save':
				self._filename = ''
		else:
			self._filename = name
			self._confirmOk()

	def _confirmOk(self):
		if self._mode == 'dir':
			fn = self._filename.strip()
			if fn:
				path = os.path.abspath(os.path.join(self._curDir,
					os.path.expanduser(fn)))
				if os.path.isdir(path):
					self._dismiss(path)
				else:
					self._error = f'Not a directory: {fn}'
				return
			self._dismiss(self._curDir)
			return
		fn = os.path.expanduser(self._filename.strip())
		if not fn:
			# no filename typed — use selected entry if it's a file
			if 0 <= self._listIdx < len(self._entries):
				name, isDir = self._entries[self._listIdx]
				if isDir:
					self._activateEntry(self._listIdx)
					return
				fn = name
		if not fn:
			return
		path = fn if os.path.isabs(fn) else os.path.join(self._curDir, fn)
		path = os.path.abspath(path)
		if os.path.isdir(path):
			self._curDir   = path
			self._filename = ''
			self._refreshEntries()
			return
		if self._mode == 'open' and not os.path.exists(path):
			self._error = f'File not found: {fn}'
			return
		if self._defExt and not os.path.splitext(path)[1]:
			ext   = self._defExt if self._defExt.startswith('.') else '.' + self._defExt
			path += ext
		self._dismiss(path)

	def _handleMouse(self, mx, my, bstate):
		x, y, w, h, listY, listH, entryY, _ = self._geometry()
		wheel = isWheel(bstate)
		if wheel:
			self._listScroll = max(0, self._listScroll + 3 * wheel)
			self._listScroll = min(self._listScroll,
				max(0, len(self._entries) - listH))
			return
		if not (_pressed(bstate) or _released(bstate)):
			return

		if listY <= my < listY + listH and x <= mx < x + w:
			idx = self._listScroll + (my - listY)
			if idx < len(self._entries):
				self._focus   = 'list'
				self._listIdx = idx
				name, isDir = self._entries[idx]
				if not isDir and self._mode != 'save':
					self._filename = name
				if bstate & B1_DCLICK or (bstate & B1_CLICK and isDir):
					self._activateEntry(idx)
			return

		if my == entryY and x + 8 <= mx < x + w - 2:
			self._focus = 'entry'
			return

		btnY, (okX, okLbl), (caX, caLbl) = self._buttons()
		if my == btnY:
			if okX <= mx < okX + len(okLbl):
				self._focus = 'ok'
				if _released(bstate):
					self._confirmOk()
			elif caX <= mx < caX + len(caLbl):
				self._focus = 'cancel'
				if _released(bstate):
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
