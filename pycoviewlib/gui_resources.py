from tkinter import IntVar, DoubleVar, StringVar, Widget
from tkinter.ttk import (
    Frame, Separator, Notebook, Labelframe, Label, OptionMenu, Checkbutton, Combobox, Spinbox
)
from pycoviewlib.functions import _isfloat
from typing import Union, Any, Optional, Callable
from re import search

""" Padding presets (frame padding: 'left top right bottom') """
THIN_PAD = 6
LINE_PAD = int(THIN_PAD / 3)
MED_PAD = int((THIN_PAD * 4) / 3)
WIDE_PAD = 2 * THIN_PAD
uniform_padding = {
    'padx': WIDE_PAD, 'pady': WIDE_PAD, 'ipadx': THIN_PAD, 'ipady': THIN_PAD
}
hist_padding = {
    'padx': 0, 'pady': (WIDE_PAD, 0), 'ipadx': 0, 'ipady': 0
}
lbf_padding = {
    'padx': WIDE_PAD, 'pady': WIDE_PAD, 'ipadx': THIN_PAD, 'ipady': THIN_PAD
}
lbf_asym_padding = {
    'padx': (WIDE_PAD, 0), 'pady': WIDE_PAD, 'ipadx': THIN_PAD, 'ipady': THIN_PAD
}
lbf_asym_padding_no_top = {
    'padx': (WIDE_PAD, 0), 'pady': (0, WIDE_PAD), 'ipadx': THIN_PAD, 'ipady': THIN_PAD
}
lbf_contents_padding = {'padx': (THIN_PAD, 0), 'pady': (MED_PAD, 2)}

""" Colors """
CH_COLORS = {'blue': '#007dff', 'red': 'red', 'green': '#66BB6A', 'gold': 'gold'}
HIST_COLOR = 'tab:blue'

# ------------------------- Entry validation helpers -------------------------
def validate_filename(entry: str) -> bool:
    valid: bool = entry == '' or not any(char in entry for char in r'<>:"/\|?*. ')
    return valid

def validate_bins(entry: str) -> bool:
    valid: bool = entry == '' or entry.isdigit()
    return valid

def validate_master_delay(entry: str) -> bool:
    valid: bool = any([
        entry == '',
        entry == '-',
        search(r'^-?\d{1,5}$', entry) is not None
    ]) and search('[a-zA-Z]', entry) is None
    return valid

def escape(widget: Widget, default: Any) -> None:
    widget.delete(0, 'end')
    widget.insert(0, default)
    widget.winfo_toplevel().focus_set()


# -------------------------- Custom Tkinter wrapper --------------------------
# TODO: make id checker function for consistency
GRID_KWARGS = (
    'column', 'row', 'rowspan', 'columnspan', 'sticky',
    'padx', 'pady', 'ipadx', 'ipady'
)

def assert_entry_ok(widget, valid_range: tuple[int, int]) -> None:
    if widget.get().isdigit():
        widget_value = int(widget.get())
    elif _isfloat(widget.get()):
        widget_value = float(widget.get())
    else:
        widget.insert(0, str(valid_range[0]))
        return

    if widget_value < valid_range[0]:
        widget.delete(0, 'end')
        widget.insert(0, str(valid_range[0]))
    elif widget_value > valid_range[1]:
        widget.delete(0, 'end')
        widget.insert(0, str(valid_range[1]))

def HSeparator(parent, row: int, columnspan: int) -> None:
    Separator(parent, orient='horizontal').grid(
        column=0,
        row=row,
        columnspan=columnspan,
        padx=(WIDE_PAD, 0),
        pady=(WIDE_PAD, 0),
        sticky='ew'
    )

tkAnyVar = Union[IntVar, DoubleVar, StringVar]

class PVLabelframe(Labelframe):
    def __init__(
            self,
            parent: Notebook,
            title: str,
            col: int,
            row: int,
            size: tuple[int, int],
            sticky: Optional[str] = 'nw',  # Same format as in tkinter
            cspan: Optional[int] = 0,
            rspan: Optional[int] = 0,
            padding: Optional[dict[str, int]] = None
            ):
        assert isinstance(sticky, str) and all([c in 'nesw' for c in sticky]), \
                f"Invalid 'sticky' parameter: expected 'nesw' (str), got {sticky}."
        self.parent = parent
        self.grandparent = parent.winfo_toplevel()  # Get root window
        self.children: dict[str, tuple[Widget, dict[str, int]]] = {}
        self.labelframe = Labelframe(parent, text=title)
        self.auto_pos_x = 0  # Auto-increasing column counter
        self.auto_pos_y = 0  # Auto-increasing row counter
        self.maxcol = size[0]
        self.maxrow = size[1]
        self.variables: dict[str, tkAnyVar] = {}  # Container for tk variables
        grid_kwargs = {'column': col, 'row': row, 'sticky': sticky}
        if cspan:
            grid_kwargs['columnspan'] = cspan
        if rspan:
            grid_kwargs['rowspan'] = rspan
        grid_kwargs.update(padding if padding else lbf_asym_padding)
        self.labelframe.grid(**grid_kwargs)

    def __auto_place(
            self,
            widget,
            id: str,
            padding: Optional[dict[str, int]] = None,
            sticky: Optional[str] = None,
            **kwargs
            ) -> None:
        assert self.auto_pos_x <= self.maxcol, \
            'Too many widgets for specified size.'
        grid_kwargs = {
            'column': self.auto_pos_x,
            'row': self.auto_pos_y,
            'sticky': 'nw' if sticky is None else sticky,
            'padx': (0, 0),
            'pady': (0, 0)
        }
        grid_kwargs.update(padding if padding else lbf_contents_padding)
        grid_kwargs.update(kwargs)
        if self.auto_pos_x > 0:  # Spacing between columns
            grid_kwargs['padx'] = (  # Checkbuttons have wider left padding by default
                WIDE_PAD * 5/3-1 if widget.winfo_class() == 'Checkbutton' else 2 * WIDE_PAD,
                grid_kwargs['padx'][1]
            )
        if self.auto_pos_y == self.maxrow - 1:
            self.auto_pos_x += 1
            self.auto_pos_y = 0
        else:
            self.auto_pos_y += 1

        self.children.update({id: (widget, grid_kwargs)})

    def __create_tk_var(self, options: list[Any], default: Any | None) -> tkAnyVar:
        inferred_type = type(options[0])
        assert default is not None and inferred_type is type(default), \
            f"Options and default value types don't match ({inferred_type!s} vs {type(default)!s})"
        assert any([inferred_type is str, inferred_type is int, inferred_type is float]), \
            f'Invalid variable type ({inferred_type})'
        if inferred_type is str:
            return StringVar(self.labelframe, value=options[0] if default is None else default)
        elif inferred_type is int:
            return IntVar(self.labelframe, value=options[0] if default is None else default)
        elif inferred_type is float:
            return DoubleVar(self.labelframe, value=options[0] if default is None else default)

    def __validate(self, entry: str) -> bool:
        valid: bool = entry == '' or entry == '-' or entry.isdigit() or _isfloat(entry)
        return valid

    def __assert_entry_ok(self, widget, valid_range: tuple[int, int]) -> None:
        assert_entry_ok(widget, valid_range)

    def __assert_option_ok(self, id: str, valid_options: tuple[str], default: Any) -> None:
        if self.children[id][0].get() not in valid_options:
            self.__escape(id, default)

    def __escape(self, id: str, default: Any) -> None:
        self.children[id][0].delete(0, 'end')
        self.children[id][0].insert(0, default)
        self.parent.focus_set()

    def arrange(self) -> None:
        for widget, grid_kwargs in self.children.values():
            widget.grid(**grid_kwargs)

    def get_value(self, id: str) -> Any:
        return self.variables[id].get()

    def get_raw(self, id: str) -> tkAnyVar:
        return self.variables[id]

    def add_label(
            self,
            id: str,
            text: str,
            parent: Optional[Notebook | Frame] = None,  # Optional parent frame for group
            sticky: Optional[str] = None,
            padding: Optional[dict[str, int]] = None,
            **kwargs
            ) -> Label:
        assert id not in self.children.keys(), \
            f"The widget ID '{id}' already exists!"
        grid_kwargs = {k: v for k, v in kwargs.items() if k in GRID_KWARGS}
        widget_kwargs = {k: v for k, v in kwargs.items() if k not in GRID_KWARGS}
        label = Label(self.labelframe if parent is None else parent, text=text, **widget_kwargs)
        self.__auto_place(label, id=id, sticky=sticky, **grid_kwargs)

        return label

    def add_spinbox(
            self,
            id: str,
            from_to: tuple[int | float, int | float],
            step: int | float,
            prompt: Optional[str] = None,
            default: Optional[Any] = None,
            width: Optional[int] = 9,
            padding: Optional[dict[str, int]] = None,
            sticky: Optional[str] = None,
            **kwargs
            ) -> Spinbox:
        assert id not in self.variables, \
            f"The widget ID '{id}' already exists!"
        grid_kwargs = {k: v for k, v in kwargs.items() if k in GRID_KWARGS}
        widget_kwargs = {k: v for k, v in kwargs.items() if k not in GRID_KWARGS}
        self.variables[id] = self.__create_tk_var(from_to, default)
        if prompt:
            self.add_label(
                id=f'{id}.label',
                text=prompt,
                padding=padding if padding else lbf_contents_padding,
                sticky=sticky
            )
        spinbox = Spinbox(
            self.labelframe,
            from_=from_to[0],
            to=from_to[1],
            textvariable=self.variables[id],
            width=width,
            increment=step,
            takefocus=0,
            **widget_kwargs
        )
        spinbox.bind('<FocusOut>', lambda _: self.__assert_entry_ok(spinbox, from_to))
        spinbox.bind('<Escape>', lambda _: self.__escape(id, default))
        self.__auto_place(
            spinbox,
            id=id,
            padding={'padx': lbf_contents_padding['padx']} if prompt else lbf_contents_padding,
            sticky=sticky,
            **grid_kwargs
        )

        return spinbox

    def add_checkbutton(
            self,
            id: str,
            prompt: str,
            on_off: tuple[Any],
            default: Optional[Any] = None,
            command: Optional[Callable] = None,
            style: Optional[str] = 'TCheckbutton',
            padding: Optional[dict[str, int]] = None,
            sticky: Optional[str] = None,
            **kwargs
            ) -> Checkbutton:
        assert id not in self.variables, \
            f"The widget ID '{id}' already exists!"
        grid_kwargs = {k: v for k, v in kwargs.items() if k in GRID_KWARGS}
        widget_kwargs = {k: v for k, v in kwargs.items() if k not in GRID_KWARGS}
        self.variables[id] = self.__create_tk_var(on_off, default)
        checkbutton = Checkbutton(
            self.labelframe,
            variable=self.variables[id],
            text=prompt,
            onvalue=on_off[0],
            offvalue=on_off[1],
            style=style,
            takefocus=0,
            **widget_kwargs
        )
        if command:
            checkbutton.config(command=command)
        self.__auto_place(
            checkbutton,
            id=id,
            padding={
                'padx': lbf_contents_padding['padx'],
                'pady': (0, 0),
            } if padding is None else padding,
            sticky=sticky,
            **grid_kwargs
        )

        return checkbutton

    def add_optionmenu(
            self,
            id: str,
            options: list[Any],
            default: Optional[Any] = None,
            prompt: Optional[str] = None,
            padding: Optional[dict[str, int]] = None,
            sticky: Optional[str] = None,
            **kwargs
            ) -> OptionMenu:
        assert id not in self.variables, \
            f"The widget ID '{id}' already exists!"
        grid_kwargs = {k: v for k, v in kwargs.items() if k in GRID_KWARGS}
        widget_kwargs = {k: v for k, v in kwargs.items() if k not in GRID_KWARGS}
        self.variables[id] = self.__create_tk_var(options, default)
        if prompt:
            self.add_label(
                id=f'{id}.label',
                text=prompt,
                padding=padding if padding else lbf_contents_padding,
                sticky=sticky
            )
        option_menu = OptionMenu(
            self.labelframe,
            self.variables[id],
            default if default else options[0],
            *options,
            **widget_kwargs
        )
        self.__auto_place(
            option_menu,
            id=id,
            padding={
                'padx': lbf_contents_padding['padx'],
            } if prompt else lbf_contents_padding,
            sticky=sticky,
            **grid_kwargs
        )

        return option_menu

    def add_combobox(
            self,
            id: str,
            options: list[Any],
            default: Optional[Any] = None,
            state: Optional[str] = 'readonly',
            prompt: Optional[str] = None,
            width: Optional[int] = 9,
            padding: Optional[dict[str, int]] = None,
            sticky: Optional[str] = None,
            **kwargs
            ) -> Combobox:
        assert id not in self.variables, \
            f"The widget ID '{id}' already exists!"
        grid_kwargs = {k: v for k, v in kwargs.items() if k in GRID_KWARGS}
        widget_kwargs = {k: v for k, v in kwargs.items() if k not in GRID_KWARGS}
        self.variables[id] = self.__create_tk_var(options, default)
        if prompt:
            self.add_label(
                id=f'{id}.label',
                text=prompt,
                padding=padding if padding else lbf_contents_padding,
                sticky=sticky
            )
        combobox = Combobox(
            self.labelframe,
            state=state,
            values=options,
            textvariable=self.variables[id],
            takefocus=0,
            width=width,
            **widget_kwargs
        )
        combobox.bind('<FocusOut>', lambda _: self.__assert_option_ok(id, options, default))
        combobox.bind('<Escape>', lambda _: self.__escape(id, default))
        self.__auto_place(
            combobox,
            id=id,
            padding={'padx': lbf_contents_padding['padx']} if prompt else lbf_contents_padding,
            sticky=sticky,
            **grid_kwargs
        )

        return combobox

    def group(
            self,
            id: str,
            members: list[str],
            name: Optional[str] = None,
            layout: Optional[str] = 'compact',  # Or 'relaxed'
            cspan: Optional[int] = 0,
            padding: Optional[dict[str, int]] = lbf_contents_padding,
            sticky: Optional[str] = None,
            ) -> None:
        assert all([id in self.variables for id in members]), \
            "One or more members don't exist!"
        n_members = len(members)
        assert n_members > 1, \
            "Can't make a group with just one member."
        assert cspan >= 0 and cspan < n_members, \
            f'Column span {cspan}, >=0 and <={n_members} expected.'

        if name:
            group_name_id = f'{id}.label'
            self.add_label(
                id=group_name_id,
                text=name,
                padding=padding,
                sticky=sticky
            )
            members.insert(0, group_name_id)
            # Find first member's row and swap it with the title
            first_member_row = min([self.children[m][1]['row'] for m in members][1:])
            first_member_col = min([self.children[m][1]['column'] for m in members][1:])
            self.children[group_name_id][1]['row'] = first_member_row
            self.children[group_name_id][1]['column'] = first_member_col
            if first_member_row > 0:
                self.children[group_name_id][1]['pady'] = (WIDE_PAD, 0)
            if first_member_col == 0:
                self.children[group_name_id][1]['padx'] = (THIN_PAD, 0)

        columnspan = (self.auto_pos_y + 1 + n_members) // self.maxrow + 1 if cspan == 0 else cspan
        if columnspan > 1:  # Set columnspan for all widgets in the same column as the group
            self.maxcol += 1
            self.auto_pos_y -= 1
            # Iterate over all widgets that are NOT group members
            for c in set(self.children).symmetric_difference(members[1:]):
                # Move up all widgets after group but in the same column
                if self.children[c][1]['row'] > self.children[members[1]][-1]['row'] \
                        and self.children[c][1]['column'] == self.children[members[0]][1]['column']:
                    self.children[c][1]['row'] -= 1
                if self.children[c][1]['column'] == self.children[members[1]][1]['column']:
                    self.children[c][1]['columnspan'] = columnspan
                if self.children[c][1]['column'] >= columnspan - 1:
                    self.children[c][1]['column'] += 1

        new_col = False
        for m in members[1:]:  # Treating group as a frame on its own
            self.children[m][1]['row'] += 1
            if not new_col and (columnspan > 1 and self.children[m][1]['row'] in (self.maxrow, n_members // columnspan + 1)):
                new_col = True
            if new_col:
                self.children[m][1]['column'] += 1
                self.children[m][1]['row'] -= 2
            if layout == 'compact':
                self.children[m][1]['pady'] = 0
