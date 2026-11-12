"""
tktext – tkinter-like text-mode UI toolkit built on curses.

Usage example::

    import tktext as tk

    root = tk.Tk()
    root.title('My App')

    lbl = tk.Label(root, text='Hello, world!', fg='cyan')
    lbl.pack(pady=1)

    btn = tk.Button(root, text='Quit', command=root.quit)
    btn.pack()

    root.mainloop()
"""

from ._core        import TclError, Widget
from ._app         import Tk
from ._toplevel    import Toplevel, Wm
from ._frame       import Frame, LabelFrame
from ._label       import Label, Message
from ._canvas      import Canvas
from ._panedwindow import PanedWindow
from ._image       import Image, PhotoImage, BitmapImage, image_names, image_types
from ._button      import Button
from ._text        import Text
from ._listbox     import Listbox
from ._treeview    import Treeview
from ._entry       import Entry
from ._checkbutton import Checkbutton
from ._radiobutton import Radiobutton
from ._menu        import Menu, OptionMenu
from ._scale       import Scale
from ._spinbox     import Spinbox
from ._notebook    import Notebook
from ._combobox    import Combobox
from ._scrollbar   import Scrollbar
from ._misc        import Separator, Progressbar
from ._events      import Event
from . import ttk

# ---------------------------------------------------------------------------
# Constants – mirrors the names exported by tkinter
# ---------------------------------------------------------------------------

TOP     = 'top'
BOTTOM  = 'bottom'
LEFT    = 'left'
RIGHT   = 'right'
BOTH    = 'both'
X       = 'x'
Y       = 'y'
NONE    = 'none'

N       = 'n'
S       = 's'
E       = 'e'
W       = 'w'
NE      = 'ne'
NW      = 'nw'
SE      = 'se'
SW      = 'sw'
NS      = 'ns'
EW      = 'ew'
NSEW    = 'nsew'
CENTER  = 'center'

END     = 'end'
INSERT  = 'insert'
CURRENT = 'current'
ANCHOR  = 'anchor'
FIRST   = 'first'
LAST    = 'last'
SEL     = 'sel'

WORD    = 'word'
CHAR    = 'char'

SINGLE   = 'single'
MULTIPLE = 'multiple'
EXTENDED = 'extended'
BROWSE   = 'browse'

NORMAL   = 'normal'
DISABLED = 'disabled'
ACTIVE   = 'active'

FLAT    = 'flat'
RAISED  = 'raised'
SUNKEN  = 'sunken'
SOLID   = 'solid'
RIDGE   = 'ridge'
GROOVE  = 'groove'

HORIZONTAL = 'horizontal'
VERTICAL   = 'vertical'

HEADINGS = 'headings'
TREE     = 'tree'

NO      = FALSE = OFF = 0
YES     = TRUE  = ON  = 1
BASELINE = 'baseline'
INSIDE  = 'inside'
OUTSIDE = 'outside'
NUMERIC = 'numeric'
UNITS   = 'units'
PAGES   = 'pages'
MOVETO  = 'moveto'
SCROLL  = 'scroll'
HIDDEN  = 'hidden'
READONLY = 'readonly'
DOTBOX  = 'dotbox'
UNDERLINE = 'underline'
ALL     = 'all'
SEPARATOR = 'separator'
COMMAND = 'command'
CASCADE = 'cascade'
CHECKBUTTON = 'checkbutton'
RADIOBUTTON = 'radiobutton'
SEL_FIRST = 'sel.first'
SEL_LAST  = 'sel.last'
CHORD   = 'chord'
PIESLICE = 'pieslice'
ARC     = 'arc'
BEVEL   = 'bevel'
MITER   = 'miter'
ROUND   = 'round'
BUTT    = 'butt'
PROJECTING = 'projecting'

_CONSTANT_NAMES = [_n for _n, _v in dict(globals()).items()
	if _n.isupper() and not _n.startswith('_') and isinstance(_v, (str, int))]

# ---------------------------------------------------------------------------
# StringVar / IntVar / BooleanVar / DoubleVar  – simple variable wrappers
# ---------------------------------------------------------------------------

class Variable:
	"""Observable variable (mirrors tkinter.Variable).

	trace_add(mode, cb) accepts 'write', 'read', 'unset' (or a list of
	them) and returns a name for trace_remove(); the legacy trace('w', cb)
	/ trace_variable / trace_vdelete API is supported too.  Callbacks are
	called as cb(name, index, mode) like in tkinter.
	"""

	_count	= 0
	_default = None

	def __init__(self, master=None, value=None, name=None):
		Variable._count += 1
		self._name   = name or f'PY_VAR{Variable._count}'
		self._traces = []	# list of (cbname, modes, callback)
		self._val    = self._default if value is None else self._convert(value)

	def _convert(self, value):
		return value

	def _fire(self, mode):
		for _, modes, cb in list(self._traces):
			if mode in modes:
				cb(self._name, '', mode)

	def get(self):
		if any('read' in modes for _, modes, _ in self._traces):
			self._fire('read')
		return self._val

	def set(self, value):
		self._val = self._convert(value)
		self._fire('write')

	initialize = set

	_MODES = {'w': 'write', 'r': 'read', 'u': 'unset',
		'write': 'write', 'read': 'read', 'unset': 'unset', 'array': 'write'}

	def trace_add(self, mode, callback):
		if isinstance(mode, str):
			mode = mode.split() if ' ' in mode else [mode]
		modes = set()
		for m in mode:
			for ch in ([m] if m in self._MODES else list(m)):
				if ch in self._MODES:
					modes.add(self._MODES[ch])
		cbname = f'{id(callback)}{callback.__name__ if hasattr(callback, "__name__") else ""}{len(self._traces)}'
		self._traces.append((cbname, modes, callback))
		return cbname

	def trace_remove(self, mode, cbname):
		self._traces = [t for t in self._traces if t[0] != cbname]

	def trace_info(self):
		return [(tuple(sorted(m)), n) for n, m, _ in self._traces]

	def trace_variable(self, mode, callback):
		return self.trace_add(mode, callback)

	trace = trace_variable

	def trace_vdelete(self, mode, cbname):
		self.trace_remove(mode, cbname)

	def trace_vinfo(self):
		return self.trace_info()

	traceAdd	= trace_add
	traceRemove	= trace_remove
	traceInfo	= trace_info

	def __str__(self):
		return self._name

	def __repr__(self):
		return f'<{type(self).__name__} {self._name}={self._val!r}>'


class StringVar(Variable):
	_default = ''

	def __init__(self, master=None, value=None, name=None):
		super().__init__(master, value, name)

	def _convert(self, value):
		return '' if value is None else str(value)

	def get(self):
		v = super().get()
		return '' if v is None else str(v)


class IntVar(Variable):
	_default = 0

	def __init__(self, master=None, value=None, name=None):
		super().__init__(master, value, name)

	def _convert(self, value):
		if isinstance(value, str):
			value = value.strip()
			if value == '':
				return 0
			return int(float(value))
		return int(value)

	def get(self):
		v = super().get()
		return 0 if v is None else int(v)


class DoubleVar(Variable):
	_default = 0.0

	def __init__(self, master=None, value=None, name=None):
		super().__init__(master, value, name)

	def _convert(self, value):
		if isinstance(value, str) and value.strip() == '':
			return 0.0
		return float(value)

	def get(self):
		v = super().get()
		return 0.0 if v is None else float(v)


class BooleanVar(Variable):
	_default = False

	def __init__(self, master=None, value=None, name=None):
		super().__init__(master, value, name)

	def _convert(self, value):
		if isinstance(value, str):
			return value.strip().lower() in ('1', 'true', 'yes', 'on')
		return bool(value)

	def get(self):
		return bool(super().get())


class _setit:
	"""Internal class used by OptionMenu menus (mirrors tkinter._setit)."""

	def __init__(self, var, value, callback=None):
		self.__value	= value
		self.__var	= var
		self.__callback	= callback

	def __call__(self, *args):
		self.__var.set(self.__value)
		if self.__callback is not None:
			self.__callback(self.__value, *args)


__version__ = '0.1.0'

__all__ = [
	# Widgets
	'Tk', 'Frame', 'LabelFrame', 'Label', 'Button', 'Text', 'Listbox',
	'Treeview', 'Entry', 'Checkbutton', 'Radiobutton', 'Menu', 'OptionMenu',
	'Scale', 'Spinbox', 'Notebook', 'Combobox', 'Scrollbar', 'Separator',
	'Progressbar', 'Event', 'TclError', 'ttk',
	# Variables
	'Variable', 'StringVar', 'IntVar', 'DoubleVar', 'BooleanVar',
	# Direction / fill constants
	'TOP', 'BOTTOM', 'LEFT', 'RIGHT', 'BOTH', 'X', 'Y', 'NONE',
	# Anchor / sticky constants
	'N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW', 'NS', 'EW', 'NSEW', 'CENTER',
	# Index constants
	'END', 'INSERT', 'CURRENT', 'ANCHOR', 'FIRST', 'LAST', 'SEL',
	# Wrap / select modes
	'WORD', 'CHAR', 'SINGLE', 'MULTIPLE', 'EXTENDED', 'BROWSE',
	# State constants
	'NORMAL', 'DISABLED', 'ACTIVE',
	# Relief constants
	'FLAT', 'RAISED', 'SUNKEN', 'SOLID', 'RIDGE', 'GROOVE',
	# Orientation
	'HORIZONTAL', 'VERTICAL',
	# Treeview show modes
	'HEADINGS', 'TREE',
	# Misc
	'NO', 'YES', 'FALSE', 'TRUE', 'OFF', 'ON', 'UNITS', 'PAGES', 'MOVETO',
	'SCROLL', 'HIDDEN', 'READONLY', 'ALL',
	# tkinter compatibility
	'Toplevel', 'Message', 'Canvas', 'PanedWindow', 'Image', 'PhotoImage',
	'BitmapImage', 'Widget', 'Misc', 'Wm', 'CallWrapper', 'EventType',
	'SEL_FIRST', 'SEL_LAST', 'TkVersion', 'TclVersion', 'install',
	'image_names', 'image_types',
]


# ---------------------------------------------------------------------------
# tkinter module-level compatibility
# ---------------------------------------------------------------------------

import enum as _enum
import sys as _sys
import types as _types

TkVersion	= 8.6
TclVersion	= 8.6
wantobjects	= 1
READABLE	= 2
WRITABLE	= 4
EXCEPTION	= 8

_default_root	= None		# set by the first Tk()
_support_default_root = True

Misc		= Widget
BaseWidget	= Widget


class CallWrapper:
	"""Calls a Python callback (tkinter.CallWrapper).  Every binding and
	timer callback is invoked through ``tktext.CallWrapper``, so that an
	application can replace it (e.g. to report exceptions its own way)."""

	def __init__(self, func, subst, widget):
		self.func	= func
		self.subst	= subst
		self.widget	= widget

	def __call__(self, *args):
		if self.subst:
			args = self.subst(*args)
		return self.func(*args)


class EventType(str, _enum.Enum):
	"""Event types; compare equal to Event.type strings."""
	KeyPress	= 'KeyPress'
	Key		= 'KeyPress'
	KeyRelease	= 'KeyRelease'
	ButtonPress	= 'ButtonPress'
	Button		= 'ButtonPress'
	ButtonRelease	= 'ButtonRelease'
	Motion		= 'Motion'
	Enter		= 'Enter'
	Leave		= 'Leave'
	FocusIn		= 'FocusIn'
	FocusOut	= 'FocusOut'
	Expose		= 'Expose'
	Visibility	= 'Visibility'
	Destroy		= 'Destroy'
	Unmap		= 'Unmap'
	Map		= 'Map'
	Configure	= 'Configure'
	MouseWheel	= 'MouseWheel'
	VirtualEvent	= 'VirtualEvent'

	def __str__(self):
		return self.value


def NoDefaultRoot():
	global _support_default_root
	_support_default_root = False


def _get_default_root(what=None):
	if _default_root is None:
		raise RuntimeError(f'Too early to {what}: no default root window'
			if what else 'No master specified and tkinter is configured '
			'to not support default root')
	return _default_root


def _get_temp_root():
	return _default_root or Tk()


def _cnfmerge(cnfs):
	"""Merge a sequence of option dictionaries (tkinter._cnfmerge)."""
	if isinstance(cnfs, dict) or cnfs is None:
		return cnfs
	cnf = {}
	for c in cnfs:
		if c:
			cnf.update(c)
	return cnf


def getboolean(s):
	from ._tcl import tcl
	return tcl.getboolean(s)


def getint(s):
	return int(s)


def getdouble(s):
	return float(s)


def mainloop(n=0):
	_get_default_root('run the main loop').mainloop(n)


# ---------------------------------------------------------------------------
# Drop-in replacement of tkinter
# ---------------------------------------------------------------------------

class _Blocker:
	"""Import hook making modules that need a real Tk unimportable."""
	names = set()

	def find_spec(self, name, path=None, target=None):
		if name in self.names:
			raise ModuleNotFoundError(f'{name} needs a graphical display '
				'(not available in text mode)', name=name)
		return None


def install(block=()):
	"""Make ``import tkinter`` (and its submodules) load tktext.

	Call it before anything imports tkinter.  Modules that need a real Tk
	(PIL.ImageTk, ttkthemes) — plus any extra names in *block* — are made
	unimportable, so that applications take their "not available" paths.
	"""
	from . import ttk as _ttk, messagebox, filedialog, font, colorchooser, \
		dnd, simpledialog, constants
	this = _sys.modules[__name__]
	core = _types.ModuleType('_tkinter')
	core.TclError	= TclError
	core.TK_VERSION	= core.TCL_VERSION = '8.6'
	core.READABLE, core.WRITABLE, core.EXCEPTION = READABLE, WRITABLE, EXCEPTION
	modules = {
		'tkinter':		this,
		'tkinter.ttk':		_ttk,
		'tkinter.messagebox':	messagebox,
		'tkinter.filedialog':	filedialog,
		'tkinter.font':		font,
		'tkinter.colorchooser':	colorchooser,
		'tkinter.dnd':		dnd,
		'tkinter.simpledialog':	simpledialog,
		'tkinter.constants':	constants,
		'_tkinter':		core,
	}
	for name in ('font', 'colorchooser', 'dnd', 'simpledialog',
			'constants', 'messagebox', 'filedialog'):
		setattr(this, name, modules[f'tkinter.{name}'])
	_sys.modules.update(modules)
	_Blocker.names.update(('PIL.ImageTk', 'ttkthemes') + tuple(block))
	if not any(isinstance(f, _Blocker) for f in _sys.meta_path):
		_sys.meta_path.insert(0, _Blocker())
	# tkinter programs measure in pixels: emulate a display of 8x16 cells
	from ._core import setPixelMode
	setPixelMode(8, 16)

