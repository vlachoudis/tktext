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

"""Emulation of the Tcl interpreter object (widget.tk) of tkinter.

tkinter applications occasionally talk to Tcl directly through
``widget.tk.call(...)`` / ``widget.tk.eval(...)``.  There is no Tcl here, so
the few commands such code uses are mapped onto the tktext widgets; harmless
look-and-feel commands are accepted and ignored; anything else raises
TclError so that callers wrapped in ``try/except TclError`` keep working.
"""

import re

from ._core import TclError


# global variables every Tcl/Tk interpreter defines (values of Tk 8.6.18)
_TCL_GLOBALS = {
	'tcl_version':		'8.6',
	'tcl_patchLevel':	'8.6.18',
	'tk_version':		'8.6',
	'tk_patchLevel':	'8.6.18',
	'tcl_interactive':	'0',
	'tcl_precision':	0,
	'tk_strictMotif':	0,
	'tcl_library':		'',
	'tk_library':		'',
}


def _nameToWidget(path, root=None):
	"""Return the widget with Tk path name *path* (or the widget itself)."""
	from . import _core
	if not isinstance(path, str):
		return path
	if root is None:
		root = _core._defaultRoot
	if root is None:
		raise TclError(f'bad window path name "{path}"')
	if path in ('', '.'):
		return root
	w = root
	for name in path.strip('.').split('.'):
		w = w.children.get(name)
		if w is None:
			raise TclError(f'bad window path name "{path}"')
	return w


def _splitlist(value):
	"""Split a Tcl list string into a tuple (braces and quotes honoured)."""
	if isinstance(value, (tuple, list)):
		return tuple(value)
	if value is None:
		return ()
	s      = str(value)
	result = []
	i      = 0
	n      = len(s)
	while i < n:
		while i < n and s[i].isspace():
			i += 1
		if i >= n:
			break
		if s[i] == '{':
			depth = 1
			j     = i + 1
			while j < n and depth:
				if s[j] == '{':
					depth += 1
				elif s[j] == '}':
					depth -= 1
				j += 1
			result.append(s[i + 1:j - 1])
			i = j
		elif s[i] == '"':
			j = s.find('"', i + 1)
			j = n if j < 0 else j
			result.append(s[i + 1:j])
			i = j + 1
		else:
			j = i
			while j < n and not s[j].isspace():
				j += 1
			result.append(s[i:j])
			i = j
	return tuple(result)


class TclShim:
	"""Stand-in for the tkapp object returned by widget.tk."""

	def __init__(self, root=None):
		self._root	= root		# the Tk application (one interpreter each)
		self._commands	= {}
		self._vars	= dict(_TCL_GLOBALS)
		self._renamed	= {}		# 'rename'd widget command -> widget
		self._hidden	= set()		# widget paths renamed away

	# ------------------------------------------------------------------
	# Conversion helpers (tkapp API)
	# ------------------------------------------------------------------

	def splitlist(self, value):
		return _splitlist(value)

	split = splitlist

	def getboolean(self, value):
		if isinstance(value, str):
			v = value.strip().lower()
			if v in ('1', 'true', 'yes', 'on'):
				return True
			if v in ('0', 'false', 'no', 'off', ''):
				return False
			raise TclError(f'expected boolean value but got "{value}"')
		return bool(value)

	def getint(self, value):
		try:
			return int(value)
		except (TypeError, ValueError):
			raise TclError(f'expected integer but got "{value}"')

	def getdouble(self, value):
		try:
			return float(value)
		except (TypeError, ValueError):
			raise TclError(f'expected floating-point number but got "{value}"')

	def exprboolean(self, value):
		return self.getboolean(value)

	def wantobjects(self, *a):
		return True

	def interpaddr(self):
		return 0

	def willdispatch(self):
		pass

	def dooneevent(self, flags=0):
		return 0

	def mainloop(self, n=0):
		from . import _core
		root = self._root or _core._defaultRoot
		if root is not None:
			root.mainloop(n)

	def _widget(self, path):
		return _nameToWidget(path, self._root)

	# ------------------------------------------------------------------
	# Commands and variables
	# ------------------------------------------------------------------

	def createcommand(self, name, func):
		self._commands[name] = func

	def deletecommand(self, name):
		self._commands.pop(name, None)

	def getvar(self, name):
		if name not in self._vars:
			raise TclError(f'can\'t read "{name}": no such variable')
		return self._vars[name]

	def setvar(self, name, value='1'):
		self._vars[name] = value

	def unsetvar(self, name):
		self._vars.pop(name, None)

	globalgetvar	= getvar
	globalsetvar	= setvar
	globalunsetvar	= unsetvar

	def createfilehandler(self, *a):
		raise TclError('file handlers are not supported by tktext')

	def deletefilehandler(self, *a):
		pass

	# ------------------------------------------------------------------

	def eval(self, script):
		words = _splitlist(script)
		if not words:
			return ''
		return self.call(*words)

	def call(self, *args):
		if len(args) == 1 and isinstance(args[0], (tuple, list)):
			args = tuple(args[0])
		args = tuple(a for a in args if a is not None)	# as _tkinter does
		if not args:
			return ''
		cmd  = str(args[0])
		rest = args[1:]
		if cmd in self._commands:
			return self._commands[cmd](*rest)
		if cmd in self._renamed:
			# the original widget command: the class methods, not the
			# instance attributes that mask them (idlelib WidgetRedirector)
			return self._widgetCommand(self._renamed[cmd], rest, True)
		if cmd in self._hidden:
			raise TclError(f'invalid command name "{cmd}"')
		if cmd.startswith('.') or not isinstance(args[0], str):
			return self._widgetCommand(self._widget(args[0]), rest)
		handler = _COMMANDS.get(cmd.lstrip(':'))
		if handler is None:
			raise TclError(f'invalid command name "{cmd}"')
		return handler(self, *rest)

	# ------------------------------------------------------------------

	def _redirected(self, widget) -> bool:
		"""True if the command of widget was replaced by a Python one
		(rename + createcommand), so its edits must go through tk.call"""
		return str(widget) in self._commands

	def _rename(self, old, new):
		"""rename oldName newName: a widget command or a created command;
		an empty newName deletes the command"""
		old = str(old)
		new = str(new)
		if new and (new in self._commands or new in self._renamed):
			raise TclError(f'can\'t rename to "{new}": command already exists')
		if old in self._commands:
			func = self._commands.pop(old)
			if new:
				self._commands[new] = func
			return ''
		if old in self._renamed:
			widget = self._renamed.pop(old)
		elif old not in self._hidden:
			widget = self._widget(old)
			self._hidden.add(old)
		else:
			raise TclError(f'can\'t rename "{old}": command doesn\'t exist')
		if new == str(widget):
			self._hidden.discard(new)
		elif new:
			self._renamed[new] = widget
		return ''

	def _widgetCommand(self, widget, args, classMethods=False):
		if not args:
			raise TclError('wrong # args')
		sub  = str(args[0])
		rest = args[1:]
		if sub == 'tag' and rest and hasattr(widget, 'tag_has'):
			op = str(rest[0])
			if op == 'names':
				return widget._tagNames() if hasattr(widget, '_tagNames') else ()
			if op == 'add':
				return widget._tagAdd(rest[1], _splitlist(rest[2]))
			if op == 'remove':
				items = _splitlist(rest[2]) if len(rest) > 2 else None
				return widget._tagRemove(rest[1], items)
		if sub in ('configure', 'config'):
			if len(rest) == 1:
				return widget.configure(str(rest[0]))
			if rest:
				return widget.configure(**_optionPairs(rest))
		elif sub == 'cget' and rest:
			return widget.cget(str(rest[0]).lstrip('-'))
		if classMethods:
			func = getattr(type(widget), sub, None)
			if callable(func):
				return func(widget, *rest)
		else:
			func = getattr(widget, sub, None)
			if callable(func):
				return func(*rest)
		raise TclError(f'bad option "{sub}"')


def _optionPairs(args):
	"""('-text', 'a', '-width', 3) -> {'text': 'a', 'width': 3}"""
	if len(args) % 2:
		raise TclError(f'value for "{args[-1]}" missing')
	return {str(args[i]).lstrip('-'): args[i+1] for i in range(0, len(args), 2)}


# ---------------------------------------------------------------------------
# Global Tcl commands
# ---------------------------------------------------------------------------

def _tkCommand(tcl, *args):
	sub = str(args[0]) if args else ''
	if sub == 'windowingsystem':
		return 'x11'
	if sub == 'scaling':
		return 1.0
	if sub in ('busy', 'appname', 'caret', 'inactive', 'useinputmethods'):
		return ''
	raise TclError(f'unknown or ambiguous subcommand "{sub}"')


def _wmCommand(tcl, *args):
	if len(args) < 2:
		raise TclError('wrong # args')
	widget = tcl._widget(args[1])
	func   = getattr(widget, 'wm_' + str(args[0]), None)
	if func is None:
		raise TclError(f'bad option "{args[0]}"')
	return func(*args[2:])


def _winfoCommand(tcl, *args):
	"""winfo <sub> <window> …: the widget's winfo_<sub>() method."""
	if len(args) < 2:
		raise TclError('wrong # args: should be "winfo option ?arg ...?"')
	sub = str(args[0])
	if sub == 'exists':
		try:
			return int(tcl._widget(args[1]).winfo_exists())
		except TclError:
			return 0
	func = getattr(tcl._widget(args[1]), f'winfo_{sub}', None)
	if func is None:
		raise TclError(f'bad option "{sub}"')
	result = func(*args[2:])
	return int(result) if isinstance(result, bool) else result


def _infoCommand(tcl, *args):
	sub = str(args[0]) if args else ''
	if sub == 'args':
		return _infoArgs(tcl, *args)
	if sub == 'patchlevel':
		return '8.6.18'
	if sub == 'tclversion':
		return '8.6'
	raise TclError(f'unknown or ambiguous subcommand "{sub}"')


def _imageCommand(tcl, *args):
	from ._image import _imageByName
	sub = str(args[0]) if args else ''
	if sub == 'names':
		from ._image import image_names
		return image_names()
	img = _imageByName(args[1]) if len(args) > 1 else None
	if img is None:
		raise TclError(f'image "{args[1] if len(args) > 1 else ""}" doesn\'t exist')
	if sub == 'width':
		return img.width()
	if sub == 'height':
		return img.height()
	if sub == 'type':
		return img.type()
	if sub == 'delete':
		img.__del__()
		return ''
	raise TclError(f'bad option "{sub}"')


def _bindCommand(tcl, *args):
	widget = tcl._widget(args[0])
	if len(args) == 1:
		return tuple(widget.bind())
	if len(args) == 2:
		return ''
	cmd = args[2]
	if callable(cmd):
		widget.bind(args[1], cmd, '+' if str(cmd).startswith('+') else None)
	return ''


def _getSelection(tcl, widget, selection='PRIMARY'):
	return tcl._widget(widget).clipboard_get()


def _placeWindow(tcl, window, *args):
	w = tcl._widget(window)
	if hasattr(w, '_placeWindow'):
		w._placeWindow(*args)
	return ''


def _treeKeynav(tcl, widget, direction):
	"""ttk::treeview::Keynav: move the focus like the arrow keys."""
	from ._events import KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_HOME, KEY_END
	key = {'up': KEY_UP, 'down': KEY_DOWN, 'left': KEY_LEFT, 'right': KEY_RIGHT,
		'home': KEY_HOME, 'end': KEY_END}.get(str(direction))
	if key is not None:
		tcl._widget(widget)._handleKey(key)
	return ''


def _treeSelectOp(tcl, widget, item, *args):
	"""ttk::treeview::SelectOp w item ?cell? op (choose/toggle/extend)."""
	tv   = tcl._widget(widget)
	op   = str(args[-1]) if args else 'choose'
	item = str(item)
	if item:
		tv._selectOp(item, op)
	return ''


def _treeSelect(tcl, widget, x, y, op='choose'):
	tv = tcl._widget(widget)
	return _treeSelectOp(tcl, widget, tv.identify_row(y), op)


def _infoArgs(tcl, *args):
	if len(args) == 2 and str(args[0]) == 'args':
		return {'ttk::treeview::SelectOp': 'w item op'}.get(str(args[1]).lstrip(':'), '')
	return None


def _textAnchor(tcl, widget):
	"""::tk::TextAnchor w: name of the selection anchor mark of a Text."""
	from ._text import ANCHOR_MARK
	return ANCHOR_MARK


def _setCommand(tcl, *args):
	"""set varName ?value?"""
	if len(args) == 2:
		tcl.setvar(str(args[0]), args[1])
		return args[1]
	if len(args) == 1:
		return tcl.getvar(str(args[0]))
	raise TclError('wrong # args: should be "set varName ?newValue?"')


def _wordRe(tcl) -> re.Pattern:
	"""Pattern of a word character from tcl_wordchars (default \\w)"""
	try:
		chars = str(tcl.getvar('tcl_wordchars'))
	except TclError:
		chars = r'\w'
	return re.compile(chars)


def _wordBreakAfter(tcl, text, start):
	"""tcl_wordBreakAfter str start: first word/non-word boundary after start"""
	text  = str(text)
	isWord = _wordRe(tcl)
	start = int(start)
	for i in range(max(start, 0) + 1, len(text)):
		if bool(isWord.match(text[i-1])) != bool(isWord.match(text[i])):
			return i
	return -1


def _wordBreakBefore(tcl, text, start):
	"""tcl_wordBreakBefore str start: last word/non-word boundary before start"""
	text  = str(text)
	isWord = _wordRe(tcl)
	for i in range(min(int(start), len(text) - 1), 0, -1):
		if bool(isWord.match(text[i-1])) != bool(isWord.match(text[i])):
			return i
	return -1


def _ignore(tcl, *args):
	return ''


def _unsupported(name):
	def handler(tcl, *args):
		raise TclError(f'invalid command name "{name}"')
	return handler


_COMMANDS = {
	'tk':			_tkCommand,
	'wm':			_wmCommand,
	'info':			_infoCommand,
	'winfo':		_winfoCommand,
	'image':		_imageCommand,
	'bind':			_bindCommand,
	'tk::GetSelection':	_getSelection,
	'tk::PlaceWindow':	_placeWindow,
	'tk::CancelRepeat':	_ignore,
	'tk::EntrySeeInsert':	_ignore,
	'tk::TextAnchor':	_textAnchor,
	'ttk::treeview::Keynav':	_treeKeynav,
	'ttk::treeview::SelectOp':	_treeSelectOp,
	'ttk::treeview::Select':	_treeSelect,
	'ttk::treeview::Release':	_ignore,
	'grid':			_ignore,
	'update':		_ignore,
	'set':			_setCommand,
	'rename':		lambda tcl, old, new: tcl._rename(old, new),
	'tcl_wordBreakAfter':	_wordBreakAfter,
	'tcl_wordBreakBefore':	_wordBreakBefore,
	'source':		_unsupported('source'),
}


tcl = TclShim()
