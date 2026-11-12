import curses

_NAMES = {
	'black':	0,
	'red':		1,
	'green':	2,
	'yellow':	3,
	'blue':		4,
	'magenta':	5,
	'cyan':		6,
	'white':	7,
	'purple':	5,	'violet':	5,
	'orange':	3,	'brown':	1,
	'navy':		4,	'teal':		6,
	'lime':		2,	'aqua':		6,
	'fuchsia':	5,	'maroon':	1,
	'olive':	3,	'silver':	7,
	'darkblue':	4,	'darkgreen':	2,
	'darkred':	1,	'darkcyan':	6,
	'darkmagenta':	5,	'darkyellow':	3,
	'gold':		3,	'pink':		5,
}

# Names that map to the bright half of a 16-colour palette (fallback when
# the terminal only has 8 colours)
_BRIGHT = {
	'gray':		(8, 7),		'grey':		(8, 7),
	'darkgray':	(8, 7),		'darkgrey':	(8, 7),
	'lightgray':	(7, 7),		'lightgrey':	(7, 7),
	'brightblack':	(8, 7),
	'brightred':	(9, 1),		'lightred':	(9, 1),
	'brightgreen':	(10, 2),	'lightgreen':	(10, 2),
	'brightyellow':	(11, 3),	'lightyellow':	(11, 3),
	'brightblue':	(12, 4),	'lightblue':	(12, 4),
	'brightmagenta':(13, 5),	'lightmagenta':	(13, 5),
	'brightcyan':	(14, 6),	'lightcyan':	(14, 6),
	'brightwhite':	(15, 7),
}

_BASIC_RGB = [
	(0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0),
	(0, 0, 238), (205, 0, 205), (0, 205, 205), (229, 229, 229),
	(127, 127, 127), (255, 0, 0), (0, 255, 0), (255, 255, 0),
	(92, 92, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
]


class ColorManager:
	"""Maps color name pairs to curses color pair numbers."""

	def __init__(self):
		self._pairs	= {}
		self._next	= 1
		self._ready	= False
		self._nColors	= 8

	def init(self):
		"""Initialise colours.  Safe on monochrome terminals."""
		self._pairs = {}
		self._next  = 1
		try:
			if not curses.has_colors():
				return
			curses.start_color()
		except curses.error:
			return
		try:
			curses.use_default_colors()
		except curses.error:
			pass
		self._nColors	= getattr(curses, 'COLORS', 8)
		self._ready	= True

	def _resolve(self, name):
		if name is None or name == '':
			return -1
		if isinstance(name, int):
			return name if name < self._nColors else -1
		n = str(name).lower().strip().replace(' ', '')
		if n.startswith('#'):
			try:
				hexpart = n[1:]
				if len(hexpart) == 3:
					r, g, b = (int(c * 2, 16) for c in hexpart)
				else:
					r = int(hexpart[0:2], 16)
					g = int(hexpart[2:4], 16)
					b = int(hexpart[4:6], 16)
			except (ValueError, IndexError):
				return -1
			limit = 16 if self._nColors >= 16 else 8
			best, bestD = 0, float('inf')
			for i, (br, bg, bb) in enumerate(_BASIC_RGB[:limit]):
				d = (r - br)**2 + (g - bg)**2 + (b - bb)**2
				if d < bestD:
					bestD, best = d, i
			return best
		if n in _BRIGHT:
			bright, dull = _BRIGHT[n]
			return bright if self._nColors >= 16 else dull
		if n.startswith('light') and n[5:] in _NAMES:
			base = _NAMES[n[5:]]
			return base + 8 if self._nColors >= 16 else base
		return _NAMES.get(n, -1)

	def getAttr(self, fg='', bg='', bold=False, reverse=False,
			underline=False, dim=False, blink=False):
		attr = 0
		if self._ready:
			key = (fg or '', bg or '')
			if key not in self._pairs:
				maxPairs = min(getattr(curses, 'COLOR_PAIRS', 64) - 1, 255)
				if key == ('', ''):
					pn = 0
				elif self._next > maxPairs:
					pn = 0
				else:
					pn = self._next
					try:
						curses.init_pair(pn, self._resolve(fg), self._resolve(bg))
						self._next += 1
					except (curses.error, ValueError):
						pn = 0
				self._pairs[key] = pn
			attr = curses.color_pair(self._pairs[key])
		if bold:
			attr |= curses.A_BOLD
		if reverse:
			attr |= curses.A_REVERSE
		if underline:
			attr |= curses.A_UNDERLINE
		if dim:
			attr |= curses.A_DIM
		if blink:
			attr |= curses.A_BLINK
		return attr
