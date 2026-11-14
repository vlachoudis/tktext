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

import curses
import time as _time
import itertools as _itertools

# Useful key constants
KEY_UP		= curses.KEY_UP
KEY_DOWN	= curses.KEY_DOWN
KEY_LEFT	= curses.KEY_LEFT
KEY_RIGHT	= curses.KEY_RIGHT
KEY_HOME	= curses.KEY_HOME
KEY_END		= curses.KEY_END
KEY_PPAGE	= curses.KEY_PPAGE
KEY_NPAGE	= curses.KEY_NPAGE
KEY_BACKSPACE	= curses.KEY_BACKSPACE
KEY_DC		= curses.KEY_DC
KEY_IC		= curses.KEY_IC
KEY_ENTER	= 10
KEY_CR		= 13
KEY_TAB		= 9
KEY_BTAB	= 353	# Shift-Tab
KEY_ESC		= 27
KEY_SPACE	= 32
KEY_CTRL_C	= 3	# raw tty: no SIGINT
KEY_CTRL_Z	= 26	# raw tty: no SIGTSTP

# Shift + movement keys (values are platform defaults; getattr guards portability)
KEY_SHIFT_UP	= getattr(curses, 'KEY_SR',        337)
KEY_SHIFT_DOWN	= getattr(curses, 'KEY_SF',        336)
KEY_SHIFT_LEFT	= getattr(curses, 'KEY_SLEFT',     393)
KEY_SHIFT_RIGHT	= getattr(curses, 'KEY_SRIGHT',    402)
KEY_SHIFT_HOME	= getattr(curses, 'KEY_SHOME',     391)
KEY_SHIFT_END	= getattr(curses, 'KEY_SEND',      384)
KEY_SHIFT_PPAGE	= getattr(curses, 'KEY_SPREVIOUS', 398)
KEY_SHIFT_NPAGE	= getattr(curses, 'KEY_SNEXT',     396)

_SYMS = {
	curses.KEY_UP:		'Up',
	curses.KEY_DOWN:	'Down',
	curses.KEY_LEFT:	'Left',
	curses.KEY_RIGHT:	'Right',
	curses.KEY_HOME:	'Home',
	curses.KEY_END:		'End',
	curses.KEY_PPAGE:	'Prior',
	curses.KEY_NPAGE:	'Next',
	curses.KEY_BACKSPACE:	'BackSpace',
	127:			'BackSpace',
	8:			'BackSpace',
	curses.KEY_DC:		'Delete',
	curses.KEY_IC:		'Insert',
	curses.KEY_ENTER:	'Return',
	10:			'Return',
	13:			'Return',
	27:			'Escape',
	9:			'Tab',
	353:			'BackTab',
	32:			'space',
	# like Tk the keysym of a shifted key is the plain name (state=Shift)
	KEY_SHIFT_UP:		'Up',
	KEY_SHIFT_DOWN:		'Down',
	KEY_SHIFT_LEFT:		'Left',
	KEY_SHIFT_RIGHT:	'Right',
	KEY_SHIFT_HOME:		'Home',
	KEY_SHIFT_END:		'End',
	KEY_SHIFT_PPAGE:	'Prior',
	KEY_SHIFT_NPAGE:	'Next',
}
for _i in range(12):
	_SYMS[curses.KEY_F1 + _i] = f'F{_i + 1}'

# Shifted special keys are reported to bindings as <Shift-XXX> as in tkinter
_SHIFTED = {
	KEY_SHIFT_UP:		'Up',
	KEY_SHIFT_DOWN:		'Down',
	KEY_SHIFT_LEFT:		'Left',
	KEY_SHIFT_RIGHT:	'Right',
	KEY_SHIFT_HOME:		'Home',
	KEY_SHIFT_END:		'End',
	KEY_SHIFT_PPAGE:	'Prior',
	KEY_SHIFT_NPAGE:	'Next',
	353:			'Tab',
}

# tkinter keysym names of printable punctuation characters
_PUNCT = {
	'!': 'exclam',		'"': 'quotedbl',	'#': 'numbersign',
	'$': 'dollar',		'%': 'percent',		'&': 'ampersand',
	"'": 'apostrophe',	'(': 'parenleft',	')': 'parenright',
	'*': 'asterisk',	'+': 'plus',		',': 'comma',
	'-': 'minus',		'.': 'period',		'/': 'slash',
	':': 'colon',		';': 'semicolon',	'<': 'less',
	'=': 'equal',		'>': 'greater',		'?': 'question',
	'@': 'at',		'[': 'bracketleft',	'\\': 'backslash',
	']': 'bracketright',	'^': 'asciicircum',	'_': 'underscore',
	'`': 'grave',		'{': 'braceleft',	'|': 'bar',
	'}': 'braceright',	'~': 'asciitilde',	' ': 'space',
}

# Control characters that are NOT reported as Control-<letter>
_NOT_CONTROL = (8, 9, 10, 13, 27)


def isPrintableKey(key) -> bool:
	"""Return True if *key* is a printable ASCII character code."""
	return isinstance(key, int) and 32 <= key <= 126


def keysymOf(key) -> str:
	"""Return the tkinter keysym for the curses key code *key*."""
	if not isinstance(key, int):
		return str(key)
	if key in _SYMS:
		return _SYMS[key]
	if 33 <= key <= 126:
		ch = chr(key)
		return _PUNCT.get(ch, ch)
	if 1 <= key <= 26 and key not in _NOT_CONTROL:
		return chr(key + 96)		# Control-<letter> → letter keysym
	return f'Key-{key}'


class Event:
	"""Event object passed to all bound callbacks (attributes as in
	tkinter.Event; virtual events may carry extra ones)."""

	def __init__(self):
		self.widget	= None
		self.x		= 0
		self.y		= 0
		self.x_root	= 0
		self.y_root	= 0
		self.char	= ''
		self.keysym	= ''
		self.keycode	= 0
		self.num	= 0
		self.type	= ''
		self.state	= 0
		self.delta	= 0
		self.data	= None
		# remaining tkinter.Event attributes
		self.time	= int(_time.monotonic() * 1000) & 0xFFFFFFFF	# ms
		self.serial	= Event._serial = (Event._serial + 1) & 0xFFFFFFFF
		self.send_event	= False
		self.keysym_num	= 0
		self.focus	= False
		self.width	= 0
		self.height	= 0

	_serial = 0

	def __repr__(self):
		return f'<Event {self.type} keysym={self.keysym!r} x={self.x} y={self.y}>'


# Modifier state bits (tkinter values)
STATE_SHIFT	= 0x0001
STATE_CONTROL	= 0x0004
STATE_ALT	= 0x0008	# Mod1
STATE_MOD4	= 0x0040	# Super / Windows key

# Binding names of the modifiers, most common spelling first
_MOD_NAMES = (
	(STATE_CONTROL,	('Control',)),
	(STATE_ALT,	('Alt', 'Mod1')),
	(STATE_MOD4,	('Mod4', 'Super')),
	(STATE_SHIFT,	('Shift',)),
)


class ModKey(int):
	"""A special key pressed with modifiers (e.g. Super-Right): compares
	equal to its plain curses key code and carries the Tk state bits."""

	def __new__(cls, key, state):
		obj		= super().__new__(cls, key)
		obj.state	= state
		return obj

	def __repr__(self):
		return f'ModKey({int(self)}, {self.state:#x})'


def isModified(key) -> bool:
	"""True for a key carrying modifiers other than Shift: the widgets'
	class behaviour must not treat it as the plain key."""
	return isinstance(key, ModKey) and bool(key.state & ~STATE_SHIFT)


# xterm "1;<m>X" / "<n>;<m>~" sequences: final letter or number → key
_CSI_LETTER = {
	'A': curses.KEY_UP,	'B': curses.KEY_DOWN,
	'C': curses.KEY_RIGHT,	'D': curses.KEY_LEFT,
	'H': curses.KEY_HOME,	'F': curses.KEY_END,
	'P': curses.KEY_F1,	'Q': curses.KEY_F1 + 1,
	'R': curses.KEY_F1 + 2,	'S': curses.KEY_F1 + 3,
}
_CSI_TILDE = {
	1: curses.KEY_HOME,	2: curses.KEY_IC,	3: curses.KEY_DC,
	4: curses.KEY_END,	5: curses.KEY_PPAGE,	6: curses.KEY_NPAGE,
	7: curses.KEY_HOME,	8: curses.KEY_END,
	11: curses.KEY_F1,	12: curses.KEY_F1 + 1,	13: curses.KEY_F1 + 2,
	14: curses.KEY_F1 + 3,	15: curses.KEY_F1 + 4,	17: curses.KEY_F1 + 5,
	18: curses.KEY_F1 + 6,	19: curses.KEY_F1 + 7,	20: curses.KEY_F1 + 8,
	21: curses.KEY_F1 + 9,	23: curses.KEY_F1 + 10,	24: curses.KEY_F1 + 11,
}
# ncurses extended key names (TERM=xterm: kRIT5 = Control-Right …)
_EXT_NAMES = {
	'kUP': curses.KEY_UP,	'kDN': curses.KEY_DOWN,
	'kLFT': curses.KEY_LEFT,	'kRIT': curses.KEY_RIGHT,
	'kHOM': curses.KEY_HOME,	'kEND': curses.KEY_END,
	'kPRV': curses.KEY_PPAGE,	'kNXT': curses.KEY_NPAGE,
	'kIC': curses.KEY_IC,	'kDC': curses.KEY_DC,
}
_SHIFT_CODE = {
	curses.KEY_UP:		KEY_SHIFT_UP,	curses.KEY_DOWN:	KEY_SHIFT_DOWN,
	curses.KEY_LEFT:	KEY_SHIFT_LEFT,	curses.KEY_RIGHT:	KEY_SHIFT_RIGHT,
	curses.KEY_HOME:	KEY_SHIFT_HOME,	curses.KEY_END:		KEY_SHIFT_END,
	curses.KEY_PPAGE:	KEY_SHIFT_PPAGE,	curses.KEY_NPAGE:	KEY_SHIFT_NPAGE,
}


def _modifiedKey(key, mod):
	"""Return *key* with the xterm modifier parameter *mod* (1 + bits:
	1 Shift, 2 Alt, 4 Control, 8 Meta/Super)."""
	bits  = max(0, mod - 1)
	state = 0
	if bits & 1: state |= STATE_SHIFT
	if bits & 2: state |= STATE_ALT
	if bits & 4: state |= STATE_CONTROL
	if bits & 8: state |= STATE_MOD4
	if state == 0:
		return key
	if state == STATE_SHIFT and key in _SHIFT_CODE:
		return _SHIFT_CODE[key]		# keep the plain curses shift codes
	return ModKey(key, state)


# "other keys" code points of xterm modifyOtherKeys / kitty → curses key
_OTHER_KEYS = {
	13:	10,		# Return
	9:	9,		# Tab
	27:	27,		# Escape
	127:	127,		# BackSpace
	8:	127,
}


def _otherKey(code, mod):
	"""Key of an xterm modifyOtherKeys / kitty sequence: *code* is the
	unmodified character code, *mod* the xterm modifier parameter."""
	key = _OTHER_KEYS.get(code)
	if key is None:
		if not 32 <= code <= 126:
			return None
		key = code
	bits = max(0, mod - 1)
	if bits & ~0x5 == 0 and bits & 4 and chr(code).isalpha():
		# Control(-Shift)-letter: the plain control character (Tk
		# reports Control-Shift-a as Control-A)
		if bits & 1:
			return ModKey(ord(chr(code).upper()), STATE_CONTROL | STATE_SHIFT)
		ctrl = ord(chr(code).lower()) & 0x1f
		if ctrl in _NOT_CONTROL:	# Control-h/i/j/m are not BackSpace/Tab/Return
			return ModKey(ord(chr(code).lower()), STATE_CONTROL)
		return ctrl
	if bits == 1:
		if key == 9:
			return 353			# Shift-Tab → BackTab
		if 32 <= key <= 126:
			return key			# shifted character, already in *code*
	return _modifiedKey(key, mod)


# rxvt: ESC [a..d = Shift-arrows, ESC Oa..d = Control-arrows and
# ESC [<n>$ / ^ / @ = Shift / Control / Control-Shift <n>~ keys
_RXVT_ARROW = {
	'a': curses.KEY_UP,	'b': curses.KEY_DOWN,
	'c': curses.KEY_RIGHT,	'd': curses.KEY_LEFT,
}
_RXVT_MOD = {'$': 2, '^': 5, '@': 6}


def decodeEscape(seq: str):
	"""Decode the body of an escape sequence (the characters after ESC,
	e.g. '[1;9C') into a key, or None if it is not a known key.
	Besides the xterm cursor/function keys it understands the
	modifyOtherKeys forms 'CSI 27;<mod>;<code>~' and 'CSI <code>;<mod>u'
	(formatOtherKeys=1, kitty), e.g. Control-Return = '[13;5u'."""
	if len(seq) < 2 or seq[0] not in '[O':
		return None
	if seq[0] == '[' and seq[-1] == 'u':
		# kitty adds ':' sub-parameters (alternate keys, event type)
		params = [p.split(':')[0] for p in seq[1:-1].split(';')]
		try:
			code = int(params[0])
			mod  = int(params[1]) if len(params) > 1 and params[1] else 1
		except ValueError:
			return None
		return _otherKey(code, mod)
	final  = seq[-1]
	if len(seq) == 2 and final in _RXVT_ARROW:
		return _modifiedKey(_RXVT_ARROW[final], 2 if seq[0] == '[' else 5)
	if seq[0] == '[' and final in _RXVT_MOD and seq[1:-1].isdigit():
		num = int(seq[1:-1])
		if num not in _CSI_TILDE:
			return None
		return _modifiedKey(_CSI_TILDE[num], _RXVT_MOD[final])
	params = seq[1:-1].split(';') if len(seq) > 2 else []
	try:
		nums = [int(p) if p else 1 for p in params]
	except ValueError:
		return None
	mod = nums[1] if len(nums) > 1 else 1
	if seq[0] == 'O' and len(nums) == 1:
		mod = nums[0]			# SS3 form: ESC O 5 C
	if final in _CSI_LETTER:
		return _modifiedKey(_CSI_LETTER[final], mod)
	if final == '~' and len(nums) == 3 and nums[0] == 27:
		return _otherKey(nums[2], nums[1])
	if final == '~' and nums and nums[0] in _CSI_TILDE:
		return _modifiedKey(_CSI_TILDE[nums[0]], mod)
	return None


def decodeExtended(name: str):
	"""Decode an ncurses extended key name ('kRIT5') into a key, or None."""
	base = name.rstrip('0123456789')
	if base not in _EXT_NAMES or base == name:
		return None
	return _modifiedKey(_EXT_NAMES[base], int(name[len(base):]))


class KeyEvent(Event):
	def __init__(self, key):
		super().__init__()
		self.type	= 'KeyPress'
		self.keycode	= key
		self.keysym	= keysymOf(key)
		if isinstance(key, int):
			if 32 <= key <= 126:
				self.char = chr(key)
				if self.char.isupper():		# like Tk: J is Shift-j
					self.state = STATE_SHIFT
			elif key in (10, 13, curses.KEY_ENTER):
				self.char = '\r'
			elif key in (8, 127, curses.KEY_BACKSPACE):
				self.char = '\x08'
			elif key == 9:
				self.char = '\t'
			elif key == 27:
				self.char = '\x1b'
			elif 1 <= key <= 26:
				self.char  = chr(key)
				self.state = STATE_CONTROL
			if key in _SHIFTED:
				self.state = STATE_SHIFT
			if isinstance(key, ModKey):
				self.state = key.state
				if key.state & STATE_CONTROL and 64 <= key <= 126:
					self.char = chr(key & 0x1f)	# Control-A → '\x01'
		else:
			self.char = str(key)
		if len(self.char) == 1 and self.char.isprintable():
			self.keysym_num = ord(self.char)	# X keysym of a character

	def patterns(self) -> list:
		"""Return the binding strings this key matches, most specific first."""
		key	= self.keycode
		sym	= self.keysym
		result	= []
		if isModified(key):
			# every spelling and order of the modifiers, e.g. <Mod4-Right>
			# like Tk a binding may omit Shift (<Control-A> matches
			# Control-Shift-a), the fully specified one comes first
			states = [key.state]
			if key.state & STATE_SHIFT:
				states.append(key.state & ~STATE_SHIFT)
			for state in states:
				names = [n for bit, n in _MOD_NAMES if state & bit]
				for combo in _itertools.product(*names):
					for perm in _itertools.permutations(combo):
						mods = '-'.join(perm)
						result += [f'<{mods}-{sym}>',
							f'<{mods}-Key-{sym}>',
							f'<{mods}-KeyPress-{sym}>']
			return result + ['<Key>', '<KeyPress>']
		if self.state & STATE_CONTROL:
			result += [f'<Control-{sym}>', f'<Control-Key-{sym}>',
				f'<Control-KeyPress-{sym}>']
		elif self.state & STATE_SHIFT:
			base = _SHIFTED.get(key, sym)
			result += [f'<Shift-{base}>', f'<Shift-Key-{base}>',
				f'<Shift-KeyPress-{base}>']
			if key == 353:
				result += ['<ISO_Left_Tab>']
		result += [f'<{sym}>', f'<Key-{sym}>', f'<KeyPress-{sym}>']
		if isinstance(key, int) and 33 <= key <= 126 and chr(key) != '<':
			result.append(chr(key))		# bare-character binding, e.g. 'q'
		if key == curses.KEY_ENTER:
			result.append('<KP_Enter>')
		result += ['<Key>', '<KeyPress>']
		return result


# ---------------------------------------------------------------------------
# Mouse
# ---------------------------------------------------------------------------

B1_PRESS	= curses.BUTTON1_PRESSED
B1_RELEASE	= curses.BUTTON1_RELEASED
B1_CLICK	= curses.BUTTON1_CLICKED
B1_DCLICK	= curses.BUTTON1_DOUBLE_CLICKED
B1_TCLICK	= getattr(curses, 'BUTTON1_TRIPLE_CLICKED', 0)
B3_ANY		= (curses.BUTTON3_PRESSED | curses.BUTTON3_CLICKED |
		   curses.BUTTON3_RELEASED)
WHEEL_UP	= curses.BUTTON4_PRESSED
WHEEL_DOWN	= getattr(curses, 'BUTTON5_PRESSED', 0x200000)
MOTION		= curses.REPORT_MOUSE_POSITION
STATE_BUTTON1	= 0x0100	# Tk Button1Mask
B2_RELEASE	= curses.BUTTON2_RELEASED
B3_RELEASE	= curses.BUTTON3_RELEASED
B23_PRESS	= curses.BUTTON2_PRESSED | curses.BUTTON3_PRESSED
B23_RELEASE	= B2_RELEASE | B3_RELEASE


def buttonMask(num) -> int:
	"""Tk Button<num>Mask state bit of mouse button 1..5 (0 otherwise)."""
	return STATE_BUTTON1 << (num - 1) if 1 <= num <= 5 else 0

# curses modifier bits of a mouse event -> Tk state bits
_MOUSE_MODIFIERS = (
	(getattr(curses, 'BUTTON_SHIFT', 0),	STATE_SHIFT),
	(getattr(curses, 'BUTTON_CTRL', 0),	STATE_CONTROL),
	(getattr(curses, 'BUTTON_ALT', 0),	STATE_ALT),
)


def mouseState(bstate) -> int:
	"""Tk event.state (modifier bits) of a curses mouse bstate.
	The raw bstate must not leak out: BUTTON1_CLICKED (0x4) is Tk's
	Control bit and BUTTON1_RELEASED (0x1) its Shift bit."""
	state = 0
	for bit, tkBit in _MOUSE_MODIFIERS:
		if bit and bstate & bit:
			state |= tkBit
	return state


def isPress(bstate) -> bool:
	"""Button-1 went down (or a full click was reported)."""
	return bool(bstate & (B1_PRESS | B1_CLICK | B1_DCLICK | B1_TCLICK))


def isRelease(bstate) -> bool:
	"""Button-1 went up (or a full click was reported)."""
	return bool(bstate & (B1_RELEASE | B1_CLICK | B1_DCLICK | B1_TCLICK))


def isWheel(bstate) -> int:
	"""Return -1 for wheel up, +1 for wheel down, 0 otherwise."""
	if bstate & WHEEL_UP:
		return -1
	if WHEEL_DOWN and bstate & WHEEL_DOWN:
		return 1
	return 0


class MouseEvent(Event):
	def __init__(self, x, y, bstate):
		super().__init__()
		self.x		= x
		self.y		= y
		self.x_root	= x
		self.y_root	= y
		self.bstate	= bstate		# raw curses button state
		self.state	= mouseState(bstate)
		self.type	= 'ButtonPress'
		if bstate & B1_PRESS:
			self.num = 1
		elif bstate & (B1_RELEASE | B1_CLICK | B1_DCLICK):
			self.num  = 1
			self.type = 'ButtonRelease' if bstate & B1_RELEASE else 'ButtonPress'
		elif bstate & (curses.BUTTON2_PRESSED | curses.BUTTON2_CLICKED):
			self.num = 2
		elif bstate & B2_RELEASE:
			self.num  = 2
			self.type = 'ButtonRelease'
		elif bstate & B3_ANY:
			self.num = 3
			if bstate & B3_RELEASE:
				self.type = 'ButtonRelease'
		wheel = isWheel(bstate)
		if wheel:
			self.num   = 4 if wheel < 0 else 5
			self.delta = -120 * wheel
		if bstate & MOTION and not (bstate & (B1_RELEASE | B1_CLICK)):
			self.type = 'Motion'
		# like Tk the release (but not the press) reports the button down
		if self.type == 'ButtonRelease':
			self.state |= buttonMask(self.num)
