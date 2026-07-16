"""filedialog — file and directory picker dialogs.  Mirrors tkinter.filedialog."""
from ._dialog import _getApp, _FileDialog


def _run(title, mode, initialdir=None, initialfile='',
		filetypes=None, defaultextension='', multiple=False, **kw):
	app = _getApp()
	if app is None:
		return '' if not multiple else []
	result = _FileDialog(app, title, mode=mode,
		initialdir=initialdir, initialfile=initialfile,
		filetypes=filetypes, defaultextension=defaultextension,
		multiple=multiple).run()
	if multiple:
		return [result] if result else []
	return result or ''


def askopenfilename(title='Open', initialdir=None, initialfile='',
		filetypes=None, defaultextension='', parent=None, **kw) -> str:
	return _run(title, 'open', initialdir=initialdir, initialfile=initialfile,
		filetypes=filetypes, defaultextension=defaultextension)


def asksaveasfilename(title='Save As', initialdir=None, initialfile='',
		filetypes=None, defaultextension='', parent=None, **kw) -> str:
	return _run(title, 'save', initialdir=initialdir, initialfile=initialfile,
		filetypes=filetypes, defaultextension=defaultextension)


def askopenfilenames(title='Open', initialdir=None,
		filetypes=None, parent=None, **kw) -> list:
	return _run(title, 'open', initialdir=initialdir,
		filetypes=filetypes, multiple=True)


def askdirectory(title='Choose Directory', initialdir=None,
		parent=None, **kw) -> str:
	return _run(title, 'dir', initialdir=initialdir)
