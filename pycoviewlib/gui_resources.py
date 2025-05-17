from tkinter import IntVar, DoubleVar, StringVar, Checkbutton, Spinbox
from tkinter.ttk import Frame, Separator, Notebook, Labelframe, Label, OptionMenu, Combobox
from pycoviewlib.functions import _isfloat
from typing import Union, Any, Optional, Callable

""" Padding presets (frame padding: 'left top right bottom') """
THIN_PAD = 6
LINE_PAD = int(THIN_PAD / 3)
MED_PAD = int((THIN_PAD * 4) / 3)
WIDE_PAD = 2 * THIN_PAD
uniform_padding = {'padx': WIDE_PAD, 'pady': WIDE_PAD, 'ipadx': THIN_PAD, 'ipady': THIN_PAD}
hist_padding = {'padx': (WIDE_PAD, 0), 'pady': (WIDE_PAD, 0), 'ipadx': 0, 'ipady': 0}
lbf_padding = {'padx': WIDE_PAD, 'pady': WIDE_PAD, 'ipadx': THIN_PAD, 'ipady': THIN_PAD}
lbf_asym_padding = {'padx': (WIDE_PAD, 0), 'pady': WIDE_PAD, 'ipadx': THIN_PAD, 'ipady': THIN_PAD}
lbf_asym_padding_no_top = {'padx': (WIDE_PAD, 0), 'pady': (0, WIDE_PAD), 'ipadx': THIN_PAD, 'ipady': THIN_PAD}
lbf_contents_padding = {'padx': (THIN_PAD, 0), 'pady': (MED_PAD, 2)}

""" Colors """
HIST_COLOR = 'tab:blue'

def HSeparator(parent, row: int, columnspan: int) -> None:
	Separator(parent, orient='horizontal').grid(
			column=0,
			row=row,
			columnspan=columnspan,
			padx=WIDE_PAD,
			pady=(WIDE_PAD, 0),
			sticky='ew'
			)

tkAnyVar = Union[IntVar, DoubleVar, StringVar]

class TabLabelframe(Labelframe):
	def __init__(
			self,
			parent: Notebook,
			title: str,
			col: int,
			row: int,
			size: tuple[int, int],
			sticky: Optional[str] = None,  # Same format as in tkinter
			cspan: Optional[int] = None,
			rspan: Optional[int] = None,
			padding: Optional[dict[str, int]] = None
			):
		self.parent = parent
		self.grandparent = parent.winfo_toplevel()  # Get root window
		self.labelframe = Labelframe(parent, text=title)
		self.auto_pos_x = 0  # Self-increasing column counter
		self.auto_pos_y = 0  # Self-increasing row counter
		self.maxcol = size[0]
		self.maxrow = size[1]
		self.variables: dict[str, tkAnyVar] = {}  # Container for tk variables
		# if not all([c in 'nesw' for c in sticky]) or not isinstance(sticky, str):
		# 	raise Exception('Invalid parameter value')
		grid_kwargs = {'column': col, 'row': row, 'sticky': 'nesw' if sticky is None else sticky}
		if cspan is not None:
			grid_kwargs['columnspan'] = cspan
		# 	_ = [self.parent.grid_columnconfigure(c + col, weight=1) for c in range(cspan)]
		# else:
		# 	self.parent.grid_columnconfigure(col, weight=1)
		if rspan is not None:
			grid_kwargs['rowspan'] = rspan
		# 	_ = [self.parent.grid_rowconfigure(r + row, weight=1) for r in range(rspan)]
		# else:
		# 	self.parent.grid_rowconfigure(row, weight=1)
		grid_kwargs.update(padding if padding is not None else lbf_asym_padding)
		self.labelframe.grid(**grid_kwargs)

	def __auto_place(self, widget, padding: dict[str, int] = None, sticky: str = None):
		# print(f'{self.auto_pos_x=}\t{self.auto_pos_y=}')
		grid_kwargs = {
				'column': self.auto_pos_x,
				'row': self.auto_pos_y,
				'sticky': 'nw' if sticky is None else sticky,
				'padx': (0, 0),
				'pady': (0, 0)
				}
		grid_kwargs.update(padding if padding is not None else lbf_contents_padding)
		if self.auto_pos_x > 0:  # Spacing between columns
			grid_kwargs['padx'] = (  # Checkbuttons have wider left padding by default
				WIDE_PAD * 5 / 3 - 1 if widget.winfo_class() == 'Checkbutton' else 2 * WIDE_PAD,
				grid_kwargs['padx'][1]
				)
		print(f'{grid_kwargs=}')
		if self.auto_pos_y == self.maxrow - 1:
			self.auto_pos_x += 1
			self.auto_pos_y = 0
		elif self.auto_pos_x == self.maxcol - 1:
			raise Exception('Too many widgets for specified size.')
		else:
			self.auto_pos_y += 1

		widget.grid(**grid_kwargs)

	def __create_tk_var(self, options: list[Any], default: Any | None) -> tkAnyVar:
		given_type = type(options[0])
		if default is not None and given_type is not type(default):
			raise TypeError(
				f'Options and default value types don\'t match ({given_type!s} vs {type(default)!s})'
				)
		if given_type is str:
			return StringVar(self.labelframe, value=options[0] if default is None else default)
		elif given_type is int:
				return IntVar(self.labelframe, value=options[0] if default is None else default)
		elif given_type is float:
				return DoubleVar(self.labelframe, value=options[0] if default is None else default)
		else:
			raise TypeError(f'Invalid variable type ({given_type})')

	def __validate(self, entry: str) -> bool:
		valid: bool = entry == '' or entry.isdigit() or _isfloat(entry)
		return valid

	def __assert_entry_ok(self, widget, valid_range: tuple[int, int]) -> None:
		if widget.get().isdigit():
			widget_value = int(widget.get())
		else:
			widget_value = float(widget.get())
		if widget_value < valid_range[0]:
			widget.delete(0, 'end')
			widget.insert(0, str(valid_range[0]))
		elif widget_value > valid_range[1]:
			widget.delete(0, 'end')
			widget.insert(0, str(valid_range[1]))

	def get_value(self, id: str) -> Any:
		return self.variables[id].get()

	def get_raw(self, id: str) -> tkAnyVar:
		return self.variables[id]

	def add_label(
			self,
			text: str,
			parent: Notebook | Frame = None,  # Optional parent frame for group
			sticky: Optional[str] = None,
			padding: Optional[dict[str, int]] = None
			) -> Label:
		label = Label(self.labelframe if parent is None else parent, text=text)
		self.__auto_place(label, sticky=sticky)
		return label

	def add_spinbox(
			self,
			id: str,
			from_to: tuple[int | float, int | float],
			step: int | float,
			prompt: str = None,
			default: Any = None,
			width: int = 7,
			padding: dict[str, int] = None,
			sticky: str = None
			) -> Spinbox:
		if id in self.variables:
			raise Exception(f'The widget ID \'{id}\' already exists!')
		self.variables[id] = self.__create_tk_var(from_to, default)
		if prompt is not None:
			self.add_label(
				text=prompt, padding=padding if padding is not None else lbf_contents_padding, sticky=sticky
				)
		spinbox = Spinbox(
				self.labelframe,
				from_=from_to[0],
				to=from_to[1],
				textvariable=self.variables[id],
				width=width,
				increment=step,
				validate='key',
				validatecommand=(self.grandparent.register(self.__validate), '%P')
				)
		spinbox.bind('<FocusOut>', lambda _: self.__assert_entry_ok(spinbox, from_to))
		self.__auto_place(
			spinbox,
			padding={'padx': lbf_contents_padding['padx']} if prompt is not None else lbf_contents_padding,
			sticky=sticky
			)
		return spinbox

	def add_checkbutton(
			self,
			id: str,
			prompt: str,
			on_off: tuple[Any],
			default: Any = None,
			command: Callable = None,
			padding: dict[str, int] = None,
			sticky: str = None
			) -> Checkbutton:
		if id in self.variables:
			raise Exception(f'The widget ID \'{id}\' already exists!')
		self.variables[id] = self.__create_tk_var(on_off, default)
		checkbutton = Checkbutton(
				self.labelframe,
				variable=self.variables[id],
				text=prompt,
				onvalue=on_off[0],
				offvalue=on_off[1]
				)
		if default == on_off[0]:
			checkbutton.select()
		if command is not None:
			checkbutton.config(command=command)
		self.__auto_place(
			checkbutton,
			padding={'pady': (THIN_PAD, 0)} if padding is None else padding,
			sticky=sticky
			)
		return checkbutton

	def add_optionmenu(
			self,
			id: str,
			options: list[Any],
			default: Any = None,
			prompt: str = None,
			padding: dict[str, int] = None,
			sticky: str = None
			) -> OptionMenu:
		if id in self.variables:
			raise Exception(f'The widget ID \'{id}\' already exists!')
		self.variables[id] = self.__create_tk_var(options, default)
		if prompt is not None:
			self.add_label(
				text=prompt, padding=padding if padding is not None else lbf_contents_padding, sticky=sticky
				)
		option_menu = OptionMenu(
				self.labelframe,
				self.variables[id],
				default if default is not None else options[0],
				*options
				)
		self.__auto_place(
			option_menu,
			padding={'padx': lbf_contents_padding['padx']} if prompt is not None else lbf_contents_padding,
			sticky=sticky
			)
		return option_menu

	def add_combobox(
			self,
			id: str,
			options: list[Any],
			default: Any = None,
			state: str = 'readonly',
			prompt: str = None,
			width: int = 7,
			padding: dict[str, int] = None,
			sticky: str = None
			) -> Combobox:
		if id in self.variables:
			raise Exception(f'The widget ID \'{id}\' already exists!')
		self.variables[id] = self.__create_tk_var(options, default)
		if prompt is not None:
			self.add_label(
				text=prompt, padding=padding if padding is not None else lbf_contents_padding, sticky=sticky
				)
		combobox = Combobox(
				self.labelframe,
				state=state,
				values=options,
				textvariable=self.variables[id],
				width=width
				)
		self.__auto_place(
			combobox,
			padding={'padx': lbf_contents_padding['padx']} if prompt is not None else lbf_contents_padding,
			sticky=sticky
			)
		return combobox

	def group(
			self,
			members: list[str],
			name: str = None,
			layout: str = 'relaxed',
			padding: dict[str, int] = None,
			sticky: str = None
			) -> None:
		""" MEGA WIP """
		if not all([id in self.variables for id in members]):
			raise Exception('One or more members don\'t exist!')
		if (len(members) == self.maxrow and name is not None) or (len(members) > self.maxrow):
			layout = 'compact'
		# frame = Frame(self.labelframe, padding=0)
		if name is not None:
			self.add_label(
				text=name, padding=padding if padding is not None else lbf_contents_padding, sticky=sticky
				)
