#!/usr/bin/env python3
"""Smallest tktext program: a native application measured in character cells."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tktext as tk

root = tk.Tk()
root.title('Hello')

name   = tk.StringVar()
answer = tk.StringVar(value='Type a name and press Greet')

row = tk.Frame(root)
row.pack(fill=tk.X, padx=1, pady=1)
tk.Label(row, text='Name:').pack(side=tk.LEFT)
entry = tk.Entry(row, textvariable=name, width=20)
entry.pack(side=tk.LEFT, padx=1)
tk.Button(row, text='Greet', command=lambda: answer.set(f'Hello, {name.get()}!')).pack(side=tk.LEFT)
tk.Button(row, text='Quit', command=root.quit).pack(side=tk.LEFT, padx=1)

tk.Label(root, textvariable=answer, fg='green', anchor='w').pack(fill=tk.X, padx=1)

entry.bind('<Return>', lambda e: answer.set(f'Hello, {name.get()}!'))
entry.focus_set()
root.mainloop()
