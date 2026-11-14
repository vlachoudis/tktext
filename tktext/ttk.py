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

"""ttk — themed widget aliases.  Mirrors tkinter.ttk for drop-in compatibility."""

from ._combobox  import Combobox
from ._notebook  import Notebook
from ._treeview  import Treeview
from ._scale     import Scale as _Scale
from ._spinbox   import Spinbox
from ._scrollbar import Scrollbar
from ._frame     import Frame, LabelFrame
from ._label     import Label as _Label
from ._button    import Button
from ._entry     import Entry
from ._checkbutton  import Checkbutton
from ._radiobutton  import Radiobutton
from ._menu      import OptionMenu as _OptionMenu
from ._menubutton import Menubutton
from ._misc      import Separator, Progressbar
from ._panedwindow import Panedwindow
from ._core      import Widget as _Widget
from ._core import _initArgs


class Label(_Label):
	"""ttk.Label: anchor defaults to 'w' like the themed widget."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		kwargs.setdefault('anchor', 'w')
		kwargs.setdefault('justify', 'left')
		super().__init__(parent, **kwargs)


class Scale(_Scale):
	"""ttk.Scale: horizontal by default."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		kwargs.setdefault('orient', 'horizontal')
		kwargs.setdefault('showvalue', 0)
		super().__init__(parent, **kwargs)

	def get(self, x=None, y=None):
		"""Current value; with x, y the value at that point (the same
		in a terminal: the coordinates are ignored)."""
		return _Scale.get(self)


class OptionMenu(_OptionMenu):
	"""ttk.OptionMenu(master, variable, default=None, *values): unlike
	tkinter.OptionMenu *default* is only the initial value."""

	def __init__(self, master, variable, default=None, *values, **kwargs):
		super().__init__(master, variable, None, **kwargs)
		self.set_menu(default, *values)

	def set_menu(self, default=None, *values):
		"""Build a new menu of radiobuttons with *values* and optionally
		a *default* value."""
		self._menu.delete(0, 'end')
		for v in values:
			self._menu.add_command(label=str(v), command=self._makeSetter(v))
		if default and self._variable is not None:
			self._variable.set(default)
		self._markDirty()


class Style:
	"""ttk.Style: themes do not apply to a terminal, but option values are
	stored and lookup() answers like Tk's 'default' theme, so programs
	that derive their palette from the theme get sensible colours."""

	_settings = {}		# style -> {option: value} (shared like Tk's)
	_DEFAULT = {
		'background':		'#d9d9d9',
		'foreground':		'#000000',
		'fieldbackground':	'#ffffff',
		'selectbackground':	'#4a6984',
		'selectforeground':	'#ffffff',
		'troughcolor':		'#c3c3c3',
		'insertcolor':		'#000000',
		'disabledforeground':	'#a3a3a3',
		'bordercolor':		'#9e9e9e',
		'lightcolor':		'#ffffff',
		'darkcolor':		'#c3c3c3',
	}

	def __init__(self, master=None):
		pass

	def configure(self, style, query_opt=None, **kw):
		cfg = Style._settings.setdefault(style, {})
		if query_opt is not None:
			return cfg.get(query_opt, '')
		if not kw:
			return dict(cfg)
		cfg.update(kw)
		if style == '.':
			from ._colors import addDefaultColors
			addDefaultColors(
				(kw.get('background'), kw.get('fieldbackground')),
				kw.get('foreground'))
		return None

	def map(self, style, query_opt=None, **kw):
		return [] if query_opt is not None else {}

	def lookup(self, style, option, state=None, default=None):
		option = option.lstrip('-')
		for s in (style, '.'):
			if option in Style._settings.get(s, {}):
				return Style._settings[s][option]
		return Style._DEFAULT.get(option, default)

	def layout(self, style, layoutspec=None):
		return []

	def theme_use(self, themename=None):
		return 'default'

	def theme_names(self):
		return ('default',)

	def element_create(self, *a, **kw):
		pass

	def element_names(self):
		return ()

	def element_options(self, elementname):
		return ()

	def theme_create(self, themename, parent=None, settings=None):
		if settings:
			self.theme_settings(themename, settings)

	def theme_settings(self, themename, settings):
		"""Apply {style: {'configure': {…}, 'map': {…}}} to the styles."""
		for style, spec in settings.items():
			cfg = spec.get('configure') if isinstance(spec, dict) else None
			if cfg:
				self.configure(style, **cfg)


LabeledScale	= Scale
Widget		= _Widget
PanedWindow	= Panedwindow
Labelframe	= LabelFrame


class Sizegrip(_Widget):
	"""ttk.Sizegrip: a terminal window cannot be resized; takes no space."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		super().__init__(parent)
		self._opts['takefocus'] = False
		if kwargs:
			Sizegrip.configure(self, **kwargs)


def setup_master(master=None):
	"""*master*, or the default root (RuntimeError without one)."""
	if master is None:
		import tktext
		master = tktext._get_default_root()
	return master


def tclobjs_to_py(adict):
	"""Values are Python objects already: *adict* is returned as is."""
	return adict


def __getattr__(name):
	# tkinter constants are reachable through ttk too (ttk.INSERT ...)
	import tktext
	if name.isupper() and name in tktext._CONSTANT_NAMES:
		return getattr(tktext, name)
	raise AttributeError(name)

__all__ = ['Button', 'Checkbutton', 'Combobox', 'Entry', 'Frame', 'Label',
	'LabelFrame', 'Notebook', 'OptionMenu', 'Progressbar', 'Radiobutton',
	'Scale', 'Scrollbar', 'Separator', 'Spinbox', 'Style', 'Treeview',
	'Panedwindow', 'PanedWindow', 'Labelframe', 'LabelFrame', 'Sizegrip',
	'Menubutton', 'LabeledScale', 'Widget', 'setup_master', 'tclobjs_to_py']
