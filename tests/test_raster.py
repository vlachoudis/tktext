"""Raster images (rasterImage) drawn with half-blocks."""
import curses
import unittest

from fakescreen import makeApp, attach, tk
from tktext import _raster
from tktext._raster import RasterRenderer, quantize, HALF, RASTER_FIRST, \
	RASTER_LAST, MARKER_PAIR


def solid(width, height, rgb):
	return bytes(rgb) * (width * height)


def stripes(width, height):
	"""Every pixel row a different colour."""
	data = bytearray()
	for y in range(height):
		data += bytes(((y * 37) % 256, (y * 91) % 256, (y * 13) % 256)) * width
	return bytes(data)


class FakeColors:
	_ready		= True
	_nColors	= 256


class PairScreen:
	"""Records init_pair/color_pair without a curses screen."""

	def __init__(self, renderer):
		self.pairs = {}
		renderer._definePair = self.define
		renderer._pairAttr   = lambda pair: pair << 8

	def define(self, pair, fg, bg):
		self.pairs[pair] = (fg, bg)


def colorRenderer():
	r = RasterRenderer(FakeColors(), 'curses')
	r.colored = True
	return r, PairScreen(r)


class InchScreen:
	"""FakeScreen-like window keeping chtype attributes for inch()."""

	def __init__(self, width, height):
		self.width, self.height = width, height
		self.cells = {}

	def getmaxyx(self):
		return (self.height, self.width)

	def addstr(self, y, x, s, attr=0):
		for i, ch in enumerate(s):
			self.cells[(y, x+i)] = (ch, attr)

	def inch(self, y, x):
		ch, attr = self.cells.get((y, x), (' ', 0))
		return (ord(ch) & 0xff) | attr

	def idcok(self, flag):
		pass


class TestQuantize(unittest.TestCase):

	def test_withinBudget(self):
		cells = [(1, 2), (1, 2), (3, 4)]
		out, combos = quantize(cells, 10)
		self.assertEqual(out, cells)
		self.assertEqual(combos, [(1, 2), (3, 4)])

	def test_nearestWhenOverBudget(self):
		# 196 (red) is common, 160 (dark red) rare: it maps to red, not to blue
		cells = [(196, 196)] * 10 + [(21, 21)] * 8 + [(160, 160)]
		out, combos = quantize(cells, 2)
		self.assertEqual(len(combos), 2)
		self.assertEqual(out[-1], (196, 196))

	def test_noBudget(self):
		out, combos = quantize([(1, 2)], 0)
		self.assertEqual(combos, [(-1, -1)])


class TestRasterWidget(unittest.TestCase):

	def setUp(self):
		self.root, self.scr = makeApp(20, 10)
		self.frame = tk.Frame(self.root)
		self.frame.pack(fill='both', expand=True)
		attach(self.root)

	def test_size(self):
		cols, rows = self.frame.rasterSize()
		self.assertEqual((cols, rows), (20, 18))	# title bar takes a row

	def test_monochromeShades(self):
		cols, rows = self.frame.rasterSize()
		self.frame.rasterImage(solid(cols, rows, (255, 255, 255)), cols, rows)
		self.root.update()
		self.assertEqual(self.scr.row(5), '█' * 20)
		self.frame.rasterImage(solid(cols, rows, (0, 0, 0)), cols, rows)
		self.root.update()
		self.assertEqual(self.scr.row(5).strip(), '')

	def test_clear(self):
		cols, rows = self.frame.rasterSize()
		self.frame.rasterImage(solid(cols, rows, (255, 255, 255)), cols, rows)
		self.assertIsNotNone(self.frame.rasterImage())
		self.frame.rasterImage(b'')
		self.root.update()
		self.assertIsNone(self.frame.rasterImage())
		self.assertNotIn('█', self.scr.text())

	def test_staleSizeStaysInside(self):
		# a raster bigger than the widget (before a resize) is sampled down
		inner = tk.Frame(self.frame, width=5, height=3)
		inner.place(x=0, y=0)
		self.root.update()
		inner.rasterImage(solid(100, 100, (255, 255, 255)), 100, 100)
		self.root.update()
		self.assertEqual(self.scr.row(1), '█' * 5 + ' ' * 15)
		self.assertEqual(self.scr.row(4).strip(), '')

	def test_tooShort(self):
		with self.assertRaises(tk.TclError):
			self.frame.rasterImage(b'abc', 10, 10)

	def test_tinyWidget(self):
		inner = tk.Frame(self.frame, width=8, height=1)
		inner.place(x=0, y=0)
		self.root.update()
		self.assertEqual(inner.rasterSize(), (8, 2))
		inner.rasterImage(solid(4, 4, (255, 255, 255)), 4, 4)
		inner.place_configure(height=0)
		self.root.update()		# unmapped: must not raise
		self.assertNotIn('█', self.scr.text())


class TestCursesRenderer(unittest.TestCase):

	def test_halfBlocksAndPairs(self):
		r, pairs = colorRenderer()
		scr = InchScreen(10, 4)
		w = tk.Frame(tk.Tk())
		w._rasterData = (stripes(10, 8), 10, 8)
		r.beginFrame(1)
		r.render(scr, w, 0, 0, 4, 10)
		self.assertTrue(all(scr.cells[(y, x)][0] == HALF
				for y in range(4) for x in range(10)))
		self.assertEqual(len(pairs.pairs), 4)		# one combo per row
		self.assertTrue(all(RASTER_FIRST <= p <= RASTER_LAST for p in pairs.pairs))

	def test_budgetShared(self):
		r, pairs = colorRenderer()
		scr  = InchScreen(10, 200)
		app  = tk.Tk()
		a, b = tk.Frame(app), tk.Frame(app)
		for w in (a, b):
			w._rasterData = (stripes(10, 400), 10, 400)
		r.beginFrame(2)
		r.render(scr, a, 0, 0, 200, 10)
		first = len(pairs.pairs)
		r.render(scr, b, 0, 0, 200, 10)
		budget = RASTER_LAST - RASTER_FIRST + 1
		self.assertLessEqual(first, budget // 2)
		self.assertLessEqual(len(pairs.pairs), budget)


class TestTruecolor(unittest.TestCase):

	def setUp(self):
		self.r, self.pairs = colorRenderer()
		self.r.mode   = 'truecolor'
		self.r.active = True
		self.out = []
		self.r.write = self.out.append
		self.scr = InchScreen(6, 3)
		self.w = tk.Frame(tk.Tk())
		self.w._rasterData = (solid(6, 6, (10, 20, 30)), 6, 6)

	def frame(self, overlay=None):
		self.r.beginFrame(1)
		self.r.render(self.scr, self.w, 0, 0, 3, 6)
		if overlay:
			self.scr.addstr(overlay[0], overlay[1], 'X', 1 << 8)
		self.r.flush(self.scr)
		return b''.join(self.out).decode()

	def test_emitOnlyChanges(self):
		text = self.frame()
		self.assertEqual(text.count(HALF), 18)
		self.assertIn('38;2;10;20;30;48;2;10;20;30m', text)
		self.assertTrue(text.startswith('\0337') and text.endswith('\0338'))
		self.out.clear()
		self.assertEqual(self.frame(), '')		# nothing changed

	def test_overlayClipped(self):
		self.frame()
		self.out.clear()
		self.assertEqual(self.frame(overlay=(1, 2)), '')
		self.out.clear()
		# overlay closed: curses repaints the marker, the cell is re-emitted
		text = self.frame()
		self.assertEqual(text.count(HALF), 1)
		self.assertIn('\033[2;3H', text)

	def test_invalidate(self):
		self.frame()
		self.out.clear()
		self.r.invalidate()
		self.assertEqual(self.frame().count(HALF), 18)

	def test_markerAttr(self):
		self.frame()
		self.assertEqual(self.scr.cells[(0, 0)][1], MARKER_PAIR << 8)


class TestMode(unittest.TestCase):

	def test_auto(self):
		import os
		saved = dict(os.environ)
		try:
			os.environ.pop('TKTEXT_GRAPHICS', None)
			os.environ['COLORTERM'] = 'truecolor'
			self.assertEqual(_raster.graphicsMode('auto'), 'truecolor')
			os.environ['COLORTERM'] = ''
			self.assertEqual(_raster.graphicsMode('auto'), 'curses')
			with self.assertRaises(ValueError):
				_raster.graphicsMode('sixel')
		finally:
			os.environ.clear()
			os.environ.update(saved)


if __name__ == '__main__':
	unittest.main()
