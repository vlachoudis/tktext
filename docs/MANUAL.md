# tktext Manual

tktext is a text-terminal implementation of the tkinter API, built on curses.
A program written for tkinter runs in a terminal window, keyboard and mouse
included, with the same widgets, geometry managers, variables, bindings and
dialogs.

There are two ways to use it:

| Mode | How | Units |
|------|-----|-------|
| **Native** | `import tktext as tk` | character cells |
| **Drop-in** | `tktext.install()` before anything imports `tkinter` | pixels (1 cell = 8×16 px) |

---

## 1. Quick start

### Native program

```python
import tktext as tk

root = tk.Tk()
root.title('Hello')

tk.Label(root, text='Name:').pack(side=tk.LEFT)
name = tk.StringVar(value='world')
tk.Entry(root, textvariable=name, width=20).pack(side=tk.LEFT, padx=1)
tk.Button(root, text='Quit', command=root.quit).pack(side=tk.LEFT)

root.mainloop()
```

Sizes, `padx`/`pady`, `width`/`height`, `place(x=, y=)` and canvas
coordinates are all in **character cells**.

Run the demo to see every widget:

```bash
python demo.py
```

### Existing tkinter program (drop-in mode)

```python
import tktext
tktext.install()          # must run before the first "import tkinter"

import tkinter as tk      # this is now tktext
from tkinter import ttk, messagebox, filedialog
...
```

`install()` registers tktext as `tkinter`, `tkinter.ttk`, `tkinter.messagebox`,
`tkinter.filedialog`, `tkinter.simpledialog`, `tkinter.font`,
`tkinter.colorchooser`, `tkinter.dnd`, `tkinter.constants` and `_tkinter`.
Modules that need a real Tk (`PIL.ImageTk`, `ttkthemes`) are made unimportable,
so applications fall back to their "not available" code paths.

```python
tktext.install(
	block      = ('matplotlib.backends.backend_tkagg',),  # extra modules to block
	colors     = 'terminal',   # 'terminal' (default) or 'tk', see §5.1
	background = 'auto',       # 'auto', 'dark', 'light' or '#rrggbb', see §5.2
	theme      = {'select': ('white', 'blue')},            # theme roles, see §5.3
)
```

In drop-in mode tktext emulates a display where one cell is 8×16 pixels.
Pixel values that the program passes in (padding, geometry strings, canvas
coordinates, column widths …) are converted to cells, and `winfo_*`, event
`x`/`y` and `bbox()` return pixels, so the program's arithmetic still works.

---

## 2. Widgets

All widgets accept tkinter's `(master, cnf={}, **kw)`, `name=` and fall back
to the default root.

| Widget | Notes |
|--------|-------|
| `Tk`, `Toplevel` | Root and extra windows (see §4) |
| `Frame`, `LabelFrame` | Containers |
| `Label`, `Message` | |
| `Button` | Raised buttons draw as `[text]` in drop-in mode |
| `Entry` | Single-line editor; default field colour from the `entry` theme role |
| `Spinbox`, `Combobox` | Entry subclasses (▲▼ arrows / drop-down list) |
| `Text` | Tk index expressions, tags, marks, undo, wrap |
| `Listbox` | |
| `Treeview` | Tree + columns |
| `Checkbutton`, `Radiobutton` | `[X]` / `( )` indicators |
| `Scale`, `Scrollbar`, `Progressbar`, `Separator` | |
| `Notebook` | Tabs |
| `Menu`, `OptionMenu` | Popup, cascade and menubar menus |
| `Canvas` | Items drawn on the character grid |
| `PanedWindow` | Draggable sashes |
| `PhotoImage`, `BitmapImage` | Size only; shown as a glyph |

`tktext.ttk` provides the ttk versions (`ttk.Entry`, `ttk.Treeview`,
`ttk.Notebook`, `ttk.Style` …).  Variables (`StringVar`, `IntVar`,
`DoubleVar`, `BooleanVar`) support traces like tkinter.

### Geometry managers

`pack`, `grid` and `place` behave like Tk.  Since a terminal cannot grow,
when there is not enough room tktext shrinks `expand=True` widgets first so
that widgets packed after them stay visible.

### Borders

`relief` accepts every Tk value plus two terminal-only ones:

| relief | Drawing |
|--------|---------|
| `'single'` | `┌─┐ │ └─┘` |
| `'double'` | `╔═╗ ║ ╚═╝` |
| `raised`, `sunken`, `ridge`, `groove`, `solid` | ASCII `+ - \|` |
| `flat` | none |

```python
tk.Frame(root, relief='single', borderwidth=1)
```

### Fonts

Terminals have one font.  A font that asks for bold
(`font=('Helvetica', 10, 'bold')`) is drawn bold; family and size are ignored.

---

## 3. Dialogs

The tkinter dialog modules work and run modally on the event loop:

```python
from tktext import messagebox, filedialog, simpledialog, colorchooser

if messagebox.askyesno('Quit', 'Really quit?'):
	root.quit()

path = filedialog.askopenfilename(title='Open', initialdir='.')
n    = simpledialog.askinteger('Count', 'How many?', minvalue=1)
```

`messagebox`: `showinfo`, `showwarning`, `showerror`, `askokcancel`,
`askyesno`, `askyesnocancel`, `askquestion`, `askretrycancel`.
`filedialog`: `askopenfilename(s)`, `asksaveasfilename`, `askdirectory`,
`askopenfile`, `asksaveasfile`.
`simpledialog`: `askstring`, `askinteger`, `askfloat`.

---

## 4. Windows, keyboard and mouse

### Windows

* A normal `Toplevel` fills the screen and has its own title bar on row 0.
* A `transient` Toplevel is a framed dialog centred on its master.
* An `overrideredirect` Toplevel is placed exactly where its geometry says.
* `grab_set()` confines keyboard and mouse to the window.
* The keyboard always goes to the topmost decorated window.

### Keys

| Key | Action |
|-----|--------|
| Tab / Shift-Tab | Move focus between widgets |
| F10 | Open the menubar (`root.configure(menu=menubar)`) |
| Escape | Close the open menu / drop-down |
| Ctrl-C | Dismiss open dialogs, otherwise close the active window (calls its `WM_DELETE_WINDOW` protocol handler; on the root, quits `mainloop`) |
| Up / Down on an OptionMenu | Cycle through its values |

Ctrl-S and Ctrl-Q reach the application (terminal flow control is switched
off while tktext runs).

### Bindings

Bindings use the tkinter event syntax:

```python
entry.bind('<Return>',          onEnter)
entry.bind('<Control-a>',       selectAll)
listbox.bind('<<ListboxSelect>>', onSelect)
canvas.bind('<B1-Motion>',      onDrag)
root.bind_all('<F1>',           showHelp)
```

Supported: `<Key>`, `<KeyRelease>`, keysyms (`<Return>`, `<Up>`, `<F1>`,
`<a>`, `<period>` …), modifiers (`<Control-x>`, `<Shift-Up>`), mouse
(`<Button-1>`, `<ButtonRelease-1>`, `<Double-Button-1>`, `<B1-Motion>`,
`<Button-3>`, `<MouseWheel>`, `<Button-4>`/`<Button-5>`), `<FocusIn>`,
`<FocusOut>`, `<Configure>`, `<Map>`, `<Unmap>`, `<Destroy>`, `<Enter>`,
`<Leave>`, and the virtual events `<<ListboxSelect>>`, `<<TreeviewSelect>>`,
`<<TreeviewOpen>>`, `<<TreeviewClose>>`, `<<ComboboxSelected>>`,
`<<NotebookTabChanged>>`, `<<Modified>>`, `<<Increment>>`, `<<Decrement>>`.
Return `'break'` from a callback to stop further processing.  `bind_class`,
`event_add` and `event_generate` work as in Tk.

Some window managers (e.g. i3) take Alt-key combinations for themselves, so
prefer Control- and function-key shortcuts in terminal applications.

### Mouse

The mouse works when the terminal reports it (xterm, gnome-terminal,
konsole, kitty, tmux with `mouse on` …).  Buttons, check buttons and menu
entries act on **release**, like Tk.  Shift-click is passed to the
application instead of starting the terminal's own text selection, where the
terminal allows it.

### Errors in callbacks

An exception raised in a callback does not kill the program: it is shown in
an error box and printed to stderr when `mainloop()` returns.  Override
`root.report_callback_exception(exc, val, tb)` to handle it yourself.

---

## 5. Colours and appearance

Every colour tktext draws is resolved in this order, first match wins:

1. the widget's own option — `Entry(root, bg='navy', fg='white')`
2. the option database — `root.option_add('*Entry.background', 'navy')`
3. the **theme role** for that part of the screen (§5.3)

So you can change the look globally with the theme, per class with the
option database, or per widget with options.

### 5.1 Colour mode (drop-in mode)

tkinter programs usually rely on Tk's default colours: a `#d9d9d9` gray
window and white entry/list fields with black text.  The colour mode decides
what to do with them:

| Mode | Effect |
|------|--------|
| `terminal` (default) | Tk's default grays/whites and black text become the **terminal's own** background and foreground, so the program blends in with your terminal theme. Explicit colours (selections, highlights, a program's `bg='yellow'`) are kept. |
| `tk` | Draws Tk's light-gray look as it is. |

Select it with `install(colors='tk')` or the environment variable:

```bash
TKTEXT_COLORS=tk python myapp.py
```

Colours registered by the program with `tk_setPalette()` or
`ttk.Style().configure('.', background=…)` are also treated as defaults in
`terminal` mode.

### 5.2 Dark or light terminal

tktext adapts some colours to the terminal's background (for example Entry
fields are dark gray on a dark terminal and light gray on a light one).  At
start-up it finds out the background in this order:

1. `TKTEXT_BACKGROUND` environment variable, or `install(background=…)`:
   `dark`, `light`, `#rrggbb` or `auto`
2. `TERM=linux` (the Linux console) — always dark
3. asks the terminal (OSC 11 query, 150 ms timeout)
4. `$COLORFGBG`
5. unknown — treated as dark

If detection gets it wrong (e.g. inside some multiplexers), force it:

```bash
TKTEXT_BACKGROUND=light python demo.py
```

From a program you can check the result with `tktext.terminalBackground()`
(`(r, g, b)` or `None`) and `tktext.isDarkTerminal()`.

In drop-in mode with `colors='tk'` the widgets sit on Tk's light gray, so the
theme is always adapted for a light background.

### 5.3 Theme roles

A theme role is the colour of one part of tktext's own drawing.  Each role
is a tuple `(fg, bg, attrs)`:

* `fg`, `bg` — a colour name (`'red'`, `'LightYellow'`, any X11 name),
  `'#rrggbb'`, or `''` to inherit the widget's own colour (or the terminal
  default);
* `attrs` — space separated: `bold`, `reverse`, `underline`, `dim`, `blink`.

| Role | Used for | Default (dark terminal) | Light terminal |
|------|----------|-------------------------|----------------|
| `entry` | Entry, Spinbox, Combobox field | `('', '#3a3a3a', '')` | `('', '#e4e4e4', '')` |
| `tk.window` | drop-in mode widget default | `('black', '#d9d9d9', '')` | |
| `tk.field` | drop-in mode Text, Listbox, Treeview … field (and Entry with `colors='tk'`) | `('black', 'white', '')` | |
| `disabled` | text of disabled widgets | `('gray', '', '')` | |
| `select` | selected text and items | `('', '', 'reverse')` | |
| `focus` | focused button, active menu entry | `('', '', 'reverse')` | |
| `pressed` | button shown pressed for 0.1 s when clicked (Return/space on a focused button shows it unfocused instead) | `('', '', 'reverse bold')` | |
| `titlebar` | row 0: menubar | `('black', 'white', '')` | |
| `titlebar.title` | row 0: window title | `('black', 'white', 'bold')` | |
| `titlebar.disabled` | disabled menubar entry | `('gray', 'white', '')` | |
| `menubar.active` | open menubar entry | `('white', 'black', 'bold')` | |
| `frame.active` | border of the active dialog window | `('cyan', '', 'bold')` | `('blue', '', 'bold')` |
| `dialog` | messagebox / file dialog body | `('white', 'blue', '')` | |
| `dialog.title` | dialog title | `('yellow', 'blue', 'bold')` | |
| `dialog.field` | simpledialog input field | `('black', 'white', '')` | |
| `dialog.select` | selected file in the file dialog | `('black', 'cyan', '')` | |
| `dialog.focus` | focused dialog button / field | `('black', 'white', 'bold')` | |
| `dialog.dir` | directory names in the file dialog | `('cyan', 'blue', 'bold')` | |
| `dialog.error` | error text in dialogs | `('red', 'blue', 'bold')` | |
| `scrollbar.trough` | scrollbar trough | `('', '#4e4e4e', '')` | `('', '#c3c3c3', '')` |
| `scrollbar.slider` | scrollbar slider | `('', '#8a8a8a', '')` | `('', '#8c8c8c', '')` |

An empty "Light terminal" cell means the role is the same on both.

#### Changing roles

```python
import tktext as tk

# one role, keyword form (only for names without a dot)
tk.setTheme(entry=('', '#303050'))          # bluish entry fields
tk.setTheme(disabled=('red', ''))
tk.setTheme(select=('white', 'blue'))       # instead of reverse video

# any role, dict form (needed for dotted names)
tk.setTheme({
	'dialog':        ('black', 'cyan'),
	'dialog.title':  ('white', 'cyan', 'bold'),
	'titlebar':      ('white', 'blue'),
})

tk.getTheme('entry')     # -> ('', '#303050', '')
tk.getTheme()            # -> copy of the whole theme
tk.resetTheme()          # back to the defaults for this background
```

In drop-in mode pass the same dict to `install(theme={…})`.

Roles you set with `setTheme()` are kept when tktext adapts the theme to a
dark or light terminal; the other roles follow the background.  Unknown role
names raise `ValueError`.  You may call `setTheme()` at any time, also while
`mainloop()` is running; the screen picks the change up on the next redraw.

#### Examples

Plain entries with no gray field (use the terminal's background):

```python
tk.setTheme(entry=('', ''))
```

Underlined entry fields instead of a coloured background:

```python
tk.setTheme(entry=('', '', 'underline'))
```

Different colour for one entry only (widget option wins over the theme):

```python
tk.Entry(root, bg='#1c3a1c', fg='white')
```

All Spinboxes, but not other entries (option database wins over the theme):

```python
root.option_add('*Spinbox.background', '#202040')
```

Choose by terminal background yourself:

```python
if tk.isDarkTerminal():
	tk.setTheme(entry=('yellow', '#202020'))
else:
	tk.setTheme(entry=('navy', '#f0f0d0'))
```

### 5.4 Colour support of the terminal

On terminals with 256 colours (or more) every `#rrggbb` is drawn with the
closest colour of the 256-colour palette.  On 8- or 16-colour terminals
colours are reduced to the nearest basic colour, so subtle grays (like the
Entry field background) may become black or white.  Set
`TERM=xterm-256color` (or your terminal's 256-colour entry) to get the full
range.

---

## 6. Adding your own coloured parts

When you write a custom widget (subclass of `tktext.Widget` or of an existing
widget), never hard-code colours in the drawing code.  Use the helpers so the
option database and the theme apply:

| Helper | Returns the curses attribute for |
|--------|----------------------------------|
| `self._getAttr()` | the widget's fg/bg (option → database → theme) |
| `self._disabledAttr()` | the `disabled` role |
| `self._selectAttr()` | the `select` role (or `selectbackground`/`selectforeground`) |
| `self._focusAttr()` | the `focus` role |
| `self._roleAttr(role)` | any theme role |

A widget class can give its default field colours a theme role, the way
`Entry` uses `entry`:

```python
class SearchEntry(tk.Entry):
	_fieldRole = 'entry'     # inherited already; set another role to change it
```

With terminal colours the field role also wins over a *palette default*
colour found in the option database: programs that store Tk's white field
colour (`option_add('*Entry.background', '#ffffff')`) still get a visible
field, while real colours (`'cyan'`) and the widget's own options are kept.
A `Label` or `Entry` inside a composite `Frame(class_='Combobox')` (a
hand-made combobox) is drawn with the `entry` role as well.

To add a **new** role, add it to `_DEFAULT_THEME` in `tktext/_colors.py`
(with a comment saying where it is used) and, if it should differ on a dark
or light terminal, to `_BACKGROUND_THEMES['dark']` / `['light']`.

---

## 7. Environment variables

| Variable | Values | Effect |
|----------|--------|--------|
| `TKTEXT_COLORS` | `terminal`, `tk` | Colour mode in drop-in mode (§5.1) |
| `TKTEXT_BACKGROUND` | `auto`, `dark`, `light`, `#rrggbb` | Override terminal background detection (§5.2) |
| `TERM` | e.g. `xterm-256color` | Number of colours and key/mouse support |
| `COLORFGBG` | `fg;bg` | Fallback hint for the background colour |

---

## 8. Terminal behaviour

* The screen is started on the first `mainloop()`, or earlier when a modal
  dialog / `wait_window()` runs before it, and is always restored on exit,
  on an uncaught exception and at interpreter exit.
* Resizing the terminal re-runs the layout; widgets that no longer fit are
  squeezed (borders are dropped before content).
* Output written to stdout/stderr while the screen is active is captured and
  printed after the screen is restored.

---

## 9. Testing tktext programs

`tests/fakescreen.py` runs tktext against an in-memory screen, without a
terminal:

```python
from fakescreen import makeApp, attach, press, click
import tktext as tk

root, scr = makeApp(80, 24)        # Tk root on an 80x24 fake screen
e = tk.Entry(root)
e.pack()
attach(root)                       # lay out and draw
e.focus_set()
press(root, 'a', 'b', 'c')          # type
assert e.get() == 'abc'
```

Run the suite:

```bash
python3 -m unittest discover -s tests                     # everything
python3 -m unittest discover -s tests -p 'test_[!t]*.py'  # skip real pty tests
```
