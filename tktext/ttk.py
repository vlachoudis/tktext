"""ttk — themed widget aliases.  Mirrors tkinter.ttk for drop-in compatibility."""
from ._combobox  import Combobox
from ._notebook  import Notebook
from ._treeview  import Treeview
from ._scale     import Scale
from ._spinbox   import Spinbox
from ._scrollbar import Scrollbar
from ._frame     import Frame
from ._label     import Label
from ._button    import Button
from ._entry     import Entry
from ._checkbutton  import Checkbutton
from ._radiobutton  import Radiobutton

# ttk-specific constants not already in __init__
HORIZONTAL = 'horizontal'
VERTICAL   = 'vertical'
