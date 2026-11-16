"""Button-2/3 drags and pixel-mode <Configure> sizes."""
import curses
import unittest

from fakescreen import makeApp, attach, tk
from tktext import _core

MOTION = curses.REPORT_MOUSE_POSITION


class ButtonDragTest(unittest.TestCase):

	def setUp(self):
		self.root, self.scr = makeApp(40, 12)
		self.a = tk.Frame(self.root, width=10, height=5)
		self.b = tk.Frame(self.root, width=10, height=5)
		self.a.pack(side='left')
		self.b.pack(side='left')
		attach(self.root)
		self.events = []
		for w, name in ((self.a, 'a'), (self.b, 'b')):
			for seq in ('<Button-2>', '<B2-Motion>', '<ButtonRelease-2>',
					'<Button-3>', '<B3-Motion>', '<ButtonRelease-3>', '<Motion>'):
				w.bind(seq, lambda e, n=name, s=seq:
					self.events.append((n, s, e.num, e.state & 0x700, e.type)))

	def mouse(self, x, y, bstate):
		self.root._onMouse(x + self.a._x, y + self.a._y, bstate)

	def test_middleDrag(self):
		self.mouse(1, 1, curses.BUTTON2_PRESSED)
		self.mouse(3, 1, MOTION)
		self.mouse(15, 2, MOTION)		# over b: still to a
		self.mouse(15, 2, curses.BUTTON2_RELEASED)
		self.assertEqual([e[:2] for e in self.events], [
			('a', '<Button-2>'), ('a', '<B2-Motion>'),
			('a', '<B2-Motion>'), ('a', '<ButtonRelease-2>')])
		self.assertEqual(self.events[1][3], 0x200)		# Button2Mask
		self.assertEqual(self.events[3][2:], (2, 0x200, 'ButtonRelease'))
		self.events.clear()
		self.mouse(15, 2, MOTION)		# drag over: plain motion on b
		self.assertEqual(self.events, [('b', '<Motion>', self.events[0][2], 0, 'Motion')])

	def test_rightDrag(self):
		self.mouse(1, 1, curses.BUTTON3_PRESSED)
		self.mouse(2, 2, MOTION)
		self.mouse(2, 2, curses.BUTTON3_RELEASED)
		self.assertEqual([e[:2] for e in self.events], [
			('a', '<Button-3>'), ('a', '<B3-Motion>'), ('a', '<ButtonRelease-3>')])
		self.assertEqual(self.events[1][3], 0x400)

	def test_button1StillNormal(self):
		self.a.bind('<B1-Motion>', lambda e: self.events.append(('a', 'B1', e.state & 0x700)))
		self.mouse(1, 1, curses.BUTTON1_PRESSED)
		self.mouse(2, 1, MOTION)
		self.mouse(2, 1, curses.BUTTON1_RELEASED)
		self.assertIn(('a', 'B1', 0x100), self.events)


class MotionCompressionTest(unittest.TestCase):

	def setUp(self):
		self.root, self.scr = makeApp(40, 12)
		self.a = tk.Frame(self.root, width=20, height=8)
		self.a.pack()
		attach(self.root)
		self.events = []
		for seq in ('<Button-1>', '<B1-Motion>', '<ButtonRelease-1>'):
			self.a.bind(seq, lambda e, s=seq: self.events.append((s, e.x, e.y)))

	def sgr(self, b, x, y, final='M'):
		self.scr.keys.extend([27] + [ord(c) for c in
			f'[<{b};{x + self.a._x + 1};{y + self.a._y + 1}{final}'])

	def dispatch(self):
		root = self.root
		while self.scr.keys or root._pendingKeys:
			root._handleInput(root._readKey(self.scr))

	def test_burstDeliversLastMotion(self):
		self.sgr(0, 1, 1)			# press
		for x in range(2, 8):
			self.sgr(32, x, 1)		# B1 drag reports
		self.sgr(0, 7, 1, 'm')			# release
		self.dispatch()
		self.assertEqual([e[0] for e in self.events],
			['<Button-1>', '<B1-Motion>', '<ButtonRelease-1>'])
		self.assertEqual(self.events[1][1:], (7, 1))

	def test_keyStopsCompression(self):
		self.sgr(0, 1, 1)
		self.sgr(32, 2, 1)
		self.scr.keys.append(ord('q'))
		self.sgr(32, 3, 1)
		self.sgr(0, 3, 1, 'm')
		self.dispatch()
		self.assertEqual([e[1:] for e in self.events if e[0] == '<B1-Motion>'],
			[(2, 1), (3, 1)])


class ConfigurePixelTest(unittest.TestCase):

	def setUp(self):
		_core.setPixelMode(8, 16)

	def tearDown(self):
		_core.setPixelMode(1, 1)

	def test_configureReportsPixels(self):
		root, scr = makeApp(40, 12)
		f = tk.Frame(root, width=160, height=48)	# 20 x 3 cells
		f.pack()
		seen = []
		f.bind('<Configure>', lambda e: seen.append((e.width, e.height)))
		attach(root)
		root.update()
		self.assertEqual(seen[-1], (f.winfo_width(), f.winfo_height()))
		self.assertEqual(seen[-1], (160, 48))


if __name__ == '__main__':
	unittest.main()
