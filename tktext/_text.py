import curses
import re

from ._core import TclError, Widget, _addStr, _fillRect, _drawBorder, _int, \
	_newMouseEvent, _mouseEventNames
from ._listbox import _ScrollMixin
from ._events import (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_HOME, KEY_END, KEY_PPAGE, KEY_NPAGE, KEY_BACKSPACE, KEY_DC, KEY_ENTER,
	KEY_SHIFT_UP, KEY_SHIFT_DOWN, KEY_SHIFT_LEFT, KEY_SHIFT_RIGHT,
	KEY_SHIFT_HOME, KEY_SHIFT_END, KEY_SHIFT_PPAGE, KEY_SHIFT_NPAGE,
	B1_PRESS, B1_RELEASE, B1_CLICK, B1_DCLICK, MOTION, isWheel,
	isPrintableKey)

# Shift+key → plain movement key mapping
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


def _isWordChar(ch) -> bool:
	return ch.isalnum() or ch == '_'


class Text(_ScrollMixin, Widget):
	"""Multi-line text editor widget.  Mirrors tkinter.Text.

	Indices follow Tk syntax: "line.col" (line 1-based, col 0-based),
	"end", "insert", "current", mark names, "sel.first"/"sel.last",
	"tag.first"/"tag.last", "@x,y" and modifiers such as "+3c", "-1l",
	"linestart", "lineend", "wordstart", "wordend" (e.g. "end-1c").

	Positions are stored as (row, col) tuples, 0-based.  The position
	after the implicit final newline ("end") is (len(lines), 0).
	"""

	def __init__(self, parent=None, **kwargs):
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

		if kwargs:
			self.configure(**kwargs)

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
					pos = self._fromOffset(self._offset(pos) + n)
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
			return self._posFromXY(int(m.group(1)), int(m.group(2))), s[m.end():]
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
		for name, ranges in self._tagRanges.items():
			newRanges = []
			for a, b in ranges:
				a = adjust(a, True)	# text inserted at the start is untagged
				b = adjust(b, False)	# … and also at the end
				if a < b:
					newRanges.append((a, b))
			self._tagRanges[name] = newRanges

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
		for name, ranges in self._tagRanges.items():
			newRanges = []
			for s, e in ranges:
				s, e = adjust(s), adjust(e)
				if s < e:
					newRanges.append((s, e))
			self._tagRanges[name] = newRanges

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
		self._changed()
		return (lastR, lastC)

	def _rawDelete(self, a, b):
		if a >= b:
			return
		self._adjustDelete(a, b)
		(ar, ac), (br, bc) = a, b
		self._buf[ar:br + 1] = [self._buf[ar][:ac] + self._buf[br][bc:]]
		if not self._buf:
			self._buf = ['']
		self._changed()

	def _changed(self):
		self._version += 1
		self._dlCache  = {}
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
		self._scrollToCursor()

	def delete(self, idx1, idx2=None):
		"""Delete text between *idx1* and *idx2* (or one char at *idx1*)."""
		if self._opts.get('state') == 'disabled':
			return
		a = self._parseIndex(idx1)
		b = self._parseIndex(idx2) if idx2 is not None else \
			self._fromOffset(self._offset(a) + 1)
		a = min(a, self._lastPos())
		b = min(b, self._lastPos())
		if a > b:
			return
		self._beginEdit()
		self._rawDelete(a, b)
		self._lastEdit = None
		self._scrollToCursor()

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
		return (x - self._x, y - self._y, 1, 1)

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
		self._markDirty()

	def markUnset(self, *names):
		for n in names:
			if n not in ('insert', 'current'):
				self._marks.pop(n, None)
				self._gravity.pop(n, None)

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

	def tagConfigure(self, name, cnf=None, **kwargs):
		"""Configure appearance of tag *name* (foreground, background,
		underline, font with 'bold'/'italic', reverse …)."""
		if cnf:
			kwargs.update(cnf)
		self._ensureTag(name)
		if not kwargs:
			return dict(self._tagCfg[name])
		for k, v in kwargs.items():
			k = {'fg': 'foreground', 'bg': 'background'}.get(k, k)
			self._tagCfg[name][k] = v
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
		ranges = self._tagRanges[name] + [(a, b)]
		ranges.sort()
		merged = []
		for s, e in ranges:
			if merged and s <= merged[-1][1]:
				merged[-1] = (merged[-1][0], max(merged[-1][1], e))
			else:
				merged.append((s, e))
		self._tagRanges[name] = merged

	def tagAdd(self, name, idx1, *more):
		"""Apply tag *name* to [idx1, idx2) (more pairs may follow)."""
		args = [idx1] + list(more)
		for i in range(0, len(args), 2):
			a = self._parseIndex(args[i])
			if i + 1 < len(args):
				b = self._parseIndex(args[i + 1])
			else:
				b = self._fromOffset(self._offset(a) + 1)
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
			self._fromOffset(self._offset(a) + 1)
		out = []
		for s, e in self._tagRanges[name]:
			if e <= a or s >= b:
				out.append((s, e))
				continue
			if s < a:
				out.append((s, a))
			if e > b:
				out.append((b, e))
		self._tagRanges[name] = out
		self._markDirty()

	def tagDelete(self, *names):
		for n in names:
			if n == 'sel':
				self._tagRanges['sel'] = []
				continue
			self._tagCfg.pop(n, None)
			self._tagRanges.pop(n, None)
			self._tagBinds.pop(n, None)
			if n in self._tagOrder:
				self._tagOrder.remove(n)
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
		return tuple(n for n in self._tagOrder
			if any(a <= pos < b for a, b in self._tagRanges.get(n, [])))

	def tagNextrange(self, name, idx1, idx2=None):
		a = self._parseIndex(idx1)
		b = self._parseIndex(idx2) if idx2 is not None else self._endPos()
		for s, e in self._tagRanges.get(name, []):
			if s >= a and s < b:
				return (self._toTkIndex(s), self._toTkIndex(e))
		return ()

	def tagPrevrange(self, name, idx1, idx2=None):
		a = self._parseIndex(idx1)
		b = self._parseIndex(idx2) if idx2 is not None else (0, 0)
		for s, e in reversed(self._tagRanges.get(name, [])):
			if s < a and s >= b:
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
		self._markDirty()

	def tagLower(self, name, belowThis=None):
		if name not in self._tagOrder or name == 'sel':
			return
		self._tagOrder.remove(name)
		if belowThis in self._tagOrder:
			self._tagOrder.insert(self._tagOrder.index(belowThis), name)
		else:
			self._tagOrder.insert(0, name)
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
		return max(1, self._w - 2*self._border())

	def _visRows(self) -> int:
		return max(1, self._h - 2*self._border())

	def _textW(self) -> int:
		"""Width available for text (excludes the internal scrollbar)."""
		w = self._innerW()
		if not callable(self._opts.get('yscrollcommand')) and w > 2:
			if len(self._displayLines(w)) > self._visRows():
				return w - 1
		return w

	def _displayLines(self, width=None):
		"""Return list of (row, start, end) display segments."""
		if width is None:
			width = self._textW()
		mode = self._wrapMode()
		key  = (width, mode, self._version)
		cached = self._dlCache.get(key)
		if cached is not None:
			return cached
		segs = []
		for r, line in enumerate(self._buf):
			if mode == 'none' or len(line) <= width:
				segs.append((r, 0, len(line)))
				continue
			s = 0
			while s < len(line):
				e = s + width
				if e >= len(line):
					segs.append((r, s, len(line)))
					break
				if mode == 'word':
					brk = line.rfind(' ', s, e + 1)
					if brk > s:
						e = brk + 1
				segs.append((r, s, e))
				s = e
		if len(self._dlCache) > 8:
			self._dlCache.clear()
		self._dlCache[key] = segs
		return segs

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
		_, start, _ = segs[i]
		bd = self._border()
		x  = pos[1] - start
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
		c = start + dx
		last = i + 1 >= len(segs) or segs[i + 1][0] != r
		c = min(c, end if last else max(start, end - 1))
		return (r, c)

	def _scrollToPos(self, pos):
		if self._h <= 0 or self._w <= 0:
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
			c    = pos[1]
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
		maxLen = max((len(l) for l in self._buf), default=0)
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

	def xview_moveto(self, fraction):
		self.xview('moveto', fraction)

	def xview_scroll(self, number, what):
		self.xview('scroll', number, what)

	def _preRender(self):
		self._clampScroll()
		self._notifyYScroll()
		cmd = self._opts.get('xscrollcommand')
		if callable(cmd):
			frac = self.xview()
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
			sfg = self._opts.get('selectforeground') or fg
			sbg = self._opts.get('selectbackground') or bg
			if not (sfg or sbg):
				flags |= curses.A_REVERSE
			fg, bg = sfg, sbg
		return fg, bg, flags

	def render(self, scr):
		if not self._isMapped():
			return

		bd     = self._border()
		relief = self._opts.get('relief', 'sunken')
		baseFg = self._opts.get('fg') or ''
		baseBg = self._opts.get('bg') or ''
		attr   = self._getAttr()

		_fillRect(scr, self._y, self._x, self._h, self._w, attr=attr)
		if bd > 0 and relief != 'flat':
			_drawBorder(scr, self._y, self._x, self._h, self._w, relief, attr)

		visH   = self._visRows()
		visW   = self._textW()
		segs   = self._displayLines(visW)
		sx     = self._scrollX if self._wrapMode() == 'none' else 0
		styles = [(n, self._tagStyle(n)) for n in self._tagOrder]
		app    = self._getApp()
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
			text  = self._buf[r][start:end][sx:sx + visW] if sx else \
				self._buf[r][start:end][:visW]
			text  = text.replace('\t', ' ')
			c0    = start + sx
			cells = [(baseFg, baseBg, 0)] * len(text)
			for name, (tfg, tbg, tflags) in styles:
				for a, b in self._tagRanges.get(name, []):
					if b[0] < r or a[0] > r:
						continue
					lo = a[1] if a[0] == r else 0
					hi = b[1] if b[0] == r else len(self._buf[r]) + 1
					lo = max(lo, c0) - c0
					hi = min(hi, c0 + len(text)) - c0
					for j in range(lo, hi):
						fg, bg, fl = cells[j]
						cells[j] = (tfg or fg, tbg or bg, fl | tflags)
			# draw runs of equal style
			y = self._y + bd + i
			x = self._x + bd
			j = 0
			while j < len(text):
				k = j
				while k < len(text) and cells[k] == cells[j]:
					k += 1
				_addStr(scr, y, x + j, text[j:k], cellAttr(cells[j]))
				j = k
			# selection covering the newline: show one highlighted cell
			if len(text) < visW and self._tagRanges.get('sel'):
				nl = (r, len(self._buf[r]))
				for a, b in self._tagRanges['sel']:
					if a <= nl < b and end == len(self._buf[r]):
						_addStr(scr, y, x + len(text), ' ',
							cellAttr(self._tagStyle('sel')))

		if self._showInternalBar():
			self._drawInternalBar(scr, self._x + self._w - bd - 1,
				self._y + bd, visH, attr)

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
		col  = self._wantCol if self._wantCol is not None else pos[1] - segs[i][1]
		self._wantCol = col
		j = max(0, min(i + delta, len(segs) - 1))
		r, start, end = segs[j]
		last = j + 1 >= len(segs) or segs[j + 1][0] != r
		c = start + col
		c = min(c, end if last else max(start, end - 1))
		return (r, c)

	def _handleKey(self, key):
		state = self._opts.get('state', 'normal')
		if state == 'disabled':
			return False

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
				prev = self._fromOffset(self._offset((r, c)) - 1)
				self._beginEdit('delete')
				self._rawDelete(prev, (r, c))
			r, c = self._cur
		elif key == KEY_DC:
			if sel:
				self._deleteSelection()
			elif (r, c) < self._lastPos():
				nxt = self._fromOffset(self._offset((r, c)) + 1)
				self._beginEdit('delete')
				self._rawDelete((r, c), nxt)
			r, c = self._cur
		elif key == _CTRL_K:
			self._beginEdit()
			end = (r, len(self._buf[r])) if c < len(self._buf[r]) else \
				min(self._fromOffset(self._offset((r, c)) + 1), self._lastPos())
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

	def _fireTagBindings(self, pos, mx, my, bstate):
		if not self._tagBinds:
			return
		names = [n for n in self._tagOrder if n in self._tagBinds and
			any(a <= pos < b for a, b in self._tagRanges.get(n, []))]
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
		barX = self._x + self._w - bd - 1
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
		x   = max(bd, min(mx - self._x, self._w - bd - 1))
		y   = max(bd, min(my - self._y, self._h - bd - 1))
		pos = self._posFromXY(x, y)
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
