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

"""scrolledtext — Text with a vertical scrollbar.  Mirrors
tkinter.scrolledtext: the Text is placed in a Frame and the geometry
methods (pack, grid, place) act on the frame."""

from ._frame		import Frame
from ._text		import Text
from ._scrollbar	import Scrollbar
from ._core		import Widget

__all__ = ['ScrolledText']


class ScrolledText(Text):
	def __init__(self, master=None, **kw):
		self.frame = Frame(master)
		self.vbar  = Scrollbar(self.frame)
		self.vbar.pack(side='right', fill='y')

		kw['yscrollcommand'] = self.vbar.set
		Text.__init__(self, self.frame, **kw)
		self.pack(side='left', fill='both', expand=True)
		self.vbar['command'] = self.yview

		# geometry methods of the Text act on the frame (like tkinter)
		for name in vars(Widget):
			if (name.startswith(('pack', 'grid', 'place')) or name in ('forget', 'info', 'location')) \
					and callable(getattr(Widget, name)) and not name.endswith('_propagate') \
					and name not in ('pack_slaves', 'grid_slaves', 'place_slaves'):
				setattr(self, name, getattr(self.frame, name))

	def __str__(self):
		return str(self.frame)
