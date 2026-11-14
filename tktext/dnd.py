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

"""dnd — tkinter.dnd stand-in.  Drag and drop across widgets is not
available in a terminal; dnd_start() returns None."""


class DndHandler:
	"""Never starts a drag: root stays None, which tkinter code reads
	as "drag and drop not started" (like a second dnd in tkinter)."""

	root = None

	def __init__(self, source, event):
		self.source = source

	def on_motion(self, event):
		pass

	def on_release(self, event):
		pass

	def cancel(self, event=None):
		pass

	def finish(self, event, commit=0):
		pass


def dnd_start(source, event):
	return None
