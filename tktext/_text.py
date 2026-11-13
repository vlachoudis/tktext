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

import re
import bisect
import curses

from ._core import TclError, Widget, _addStr, _fillRect, _drawBorder, _int, \
	_newMouseEvent, _mouseEventNames, _cellX, _cellY, _pxBox
from . import _core, _colors
from ._listbox import _ScrollMixin
from ._events import (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_PPAGE, KEY_NPAGE, KEY_BACKSPACE, KEY_DC, KEY_ENTER,
	KEY_SHIFT_UP, KEY_SHIFT_DOWN, KEY_SHIFT_LEFT, KEY_SHIFT_RIGHT,
	KEY_SHIFT_HOME, KEY_SHIFT_END, KEY_SHIFT_PPAGE, KEY_SHIFT_NPAGE,
	B1_PRESS, B1_RELEASE, B1_CLICK, B1_DCLICK, MOTION, isWheel,
	isPrintableKey)

# Shift+key → plain movement key mapping
# Name of the selection anchor mark returned by ::tk::TextAnchor (text.tcl);
# setting/unsetting it moves the anchor used by Shift-selection.
ANCHOR_MARK = 'tk::anchor1'

# Tk text tag options (reported by tag_configure(tag) like tkinter)
_TAG_OPTIONS = ('background', 'bgstipple', 'borderwidth', 'elide',
	'fgstipple', 'font', 'foreground', 'justify', 'lmargin1', 'lmargin2',
	'lmargincolor', 'offset', 'overstrike', 'overstrikefg', 'relief',
	'rmargin', 'rmargincolor', 'selectbackground', 'selectforeground',
	'spacing1', 'spacing2', 'spacing3', 'tabs', 'tabstyle', 'underline',
	'underlinefg', 'wrap')

_SHIFT_MAP = {
	KEY_SHIFT_UP:    KEY_UP,
	KEY_SHIFT_DOWN:  KEY_DOWN,
	KEY_SHIFT_LEFT:  KEY_LEFT,
	KEY_SHIFT_RIGHT: KEY_RIGHT,
	KEY_SHIFT_HOME:  KEY_HOME,
	KEY_SHIFT_END:   KEY_END,
	KEY_SHIFT_PPAGE: KEY_PPAGE,
	KEY_SHIFT_NPAGE: KEY_NPAGE,
}

_MOVEMENT_KEYS = frozenset({
	KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_PPAGE, KEY_NPAGE,
})

_CTRL_A	= 1	# select all
_CTRL_E	= 5	# end of line
_CTRL_K	= 11	# delete to end of line

_RE_LINECOL	= re.compile(r'(\d+)\.(\d+|end)')
_RE_AT		= re.compile(r'@(-?\d+),(-?\d+)')
_RE_NAME	= re.compile(r'[^\s+\-]+')
_RE_COUNT	= re.compile(r'\s*([+-])\s*(-?\d+)\s*([a-z]+)')
_RE_WORD	= re.compile(r'\s*(linestart|lineend|wordstart|wordend)\b')


# Tag ranges: per tag a sorted list of disjoint (start, end) positions, so
# both the starts and the ends are sorted and can be searched with bisect
def _rangeStart(rng):
	return rng[0]

def _rangeEnd(rng):
	return rng[1]

def _segRow(seg):
	return seg[0]

def _isWordChar(ch) -> bool:
	return ch.isalnum() or ch == '_'
from ._core import _initArgs


class Text(_ScrollMixin, Widget):
	"""Multi-line text editor widget.  Mirrors tkinter.Text.

	Indices follow Tk syntax: "line.col" (line 1-based, col 0-based),
	"end", "insert", "current", mark names, "sel.first"/"sel.last",
	"tag.first"/"tag.last", "@x,y" and modifiers such as "+3c", "-1l",
	"linestart", "lineend", "wordstart", "wordend" (e.g. "end-1c").

	Positions are stored as (row, col) tuples, 0-based.  The position
	after the implicit final newline ("end") is (len(lines), 0).
	"""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts.update({
			'wrap':			'char',
			'undo':			False,
			'autoseparators':	True,
			'maxundo':		-1,
			'insertbackground':	'',
			'insertwidth':		1,
			'selectbackground':	'',
			'selectforeground':	'',
			'inactiveselectbackground': '',
			'exportselection':	True,
			'spacing1':		0,
			'spacing2':		0,
			'spacing3':		0,
			'tabs':			(),
			'tabstyle':		'tabular',
			'yscrollcommand':	None,
			'xscrollcommand':	None,
		})
		kwargs.setdefault('relief', 'sunken')
		kwargs.setdefault('borderwidth', 1)
		kwargs.setdefault('width', 40)
		kwargs.setdefault('height', 10)

		# Buffer: list of str (one per logical line, no newlines)
		self._buf	= ['']
		# Marks: name -> (row, col); gravity: name -> 'left'|'right'
		self._marks	= {'insert': (0, 0), 'current': (0, 0)}
		self._gravity	= {'insert': 'right', 'current': 'right'}
		# Viewport: first display line / first column (wrap=none)
		self._scrollY	= 0
		self._scrollX	= 0
		self._selAnchor	= None
		self._mouseDown	= False
		self._wantCol	= None		# column kept while moving up/down
		self._sbDrag	= None
		# Tags: name -> options dict / list of (start, end) ranges
		self._tagCfg	= {'sel': {}}
		self._tagRanges	= {'sel': []}
		self._tagOrder	= ['sel']	# priority (last wins); 'sel' stays on top
		self._tagBinds	= {}		# tag -> {sequence: [callable]}
		# Undo
		self._undoStack	= []
		self._redoStack	= []
		self._lastEdit	= None		# kind of the last edit (for grouping)
		self._modified	= False
		# Display-line cache: (width, wrap, version) -> segments
		self._dlCache	= {}
		self._version	= 0
		# bumped when a tag is created, configured, deleted, raised or
		# lowered: caches the tags using elide / lmargin (_specialTags)
		self._tagCfgVersion = 0
		# bumped when the ranges of an elide / lmargin tag change
		# without a text edit (tag_add, tag_remove …)
		self._tagRangeVersion = 0

		if kwargs:
			Text.configure(self, **kwargs)

	# ------------------------------------------------------------------
	# Convenience accessors
	# ------------------------------------------------------------------

	@property
	def _cur(self):
		return self._marks['insert']

	@_cur.setter
	def _cur(self, pos):
		self._marks['insert'] = self._clampPos(pos, allowEnd=False)

	@property
	def _sel(self):
		"""Selection as (r0, c0, r1, c1) or None."""
		ranges = self._tagRanges.get('sel') or []
		if not ranges:
			return None
		(r0, c0), (r1, c1) = ranges[0][0], ranges[-1][1]
		return (r0, c0, r1, c1)

	def _setSel(self, a, b):
		if a is None or b is None or a == b:
			self._tagRanges['sel'] = []
		else:
			a, b = sorted((self._clampPos(a, False), self._clampPos(b, False)))
			self._tagRanges['sel'] = [(a, b)] if a < b else []
		self._rangesChanged('sel')
		self._markDirty()

	def _endPos(self):
		return (len(self._buf), 0)

	def _lastPos(self):
		return (len(self._buf) - 1, len(self._buf[-1]))

	def _clampPos(self, pos, allowEnd=True):
		r, c = pos
		if r < 0:
			return (0, 0)
		if r >= len(self._buf):
			return self._endPos() if allowEnd else self._lastPos()
		return (r, max(0, min(c, len(self._buf[r]))))

	def _offset(self, pos) -> int:
		r, c = pos
		return sum(len(self._buf[i]) + 1 for i in range(min(r, len(self._buf)))) + c

	def _movePos(self, pos, n):
		"""Position *n* characters after (n < 0: before) *pos*; same
		result as _fromOffset(_offset(pos) + n) without walking the
		whole buffer."""
		buf  = self._buf
		r, c = pos
		if r >= len(buf):		# end: one char after the last one
			if n >= 0:
				return self._endPos()
			r, c = len(buf) - 1, len(buf[-1])
			n   += 1
		if n >= 0:
			while True:
				room = len(buf[r]) - c
				if n <= room:
					return (r, c + n)
				n -= room + 1
				r += 1
				c  = 0
				if r >= len(buf):
					return self._endPos()
		n = -n
		while n > c:
			n -= c + 1
			r -= 1
			if r < 0:
				return (0, 0)
			c = len(buf[r])
		return (r, c - n)

	def _fromOffset(self, off):
		if off <= 0:
			return (0, 0)
		for r, line in enumerate(self._buf):
			if off <= len(line):
				return (r, off)
			off -= len(line) + 1
		return self._endPos()

	# ------------------------------------------------------------------
	# Index parsing
	# ------------------------------------------------------------------

	def _parseIndex(self, idx):
		"""Convert any Tk index expression to (row, col).  May return
		the end position (len(lines), 0)."""
		if isinstance(idx, tuple):
			return self._clampPos(idx)
		if isinstance(idx, float):
			idx = repr(idx)
		s = str(idx).strip()
		pos, rest = self._parseBase(s)
		while rest.strip():
			m = _RE_COUNT.match(rest)
			if m:
				sign, num, unit = m.groups()
				n = int(num) * (-1 if sign == '-' else 1)
				if unit.startswith('l'):
					r = max(0, min(pos[0] + n, len(self._buf) - 1))
					c = pos[1] if pos[0] < len(self._buf) else 0
					pos = (r, min(c, len(self._buf[r])))
				else:		# chars / indices / display chars
					pos = self._movePos(pos, n)
				rest = rest[m.end():]
				continue
			m = _RE_WORD.match(rest)
			if m:
				pos  = self._applyWordMod(pos, m.group(1))
				rest = rest[m.end():]
				continue
			raise TclError(f'bad text index "{s}"')
		return pos

	def _parseBase(self, s):
		m = _RE_LINECOL.match(s)
		if m:
			r = int(m.group(1)) - 1
			if r >= len(self._buf):
				return self._endPos(), s[m.end():]
			r = max(0, r)
			c = len(self._buf[r]) if m.group(2) == 'end' else int(m.group(2))
			return self._clampPos((r, c)), s[m.end():]
		m = _RE_AT.match(s)
		if m:
			return self._posFromXY(_cellX(m.group(1)), _cellY(m.group(2))), s[m.end():]
		m = _RE_NAME.match(s)
		if not m:
			raise TclError(f'bad text index "{s}"')
		name = m.group(0)
		rest = s[m.end():]
		if name == 'end':
			return self._endPos(), rest
		if name in self._marks:
			return self._clampPos(self._marks[name]), rest
		if '.' in name:
			tag, which = name.rsplit('.', 1)
			ranges = self._tagRanges.get(tag) or []
			if which in ('first', 'last'):
				if not ranges:
					raise TclError(f'text doesn\'t contain any characters tagged with "{tag}"')
				return (ranges[0][0] if which == 'first' else ranges[-1][1]), rest
		raise TclError(f'bad text index "{s}"')

	def _applyWordMod(self, pos, mod):
		r, c = self._clampPos(pos, allowEnd=False)
		line = self._buf[r]
		if mod == 'linestart':
			return (r, 0)
		if mod == 'lineend':
			return (r, len(line))
		if mod == 'wordstart':
			if c < len(line) and not _isWordChar(line[c]):
				return (r, c)
			while c > 0 and _isWordChar(line[c-1]):
				c -= 1
			return (r, c)
		# wordend
		if c < len(line) and not _isWordChar(line[c]):
			return (r, c + 1)
		while c < len(line) and _isWordChar(line[c]):
			c += 1
		return (r, c)

	def _toTkIndex(self, row, col=None):
		if col is None:
			row, col = row
		return f'{row + 1}.{col}'

	# ------------------------------------------------------------------
	# Low level edit primitives (keep marks and tags consistent)
	# ------------------------------------------------------------------

	def _adjustInsert(self, pos, text):
		lines	= text.split('\n')
		nLines	= len(lines) - 1
		lastLen	= len(lines[-1])
		pr, pc	= pos

		def adjust(q, right):
			if q < pos or (q == pos and not right):
				return q
			qr, qc = q
			if qr == pr:
				if nLines == 0:
					return (qr, qc + lastLen)
				return (qr + nLines, lastLen + (qc - pc))
			return (qr + nLines, qc)

		for name in self._marks:
			self._marks[name] = adjust(self._marks[name],
				self._gravity.get(name, 'right') == 'right')
		# ranges are sorted and disjoint: the ones ending at or before
		# pos are not affected (appending text costs nothing)
		for ranges in self._tagRanges.values():
			i = bisect.bisect_right(ranges, pos, key=_rangeEnd)
			n = len(ranges)
			if i == n:
				continue
			if nLines == 0:
				# typing inside a line: only positions on row pr move,
				# the ranges starting on a later row stay as they are
				j = i
				while j < n and ranges[j][0][0] <= pr:
					j += 1
			else:
				j = n
			# text inserted at the start or the end is untagged
			ranges[i:j] = [(adjust(a, True), adjust(b, False))
					for a, b in ranges[i:j]]

	def _adjustDelete(self, a, b):
		ar, ac = a
		br, bc = b

		def adjust(q):
			if q <= a:
				return q
			if q <= b:
				return a
			qr, qc = q
			if qr == br:
				return (ar, ac + (qc - bc))
			return (qr - (br - ar), qc)

		for name in self._marks:
			self._marks[name] = adjust(self._marks[name])
		for ranges in self._tagRanges.values():
			i = bisect.bisect_right(ranges, a, key=_rangeEnd)
			if i == len(ranges):
				continue
			# start one before: ranges brought together are merged
			i = max(0, i - 1)
			n = len(ranges)
			if ar == br:
				# deleting inside a line: the ranges starting on a
				# later row are not affected (nor merged)
				j = i
				while j < n and ranges[j][0][0] <= ar:
					j += 1
			else:
				j = n
			newRanges = []
			for s, e in ranges[i:j]:
				s, e = adjust(s), adjust(e)
				if s >= e:
					continue
				if newRanges and s <= newRanges[-1][1]:
					newRanges[-1] = (newRanges[-1][0], e)
				else:
					newRanges.append((s, e))
			ranges[i:j] = newRanges

	def _rawInsert(self, pos, text):
		r, c   = pos
		self._adjustInsert(pos, text)
		lines  = text.split('\n')
		tail   = self._buf[r][c:]
		self._buf[r] = self._buf[r][:c] + lines[0]
		for i in range(1, len(lines)):
			self._buf.insert(r + i, lines[i])
		lastR  = r + len(lines) - 1
		lastC  = len(self._buf[lastR])
		self._buf[lastR] += tail
		self._changed(r if lastR == r else None)
		return (lastR, lastC)

	def _rawDelete(self, a, b):
		if a >= b:
			return
		self._adjustDelete(a, b)
		(ar, ac), (br, bc) = a, b
		self._buf[ar:br + 1] = [self._buf[ar][:ac] + self._buf[br][bc:]]
		if not self._buf:
			self._buf = ['']
		self._changed(ar if ar == br else None)

	def _changed(self, row=None):
		"""The text changed; *row* = the only row edited (no line was
		added or removed): the cached display lines are then patched
		instead of being recomputed for the whole text."""
		old    = self._version
		cache  = self._dlCache
		self._version += 1
		self._dlCache  = {}
		if row is not None:
			self._patchCaches(old, row, cache)
		if not self._modified:
			self._modified = True
			self._fireVirtual('<<Modified>>')
		self._markDirty()

	# ------------------------------------------------------------------
	# Undo
	# ------------------------------------------------------------------

	def _snapshot(self):
		return (list(self._buf), dict(self._marks),
			{k: list(v) for k, v in self._tagRanges.items()})

	def _restore(self, snap):
		buf, marks, tags = snap
		self._buf	= list(buf)
		self._marks	= dict(marks)
		self._tagRanges	= {k: list(v) for k, v in tags.items()}
		for name in self._tagOrder:
			self._tagRanges.setdefault(name, [])
		self._changed()
		self._scrollToCursor()

	def _beginEdit(self, kind=None):
		"""Record an undo point before an edit.  Consecutive edits of the
		same *kind* (typing) are grouped when autoseparators is on."""
		if not self._opts.get('undo'):
			return
		if kind is not None and kind == self._lastEdit and \
				self._opts.get('autoseparators', True):
			return
		self._undoStack.append(self._snapshot())
		maxUndo = _int(self._opts.get('maxundo'), -1)
		if maxUndo > 0 and len(self._undoStack) > maxUndo:
			del self._undoStack[0]
		self._redoStack.clear()
		self._lastEdit = kind

	def editUndo(self):
		if not self._undoStack:
			return False
		self._redoStack.append(self._snapshot())
		self._restore(self._undoStack.pop())
		self._lastEdit = None
		return True

	def editRedo(self):
		if not self._redoStack:
			return False
		self._undoStack.append(self._snapshot())
		self._restore(self._redoStack.pop())
		self._lastEdit = None
		return True

	def editSeparator(self):
		self._lastEdit = None

	def editReset(self):
		self._undoStack.clear()
		self._redoStack.clear()
		self._lastEdit = None

	def editModified(self, flag=None):
		if flag is None:
			return self._modified
		self._modified = bool(flag)
		return None

	def edit(self, *args):
		if not args:
			return None
		cmd = args[0]
		if cmd == 'undo':
			return self.editUndo()
		if cmd == 'redo':
			return self.editRedo()
		if cmd == 'separator':
			return self.editSeparator()
		if cmd == 'reset':
			return self.editReset()
		if cmd == 'modified':
			return self.editModified(*args[1:])
		return None

	edit_undo	= editUndo
	edit_redo	= editRedo
	edit_separator	= editSeparator
	edit_reset	= editReset
	edit_modified	= editModified

	# ------------------------------------------------------------------
	# Public API — content
	# ------------------------------------------------------------------

	def insert(self, idx, chars, *tags):
		"""Insert *chars* at *idx*; extra args are (tags, chars, tags…)."""
		if self._opts.get('state') == 'disabled':
			return
		pos = self._parseIndex(idx)
		if pos == self._endPos():
			pos = self._lastPos()		# never after the final newline
		self._beginEdit()
		args = [chars] + list(tags)
		for i in range(0, len(args), 2):
			text  = str(args[i])
			tagls = args[i + 1] if i + 1 < len(args) else ()
			if isinstance(tagls, str):
				tagls = tagls.split()
			start = pos
			pos   = self._rawInsert(pos, text)
			for t in tagls:
				self._addTagRange(t, start, pos)
		self._lastEdit = None
		# like Tk the view does not follow programmatic edits (scrolling
		# here relaid the whole text out at every insert); keyboard
		# editing scrolls in _handleKey, applications call see()

	def delete(self, idx1, idx2=None):
		"""Delete text between *idx1* and *idx2* (or one char at *idx1*)."""
		if self._opts.get('state') == 'disabled':
			return
		a = self._parseIndex(idx1)
		b = self._parseIndex(idx2) if idx2 is not None else \
			self._movePos(a, 1)
		a = min(a, self._lastPos())
		b = min(b, self._lastPos())
		if a > b:
			return
		self._beginEdit()
		self._rawDelete(a, b)
		self._lastEdit = None

	def replace(self, idx1, idx2, chars, *tags):
		if self._opts.get('state') == 'disabled':
			return
		a = self._toTkIndex(min(self._parseIndex(idx1), self._lastPos()))
		self.delete(idx1, idx2)
		self.insert(a, chars, *tags)

	def get(self, idx1, idx2=None):
		"""Return text between *idx1* and *idx2*."""
		a = self._parseIndex(idx1)
		if idx2 is None:
			if a == self._endPos():
				return ''
			r, c = a
			return self._buf[r][c] if c < len(self._buf[r]) else '\n'
		b = self._parseIndex(idx2)
		if b <= a:
			return ''
		trailing = ''
		if b == self._endPos():
			b        = self._lastPos()
			trailing = '\n'
		(r1, c1), (r2, c2) = a, b
		if r1 == r2:
			return self._buf[r1][c1:c2] + trailing
		parts = [self._buf[r1][c1:]]
		parts.extend(self._buf[r1 + 1:r2])
		parts.append(self._buf[r2][:c2])
		return '\n'.join(parts) + trailing

	def dump(self, index1, index2=None, command=None, **kw):
		"""Return [(key, value, index), …] for the range like Tk's dump:
		keys 'text', 'mark', 'tagon', 'tagoff' (image/window: none).
		Options all/text/mark/tag select what is reported."""
		want = {k for k in ('text', 'mark', 'tag') if kw.get(k)}
		if kw.get('all') or not want:
			want = {'text', 'mark', 'tag'}
		a = self._parseIndex(index1)
		if index2 is None:
			b = self._movePos(a, 1)
		else:
			b = self._parseIndex(index2)
		result = []
		if b <= a:
			return result
		events = {}
		if 'tag' in want:
			for name in self._tagOrder:
				for start, end in self._tagRanges.get(name, []):
					if end <= a or start >= b:
						continue
					events.setdefault(max(start, a), []).append((2, 'tagon', name))
					if end < b:
						events.setdefault(end, []).append((0, 'tagoff', name))
		if 'mark' in want:
			for name, pos in self._marks.items():
				if a <= pos < b:
					events.setdefault(pos, []).append((1, 'mark', name))
		points = sorted(p for p in events if a <= p < b)
		cur = a
		for nxt in points + [b]:
			if nxt < cur:
				continue
			if 'text' in want and nxt > cur:
				r, c = cur
				for piece in self.get(self._toTkIndex(cur),
						self._toTkIndex(nxt)).splitlines(True):
					result.append(('text', piece, f'{r + 1}.{c}'))
					if piece.endswith('\n'):
						r, c = r + 1, 0
					else:
						c += len(piece)
			for _, key, value in sorted(events.get(nxt, ())):
				if nxt < b:
					result.append((key, value, self._toTkIndex(nxt)))
			cur = nxt
		# like Tk, the implicit final newline is a chunk of its own
		if result and b == self._parseIndex('end') and result[-1][0] == 'text' \
				and len(result[-1][1]) > 1 and result[-1][1].endswith('\n'):
			key, piece, idx = result.pop()
			r, c = (int(v) for v in idx.split('.'))
			result.append((key, piece[:-1], idx))
			result.append((key, '\n', f'{r}.{c + len(piece) - 1}'))
		if command is not None:
			for item in result:
				command(*item)
			return None
		return result

	def index(self, idx) -> str:
		"""Return the normalised "line.col" form of *idx*."""
		return self._toTkIndex(self._parseIndex(idx))

	def compare(self, idx1, op, idx2) -> bool:
		a = self._parseIndex(idx1)
		b = self._parseIndex(idx2)
		return {'<': a < b, '<=': a <= b, '==': a == b,
			'>=': a >= b, '>': a > b, '!=': a != b}[op]

	def count(self, idx1, idx2, *options):
		a = self._offset(self._parseIndex(idx1))
		b = self._offset(self._parseIndex(idx2))
		if 'lines' in options:
			return (self._parseIndex(idx2)[0] - self._parseIndex(idx1)[0],)
		return (b - a,)

	def search(self, pattern, index, stopindex=None, forwards=None,
			backwards=None, exact=None, regexp=None, nocase=None,
			count=None, elide=None):
		"""Search for *pattern*; return the index of the match or ''."""
		if not pattern:
			return ''
		flags = re.IGNORECASE if nocase else 0
		rx    = re.compile(pattern if regexp else re.escape(pattern), flags)
		text  = '\n'.join(self._buf)
		start = self._offset(self._parseIndex(index))
		stop  = self._offset(self._parseIndex(stopindex)) if stopindex else None
		m     = None
		if backwards:
			lo = stop if stop is not None else 0
			for cand in rx.finditer(text, lo, start):
				m = cand
			if m is None and stopindex is None:
				for cand in rx.finditer(text, start):
					m = cand
		else:
			m = rx.search(text, start, stop if stop is not None else len(text))
			if m is None and stopindex is None:
				m = rx.search(text, 0, start)
		if m is None:
			return ''
		if count is not None and hasattr(count, 'set'):
			count.set(m.end() - m.start())
		return self._toTkIndex(self._fromOffset(m.start()))

	def see(self, idx):
		"""Scroll so that *idx* is visible."""
		pos = self._clampPos(self._parseIndex(idx), allowEnd=False)
		self._scrollToPos(pos)
		self._markDirty()

	def bbox(self, idx):
		pos = self._clampPos(self._parseIndex(idx), allowEnd=False)
		sp  = self._screenPos(pos)
		if sp is None:
			return None
		y, x = sp
		return _pxBox((x - self._x, y - self._y, 1, 1))

	def dlineinfo(self, index):
		"""(x, y, width, height, baseline) of the display line of *index*."""
		pos = self._clampPos(self._parseIndex(index), allowEnd=False)
		sp  = self._screenPos(pos)
		if sp is None:
			return None
		y, _ = sp
		bd   = self._border()
		return _pxBox((bd, y - self._y, self._width - 2 * bd, 1)) + (_core.PY - 2,)

	def image_create(self, index, cnf={}, **kw):
		"""Embedded image: occupies one character (a glyph) like in Tk."""
		from ._image import IMAGE_GLYPH
		self.insert(index, IMAGE_GLYPH)
		Widget._funcSerial += 1
		return kw.get('name') or f'image{Widget._funcSerial}'

	def window_create(self, index, cnf={}, **kw):
		"""Embedded windows are not supported: a placeholder character
		keeps index arithmetic consistent."""
		self.insert(index, ' ')

	def image_cget(self, index, option):
		return ''

	def image_configure(self, index, cnf=None, **kw):
		return {}

	def image_names(self):
		return ()

	def window_names(self):
		return ()

	def scan_mark(self, x, y):
		pass

	def scan_dragto(self, x, y, gain=10):
		pass

	# ------------------------------------------------------------------
	# Marks
	# ------------------------------------------------------------------

	def markSet(self, name, idx):
		"""Set named mark to *idx*."""
		pos = self._parseIndex(idx)
		if name == 'insert':
			pos = self._clampPos(pos, allowEnd=False)
		self._marks[name] = pos
		self._gravity.setdefault(name, 'right')
		if name == 'insert':
			self._wantCol = None
		elif name == ANCHOR_MARK:
			self._selAnchor = pos
		self._markDirty()

	def markUnset(self, *names):
		for n in names:
			if n not in ('insert', 'current'):
				self._marks.pop(n, None)
				self._gravity.pop(n, None)
				if n == ANCHOR_MARK:
					self._selAnchor = None

	def markNames(self):
		return tuple(self._marks.keys())

	def markGravity(self, name, direction=None):
		if direction is None:
			return self._gravity.get(name, 'right')
		self._gravity[name] = direction

	mark_set	= markSet
	mark_unset	= markUnset
	mark_names	= markNames
	mark_gravity	= markGravity

	# ------------------------------------------------------------------
	# Tags
	# ------------------------------------------------------------------

	def _ensureTag(self, name):
		if name not in self._tagCfg:
			self._tagCfg[name]	= {}
			self._tagRanges[name]	= []
			# new tags get the highest priority below 'sel'
			self._tagOrder.insert(len(self._tagOrder) - 1, name)
			self._tagCfgVersion += 1

	def tagConfigure(self, name, cnf=None, **kwargs):
		"""Configure appearance of tag *name* (foreground, background,
		underline, font with 'bold'/'italic', reverse …)."""
		self._ensureTag(name)
		cfg = self._tagCfg[name]
		if isinstance(cnf, str):	# tag_configure(tag, 'option')
			opt = {'fg': 'foreground', 'bg': 'background'}.get(cnf, cnf)
			return (opt, '', '', '', cfg.get(opt, ''))
		if cnf:
			kwargs.update(cnf)
		if not kwargs:
			# like tkinter: {option: (name, dbName, dbClass, default, value)}
			return {opt: (opt, '', '', '', cfg.get(opt, ''))
				for opt in sorted(set(_TAG_OPTIONS) | set(cfg))}
		for k, v in kwargs.items():
			k = {'fg': 'foreground', 'bg': 'background'}.get(k, k)
			self._tagCfg[name][k] = v
		self._tagCfgVersion += 1
		self._markDirty()
		return None

	def tagCget(self, name, option):
		option = {'fg': 'foreground', 'bg': 'background'}.get(option, option)
		return self._tagCfg.get(name, {}).get(option, '')

	def _addTagRange(self, name, a, b):
		self._ensureTag(name)
		a = min(a, self._endPos())
		b = min(b, self._endPos())
		if a >= b:
			return
		ranges = self._tagRanges[name]
		# merge with every range overlapping or touching [a, b]
		lo = bisect.bisect_left(ranges, a, key=_rangeEnd)
		hi = bisect.bisect_right(ranges, b, key=_rangeStart)
		if lo < hi:
			a = min(a, ranges[lo][0])
			b = max(b, ranges[hi - 1][1])
		ranges[lo:hi] = [(a, b)]
		self._rangesChanged(name)

	def _rangesOnRow(self, name, r):
		"""Tag ranges of *name* that touch text row *r*."""
		ranges = self._tagRanges.get(name)
		if not ranges:
			return
		i = bisect.bisect_left(ranges, (r, 0), key=_rangeEnd)
		n = len(ranges)
		while i < n and ranges[i][0][0] <= r:
			yield ranges[i]
			i += 1

	def _tagCovers(self, name, pos) -> bool:
		"""True when tag *name* covers the character at *pos*."""
		ranges = self._tagRanges.get(name)
		if not ranges:
			return False
		i = bisect.bisect_right(ranges, pos, key=_rangeStart) - 1
		return i >= 0 and pos < ranges[i][1]

	def tagAdd(self, name, idx1, *more):
		"""Apply tag *name* to [idx1, idx2) (more pairs may follow)."""
		args = [idx1] + list(more)
		for i in range(0, len(args), 2):
			a = self._parseIndex(args[i])
			if i + 1 < len(args):
				b = self._parseIndex(args[i + 1])
			else:
				b = self._movePos(a, 1)
			if name == 'sel':
				a = min(a, self._lastPos())
				b = min(b, self._lastPos())
			self._addTagRange(name, a, b)
		self._markDirty()

	def tagRemove(self, name, idx1, idx2=None):
		"""Remove tag from the range [idx1, idx2)."""
		if name not in self._tagRanges:
			return
		a = self._parseIndex(idx1)
		b = self._parseIndex(idx2) if idx2 is not None else \
			self._movePos(a, 1)
		if a >= b:		# like Tk: nothing to remove
			return
		ranges = self._tagRanges[name]
		# only the ranges overlapping [a, b) change
		lo  = bisect.bisect_right(ranges, a, key=_rangeEnd)
		hi  = bisect.bisect_left(ranges, b, key=_rangeStart)
		out = []
		for s, e in ranges[lo:hi]:
			if s < a:
				out.append((s, a))
			if e > b:
				out.append((b, e))
		ranges[lo:hi] = out
		self._rangesChanged(name)
		self._markDirty()

	def tagDelete(self, *names):
		for n in names:
			if n == 'sel':
				self._tagRanges['sel'] = []
				self._rangesChanged('sel')
				continue
			self._tagCfg.pop(n, None)
			self._tagRanges.pop(n, None)
			self._tagBinds.pop(n, None)
			if n in self._tagOrder:
				self._tagOrder.remove(n)
		self._tagCfgVersion += 1
		self._markDirty()

	def tagRanges(self, name):
		result = []
		for a, b in self._tagRanges.get(name, []):
			result += [self._toTkIndex(a), self._toTkIndex(b)]
		return tuple(result)

	def tagNames(self, idx=None):
		if idx is None:
			return tuple(self._tagOrder)
		pos = self._parseIndex(idx)
		return tuple(n for n in self._tagOrder if self._tagCovers(n, pos))

	def tagNextrange(self, name, idx1, idx2=None):
		a = self._parseIndex(idx1)
		b = self._parseIndex(idx2) if idx2 is not None else self._endPos()
		ranges = self._tagRanges.get(name, [])
		i = bisect.bisect_left(ranges, a, key=_rangeStart)
		if i < len(ranges) and ranges[i][0] < b:
			s, e = ranges[i]
			return (self._toTkIndex(s), self._toTkIndex(e))
		return ()

	def tagPrevrange(self, name, idx1, idx2=None):
		a = self._parseIndex(idx1)
		b = self._parseIndex(idx2) if idx2 is not None else (0, 0)
		ranges = self._tagRanges.get(name, [])
		i = bisect.bisect_left(ranges, a, key=_rangeStart) - 1
		if i >= 0 and ranges[i][0] >= b:
			s, e = ranges[i]
			return (self._toTkIndex(s), self._toTkIndex(e))
		return ()

	def tagRaise(self, name, aboveThis=None):
		if name not in self._tagOrder or name == 'sel':
			return
		self._tagOrder.remove(name)
		if aboveThis in self._tagOrder:
			self._tagOrder.insert(self._tagOrder.index(aboveThis) + 1, name)
		else:
			self._tagOrder.insert(len(self._tagOrder) - 1, name)
		self._tagCfgVersion += 1
		self._markDirty()

	def tagLower(self, name, belowThis=None):
		if name not in self._tagOrder or name == 'sel':
			return
		self._tagOrder.remove(name)
		if belowThis in self._tagOrder:
			self._tagOrder.insert(self._tagOrder.index(belowThis), name)
		else:
			self._tagOrder.insert(0, name)
		self._tagCfgVersion += 1
		self._markDirty()

	def tagBind(self, name, sequence, func, add=None):
		self._ensureTag(name)
		binds = self._tagBinds.setdefault(name, {})
		if not add or sequence not in binds:
			binds[sequence] = []
		binds[sequence].append(func)
		return f'{name}{sequence}{id(func)}'

	def tagUnbind(self, name, sequence, funcid=None):
		self._tagBinds.get(name, {}).pop(sequence, None)

	tag_configure	= tagConfigure
	tag_config	= tagConfigure
	tag_cget	= tagCget
	tag_add		= tagAdd
	tag_remove	= tagRemove
	tag_delete	= tagDelete
	tag_ranges	= tagRanges
	tag_names	= tagNames
	tag_nextrange	= tagNextrange
	tag_prevrange	= tagPrevrange
	tag_raise	= tagRaise
	tag_lower	= tagLower
	tag_bind	= tagBind
	tag_unbind	= tagUnbind

	def selGet(self):
		"""Return selected text or ''."""
		s = self._sel
		if not s:
			return ''
		return self.get((s[0], s[1]), (s[2], s[3]))

	def selection_get(self, **kw):
		s = self.selGet()
		if not s:
			raise TclError('PRIMARY selection doesn\'t exist')
		return s

	# ------------------------------------------------------------------
	# Display lines (wrapping) and scrolling
	# ------------------------------------------------------------------

	def _wrapMode(self) -> str:
		w = str(self._opts.get('wrap') or 'none').lower()
		return w if w in ('char', 'word') else 'none'

	def _innerW(self) -> int:
		return max(1, self._width - 2*self._border())

	def _visRows(self) -> int:
		return max(1, self._height - 2*self._border())

	def _textW(self) -> int:
		"""Width available for text (excludes the internal scrollbar)."""
		w = self._innerW()
		if not callable(self._opts.get('yscrollcommand')) and w > 2:
			if len(self._displayLines(w)) > self._visRows():
				return w - 1
		return w

	# ------------------------------------------------------------------
	# Elided text (tag option elide=True): not displayed, skipped by the
	# cursor, but still part of the text and of index arithmetic.
	# ------------------------------------------------------------------

	_NO_ELIDE = (None, '', 0, False, '0', 'false', 'no')

	def _specialTags(self):
		"""([elide tag names], [(name, lmargin1, lmargin2)]) in priority
		order.  Cached: with many tags (one per line or card) scanning
		them all on every keystroke dominates the editing time."""
		if getattr(self, '_specialKey', None) == self._tagCfgVersion:
			return self._specialCache
		elide   = []
		margins = []
		for n in self._tagOrder:
			cfg = self._tagCfg.get(n)
			if not cfg:
				continue
			if cfg.get('elide') not in self._NO_ELIDE:
				elide.append(n)
			m1 = cfg.get('lmargin1')
			m2 = cfg.get('lmargin2')
			if m1 not in self._NO_ELIDE or m2 not in self._NO_ELIDE:
				margins.append((n, m1, m2))
		special = set(elide) | {n for n, _, _ in margins}
		self._specialKey   = self._tagCfgVersion
		self._specialCache = (elide, margins, special)
		return self._specialCache

	def _rangesChanged(self, name):
		"""The ranges of tag *name* changed without a text edit."""
		if name in self._specialTags()[2]:
			self._tagRangeVersion += 1

	def _elideKey(self):
		names = self._specialTags()[0]
		if not names:
			return None
		return (tuple(names), self._tagRangeVersion)

	def _elideRow(self, r, names):
		"""Merged elided column ranges [(lo, hi), …] of row *r*."""
		lst  = []
		line = len(self._buf[r])
		for n in names:
			for a, b in self._rangesOnRow(n, r):
				lo = a[1] if a[0] == r else 0
				hi = b[1] if b[0] == r else line + 1
				if hi > lo:
					lst.append((lo, hi))
		if not lst:
			return lst
		lst.sort()
		merged = [lst[0]]
		for lo, hi in lst[1:]:
			if lo <= merged[-1][1]:
				merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
			else:
				merged.append((lo, hi))
		return merged

	def _elideMap(self):
		"""{row: [(lo, hi), …]} merged elided column ranges; column
		len(line) stands for the newline of the row."""
		key = self._elideKey()
		if key is None:
			return {}
		if getattr(self, '_elideCacheKey', None) == (self._version, key):
			return self._elideCache
		rows = {}
		nbuf = len(self._buf)
		for n in key[0]:
			for a, b in self._tagRanges.get(n, ()):
				for r in range(a[0], min(b[0], nbuf - 1) + 1):
					lo = a[1] if r == a[0] else 0
					hi = b[1] if r == b[0] else len(self._buf[r]) + 1
					if hi > lo:
						rows.setdefault(r, []).append((lo, hi))
		for r, lst in rows.items():
			lst.sort()
			merged = [lst[0]]
			for lo, hi in lst[1:]:
				if lo <= merged[-1][1]:
					merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
				else:
					merged.append((lo, hi))
			rows[r] = merged
		self._elideCacheKey = (self._version, key)
		self._elideCache    = rows
		return rows

	def _isElided(self, pos) -> bool:
		r, c = pos
		return any(lo <= c < hi for lo, hi in self._elideMap().get(r, ()))

	def _rowHidden(self, r, emap=None) -> bool:
		"""The whole row including its newline is elided."""
		emap = self._elideMap() if emap is None else emap
		rng  = emap.get(r)
		return bool(rng) and rng[0][0] <= 0 and rng[0][1] > len(self._buf[r])

	def _visibleCols(self, r, start, end):
		"""Buffer columns of row *r* in [start, end) that are displayed."""
		rng = self._elideMap().get(r)
		if not rng:
			return range(start, end)
		return [c for c in range(start, end)
			if not any(lo <= c < hi for lo, hi in rng)]

	def _skipElided(self, pos, forward=True):
		"""Move *pos* out of elided text, in the direction of motion
		(or backwards when nothing visible follows)."""
		if not self._elideMap():
			return pos
		for direction in (forward, not forward):
			p = pos
			while self._isElided(p):
				off = self._offset(p) + (1 if direction else -1)
				if off < 0 or (direction and p >= self._lastPos()):
					break
				p = self._fromOffset(off)
			if not self._isElided(p):
				return p
		return pos

	# ------------------------------------------------------------------
	# Left margins (tag options lmargin1 / lmargin2), like Tk: the first
	# display line of a text line is indented by lmargin1, the wrapped
	# continuation lines by lmargin2, both taken from the highest
	# priority tag setting the option on the first displayed character
	# of the display line.
	# ------------------------------------------------------------------

	_MARGIN_OPTS = ('lmargin1', 'lmargin2')

	def _marginKey(self):
		specs = self._specialTags()[1]
		if not specs:
			return None
		return (_core.PX, tuple(specs), self._tagRangeVersion)

	def _margins(self, key=None):
		"""Return a function (row, start) -> left margin in cells of the
		display line starting at (row, start), or None without margins."""
		if key is None:
			key = self._marginKey()
		if key is None:
			return None
		full = (self._version, key, self._elideKey())
		if getattr(self, '_marginCacheKey', None) != full:
			self._marginCacheKey = full
			self._marginCache    = {}
		cache = self._marginCache
		emap  = self._elideMap()
		tags  = key[1]

		def visible(r, c):
			for lo, hi in emap.get(r, ()):
				if lo <= c < hi:
					c = hi
			return c

		def lookup(p, opt):
			for name, m1, m2 in reversed(tags):
				val = m1 if opt == 0 else m2
				if val in self._NO_ELIDE:
					continue
				ranges = self._tagRanges.get(name, ())
				i = bisect.bisect_right(ranges, (p, (1 << 60, 0))) - 1
				if i >= 0 and ranges[i][0] <= p < ranges[i][1]:
					try:
						return max(0, _core._cellsX(val))
					except (TclError, ValueError):
						return 0
			return 0

		def margin(r, start):
			m = cache.get((r, start))
			if m is None:
				c     = visible(r, start)
				first = start == 0 or visible(r, 0) >= start
				m     = lookup((r, c), 0 if first else 1)
				cache[(r, start)] = m
			return m
		return margin

	def _segMargin(self, seg) -> int:
		fn = self._margins()
		return fn(seg[0], seg[1]) if fn else 0

	# ------------------------------------------------------------------
	# Tab stops (options tabs= and tabstyle=), like Tk:
	#   - tabs is a list of distances, each optionally followed by its
	#     alignment (left, right, center, numeric);
	#   - beyond the last stop the stops repeat with the distance of the
	#     last two (or of the single stop); no tabs = every 8 cells;
	#   - tabstyle tabular: the n-th tab of a display line uses the n-th
	#     stop; wordprocessor: the first stop right of the text;
	#   - a tab is always at least one space wide.
	# ------------------------------------------------------------------

	_TAB_ALIGN = {'l': 'left', 'r': 'right', 'c': 'center', 'n': 'numeric'}

	def _tabKey(self):
		return (repr(self._opts.get('tabs')), str(self._opts.get('tabstyle')),
			_core.PX)

	def _tabStops(self):
		"""Return ([(cell, align), …], increment, wordprocessor)."""
		key = self._tabKey()
		if getattr(self, '_tabCacheKey', None) == key:
			return self._tabCache
		tabs = self._opts.get('tabs') or ()
		if isinstance(tabs, str):
			tabs = tabs.split()
		stops = []
		for tok in tabs:
			s = str(tok).strip().lower()
			if not s:
				continue
			if s[0] in self._TAB_ALIGN and s.isalpha():
				if not stops:
					raise TclError(f'bad tab stop "{tok}"')
				stops[-1] = (stops[-1][0], self._TAB_ALIGN[s[0]])
				continue
			stops.append((_core._cellsX(tok), 'left'))
		inc = 8
		if len(stops) >= 2:
			inc = stops[-1][0] - stops[-2][0]
		elif stops:
			inc = stops[0][0]
		wordproc = str(self._opts.get('tabstyle')).startswith('w')
		self._tabCacheKey = key
		self._tabCache    = (stops, max(1, inc), wordproc)
		return self._tabCache

	def _tabStop(self, n, x):
		"""(cell, align) of the n-th tab of a display line found at x."""
		stops, inc, wordproc = self._tabStops()
		if not stops:
			return ((x // inc + 1) * inc, 'left')

		def nth(k):
			if k < len(stops):
				return stops[k]
			s, a = stops[-1]
			return (s + (k - len(stops) + 1) * inc, a)

		if not wordproc:
			return nth(n)
		k = 0
		while True:
			s, a = nth(k)
			if s > x:
				return (s, a)
			k += 1

	def _segXs(self, r, start, end):
		"""Display x (relative to the segment) of every column of the
		display segment (r, start, end), end included; None when the
		segment has no tab (then x = visible columns before it)."""
		line = self._buf[r]
		if '\t' not in line[start:end]:
			return None
		ekey = self._elideKey()
		key  = (self._version, ekey, self._tabKey())
		if getattr(self, '_xsCacheKey', None) != key:
			self._xsCacheKey = key
			self._xsCache    = {}
		xs = self._xsCache.get((r, start, end))
		if xs is not None:
			return xs
		rng  = self._elideMap().get(r) if ekey else None
		hide = (lambda c: any(lo <= c < hi for lo, hi in rng)) if rng \
			else (lambda c: False)
		xs   = [0] * (end - start + 1)
		x    = 0
		ntab = 0
		for k, c in enumerate(range(start, end)):
			xs[k] = x
			if hide(c):
				continue
			if line[c] != '\t':
				x += 1
				continue
			stop, align = self._tabStop(ntab, x)
			ntab += 1
			if align != 'left':
				# width of the text that follows, up to the next tab
				w   = 0
				dot = None
				for j in range(c + 1, len(line)):
					ch = line[j]
					if ch == '\t':
						break
					if hide(j):
						continue
					if ch == '.' and dot is None:
						dot = w
					w += 1
				if align == 'right':
					stop -= w
				elif align == 'center':
					stop -= w // 2
				else:			# numeric: align on the decimal point
					stop -= w if dot is None else dot
			x += max(1, stop - x)
		xs[-1] = x
		if len(self._xsCache) > 4096:
			self._xsCache.clear()
		self._xsCache[(r, start, end)] = xs
		return xs

	def _segX(self, seg, c) -> int:
		"""Display x of column c inside the display segment seg."""
		r, start, end = seg
		c  = max(start, min(c, end))
		m  = self._segMargin(seg)
		xs = self._segXs(r, start, end)
		if xs is not None:
			return m + xs[c - start]
		if r in self._elideMap():
			return m + len(self._visibleCols(r, start, c))
		return m + c - start

	def _segCol(self, seg, dx) -> int:
		"""Column of the display segment seg shown at display x dx."""
		r, start, end = seg
		dx = max(0, dx - self._segMargin(seg))
		xs = self._segXs(r, start, end)
		if xs is not None:
			k = bisect.bisect_right(xs, dx) - 1
			return start + max(0, min(k, end - start))
		if r in self._elideMap():
			cols = list(self._visibleCols(r, start, end))
			return cols[dx] if dx < len(cols) else end
		return start + dx

	def _segWidth(self, seg, margin=None) -> int:
		"""Display width of seg including its left margin."""
		if margin is None:
			margin = self._margins()
		m  = margin(seg[0], seg[1]) if margin else 0
		xs = self._segXs(*seg)
		return m + (xs[-1] if xs is not None else seg[2] - seg[1])

	def _wrapTabRow(self, r, width, mode, segs, margin=None):
		"""Wrap row r, which contains tabs, into display segments."""
		line = self._buf[r]
		n    = len(line)
		s    = 0
		while True:
			if mode == 'none':
				segs.append((r, s, n))
				return
			w  = width - (margin(r, s) if margin else 0)
			xs = self._segXs(r, s, n)
			if xs is None:		# no more tabs
				xs = list(range(n - s + 1))
			if xs[-1] <= w:
				segs.append((r, s, n))
				return
			# longest prefix that fits (at least one character)
			e = s + max(1, bisect.bisect_right(xs, w) - 1)
			if mode == 'word':
				brk = line.rfind(' ', s, e + 1)
				if brk > s:
					e = brk + 1
			segs.append((r, s, e))
			s = e
			if s >= n:
				return

	def _displayLines(self, width=None):
		"""Return list of (row, start, end) display segments."""
		if width is None:
			width = self._textW()
		mode = self._wrapMode()
		ekey = self._elideKey()
		mkey = self._marginKey()
		key  = (width, mode, self._version, ekey, self._tabKey(), mkey)
		cached = self._dlCache.get(key)
		if cached is not None:
			return cached
		emap = self._elideMap() if ekey else {}
		mfn  = self._margins(mkey) if mkey else None
		segs = []
		for r, line in enumerate(self._buf):
			if emap and self._rowHidden(r, emap):
				continue
			if mode == 'none' and '\t' not in line:
				segs.append((r, 0, len(line)))	# fast path
				continue
			self._rowSegs(r, width, mode, segs, mfn)
		if len(self._dlCache) > 8:
			self._dlCache.clear()
		self._dlCache[key] = segs
		return segs

	def _rowSegs(self, r, width, mode, segs, mfn=None):
		"""Append the display segments of text row *r* to *segs*."""
		line = self._buf[r]
		if '\t' in line:
			self._wrapTabRow(r, width, mode, segs, mfn)
			return
		if mode == 'none' or \
		   len(line) + (mfn(r, 0) if mfn else 0) <= width:
			segs.append((r, 0, len(line)))
			return
		s = 0
		while s < len(line):
			e = s + max(1, width - (mfn(r, s) if mfn else 0))
			if e >= len(line):
				segs.append((r, s, len(line)))
				return
			if mode == 'word':
				brk = line.rfind(' ', s, e + 1)
				if brk > s:
					e = brk + 1
			segs.append((r, s, e))
			s = e

	def _patchCaches(self, old, r, dlCache):
		"""Only row *r* was edited (no line added or removed) since
		version *old*: update the entries of row r of the layout caches
		(elide map, margins, tab layout, display lines) and keep the
		rest, instead of recomputing them over the whole text on every
		keystroke."""
		new  = self._version
		ekey = self._elideKey()
		mkey = self._marginKey()
		if ekey is not None and \
		   getattr(self, '_elideCacheKey', None) == (old, ekey):
			rows = self._elideCache
			lst  = self._elideRow(r, ekey[0])
			if lst:
				rows[r] = lst
			else:
				rows.pop(r, None)
			self._elideCacheKey = (new, ekey)
		if mkey is not None and getattr(self, '_marginCacheKey', None) \
				== (old, mkey, ekey):
			self._marginCacheKey = (new, mkey, ekey)
			self._marginCache = {k: v for k, v in
				self._marginCache.items() if k[0] != r}
		xkey = getattr(self, '_xsCacheKey', None)
		if xkey is not None and xkey[0] == old and xkey[1] == ekey:
			self._xsCacheKey = (new,) + xkey[1:]
			self._xsCache = {k: v for k, v in self._xsCache.items()
				if k[0] != r}
		emap = self._elideMap() if ekey else {}
		mfn  = self._margins(mkey) if mkey else None
		for key, segs in dlCache.items():
			width, mode, ver, ek, tkey, mk = key
			if ver != old or ek != ekey or mk != mkey:
				continue
			lo  = bisect.bisect_left(segs, r, key=_segRow)
			hi  = bisect.bisect_right(segs, r, key=_segRow)
			lst = []
			if not (emap and self._rowHidden(r, emap)):
				self._rowSegs(r, width, mode, lst, mfn)
			segs[lo:hi] = lst
			self._dlCache[(width, mode, new, ek, tkey, mk)] = segs

	def _totalRows(self) -> int:
		return len(self._displayLines())

	def _segIndex(self, pos, segs=None):
		"""Index of the display segment containing *pos*."""
		if segs is None:
			segs = self._displayLines()
		r, c = self._clampPos(pos, allowEnd=False)
		lo, hi = 0, len(segs) - 1
		while lo < hi:			# first segment of row r
			mid = (lo + hi) // 2
			if segs[mid][0] < r:
				lo = mid + 1
			else:
				hi = mid
		i = lo
		while i + 1 < len(segs) and segs[i + 1][0] == r and segs[i + 1][1] <= c:
			i += 1
		return i

	def _screenPos(self, pos):
		segs = self._displayLines()
		i    = self._segIndex(pos, segs)
		if not (self._scrollY <= i < self._scrollY + self._visRows()):
			return None
		bd = self._border()
		x  = self._segX(segs[i], pos[1])
		if self._wrapMode() == 'none':
			x -= self._scrollX
		if not (0 <= x < self._textW()) and not (x == self._textW() and
				self._wrapMode() != 'none'):
			return None
		return (self._y + bd + i - self._scrollY, self._x + bd + x)

	def _posFromXY(self, x, y):
		"""Widget-relative (x, y) → buffer position."""
		segs = self._displayLines()
		bd   = self._border()
		i    = max(0, min(self._scrollY + y - bd, len(segs) - 1))
		r, start, end = segs[i]
		dx   = max(0, x - bd)
		if self._wrapMode() == 'none':
			dx += self._scrollX
		c = self._segCol(segs[i], dx)
		last = i + 1 >= len(segs) or segs[i + 1][0] != r
		c = min(c, end if last else max(start, end - 1))
		return (r, c)

	def _scrollToPos(self, pos):
		if self._height <= 0 or self._width <= 0:
			return
		segs = self._displayLines()
		i    = self._segIndex(pos, segs)
		visH = self._visRows()
		if i < self._scrollY:
			self._scrollY = i
		elif i >= self._scrollY + visH:
			self._scrollY = i - visH + 1
		if self._wrapMode() == 'none':
			visW = self._textW()
			c    = self._segX(segs[i], pos[1])
			if c < self._scrollX:
				self._scrollX = c
			elif c >= self._scrollX + visW:
				self._scrollX = c - visW + 1
		else:
			self._scrollX = 0
		self._clampScroll()

	def _scrollToCursor(self):
		self._scrollToPos(self._cur)

	def _indexForYview(self, idx):
		return self._segIndex(self._parseIndex(idx))

	def xview(self, *args):
		mfn    = self._margins()
		maxLen = max((self._segWidth((r, 0, len(l)), mfn)
			if '\t' in l or mfn else len(l)
			for r, l in enumerate(self._buf)), default=0)
		visW   = self._textW()
		if not args:
			if maxLen <= 0 or self._wrapMode() != 'none':
				return (0.0, 1.0)
			return (self._scrollX / maxLen, min(1.0, (self._scrollX + visW) / maxLen))
		if args[0] == 'moveto':
			self._scrollX = int(float(args[1]) * maxLen)
		elif args[0] == 'scroll':
			n = int(args[1])
			if len(args) > 2 and str(args[2]).startswith('page'):
				n *= visW
			self._scrollX += n
		self._scrollX = max(0, min(self._scrollX, max(0, maxLen - visW)))
		self._markDirty()
		return None

	# Internal callers use Text.xview(): applications override xview()
	# (e.g. to close a popup when the view scrolls), and tkinter's
	# xview_moveto()/redraws never go through the Python method.
	def xview_moveto(self, fraction):
		Text.xview(self, 'moveto', fraction)

	def xview_scroll(self, number, what):
		Text.xview(self, 'scroll', number, what)

	def _preRender(self):
		self._clampScroll()
		self._notifyYScroll()
		cmd = self._opts.get('xscrollcommand')
		if callable(cmd):
			frac = Text.xview(self)
			if getattr(self, '_lastXScroll', None) != frac:
				self._lastXScroll = frac
				cmd(*frac)

	# ------------------------------------------------------------------
	# Preferred size
	# ------------------------------------------------------------------

	def _preferredSize(self):
		bd = self._cfgBorder()
		ow = _int(self._opts.get('width'), 40) or 40
		oh = _int(self._opts.get('height'), 10) or 10
		return (ow + 2*bd, oh + 2*bd)

	# ------------------------------------------------------------------
	# Rendering
	# ------------------------------------------------------------------

	def _tagStyle(self, name):
		"""Return (fg, bg, flags) for tag *name*."""
		cfg   = self._tagCfg.get(name, {})
		fg    = cfg.get('foreground') or ''
		bg    = cfg.get('background') or ''
		flags = 0
		font  = str(cfg.get('font') or '').lower()
		if 'bold' in font:
			flags |= curses.A_BOLD
		if 'italic' in font and hasattr(curses, 'A_ITALIC'):
			flags |= curses.A_ITALIC
		if cfg.get('underline') not in (None, '', 0, False, '0'):
			flags |= curses.A_UNDERLINE
		if cfg.get('reverse'):
			flags |= curses.A_REVERSE
		if name == 'sel':
			sfg = self._optColor('selectforeground') or fg
			sbg = self._optColor('selectbackground') or bg
			if not (sfg or sbg):
				sfg, sbg, _ = _colors.getTheme('select')
				flags |= _colors.roleCursesFlags('select')
			fg, bg = sfg, sbg
		return fg, bg, flags

	_NO_STYLE = ('', '', 0)

	def _visibleStyles(self, segs, visH):
		"""[(name, style)] in priority order of the tags that change the
		look of the text and have a range on the displayed rows.  Done
		once per render: testing every tag on every row is too slow
		with thousands of tags (one per line or card)."""
		if not segs:
			return []
		first = min(self._scrollY, len(segs) - 1)
		last  = min(self._scrollY + visH, len(segs)) - 1
		r0    = segs[first][0]
		r1    = segs[max(first, last)][0]
		result = []
		for n in self._tagOrder:
			ranges = self._tagRanges.get(n)
			if not ranges:
				continue
			i = bisect.bisect_left(ranges, (r0, 0), key=_rangeEnd)
			if i >= len(ranges) or ranges[i][0][0] > r1:
				continue
			style = self._tagStyle(n)
			if style != self._NO_STYLE:
				result.append((n, style))
		return result

	def _cellStyle(self, r, c, styles, base):
		"""Style (fg, bg, flags) of the character (or newline) at (r, c)."""
		fg, bg, fl = base
		for name, (tfg, tbg, tflags) in styles:
			if self._tagCovers(name, (r, c)):
				fg, bg, fl = tfg or fg, tbg or bg, fl | tflags
		return (fg, bg, fl)

	def _edgeStyle(self, seg, styles, base):
		"""Style that fills the rest of the display line after *seg*
		(*styles* = the tags with a background or reverse)
		(like Tk: the newline's tags reach the right edge; a wrapped line
		is filled when the tags continue on the next display line), or
		None when the base background stays."""
		if not styles:
			return None
		r, start, end = seg
		if end >= len(self._buf[r]):
			style = self._cellStyle(r, end, styles, base)
		elif end > start:
			style = self._cellStyle(r, end - 1, styles, base)
			if style != self._cellStyle(r, end, styles, base):
				return None
		else:
			return None
		# only the background (and a reverse selection) is extended
		style = (base[0], style[1], style[2] & curses.A_REVERSE)
		return None if style == base else style

	def _fillEdge(self, scr, i, bd, x0, n, style, cellAttr):
		"""Paint *n* blank cells from display column x0 in *style*."""
		if n > 0 and style is not None:
			_addStr(scr, self._y + bd + i, self._x + bd + x0, ' ' * n,
				cellAttr(style))

	def render(self, scr):
		if not self._isMapped():
			return

		bd     = self._border()
		relief = self._opts.get('relief', 'sunken')
		baseFg = self._color('fg')
		baseBg = self._color('bg')
		attr   = self._getAttr()

		_fillRect(scr, self._y, self._x, self._height, self._width, attr=attr)
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._height, self._width, relief,
				self._borderAttr(attr))

		self._clampScroll()		# text may have been deleted below
		visH   = self._visRows()
		visW   = self._textW()
		segs   = self._displayLines(visW)
		sx     = self._scrollX if self._wrapMode() == 'none' else 0
		styles = self._visibleStyles(segs, visH)
		edge   = [it for it in styles
				if it[1][1] or it[1][2] & curses.A_REVERSE]
		emap   = self._elideMap()
		app    = self._getApp()
		mfn    = self._margins()
		base   = (baseFg, baseBg, 0)
		attrCache = {}

		def cellAttr(style):
			a = attrCache.get(style)
			if a is None:
				fg, bg, flags = style
				a = (app._colors.getAttr(fg, bg) if app else 0) | flags
				attrCache[style] = a
			return a

		for i in range(visH):
			si = self._scrollY + i
			if si >= len(segs):
				break
			r, start, end = segs[si]
			# left margin: skip cs content cells, start dx0 cells in
			m     = mfn(r, start) if mfn else 0
			cs    = max(0, sx - m)
			dx0   = max(0, m - sx)
			avail = max(0, visW - dx0)
			xs = self._segXs(r, start, end)
			if xs is not None:
				self._renderTabSeg(scr, i, bd, segs[si], xs, cs, avail,
					styles, base, cellAttr, dx0, edge)
				continue
			if r in emap:
				cols  = list(self._visibleCols(r, start, end))[cs:cs + avail]
				line  = self._buf[r]
				text  = ''.join(line[c] for c in cols).replace('\t', ' ')
				cells = [(baseFg, baseBg, 0)] * len(text)
				for name, (tfg, tbg, tflags) in styles:
					for a, b in self._rangesOnRow(name, r):
						lo = a[1] if a[0] == r else 0
						hi = b[1] if b[0] == r else len(line) + 1
						for j, c in enumerate(cols):
							if lo <= c < hi:
								fg, bg, fl = cells[j]
								cells[j] = (tfg or fg, tbg or bg, fl | tflags)
				self._drawCells(scr, i, bd, text, cells, cellAttr, dx0)
				self._fillEdge(scr, i, bd, dx0 + len(text), avail - len(text),
					self._edgeStyle(segs[si], edge, base), cellAttr)
				continue
			text  = self._buf[r][start:end][cs:cs + avail]
			text  = text.replace('\t', ' ')
			c0    = start + cs
			cells = [(baseFg, baseBg, 0)] * len(text)
			for name, (tfg, tbg, tflags) in styles:
				for a, b in self._rangesOnRow(name, r):
					lo = a[1] if a[0] == r else 0
					hi = b[1] if b[0] == r else len(self._buf[r]) + 1
					lo = max(lo, c0) - c0
					hi = min(hi, c0 + len(text)) - c0
					for j in range(lo, hi):
						fg, bg, fl = cells[j]
						cells[j] = (tfg or fg, tbg or bg, fl | tflags)
			# draw runs of equal style
			y = self._y + bd + i
			x = self._x + bd + dx0
			j = 0
			while j < len(text):
				k = j
				while k < len(text) and cells[k] == cells[j]:
					k += 1
				_addStr(scr, y, x + j, text[j:k], cellAttr(cells[j]))
				j = k
			# tags covering the newline / the wrap reach the right edge
			self._fillEdge(scr, i, bd, dx0 + len(text), avail - len(text),
				self._edgeStyle(segs[si], edge, base), cellAttr)

		if self._showInternalBar():
			self._drawInternalBar(scr, self._x + self._width - bd - 1,
				self._y + bd, visH, attr)

	def _renderTabSeg(self, scr, i, bd, seg, xs, sx, visW, styles, base,
			cellAttr, dx0=0, edge=()):
		"""Draw display segment seg containing tabs (xs = its layout)."""
		r, start, end = seg
		line  = self._buf[r]
		n     = len(line)
		# style of every buffer column of the segment (+ its newline)
		hasNl = end == n
		ncol  = end - start + (1 if hasNl else 0)
		style = [base] * ncol
		for name, (tfg, tbg, tflags) in styles:
			for a, b in self._rangesOnRow(name, r):
				lo = max(a[1] if a[0] == r else 0, start) - start
				hi = min(b[1] if b[0] == r else n + 1, start + ncol) - start
				for k in range(lo, hi):
					fg, bg, fl = style[k]
					style[k] = (tfg or fg, tbg or bg, fl | tflags)
		chars = []
		cells = []
		for k in range(end - start):
			w = xs[k + 1] - xs[k]
			if w <= 0:
				continue
			ch = line[start + k]
			chars.append(' ' * w if ch == '\t' else ch)
			cells.extend([style[k]] * w)
		text  = ''.join(chars)[sx:sx + visW]
		cells = cells[sx:sx + visW]
		self._drawCells(scr, i, bd, text, cells, cellAttr, dx0)
		# tags covering the newline / the wrap reach the right edge
		self._fillEdge(scr, i, bd, dx0 + len(text), visW - len(text),
			self._edgeStyle(seg, edge, base), cellAttr)

	def _drawCells(self, scr, i, bd, text, cells, cellAttr, dx0=0):
		y = self._y + bd + i
		x = self._x + bd + dx0
		j = 0
		while j < len(text):
			k = j
			while k < len(text) and cells[k] == cells[j]:
				k += 1
			_addStr(scr, y, x + j, text[j:k], cellAttr(cells[j]))
			j = k

	def _cursorPos(self):
		"""Return screen (y, x) of cursor for Tk to position the cursor block."""
		if self._opts.get('state') == 'disabled':
			return None
		return self._screenPos(self._cur)

	# ------------------------------------------------------------------
	# Keyboard input
	# ------------------------------------------------------------------

	def _moveVertical(self, pos, delta):
		segs = self._displayLines()
		i    = self._segIndex(pos, segs)
		col  = self._wantCol if self._wantCol is not None else \
			self._segX(segs[i], pos[1])
		self._wantCol = col
		j = max(0, min(i + delta, len(segs) - 1))
		r, start, end = segs[j]
		last = j + 1 >= len(segs) or segs[j + 1][0] != r
		c = self._segCol(segs[j], col)
		c = min(c, end if last else max(start, end - 1))
		return (r, c)

	def _handleKey(self, key):
		state = self._opts.get('state', 'normal')
		if state == 'disabled' and not (key in _MOVEMENT_KEYS or
				key in _SHIFT_MAP or key in (_CTRL_A, _CTRL_E)):
			return False		# like Tk: a disabled text still scrolls

		r, c = self._cur

		if key == _CTRL_A:
			self._selAnchor = (0, 0)
			self._setSel((0, 0), self._lastPos())
			return True

		# Determine whether this is a shift+movement (extends selection)
		extendSel = key in _SHIFT_MAP
		if extendSel:
			if self._sel is None or self._selAnchor is None:
				self._selAnchor = (r, c)
			key = _SHIFT_MAP[key]
		if key == _CTRL_E:
			key = KEY_END

		keepCol = key in (KEY_UP, KEY_DOWN, KEY_PPAGE, KEY_NPAGE)
		if not keepCol:
			self._wantCol = None
		sel = self._sel

		if key == KEY_UP:
			r, c = self._moveVertical((r, c), -1)
		elif key == KEY_DOWN:
			r, c = self._moveVertical((r, c), +1)
		elif key == KEY_PPAGE:
			r, c = self._moveVertical((r, c), -self._visRows())
		elif key == KEY_NPAGE:
			r, c = self._moveVertical((r, c), +self._visRows())
		elif key == KEY_LEFT:
			if not extendSel and sel:
				r, c = sel[0], sel[1]			# collapse to start
			elif c > 0:
				c -= 1
			elif r > 0:
				r -= 1
				c = len(self._buf[r])
		elif key == KEY_RIGHT:
			if not extendSel and sel:
				r, c = sel[2], sel[3]			# collapse to end
			elif c < len(self._buf[r]):
				c += 1
			elif r < len(self._buf) - 1:
				r += 1
				c = 0
		elif key == KEY_HOME:
			segs = self._displayLines()
			c = segs[self._segIndex((r, c), segs)][1]
		elif key == KEY_END:
			segs = self._displayLines()
			i    = self._segIndex((r, c), segs)
			_, start, end = segs[i]
			last = i + 1 >= len(segs) or segs[i + 1][0] != r
			c = end if last else max(start, end - 1)
		elif key == KEY_BACKSPACE:
			if sel:
				self._deleteSelection()
			elif (r, c) > (0, 0):
				prev = self._movePos((r, c), -1)
				self._beginEdit('delete')
				self._rawDelete(prev, (r, c))
			r, c = self._cur
		elif key == KEY_DC:
			if sel:
				self._deleteSelection()
			elif (r, c) < self._lastPos():
				nxt = self._movePos((r, c), 1)
				self._beginEdit('delete')
				self._rawDelete((r, c), nxt)
			r, c = self._cur
		elif key == _CTRL_K:
			self._beginEdit()
			end = (r, len(self._buf[r])) if c < len(self._buf[r]) else \
				min(self._movePos((r, c), 1), self._lastPos())
			self._rawDelete((r, c), end)
			r, c = self._cur
		elif key == KEY_ENTER:
			if sel:
				self._deleteSelection()
			self._beginEdit('type')
			self._rawInsert(self._cur, '\n')
			r, c = self._cur
			self._lastEdit = None		# one undo step per line
		elif isPrintableKey(key):
			if sel:
				self._deleteSelection()
			self._beginEdit('type')
			self._rawInsert(self._cur, chr(key))
			r, c = self._cur
			if key == 32:
				self._lastEdit = None	# group typing word by word
		else:
			return False

		# Update selection state
		if extendSel:
			self._setSel(self._selAnchor, (r, c))
		elif key in _MOVEMENT_KEYS:
			self._setSel(None, None)
			self._selAnchor = None
			self._lastEdit  = None

		if key in _MOVEMENT_KEYS and self._elideMap():
			forward = key in (KEY_RIGHT, KEY_DOWN, KEY_NPAGE, KEY_END)
			r, c = self._skipElided((r, c), forward)
		self._cur = (r, c)
		self._scrollToCursor()
		self._markDirty()
		return True

	def _deleteSelection(self):
		"""Delete selected text.  Return True if a selection existed."""
		s = self._sel
		if s is None:
			return False
		self._beginEdit()
		self._rawDelete((s[0], s[1]), (s[2], s[3]))
		self._selAnchor = None
		self._cur       = (s[0], s[1])
		return True

	# ------------------------------------------------------------------
	# Mouse input
	# ------------------------------------------------------------------

	def _posAtScreen(self, mx, my):
		"""Text position under screen cell (mx, my), clamped to the view."""
		bd = self._border()
		x  = max(bd, min(mx - self._x, self._width - bd - 1))
		y  = max(bd, min(my - self._y, self._height - bd - 1))
		return self._posFromXY(x, y)

	def _pointerAt(self, mx, my):
		self._marks['current'] = self._posAtScreen(mx, my)

	def _fireTagBindings(self, pos, mx, my, bstate):
		if not self._tagBinds:
			return
		names = [n for n in self._tagOrder if n in self._tagBinds and
			self._tagCovers(n, pos)]
		if not names:
			return
		evt = _newMouseEvent(self, mx, my, bstate)
		for alts in _mouseEventNames(bstate, self._dragging()):
			for name in reversed(names):
				for seq in alts:
					funcs = self._tagBinds[name].get(seq)
					if funcs:
						for f in funcs:
							f(evt)
						break

	def _dragLost(self):
		self._mouseDown = False
		self._sbDrag    = None

	def _handleMouse(self, mx, my, bstate):
		bd    = self._border()
		wheel = isWheel(bstate)
		if wheel:
			self._scrollY += 3 * wheel
			self._clampScroll()
			self._markDirty()
			return True

		press   = bool(bstate & B1_PRESS) and not (bstate & MOTION)
		release = bool(bstate & (B1_RELEASE | B1_CLICK))
		motion  = bool(bstate & MOTION) or (bool(bstate & B1_PRESS) and self._mouseDown)
		visH    = self._visRows()

		# internal scrollbar
		barX = self._x + self._width - bd - 1
		if self._sbDrag is not None:
			if motion or release:
				self._barDrag(my - self._y - bd, visH)
			if release:
				self._sbDrag = None
			return True
		if self._showInternalBar() and mx == barX and \
				self._y + bd <= my < self._y + bd + visH and \
				(press or bstate & B1_CLICK):
			self._barClick(my - self._y - bd, visH, press)
			return True

		# auto-scroll while dragging outside the text area
		if self._mouseDown and motion:
			if my < self._y + bd:
				self._scrollY -= 1
			elif my >= self._y + bd + visH:
				self._scrollY += 1
			self._clampScroll()
		pos = self._posAtScreen(mx, my)
		self._marks['current'] = pos

		if not (press or release or motion or bstate & B1_DCLICK):
			return False

		if bstate & B1_DCLICK:
			a = self._applyWordMod(pos, 'wordstart')
			b = self._applyWordMod(pos, 'wordend')
			self._selAnchor = a
			self._setSel(a, b)
			self._cur       = b
			self._mouseDown = False
		elif (press or bstate & B1_CLICK) and not self._mouseDown:
			self._mouseDown = not (bstate & B1_CLICK)
			self._setSel(None, None)
			self._selAnchor = pos
			self._cur       = pos
			self._wantCol   = None
			self._lastEdit  = None
		elif self._mouseDown:
			if self._selAnchor is not None:
				self._setSel(self._selAnchor, pos)
			self._cur = pos
			if release:
				self._mouseDown = False

		self._fireTagBindings(pos, mx, my, bstate)
		self._markDirty()
		return True
