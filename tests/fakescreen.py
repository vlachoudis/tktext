"""A minimal in-memory stand-in for a curses window, used by the tests.

It mimics the parts of curses behaviour that matter for rendering bugs:
addstr() wraps onto the next line at the right edge and raises
curses.error when writing past the last cell.
"""
import curses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tktext as tk		# noqa: E402


class FakeScreen:
	def __init__(self, width=80, height=24):
		self.width	= width
		self.height	= height
		self.cursor	= (0, 0)
		self.keys	= []
		self.erase()

	# ---- curses window API used by tktext ----
	def getmaxyx(self):
		return (self.height, self.width)

	def erase(self):
		self.chars = [[' '] * self.width for _ in range(self.height)]
		self.attrs = [[0] * self.width for _ in range(self.height)]

	clear = erase

	def addstr(self, y, x, s, attr=0):
		if not (0 <= y < self.height and 0 <= x < self.width):
			raise curses.error('addwstr() returned ERR')
		for ch in s:
			if x >= self.width:
				x  = 0
				y += 1
				if y >= self.height:
					raise curses.error('addwstr() returned ERR')
			self.chars[y][x] = ch
			self.attrs[y][x] = attr
			x += 1
		if y == self.height - 1 and x >= self.width:
			raise curses.error('addwstr() returned ERR')

	def addch(self, y, x, ch, attr=0):
		self.addstr(y, x, ch if isinstance(ch, str) else chr(ch), attr)

	def move(self, y, x):
		self.cursor = (y, x)

	def refresh(self):
		pass

	def keypad(self, flag):
		pass

	def nodelay(self, flag):
		pass

	def timeout(self, ms):
		pass

	def getch(self):
		# An exhausted key queue behaves like Ctrl-C so that a modal loop
		# under test can never hang.
		if not self.keys:
			raise KeyboardInterrupt
		return self.keys.pop(0)

	def resize(self, width, height):
		self.width  = width
		self.height = height
		self.erase()

	# ---- helpers for assertions ----
	def row(self, y) -> str:
		return ''.join(self.chars[y])

	def text(self) -> str:
		return '\n'.join(self.row(y).rstrip() for y in range(self.height))

	def find(self, s):
		"""Return (y, x) of the first occurrence of *s*, or None."""
		for y in range(self.height):
			x = self.row(y).find(s)
			if x >= 0:
				return (y, x)
		return None


def makeApp(width=80, height=24):
	"""Create a Tk root attached to a FakeScreen (no real terminal)."""
	root = tk.Tk()
	scr  = FakeScreen(width, height)
	root._fakeScr = scr
	return root, scr


def attach(root):
	root._attach(root._fakeScr, initCurses=False)


def press(root, *keys):
	"""Send keys (ints or str characters) through the app and redraw."""
	for k in keys:
		if isinstance(k, str):
			for ch in k:
				root._onKey(ord(ch))
		else:
			root._onKey(k)
		root._fireAfterCallbacks()
		root._update()


def click(root, x, y, button='click'):
	"""Simulate a mouse click: 'click', 'press', 'release', 'double', 'motion'."""
	states = {
		'click':	curses.BUTTON1_CLICKED,
		'press':	curses.BUTTON1_PRESSED,
		'release':	curses.BUTTON1_RELEASED,
		'double':	curses.BUTTON1_DOUBLE_CLICKED,
		'motion':	curses.REPORT_MOUSE_POSITION,
		'wheelup':	curses.BUTTON4_PRESSED,
		'wheeldown':	getattr(curses, 'BUTTON5_PRESSED', 0x200000),
	}
	root._onMouse(x, y, states[button])
	root._fireAfterCallbacks()
	root._update()
