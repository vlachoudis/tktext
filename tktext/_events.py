import curses

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
	KEY_SHIFT_UP:		'Shift_Up',
	KEY_SHIFT_DOWN:		'Shift_Down',
	KEY_SHIFT_LEFT:		'Shift_Left',
	KEY_SHIFT_RIGHT:	'Shift_Right',
	KEY_SHIFT_HOME:		'Shift_Home',
	KEY_SHIFT_END:		'Shift_End',
	KEY_SHIFT_PPAGE:	'Shift_Prior',
	KEY_SHIFT_NPAGE:	'Shift_Next',
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

	def __repr__(self):
		return f'<Event {self.type} keysym={self.keysym!r} x={self.x} y={self.y}>'


# Modifier state bits (tkinter values)
STATE_SHIFT	= 0x0001
STATE_CONTROL	= 0x0004


class KeyEvent(Event):
	def __init__(self, key):
		super().__init__()
		self.type	= 'KeyPress'
		self.keycode	= key
		self.keysym	= keysymOf(key)
		if isinstance(key, int):
			if 32 <= key <= 126:
				self.char = chr(key)
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
		else:
			self.char = str(key)

	def patterns(self) -> list:
		"""Return the binding strings this key matches, most specific first."""
		key	= self.keycode
		sym	= self.keysym
		result	= []
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
		self.state	= bstate
		self.type	= 'ButtonPress'
		if bstate & B1_PRESS:
			self.num = 1
		elif bstate & (B1_RELEASE | B1_CLICK | B1_DCLICK):
			self.num  = 1
			self.type = 'ButtonRelease' if bstate & B1_RELEASE else 'ButtonPress'
		elif bstate & (curses.BUTTON2_PRESSED | curses.BUTTON2_CLICKED):
			self.num = 2
		elif bstate & B3_ANY:
			self.num = 3
		wheel = isWheel(bstate)
		if wheel:
			self.num   = 4 if wheel < 0 else 5
			self.delta = -120 * wheel
		if bstate & MOTION and not (bstate & (B1_RELEASE | B1_CLICK)):
			self.type = 'Motion'
