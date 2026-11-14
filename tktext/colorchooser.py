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

"""colorchooser — tkinter.colorchooser replacement (text input of a colour)."""
from ._colors import ColorManager
from .commondialog import Dialog


def askcolor(color=None, **options):
	"""Ask for a colour name or #rrggbb value.

	Returns ((r, g, b), '#rrggbb') like tkinter, or (None, None)."""
	from .simpledialog import askstring
	initial = '' if color is None else str(color)
	value   = askstring(options.get('title', 'Color'),
			'Color (name or #rrggbb):', initialvalue=initial,
			parent=options.get('parent'))
	if not value:
		return (None, None)
	rgb = ColorManager.toRGB(value.strip())
	if rgb is None:
		return (None, None)
	return (rgb, '#%02x%02x%02x' % rgb)


class Chooser(Dialog):
	"""Colour chooser dialog (tkinter.colorchooser.Chooser)."""
	command = 'tk_chooseColor'

	def _show(self, options):
		return askcolor(options.pop('initialcolor', None), **options)
