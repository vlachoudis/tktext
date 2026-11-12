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
from ._menu      import OptionMenu
from ._misc      import Separator, Progressbar


class Label(_Label):
	"""ttk.Label: anchor defaults to 'w' like the themed widget."""

	def __init__(self, parent=None, **kwargs):
		kwargs.setdefault('anchor', 'w')
		kwargs.setdefault('justify', 'left')
		super().__init__(parent, **kwargs)


class Scale(_Scale):
	"""ttk.Scale: horizontal by default."""

	def __init__(self, parent=None, **kwargs):
		kwargs.setdefault('orient', 'horizontal')
		kwargs.setdefault('showvalue', 0)
		super().__init__(parent, **kwargs)


class Style:
	"""No-op stand-in for ttk.Style (themes do not apply to terminals)."""

	def __init__(self, master=None):
		pass

	def configure(self, style, query_opt=None, **kw):
		return {}

	def map(self, style, query_opt=None, **kw):
		return {}

	def lookup(self, style, option, state=None, default=None):
		return default

	def layout(self, style, layoutspec=None):
		return []

	def theme_use(self, themename=None):
		return 'default'

	def theme_names(self):
		return ('default',)

	def element_create(self, *a, **kw):
		pass


LabeledScale = Scale

__all__ = ['Button', 'Checkbutton', 'Combobox', 'Entry', 'Frame', 'Label',
	'LabelFrame', 'Notebook', 'OptionMenu', 'Progressbar', 'Radiobutton',
	'Scale', 'Scrollbar', 'Separator', 'Spinbox', 'Style', 'Treeview']
