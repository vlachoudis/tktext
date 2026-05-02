#!/usr/bin/env python3
"""
Demo application showing all tktext widgets.

Run with:
    python demo.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import tktext as tk

def buildDemo():
	root = tk.Tk()
	root.title('tktext demo')

	# ----------------------------------------------------------------
	# Top banner
	# ----------------------------------------------------------------
	banner = tk.Label(root,
		text=' tktext – terminal UI toolkit ',
		fg='black', bg='cyan',
		anchor='center')
	banner.pack(fill=tk.X)

	# ----------------------------------------------------------------
	# Main area: left panel + right panel
	# ----------------------------------------------------------------
	main = tk.Frame(root)
	main.pack(fill=tk.BOTH, expand=True)
	main.columnconfigure(0, weight=1)
	main.columnconfigure(1, weight=2)
	main.rowconfigure(0, weight=1)

	# ---- left panel ------------------------------------------------
	left = tk.Frame(main, relief=tk.RIDGE, borderwidth=1)
	left.grid(row=0, column=0, sticky=tk.NSEW, padx=1, pady=1)

	tk.Label(left, text='Listbox', fg='yellow', anchor='w').pack(fill=tk.X)

	lb = tk.Listbox(left, height=8, selectmode=tk.BROWSE,
		fg='white', selectbackground='blue')
	for fruit in ('Apple', 'Banana', 'Cherry', 'Date', 'Elderberry',
			'Fig', 'Grape', 'Honeydew', 'Kiwi', 'Lemon'):
		lb.insert(tk.END, fruit)
	lb.pack(fill=tk.BOTH, expand=True)

	statusVar = tk.StringVar(value='Select a fruit')
	statusLbl = tk.Label(left, textvariable=statusVar, fg='green', anchor='w')
	statusLbl.pack(fill=tk.X)

	def onLbSelect(evt):
		sel = lb.curselection()
		if sel:
			statusVar.set(f'Selected: {lb.get(sel[0])}')

	lb.bind('<<ListboxSelect>>', onLbSelect)
	lb.bind('<ListboxSelect>', onLbSelect)

	# ---- right panel -----------------------------------------------
	right = tk.Frame(main, relief=tk.RIDGE, borderwidth=1)
	right.grid(row=0, column=1, sticky=tk.NSEW, padx=1, pady=1)
	right.columnconfigure(0, weight=1)
	right.rowconfigure(1, weight=1)
	right.rowconfigure(3, weight=1)

	# Treeview
	tk.Label(right, text='Treeview', fg='yellow', anchor='w').grid(
		row=0, column=0, sticky=tk.EW)

	tv = tk.Treeview(right, columns=('size', 'type'),
		show='tree headings', height=7, fg='white')
	tv.heading('#0',   text='Name')
	tv.heading('size', text='Size')
	tv.heading('type', text='Type')
	tv.column('#0',   width=16)
	tv.column('size', width=8)
	tv.column('type', width=8)

	docs = tv.insert('', 'end', text='Documents',  values=['', 'dir'])
	tv.insert(docs, 'end', text='report.txt', values=['12K', 'txt'])
	tv.insert(docs, 'end', text='budget.csv', values=['4K',  'csv'])
	pics = tv.insert('', 'end', text='Pictures',   values=['', 'dir'])
	tv.insert(pics, 'end', text='photo.png',  values=['2M',  'png'])
	tv.insert(pics, 'end', text='avatar.jpg', values=['80K', 'jpg'])
	tv.insert('',   'end', text='README.md',  values=['1K',  'md'])
	tv.item(docs, open=True)
	tv.grid(row=1, column=0, sticky=tk.NSEW)

	# Text editor
	tk.Label(right, text='Text editor', fg='yellow', anchor='w').grid(
		row=2, column=0, sticky=tk.EW)

	editor = tk.Text(right, width=30, height=6, wrap=tk.WORD,
		fg='white', relief=tk.SUNKEN, borderwidth=1)
	editor.insert('1.0',
		'Type here…\n'
		'Shift+arrows selects text.\n'
		'Ctrl+A selects all.')
	editor.tagConfigure('highlight', background='yellow')
	editor.tagAdd('highlight', '1.0', '1.4')
	editor.grid(row=3, column=0, sticky=tk.NSEW)

	# ----------------------------------------------------------------
	# Controls row: Entry, Checkbutton, Radiobutton, OptionMenu
	# ----------------------------------------------------------------
	ctrlFrame = tk.Frame(root, relief=tk.RIDGE, borderwidth=1)
	ctrlFrame.pack(fill=tk.X, padx=1, pady=1)

	# Entry
	tk.Label(ctrlFrame, text='Entry:', fg='yellow', anchor='w').pack(
		side=tk.LEFT, padx=(2, 0))
	entryVar = tk.StringVar(value='edit me')
	entry = tk.Entry(ctrlFrame, textvariable=entryVar, width=14,
		relief='single')
	entry.pack(side=tk.LEFT, padx=2)

	# Checkbutton
	boldVar = tk.BooleanVar(value=False)
	tk.Checkbutton(ctrlFrame, text='Bold', variable=boldVar,
		fg='white').pack(side=tk.LEFT, padx=4)

	# Radiobutton group
	tk.Label(ctrlFrame, text='Align:', fg='yellow').pack(side=tk.LEFT)
	alignVar = tk.StringVar(value='left')
	for val, label in (('left', 'L'), ('center', 'C'), ('right', 'R')):
		tk.Radiobutton(ctrlFrame, text=label, variable=alignVar,
			value=val, fg='white').pack(side=tk.LEFT)

	# OptionMenu
	tk.Label(ctrlFrame, text='Theme:', fg='yellow').pack(
		side=tk.LEFT, padx=(8, 0))
	themeVar = tk.StringVar(value='dark')
	tk.OptionMenu(ctrlFrame, themeVar, 'dark', 'light', 'solarized',
		'nord').pack(side=tk.LEFT, padx=2)

	# Show current entry value
	entryStatus = tk.Label(ctrlFrame, text='', fg='cyan', anchor='w')
	entryStatus.pack(side=tk.LEFT, padx=4)

	def onEntryReturn(evt):
		entryStatus.configure(text=f'→ {entryVar.get()!r}')

	entry.bind('<Return>', onEntryReturn)

	# ----------------------------------------------------------------
	# Button row
	# ----------------------------------------------------------------
	btnFrame = tk.Frame(root)
	btnFrame.pack(fill=tk.X)

	# Popup menu attached to a button
	popupMenu = tk.Menu(root)
	popupMenu.add_command(label='About…',    command=lambda: _showAbout(editor))
	popupMenu.add_command(label='Clear',     command=lambda: _clearEditor(editor))
	popupMenu.add_separator()
	subMenu = tk.Menu(root)
	subMenu.add_command(label='Red',   command=lambda: statusVar.set('colour: red'))
	subMenu.add_command(label='Green', command=lambda: statusVar.set('colour: green'))
	subMenu.add_command(label='Blue',  command=lambda: statusVar.set('colour: blue'))
	popupMenu.add_cascade(label='Colour', menu=subMenu)
	popupMenu.add_separator()
	popupMenu.add_command(label='Quit', command=root.quit)

	def openMenu():
		b = menuBtn
		popupMenu.post(b._x, b._y + b._h)

	menuBtn = tk.Button(btnFrame, text='Menu ▼', relief='single',
		command=openMenu)
	menuBtn.pack(side=tk.LEFT, padx=2, pady=1)

	tk.Button(btnFrame, text='Clear editor', relief='double',
		command=lambda: _clearEditor(editor)).pack(side=tk.LEFT, padx=2, pady=1)

	tk.Button(btnFrame, text='Quit',
		command=root.quit, borderwidth=0,
		fg='red', padx=0, pady=0).pack(side=tk.RIGHT, padx=2, pady=1)

	# ----------------------------------------------------------------
	# Global key bindings
	# ----------------------------------------------------------------
	def onKey(evt):
		if evt.keysym in ('F10',) or evt.char in ('q', 'Q'):
			root.quit()
			return 'break'

	root.bind('<Key>', onKey)

	# Status bar
	tk.Label(root,
		text='TAB/Shift-TAB: focus  |  arrows: navigate  |  F10 or q: quit',
		fg='black', bg='white', anchor='w').pack(fill=tk.X)

	return root


def _clearEditor(editor):
	editor.delete('1.0', 'end')
	editor.insert('1.0', '(cleared)')


def _showAbout(editor):
	editor.delete('1.0', 'end')
	editor.insert('1.0',
		'tktext v0.1\n'
		'A curses-based tkinter-like\n'
		'widget library for Python.\n\n'
		'Widgets: Label, Button, Entry,\n'
		'Text, Listbox, Treeview,\n'
		'Checkbutton, Radiobutton,\n'
		'Menu, OptionMenu.\n\n'
		'TAB / Shift-TAB: focus\n'
		'F10 / q: quit')


def main():
	root = buildDemo()
	root.mainLoop()


if __name__ == '__main__':
	main()
