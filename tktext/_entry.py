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

from ._core import (TclError, Widget, _fillRect, _drawBorder, _addStr, _int, _initArgs, _cellX,
	_pxBox, _callback)
from ._tcl import _splitlist
from ._events import (KEY_LEFT, KEY_RIGHT, KEY_HOME, KEY_END,
	KEY_BACKSPACE, KEY_DC, KEY_SHIFT_LEFT, KEY_SHIFT_RIGHT, KEY_SHIFT_HOME,
	KEY_SHIFT_END, B1_PRESS, B1_RELEASE, B1_CLICK, B1_DCLICK, MOTION,
	isPrintableKey)

_SHIFT_MAP = {
	KEY_SHIFT_LEFT:  KEY_LEFT,
	KEY_SHIFT_RIGHT: KEY_RIGHT,
	KEY_SHIFT_HOME:  KEY_HOME,
	KEY_SHIFT_END:   KEY_END,
}

_CTRL_A	= 1	# select all
_CTRL_E	= 5	# end of line
_CTRL_K	= 11	# kill to end of line
_CTRL_U	= 21	# kill to start of line
_CTRL_W	= 23	# delete previous word


class Entry(Widget):
	"""Single-line text entry widget.  Mirrors tkinter.Entry.

	state may be 'normal', 'readonly' (focusable, selectable, not
	editable) or 'disabled'.
	"""

	_fieldRole = 'entry'		# default colours: the 'entry' theme role

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'textvariable':		None,
			'show':			'',
			'justify':		'left',
			'selectbackground':	'',
			'selectforeground':	'',
			'exportselection':	True,
			'insertbackground':	'',
			'insertwidth':		1,
			'disabledforeground':	'',
			'readonlybackground':	'',
			'xscrollcommand':	None,
			'validate':		'none',
			'validatecommand':	None,
			'invalidcommand':	None,
		})
		kwargs.setdefault('relief', 'sunken')
		kwargs.setdefault('borderwidth', 1)
		kwargs.setdefault('width', 20)

		self._buf		= ''
		self._cur		= 0	# cursor column index
		self._scrollX		= 0	# horizontal scroll offset
		self._sel		= None	# None or (start, end) with start < end
		self._selAnchor		= None
		self._mouseDown		= False
		self._lastXScroll	= None
		self._scanX		= None	# scan_mark anchor (x, scrollX)

		if kwargs:
			Entry.configure(self, **kwargs)

	# ------------------------------------------------------------------
	# Buffer access (routes through textvariable when set)
	# ------------------------------------------------------------------

	def _getBuf(self) -> str:
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'get'):
			return str(tv.get())
		return self._buf

	def _setBuf(self, s: str):
		tv = self._opts.get('textvariable')
		if tv is not None and hasattr(tv, 'set'):
			tv.set(s)
		else:
			self._buf = s
		self._markDirty()

	def _editable(self) -> bool:
		return self._opts.get('state', 'normal') == 'normal'

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def get(self) -> str:
		"""Return current entry contents."""
		return self._getBuf()

	def insert(self, index: object, string):
		"""Insert *string* at position *index* ('end' or int)."""
		if not self._editable():
			return
		s   = str(string)
		buf = self._getBuf()
		pos = max(0, min(self._resolveIdx(index, buf), len(buf)))
		if not self._change(buf[:pos] + s + buf[pos:], 1, pos, s):
			return
		if self._cur >= pos:
			self._cur += len(s)
		self._clampCur()
		self._scrollToCursor()

	def delete(self, first: object, last: object = None):
		"""Delete characters from *first* to *last* (exclusive)."""
		if not self._editable():
			return
		buf  = self._getBuf()
		pos1 = self._resolveIdx(first, buf)
		pos2 = pos1 + 1 if last is None else self._resolveIdx(last, buf)
		pos1 = max(0, min(pos1, len(buf)))
		pos2 = max(0, min(pos2, len(buf)))
		if pos1 > pos2:
			pos1, pos2 = pos2, pos1
		if pos1 == pos2 or not self._change(buf[:pos1] + buf[pos2:], 0, pos1, buf[pos1:pos2]):
			return
		if self._cur > pos2:
			self._cur -= pos2 - pos1
		elif self._cur > pos1:
			self._cur = pos1
		self._sel = None
		self._clampCur()
		self._scrollToCursor()

	def icursor(self, index: object):
		"""Set insertion cursor to *index*."""
		self._cur = self._resolveIdx(index, self._getBuf())
		self._clampCur()
		self._scrollToCursor()
		self._markDirty()

	def index(self, index: object) -> int:
		"""Return integer index for *index*."""
		buf = self._getBuf()
		return max(0, min(self._resolveIdx(index, buf), len(buf)))

	def bbox(self, index):
		"""Bounding box (x, y, width, height) of the character at *index*
		relative to the widget, like Tk."""
		buf	= self._getBuf()
		pos	= max(0, min(self._resolveIdx(index, buf), len(buf)))
		bd	= self._border()
		col	= max(0, pos - self._scrollX)
		row	= (self._height - 2*bd - 1) // 2
		width	= 1 if pos < len(buf) else 0
		return _pxBox((bd + col, bd + max(0, row), width, 1))

	def selectionRange(self, start, end):
		"""Select from *start* to *end*."""
		buf = self._getBuf()
		s   = max(0, min(self._resolveIdx(start, buf), len(buf)))
		e   = max(0, min(self._resolveIdx(end, buf), len(buf)))
		if s > e:
			s, e = e, s
		self._sel       = (s, e) if s != e else None
		self._selAnchor = s
		self._markDirty()

	def selectionClear(self):
		"""Clear selection."""
		self._sel = None
		self._markDirty()

	def selectionPresent(self) -> bool:
		"""Return True if any text is selected."""
		return self._sel is not None

	def selectionFrom(self, index):
		"""Set selection anchor to *index*."""
		self._selAnchor = self._resolveIdx(index, self._getBuf())

	def selectionTo(self, index):
		"""Extend selection to *index* from current anchor."""
		b = self._resolveIdx(index, self._getBuf())
		if self._selAnchor is None:
			self._selAnchor = b
		a = self._selAnchor
		self._sel = (min(a, b), max(a, b)) if a != b else None
		self._markDirty()

	def selectionAdjust(self, index):
		"""Extend the selection end nearest to *index* (Tk select adjust)."""
		b = self._resolveIdx(index, self._getBuf())
		if self._sel is not None:
			s, e = self._sel
			self._selAnchor = e if abs(b - s) < abs(b - e) else s
		self.selectionTo(b)

	def selectionGet(self, **kw) -> str:
		"""Selected text; selection='CLIPBOARD' reads the clipboard."""
		if kw.get('selection') == 'CLIPBOARD':
			return Widget.selection_get(self, **kw)
		if self._sel is None:
			return ''
		return self._getBuf()[self._sel[0]:self._sel[1]]

	selection_range		= selectionRange
	select_range		= selectionRange
	selection_clear		= selectionClear
	select_clear		= selectionClear
	selection_present	= selectionPresent
	select_present		= selectionPresent
	selection_from		= selectionFrom
	select_from		= selectionFrom
	selection_to		= selectionTo
	select_to		= selectionTo
	selection_adjust	= selectionAdjust
	select_adjust		= selectionAdjust
	selection_get		= selectionGet

	def xview(self, *args):
		"""Query or change the horizontal view."""
		buf  = self._getBuf()
		total = max(1, len(buf))
		if not args:
			visW = self._visW()
			return (self._scrollX / total, min(1.0, (self._scrollX + visW) / total))
		if args[0] == 'moveto':
			self._scrollX = int(float(args[1]) * total)
		elif args[0] == 'scroll':
			n = int(args[1])
			if len(args) > 2 and args[2] == 'pages':
				n *= self._visW()
			self._scrollX += n
		else:
			self._scrollX = self._resolveIdx(args[0], buf)
		self._scrollX = max(0, min(self._scrollX, len(buf)))
		self._markDirty()
		return None

	def xview_moveto(self, fraction):
		Entry.xview(self, 'moveto', fraction)

	def xview_scroll(self, number, what):
		Entry.xview(self, 'scroll', number, what)

	def scan_mark(self, x):
		"""Anchor for scan_dragto at the pixel position *x*."""
		self._scanX = (_cellX(x), self._scrollX)

	def scan_dragto(self, x):
		"""Scroll by 10 times the distance from the scan_mark position."""
		if self._scanX is None:
			return
		x0, scroll = self._scanX
		buf = self._getBuf()
		self._scrollX = max(0, min(scroll - 10 * (_cellX(x) - x0), len(buf)))
		self._markDirty()

	# ------------------------------------------------------------------
	# Validation (validate, validatecommand, invalidcommand)
	# ------------------------------------------------------------------

	def _change(self, newBuf: str, action: int, pos: int, text: str) -> bool:
		"""Set the buffer to *newBuf* after the 'key' validation of the
		edit; return False when the validation rejected it."""
		if self._opts.get('validate') in ('key', 'all'):
			if not self._validate('key', action, pos, text, newBuf):
				return False
		self._setBuf(newBuf)
		return True

	def _focusChanged(self, gained):
		mode = self._opts.get('validate')
		why  = 'focusin' if gained else 'focusout'
		if mode in ('focus', 'all', why):
			buf = self._getBuf()
			self._validate(why, -1, -1, '', buf)

	def _substitute(self, arg, why, action, pos, text, newBuf):
		subst = {
			'%d': str(action),
			'%i': str(pos),
			'%P': newBuf,
			'%s': self._getBuf(),
			'%S': text,
			'%v': str(self._opts.get('validate')),
			'%V': why,
			'%W': str(self),
			'%%': '%',
		}
		return subst.get(arg, arg)

	def _runCommand(self, cmd, why, action, pos, text, newBuf):
		"""Run a validate/invalid command: a callable, a registered command
		name or a tuple/string of the name followed by %-substitutions."""
		if callable(cmd):
			return _callback(self, cmd)
		words = list(cmd) if isinstance(cmd, (tuple, list)) else list(_splitlist(cmd))
		if not words:
			return True
		func = words[0]
		args = [self._substitute(str(a), why, action, pos, text, newBuf) for a in words[1:]]
		if callable(func):
			return _callback(self, func, *args)
		return self.tk.call(str(func), *args)

	def _validate(self, why, action, pos, text, newBuf) -> bool:
		"""Tk validation: run validatecommand, invalidcommand when it fails.
		An error or a non boolean result switches validation off."""
		cmd = self._opts.get('validatecommand')
		if not cmd:
			return True
		try:
			result = self._runCommand(cmd, why, action, pos, text, newBuf)
			ok     = self.tk.getboolean(result if isinstance(result, str) else bool(result))
		except Exception:
			self._opts['validate'] = 'none'
			return True
		if not ok:
			inv = self._opts.get('invalidcommand')
			if inv:
				self._runCommand(inv, why, action, pos, text, newBuf)
		return ok

	# ------------------------------------------------------------------
	# Preferred size / cursor position
	# ------------------------------------------------------------------

	def _preferredSize(self):
		bd = self._cfgBorder()
		ow = _int(self._opts.get('width'), 20) or 20
		return (ow + 2*bd, 1 + 2*bd)

	def _visW(self) -> int:
		return max(1, self._width - 2*self._border())

	def _showsFocus(self) -> bool: return self._cursorPos() is not None

	def _cursorPos(self):
		"""Return screen (y, x) for the cursor block."""
		if self._opts.get('state') != 'normal':
			return None
		self._clampCur()
		bd = self._border()
		return (self._y + bd + (self._height - 2*bd - 1) // 2,
			self._x + bd + self._cur - self._scrollX)

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _resolveIdx(self, idx, buf: str) -> int:
		if isinstance(idx, int):
			return idx
		s = str(idx)
		if s in ('end', 'END'):
			return len(buf)
		if s == 'insert':
			return self._cur
		if s == 'anchor':
			return self._selAnchor or 0
		if s == 'sel.first':
			if not self._sel:
				raise TclError('selection isn\'t in widget')
			return self._sel[0]
		if s == 'sel.last':
			if not self._sel:
				raise TclError('selection isn\'t in widget')
			return self._sel[1]
		if s.startswith('@'):
			bd = self._border()
			return self._scrollX + _cellX(_int(s[1:])) - bd
		try:
			return int(s)
		except ValueError:
			return 0

	def _clampCur(self):
		self._cur = max(0, min(self._cur, len(self._getBuf())))

	def _scrollToCursor(self):
		if self._width <= 0:
			return
		visW = self._visW()
		if self._cur < self._scrollX:
			self._scrollX = self._cur
		elif self._cur >= self._scrollX + visW:
			self._scrollX = self._cur - visW + 1
		self._scrollX = max(0, self._scrollX)

	def _deleteSelection(self) -> bool:
		"""Delete selected text; return True if anything was deleted."""
		if self._sel is None:
			return False
		s, e = self._sel
		buf  = self._getBuf()
		if not self._change(buf[:s] + buf[e:], 0, s, buf[s:e]):
			return False
		self._cur       = s
		self._sel       = None
		self._selAnchor = None
		return True

	# Tk's Entry class bindings of the movement virtual events
	_VIRTUAL_KEYS = {
		'<<PrevChar>>':		KEY_LEFT,
		'<<NextChar>>':		KEY_RIGHT,
		'<<LineStart>>':	KEY_HOME,
		'<<LineEnd>>':		KEY_END,
		'<<SelectPrevChar>>':	KEY_SHIFT_LEFT,
		'<<SelectNextChar>>':	KEY_SHIFT_RIGHT,
		'<<SelectLineStart>>':	KEY_SHIFT_HOME,
		'<<SelectLineEnd>>':	KEY_SHIFT_END,
	}

	def _handleVirtual(self, sequence):
		"""Tk Entry class bindings of the movement, clipboard, selection
		and traversal events; like Tk a -show (password) entry does not copy"""
		key = self._VIRTUAL_KEYS.get(sequence)
		if key is not None:
			return Entry._handleKey(self, key)
		state    = self._opts.get('state', 'normal')
		editable = state == 'normal'
		if sequence == '<<TraverseIn>>':
			buf             = self._getBuf()
			self._selAnchor = 0
			self._sel       = (0, len(buf)) if buf else None
			self._cur       = len(buf)
		elif sequence in ('<<Copy>>', '<<Cut>>'):
			if self._sel is None or self._opts.get('show'):
				return False
			self.clipboard_clear()
			self.clipboard_append(self.selectionGet())
			if sequence == '<<Cut>>' and editable:
				self._deleteSelection()
		elif sequence == '<<Paste>>':
			if not editable:
				return False
			try:
				text = self.clipboard_get()
			except TclError:
				return False
			self._deleteSelection()
			self.insert(self._cur, text)
		elif sequence == '<<SelectAll>>':
			if state == 'disabled':
				return False
			buf             = self._getBuf()
			self._selAnchor = 0
			self._sel       = (0, len(buf)) if buf else None
		elif sequence == '<<SelectNone>>':
			self._sel = None
		elif sequence == '<<Clear>>':
			if not editable or not self._deleteSelection():
				return False
		else:
			return False
		self._scrollToCursor()
		self._markDirty()
		return True

	def _preRender(self):
		self._clampCur()
		buf = self._getBuf()
		if self._sel is not None:
			s, e = self._sel
			e = min(e, len(buf))
			self._sel = (s, e) if s < e else None
		self._scrollToCursor()
		cmd = self._opts.get('xscrollcommand')
		if callable(cmd):
			first, last = Entry.xview(self)
			if self._lastXScroll != (first, last):
				self._lastXScroll = (first, last)
				cmd(first, last)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def render(self, scr):
		if not self._isMapped():
			return

		state  = self._opts.get('state', 'normal')
		bd     = self._border()
		relief = self._opts.get('relief', 'sunken')

		if state == 'disabled':
			attr = self._disabledAttr()
		elif state == 'readonly' and self._opts.get('readonlybackground'):
			attr = self._getAttr(bg=self._opts.get('readonlybackground'))
		else:
			attr = self._getAttr()

		_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._height, self._width, relief,
				self._borderAttr(attr))

		visW = self._visW()
		buf  = self._getBuf()
		show = self._opts.get('show') or ''
		disp = show[0] * len(buf) if show else buf

		screenY = self._y + bd + (self._height - 2*bd - 1) // 2
		screenX = self._x + bd

		selAttr = self._selectAttr()

		vis = disp[self._scrollX:self._scrollX + visW].ljust(visW)
		if self._sel is None:
			_addStr(scr, screenY, screenX, vis, attr)
			return
		s = max(0, self._sel[0] - self._scrollX)
		e = max(0, min(visW, self._sel[1] - self._scrollX))
		_addStr(scr, screenY, screenX, vis[:s], attr)
		_addStr(scr, screenY, screenX + s, vis[s:e], selAttr)
		_addStr(scr, screenY, screenX + e, vis[e:], attr)

	# ------------------------------------------------------------------
	# Focus
	# ------------------------------------------------------------------

	def _isFocusable(self) -> bool:
		tf = self._opts.get('takefocus', True)
		return (tf not in (False, 0, '0', '') and
			self._opts.get('state', 'normal') in ('normal', 'readonly'))

	# ------------------------------------------------------------------
	# Keyboard input
	# ------------------------------------------------------------------

	def _handleKey(self, key: int) -> bool:
		state = self._opts.get('state', 'normal')
		if state == 'disabled':
			return False
		editable = state == 'normal'

		buf = self._getBuf()
		self._clampCur()
		c   = self._cur

		if key == _CTRL_A:
			self._selAnchor = 0
			self._sel       = (0, len(buf)) if buf else None
			self._markDirty()
			return True

		# Shift+movement — extend selection
		extendSel = key in _SHIFT_MAP
		if extendSel:
			if self._sel is None or self._selAnchor is None:
				self._selAnchor = c
			key = _SHIFT_MAP[key]

		if key == _CTRL_E:
			key = KEY_END

		if key == KEY_LEFT:
			if not extendSel and self._sel:
				c = self._sel[0]	# collapse to start
			elif c > 0:
				c -= 1
		elif key == KEY_RIGHT:
			if not extendSel and self._sel:
				c = self._sel[1]	# collapse to end
			elif c < len(buf):
				c += 1
		elif key == KEY_HOME:
			c = 0
		elif key == KEY_END:
			c = len(buf)
		elif not editable:
			return False
		elif key == KEY_BACKSPACE:
			if self._sel is not None:
				if self._deleteSelection():
					c = self._cur
			elif c > 0 and self._change(buf[:c-1] + buf[c:], 0, c-1, buf[c-1]):
				c -= 1
		elif key == KEY_DC:
			if self._sel is not None:
				if self._deleteSelection():
					c = self._cur
			elif c < len(buf):
				self._change(buf[:c] + buf[c+1:], 0, c, buf[c])
		elif key == _CTRL_K:
			if c < len(buf):
				self._change(buf[:c], 0, c, buf[c:])
		elif key == _CTRL_U:
			if c > 0 and self._change(buf[c:], 0, 0, buf[:c]):
				c = 0
		elif key == _CTRL_W:
			i = c
			while i > 0 and buf[i-1] == ' ':
				i -= 1
			while i > 0 and buf[i-1] != ' ':
				i -= 1
			if i < c and self._change(buf[:i] + buf[c:], 0, i, buf[i:c]):
				c = i
		elif isPrintableKey(key):
			if self._sel is not None and not self._deleteSelection():
				return True
			buf = self._getBuf()
			c   = self._cur
			if self._change(buf[:c] + chr(key) + buf[c:], 1, c, chr(key)):
				c += 1
		else:
			return False

		# Update selection
		if extendSel:
			a = self._selAnchor
			self._sel = (min(a, c), max(a, c)) if a != c else None
		elif key in (KEY_LEFT, KEY_RIGHT, KEY_HOME, KEY_END):
			self._sel       = None
			self._selAnchor = None

		self._cur = c
		self._clampCur()
		self._scrollToCursor()
		self._markDirty()
		return True

	# ------------------------------------------------------------------
	# Mouse input
	# ------------------------------------------------------------------

	def _dragLost(self):
		self._mouseDown = False

	def _handleMouse(self, mx: int, my: int, bstate: int) -> bool:
		bd      = self._border()
		release = bool(bstate & (B1_RELEASE | B1_CLICK))
		press   = bool(bstate & B1_PRESS) and not (bstate & MOTION)
		motion  = bool(bstate & MOTION) or (bool(bstate & B1_PRESS) and self._mouseDown)

		if not (press or release or motion or bstate & B1_DCLICK):
			return False

		buf = self._getBuf()
		mx  = max(self._x + bd, min(mx, self._x + self._width - bd - 1))
		col = max(0, min(self._scrollX + (mx - self._x - bd), len(buf)))

		if bstate & B1_DCLICK:
			# select the word under the pointer
			s = e = min(col, len(buf))
			while s > 0 and not buf[s-1].isspace():
				s -= 1
			while e < len(buf) and not buf[e].isspace():
				e += 1
			self._sel       = (s, e) if s < e else None
			self._selAnchor = s
			self._cur       = e
			self._mouseDown = False
		elif (press or bstate & B1_CLICK) and not self._mouseDown:
			self._mouseDown = not (bstate & B1_CLICK)
			self._sel       = None
			self._selAnchor = col
			self._cur       = col
		elif self._mouseDown:
			a = self._selAnchor if self._selAnchor is not None else col
			self._sel = (min(a, col), max(a, col)) if a != col else None
			self._cur = col
			if release:
				self._mouseDown = False

		self._clampCur()
		self._scrollToCursor()
		self._markDirty()
		return True
