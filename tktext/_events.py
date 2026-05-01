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
	curses.KEY_DC:		'Delete',
	curses.KEY_IC:		'Insert',
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


class Event:
	"""Event object passed to all bound callbacks."""
	__slots__ = ('widget', 'x', 'y', 'char', 'keysym', 'keycode',
				'num', 'type', 'state', 'delta')

	def __init__(self):
		self.widget	= None
		self.x		= 0
		self.y		= 0
		self.char	= ''
		self.keysym	= ''
		self.keycode	= 0
		self.num	= 0
		self.type	= ''
		self.state	= 0
		self.delta	= 0


class KeyEvent(Event):
	def __init__(self, key):
		super().__init__()
		self.type = 'KeyPress'
		self.keycode = key
		if isinstance(key, int):
			self.keysym = _SYMS.get(key, f'Key-{key}')
			if 32 <= key <= 126:
				self.char = chr(key)
		else:
			self.char = str(key)
			self.keysym = str(key)


class MouseEvent(Event):
	def __init__(self, x, y, bstate):
		super().__init__()
		self.x = x
		self.y = y
		self.state = bstate
		self.type = 'ButtonPress'
		if bstate & curses.BUTTON1_PRESSED:
			self.num = 1
		elif bstate & curses.BUTTON1_RELEASED:
			self.num = 1
			self.type = 'ButtonRelease'
		elif bstate & curses.BUTTON1_CLICKED:
			self.num = 1
			self.type = 'ButtonRelease'
		elif bstate & curses.BUTTON2_CLICKED:
			self.num = 2
		elif bstate & curses.BUTTON3_CLICKED:
			self.num = 3
		if bstate & curses.BUTTON4_PRESSED:
			self.delta = -3
		if bstate & curses.BUTTON5_PRESSED:
			self.delta = 3
