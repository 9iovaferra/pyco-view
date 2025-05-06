"""
Copyright (C) 2019 Pico Technology Ltd.
tkSliderWidget Copyright (c) 2020, Mengxun Li
"""
# from tkinter import *
from tkinter import (
		Tk, Menu, Checkbutton, Spinbox, IntVar, StringVar, N, E, S, W, CENTER
		)
from tkinter import ttk
# from tkinter.ttk import (
# 		Label, Frame, Labelframe, Button, Combobox, Separator, OptionMenu, Notebook
# 		)
from pycoviewlib.functions import parse_config, key_from_value, ADCDataPack
from pycoviewlib.constants import *
from pycoviewlib.gui_resources import *
from pycoviewlib.tkSliderWidget.tkSliderWidget import Slider
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from threading import Thread, Event
from subprocess import Popen, PIPE, STDOUT
from queue import Queue
import pickle
from os import path, system, listdir, remove
from pathlib import Path
from typing import Union
from webbrowser import open_new

def placeholder():
	print('This command definitely does something (trust me).')

class RootWindow(Tk):
	def __init__(self, *args, **kwargs):
		Tk.__init__(self, *args, **kwargs)
		self.after(0, self.hide())
		self.title('PycoView')
		self.protocol('WM_DELETE_WINDOW', self.delete_window)
		self.menu_bar = Menu(self)
		self.config(menu=self.menu_bar)
		self.file_menu = Menu(self.menu_bar, tearoff=0)
		self.menu_bar.add_cascade(menu=self.file_menu, label='File')
		self.file_menu.add_command(label='Open data folder', command=self.show_data_folder)
		self.help_menu = Menu(self.menu_bar, tearoff=0)
		self.menu_bar.add_cascade(menu=self.help_menu, label='Help')
		self.help_menu.add_command(label='About', command=self.open_about_window)

	def hide(self, target=None) -> None:
		""" Hide window until widgets are drawn to avoid visual glitch """
		if target is None:
			target = self
		self.attributes('-alpha', 0.0)

	def center(self, target=None) -> None:
		if target is None:
			target = self
		target.update_idletasks()
		screen_w = target.winfo_screenwidth()
		screen_h = target.winfo_screenheight()
		border_w = target.winfo_rootx() - target.winfo_x()
		title_h = target.winfo_rooty() - target.winfo_y()
		target_w = target.winfo_width() + 2 * border_w
		target_h = target.winfo_height() + title_h + border_w
		x = (screen_w - target_w) // 2
		y = (screen_h - target_h) // 2
		target.geometry(f'+{x}+{y}')
		target.attributes('-alpha', 1.0)

	def show_data_folder(self) -> None:
		home = path.expanduser('~')
		datapath = path.realpath(home + '/Documents/pyco-view/Data')
		system(f'xdg-open {datapath}')

	def open_about_window(self) -> None:
		about = Toplevel()
		about.after(0, self.hide())
		about.title('About')
		title = ttk.Label(about, text='PycoView', font=18, anchor=CENTER)
		title.grid(column=0, row=0, **uniform_padding, sticky=N+W+E)
		app_version = ttk.Label(about, text='v0.57 (pre-alpha)', anchor=CENTER)
		app_version.grid(column=0, row=1, **uniform_padding, sticky=N+W+E)
		link = ttk.Label(about, text='Github Repository', foreground='blue', cursor='hand2', anchor=CENTER)
		link.grid(column=0, row=2, **uniform_padding, sticky=S+W+E)
		link.bind('<Button-1>', lambda _: open_new('https://github.com/9iovaferra/pyco-view'))
		self.center(target=about)

	def delete_window(self) -> None:
		self.quit()
		self.destroy()

class ChannelSettings():
	def __init__(self, parent, id_: str, column: int):
		self.frame = ttk.Labelframe(parent, text=f'Channel {id_}')
		self.frame.grid(column=column, row=0, **asym_left_padding, sticky=W+E+N)

		settings[f'ch{id_}enabled'] = IntVar(value=params[f'ch{id_}enabled'])
		self.enabled = Checkbutton(
				self.frame,
				variable=settings[f'ch{id_}enabled'],
				text='Enabled',
				onvalue=1,
				offvalue=0,
				command=lambda : update_setting([f'ch{id_}enabled'], [settings[f'ch{id_}enabled'].get()])
				)
		self.enabled.grid(column=0, row=0, pady=(THIN_PAD,0), sticky=W+N)

		ttk.Label(self.frame, text='Range (±mV)').grid(column=0, row=1, **lbf_contents_padding, sticky=W+N) 
		settings[f'ch{id_}range'] = IntVar(value=chInputRanges[params[f'ch{id_}range']])
		self.chRange = ttk.Combobox(
				self.frame,
				state='readonly',
				values=chInputRanges,
				textvariable=settings[f'ch{id_}range'],
				width=7
				)
		self.chRange.grid(column=0, row=2, padx=THIN_PAD, sticky=W+N)

		ttk.Label(self.frame, text='Coupling').grid(column=0, row=3, **lbf_contents_padding, sticky=W+N) 
		settings[f'ch{id_}coupling'] = StringVar(value=key_from_value(couplings, params[f'ch{id_}coupling']))
		self.coupling = ttk.Combobox(
				self.frame,
				state='readonly',
				values=list(couplings.keys()),
				textvariable=settings[f'ch{id_}coupling'],
				width=7
				)
		self.coupling.grid(column=0, row=4, padx=THIN_PAD, sticky=W+N)

		ttk.Label(self.frame, text='Analogue offset (mV)').grid(column=0, row=5, **lbf_contents_padding, sticky=W+N) 
		settings[f'ch{id_}analogOffset'] = IntVar(value=params[f'ch{id_}analogOffset'] * 1000)
		self.analogOffset = Spinbox(
				self.frame,
				from_=0,
				to=settings[f'ch{id_}range'].get(),
				textvariable=settings[f'ch{id_}analogOffset'],
				width=7,
				increment=1
				)
		self.analogOffset.grid(column=0, row=6, padx=THIN_PAD, sticky=W+N)

		ttk.Label(self.frame, text='Bandwidth').grid(column=0, row=7, **lbf_contents_padding, sticky=W+N) 
		settings[f'ch{id_}bandwidth'] = StringVar(value=key_from_value(bandwidths, params[f'ch{id_}bandwidth']))
		self.bandwidth = ttk.Combobox(
				self.frame,
				state='readonly',
				values=list(bandwidths.keys()),
				textvariable=settings[f'ch{id_}bandwidth'],
				width=7
				)
		self.bandwidth.grid(column=0, row=8, padx=THIN_PAD, sticky=W+N)

def refresh_run_tab(event, tab: ttk.Frame) -> None:
	if event.widget.tab('current')['text'] == 'Run':
		tab.update_idletasks()

def get_timebase_lbl(timebase: int) -> str:
	interval = int(2 ** timebase / 5e-3 if timebase in range(5) else (timebase - 4) / 1.5625e-4)
	return f'{interval} ps' if interval < 1000 else f'{round(interval / 1000, 1)} ns'

def h_separator(parent, row: int, columnspan: int) -> None:
	ttk.Separator(parent, orient='horizontal').grid(
			column=0,
			row=row,
			columnspan=columnspan,
			padx=WIDE_PAD,
			pady=(WIDE_PAD,0),
			sticky=W+E
			)

def target_selection(flags: list[StringVar], targets: StringVar) -> None:
	targets.set(flags[0].get() + flags[1].get() + flags[2].get() + flags[3].get())

def apply_changes(settings: dict) -> None:
	""" Compares `settings` against `params`,
	sends updated values to `update_setting()` """
	keys = []
	values = []
	update = False
	for k, v in settings.items():
		if 'mode' in k:
			new_value = modes[v.get()]
		elif 'range' in k:
			new_value = chInputRanges.index(v.get())
		elif 'coupling' in k:
			new_value = couplings[v.get()][0]
		elif 'analogOffset' in k:
			new_value = v.get() / 1000
		elif 'bandwidth' in k:
			new_value = bandwidths[v.get()]
		# elif 'target' in k:
		# 	new_value = list(v.get())
		else:
			new_value = v.get()
		if params[k] != new_value:
			keys.append(k)
			values.append(new_value)
			update = True
	if update:
		update_setting(keys, values)

def update_setting(
		keys: list[str],
		new_values: list[Union[str, int, float]]
		) -> None:
	"""
	Compares keys-value pairs in `config.ini` to
	the same pairs given as input, overwrites file as needed
	"""
	with open('/home/pi/Documents/pyco-view/config.ini', 'r') as ini:
		lines = ini.readlines()
	for k, v in zip(keys, new_values):
		print(f'{k}: {params[k]} -> {v}')
		params[k] = v
		for i, line in enumerate(lines):
			if k in line:
				lines[i] = f'{k} = {v}\n'
				break
	with open('/home/pi/Documents/pyco-view/config.ini', 'w') as ini:
		ini.writelines(lines)
	print('Config updated.\n')

class Histogram():
	def __init__(self, root, xlim: list[int], ylim: list[int], bins: int):
		self.root = root
		self.fig, self.ax = plt.subplots(figsize=(6, 4), layout='tight')
		self.xlim = xlim
		self.ylim = ylim
		self.bins = bins
		self.buffer = []
		self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
		self.canvas.get_tk_widget().grid(column=0, row=0, padx=THIN_PAD, pady=THIN_PAD, sticky='nesw')
		self.stop_event = Event()
		self.queue = Queue()

	def draw(self, mode: str) -> None:
		self.ax.set_xlabel('Charge (C)' if mode == 'adc' else 'Delay (ns)')
		self.ax.set_ylabel('Counts')
		self.ax.set_yticks(
				ticks=list(range(0, self.ylim[1] + 50, 50)),
				labels=[f'{l}' for l in range(0, self.ylim[1] + 50, 50)]
				)
		self.ax.yaxis.grid(True)
		self.ax.set_xlim(self.xlim)
		self.ax.set_ylim(self.ylim)
		self.canvas.draw()

	def follow(self):
		"""
		Checks /pickles folder for pickled data coming from applet.
		All tkinter commands must run in mainloop, so data is queued
		to `place_on_canvas` which is outside of follower thread.
		"""
		# plt.ion()
		while not self.stop_event.is_set():
			pickle_files = listdir('pickles')
			if pickle_files:
				try:
					with open(f'pickles/{pickle_files[-1]}', 'rb') as pkl:
						data = pickle.load(pkl)
				except EOFError:
					continue
				except pickle.UnpicklingError:
					print(f'/!\\ {pickle_files[-1]} has corrupted data')
					continue
				self.queue.put(f'{pickle_files[-1]}')
				self.place_on_canvas(data=data.x)
				print(f'follow: Unpickled {pickle_files[-1]}')
				remove(f'pickles/{pickle_files[-1]}')

		# plt.ioff()
		self.cleanup()

	def place_on_canvas(self, data: float) -> None:
		item = self.queue.get_nowait()
		if self.ax.containers:
			_ = [bar.remove() for bar in self.ax.containers]
		self.buffer.append(data)
		counts, bins = np.histogram(self.buffer, range=self.xlim, bins=self.bins)
		livecounts, livebins, livebars = self.ax.hist(
				bins[:-1], bins, weights=counts, color='tab:blue'
				)
		# plt.pause(0.01)
		self.canvas.draw_idle()
		self.queue.task_done()

	def cleanup(self):
		if listdir('pickles'):
			_ = [remove(f'pickles/{p}') for p in listdir('pickles')]

class Job:
	def __init__(self, root: Tk, applet: str, hist: Histogram) -> None:
		self.python = path.expanduser('~/.venv/bin/python3')
		self.root = root
		self.applet = applet
		self.hist = hist
		self.follower_thread = Thread(target=self.hist.follow)

	def run(self, mode: str) -> None:
		self.applet = mode
		self.thread = Thread(target=self.start)
		self.thread.start()
		self.follower_thread.start()
		# Exit subprocess if GUI is closed
		self.root.protocol('WM_DELETE_WINDOW', self.kill)

	def start(self) -> None:
		print(f'Running {self.applet}.py...')
		self.process = Popen(
				[self.python, f'{self.applet}.py'], stdin=PIPE, stderr=STDOUT
				)
		self.stopped = False

	def stop(self) -> None:
		"""
		Stop subprocess and quit GUI.
		Avoid killing subprocess more than once.
		"""
		if self.stopped:
			return
		print(f'Stopping acquisition in {self.applet}.py')
		out, err = self.process.communicate(input=b'q\n')
		self.process.wait()
		self.thread.join()
		self.hist.stop_event.set()
		self.stopped = True

	def kill(self) -> None:
		self.stop()
		self.root.quit()
		self.root.destroy()


def main() -> None:
	""" Reading runtime parameters from .ini file """
	# params: dict[str, Union[int, float, str]]
	global params
	params = parse_config()

	param_offsets: list[float] = []
	param_ranges: list[int] = []
	param_couplings: list[str] = []
	for k, v in params.items():
		if 'Offset' in k:
			param_offsets.append(v)
		elif 'range' in k:
			param_ranges.append(chInputRanges[v])
		elif 'coupling' in k:
			param_couplings.append(key_from_value(couplings, v))

	try:
		pycoview_folder: Path = Path('~/Documents/pyco-view/Data').expanduser()
		pycoview_folder.mkdir(exist_ok=True)
	except PermissionError:
		print("Permission Error: cannot write to this location.")
		return

	""" Main window & menu bar """
	root = RootWindow()

	topFrame = ttk.Frame(root, padding=(THIN_PAD,0,THIN_PAD,THIN_PAD))
	topFrame.grid(column=0, row=0, padx=WIDE_PAD, pady=(WIDE_PAD,0), sticky=N+W+E)
	topFrame.columnconfigure(3, weight=3)

	ttk.Label(topFrame, text='Mode:').grid(column=0, row=0, sticky=W)
	modeVar = StringVar(value=key_from_value(modes, params['mode']))
	modeSelector = ttk.OptionMenu(
			topFrame,
			modeVar,
			key_from_value(modes, params['mode']),
			*tuple(modes.keys()),
			command=lambda _: update_setting(['mode'], [modes[modeVar.get()]])
			)
	modeSelector.grid(column=1, row=0, padx=WIDE_PAD, sticky=W)

	""" Tabs """
	tabsFrame = ttk.Frame(root, padding=(THIN_PAD,0,THIN_PAD,THIN_PAD))
	tabsFrame.grid(column=0, row=1, **uniform_padding, sticky=W+E+N+S)
	tabControl = ttk.Notebook(tabsFrame)
	runTab = ttk.Frame(tabControl, padding=(0,0))
	# tabControl.bind('<<NotebookTabChanged>>', lambda _: refresh_run_tab(event, runTab))
	settingsTab = ttk.Frame(tabControl, padding=(0,0))
	tabControl.add(runTab, text='Run')
	tabControl.add(settingsTab, text='Settings')
	tabControl.pack(expand=1, fill='both')

	""" Run tab """
	summary = ttk.Labelframe(runTab, text='Summary')
	summary.grid(column=0, row=0, columnspan=2, **asym_left_padding, sticky=W+E+N+S)

	""" Summary labelframe contents.
	'summary_textvar' is a container of 'StringVar' or 'IntVar' objects used to update the UI
	as settings are changed. The 'refresh_run_tab' function takes care of setting the
	new values so that the UI reflects said changes. """
	summary_textvar = {
			'range': [StringVar(value=f'±{r}') for r in param_ranges],
			'analogOffset': [IntVar(value=int(o * 1000)) for o in param_offsets],
			'coupling': [StringVar(value=c) for c in param_couplings],
			'target': [StringVar(value=u'\u2713' if ch in params['target'] else u'\u2717') for ch in channelIDs],
			'timebase': StringVar(value=get_timebase_lbl(params['timebase'])),
			'thresholdmV': StringVar(value=f"{params['thresholdmV']:.0f} mV"),
			'delaySeconds': StringVar(value=f"{params['delaySeconds']} s"),
			'autoTrigms': StringVar(value=f"{params['autoTrigms']} ms"),
			'preTrigSamples': StringVar(value=f"{params['preTrigSamples']}"),
			'postTrigSamples': StringVar(value=f"{params['postTrigSamples']}")
			}

	for i, ch, color in zip(range(1, 5), channelIDs, ['blue', 'red', 'green3', 'gold']):
		ttk.Label(summary, text=ch, background=color, foreground='white', font='bold', anchor=E).grid(
				column=i, row=0, padx=0 if i == 1 else (THIN_PAD, 0), pady=(WIDE_PAD, 0), sticky='we'
				)
	for i, entry in enumerate(['Range (mV)', 'Analog offset (mV)', 'Coupling', 'Trigger target']):
		ttk.Label(summary, text=entry).grid(
				column=0, row=i + 1, padx=(THIN_PAD, 0), pady=(WIDE_PAD if i == 0 else LINE_PAD, 0), sticky=W
				)
	for i in range(4):
		ttk.Label(summary, textvariable=summary_textvar['range'][i], anchor=E).grid(
				column=i + 1, row=1, padx=0 if i == 0 else (THIN_PAD,0), pady=(WIDE_PAD,0), sticky=E
				)
		ttk.Label(summary, textvariable=summary_textvar['analogOffset'][i], anchor=E).grid(
				column=i + 1, row=2, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky=E
				)
		ttk.Label(summary, textvariable=summary_textvar['coupling'][i], anchor=E).grid(
				column=i + 1, row=3, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky=E
				)
		ttk.Label(summary, textvariable=summary_textvar['target'][i], anchor=E).grid(
				column=i + 1, row=4, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky=E
				)

	h_separator(summary, row=5, columnspan=5)

	ttk.Label(summary, text='Timebase').grid(column=0, row=6, padx=(THIN_PAD,0), pady=(WIDE_PAD,0), sticky=W)
	ttk.Label(summary, textvariable=summary_textvar['timebase'], anchor=E).grid(
			column=1, row=6, columnspan=4, padx=0, pady=(WIDE_PAD,0), sticky=W+E
			)
	ttk.Label(summary, text='Threshold').grid(column=0, row=7, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
	ttk.Label(summary, textvariable=summary_textvar['thresholdmV'], anchor=E).grid(
			column=1, row=7, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky=W+E
			)
	ttk.Label(summary, text='Trigger delay').grid(column=0, row=8, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
	ttk.Label(summary, textvariable=summary_textvar['delaySeconds'], anchor=E).grid(
			column=1, row=8, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky=W+E
			)
	ttk.Label(summary, text='Auto-trigger after').grid(column=0, row=9, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
	ttk.Label(summary, textvariable=summary_textvar['autoTrigms'], anchor=E).grid(
			column=1, row=9, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky=W+E
			)
	ttk.Label(summary, text='Pre-trigger samples').grid(column=0, row=10, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
	ttk.Label(summary, textvariable=summary_textvar['preTrigSamples'], anchor=E).grid(
			column=1, row=10, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky=W+E
			)
	ttk.Label(summary, text='Post-trigger samples').grid(column=0, row=11, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
	ttk.Label(summary, textvariable=summary_textvar['postTrigSamples'], anchor=E).grid(
			column=1, row=11, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky=W+E
			)

	h_separator(summary, row=12, columnspan=5)

	logFlag = IntVar(value=params['log'])
	logCheckBox = Checkbutton(
			summary, variable=logFlag, text='Log acquisition',
			onvalue=1, offvalue=0, command=lambda : update_setting(['log'], [logFlag.get()])
			)
	logCheckBox.grid(column=0, row=13, columnspan=4, pady=(WIDE_PAD,0), sticky=W+S)
	plotFlag = IntVar(value=params['plot'])
	plotCheckBox = Checkbutton(
			summary, variable=plotFlag, text='Export figure for each capture',
			onvalue=1, offvalue=0, command=lambda : update_setting(['plot'], [plotFlag.get()])
			)
	plotCheckBox.grid(column=0, row=14, columnspan=4, pady=(LINE_PAD, WIDE_PAD), sticky='ws')

	""" Histogram """
	histogramLbf = ttk.Labelframe(runTab, text='Histogram')
	histogramLbf.grid(column=2, row=0, columnspan=7, rowspan=2, **hist_padding, sticky='nesw')
	ttk.Label(runTab, text='Bounds:', anchor='w').grid(column=2, row=2, padx=(THIN_PAD, 0), pady=(THIN_PAD, 0), sticky='n')
	histBinsSlider = Slider(
			runTab, width=200, height=40, min_val=0, max_val=100, init_lis=params['histBounds'],
			step_size=1, show_value=True, removable=False, addable=False
			)
	histBinsSlider.grid(column=3, row=2, padx=0, pady=0, sticky=N)
	ttk.Label(runTab, text='Bins:', anchor=CENTER).grid(column=4, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky='n')
	histBinsVar = IntVar(value=params['histBins'])
	binsSpbx = Spinbox(runTab, from_=50, to=200, textvariable=histBinsVar, width=5, increment=10)
	binsSpbx.grid(column=5, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky='nw')

	histogram = Histogram(
			root=histogramLbf, xlim=histBinsSlider.getValues(), ylim=[0, 250], bins=histBinsVar.get()
			)
	histogram.draw(mode=modes[modeVar.get()])

	""" Start/Stop job buttons """
	job = Job(root=root, applet=modes[modeVar.get()], hist=histogram)
	startButton = ttk.Button(runTab, text='START', command=lambda : job.run(modes[modeVar.get()]))
	startButton.grid(column=0, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=W+E+S)
	stopButton = ttk.Button(runTab, text='STOP', command=job.stop)
	stopButton.grid(column=1, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=W+E+S)

	histApplyBtn = ttk.Button(runTab, text='Apply', width=8, command=lambda : histogram.draw(modes[modeVar.get()]))
	histApplyBtn.grid(column=6, row=2, padx=(THIN_PAD, 0), pady=(THIN_PAD, 0), ipady=THIN_PAD, sticky='ne')
	# histResetBtn = ttk.Button(runTab, text='Reset', width=6, command=placeholder)
	# histResetBtn.grid(column=7, row=2, padx=(THIN_PAD, 0), pady=(THIN_PAD, 0), ipady=THIN_PAD, sticky='ne')
	histSaveBtn = ttk.Button(runTab, text='Save as...', width=8, command=placeholder)
	histSaveBtn.grid(column=8, row=2, padx=(THIN_PAD, 0), pady=(THIN_PAD, 0), ipady=THIN_PAD, sticky='ne')

	""" Settings tab. The 'settings' dictionary will store all the
	temporary changes until the 'Apply' button is pressed, when
	such changes will be written to the config.ini file. """
	global settings
	settings = {}

	""" Trigger settings """
	trigSettingsLbf = ttk.Labelframe(settingsTab, text='Trigger')
	trigSettingsLbf.grid(column=0, row=0, rowspan=2, **asym_left_padding, sticky=W+E+N)

	ttk.Label(trigSettingsLbf, text='Target(s)').grid(column=0, row=0, columnspan=2, **lbf_contents_padding, sticky=W+N) 
	settings['target'] = StringVar(value=''.join(params['target']))
	targetFlags = [StringVar(value='') for _ in range(4)]
	targetAChbx = Checkbutton(
			trigSettingsLbf,
			variable=targetFlags[0],
			text='A',
			onvalue='A',
			offvalue='',
			command=lambda : target_selection(targetFlags, settings['target'])
			)
	targetBChbx = Checkbutton(
			trigSettingsLbf,
			variable=targetFlags[1],
			text='B',
			onvalue='B',
			offvalue='',
			command=lambda : target_selection(targetFlags, settings['target'])
			)
	targetCChbx = Checkbutton(
			trigSettingsLbf,
			variable=targetFlags[2],
			text='C',
			onvalue='C',
			offvalue='',
			command=lambda : target_selection(targetFlags, settings['target'])
			)
	targetDChbx = Checkbutton(
			trigSettingsLbf,
			variable=targetFlags[3],
			text='D',
			onvalue='D',
			offvalue='',
			command=lambda : target_selection(targetFlags, settings['target'])
			)
	for i, c in enumerate([targetAChbx, targetBChbx, targetCChbx, targetDChbx]):
		if channelIDs[i] in params['target']:
			c.select()
		c.grid(column=0 if i <= 1 else 1, row=i+1 if i <= 1 else i-1,
			padx=lbf_contents_padding['padx'], sticky=W+N)

	ttk.Label(trigSettingsLbf, text='Pre-trigger samples').grid(column=0, row=3, columnspan=2, **lbf_contents_padding, sticky=W+N) 
	settings['preTrigSamples'] = IntVar(value=params['preTrigSamples'])
	preTrigSpbx = Spinbox(
			trigSettingsLbf,
			from_=0,
			to=500,
			textvariable=settings['preTrigSamples'],
			width=7,
			increment=1
			)
	preTrigSpbx.grid(column=0, row=4, columnspan=2, padx=lbf_contents_padding['padx'], sticky=W+N)

	ttk.Label(trigSettingsLbf, text='Post-trigger samples').grid(column=0, row=5, columnspan=2, **lbf_contents_padding, sticky=W+N) 
	settings['postTrigSamples'] = IntVar(value=params['postTrigSamples'])
	postTrigSpbx = Spinbox(
			trigSettingsLbf,
			from_=1,
			to=500,
			textvariable=settings['postTrigSamples'],
			width=7,
			increment=1
			)
	postTrigSpbx.grid(column=0, row=6, columnspan=2, padx=lbf_contents_padding['padx'], sticky=W+N)

	ttk.Label(trigSettingsLbf, text='Timebase').grid(column=0, row=7, columnspan=2, **lbf_contents_padding, sticky=W+N) 
	settings['timebase'] = IntVar(value=params['timebase'])
	timebaseSpbx = Spinbox(
			trigSettingsLbf,
			from_=0,
			to=2 ** 32 - 1,
			textvariable=settings['timebase'],
			width=7,
			increment=1
			)
	timebaseSpbx.grid(column=0, row=8, columnspan=2, padx=lbf_contents_padding['padx'], sticky=W+N)

	ttk.Label(trigSettingsLbf, text='Threshold (mV)').grid(column=0, row=9, columnspan=2, **lbf_contents_padding, sticky=W+N) 
	settings['thresholdmV'] = IntVar(value=int(params['thresholdmV']))
	thresholdSpbx = Spinbox(
			trigSettingsLbf,
			from_=-chInputRanges[params[f"ch{params['target'][0]}range"]], # will need a better fix for this
			to=0,
			textvariable=settings['thresholdmV'],
			width=7,
			increment=1
			)
	thresholdSpbx.grid(column=0, row=10, columnspan=2, padx=lbf_contents_padding['padx'], sticky=W+N)

	ttk.Label(trigSettingsLbf, text='Auto trigger (ms)').grid(column=0, row=11, columnspan=2, **lbf_contents_padding, sticky=W+N) 
	settings['autoTrigms'] = IntVar(value=params['autoTrigms'])
	autoTrigSpbx = Spinbox(
			trigSettingsLbf,
			from_=500,
			to=10000,
			textvariable=settings['autoTrigms'],
			width=7,
			increment=100
			)
	autoTrigSpbx.grid(column=0, row=12, columnspan=2, padx=lbf_contents_padding['padx'], sticky=W+N)

	ttk.Label(trigSettingsLbf, text='Trigger delay (s)').grid(column=0, row=13, columnspan=2, **lbf_contents_padding, sticky=W+N) 
	settings['delaySeconds'] = IntVar(value=params['delaySeconds'])
	delaySpbx = Spinbox(
			trigSettingsLbf,
			from_=0,
			to=10,
			textvariable=settings['delaySeconds'],
			width=7,
			increment=1
			)
	delaySpbx.grid(column=0, row=14, columnspan=2, padx=lbf_contents_padding['padx'], sticky=W+N)

	""" Channels settings """
	chASettings = ChannelSettings(settingsTab, id_='A', column=1)
	chBSettings = ChannelSettings(settingsTab, id_='B', column=2)
	chCSettings = ChannelSettings(settingsTab, id_='C', column=3)
	chDSettings = ChannelSettings(settingsTab, id_='D', column=4)

	applySettingsBtn = ttk.Button(settingsTab, text='Apply', command=lambda : apply_changes(settings))
	applySettingsBtn.grid(column=4, row=1, padx=0, pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=E)

	root.center()
	root.mainloop()

if __name__ == '__main__':
	main()
