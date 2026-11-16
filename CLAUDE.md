# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## What is tktext

tktext is a library mimicking the tkinter functionality using curses in a text terminal

## Reference Documentation

### Available online (Claude can fetch directly)
- Tkinter: https://docs.python.org/3/library/tkinter.html

## Running demo

```bash
python demo.py      # launch the demo
```

## Coding Style

### General Philosophy
- Style follows Linux kernel coding style as the base reference, not PEP 8
- Consistency with the codebase always wins over language defaults
- Use type hints for all public functions and methods.
- Keep widget state and rendering logic separate when possible.
- Avoid global mutable state.
- Prefer small, composable classes over large monolithic ones.

### Naming Conventions
- **Classes**: PascalCase (e.g., `VehicleEngine`, `DataProcessor`)
- **Methods**: camelCase (e.g., `calculateSpeed()`, `parseInput()`)
- **Public members / large-scope variables**: explicit names
  (e.g., `maximumAllowedRetryCount`, `primaryConnectionTimeout`)
- **Local variables**: short but clear (e.g., `result`, `count`, `buffer`)
- **Loop variables / very short-lived**: abbreviated (e.g., `i`, `j`, `it`, `tmp`)
- **No underscore-separated names** — camelCase everywhere, in both C++ and Python

### Formatting
- **Indentation**: tabs (never spaces)
- **Alignment**: align variable assignments on `=`
- **Do not follow PEP 8** — this codebase uses Linux kernel style adapted for Python
- **Increment/Decrement**: operators at the end like i++, j--

### Alignment Example
```python
class DataProcessor:
	primaryOutputDirectory  = "/var/output"
	maximumRetryAttempts    = 3
	connectionTimeoutSecs   = 30.0

	def processInput(self, inputFilePath: str):
		count  = 0
		ready  = False

		for i in range(self.maximumRetryAttempts):
			tmp    = self._fetchChunk(i)
			count += len(tmp)
			ready  = tmp.valid()
```

### ❌ Never do this
```python
def process_input(self, input_file_path):  # snake_case — wrong
	maximum_retry_attempts = 3             # underscore — wrong
	for index in range(3):                 # overly long loop var — wrong
```

## Curses and Terminal Rules
- Do not call curses initialization code outside the app entry point.
- Always handle terminal resize events.
- Keep drawing code resilient to small terminal sizes.
- Avoid blocking the event loop on long operations.
- Ensure cleanup restores terminal state on exit or exceptions.

## Tkinter-Inspired Design Rules
- Widgets should expose a small, consistent API.
- Prefer `pack`/`grid`-like layout concepts only if they already exist in the codebase.
- Use naming that reflects widget behavior, not backend implementation details.
- Keep event bindings explicit and readable.

## Testing Rules
- Add or update tests for any behavior change.
- Prefer unit tests for widget logic and backend-independent behavior.
- Add regression tests for terminal rendering bugs when practical.
- Keep tests deterministic; do not rely on interactive terminal input.

## Before You Finish
- Run relevant tests.
- Run linting if code was changed.
- Check for terminal cleanup and resize safety in any curses-related change.

---

## Package Structure

```
tktext/
  __init__.py        # Public API + Variable classes (traces) + constants + _setit,
                     # tkinter module-level API (CallWrapper, EventType, …) and install()
  _colors.py         # ColorManager: (fg,bg) -> curses color pair + attribute
  _events.py         # Key constants, keysymOf(), Event/KeyEvent/MouseEvent, mouse helpers
  _core.py           # Widget base class (tkinter Misc API: winfo_*, bind_class, option db,
                     # grab/wait, busy, ttk state), binding dispatch, pixel mode, TclError
  _tcl.py            # widget.tk: emulated Tcl interpreter (call/eval/splitlist, wm, image …)
  _toplevel.py       # Wm mixin (wm_* API) + Toplevel windows
  _image.py          # PhotoImage / BitmapImage (size only; shown as a glyph)
  _raster.py         # RasterRenderer: widget.rasterImage() RGB pictures as '▀' cells,
                     # curses (pairs 160-254) or truecolor overlay after refresh
  _canvas.py         # Canvas items on a character grid
  _panedwindow.py    # PanedWindow (tk) / Panedwindow (ttk) with draggable sashes
  _layout.py         # doPackLayout (port of tkPack.c), doGridLayout, doPlaceLayout
  _frame.py          # Frame / LabelFrame containers (size propagation)
  _app.py            # Tk root: event loop, input dispatch, focus, menubar, timers, errors
  _label.py          # Label
  _button.py         # Button
  _menubutton.py     # Menubutton (tk + ttk): Button posting its menu=
  _tkoptions.py      # Tk 8.6.18 option table per widget class (generated from tkinter
                     # keys()): configure() checks/expands names, keys(), configure('opt')
  _entry.py          # Entry (single-line editor; base class of Spinbox and Combobox)
  _spinbox.py        # Spinbox (Entry + ▲▼)
  _combobox.py       # Combobox (Entry + dropdown overlay in _postedMenus)
  _text.py           # Text (Tk index expressions, tags, marks, undo, wrap)
  _listbox.py        # Listbox + _ScrollMixin (yscrollcommand / internal scrollbar)
  _treeview.py       # Treeview (uses _ScrollMixin)
  _checkbutton.py    # Checkbutton ([X]/[ ] indicator, variable, onvalue/offvalue)
  _radiobutton.py    # Radiobutton (subclass of Checkbutton, shared variable+value)
  _scale.py          # Scale
  _scrollbar.py      # Scrollbar (drives linked widgets through command=)
  _notebook.py       # Notebook (tabs; pages are children without geometry manager)
  _menu.py           # Menu (overlay popup / menubar) + OptionMenu
  _misc.py           # Separator, Progressbar
  _dialog.py         # modal dialogs (_MsgDialog, _FileDialog) run on the app loop
  _sysclip.py        # system clipboard (pbcopy, Win32, wl-copy, xclip/xsel, WSL, OSC 52)
                     # for the STRING format of the per-type app._clipboard (_core.py);
                     # used only with a real screen (_ownScreen), never by the fake-screen tests
  messagebox.py, filedialog.py, ttk.py   # tkinter-compatible modules
  font.py, colorchooser.py, dnd.py, simpledialog.py, constants.py,
  scrolledtext.py, commondialog.py, dialog.py
tests/               # unittest suite; fakescreen.py = in-memory curses window
docs/MANUAL.md       # user manual (API, dialogs, keys, colours/theme roles, env vars):
                     # update it when public behaviour or theme roles change
docs/TKINTER_DIFF.md # what differs from / is missing vs tkinter (Python 3.14, Tk 8.6.18)
```

## Running Tests

```bash
python3 -m unittest discover -s tests        # all tests (incl. real pty sessions)
python3 -m unittest discover -s tests -p 'test_[!t]*.py'   # skip the pty tests
```

`tests/fakescreen.py` provides `makeApp()`, `attach()`, `press()` and `click()`:
the Tk root is attached to a fake curses window (`Tk._attach(scr, initCurses=False)`),
so layout, rendering and input are tested without a terminal.  When the fake key
queue is empty `getch()` raises `KeyboardInterrupt`, so a modal dialog under test
can never hang.

## tkinter Drop-in Mode (`tktext.install()`)

`tktext.install(block=())` registers tktext as `tkinter`, `tkinter.ttk`, `tkinter.font` …
in `sys.modules` and makes modules that need a real Tk (`PIL.ImageTk`, `ttkthemes`, plus
`block`) raise ImportError.  It must run before anything imports tkinter.  flair uses it
(`flair.py --text` / `FLAIR_TK=text`, flair checkout in `flair/`).

It also switches on **pixel mode** (`_core.setPixelMode(8, 16)`): tkinter programs measure
in pixels, so one cell is 8x16 px of a virtual display.  Screen distances (padx/pady,
frame/canvas width/height, place x/y, geometry strings, canvas coordinates, column
widths, grid minsize …) are converted to cells on input (`_cellsX/_cellsY`, done in
`configure()` via `_PIXEL_OPTIONS`/`_pixelSize` and in pack/grid/place), and `winfo_*`,
event x/y, `bbox()` results are reported back in pixels (`_pxBox`).  Coordinate inputs
(`nearest(y)`, `identify_row(y)`, `'@x,y'`) go through `_cellX/_cellY`.  Native tktext
programs keep scale 1 (cells everywhere).  In pixel mode Tk borders are not drawn (except
LabelFrame and 'single'/'double' reliefs), raised Buttons render as `[text]`, and widgets
without colours take Tk's defaults (`#d9d9d9`, white fields) after the option database.

Colour mode (`_colors.setColorMode`): `install(colors='terminal')` (the default,
overridden by `TKTEXT_COLORS=terminal|tk`) renders the palette default colours —
Tk's gray/white backgrounds, black text, and anything registered by `tk_setPalette()`
or `ttk.Style().configure('.', background=…)` — with the terminal's own colours (-1)
in `ColorManager.getAttr` → `mapDefaults`.  The foreground is mapped only when the
background is, so explicit backgrounds (selection, highlights) keep their text colour.
`'tk'` keeps Tk's light-gray look.

Rasters (`_raster.py`, `TKTEXT_GRAPHICS=curses|truecolor|auto`): Python curses packs the
pair into 8 bits of the attribute, so UI colours use pairs 1-159 (`ColorManager.getAttr`)
and rasters 160-254; pair 255 is the truecolor marker.  `Tk._redraw` calls
`_raster.beginFrame()` before drawing and `_raster.flush(scr)` after `scr.refresh()`;
flush writes 24-bit cells only where `scr.inch()` still shows the marker (overlays clip
themselves) and keeps a shadow of what the terminal shows (`invalidate()` on resize).

Toplevels: a normal Toplevel is maximised (own title bar/menubar on row 0), a transient
one is a framed dialog centred on its master, an override-redirect one is placed exactly.
The keyboard always belongs to the topmost decorated window (`Tk._activeWindow()`);
`grab_set()` confines mouse and keys; transients stay above their master.  Modal loops
(`wait_window`, `wait_variable`) may run before `mainloop()`: the screen is started lazily
(`Tk._startScreen`, restored by `_stopScreen`, atexit and the excepthook).

## Colours and Theme

Every colour tktext draws with resolves in this order: the widget's own option →
the option database (`option_add('*selectBackground', …)`, `'*Listbox.selectBackground'`;
`Widget._color()` for fg/bg, `Widget._optColor(option)` for the others, names in
`Widget._DB_NAMES`) → a **theme role** in `_colors._theme`.  A role is
`(fg, bg, attrs)`; `''` inherits the widget's colour, attrs are
`bold reverse underline dim blink`.  API: `tktext.setTheme({'dialog.title': (…)})`
or `setTheme(disabled=('red', ''))`, `getTheme(role)`, `resetTheme()`,
`install(theme={…})`.  Roles: `tk.window`, `tk.field` (pixel-mode class defaults),
`disabled`, `select`, `focus`, `pressed`, `titlebar`, `titlebar.title`, `titlebar.disabled`,
`menubar.active`, `frame.active`, `border` (widget borders in the normal state, `Widget._borderAttr(attr)`), `dialog`, `dialog.title`, `dialog.field`,
`dialog.select`, `dialog.focus`, `dialog.dir`, `dialog.error`, `scrollbar.trough`,
`scrollbar.slider`, `entry` (default field colours of Entry/Spinbox/Combobox and of Label/Entry
inside a `Frame(class_='Combobox')`; it beats palette-default database colours; through
`Widget._fieldRole`: bright white `#ffffff` on dark gray `#3a3a3a` on a dark terminal, black on `#e4e4e4` on a light one;
natively and in pixel mode with terminal colours, `'tk'` colours keep `tk.field`).  Render code never hard-codes colours: use `_disabledAttr()`,
`_selectAttr()`, `_focusAttr()`, `_roleAttr(role)` (widgets) or
`app._colors.roleAttr(role)` (dialogs, title bar).  Colour option defaults are
`''` (e.g. `disabledforeground`) so the database and theme can apply.

Dark/light terminal (`_termbg.py`): `terminalBackground()` → `(r,g,b)` or None,
`isDarkTerminal()` (unknown → dark).  Order: `TKTEXT_BACKGROUND` env
(`dark|light|#rrggbb|auto`) / `install(background=…)` → `TERM=linux` (dark) →
OSC 11 query on `/dev/tty` (followed by DA1 so non-supporting terminals answer at
once, then 0.1 s more for an OSC reply behind it (screen/tmux answer DA1 themselves);
0.5 s timeout; a later reply is swallowed by `Tk._readOsc`) → `$COLORFGBG` → None.  The query reads the tty, so it only
runs in `Tk._startScreen()` **before** `curses.initscr()` (never with a fake
screen).  `Tk._adaptTheme()` then calls `_colors.setBackground('dark'|'light')`
('light' when pixel mode draws Tk's gray, i.e. colour mode 'tk'), which applies the
`_BACKGROUND_THEMES` deltas to every role not set with `setTheme()`.

## Widget Init Pattern

Every widget subclass **must** follow this exact order or `_opts` will not exist when
`configure()` is called:

```python
def __init__(self, parent=None, cnf=None, **kwargs):
    parent, kwargs = _initArgs(parent, cnf, kwargs)  # master=, cnf, default root
    super().__init__(parent)          # Widget.__init__ creates self._opts
    self._opts.update({...})          # add widget-specific option defaults
    kwargs.setdefault('relief', ...)  # set any kwarg defaults
    if kwargs:
        MyWidget.configure(self, **kwargs)  # apply caller's options (non-virtual)
```

Never call `self._opts.update(...)` before `super().__init__()`.  Instance state that
`configure()` or the render path may touch must be created before `configure()`.
Constructors call **their own class's** `configure` (`Label.configure(self, **kwargs)`),
never `self.configure(...)`: like tkinter, a subclass's overridden `configure()` must not
run before the subclass has finished its own `__init__`.  Constructors accept tkinter's
`(master, cnf={}, **kw)`, `master=`/`name=` and fall back to the default root.

## Event Dispatch

Keys (`Tk._onKey`): posted dialog → posted menu (they grab the keyboard) →
user bindings of the focus widget (most specific pattern only; `'break'` stops) →
class behaviour `widget._handleKey(key)` → if unconsumed, the first ancestor with a
matching binding → `bind_all` bindings and Tab/Shift-Tab traversal (suppressed only
by `'break'`) → `<KeyRelease>`.  `_handleKey` must **not** dispatch user bindings itself.

Mouse (`Tk._onMouse`): dialogs → menubar row → posted menus → drag widget / widget
under the pointer: user bindings first, then `_handleMouse`.  Buttons, check/radio
buttons and menu items act on **release** (or CLICKED) like tkinter; a release whose
press was not delivered (e.g. the press closed a menu or a dialog) is dropped.

Class bindings (`bind_class`) fire after the widget's own bindings and before
`_handleKey`; keys matching `event_add()` sequences fire the virtual event when bound.
Widget generated virtual events (`<<ListboxSelect>>`, `<<NotebookTabChanged>>` …) are
**queued** like in Tk and delivered by the event loop (`root.update()` in tests).
`focus_set()` likewise only queues `<FocusIn>`/`<FocusOut>` (the focus itself changes at
once), so focus bindings never run re-entrantly inside the caller.
`<Configure>`, `<Map>`, `<Unmap>`, `<Destroy>`, `<Enter>`, `<Leave>` are generated.

Every callback goes through `tktext.CallWrapper` (`_core._callback`); applications may
replace it.  Callback exceptions are caught by `_processOneEvent`, shown in an error box
and printed to stderr when `mainloop()` returns (`report_callback_exception`).

## Menu System

Menu widgets are **overlay widgets** — they are never registered with a geometry manager.
When posted, they are added to `Tk._postedMenus` and rendered last (on top) by `_redraw`.

- `menu.post(x, y)` — show at absolute screen coords; auto-clamps to screen edges
- `menu.unpost()` — hide and remove from `_postedMenus`
- Key events go to `_postedMenus[-1]`, which consumes all keys while posted
- Mouse clicks outside all posted menus close them all (but the click still lands on the widget beneath)
- Cascade submenus set `_parentMenu` on the child and post at the right edge of the parent
- `root.configure(menu=menubar)` draws a menubar on the title row (F10 opens it)

OptionMenu posts its internal `_menu` below itself (or above if not enough room).
Up/Down on an OptionMenu cycles values directly without opening the popup.

## Mouse Drag Tracking

`Tk._dragWidget` holds the widget that received `BUTTON1_PRESSED`.  All subsequent mouse
events (including motion that drifts outside the widget) are routed to that widget until
`BUTTON1_RELEASED`; `widget._dragging()` tells a widget it owns the drag.  Widgets that
support drag-selection (Entry, Text) use their own `_mouseDown` flag and `_selAnchor` to
avoid re-initialising the anchor on terminals that re-send `BUTTON1_PRESSED` on motion.

Middle/right drags use a separate `Tk._btnDrag = (widget, 2|3)`: curses reports drag motion as a
bare `REPORT_MOUSE_POSITION`, so the app remembers the pressed button and routes the motion as
`<B2-Motion>`/`<B3-Motion>` (state `Button2Mask`/`Button3Mask`) and `BUTTON2/3_RELEASED` as
`<ButtonRelease-2/3>` to the press widget.  `_mouseEventNames(bstate, dragging)` takes the held
button (`True` = 1).  `<Configure>` reports `width`/`height` like `winfo_*` (pixels in pixel mode).

## Border Relief Values

`relief` option accepts all tkinter values plus two terminal-specific ones:
- `'single'` — Unicode single-line box (`┌─┐ │ └─┘`)
- `'double'` — Unicode double-line box (`╔═╗ ║ ╚═╝`)
- All other non-flat values use ASCII `+`, `-`, `|`

`_cfgBorder()` is the configured width (use it in `_preferredSize`); `_border()` is the
width actually drawn — a widget squeezed below its border drops the border.

## Known Pitfalls

- Geometry is `_x, _y, _width, _height` (cells).  `_w` is the Tk **path name** (`str(w)`)
  like in tkinter, because applications pass `widget._w` to `tk.call`.

- With `pack/grid/place(in_=master)` a widget lives in `master._children`; use
  `widget._container()` (not `_parent`) for the list that holds it.

- `curses.COLS` / `curses.LINES` do not exist until after `curses.initscr()`.  Always
  use the screen's `getmaxyx()` in drawing helpers; `_addStr` clips to the screen.

- Anchors: `'e' in 'center'` and `'n' in 'center'` are both true — normalise with
  `_layout._anchor()` before testing compass letters.

- `doPackLayout` follows Tk (expansion computed per slave from the remaining cavity).
  Because a terminal cannot grow, `_shrinkToFit` first takes any shortage from
  `expand=True` widgets so that widgets packed after them stay visible.

- Hidden widgets (`*_forget`, inactive notebook pages, zero-size parcels) are zeroed
  with `_unmapTree()`; focus, hit-testing and rendering skip unmapped widgets.

- Text positions are `(row, col)`; `end` is `(len(lines), 0)`, i.e. after the implicit
  final newline (`get('1.0', 'end')` ends with `'\n'`, insert at `end` goes before it).

- Tag/selection colours are resolved at draw time; never OR two `color_pair()` values.

- Applications subclass widgets: give internal state widget-specific names (`_lbItems`,
  `_menuItems`, `_canvasItems`, `_treeItems`) — flair's `SearchListbox` has its own
  `self._items` — and never call overridable public methods (`xview()`, `yview()`)
  from internal code; use `Text.xview(self, …)` (flair's `xview()` closes its popup).

- `place()` works inside any widget (`Widget._layoutChildren`); leaf widgets'
  placed children are drawn after the widget (`_renderWithSlaves`), containers set
  `_rendersChildren = True`.  Tk class bindings of virtual events (Listbox
  `<<PrevLine>>` …) go in `_handleVirtual(sequence)`.  The Text `current` mark is
  moved before the mouse bindings run (`_pointerAt`).

- `Tk._layoutChildren` uses a `_TkInner` proxy that offsets `_y += 1` and `_h -= 1` to
  leave row 0 for the title bar drawn by `_redraw`.

## Event String Conventions

Bindings follow tkinter conventions:
- `<Key>` — any key press; `<KeyRelease>` is emitted right after it
- `<keysym>` / `<Key-keysym>` — e.g. `<Return>`, `<Up>`, `<F1>`, `<a>`, `'a'`, `<period>`
- `<Control-x>`, `<Shift-Up>` — modified keys
- `<Button-1>`, `<ButtonRelease-1>`, `<Double-Button-1>`, `<B1-Motion>`, `<Button-3>`,
  `<MouseWheel>` (also `<Button-4>`/`<Button-5>`)
- `<FocusIn>` / `<FocusOut>`
- `<<ListboxSelect>>`, `<<TreeviewSelect>>`, `<<TreeviewOpen>>`, `<<TreeviewClose>>`,
  `<<ComboboxSelected>>`, `<<NotebookTabChanged>>`, `<<Modified>>`, `<<Increment>>`,
  `<<Decrement>>` — virtual events
