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
"""System clipboard for the text (STRING) format of the tktext clipboard.

The backend is chosen once by platform; TKTEXT_CLIPBOARD overrides it:
auto, macos, windows, wayland, xclip, xsel, wsl, osc52, none.
OSC 52 can only copy (the terminal decides whether it accepts it)."""
import os
import sys
import base64
import shutil
import subprocess

_backend = None		# chosen backend name (lazy)

# command lines: name -> (copy, paste)
_COMMANDS = {
	'macos':	(['pbcopy'],				['pbpaste']),
	'wayland':	(['wl-copy'],				['wl-paste', '-n']),
	'xclip':	(['xclip', '-selection', 'clipboard', '-i'],
			 ['xclip', '-selection', 'clipboard', '-o']),
	'xsel':		(['xsel', '--clipboard', '--input'],
			 ['xsel', '--clipboard', '--output']),
	'wsl':		(['clip.exe'],
			 ['powershell.exe', '-NoProfile', '-Command', 'Get-Clipboard']),
}

_BACKENDS = ('macos', 'windows', 'wayland', 'xclip', 'xsel', 'wsl', 'osc52', 'none')


# -----------------------------------------------------------------------------
def _isWsl() -> bool:
	try:
		with open('/proc/version') as f:
			return 'microsoft' in f.read().lower()
	except OSError:
		return False


# -----------------------------------------------------------------------------
def _hasTool(name: str) -> bool:
	return shutil.which(_COMMANDS[name][0][0]) is not None


# -----------------------------------------------------------------------------
def _detect() -> str:
	"""The first backend available on this system."""
	if sys.platform == 'darwin' and _hasTool('macos'):
		return 'macos'
	if sys.platform == 'win32':
		return 'windows'
	if os.environ.get('WAYLAND_DISPLAY') and _hasTool('wayland'):
		return 'wayland'
	if os.environ.get('DISPLAY'):
		for name in ('xclip', 'xsel'):
			if _hasTool(name):
				return name
	if _isWsl() and _hasTool('wsl'):
		return 'wsl'
	return 'osc52'


# -----------------------------------------------------------------------------
def backend(name: str = None) -> str:
	"""Get (or set with *name*) the backend in use."""
	global _backend
	if name is not None:
		_backend = name
		return name
	if _backend is None:
		env = os.environ.get('TKTEXT_CLIPBOARD', 'auto').lower()
		_backend = env if env in _BACKENDS else _detect()
	return _backend


# -----------------------------------------------------------------------------
def _env() -> dict:
	"""pbcopy/pbpaste use the locale encoding: force UTF-8."""
	env = dict(os.environ)
	if backend() == 'macos' and 'UTF-8' not in env.get('LANG', '').upper():
		env['LANG'] = 'en_US.UTF-8'
	return env


# -----------------------------------------------------------------------------
def osc52(text: str, term: str = None, screen: bool = None) -> bytes:
	"""The OSC 52 sequence setting the clipboard to *text*; under GNU screen
	wrapped in a DCS passthrough (screen does not forward OSC 52)."""
	data = base64.b64encode(text.encode('utf-8'))
	seq  = b'\x1b]52;c;' + data + b'\x07'
	term   = os.environ.get('TERM', '') if term is None else term
	screen = bool(os.environ.get('STY')) if screen is None else screen
	if screen or term.startswith('screen'):
		seq = b'\x1bP' + seq + b'\x1b\\'
	return seq


# -----------------------------------------------------------------------------
def copy(text: str) -> bool:
	"""Put *text* on the system clipboard. @return True on success."""
	name = backend()
	try:
		if name == 'none':
			return False
		if name == 'windows':
			return _winCopy(text)
		if name == 'osc52':
			if not os.isatty(1):
				return False
			os.write(1, osc52(text))
			return True
		data = text.encode('utf-16-le' if name == 'wsl' else 'utf-8')
		# the X11/Wayland tools fork a server and return: DEVNULL keeps
		# them from holding our pipes open
		subprocess.run(_COMMANDS[name][0], input=data, env=_env(),
			stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
			timeout=1, check=True)
		return True
	except (OSError, subprocess.SubprocessError, ValueError):
		return False


# -----------------------------------------------------------------------------
def paste() -> str | None:
	"""The text on the system clipboard, None when it cannot be read."""
	name = backend()
	try:
		if name in ('none', 'osc52'):
			return None
		if name == 'windows':
			return _winPaste()
		res = subprocess.run(_COMMANDS[name][1], env=_env(),
			stdin=subprocess.DEVNULL, capture_output=True, timeout=0.5)
		if res.returncode != 0:
			return ''	# empty or no owner
		text = res.stdout.decode('utf-8', 'replace')
		if name == 'wsl':
			text = text.replace('\r\n', '\n')
			if text.endswith('\n'):
				text = text[:-1]	# Get-Clipboard adds one
		return text
	except (OSError, subprocess.SubprocessError, ValueError):
		return None


# -----------------------------------------------------------------------------
# Windows: Win32 clipboard API with ctypes (CF_UNICODETEXT)
# -----------------------------------------------------------------------------
_CF_UNICODETEXT	= 13
_GMEM_MOVEABLE	= 0x0002


def _winApi():
	import ctypes
	from ctypes import wintypes
	user32	 = ctypes.WinDLL('user32', use_last_error=True)
	kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
	user32.OpenClipboard.argtypes		= [wintypes.HWND]
	user32.OpenClipboard.restype		= wintypes.BOOL
	user32.GetClipboardData.argtypes	= [wintypes.UINT]
	user32.GetClipboardData.restype		= wintypes.HANDLE
	user32.SetClipboardData.argtypes	= [wintypes.UINT, wintypes.HANDLE]
	user32.SetClipboardData.restype		= wintypes.HANDLE
	kernel32.GlobalAlloc.argtypes		= [wintypes.UINT, ctypes.c_size_t]
	kernel32.GlobalAlloc.restype		= wintypes.HGLOBAL
	kernel32.GlobalLock.argtypes		= [wintypes.HGLOBAL]
	kernel32.GlobalLock.restype		= wintypes.LPVOID
	kernel32.GlobalUnlock.argtypes		= [wintypes.HGLOBAL]
	kernel32.GlobalFree.argtypes		= [wintypes.HGLOBAL]
	return ctypes, user32, kernel32


def _winCopy(text: str) -> bool:
	ctypes, user32, kernel32 = _winApi()
	data = (text.replace('\r\n', '\n').replace('\n', '\r\n') + '\0').encode('utf-16-le')
	if not user32.OpenClipboard(None):
		return False
	try:
		user32.EmptyClipboard()
		handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(data))
		if not handle:
			return False
		ptr = kernel32.GlobalLock(handle)
		ctypes.memmove(ptr, data, len(data))
		kernel32.GlobalUnlock(handle)
		if not user32.SetClipboardData(_CF_UNICODETEXT, handle):
			kernel32.GlobalFree(handle)
			return False
		return True		# the clipboard owns the memory now
	finally:
		user32.CloseClipboard()


def _winPaste() -> str | None:
	ctypes, user32, kernel32 = _winApi()
	if not user32.OpenClipboard(None):
		return None
	try:
		handle = user32.GetClipboardData(_CF_UNICODETEXT)
		if not handle:
			return ''
		ptr = kernel32.GlobalLock(handle)
		try:
			return ctypes.wstring_at(ptr).replace('\r\n', '\n')
		finally:
			kernel32.GlobalUnlock(handle)
	finally:
		user32.CloseClipboard()
