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


class Chooser:
	def __init__(self, master=None, **options):
		self.options = options

	def show(self, **options):
		return askcolor(**{**self.options, **options})
