from tkinter import IntVar, DoubleVar, StringVar
from tkinter.ttk import Separator, Notebook, Labelframe, Label, OptionMenu
from typing import Union, Any, Optional

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

def h_separator(parent, row: int, columnspan: int) -> None:
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
		self.labelframe = Labelframe(parent, text=title)
		self.auto_pos_x = 0  # Self-increasing column counter
		self.auto_pos_y = 0  # Self-increasing row counter
		self.maxcol = size[0]
		self.maxrow = size[1]
		self.variables: dict[str, tkAnyVar] = {}  # Container for tk variables
		# if not all([c in 'nesw' for c in sticky]) or not isinstance(sticky, str):
		# 	raise Exception('Invalid parameter value')
		grid_kwargs = {'column': col, 'row': row, 'sticky': 'nw' if sticky is None else sticky}
		if cspan is not None:
			grid_kwargs['columnspan'] = cspan
		if rspan is not None:
			grid_kwargs['rowspan'] = rspan
		grid_kwargs.update(padding if padding is not None else lbf_asym_padding)
		self.labelframe.grid(**grid_kwargs)

	def __auto_place(self, widget, padding=None, sticky=None):
		# print(f'{self.auto_pos_x=}\t{self.auto_pos_y=}')
		grid_kwargs = {
				'column': self.auto_pos_x,
				'row': self.auto_pos_y,
				'sticky': 'nw' if sticky is None else sticky,
				}
		grid_kwargs.update(padding if padding is not None else lbf_contents_padding)
		# print(f'{grid_kwargs=}')
		widget.grid(**grid_kwargs)
		if self.auto_pos_y == self.maxrow:
			self.auto_pos_x += 1
			self.auto_pos_y = 0
		elif self.auto_pos_x == self.maxcol:
			raise Exception('Too many widgets for specified size.')
		else:
			self.auto_pos_y += 1

	def __create_tk_var(self, vtype: str) -> tkAnyVar:
		match vtype:
			case 'str':
				return StringVar(self.labelframe, value='')
			case 'int':
				return IntVar(self.labelframe, value=0)
			case 'double':
				return DoubleVar(self.labelframe, value=0.0)
			case _:
				raise TypeError(f'Invalid variable type ({vtype})')

	def get_value(self, id: str) -> Any:
		return self.variables[id].get()

	def get_raw(self, id: str) -> tkAnyVar:
		return self.variables[id]

	def add_label(
			self,
			text: str,
			sticky: Optional[str] = None,
			padding: Optional[dict[str, int]] = None
			) -> Label:
		label = Label(self.labelframe, text=text)
		self.__auto_place(label, sticky=sticky)
		return label

	def add_optionmenu(
			self,
			id: str,
			vtype: str,
			options: list[Any],
			default=None,
			prompt=None,
			padding=None,
			sticky=None
			) -> OptionMenu:
		if prompt is not None:
			self.add_label(
					text=prompt, padding=padding if padding is not None else lbf_contents_padding, sticky=sticky
					)
		self.variables[id] = self.__create_tk_var(vtype)
		self.variables[id].set(default if default is not None else options[0])
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
		# return option_menu
