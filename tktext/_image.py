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

"""Image objects (PhotoImage, BitmapImage) for a text terminal.

A terminal cannot show pixels, so images keep only their name and size.
Widgets accept ``image=`` and ``compound=`` like tkinter.  A clickable
image-only widget shows the image's ``alt`` text (or a glyph): programs
may set ``image.alt = 'save'`` (a plain attribute, harmless for tkinter),
an image loaded with file= defaults to its file name.
"""
import os
import struct
import base64

from ._core import TclError

_images		= {}	# name -> Image
_imageCount	= 0


def _imageByName(name):
	if isinstance(name, Image):
		return name
	return _images.get(str(name))


def image_names():
	return tuple(_images.keys())


def image_types():
	return ('photo', 'bitmap')


def _sizeFromBytes(raw):
	"""Return (width, height) of GIF/PNG/PPM image bytes, or (0, 0)."""
	try:
		if raw[:6] in (b'GIF87a', b'GIF89a'):
			return struct.unpack('<HH', raw[6:10])
		if raw[:8] == b'\x89PNG\r\n\x1a\n':
			return struct.unpack('>II', raw[16:24])
		if raw[:2] in (b'P3', b'P6'):
			tok = raw.split(None, 3)
			return (int(tok[1]), int(tok[2]))
	except Exception:
		pass
	return (0, 0)


class Image:
	"""Base image class (mirrors tkinter.Image)."""

	_type = 'photo'

	def __init__(self, imgtype='photo', name=None, cnf={}, master=None, **kw):
		global _imageCount
		if name is None:
			_imageCount += 1
			name = f'pyimage{_imageCount}'
		self.name	= str(name)
		self._opts	= {}
		self._size	= (0, 0)
		self.alt	= ''		# text shown in place of the image
		self.configure(**{**cnf, **kw})
		_images[self.name] = self

	def __str__(self):
		return self.name

	def __del__(self):
		if _images.get(getattr(self, 'name', None)) is self:
			del _images[self.name]

	def configure(self, **kw):
		if 'alt' in kw:
			self.alt = str(kw.pop('alt') or '')
		if kw.get('file') and not self.alt:
			self.alt = os.path.splitext(os.path.basename(str(kw['file'])))[0]
		self._opts.update(kw)
		raw = None
		if kw.get('data'):
			data = kw['data']
			if isinstance(data, str):
				try:
					raw = base64.b64decode(data)
				except Exception:
					raw = data.encode('latin-1', 'replace')
			else:
				raw = bytes(data)
		elif kw.get('file'):
			try:
				with open(kw['file'], 'rb') as f:
					raw = f.read(64)
			except OSError as ex:
				raise TclError(f'couldn\'t open "{kw["file"]}": {ex.strerror}')
		if raw is not None:
			self._size = _sizeFromBytes(raw)
		w = int(self._opts.get('width') or 0)
		h = int(self._opts.get('height') or 0)
		if w or h:
			self._size = (w or self._size[0], h or self._size[1])

	config = configure

	def cget(self, key):
		return self._opts.get(key, '')

	__getitem__ = cget

	def __setitem__(self, key, value):
		self.configure(**{key: value})

	def width(self):
		return self._size[0]

	def height(self):
		return self._size[1]

	def type(self):
		return self._type


class PhotoImage(Image):
	"""Full colour image (mirrors tkinter.PhotoImage)."""

	_type = 'photo'

	def __init__(self, name=None, cnf={}, master=None, **kw):
		super().__init__('photo', name, cnf, master, **kw)

	def _derived(self, w, h):
		img = PhotoImage(width=max(0, int(w)), height=max(0, int(h)))
		img.alt = self.alt
		return img

	def blank(self):
		pass

	def copy(self, *a, **kw):
		return self._derived(*self._size)

	def zoom(self, x, y=''):
		y = x if y == '' else y
		return self._derived(self._size[0] * int(x), self._size[1] * int(y))

	def subsample(self, x, y=''):
		y = x if y == '' else y
		return self._derived(self._size[0] // max(1, int(x)),
			self._size[1] // max(1, int(y)))

	def get(self, x, y):
		return (0, 0, 0)

	def put(self, data, to=None):
		pass

	def read(self, filename, format=None, from_coords=None, to=None, shrink=False):
		self.configure(file=filename)

	def write(self, filename, format=None, from_coords=None, **kw):
		raise TclError('tktext images have no pixel data')

	def data(self, format=None, **kw):
		return ''

	def transparency_get(self, x, y):
		return False

	def transparency_set(self, x, y, boolean):
		pass


class BitmapImage(Image):
	"""Two colour image (mirrors tkinter.BitmapImage)."""

	_type = 'bitmap'

	def __init__(self, name=None, cnf={}, master=None, **kw):
		super().__init__('bitmap', name, cnf, master, **kw)


# Glyph drawn for a widget that shows an image but no text
IMAGE_GLYPH = '▪'


def _imageText(text, image, compound):
	"""Return the string a label/button should display for text+image.

	tkinter shows only the image when *compound* is 'none' and an image is
	set; a terminal shows the text whenever there is some, otherwise a
	one-cell placeholder so that toolbar buttons stay visible/clickable.
	"""
	if not image:
		return text
	if text:
		return text
	return IMAGE_GLYPH
