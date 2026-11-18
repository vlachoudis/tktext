# tktext vs tkinter

Comparison of tktext with the tkinter of Python 3.14 (`/usr/lib/python3.14/tkinter/`,
Tcl/Tk 8.6.18), made by introspection: module names, class members, method
signatures, the widget options (`keys()` of a real `tkinter.Tk()`) and behaviour
probes on the fake screen.

Legend: **done**: fixed by this comparison, **missing**: not implemented yet,
**n/a**: no meaning in a terminal (kept as a no-op or not provided).

## Version

| | tkinter | tktext |
|---|---|---|
| `TkVersion`, `TclVersion` | 8.6 | 8.6 |
| `info patchlevel`, `info_patchlevel()` | 8.6.18 | 8.6.18 (**done**, was 8.6.16) |
| `_tkinter.TK_VERSION` (drop-in) | '8.6' | '8.6' |

`tktext.__version__` (0.1.0) is the library's own version.

## Modules

| Module | Status |
|---|---|
| `tkinter.scrolledtext` (`ScrolledText`) | **done** |
| `tkinter.commondialog` (`Dialog`) | **done** (subclasses implement `_show`) |
| `tkinter.dialog` (`Dialog`, `DIALOG_ICON`) | **done** |
| `filedialog.Open`, `SaveAs`, `Directory`, `askopenfiles` | **done** |
| `filedialog.FileDialog`, `LoadFileDialog`, `SaveFileDialog` (legacy Tk-widget dialogs) | missing |
| `messagebox.Message` | **done** |
| `colorchooser.Chooser` as `commondialog.Dialog` | **done** |
| `simpledialog.Dialog`, `SimpleDialog` (widget based dialog classes) | missing (`askstring/askinteger/askfloat` exist) |
| `dnd.DndHandler` (`root = None`, `on_motion`, `on_release`) | **done**: a drag never starts, so flair's `h if h.root else None` disables it |
| `dnd.Icon/Tester/test` | missing |
| `__main__`, `_test()` | n/a |

`simpledialog` in tkinter also re-exports `from tkinter import *`; tktext does not.

## Module `tkinter`

| Name | Status |
|---|---|
| `Tcl()` | **done** (`TclShim` without windows, `loadtk()` no-op) |
| `Menubutton` | **done** (also `ttk.Menubutton`) |
| `Pack`, `Grid`, `Place`, `XView`, `YView` | **done** as aliases of `Widget` (mixin names for `isinstance`/subclassing) |
| `EventType` X11 members (`Activate`, `Create`, `Property` …) | **done** (never generated) |
| `_destroy_temp_root` | missing (internal) |

## Module `tkinter.ttk`

| Name | Status |
|---|---|
| `Menubutton`, `Widget`, `setup_master`, `tclobjs_to_py` | **done** |
| `OptionMenu(master, variable, default, *values)`, `set_menu()` | **done** (the default is no longer added as an item) |
| `Scale.get(x, y)` | **done** (coordinates ignored) |
| `Style.element_names/element_options/theme_create/theme_settings` | **done** as stubs (`theme_settings` applies `configure` specs) |
| `Style.map`, `layout`, `element_create` | n/a (return empty values) |
| `LabeledScale` (compound widget with `label`, `scale`, `value`) | missing: alias of `ttk.Scale` |

## Options (`configure`, `cget`, `keys`)

| Behaviour | Before | Now |
|---|---|---|
| `configure('text')` | ValueError | **done**: `('text', 'text', 'Text', default, value)`; aliases `('bd', '-borderwidth')` |
| `configure()` | `{name: value}` | **done**: `{name: 5-tuple}` like tkinter |
| unknown option | silently stored | **done**: `TclError('unknown option "-foo"')` |
| abbreviated option (`border=`) | stored under the abbreviation, ignored | **done**: expanded like Tk, ambiguous → `TclError` |
| `keys()` | only the options tktext uses | **done**: every Tk option of the class + tktext's |
| `tk.call(w, 'configure', '-opt', v)`, `'cget'` | TypeError | **done** |

The Tk option names come from `tktext/_tkoptions.py` (generated from tkinter's
`keys()`, classic and ttk options merged since tktext uses one class for both).

Options accepted and stored but **not drawn** (n/a in a terminal or missing):
`highlightthickness/highlightcolor/highlightbackground`, `insertwidth/insertofftime/
insertontime/insertborderwidth`, `selectborderwidth`, `activeborderwidth`, `bitmap`,
`repeatdelay/repeatinterval` (Button, Scale, Scrollbar, Spinbox), `overrelief`,
`offrelief`, `selectimage`, `tristateimage/tristatevalue`, `image/compound` on
Check/Radiobutton, `labelwidget` (LabelFrame), `tearoffcommand`, `title`,
`type` (Menu), `setgrid`, `blockcursor`, `startline/endline`, `insertunfocussed`,
`colormap/visual/container/use/screen`, PanedWindow `proxy*/sash*/handle*`,
Scrollbar `jump/elementborderwidth/activerelief`, ttk `style`, `padding`, `class`.

## Methods present in tkinter, missing in tktext

### Every widget (`Misc`)

| Method | Status |
|---|---|
| `after(ms, func, *args, **kw)`, `after_idle(func, *args, **kw)` (3.14) | **done** |
| `after_info(id=None)` (3.13) | **done** |
| `info_patchlevel()` (3.11) | **done** |
| `tk_busy` (3.13 alias) | **done** |
| `anchor` (= `grid_anchor`), `location` (= `grid_location`), `info` (= `pack_info`) | **done** |
| `bell(displayof=0)` on `Tk` | **done** |
| `winfo_atomname`, `winfo_colormapfull`, `winfo_visualid`, `winfo_visualsavailable` | **done** (constant answers) |
| `send` | n/a (X11 inter-application messages) |
| `_register`, `_getints`, `_options`, `_configure`, `_bind`, `_last_child_ids` | internal tkinter helpers, not provided |
| `Variable._register` | missing (internal) |

### Per widget

| Widget | Missing | Status |
|---|---|---|
| Entry / Spinbox / Combobox | `bbox(index)` (fell back to `grid_bbox`) | **done** |
| Entry / Spinbox / Combobox | validation (`validate`, `validatecommand`, `invalidcommand`) | **done** (`forced` validation of Spinbox steps/textvariable missing) |
| Entry / Spinbox / Combobox | `scan_mark`, `scan_dragto`, `select_adjust` | **done** |
| Spinbox | `scan`, `selection`, `selection_element` | missing |
| Canvas | `addtag_above/below/closest/enclosed/overlapping`, `select_adjust/from/item/to` | missing |
| Checkbutton / Radiobutton | `flash` | missing |
| Text | `mark_next`, `mark_previous`, `peer_create`, `peer_names`, `window_cget`, `window_configure`, `debug`, `yview_pickplace` | missing |
| Text | `count(..., return_ints=)` (3.13 semantics, None for a zero count) | **done** |
| Scrollbar | `activate`, `delta`, `fraction` | missing |
| PanedWindow | `proxy_coord/forget/place`, `sash_mark` | missing |
| Tk | `loadtk`, `readprofile` | **done** (no-ops) |
| Tk / Toplevel (`Wm`) | `wm_manage`, `wm_forget(window)` | n/a (no-ops) |
| PhotoImage | `copy(from_coords=, zoom=, subsample=)`, `zoom/subsample(from_coords=)`, `copy_replace` (3.13) | **done** (size only) |
| font.Font | `counter` | **done** |

## Signatures

Parameter names now follow tkinter, so keyword calls work (**done**):
`bind/bind_all(sequence, func, add)`, `unbind(sequence, funcid)`, `after_cancel(id)`,
Entry `insert(index, string)`, `icursor/index/selection_*(index)`,
Text `index1/index2/index`, `tagName`, `markName`, `edit_modified(arg)`,
Listbox/Menu `index`, Notebook `tab_id`, Combobox `current(newindex)`,
PhotoImage `cget(option)`, Entry `selection_get(**kw)`.

Remaining differences:

- Canvas `dchars/dtag/gettags/index/insert/lift/lower/move/scale/tag_raise/tag_lower`
  take named positional arguments instead of tkinter's `*args` (same positional calls).
- `tkinter.Entry` has no `bbox(index)` (only ttk.Entry); tktext uses one class, so
  `Entry.bbox()` is the ttk one.
- `Grid.slaves` is `grid_slaves(row, column)` in tkinter; tktext's mixin aliases are
  `Widget`, whose `slaves` is `pack_slaves` (as on tkinter widgets).

## idlelib (`python3 examples/tkrun.py /usr/lib/python3.14/idlelib/idle.py`)

| Feature | Status |
|---|---|
| `simpledialog._setup_dialog`, `_place_window` | **done** |
| `widget._windowingsystem` | **done** (`'x11'`) |
| Tcl `rename` of a widget command + `createcommand` (`WidgetRedirector`) | **done**: the renamed command calls the class methods; a redirected Text sends its keyboard edits, Cut and Paste through the command like Tk's class bindings |
| Tcl `set`, `tcl_wordBreakAfter`, `tcl_wordBreakBefore` | **done** |
| `None` arguments of `tk.call`, `Text.tag_add`, `Text.insert` tags | **done**: dropped like `_tkinter` |
| `bind(seq)` / `bind_class(cls, seq)` query | **done**: a string (one line per callback) like Tk's script; a Tcl script as callback is ignored |
| Text `+Nlines` past the last line, `dlineinfo('end')` | **done**: `end` and `None` like Tk |
| `<1>`…`<5>` | mouse buttons only (the keys are `<Key-3>`, `'3'`) |
| Tcl globals `tk_patchLevel`, `tk_version`, `tcl_version`, `tcl_patchLevel`, `tcl_interactive`, `tcl_precision`, `tk_strictMotif`, `tcl_library`, `tk_library` | **done** (Tk 8.6.18 values; the libraries are empty) |
| `Tk.__getattr__` delegating to the interpreter (`root.globalgetvar(…)`) | **done** |
| `str(info_patchlevel())` | **done**: `'8.6.18'` |
| `event.type` | **done**: a `tkinter.EventType` member (`event.type.name`); its values are the type names, so it still compares equal to `'KeyPress'` … |

## Behavioural notes (by design)

- One class serves both classic and ttk widgets (`tk.Button is ttk.Button`), so the
  accepted options are the union of both sets.
- `Menubutton` shows `▼` by default (`indicatoron=1`), Tk's classic default is 0.
- X11-only features (visuals, colormaps, `send`, `wm_manage`, embedding with `use`)
  are accepted and ignored.
- Extension: `widget.rasterImage(data, width, height)` / `widget.rasterSize()` show
  a crude RGB picture with half-block characters (MANUAL §5.5); tkinter has no
  equivalent, so check `tk.__name__ == 'tktext'` before using them.
