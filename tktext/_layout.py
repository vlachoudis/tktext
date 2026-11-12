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

"""
Layout managers: pack, grid, place.

All functions receive a *container* (any object exposing _x, _y, _w, _h —
the content rectangle) and a list of (widget, opts) pairs.  They set each
child's geometry through child._doLayout() and recurse into containers.

The pack implementation follows Tk's tkPack.c (cavity algorithm with
XExpansion / YExpansion) so that expand / fill behave as in tkinter.
"""


# ---------------------------------------------------------------------------
# Option helpers
# ---------------------------------------------------------------------------

def _pads(v):
	"""Normalise a pad value to (before, after): 2 → (2,2), (1,3) → (1,3)."""
	if isinstance(v, (tuple, list)):
		if len(v) == 0:
			return (0, 0)
		if len(v) == 1:
			a = int(v[0] or 0)
			return (a, a)
		return (int(v[0] or 0), int(v[1] or 0))
	if isinstance(v, str):
		parts = v.split()
		if len(parts) >= 2:
			return (int(parts[0]), int(parts[1]))
		v = parts[0] if parts else 0
	a = int(v or 0)
	return (a, a)


def _p(v) -> int:
	"""Total padding of a pad value: 2 → 4, (1,3) → 4."""
	a, b = _pads(v)
	return a + b


def _ipad(v) -> int:
	"""Internal padding total (ipadx=1 adds one cell on each side)."""
	if isinstance(v, (tuple, list)):
		v = v[0] if v else 0
	return 2 * int(v or 0)


def _truthy(v) -> bool:
	if isinstance(v, str):
		return v.lower() not in ('', '0', 'false', 'no', 'off')
	return bool(v)


def _anchor(v) -> str:
	"""Normalise an anchor: 'center' becomes '' so that letter tests
	('e' in anchor, 'n' in anchor …) only see compass directions."""
	v = str(v or 'center').lower()
	return '' if v == 'center' else v


def _sticky(v) -> str:
	if isinstance(v, (tuple, list)):
		v = ''.join(str(x) for x in v)
	return str(v or '').lower()


def _layoutWidget(widget, x, y, w, h):
	w = max(0, w)
	h = max(0, h)
	if w == 0 or h == 0:
		widget._unmapTree()
		return
	widget._doLayout(x, y, w, h)
	if hasattr(widget, '_layoutChildren'):
		widget._layoutChildren()


# ---------------------------------------------------------------------------
# Pack
# ---------------------------------------------------------------------------

def _isVertical(opts) -> bool:
	return opts.get('side', 'top') in ('top', 'bottom')


def _packItems(children):
	"""Return [(widget, opts, reqW, reqH)] where req* include padding."""
	items = []
	for widget, opts in children:
		pw, ph = widget._preferredSize()
		items.append([widget, opts,
			pw + _p(opts.get('padx', 0)) + _ipad(opts.get('ipadx', 0)),
			ph + _p(opts.get('pady', 0)) + _ipad(opts.get('ipady', 0))])
	return items


def _packExtent(items):
	"""Port of tkPack.c geometry propagation on precomputed items."""
	width = height = maxW = maxH = 0
	for _, opts, reqW, reqH in items:
		if _isVertical(opts):
			maxW	 = max(maxW, reqW + width)
			height	+= reqH
		else:
			maxH	 = max(maxH, reqH + height)
			width	+= reqW
	return (max(maxW, width), max(maxH, height))


def _shrinkToFit(items, availW, availH):
	"""A terminal cannot grow like a toplevel window: when the packed
	children request more than the container offers, take the shortage
	from the expanding widgets first (down to one cell) so the widgets
	packed after them stay visible."""
	for axis, avail in ((0, availW), (1, availH)):
		deficit = _packExtent(items)[axis] - avail
		if deficit <= 0:
			continue
		for item in items:
			opts = item[1]
			if deficit <= 0:
				break
			if not _truthy(opts.get('expand')) or _isVertical(opts) != (axis == 1):
				continue
			take = min(deficit, max(0, item[2 + axis] - 1))
			item[2 + axis] -= take
			deficit        -= take


def _expansion(items, start, cavity, vertical):
	"""Port of tkPack.c XExpansion (vertical=False) / YExpansion."""
	minExpand = cavity
	numExpand = 0
	for _, opts, reqW, reqH in items[start:]:
		child = reqH if vertical else reqW
		if _isVertical(opts) != vertical:
			if numExpand:
				minExpand = min(minExpand, (cavity - child) // numExpand)
		else:
			cavity -= child
			if _truthy(opts.get('expand')):
				numExpand += 1
	if numExpand:
		minExpand = min(minExpand, cavity // numExpand)
	return max(0, minExpand)


def doPackLayout(container, children):
	"""
	*children* is a list of (widget, opts) pairs in packing order.
	Implements the classic Tk cavity algorithm.
	"""
	if not children:
		return

	cavX = container._x
	cavY = container._y
	cavW = container._width
	cavH = container._height

	items = _packItems(children)
	_shrinkToFit(items, cavW, cavH)

	for i, (widget, opts, reqW, reqH) in enumerate(items):
		side	= opts.get('side', 'top')
		fill	= str(opts.get('fill', 'none') or 'none').lower()
		expand	= _truthy(opts.get('expand', False))
		anchor	= _anchor(opts.get('anchor', 'center'))
		padL, padR = _pads(opts.get('padx', 0))
		padT, padB = _pads(opts.get('pady', 0))
		borderX	= padL + padR
		borderY	= padT + padB

		# ---- allocate the parcel for this slave ----
		if side in ('top', 'bottom'):
			frameW = cavW
			frameH = reqH
			if expand:
				frameH += _expansion(items, i, cavH, True)
			cavH -= frameH
			if cavH < 0:
				frameH += cavH
				cavH = 0
			frameX = cavX
			if side == 'top':
				frameY = cavY
				cavY  += frameH
			else:
				frameY = cavY + cavH
		else:
			frameH = cavH
			frameW = reqW
			if expand:
				frameW += _expansion(items, i, cavW, False)
			cavW -= frameW
			if cavW < 0:
				frameW += cavW
				cavW = 0
			frameY = cavY
			if side == 'left':
				frameX = cavX
				cavX  += frameW
			else:
				frameX = cavX + cavW

		# ---- place the slave inside its parcel ----
		width	= reqW - borderX
		height	= reqH - borderY
		if fill in ('x', 'both') or width > frameW - borderX:
			width = frameW - borderX
		if fill in ('y', 'both') or height > frameH - borderY:
			height = frameH - borderY

		if 'w' in anchor:
			x = frameX + padL
		elif 'e' in anchor:
			x = frameX + frameW - width - padR
		else:
			x = frameX + padL + (frameW - borderX - width) // 2
		if 'n' in anchor:
			y = frameY + padT
		elif 's' in anchor:
			y = frameY + frameH - height - padB
		else:
			y = frameY + padT + (frameH - borderY - height) // 2

		_layoutWidget(widget, x, y, width, height)


def packPreferredSize(children):
	"""Return the (w, h) a container needs for its packed *children*."""
	return _packExtent(_packItems(children))


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------

def _gridMinSizes(children, rowCfg, colCfg):
	"""Return (minColW, minRowH) lists for the gridded *children*."""
	nRows = max(o['row'] + o.get('rowspan', 1) for _, o in children)
	nCols = max(o['column'] + o.get('columnspan', 1) for _, o in children)
	nRows = max(nRows, max((r + 1 for r in rowCfg), default=0))
	nCols = max(nCols, max((c + 1 for c in colCfg), default=0))

	minColW = [0] * nCols
	minRowH = [0] * nRows

	# Apply minsize from config
	for c, cfg in colCfg.items():
		if 0 <= c < nCols:
			minColW[c] = max(minColW[c], int(cfg.get('minsize', 0) or 0))
	for r, cfg in rowCfg.items():
		if 0 <= r < nRows:
			minRowH[r] = max(minRowH[r], int(cfg.get('minsize', 0) or 0))

	# Single-span widgets first, then spanning widgets grow the spanned
	# cells (extra goes to weighted cells, else to the last one).
	ordered = sorted(children, key=lambda wo: (wo[1].get('columnspan', 1),
		wo[1].get('rowspan', 1)))
	for widget, opts in ordered:
		r  = opts['row']
		c  = opts['column']
		rs = opts.get('rowspan', 1)
		cs = opts.get('columnspan', 1)
		pw, ph = widget._preferredSize()
		pw += _ipad(opts.get('ipadx', 0)) + _p(opts.get('padx', 0))
		ph += _ipad(opts.get('ipady', 0)) + _p(opts.get('pady', 0))
		_growSpan(minColW, c, cs, pw, colCfg)
		_growSpan(minRowH, r, rs, ph, rowCfg)
	return minColW, minRowH


def _growSpan(sizes, start, span, need, cfg):
	have = sum(sizes[start:start + span])
	if need <= have:
		return
	extra   = need - have
	idx     = list(range(start, start + span))
	weights = [int(cfg.get(i, {}).get('weight', 0) or 0) for i in idx]
	total   = sum(weights)
	if total <= 0:
		sizes[idx[-1]] += extra
		return
	given = 0
	for i, wgt in zip(idx, weights):
		add = extra * wgt // total
		sizes[i] += add
		given    += add
	# remainder to the last weighted cell
	for i, wgt in reversed(list(zip(idx, weights))):
		if wgt:
			sizes[i] += extra - given
			break


def _distribute(sizes, avail, cfg):
	"""Distribute extra space among weighted rows/columns; like Tk, take a
	shortage from the weighted ones (down to their minsize)."""
	extra	= avail - sum(sizes)
	weights	= [int(cfg.get(i, {}).get('weight', 0) or 0) for i in range(len(sizes))]
	total	= sum(weights)
	if total <= 0 or extra == 0:
		return list(sizes)
	if extra < 0:
		out     = list(sizes)
		deficit = -extra
		while deficit > 0:
			mins  = [int(cfg.get(i, {}).get('minsize', 0) or 0) for i in range(len(out))]
			cands = [i for i in range(len(out)) if weights[i] and out[i] > max(1, mins[i])]
			if not cands:
				break
			wsum = sum(weights[i] for i in cands)
			took = 0
			for i in cands:
				take = min(out[i] - max(1, mins[i]),
					max(1, deficit * weights[i] // wsum), deficit - took)
				out[i] -= take
				took   += take
				if took >= deficit:
					break
			deficit -= took
			if took == 0:
				break
		return out
	out	= list(sizes)
	given	= 0
	for i, wgt in enumerate(weights):
		add	 = extra * wgt // total
		out[i]	+= add
		given	+= add
	for i in range(len(out) - 1, -1, -1):
		if weights[i]:
			out[i] += extra - given
			break
	return out


def doGridLayout(container, children, rowCfg, colCfg):
	"""
	*children*  – list of (widget, opts) pairs.
	*rowCfg*    – dict row -> {'weight': int, 'minsize': int, 'pad': int}
	*colCfg*    – dict col -> {'weight': int, 'minsize': int, 'pad': int}
	"""
	if not children:
		return

	cx = container._x
	cy = container._y

	minColW, minRowH = _gridMinSizes(children, rowCfg, colCfg)
	colW = _distribute(minColW, container._width, colCfg)
	rowH = _distribute(minRowH, container._height, rowCfg)

	# ---- compute cumulative offsets ----
	colX = [cx]
	for w in colW:
		colX.append(colX[-1] + w)
	rowY = [cy]
	for h in rowH:
		rowY.append(rowY[-1] + h)

	right  = cx + container._width
	bottom = cy + container._height

	# ---- place each widget ----
	for widget, opts in children:
		r	= opts['row']
		c	= opts['column']
		rs	= opts.get('rowspan', 1)
		cs	= opts.get('columnspan', 1)
		padL, padR = _pads(opts.get('padx', 0))
		padT, padB = _pads(opts.get('pady', 0))
		sticky	= _sticky(opts.get('sticky', ''))

		# Cell bounding box (clipped to the container)
		cellX = colX[c]
		cellY = rowY[r]
		cellW = min(colX[c + cs], right) - cellX
		cellH = min(rowY[r + rs], bottom) - cellY

		pw, ph = widget._preferredSize()
		pw += _ipad(opts.get('ipadx', 0))
		ph += _ipad(opts.get('ipady', 0))

		availW = cellW - padL - padR
		availH = cellH - padT - padB
		wW = availW if ('e' in sticky and 'w' in sticky) else min(pw, availW)
		wH = availH if ('n' in sticky and 's' in sticky) else min(ph, availH)

		if 'w' in sticky and 'e' not in sticky:
			wx = cellX + padL
		elif 'e' in sticky and 'w' not in sticky:
			wx = cellX + cellW - padR - wW
		else:
			wx = cellX + padL + (availW - wW) // 2

		if 'n' in sticky and 's' not in sticky:
			wy = cellY + padT
		elif 's' in sticky and 'n' not in sticky:
			wy = cellY + cellH - padB - wH
		else:
			wy = cellY + padT + (availH - wH) // 2

		_layoutWidget(widget, wx, wy, wW, wH)


def gridPreferredSize(children, rowCfg, colCfg):
	if not children:
		return (0, 0)
	minColW, minRowH = _gridMinSizes(children, rowCfg, colCfg)
	return (sum(minColW), sum(minRowH))


# ---------------------------------------------------------------------------
# Place
# ---------------------------------------------------------------------------

def doPlaceLayout(container, children):
	cx = container._x
	cy = container._y
	cw = container._width
	ch = container._height

	for widget, opts in children:
		pw, ph = widget._preferredSize()

		relx = float(opts.get('relx', 0.0) or 0.0)
		rely = float(opts.get('rely', 0.0) or 0.0)
		x = int(opts.get('x', 0) or 0) + int(relx * cw)
		y = int(opts.get('y', 0) or 0) + int(rely * ch)

		rw = opts.get('relwidth')
		rh = opts.get('relheight')
		ow = opts.get('width')
		oh = opts.get('height')

		wW = int(ow or 0) if ow is not None else 0
		wH = int(oh or 0) if oh is not None else 0
		if rw is not None:
			wW += int(float(rw) * cw)
		if rh is not None:
			wH += int(float(rh) * ch)
		if ow is None and rw is None:
			wW = pw
		if oh is None and rh is None:
			wH = ph

		anchor = _anchor(opts.get('anchor', 'nw'))
		if 'e' in anchor:
			x -= wW
		elif 'w' not in anchor:
			x -= wW // 2
		if 's' in anchor:
			y -= wH
		elif 'n' not in anchor:
			y -= wH // 2

		_layoutWidget(widget, cx + x, cy + y, wW, wH)
