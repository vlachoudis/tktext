"""End-to-end tests: run real curses programs inside a pseudo terminal."""
import os
import select
import signal
import struct
import sys
import time
import unittest

try:
	import fcntl
	import pty
	import termios
except ImportError:		# not POSIX
	pty = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# keys as an xterm in application-cursor mode (ncurses keypad) sends them
UP, DOWN, RIGHT, LEFT = '\x1bOA', '\x1bOB', '\x1bOC', '\x1bOD'
TAB, BTAB, ENTER, ESC = '\t', '\x1b[Z', '\r', '\x1b'


def mouseClick(x, y):
	"""SGR (1006) press + release at 0-based screen cell (x, y)."""
	return [f'\x1b[<0;{x + 1};{y + 1}M', f'\x1b[<0;{x + 1};{y + 1}m']


def runInPty(argv, keys, cols=110, rows=36, delay=0.15, timeout=10.0,
		term='xterm-256color'):
	pid, fd = pty.fork()
	if pid == 0:
		os.environ['TERM'] = term
		os.chdir(ROOT)
		os.execvp(argv[0], argv)
	fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
	out = bytearray()

	def drain(t):
		end = time.time() + t
		while time.time() < end:
			r, _, _ = select.select([fd], [], [], 0.05)
			if r:
				try:
					data = os.read(fd, 65536)
				except OSError:
					return
				if not data:
					return
				out.extend(data)

	drain(1.0)
	for k in keys:
		if k == 'RESIZE':
			fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 15, 50, 0, 0))
			os.kill(pid, signal.SIGWINCH)
		else:
			os.write(fd, k.encode())
		drain(delay)
	end = time.time() + timeout
	status = None
	while time.time() < end:
		drain(0.1)
		wpid, st = os.waitpid(pid, os.WNOHANG)
		if wpid:
			status = os.waitstatus_to_exitcode(st)
			break
	if status is None:
		os.kill(pid, signal.SIGKILL)
		os.waitpid(pid, 0)
	drain(0.2)
	os.close(fd)
	return status, out.decode('utf-8', 'replace')


@unittest.skipIf(pty is None, 'needs a POSIX pseudo terminal')
class TerminalTest(unittest.TestCase):

	def test_demo_session(self):
		keys  = [DOWN, DOWN, TAB, RIGHT, TAB, 'typed text', ENTER]
		keys += [TAB, TAB, ' ', TAB, RIGHT, TAB, DOWN]
		keys += mouseClick(5, 32) + [DOWN, DOWN, RIGHT, ENTER]	# popup menu
		keys += mouseClick(48, 3)				# Widgets tab
		keys += ['RESIZE', ESC, '\x1b[21~']		# F10 quits the demo
		code, out = runInPty([sys.executable, 'demo.py'], keys)
		self.assertNotIn('Traceback', out)
		self.assertEqual(code, 0)

	def test_ctrl_c_and_callback_errors(self):
		script = ('import sys; sys.path.insert(0, %r)\n'
			'import tktext as tk\n'
			'root = tk.Tk()\n'
			'tk.Button(root, text="boom", command=lambda: 1/0).pack()\n'
			'root.mainloop()\n'
			'print("MAINLOOP-RETURNED")\n') % ROOT
		code, out = runInPty([sys.executable, '-c', script],
			[ENTER, ENTER, '\x03'])
		self.assertEqual(code, 0)
		self.assertIn('MAINLOOP-RETURNED', out)
		self.assertIn('ZeroDivisionError', out)


	def test_output_while_running_is_deferred(self):
		"""print()/stderr output during the session must not be written
		over the curses screen; it is shown after the terminal is restored."""
		script = ('import sys, os; sys.path.insert(0, %r)\n'
			'import tktext as tk\n'
			'root = tk.Tk()\n'
			'tk.Label(root, text="hello").pack()\n'
			'def chatter():\n'
			'	print("PRINTED-STDOUT")\n'
			'	print("PRINTED-STDERR", file=sys.stderr)\n'
			'	os.write(2, b"FD2-STDERR\\n")\n'
			'root.after(100, chatter)\n'
			'root.after(600, root.quit)\n'
			'root.mainloop()\n') % ROOT
		code, out = runInPty([sys.executable, '-c', script], [''] * 4)
		self.assertEqual(code, 0)
		end = out.rfind('\x1b[?1049l')		# leaving the alternate screen
		self.assertGreater(end, 0)
		for text in ('PRINTED-STDOUT', 'PRINTED-STDERR', 'FD2-STDERR'):
			self.assertGreater(out.find(text), end, text)

	def test_drag_motion(self):
		"""curses enables only the press/release mouse tracking: tktext
		turns on ?1002 so that <B1-Motion> fires while dragging (flair
		InputEditor tab markers), in the SGR and in the X10 encoding."""
		script = ('import sys; sys.path.insert(0, %r)\n'
			'import tktext as tk\n'
			'root = tk.Tk()\n'
			'lbl = tk.Label(root, text="V")\n'
			'lbl.place(x=4, y=2)\n'
			'got = []\n'
			'lbl.bind("<Button-1>", lambda e: got.append("press"))\n'
			'lbl.bind("<B1-Motion>", lambda e: got.append(e.x_root))\n'
			'lbl.bind("<ButtonRelease-1>", lambda e: root.after(100, root.quit))\n'
			'root.mainloop()\n'
			'print("GOT", got)\n') % ROOT
		x10 = lambda b, x, y: '\x1b[M' + chr(32 + b) + chr(33 + x) + chr(33 + y)
		for term, seq in (
				('xterm-256color', lambda b, x, y, up='M':
					f'\x1b[<{b};{x + 1};{y + 1}{up}'),
				('screen-256color', lambda b, x, y, up='M':
					x10(3 if up == 'm' else b, x, y))):
			with self.subTest(term=term):
				keys = [seq(0, 4, 3), seq(32, 6, 3), seq(32, 9, 3),
					seq(0, 9, 3, 'm')]
				code, out = runInPty([sys.executable, '-c', script], keys,
					term=term)
				self.assertEqual(code, 0)
				self.assertGreater(out.find('\x1b[?1002h'),
					out.find('1000h'))
				self.assertIn("GOT ['press', 6, 9]", out)


def queryInPty(reply, timeout=5.0):
	"""Run tktext's terminal background query in a pty whose 'terminal'
	(this process) answers the OSC 11 query with *reply* (None: it does
	not know OSC 11) and DA1 always.  Returns (child output, seconds)."""
	script = ('import sys, time; sys.path.insert(0, %r)\n'
		'from tktext import _termbg\n'
		't = time.monotonic()\n'
		'rgb = _termbg.terminalBackground()\n'
		'print("RESULT", rgb, _termbg.isDarkTerminal(), '
		'round(time.monotonic() - t, 3))\n') % ROOT
	pid, fd = pty.fork()
	if pid == 0:
		os.environ['TERM'] = 'xterm-256color'
		os.environ.pop('TKTEXT_BACKGROUND', None)
		os.environ.pop('COLORFGBG', None)
		os.execvp(sys.executable, [sys.executable, '-c', script])
	out      = bytearray()
	answered = False
	end      = time.time() + timeout
	while time.time() < end:
		r, _, _ = select.select([fd], [], [], 0.05)
		if not r:
			continue
		try:
			data = os.read(fd, 4096)
		except OSError:
			break
		if not data:
			break
		out.extend(data)
		if not answered and b'\x1b[c' in out:
			answered = True
			if reply is not None:
				os.write(fd, b'\x1b]11;' + reply + b'\x1b\\')
			os.write(fd, b'\x1b[?62;22c')
	os.waitpid(pid, 0)
	os.close(fd)
	return out.decode('utf-8', 'replace')


FLAIR = os.path.join(ROOT, 'flair', 'flair.py')


@unittest.skipIf(pty is None, 'needs a POSIX pseudo terminal')
class TerminalBackgroundTest(unittest.TestCase):

	def result(self, out):
		line = next(l for l in out.splitlines() if 'RESULT ' in l)
		return line.split('RESULT ', 1)[1].strip()

	def test_light_terminal(self):
		out = queryInPty(b'rgb:ffff/ffff/ffff')
		self.assertTrue(self.result(out).startswith('(255, 255, 255) False'), out)

	def test_dark_terminal(self):
		out = queryInPty(b'rgb:1e1e/1e1e/2e2e')
		self.assertTrue(self.result(out).startswith('(30, 30, 46) True'), out)

	def test_no_osc11_stops_at_da1(self):
		out = queryInPty(None)
		res = self.result(out)
		self.assertTrue(res.startswith('None True'), out)
		self.assertLess(float(res.split()[-1]), 0.14)	# did not wait the timeout


@unittest.skipIf(pty is None or not os.path.exists(FLAIR),
	'needs a POSIX pseudo terminal and a flair checkout in flair/')
class FlairTest(unittest.TestCase):
	"""flair --text: start, accept the licence, close the update dialog
	and quit with Ctrl-C (the main window's WM_DELETE_WINDOW)."""

	def test_flair_text_session(self):
		import tempfile
		with tempfile.TemporaryDirectory() as tmp:
			os.environ['PYTHONPATH'] = ROOT
			argv  = [sys.executable, FLAIR, '--text', '-s',
				'-i', os.path.join(tmp, 'flair.ini')]
			keys  = [''] * 10			# let flair start
			keys += ['\x1b[6~'] * 30		# page down the licence
			keys += [TAB, TAB, ENTER, '', '', ESC, '', '', '\x03', '', '']
			code, out = runInPty(argv, keys, cols=120, rows=40,
				delay=0.3, timeout=20)
		self.assertNotIn('Traceback', out)
		self.assertIn('\x1b[?1049l', out)		# terminal restored
		self.assertEqual(code, 0)


if __name__ == '__main__':
	unittest.main()
