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

"""messagebox — modal dialog functions.  Mirrors tkinter.messagebox."""
from ._dialog import _getApp, _MsgDialog

# Return values / constants (same as tkinter.messagebox)
ERROR		= 'error'
INFO		= 'info'
QUESTION	= 'question'
WARNING		= 'warning'
ABORTRETRYIGNORE = 'abortretryignore'
OK		= 'ok'
OKCANCEL	= 'okcancel'
RETRYCANCEL	= 'retrycancel'
YESNO		= 'yesno'
YESNOCANCEL	= 'yesnocancel'
ABORT		= 'abort'
RETRY		= 'retry'
IGNORE		= 'ignore'
CANCEL		= 'cancel'
YES		= 'yes'
NO		= 'no'


def _run(title, message, buttons, icon='', **kw):
	app = _getApp(kw.get('parent'))
	icon = kw.get('icon') or icon
	if kw.get('detail'):
		message = f'{message}\n\n{kw["detail"]}'
	if app is None:
		return buttons[0][1]
	return _MsgDialog(app, title or '', message or '', buttons, icon,
		default=kw.get('default')).run()


# ------------------------------------------------------------------
# Information / error / warning
# ------------------------------------------------------------------

def showinfo(title=None, message=None, **kw) -> str:
	return _run(title, message, [('OK', OK)], INFO, **kw) or OK

def showwarning(title=None, message=None, **kw) -> str:
	return _run(title, message, [('OK', OK)], WARNING, **kw) or OK

def showerror(title=None, message=None, **kw) -> str:
	return _run(title, message, [('OK', OK)], ERROR, **kw) or OK


# ------------------------------------------------------------------
# Confirmation dialogs
# ------------------------------------------------------------------

def askokcancel(title=None, message=None, **kw) -> bool:
	return bool(_run(title, message, [('OK', True), ('Cancel', False)],
		QUESTION, **kw))

def askyesno(title=None, message=None, **kw) -> bool:
	return bool(_run(title, message, [('Yes', True), ('No', False)],
		QUESTION, **kw))

def askyesnocancel(title=None, message=None, **kw):
	"""Return True, False, or None (Cancel)."""
	return _run(title, message,
		[('Yes', True), ('No', False), ('Cancel', None)], QUESTION, **kw)

def askquestion(title=None, message=None, **kw) -> str:
	"""Return 'yes' or 'no'."""
	return _run(title, message, [('Yes', YES), ('No', NO)], QUESTION, **kw) or NO

def askretrycancel(title=None, message=None, **kw) -> bool:
	return bool(_run(title, message, [('Retry', True), ('Cancel', False)],
		WARNING, **kw))
