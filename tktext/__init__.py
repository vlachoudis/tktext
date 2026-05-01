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

    root.mainLoop()
"""

from ._app      import Tk
from ._frame    import Frame
from ._label    import Label
from ._button   import Button
from ._text     import Text
from ._listbox  import Listbox
from ._treeview import Treeview

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

# ---------------------------------------------------------------------------
# StringVar / IntVar / BooleanVar / DoubleVar  – simple variable wrappers
# ---------------------------------------------------------------------------

class Variable:
	"""Observable variable (mirrors tkinter.Variable)."""

	def __init__(self, master=None, value=None, name=None):
		self._val   = value
		self._name  = name
		self._traces = []

	def get(self):
		return self._val

	def set(self, value):
		self._val = value
		for cb in self._traces:
			try:
				cb(self._name, '', 'write')
			except Exception:
				pass

	def trace_add(self, mode, callback):
		if mode == 'write':
			self._traces.append(callback)

	def trace_variable(self, mode, callback):
		self.trace_add(mode, callback)

	trace = trace_variable

	def trace_remove(self, mode, cbname):
		pass

	def trace_info(self):
		return []

	def __str__(self):
		return str(self._val)


class StringVar(Variable):
	def __init__(self, master=None, value='', name=None):
		super().__init__(master, str(value) if value is not None else '', name)

	def get(self):
		return '' if self._val is None else str(self._val)

	def set(self, value):
		super().set(str(value))


class IntVar(Variable):
	def __init__(self, master=None, value=0, name=None):
		super().__init__(master, int(value), name)

	def get(self):
		return 0 if self._val is None else int(self._val)

	def set(self, value):
		super().set(int(value))


class DoubleVar(Variable):
	def __init__(self, master=None, value=0.0, name=None):
		super().__init__(master, float(value), name)

	def get(self):
		return 0.0 if self._val is None else float(self._val)

	def set(self, value):
		super().set(float(value))


class BooleanVar(Variable):
	def __init__(self, master=None, value=False, name=None):
		super().__init__(master, bool(value), name)

	def get(self):
		return bool(self._val)

	def set(self, value):
		super().set(bool(value))


__version__ = '0.1.0'

__all__ = [
	# Widgets
	'Tk', 'Frame', 'Label', 'Button', 'Text', 'Listbox', 'Treeview',
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
]
