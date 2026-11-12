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

"""filedialog — file and directory picker dialogs.  Mirrors tkinter.filedialog."""
from ._dialog import _getApp, _FileDialog


def _run(title, mode, initialdir=None, initialfile='',
		filetypes=None, defaultextension='', multiple=False, parent=None, **kw):
	app = _getApp(parent)
	if app is None:
		return '' if not multiple else ()
	result = _FileDialog(app, title, mode=mode,
		initialdir=initialdir, initialfile=initialfile or '',
		filetypes=filetypes, defaultextension=defaultextension or '',
		multiple=multiple).run()
	if multiple:
		return (result,) if result else ()
	return result or ''


def askopenfilename(title='Open', initialdir=None, initialfile='',
		filetypes=None, defaultextension='', parent=None, **kw) -> str:
	return _run(title, 'open', initialdir=initialdir, initialfile=initialfile,
		filetypes=filetypes, defaultextension=defaultextension, parent=parent)


def asksaveasfilename(title='Save As', initialdir=None, initialfile='',
		filetypes=None, defaultextension='', parent=None, **kw) -> str:
	return _run(title, 'save', initialdir=initialdir, initialfile=initialfile,
		filetypes=filetypes, defaultextension=defaultextension, parent=parent)


def askopenfilenames(title='Open', initialdir=None,
		filetypes=None, parent=None, **kw) -> tuple:
	return _run(title, 'open', initialdir=initialdir,
		filetypes=filetypes, multiple=True, parent=parent)


def askdirectory(title='Choose Directory', initialdir=None,
		parent=None, **kw) -> str:
	return _run(title, 'dir', initialdir=initialdir, parent=parent)


def askopenfile(mode='r', **kw):
	"""Ask for a file name and return the opened file (or None)."""
	fn = askopenfilename(**kw)
	return open(fn, mode) if fn else None


def asksaveasfile(mode='w', **kw):
	fn = asksaveasfilename(**kw)
	return open(fn, mode) if fn else None
