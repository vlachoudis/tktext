#!/usr/bin/env python3
"""A plain tkinter/ttk program; nothing in it knows about tktext.

python3 examples/inventory.py               # real Tk window
python3 examples/tkrun.py examples/inventory.py  # same program in the terminal
"""
import tkinter as tk
from tkinter import ttk, messagebox

ITEMS = [
	('Detector',  'Scintillator',   12, 450.0),
	('Detector',  'Ion chamber',     4, 1200.0),
	('Detector',  'Silicon strip',   8, 980.0),
	('Shielding', 'Concrete block', 60, 85.0),
	('Shielding', 'Lead brick',    120, 22.5),
	('Shielding', 'Borated PE',     30, 64.0),
	('Beam',      'Quadrupole',      6, 15000.0),
	('Beam',      'Collimator',      3, 4300.0),
]


class InventoryApp(ttk.Frame):
	def __init__(self, master):
		super().__init__(master)
		master.title('Inventory')
		master.geometry('800x480')
		self.pack(fill=tk.BOTH, expand=True)
		self.statusVar = tk.StringVar(value='Ready')
		self.createMenu(master)

		pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
		pane.pack(fill=tk.BOTH, expand=True)
		pane.add(self.createTable(pane), weight=3)
		pane.add(self.createForm(pane), weight=2)

		ttk.Label(self, textvariable=self.statusVar, anchor=tk.W,
			relief=tk.SUNKEN).pack(fill=tk.X, side=tk.BOTTOM)
		self.fillTable()

	def createMenu(self, master):
		menubar = tk.Menu(master)
		fileMenu = tk.Menu(menubar, tearoff=0)
		fileMenu.add_command(label='New item', accelerator='Ctrl-N', command=self.clearForm)
		fileMenu.add_command(label='Delete item', command=self.deleteItem)
		fileMenu.add_separator()
		fileMenu.add_command(label='Quit', command=master.quit)
		menubar.add_cascade(label='File', menu=fileMenu)
		helpMenu = tk.Menu(menubar, tearoff=0)
		helpMenu.add_command(label='About', command=lambda: messagebox.showinfo(
			'About', 'Inventory\nA plain tkinter program.'))
		menubar.add_cascade(label='Help', menu=helpMenu)
		master.config(menu=menubar)
		master.bind('<Control-n>', lambda e: self.clearForm())

	def createTable(self, master):
		frame = ttk.Frame(master)
		self.tree = ttk.Treeview(frame, columns=('qty', 'price'), selectmode='browse')
		self.tree.heading('#0',    text='Item')
		self.tree.heading('qty',   text='Qty')
		self.tree.heading('price', text='Price')
		self.tree.column('#0',    width=200)
		self.tree.column('qty',   width=60,  anchor=tk.E)
		self.tree.column('price', width=100, anchor=tk.E)
		sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
		self.tree.configure(yscrollcommand=sb.set)
		sb.pack(side=tk.RIGHT, fill=tk.Y)
		self.tree.pack(fill=tk.BOTH, expand=True)
		self.tree.bind('<<TreeviewSelect>>', self.onSelect)

		self.chart = tk.Canvas(frame, height=96, background='white')
		self.chart.pack(fill=tk.X)
		return frame

	def createForm(self, master):
		form = ttk.LabelFrame(master, text='Item', padding=8)
		self.nameVar     = tk.StringVar()
		self.categoryVar = tk.StringVar()
		self.qtyVar      = tk.IntVar(value=1)
		self.priceVar    = tk.DoubleVar(value=0.0)
		self.orderVar    = tk.BooleanVar(value=False)
		rows = (
			('Name',     ttk.Entry(form, textvariable=self.nameVar)),
			('Category', ttk.Combobox(form, textvariable=self.categoryVar,
				values=('Detector', 'Shielding', 'Beam'))),
			('Quantity', ttk.Spinbox(form, from_=0, to=999, textvariable=self.qtyVar)),
			('Price',    ttk.Entry(form, textvariable=self.priceVar)),
		)
		for i, (label, widget) in enumerate(rows):
			ttk.Label(form, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
			widget.grid(row=i, column=1, sticky=tk.EW, pady=2)
		ttk.Checkbutton(form, text='Re-order', variable=self.orderVar).grid(
			row=4, column=1, sticky=tk.W, pady=2)
		buttons = ttk.Frame(form)
		buttons.grid(row=5, column=0, columnspan=2, pady=8)
		ttk.Button(buttons, text='Save', command=self.saveItem).pack(side=tk.LEFT, padx=4)
		ttk.Button(buttons, text='Clear', command=self.clearForm).pack(side=tk.LEFT, padx=4)
		form.columnconfigure(1, weight=1)
		return form

	def fillTable(self):
		self.tree.delete(*self.tree.get_children())
		groups = {}
		for category, name, qty, price in ITEMS:
			if category not in groups:
				groups[category] = self.tree.insert('', tk.END, text=category, open=True)
			self.tree.insert(groups[category], tk.END, text=name,
				values=(qty, f'{price:,.2f}'))
		self.drawChart()

	def drawChart(self):
		self.chart.delete('all')
		totals = {}
		for category, name, qty, price in ITEMS:
			totals[category] = totals.get(category, 0) + qty * price
		top    = max(totals.values())
		colors = ('#4e79a7', '#f28e2b', '#59a14f')
		for i, (category, total) in enumerate(totals.items()):
			y = 8 + i * 32
			w = int(300 * total / top)
			self.chart.create_rectangle(100, y - 6, 100 + w, y + 6, fill=colors[i], outline='')
			self.chart.create_text(8, y, text=category, anchor=tk.W)
			self.chart.create_text(108 + w, y, text=f'{total:,.0f}', anchor=tk.W)

	def onSelect(self, event):
		sel = self.tree.selection()
		if not sel or not self.tree.parent(sel[0]):
			return
		item = self.tree.item(sel[0])
		self.nameVar.set(item['text'])
		self.categoryVar.set(self.tree.item(self.tree.parent(sel[0]))['text'])
		self.qtyVar.set(item['values'][0])
		self.priceVar.set(float(str(item['values'][1]).replace(',', '')))
		self.statusVar.set(f"Selected {item['text']}")

	def saveItem(self):
		name = self.nameVar.get().strip()
		if not name:
			messagebox.showerror('Save', 'The item needs a name')
			return
		for i, row in enumerate(ITEMS):
			if row[1] == name:
				del ITEMS[i]
				break
		ITEMS.append((self.categoryVar.get() or 'Detector', name,
			self.qtyVar.get(), self.priceVar.get()))
		self.fillTable()
		self.statusVar.set(f'Saved {name}')

	def deleteItem(self):
		name = self.nameVar.get()
		if name and messagebox.askyesno('Delete', f'Delete {name}?'):
			ITEMS[:] = [row for row in ITEMS if row[1] != name]
			self.fillTable()
			self.clearForm()

	def clearForm(self):
		self.nameVar.set('')
		self.categoryVar.set('')
		self.qtyVar.set(1)
		self.priceVar.set(0.0)
		self.orderVar.set(False)


if __name__ == '__main__':
	root = tk.Tk()
	InventoryApp(root)
	root.mainloop()
