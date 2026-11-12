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

from ._core        import TclError
from ._app         import Tk
from ._frame       import Frame, LabelFrame
from ._label       import Label
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
]
