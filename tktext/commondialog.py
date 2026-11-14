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

"""commondialog — base class of the standard dialogs.  Mirrors
tkinter.commondialog: subclasses implement _show(options) instead of
calling a Tk command."""


class Dialog:
	command = None

	def __init__(self, master=None, **options):
		if master is None:
			master = options.get('parent')
		self.master	= master
		self.options	= options

	def _fixoptions(self):
		pass

	def _fixresult(self, widget, result):
		return result

	def _show(self, options):
		raise NotImplementedError

	def show(self, **options):
		"""Run the dialog modally and return its result."""
		for k, v in options.items():
			self.options[k] = v
		self._fixoptions()
		opts = dict(self.options)
		if self.master is not None:
			opts.setdefault('parent', self.master)
		return self._fixresult(self.master, self._show(opts))
