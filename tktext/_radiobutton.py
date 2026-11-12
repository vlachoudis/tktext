from ._checkbutton import Checkbutton
from ._core import _sameValue, _initArgs
from ._events import KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN


# Default variable when none provided
class _StrVar:
	def __init__(self):
		self._val = ''
	def get(self):
		return self._val
	def set(self, v):
		self._val = v


class Radiobutton(Checkbutton):
	"""Radio button widget.  Mirrors tkinter.Radiobutton.

	Shares rendering and input handling with Checkbutton; only the
	indicator and the selection semantics differ."""

	def __init__(self, parent=None, cnf=None, **kwargs):
		parent, kwargs = _initArgs(parent, cnf, kwargs)
		kwargs.setdefault('value', '')
		super().__init__(parent, **kwargs)

	def _defaultVar(self):
		return _StrVar()

	# ------------------------------------------------------------------

	def _isSelected(self) -> bool:
		try:
			cur = self._getVar().get()
		except (TypeError, ValueError):
			return False
		return _sameValue(cur, self._opts.get('value', ''))

	_isChecked = _isSelected

	def _indicator(self) -> str:
		return '(*) ' if self._isSelected() else '( ) '

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def invoke(self):
		"""Select this radio button and call its command."""
		if self._opts.get('state') == 'disabled':
			return None
		self._getVar().set(self._opts.get('value', ''))
		self._markDirty()
		cmd = self._opts.get('command')
		if callable(cmd):
			return cmd()
		return None

	def select(self):
		"""Set variable to this button's value."""
		self._getVar().set(self._opts.get('value', ''))
		self._markDirty()

	def deselect(self):
		"""Clear the variable if this button is selected."""
		if self._isSelected():
			self._getVar().set('')
			self._markDirty()

	def toggle(self):
		self.select()

	# ------------------------------------------------------------------

	def _handleKey(self, key: int) -> bool:
		if key in (KEY_LEFT, KEY_UP, KEY_RIGHT, KEY_DOWN):
			return self._moveFocus(backward=(key in (KEY_LEFT, KEY_UP)))
		return super()._handleKey(key)

	def _moveFocus(self, backward: bool) -> bool:
		app = self._getApp()
		if app is None:
			return False
		myVar    = self._opts.get('variable')
		siblings = [w for w in app._getAllFocusable()
			if isinstance(w, Radiobutton) and w._opts.get('variable') is myVar]
		if len(siblings) < 2 or self not in siblings:
			return False
		idx = siblings.index(self) + (-1 if backward else 1)
		nxt = siblings[idx % len(siblings)]
		app._setFocus(nxt)
		nxt.invoke()
		return True
