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

# X11 colour names (beyond the basic ones) used by Tk programs
_X11 = {
	'white': (255, 255, 255), 'black': (0, 0, 0), 'red': (255, 0, 0),
	'green': (0, 255, 0), 'blue': (0, 0, 255), 'yellow': (255, 255, 0),
	'cyan': (0, 255, 255), 'magenta': (255, 0, 255), 'gray': (190, 190, 190),
	'grey': (190, 190, 190), 'lightgray': (211, 211, 211),
	'lightgrey': (211, 211, 211), 'darkgray': (169, 169, 169),
	'darkgrey': (169, 169, 169), 'dimgray': (105, 105, 105),
	'lightyellow': (255, 255, 224), 'lightblue': (173, 216, 230),
	'lightgreen': (144, 238, 144), 'lightcyan': (224, 255, 255),
	'lightpink': (255, 182, 193), 'lightcoral': (240, 128, 128),
	'lightsalmon': (255, 160, 122), 'lightsteelblue': (176, 196, 222),
	'lightskyblue': (135, 206, 250), 'lightgoldenrodyellow': (250, 250, 210),
	'darkred': (139, 0, 0), 'darkgreen': (0, 100, 0), 'darkblue': (0, 0, 139),
	'darkcyan': (0, 139, 139), 'darkmagenta': (139, 0, 139),
	'darkorange': (255, 140, 0), 'darkviolet': (148, 0, 211),
	'darkkhaki': (189, 183, 107), 'darkolivegreen': (85, 107, 47),
	'darkslategray': (47, 79, 79), 'darkslateblue': (72, 61, 139),
	'navy': (0, 0, 128), 'navyblue': (0, 0, 128), 'orange': (255, 165, 0),
	'pink': (255, 192, 203), 'brown': (165, 42, 42), 'purple': (160, 32, 240),
	'violet': (238, 130, 238), 'gold': (255, 215, 0), 'khaki': (240, 230, 140),
	'beige': (245, 245, 220), 'ivory': (255, 255, 240), 'linen': (250, 240, 230),
	'snow': (255, 250, 250), 'wheat': (245, 222, 179), 'tan': (210, 180, 140),
	'salmon': (250, 128, 114), 'coral': (255, 127, 80), 'tomato': (255, 99, 71),
	'chocolate': (210, 105, 30), 'firebrick': (178, 34, 34),
	'maroon': (176, 48, 96), 'orchid': (218, 112, 214), 'plum': (221, 160, 221),
	'turquoise': (64, 224, 208), 'aquamarine': (127, 255, 212),
	'skyblue': (135, 206, 235), 'steelblue': (70, 130, 180),
	'royalblue': (65, 105, 225), 'dodgerblue': (30, 144, 255),
	'cornflowerblue': (100, 149, 237), 'slateblue': (106, 90, 205),
	'slategray': (112, 128, 144), 'seagreen': (46, 139, 87),
	'forestgreen': (34, 139, 34), 'limegreen': (50, 205, 50),
	'yellowgreen': (154, 205, 50), 'olivedrab': (107, 142, 35),
	'palegreen': (152, 251, 152), 'springgreen': (0, 255, 127),
	'lawngreen': (124, 252, 0), 'goldenrod': (218, 165, 32),
	'indianred': (205, 92, 92), 'hotpink': (255, 105, 180),
	'deeppink': (255, 20, 147), 'mediumpurple': (147, 112, 219),
	'lavender': (230, 230, 250), 'mintcream': (245, 255, 250),
	'honeydew': (240, 255, 240), 'azure': (240, 255, 255),
	'aliceblue': (240, 248, 255), 'ghostwhite': (248, 248, 255),
	'whitesmoke': (245, 245, 245), 'gainsboro': (220, 220, 220),
	'seashell': (255, 245, 238), 'oldlace': (253, 245, 230),
	'cornsilk': (255, 248, 220), 'lemonchiffon': (255, 250, 205),
	'moccasin': (255, 228, 181), 'peachpuff': (255, 218, 185),
	'bisque': (255, 228, 196), 'mistyrose': (255, 228, 225),
	'sienna': (160, 82, 45), 'peru': (205, 133, 63),
	'saddlebrown': (139, 69, 19), 'rosybrown': (188, 143, 143),
	'silver': (192, 192, 192), 'teal': (0, 128, 128), 'olive': (128, 128, 0),
	'lime': (0, 255, 0), 'aqua': (0, 255, 255), 'fuchsia': (255, 0, 255),
	'systembuttonface': (217, 217, 217), 'systemwindow': (255, 255, 255),
	'systemwindowtext': (0, 0, 0), 'systembuttontext': (0, 0, 0),
}


def _x11(name):
	"""RGB of an X11 colour name ('gray75', 'green3' …) or None."""
	if name in _X11:
		return _X11[name]
	for prefix in ('gray', 'grey'):
		if name.startswith(prefix) and name[len(prefix):].isdigit():
			v = round(int(name[len(prefix):]) * 255 / 100)
			return (v, v, v)
	base = name.rstrip('1234')
	if base != name and base in _X11:
		k = {'1': 1.0, '2': 0.932, '3': 0.804, '4': 0.545}[name[-1]]
		return tuple(int(c * k) for c in _X11[base])
	return None


def _rgb256(r, g, b):
	"""Nearest xterm-256 colour index (6x6x6 cube or grey ramp)."""
	def cube(v):
		return 0 if v < 48 else (1 if v < 115 else (v - 35) // 40)
	cr, cg, cb = cube(r), cube(g), cube(b)
	steps = (0, 95, 135, 175, 215, 255)
	cubeRGB = (steps[cr], steps[cg], steps[cb])
	grey  = min(23, max(0, round(((r + g + b) / 3 - 8) / 10)))
	greyV = 8 + 10 * grey
	dCube = sum((a - c) ** 2 for a, c in zip((r, g, b), cubeRGB))
	dGrey = sum((a - greyV) ** 2 for a in (r, g, b))
	if dGrey < dCube:
		return 232 + grey
	return 16 + 36 * cr + 6 * cg + cb


_BASIC_RGB = [
	(0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0),
	(0, 0, 238), (205, 0, 205), (0, 205, 205), (229, 229, 229),
	(127, 127, 127), (255, 0, 0), (0, 255, 0), (255, 255, 0),
	(92, 92, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
]


# Colour mode.  'tk' renders every colour as given.  'terminal' renders the
# palette default colours (Tk's gray background, white entry/list fields,
# black text and whatever the program installs with tk_setPalette()) with
# the terminal's own default colours (curses -1).
_colorMode		= 'tk'
_defaultBackgrounds	= set()		# RGB tuples mapped to the terminal bg
_defaultForegrounds	= set()		# RGB tuples mapped to the terminal fg
_colorGeneration	= 0		# bumped on every change (cache key)
_TK_DEFAULT_BG		= ('#d9d9d9', '#ffffff')
_TK_DEFAULT_FG		= ('#000000',)


def _bump():
	global _colorGeneration
	_colorGeneration += 1


def setColorMode(mode: str) -> None:
	"""Select 'terminal' (palette defaults -> terminal colours) or 'tk'."""
	global _colorMode
	mode = str(mode).lower()
	if mode not in ('terminal', 'tk'):
		raise ValueError(f'unknown colour mode {mode!r}')
	_colorMode = mode
	if mode == 'terminal':
		addDefaultColors(_TK_DEFAULT_BG, _TK_DEFAULT_FG)
	_bump()


def colorMode() -> str:
	return _colorMode


def addDefaultColors(backgrounds=(), foregrounds=()) -> None:
	"""Register palette colours rendered as the terminal defaults in
	'terminal' mode (single names or sequences)."""
	for names, target in ((backgrounds, _defaultBackgrounds),
			(foregrounds, _defaultForegrounds)):
		if isinstance(names, str):
			names = (names,)
		for name in names or ():
			rgb = ColorManager.toRGB(name) if name else None
			if rgb is not None:
				target.add(tuple(rgb))
	_bump()


def resetDefaultColors() -> None:
	"""Forget all palette default colours (tests)."""
	_defaultBackgrounds.clear()
	_defaultForegrounds.clear()
	if _colorMode == 'terminal':
		addDefaultColors(_TK_DEFAULT_BG, _TK_DEFAULT_FG)
	_bump()


class ColorManager:
	"""Maps color name pairs to curses color pair numbers."""

	def __init__(self):
		self._pairs	= {}
		self._next	= 1
		self._ready	= False
		self._nColors	= 8
		self._mapCache	= {}
		self._mapGen	= -1

	def mapDefaults(self, fg, bg):
		"""In 'terminal' mode return (fg, bg) with the palette default
		colours replaced by '' (terminal default).  The foreground is
		only replaced when the background is, so that e.g. black text
		on an explicit yellow background keeps its colour."""
		if _colorMode != 'terminal':
			return fg, bg
		if self._mapGen != _colorGeneration:
			self._mapCache.clear()
			self._mapGen = _colorGeneration
		key = (fg, bg)
		result = self._mapCache.get(key)
		if result is None:
			result = key
			if not bg or self._rgbIn(bg, _defaultBackgrounds):
				if fg and self._rgbIn(fg, _defaultForegrounds):
					fg = ''
				result = (fg, '')
			self._mapCache[key] = result
		return result

	@staticmethod
	def _rgbIn(name, colors):
		if isinstance(name, int):
			return False
		rgb = ColorManager.toRGB(name)
		return rgb is not None and tuple(rgb) in colors

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
		if self._nColors >= 256:
			rgb = self.toRGB(n)
			if rgb is not None:
				return _rgb256(*rgb)
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
		if n in _NAMES:
			return _NAMES[n]
		rgb = _x11(n)
		if rgb is None:
			return -1
		return self._resolve('#%02x%02x%02x' % rgb)

	@staticmethod
	def toRGB(name):
		"""Return (r, g, b) 0..255 for a colour name or #rgb value, or None."""
		n = str(name).lower().strip().replace(' ', '')
		if n.startswith('#'):
			h = n[1:]
			try:
				if len(h) == 3:
					return tuple(int(c * 2, 16) for c in h)
				if len(h) == 6:
					return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
				if len(h) == 12:
					return tuple(int(h[i:i+2], 16) for i in (0, 4, 8))
			except ValueError:
				return None
			return None
		rgb = _x11(n)
		if rgb is not None:
			return rgb
		if n in _BRIGHT:
			return _BASIC_RGB[_BRIGHT[n][0]]
		if n.startswith('light') and n[5:] in _NAMES:
			return _BASIC_RGB[_NAMES[n[5:]] + 8]
		if n in _NAMES:
			return _BASIC_RGB[_NAMES[n]]
		return None

	def getAttr(self, fg='', bg='', bold=False, reverse=False,
			underline=False, dim=False, blink=False):
		attr = 0
		if self._ready:
			key = self.mapDefaults(fg or '', bg or '')
			if key not in self._pairs:
				maxPairs = min(getattr(curses, 'COLOR_PAIRS', 64) - 1, 255)
				if key == ('', ''):
					pn = 0
				elif self._next > maxPairs:
					pn = 0
				else:
					pn = self._next
					try:
						# the pair is shared by every colour with the same
						# mapped key: build it from the key, not from fg/bg
						curses.init_pair(pn, self._resolve(key[0]),
							self._resolve(key[1]))
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
