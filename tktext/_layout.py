"""
Layout managers: pack, grid, place.

All functions receive the container widget and operate on its _children,
setting each child's _x, _y, _w, _h.  After layout the container must call
_layoutChildren() on each child that is itself a container.
"""


# ---------------------------------------------------------------------------
# Pack
# ---------------------------------------------------------------------------

def doPackLayout(container, children):
	"""
	*children* is a list of (widget, opts) pairs in packing order.
	Implements the classic tkinter cavity algorithm.
	"""
	if not children:
		return

	cx = container._x
	cy = container._y
	cw = container._w
	ch = container._h

	# Cavity edges (absolute screen coords)
	top    = cy
	left   = cx
	right  = cx + cw
	bottom = cy + ch

	# ---- first pass: identify expand widgets and remaining space ----
	tbExpand = [(w, o) for w, o in children
		if o.get('side', 'top') in ('top', 'bottom') and o.get('expand')]
	lrExpand = [(w, o) for w, o in children
		if o.get('side', 'top') in ('left', 'right') and o.get('expand')]

	usedH = sum(
		w._preferredSize()[1] + 2*o.get('ipady', 0) + 2*o.get('pady', 0)
		for w, o in children
		if o.get('side', 'top') in ('top', 'bottom')
	)
	usedW = sum(
		w._preferredSize()[0] + 2*o.get('ipadx', 0) + 2*o.get('padx', 0)
		for w, o in children
		if o.get('side', 'top') in ('left', 'right')
	)
	extraH = max(0, ch - usedH)
	extraW = max(0, cw - usedW)
	perExpH = extraH // len(tbExpand) if tbExpand else 0
	perExpW = extraW // len(lrExpand) if lrExpand else 0

	# ---- second pass: place widgets in cavity order ----
	for widget, opts in children:
		side   = opts.get('side', 'top')
		padx   = opts.get('padx', 0)
		pady   = opts.get('pady', 0)
		ipadx  = opts.get('ipadx', 0)
		ipady  = opts.get('ipady', 0)
		fill   = opts.get('fill', 'none')
		expand = opts.get('expand', False)
		anchor = opts.get('anchor', 'center')

		pw, ph = widget._preferredSize()
		cavW = right - left
		cavH = bottom - top

		if side in ('top', 'bottom'):
			# strip height
			stripH = ph + 2*ipady + (perExpH if expand and tbExpand else 0)
			stripH = max(1, stripH)

			wW = (cavW - 2*padx) if fill in ('x', 'both') else (pw + 2*ipadx)
			wH = stripH if fill in ('y', 'both') else (ph + 2*ipady)
			wW = max(1, wW)
			wH = max(1, wH)

			# horizontal anchor
			if anchor in ('w', 'nw', 'sw'):
				wx = left + padx
			elif anchor in ('e', 'ne', 'se'):
				wx = left + cavW - padx - wW
			else:
				wx = left + (cavW - wW) // 2

			if side == 'top':
				wy = top + pady
				top += stripH + 2*pady
			else:
				wy = bottom - stripH - pady
				bottom -= stripH + 2*pady

		else:  # left / right
			stripW = pw + 2*ipadx + (perExpW if expand and lrExpand else 0)
			stripW = max(1, stripW)

			wW = stripW if fill in ('x', 'both') else (pw + 2*ipadx)
			wH = (cavH - 2*pady) if fill in ('y', 'both') else (ph + 2*ipady)
			wW = max(1, wW)
			wH = max(1, wH)

			# vertical anchor
			if anchor in ('n', 'nw', 'ne'):
				wy = top + pady
			elif anchor in ('s', 'sw', 'se'):
				wy = top + cavH - pady - wH
			else:
				wy = top + (cavH - wH) // 2

			if side == 'left':
				wx = left + padx
				left += stripW + 2*padx
			else:
				wx = right - stripW - padx
				right -= stripW + 2*padx

		widget._doLayout(wx, wy, wW, wH)
		if hasattr(widget, '_layoutChildren'):
			widget._layoutChildren()


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------

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
	cw = container._w
	ch = container._h

	# ---- find grid extents ----
	maxRow = max(o['row'] + o.get('rowspan', 1) - 1 for _, o in children)
	maxCol = max(o['column'] + o.get('columnspan', 1) - 1 for _, o in children)
	nRows = maxRow + 1
	nCols = maxCol + 1

	# ---- compute minimum sizes ----
	minColW = [0] * nCols
	minRowH = [0] * nRows

	for widget, opts in children:
		r = opts['row']
		c = opts['column']
		rs = opts.get('rowspan', 1)
		cs = opts.get('columnspan', 1)
		pw, ph = widget._preferredSize()
		pw += 2*opts.get('ipadx', 0) + 2*opts.get('padx', 0)
		ph += 2*opts.get('ipady', 0) + 2*opts.get('pady', 0)
		# Distribute across spans (simplified: give all to first cell)
		minColW[c] = max(minColW[c], pw // cs)
		minRowH[r] = max(minRowH[r], ph // rs)

	# Apply minsize from config
	for c, cfg in colCfg.items():
		if c < nCols:
			minColW[c] = max(minColW[c], cfg.get('minsize', 0))
	for r, cfg in rowCfg.items():
		if r < nRows:
			minRowH[r] = max(minRowH[r], cfg.get('minsize', 0))

	# ---- distribute extra space to weighted rows/cols ----
	totalMinW = sum(minColW)
	totalMinH = sum(minRowH)
	extraW = max(0, cw - totalMinW)
	extraH = max(0, ch - totalMinH)

	totalColWeight = sum(colCfg.get(c, {}).get('weight', 0) for c in range(nCols))
	totalRowWeight = sum(rowCfg.get(r, {}).get('weight', 0) for r in range(nRows))

	colW = list(minColW)
	rowH = list(minRowH)

	if totalColWeight > 0:
		for c in range(nCols):
			w = colCfg.get(c, {}).get('weight', 0)
			colW[c] += int(extraW * w / totalColWeight)

	if totalRowWeight > 0:
		for r in range(nRows):
			w = rowCfg.get(r, {}).get('weight', 0)
			rowH[r] += int(extraH * w / totalRowWeight)

	# ---- compute cumulative offsets ----
	colX = [cx]
	for c in range(nCols - 1):
		colX.append(colX[-1] + colW[c])

	rowY = [cy]
	for r in range(nRows - 1):
		rowY.append(rowY[-1] + rowH[r])

	# ---- place each widget ----
	for widget, opts in children:
		r    = opts['row']
		c    = opts['column']
		rs   = opts.get('rowspan', 1)
		cs   = opts.get('columnspan', 1)
		padx = opts.get('padx', 0)
		pady = opts.get('pady', 0)
		ipadx = opts.get('ipadx', 0)
		ipady = opts.get('ipady', 0)
		sticky = opts.get('sticky', '')

		# Cell bounding box
		cellX = colX[c]
		cellY = rowY[r]
		cellW = sum(colW[c:c+cs])
		cellH = sum(rowH[r:r+rs])

		pw, ph = widget._preferredSize()
		pw += 2*ipadx
		ph += 2*ipady

		# Apply sticky (fill / anchor)
		if 'e' in sticky and 'w' in sticky:
			wW = cellW - 2*padx
		elif 'e' in sticky:
			wW = pw
		elif 'w' in sticky:
			wW = pw
		else:
			wW = pw

		if 'n' in sticky and 's' in sticky:
			wH = cellH - 2*pady
		elif 'n' in sticky:
			wH = ph
		elif 's' in sticky:
			wH = ph
		else:
			wH = ph

		wW = max(1, min(wW, cellW - 2*padx))
		wH = max(1, min(wH, cellH - 2*pady))

		# Horizontal position
		if 'w' in sticky and 'e' not in sticky:
			wx = cellX + padx
		elif 'e' in sticky and 'w' not in sticky:
			wx = cellX + cellW - wW - padx
		else:
			wx = cellX + (cellW - wW) // 2

		# Vertical position
		if 'n' in sticky and 's' not in sticky:
			wy = cellY + pady
		elif 's' in sticky and 'n' not in sticky:
			wy = cellY + cellH - wH - pady
		else:
			wy = cellY + (cellH - wH) // 2

		widget._doLayout(wx, wy, wW, wH)
		if hasattr(widget, '_layoutChildren'):
			widget._layoutChildren()


# ---------------------------------------------------------------------------
# Place
# ---------------------------------------------------------------------------

def doPlaceLayout(container, children):
	cx = container._x
	cy = container._y
	cw = container._w
	ch = container._h

	for widget, opts in children:
		pw, ph = widget._preferredSize()

		relx = opts.get('relx', 0.0) or 0.0
		rely = opts.get('rely', 0.0) or 0.0
		x = int(opts.get('x', 0) or 0) + int(relx * cw)
		y = int(opts.get('y', 0) or 0) + int(rely * ch)

		rw = opts.get('relwidth')
		rh = opts.get('relheight')
		ow = opts.get('width')
		oh = opts.get('height')

		wW = int(rw * cw) if rw is not None else (int(ow) if ow is not None else pw)
		wH = int(rh * ch) if rh is not None else (int(oh) if oh is not None else ph)
		wW = max(1, wW)
		wH = max(1, wH)

		anchor = opts.get('anchor', 'nw')
		if 'e' in anchor:
			x -= wW
		elif anchor not in ('nw', 'w', 'sw'):
			x -= wW // 2
		if 's' in anchor:
			y -= wH
		elif anchor not in ('nw', 'n', 'ne'):
			y -= wH // 2

		widget._doLayout(cx + x, cy + y, wW, wH)
		if hasattr(widget, '_layoutChildren'):
			widget._layoutChildren()
