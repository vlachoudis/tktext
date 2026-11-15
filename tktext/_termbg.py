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
# Date:   13-Nov-2026
#
# Detect the background colour of the terminal: dark or light.
#
# Order: TKTEXT_BACKGROUND (or install(background=)) -> TERM=linux (always
# dark) -> ask the terminal with OSC 11 -> $COLORFGBG -> unknown (None).
# The OSC 11 query must run before curses.initscr(), otherwise the reply is
# read as key presses.

import os
import re
import select
import time

try:
	import termios
	import tty
except ImportError:		# not POSIX
	termios = None

from ._colors import _BASIC_RGB

QUERY_TIMEOUT	= 0.5		# seconds to wait for the terminal's reply (DA1 ends it earlier)

_override	= 'auto'	# install(background=…): 'auto', 'dark', 'light', '#rrggbb'
_cached		= False		# detection done
_background	= None		# detected (r, g, b) or None

_OSC_RE = re.compile(rb'\x1b\]11;rgb:([0-9a-fA-F]{1,4})/([0-9a-fA-F]{1,4})/([0-9a-fA-F]{1,4})')
_DA1_RE = re.compile(rb'\x1b\[\?[0-9;]*c')


def parseOscReply(data: bytes):
	"""(r, g, b) 0..255 from an OSC 11 reply ('ESC]11;rgb:RRRR/GGGG/BBBB'
	ended by ST or BEL), or None."""
	m = _OSC_RE.search(data)
	if m is None:
		return None
	rgb = []
	for h in m.groups():
		v = int(h, 16)
		rgb.append(round(v * 255 / ((1 << (4 * len(h))) - 1)))
	return tuple(rgb)


def parseColorFgBg(value: str):
	"""(r, g, b) of the background in $COLORFGBG ('fg;bg' or
	'fg;default;bg'), or None."""
	if not value:
		return None
	bg = value.split(';')[-1].strip()
	if not bg.isdigit():
		return None
	n = int(bg)
	if not 0 <= n < 16:
		return None
	return _BASIC_RGB[n]


def parseSpec(spec):
	"""(r, g, b) of 'dark', 'light' or '#rrggbb'; None for 'auto'/''."""
	spec = str(spec or '').strip().lower()
	if spec in ('', 'auto'):
		return None
	if spec == 'dark':
		return (0, 0, 0)
	if spec == 'light':
		return (255, 255, 255)
	if re.fullmatch(r'#[0-9a-f]{6}', spec):
		return tuple(int(spec[i:i + 2], 16) for i in (1, 3, 5))
	raise ValueError(f'background must be auto, dark, light or #rrggbb: {spec!r}')


def queryTerminal(timeout: float = QUERY_TIMEOUT):
	"""Ask the controlling terminal for its background colour (OSC 11).
	A DA1 request is sent after it: every terminal answers DA1, so when
	that reply comes first the terminal does not know OSC 11 and we stop
	without waiting for the timeout.  Returns (r, g, b) or None."""
	if termios is None:
		return None
	try:
		fd = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
	except OSError:
		return None
	try:
		try:
			saved = termios.tcgetattr(fd)
		except termios.error:
			return None
		try:
			tty.setcbreak(fd, termios.TCSANOW)	# also turns echo off
			os.write(fd, b'\x1b]11;?\x1b\\\x1b[c')
			data = bytearray()
			end  = time.monotonic() + timeout
			while True:
				left = end - time.monotonic()
				if left <= 0:
					break
				r, _, _ = select.select([fd], [], [], left)
				if not r:
					break
				chunk = os.read(fd, 1024)
				if not chunk:
					break
				data.extend(chunk)
				if _DA1_RE.search(data):
					break
			return parseOscReply(bytes(data))
		finally:
			termios.tcsetattr(fd, termios.TCSAFLUSH, saved)
	except OSError:
		return None
	finally:
		os.close(fd)


def detect():
	"""Run the detection (no cache).  Returns (r, g, b) or None."""
	try:
		rgb = parseSpec(os.environ.get('TKTEXT_BACKGROUND') or _override)
	except ValueError:		# a bad environment value: detect
		rgb = parseSpec(_override)
	if rgb is not None:
		return rgb
	if os.environ.get('TERM') == 'linux':
		return (0, 0, 0)
	try:
		isTty = os.isatty(0) and os.isatty(1)
	except (OSError, ValueError):
		isTty = False
	if isTty:
		rgb = queryTerminal()
		if rgb is not None:
			return rgb
	return parseColorFgBg(os.environ.get('COLORFGBG', ''))


def terminalBackground():
	"""Background colour of the terminal as (r, g, b) 0..255, or None
	when it cannot be found.  Detected once; call it before the screen
	starts (Tk() does it) since the terminal is asked through the tty."""
	global _cached, _background
	if not _cached:
		_background = detect()
		_cached     = True
	return _background


def isDark(rgb) -> bool:
	if rgb is None:
		return True		# the usual terminal default
	r, g, b = rgb
	return 0.299 * r + 0.587 * g + 0.114 * b < 128


def isDarkTerminal() -> bool:
	"""True for a dark (or unknown) terminal background."""
	return isDark(terminalBackground())


def setOverride(spec) -> None:
	"""install(background=…): 'auto', 'dark', 'light' or '#rrggbb'."""
	global _override, _cached
	parseSpec(spec)			# validate
	_override = str(spec or 'auto')
	_cached   = False
