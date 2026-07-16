"""messagebox — modal dialog functions.  Mirrors tkinter.messagebox."""
from ._dialog import _getApp, _MsgDialog


def _run(title, message, buttons, icon=''):
	app = _getApp()
	if app is None:
		return buttons[0][1]
	return _MsgDialog(app, title or '', message or '', buttons, icon).run()


# ------------------------------------------------------------------
# Information / error / warning
# ------------------------------------------------------------------

def showinfo(title='', message='', **kw) -> str:
	return _run(title, message, [('OK', 'ok')], 'info')

def showwarning(title='', message='', **kw) -> str:
	return _run(title, message, [('OK', 'ok')], 'warning')

def showerror(title='', message='', **kw) -> str:
	return _run(title, message, [('OK', 'ok')], 'error')


# ------------------------------------------------------------------
# Confirmation dialogs
# ------------------------------------------------------------------

def askokcancel(title='', message='', **kw) -> bool:
	result = _run(title, message,
		[('OK', True), ('Cancel', False)], 'question')
	return bool(result)

def askyesno(title='', message='', **kw) -> bool:
	result = _run(title, message,
		[('Yes', True), ('No', False)], 'question')
	return bool(result)

def askyesnocancel(title='', message='', **kw):
	"""Return True, False, or None (Cancel)."""
	return _run(title, message,
		[('Yes', True), ('No', False), ('Cancel', None)], 'question')

def askquestion(title='', message='', **kw) -> str:
	"""Return 'yes' or 'no'."""
	result = _run(title, message,
		[('Yes', 'yes'), ('No', 'no')], 'question')
	return result or 'no'

def askretrycancel(title='', message='', **kw) -> bool:
	result = _run(title, message,
		[('Retry', True), ('Cancel', False)], 'warning')
	return bool(result)
