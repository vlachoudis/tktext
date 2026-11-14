import unittest

from fakescreen import makeApp, attach, tk


class PackTest(unittest.TestCase):

	def test_top_bottom_left_right(self):
		root, scr = makeApp(40, 11)
		top    = tk.Label(root, text='top');    top.pack(side=tk.TOP, fill=tk.X)
		bottom = tk.Label(root, text='bottom'); bottom.pack(side=tk.BOTTOM, fill=tk.X)
		left   = tk.Label(root, text='L');      left.pack(side=tk.LEFT, fill=tk.Y)
		right  = tk.Label(root, text='R');      right.pack(side=tk.RIGHT, fill=tk.Y)
		attach(root)
		self.assertEqual((top._x, top._y, top._width, top._height), (0, 1, 40, 1))
		self.assertEqual((bottom._x, bottom._y, bottom._width), (0, 10, 40))
		self.assertEqual((left._x, left._y, left._width, left._height), (0, 2, 1, 8))
		self.assertEqual((right._x, right._y, right._width, right._height), (39, 2, 1, 8))

	def test_expand_shares_space(self):
		root, scr = makeApp(20, 11)
		a = tk.Frame(root, height=1); a.pack(fill=tk.BOTH, expand=True)
		b = tk.Frame(root, height=1); b.pack(fill=tk.BOTH, expand=True)
		attach(root)
		self.assertEqual(a._height + b._height, 10)
		self.assertLessEqual(abs(a._height - b._height), 1)

	def test_anchor_center_is_centered(self):
		root, scr = makeApp(20, 6)
		f = tk.Frame(root); f.pack(fill=tk.BOTH, expand=True)
		b = tk.Label(f, text='x'); b.pack(side=tk.RIGHT)
		attach(root)
		# side=right, anchor center → vertically centred in the 5-row parcel
		self.assertEqual(f._height, 5)
		self.assertEqual(b._y, f._y + 2)

	def test_tuple_padding(self):
		root, scr = makeApp(20, 5)
		lbl = tk.Label(root, text='abc')
		lbl.pack(side=tk.LEFT, padx=(3, 0))
		attach(root)
		self.assertEqual(lbl._x, 3)

	def test_frame_preferred_size_sums_stacked_children(self):
		root, scr = makeApp(40, 20)
		f = tk.Frame(root)
		for i in range(3):
			tk.Label(f, text=f'line{i}').pack()
		f.pack()
		self.assertEqual(f._preferredSize(), (5, 3))
		attach(root)
		self.assertEqual(f._height, 3)
		self.assertEqual([c._y for c in f._children], [f._y, f._y + 1, f._y + 2])

	def test_expanding_widget_shrinks_to_keep_later_widgets_visible(self):
		root, scr = makeApp(20, 10)
		big = tk.Listbox(root, height=30); big.pack(fill=tk.BOTH, expand=True)
		status = tk.Label(root, text='status'); status.pack(fill=tk.X)
		attach(root)
		self.assertEqual(status._y, 9)
		self.assertEqual(status._height, 1)
		self.assertEqual(big._height, 8)

	def test_forget_unmaps(self):
		root, scr = makeApp(20, 5)
		b = tk.Button(root, text='x'); b.pack()
		attach(root)
		self.assertTrue(b._isMapped())
		b.pack_forget()
		root._update()
		self.assertFalse(b._isMapped())
		self.assertIsNot(root._findAt(b._x, b._y), b)


class GridTest(unittest.TestCase):

	def test_weights_and_sticky(self):
		root, scr = makeApp(30, 11)
		root.columnconfigure(0, weight=1)
		root.columnconfigure(1, weight=2)
		root.rowconfigure(0, weight=1)
		a = tk.Frame(root); a.grid(row=0, column=0, sticky='nsew')
		b = tk.Frame(root); b.grid(row=0, column=1, sticky=tk.NSEW)
		attach(root)
		self.assertEqual(a._width + b._width, 30)
		self.assertEqual(a._width, 10)
		self.assertEqual(a._height, 10)

	def test_default_row_is_next_row(self):
		root, scr = makeApp(30, 10)
		a = tk.Label(root, text='a'); a.grid()
		b = tk.Label(root, text='b'); b.grid()
		self.assertEqual((a.grid_info()['row'], b.grid_info()['row']), (0, 1))

	def test_tuple_pad_and_span(self):
		root, scr = makeApp(30, 10)
		a = tk.Label(root, text='aaaa'); a.grid(row=0, column=0, padx=(2, 0))
		b = tk.Label(root, text='bb');   b.grid(row=0, column=1)
		c = tk.Label(root, text='c');    c.grid(row=1, column=0, columnspan=2, sticky='ew')
		attach(root)
		self.assertEqual(a._x, 2)
		self.assertEqual(c._width, 8)

	def test_weighted_rows_shrink_when_short(self):
		root, scr = makeApp(20, 6)
		root.rowconfigure(0, weight=1)
		big = tk.Listbox(root, height=20); big.grid(row=0, column=0, sticky='nsew')
		lbl = tk.Label(root, text='x');     lbl.grid(row=1, column=0)
		attach(root)
		self.assertEqual(lbl._y, 5)

	def test_spans_resolved_per_dimension(self):
		# flair's Geometry "Selection" group: a 2-row icon next to a
		# columnspan=3 row must not make the grid 4 rows high
		root, scr = makeApp(40, 10)
		f = tk.Frame(root); f.grid(row=0, column=0, sticky='nw')
		for i in range(3):
			f.grid_rowconfigure(i, weight=1)
		icon = tk.Frame(f, width=5, height=2)
		icon.grid(row=0, column=0, rowspan=2, sticky='nsew')
		lock = tk.Label(f, text='Lock')
		lock.grid(row=0, column=1, columnspan=3, sticky='nsew')
		tk.Label(f, text='Freeze').grid(row=1, column=1)
		vis = tk.Label(f, text='Visibility')
		vis.grid(row=2, column=0)
		attach(root)
		self.assertEqual(f.winfo_reqheight(), 3)
		self.assertEqual((icon._height, vis._y - f._y), (2, 2))


	def test_abbreviated_options(self):
		# Tk accepts unique abbreviations: flair grids with stick=NSEW
		root, scr = makeApp(30, 6)
		root.grid_columnconfigure(0, weight=1)
		a = tk.Frame(root, height=1); a.grid(row=0, column=0, stick=tk.EW)
		b = tk.Label(root, text='b')
		b.grid(row=1, column=0, columnsp=1, sti='w')
		attach(root)
		self.assertEqual(a.grid_info()['sticky'], tk.EW)
		self.assertEqual((a._x, a._width), (0, 30))
		self.assertEqual(b.grid_info()['sticky'], 'w')


class PlaceTest(unittest.TestCase):

	def test_relative_center(self):
		root, scr = makeApp(41, 11)
		lbl = tk.Label(root, text='abc')
		lbl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
		attach(root)
		self.assertEqual((lbl._x, lbl._y), (20 - 1, 1 + 5 - 0))


if __name__ == '__main__':
	unittest.main()
