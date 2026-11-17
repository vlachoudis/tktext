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
# Date:   14-Nov-2026

"""dialog — the classic Tk dialog box.  Mirrors tkinter.dialog."""

from ._dialog import _getApp, _MsgDialog

DIALOG_ICON = 'questhead'


class Dialog:
	"""Dialog(master, title=, text=, bitmap=, default=, strings=(…)):
	runs at once and stores the index of the chosen button in num."""

	def __init__(self, master=None, cnf={}, **kw):
		cnf = {**cnf, **kw}
		buttons = [(str(s), i) for i, s in enumerate(cnf.get('strings', ()))] \
			or [('OK', 0)]
		default = cnf.get('default')
		app	= _getApp(master)
		self.num = default if default is not None else 0
		if app is not None:
			result = _MsgDialog(app, str(cnf.get('title', '')),
				str(cnf.get('text', '')), buttons, str(cnf.get('bitmap', '')),
				default=default,
				parent=master).run()
			self.num = -1 if result is None else result

	def destroy(self):
		pass
