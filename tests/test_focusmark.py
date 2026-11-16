"""Focus mark: reversed outline of a focused widget that does not show the focus."""
import curses
import unittest

from fakescreen import makeApp, attach, tk


class FocusMarkTest(unittest.TestCase):
	def setUp(self):
		self.root, self.scr = makeApp(40, 12)
		self.frame = tk.Frame(self.root, width=20, height=6)
		self.frame.pack()
		self.canvas = tk.Canvas(self.frame, width=10, height=4)
		self.canvas.pack()
		attach(self.root)
		self.root._update(force=True)

	def tearDown(self):
		self.root.destroy()

	def reversed(self, w):
		return any(self.scr.attrs[w._y + i][w._x] & curses.A_REVERSE
			for i in range(w._height))

	def redraw(self):
		self.root._dirty = True
		self.root._update(force=True)

	def test_focusedFrameNotMarked(self):
		# a container given the focus by focus_set() shows no ring, like Tk
		self.frame.focus_set()
		self.redraw()
		self.assertFalse(self.reversed(self.frame))

	def test_focusedFrameWithTakefocusMarked(self):
		self.frame.configure(takefocus=1)
		self.frame.focus_set()
		self.redraw()
		self.assertTrue(self.reversed(self.frame))

	def test_focusedCanvasMarked(self):
		self.canvas.focus_set()
		self.redraw()
		self.assertTrue(self.reversed(self.canvas))

	def test_explicitMarkOnFrame(self):
		tk.focusMark(self.root, self.frame)
		self.redraw()
		self.assertTrue(self.reversed(self.frame))
		tk.focusMark(self.root, None)
		self.redraw()
		self.assertFalse(self.reversed(self.frame))


if __name__ == '__main__':
	unittest.main()
