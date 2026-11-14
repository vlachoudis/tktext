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

An image may also carry a one-cell ``glyph`` (``image.glyph = '▾'``): an
image-only widget shows it instead of the alt text (whatever the image size
or whether it is clickable; a 32 px icon becomes a 5x2 box ``│ + │``), and it is drawn next to the text when
``compound=`` puts the image beside it, e.g. the
dropdown triangle of a menu button.  Images named like a known arrow or
triangle (``triangle_down``, ``arrow_up`` …) get their glyph by default.
"""
import os
import struct
import base64

from ._core import TclError

_images		= {}	# name -> Image
_imageCount	= 0

# Default glyph of images named after an arrow/triangle shape
_NAMED_GLYPHS	= {
	'triangle_down':	'▾',
	'triangle_up':		'▴',
	'triangle_left':	'◂',
	'triangle_right':	'▸',
	'arrow_down':		'↓',
	'arrow_up':		'↑',
	'arrow_left':		'←',
	'arrow_right':		'→',
}


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
		self.glyph	= ''		# one cell shown next to the text (compound)
		self.configure(**{**cnf, **kw})
		_images[self.name] = self

	def __str__(self):
		return self.name

	def __del__(self):
		if _images.get(getattr(self, 'name', None)) is self:
			del _images[self.name]

	def __setattr__(self, key, value):
		super().__setattr__(key, value)
		# a known shape name also gives the image its glyph
		if key == 'alt' and not getattr(self, 'glyph', ''):
			glyph = _NAMED_GLYPHS.get(str(value).lower())
			if glyph:
				super().__setattr__('glyph', glyph)

	def configure(self, **kw):
		if 'alt' in kw:
			self.alt = str(kw.pop('alt') or '')
		if 'glyph' in kw:
			self.glyph = str(kw.pop('glyph') or '')
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

	def cget(self, option):
		return self._opts.get(option, '')

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
		img.alt   = self.alt
		img.glyph = self.glyph
		return img

	def blank(self):
		pass

	def _region(self, fromCoords):
		"""Size of the from_coords=(x1, y1[, x2, y2]) region."""
		w, h = self._size
		if not fromCoords:
			return w, h
		c = [int(v) for v in fromCoords]
		if len(c) < 4:
			return max(0, w - c[0]), max(0, h - (c[1] if len(c) > 1 else 0))
		return abs(c[2] - c[0]), abs(c[3] - c[1])

	@staticmethod
	def _factors(value, default):
		if value is None:
			return default, default
		if isinstance(value, (int, float, str)):
			return int(value), int(value)
		v = [int(x) for x in value]
		return v[0], v[-1]

	def copy(self, *, from_coords=None, zoom=None, subsample=None):
		w, h	= self._region(from_coords)
		zx, zy	= self._factors(zoom, 1)
		sx, sy	= self._factors(subsample, 1)
		return self._derived(w * zx // max(1, sx), h * zy // max(1, sy))

	def zoom(self, x, y='', *, from_coords=None):
		y = x if y == '' else y
		return self.copy(zoom=(x, y), from_coords=from_coords)

	def subsample(self, x, y='', *, from_coords=None):
		y = x if y == '' else y
		return self.copy(subsample=(x, y), from_coords=from_coords)

	def copy_replace(self, sourceImage, *, from_coords=None, to=None, shrink=False,
			zoom=None, subsample=None, compositingrule=None):
		"""Copy (a region of) *sourceImage* into this image: only the size
		and the glyph matter in a terminal."""
		if isinstance(sourceImage, str):
			sourceImage = _imageByName(sourceImage)
		img = sourceImage.copy(from_coords=from_coords, zoom=zoom, subsample=subsample)
		x, y = (list(map(int, to)) + [0, 0])[:2] if to else (0, 0)
		w, h = self._size
		if shrink:
			w, h = x + img._size[0], y + img._size[1]
		else:
			w, h = max(w, x + img._size[0]), max(h, y + img._size[1])
		self.configure(width=w, height=h)
		self.glyph = sourceImage.glyph

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
