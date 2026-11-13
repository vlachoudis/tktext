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

"""font — tkinter.font compatible fonts for a character terminal.

Every character is one cell wide and one line high, so measure() returns
the length of the text and the line space is 1.  Font attributes are kept
so that configure()/actual()/cget() round-trip; 'weight': 'bold' and
'underline' are used by widgets that honour fonts.
"""
from ._core import TclError

NORMAL		= 'normal'
ROMAN		= 'roman'
BOLD		= 'bold'
ITALIC		= 'italic'

_fonts		= {}	# name -> Font
_fontCount	= 0
_DEFAULTS	= ('TkDefaultFont', 'TkTextFont', 'TkFixedFont', 'TkMenuFont',
		   'TkHeadingFont', 'TkCaptionFont', 'TkSmallCaptionFont',
		   'TkIconFont', 'TkTooltipFont')


def _parse(font):
	"""Convert a font description (tuple, 'family size style', Font) into
	an option dict."""
	opts = {}
	if font is None or font == '':
		return opts
	if isinstance(font, Font):
		return dict(font._opts)
	if isinstance(font, str):
		if font in _fonts:
			return dict(_fonts[font]._opts)
		from ._tcl import _splitlist
		font = _splitlist(font)
	if isinstance(font, (tuple, list)):
		if font:
			opts['family'] = str(font[0])
		if len(font) > 1:
			try:
				opts['size'] = int(font[1])
			except (TypeError, ValueError):
				pass
		for style in font[2:]:
			for s in str(style).split():
				if s in (BOLD, NORMAL):
					opts['weight'] = s
				elif s in (ITALIC, ROMAN):
					opts['slant'] = s
				elif s == 'underline':
					opts['underline'] = 1
				elif s == 'overstrike':
					opts['overstrike'] = 1
	return opts


class Font:
	"""Mirrors tkinter.font.Font."""

	def __init__(self, root=None, font=None, name=None, exists=False, **options):
		global _fontCount
		if name is None:
			_fontCount += 1
			name = f'font{_fontCount}'
		self.name	= str(name)
		if exists and self.name in _fonts:
			self._opts = _fonts[self.name]._opts
		else:
			self._opts = {'family': 'Terminal', 'size': 10,
				'weight': NORMAL, 'slant': ROMAN,
				'underline': 0, 'overstrike': 0}
			self._opts.update(_parse(font))
			self._opts.update(options)
			_fonts[self.name] = self
		self.delete_font = False

	def __str__(self):
		return self.name

	def __eq__(self, other):
		return isinstance(other, Font) and self.name == other.name

	def __hash__(self):
		return hash(self.name)

	def __getitem__(self, key):
		return self.cget(key)

	def __setitem__(self, key, value):
		self.configure(**{key: value})

	def copy(self):
		return Font(**self._opts)

	def actual(self, option=None, displayof=None):
		return self._opts.get(option) if option else dict(self._opts)

	def cget(self, option):
		if option not in self._opts:
			raise TclError(f'bad option "-{option}"')
		return self._opts[option]

	def configure(self, **options):
		if not options:
			return dict(self._opts)
		self._opts.update(options)

	config = configure

	def measure(self, text, displayof=None):
		return max((len(l) for l in str(text).split('\n')), default=0)

	def metrics(self, *options, **kw):
		values = {'ascent': 1, 'descent': 0, 'linespace': 1, 'fixed': 1}
		if len(options) == 1:
			return values[options[0].lstrip('-')]
		if options:
			return {o.lstrip('-'): values[o.lstrip('-')] for o in options}
		return values


def families(root=None, displayof=None):
	return ('Terminal',)


def names(root=None):
	return tuple(_fonts.keys())


def nametofont(name, root=None):
	name = str(name)
	if name not in _fonts:
		if name in _DEFAULTS:
			return Font(name=name)
		raise TclError(f'named font "{name}" does not exist')
	return _fonts[name]


def isBold(font) -> bool:
	"""True if *font* (any tkinter font description) asks for bold."""
	return _parse(font).get('weight') == BOLD


for _name in _DEFAULTS:
	Font(name=_name)
