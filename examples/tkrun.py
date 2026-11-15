#!/usr/bin/env python3
"""Run an unmodified tkinter program in the terminal.

usage: python3 examples/tkrun.py program.py [args...]
"""
import os
import sys
import runpy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tktext
tktext.install()		# from now on "import tkinter" loads tktext

if len(sys.argv) < 2:
	sys.exit(__doc__)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
