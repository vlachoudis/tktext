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
	'gray':		0,	'grey':		0,
	'purple':	5,	'violet':	5,
	'orange':	3,	'brown':	1,
	'navy':		4,	'teal':		6,
	'lime':		2,	'aqua':		6,
	'fuchsia':	5,	'maroon':	1,
	'olive':	3,	'silver':	7,
	'darkblue':	4,	'darkgreen':	2,
	'darkred':	1,	'darkgray':	0,
}


class ColorManager:
	"""Maps color name pairs to curses color pair numbers."""

	def __init__(self):
		self._pairs = {}
		self._next = 1
		self._ready = False

	def init(self):
		curses.start_color()
		try:
			curses.use_default_colors()
		except curses.error:
			pass
		self._ready = True

	def _resolve(self, name):
		if not name:
			return -1
		n = name.lower().strip()
		if n.startswith('#'):
			try:
				r = int(n[1:3], 16)
				g = int(n[3:5], 16)
				b = int(n[5:7], 16)
				basics = [
					(0,0,0),(128,0,0),(0,128,0),(128,128,0),
					(0,0,128),(128,0,128),(0,128,128),(192,192,192),
				]
				best, bestD = 0, float('inf')
				for i, (br, bg, bb) in enumerate(basics):
					d = (r-br)**2 + (g-bg)**2 + (b-bb)**2
					if d < bestD:
						bestD, best = d, i
				return best
			except (ValueError, IndexError):
				return -1
		return _NAMES.get(n, 7)

	def getAttr(self, fg='', bg='', bold=False, reverse=False,
			underline=False, dim=False, blink=False):
		if not self._ready:
			attr = 0
		else:
			key = (fg or '', bg or '')
			if key not in self._pairs:
				maxPairs = min(curses.COLOR_PAIRS - 1, 255)
				if self._next > maxPairs:
					pn = 1
				else:
					pn = self._next
					self._next += 1
					try:
						curses.init_pair(pn, self._resolve(fg), self._resolve(bg))
					except curses.error:
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
