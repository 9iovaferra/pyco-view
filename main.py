"""
Copyright (C) 2019 Pico Technology Ltd.
tkSliderWidget Copyright (c) 2020, Mengxun Li
"""
# from tkinter import *
from tkinter import (
		Tk, Toplevel, Menu, Checkbutton, Spinbox, IntVar, StringVar, CENTER
		)
from tkinter.filedialog import asksaveasfilename
from tkinter.ttk import (
		Label, Frame, Labelframe, Button, Combobox, OptionMenu, Notebook
		)
from pycoviewlib.functions import parse_config, key_from_value, DataPack
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
from os import system, listdir, remove
from pathlib import Path
from typing import Union
from webbrowser import open_new

def placeholder():
	print('This command definitely does something (trust me).')

class RootWindow(Tk):
	def __init__(self, *args, **kwargs):
		Tk.__init__(self, *args, **kwargs)
		self.resizable(0, 0)
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
		datapath = Path(f'{PV_DIR}/Data')
		system(f'xdg-open {datapath}')

	def open_about_window(self) -> None:
		about = Toplevel()
		about.resizable(0, 0)
		about.after(0, self.hide())
		about.title('About')
		title = Label(about, text='PycoView', font=18, anchor=CENTER)
		title.grid(column=0, row=0, **uniform_padding, sticky='new')
		app_version = Label(about, text='v0.57 (pre-alpha)', anchor=CENTER)
		app_version.grid(column=0, row=1, **uniform_padding, sticky='new')
		link = Label(about, text='Github Repository', foreground='blue', cursor='hand2', anchor=CENTER)
		link.grid(column=0, row=2, **uniform_padding, sticky='esw')
		link.bind('<Button-1>', lambda _: open_new('https://github.com/9iovaferra/pyco-view'))
		self.center(target=about)

	def delete_window(self) -> None:
		self.quit()
		self.destroy()

class ChannelSettings():
	def __init__(self, parent: Notebook, id: str, column: int):
		self.id = id
		self.frame = Labelframe(parent, text=f'Channel {id}')
		self.frame.grid(column=column, row=0, **lbf_asym_padding, sticky='new')

		settings[f'ch{id}enabled'] = IntVar(value=params[f'ch{id}enabled'])
		self.enabled = Checkbutton(
				self.frame,
				variable=settings[f'ch{id}enabled'],
				text='Enabled',
				onvalue=1,
				offvalue=0
				)
		self.enabled.grid(column=0, row=0, pady=(THIN_PAD, 0), sticky='nw')

		Label(self.frame, text='Range (±mV)').grid(column=0, row=1, **lbf_contents_padding, sticky='nw') 
		settings[f'ch{id}range'] = IntVar(value=chInputRanges[params[f'ch{id}range']])
		self.chRange = Combobox(
				self.frame,
				state='readonly',
				values=chInputRanges,
				textvariable=settings[f'ch{id}range'],
				width=7
				)
		self.chRange.grid(column=0, row=2, padx=THIN_PAD, sticky='nw')

		Label(self.frame, text='Coupling').grid(column=0, row=3, **lbf_contents_padding, sticky='nw') 
		settings[f'ch{id}coupling'] = StringVar(value=key_from_value(couplings, params[f'ch{id}coupling']))
		self.coupling = Combobox(
				self.frame,
				state='readonly',
				values=list(couplings.keys()),
				textvariable=settings[f'ch{id}coupling'],
				width=7
				)
		self.coupling.grid(column=0, row=4, padx=THIN_PAD, sticky='nw')

		Label(self.frame, text='Analogue offset (mV)').grid(column=0, row=5, **lbf_contents_padding, sticky='nw')
		settings[f'ch{id}analogOffset'] = IntVar(value=params[f'ch{id}analogOffset'] * 1000)
		self.analogOffset = Spinbox(
				self.frame,
				from_=0,
				to=settings[f'ch{id}range'].get(),
				textvariable=settings[f'ch{id}analogOffset'],
				width=7,
				increment=1
				)
		self.analogOffset.grid(column=0, row=6, padx=THIN_PAD, sticky='nw')

		Label(self.frame, text='Bandwidth').grid(column=0, row=7, **lbf_contents_padding, sticky='nw') 
		settings[f'ch{id}bandwidth'] = StringVar(value=key_from_value(bandwidths, params[f'ch{id}bandwidth']))
		self.bandwidth = Combobox(
				self.frame,
				state='readonly',
				values=list(bandwidths.keys()),
				textvariable=settings[f'ch{id}bandwidth'],
				width=7
				)
		self.bandwidth.grid(column=0, row=8, padx=THIN_PAD, sticky='nw')

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

	def create(self, mode: str, bounds=None, bins=None) -> None:
		self.ax.set_xlabel('Charge (pC)' if mode == 'adc' else 'Delay (ns)')
		self.ax.set_ylabel('Counts')

		if bounds is not None and bounds != self.xlim:
			self.xlim = bounds
			self.ax.set_xlim(bounds)
			update_setting(['histBounds'], [f'{int(bounds[0])},{int(bounds[1])}'])
		else:
			self.ax.set_xlim(self.xlim)
		if not self.ax.patches:  # Only update ylim if histogram is empty
			self.ax.set_ylim(self.ylim)
		yticks = range(0, int(self.ax.get_ylim()[1]) + 5, 5)
		if (self.xlim[1] - self.xlim[0]) == 200:
			xticks = range(int(self.xlim[0]), int(self.xlim[1]) + 20, 20)
		elif (self.xlim[1] - self.xlim[0]) >= 100:
			xticks = range(int(self.xlim[0]), int(self.xlim[1]) + 10, 10)
		else:
			xticks = range(int(self.xlim[0]), int(self.xlim[1]) + 5, 5)
		self.ax.set_xticks(ticks=list(xticks), labels=[f'{lbl}' for lbl in xticks])
		self.ax.set_yticks(ticks=list(yticks), labels=[f'{lbl}' for lbl in yticks])
		self.ax.yaxis.grid(zorder=0)

		if bins is not None and bins != self.bins:
			self.bins = bins
			update_setting(['histBins'], [bins])
			if self.ax.patches:  # Readjust bins if histogram has data
				_ = [bar.remove() for bar in self.ax.patches]
				counts, bins = np.histogram(self.buffer, range=self.xlim, bins=self.bins)
				self.ax.stairs(counts, bins, fill=True, color='tab:blue', zorder=3)

		self.canvas.draw()

	def save(self) -> None:
		figureSavePath = asksaveasfilename(
				initialdir=f'{PV_DIR}/Data',
				filetypes=[('PNG', '*.png'), ('PDF', '*.pdf')]
				)
		plt.savefig(figureSavePath)

	def follow(self):
		"""
		Checks /pickles folder for pickled data coming from applet.
		All tkinter commands must run in mainloop, so data is queued
		to `place_on_canvas` which is outside of follower thread.
		"""
		self.cleanup()
		n = 1
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
				self.place_on_canvas(data=data.x, n=n)
				print(f'follow: Unpickled {pickle_files[-1]}')
				remove(f'pickles/{pickle_files[-1]}')
				n += 1

		self.cleanup()

	def place_on_canvas(self, data: float, n: int) -> None:
		self.queue.get_nowait()
		if self.ax.patches and n % 5 == 0:  # Only update every 5 counts
			_ = [bar.remove() for bar in self.ax.patches]

		self.buffer.append(data)

		if n % 5 == 0:
			counts, bins = np.histogram(self.buffer, range=self.xlim, bins=self.bins)
			self.ax.stairs(counts, bins, fill=True, color='tab:blue', zorder=3)

			yUpperLim = int(self.ax.get_ylim()[1])
			if np.max(counts) > yUpperLim * 0.95:
				if yUpperLim < 50:
					yLimNudge = 5
				elif yUpperLim in range(50, 100):
					yLimNudge = 10
				elif yUpperLim in range(100, 200):
					yLimNudge = 20
				elif yUpperLim in range(200, 500):
					yLimNudge = 25
				elif yUpperLim >= 500:
					yLimNudge = 50
				self.ax.set_ylim(0, yUpperLim + yLimNudge)
				self.ax.set_yticks(
						ticks=list(range(0, yUpperLim + 2 * yLimNudge, yLimNudge)),
						labels=[f'{lbl}' for lbl in range(0, yUpperLim + 2 * yLimNudge, yLimNudge)]
						)
			self.canvas.draw()

		self.queue.task_done()

	def cleanup(self):
		if listdir('pickles'):
			_ = [remove(f'pickles/{p}') for p in listdir('pickles')]

class Job:
	def __init__(self, root: Tk, applet: str, hist: Histogram) -> None:
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
				[PYTHON, f'{self.applet}.py'], stdin=PIPE, stderr=STDOUT
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

def refresh_run_tab(event, tab: Frame) -> None:
	if event.widget.tab('current')['text'] == 'Run':
		tab.update_idletasks()

def on_mode_change(mode: str, hist: Histogram) -> None:
	update_setting(['mode'], [mode])
	hist.create(mode=mode)

def get_timebase_lbl(timebase: int) -> str:
	""" Calculate time interval between captures based on timebase to display on widget """
	interval = int(2 ** timebase / 5e-3 if timebase in range(5) else (timebase - 4) / 1.5625e-4)
	return f'{interval} ps' if interval < 1000 else f'{round(interval / 1000, 1)} ns'

def enable_apply_btn(apply_btn: Button) -> None:
	if apply_btn.instate(['disabled']):
		apply_btn.state(['!disabled'])


def main() -> None:
	""" Reading runtime parameters from .ini file """
	global params  # dict[str, Union[int, float, str]]
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
		pv_data_folder: Path = Path(f'{PV_DIR}/Data').expanduser()
		pv_data_folder.mkdir(exist_ok=True)
	except PermissionError:
		print("Permission Error: cannot write to this location.")
		return

	""" Main window & menu bar """
	root: Tk = RootWindow()

	topFrame = Frame(root, padding=(THIN_PAD, 0, THIN_PAD, THIN_PAD))
	topFrame.grid(column=0, row=0, padx=WIDE_PAD, pady=(WIDE_PAD, 0), sticky='new')
	topFrame.columnconfigure(3, weight=3)

	# Mode selector was moved *after* histogram creation because it needs Histogram instance

	""" Tabs """
	tabsFrame = Frame(root, padding=(THIN_PAD,0,THIN_PAD,THIN_PAD))
	tabsFrame.grid(column=0, row=1, **uniform_padding, sticky='nesw')
	tabControl = Notebook(tabsFrame)
	runTab = Frame(tabControl, padding=(0, 0))
	# tabControl.bind('<<NotebookTabChanged>>', lambda _: refresh_run_tab(event, runTab))
	settingsTab = Frame(tabControl, padding=(0, 0))
	tabControl.add(runTab, text='Run')
	tabControl.add(settingsTab, text='Settings')
	tabControl.pack(expand=1, fill='both')

	""" Run tab """
	summary = Labelframe(runTab, text='Summary')
	summary.grid(column=0, row=0, columnspan=2, **lbf_asym_padding, sticky='nesw')

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
		Label(
			summary, text=ch, background=color if params[f'ch{ch}enabled'] else 'gray63',
			foreground='white' if params[f'ch{ch}enabled'] else 'light gray', anchor='e'
			).grid(column=i, row=0, padx=0 if i == 1 else (THIN_PAD, 0), pady=(WIDE_PAD, 0), sticky='we')
	for i, entry in enumerate(['Range (mV)', 'Analog offset (mV)', 'Coupling', 'Trigger target']):
		Label(summary, text=entry).grid(
				column=0, row=i + 1, padx=(THIN_PAD, 0), pady=(WIDE_PAD if i == 0 else LINE_PAD, 0), sticky='w'
				)
	for i in range(4):
		Label(summary, textvariable=summary_textvar['range'][i], anchor='e').grid(
				column=i + 1, row=1, padx=0 if i == 0 else (THIN_PAD,0), pady=(WIDE_PAD,0), sticky='e'
				)
		Label(summary, textvariable=summary_textvar['analogOffset'][i], anchor='e').grid(
				column=i + 1, row=2, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky='e'
				)
		Label(summary, textvariable=summary_textvar['coupling'][i], anchor='e').grid(
				column=i + 1, row=3, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky='e'
				)
		Label(summary, textvariable=summary_textvar['target'][i], anchor='e').grid(
				column=i + 1, row=4, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky='e'
				)

	h_separator(summary, row=5, columnspan=5)

	Label(summary, text='Timebase').grid(column=0, row=6, padx=(THIN_PAD,0), pady=(WIDE_PAD,0), sticky='w')
	Label(summary, textvariable=summary_textvar['timebase'], anchor='e').grid(
			column=1, row=6, columnspan=4, padx=0, pady=(WIDE_PAD,0), sticky='ew'
			)
	Label(summary, text='Threshold').grid(column=0, row=7, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky='w')
	Label(summary, textvariable=summary_textvar['thresholdmV'], anchor='e').grid(
			column=1, row=7, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky='ew'
			)
	Label(summary, text='Trigger delay').grid(column=0, row=8, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky='w')
	Label(summary, textvariable=summary_textvar['delaySeconds'], anchor='e').grid(
			column=1, row=8, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky='ew'
			)
	Label(summary, text='Auto-trigger after').grid(column=0, row=9, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky='w')
	Label(summary, textvariable=summary_textvar['autoTrigms'], anchor='e').grid(
			column=1, row=9, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky='ew'
			)
	Label(summary, text='Pre-trigger samples').grid(column=0, row=10, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky='w')
	Label(summary, textvariable=summary_textvar['preTrigSamples'], anchor='e').grid(
			column=1, row=10, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky='ew'
			)
	Label(summary, text='Post-trigger samples').grid(column=0, row=11, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky='w')
	Label(summary, textvariable=summary_textvar['postTrigSamples'], anchor='e').grid(
			column=1, row=11, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky='ew'
			)

	h_separator(summary, row=12, columnspan=5)

	logFlag = IntVar(value=params['log'])
	logCheckBox = Checkbutton(
			summary, variable=logFlag, text='Log acquisition',
			onvalue=1, offvalue=0, command=lambda: update_setting(['log'], [logFlag.get()])
			)
	logCheckBox.grid(column=0, row=13, columnspan=4, pady=(WIDE_PAD, 0), sticky='sw')
	plotFlag = IntVar(value=params['plot'])
	plotCheckBox = Checkbutton(
			summary, variable=plotFlag, text='Export figure for each capture',
			onvalue=1, offvalue=0, command=lambda: update_setting(['plot'], [plotFlag.get()])
			)
	plotCheckBox.grid(column=0, row=14, columnspan=4, pady=(LINE_PAD, WIDE_PAD), sticky='ws')

	""" Histogram """
	histogramLbf = Labelframe(runTab, text='Histogram')
	histogramLbf.grid(column=2, row=0, columnspan=6, rowspan=2, **hist_padding, sticky='nesw')
	Label(runTab, text='Bounds:', anchor='w').grid(column=2, row=2, padx=(THIN_PAD, 0), pady=(THIN_PAD, 0), sticky='n')
	histBounds = Slider(
			runTab, width=220, height=40, min_val=-100, max_val=100, init_lis=params['histBounds'],
			step_size=5, show_value=True, removable=False, addable=False
			)
	histBounds.grid(column=3, row=2, pady=0, sticky='n')
	Label(runTab, text='Bins:', anchor=CENTER).grid(column=4, row=2, padx=0, pady=THIN_PAD, sticky='n')
	histBinsVar = IntVar(value=params['histBins'])
	binsSpbx = Spinbox(runTab, from_=50, to=200, textvariable=histBinsVar, width=5, increment=10)
	binsSpbx.grid(column=5, row=2, padx=(MED_PAD, 0), pady=(THIN_PAD, 0), sticky='nw')

	histogram = Histogram(
			root=histogramLbf, xlim=histBounds.get(), ylim=[0, 15], bins=histBinsVar.get()
			)
	Label(topFrame, text='Mode:').grid(column=0, row=0, sticky='w')

	modeVar = StringVar(value=key_from_value(modes, params['mode']))
	modeSelector = OptionMenu(
			topFrame,
			modeVar,
			key_from_value(modes, params['mode']),
			*tuple(modes.keys()),
			command=lambda _: on_mode_change(modes[modeVar.get()], hist=histogram)
			)
	modeSelector.grid(column=1, row=0, padx=WIDE_PAD, sticky='w')

	histogram.create(modes[modeVar.get()])

	histApplyBtn = Button(
			runTab,
			text='Apply',
			width=9,
			command=lambda: histogram.create(modes[modeVar.get()], histBounds.get(), histBinsVar.get())
			)
	histApplyBtn.grid(column=6, row=2, padx=(THIN_PAD, 0), pady=(THIN_PAD, 0), ipady=THIN_PAD, sticky='ne')
	histSaveBtn = Button(runTab, text='Save as...', width=9, command=histogram.save)
	histSaveBtn.grid(column=7, row=2, padx=0, pady=(THIN_PAD, 0), ipady=THIN_PAD, sticky='ne')

	""" Start/Stop job buttons """
	job = Job(root=root, applet=modes[modeVar.get()], hist=histogram)
	startButton = Button(runTab, text='START', command=lambda: job.run(modes[modeVar.get()]))
	startButton.grid(column=0, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky='esw')
	stopButton = Button(runTab, text='STOP', command=job.stop)
	stopButton.grid(column=1, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky='esw')

	""" Settings tab. The 'settings' dictionary will store all the
	temporary changes until the 'Apply' button is pressed, when
	such changes will be written to the config.ini file. """
	global settings
	settings = {}

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
			else:
				new_value = v.get()
			if params[k] != new_value:
				keys.append(k)
				values.append(new_value)
				update = True
		if update:
			update_setting(keys, values)
		applySettingsBtn.state(['disabled'])

	def update_setting(
			keys: list[str],
			new_values: list[Union[str, int, float]]
			) -> None:
		"""
		Compares keys-value pairs in `config.ini` to
		the same pairs given as input, overwrites file as needed
		"""
		with open(f'{PV_DIR}/config.ini', 'r') as ini:
			lines = ini.readlines()
		for k, v in zip(keys, new_values):
			print(f'{k}: {params[k]} -> {v}')
			params[k] = v
			for i, line in enumerate(lines):
				if k in line:
					lines[i] = f'{k} = {v}\n'
					break
		with open(f'{PV_DIR}/config.ini', 'w') as ini:
			ini.writelines(lines)
		print('Config updated.\n')


	""" Trigger settings """
	def target_selection(flags: list[StringVar], targets: StringVar, apply_btn: Button) -> None:
		targets.set(flags[0].get() + flags[1].get() + flags[2].get() + flags[3].get())
		enable_apply_btn(apply_btn)

	trigSettingsLbf = Labelframe(settingsTab, text='Trigger')
	trigSettingsLbf.grid(column=0, row=0, rowspan=2, **lbf_asym_padding, sticky='new')

	Label(trigSettingsLbf, text='Target(s)').grid(column=0, row=0, columnspan=2, **lbf_contents_padding, sticky='nw') 
	settings['target'] = StringVar(value=''.join(params['target']))
	targetFlags = [StringVar(value='') for _ in range(4)]
	targetAChbx = Checkbutton(
			trigSettingsLbf,
			variable=targetFlags[0],
			text='A',
			onvalue='A',
			offvalue='',
			command=lambda: target_selection(targetFlags, settings['target'], applySettingsBtn)
			)
	targetBChbx = Checkbutton(
			trigSettingsLbf,
			variable=targetFlags[1],
			text='B',
			onvalue='B',
			offvalue='',
			command=lambda: target_selection(targetFlags, settings['target'], applySettingsBtn)
			)
	targetCChbx = Checkbutton(
			trigSettingsLbf,
			variable=targetFlags[2],
			text='C',
			onvalue='C',
			offvalue='',
			command=lambda: target_selection(targetFlags, settings['target'], applySettingsBtn)
			)
	targetDChbx = Checkbutton(
			trigSettingsLbf,
			variable=targetFlags[3],
			text='D',
			onvalue='D',
			offvalue='',
			command=lambda: target_selection(targetFlags, settings['target'], applySettingsBtn)
			)
	for i, c in enumerate([targetAChbx, targetBChbx, targetCChbx, targetDChbx]):
		if channelIDs[i] in params['target']:
			c.select()
		c.grid(column=0 if i in (0, 2) else 1, row=1 if i in (0, 1) else 2,
			padx=lbf_contents_padding['padx'], sticky='nw')

	Label(trigSettingsLbf, text='Pre-trigger samples').grid(column=0, row=3, columnspan=2, **lbf_contents_padding, sticky='nw') 
	settings['preTrigSamples'] = IntVar(value=params['preTrigSamples'])
	preTrigSpbx = Spinbox(
			trigSettingsLbf,
			from_=0,
			to=500,
			textvariable=settings['preTrigSamples'],
			width=7,
			increment=1
			)
	preTrigSpbx.grid(column=0, row=4, columnspan=2, padx=lbf_contents_padding['padx'], sticky='nw')

	Label(trigSettingsLbf, text='Post-trigger samples').grid(column=0, row=5, columnspan=2, **lbf_contents_padding, sticky='nw') 
	settings['postTrigSamples'] = IntVar(value=params['postTrigSamples'])
	postTrigSpbx = Spinbox(
			trigSettingsLbf,
			from_=1,
			to=500,
			textvariable=settings['postTrigSamples'],
			width=7,
			increment=1
			)
	postTrigSpbx.grid(column=0, row=6, columnspan=2, padx=lbf_contents_padding['padx'], sticky='nw')

	Label(trigSettingsLbf, text='Timebase').grid(column=0, row=7, columnspan=2, **lbf_contents_padding, sticky='nw') 
	settings['timebase'] = IntVar(value=params['timebase'])
	timebaseSpbx = Spinbox(
			trigSettingsLbf,
			from_=0,
			to=2 ** 32 - 1,
			textvariable=settings['timebase'],
			width=7,
			increment=1
			)
	timebaseSpbx.grid(column=0, row=8, columnspan=2, padx=lbf_contents_padding['padx'], sticky='nw')

	Label(trigSettingsLbf, text='Threshold (mV)').grid(column=0, row=9, columnspan=2, **lbf_contents_padding, sticky='nw') 
	settings['thresholdmV'] = IntVar(value=int(params['thresholdmV']))
	thresholdSpbx = Spinbox(
			trigSettingsLbf,
			from_=-chInputRanges[params[f"ch{params['target'][0]}range"]], # will need a better fix for this
			to=0,
			textvariable=settings['thresholdmV'],
			width=7,
			increment=1
			)
	thresholdSpbx.grid(column=0, row=10, columnspan=2, padx=lbf_contents_padding['padx'], sticky='nw')

	Label(trigSettingsLbf, text='Auto trigger (ms)').grid(column=0, row=11, columnspan=2, **lbf_contents_padding, sticky='nw') 
	settings['autoTrigms'] = IntVar(value=params['autoTrigms'])
	autoTrigSpbx = Spinbox(
			trigSettingsLbf,
			from_=500,
			to=10000,
			textvariable=settings['autoTrigms'],
			width=7,
			increment=100
			)
	autoTrigSpbx.grid(column=0, row=12, columnspan=2, padx=lbf_contents_padding['padx'], sticky='nw')

	Label(trigSettingsLbf, text='Trigger delay (s)').grid(column=0, row=13, columnspan=2, **lbf_contents_padding, sticky='nw') 
	settings['delaySeconds'] = IntVar(value=params['delaySeconds'])
	delaySpbx = Spinbox(
			trigSettingsLbf,
			from_=0,
			to=10,
			textvariable=settings['delaySeconds'],
			width=7,
			increment=1
			)
	delaySpbx.grid(column=0, row=14, columnspan=2, padx=lbf_contents_padding['padx'], sticky='nw')

	""" Channels settings """
	chASettings = ChannelSettings(settingsTab, id='A', column=1)
	chBSettings = ChannelSettings(settingsTab, id='B', column=2)
	chCSettings = ChannelSettings(settingsTab, id='C', column=3)
	chDSettings = ChannelSettings(settingsTab, id='D', column=4)

	""" File settings """
	fileSettings = TabLabelframe(
			settingsTab, title='File settings', col=1, row=1, size=(3, 4), cspan=4, padding=lbf_asym_padding_no_top
			)
	fileSettings.add_optionmenu(
			id='dataFileType', prompt='Save data as:', vtype='str', options=dataFileTypes
			)
	settings['dformat'] = fileSettings.get_raw('dataFileType')

	""" Apply settings button """
	applySettingsBtn = Button(
			settingsTab, text='Apply', takefocus=False, command=lambda: apply_changes(settings)
			)
	applySettingsBtn.state(['disabled'])  # Will only be enabled if a setting is changed
	applySettingsBtn.grid(column=4, row=2, padx=0, pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky='e')

	for variable in settings.values():  # Enable Apply button if any variable is changed
		variable.trace_add('write', lambda var, index, mode: enable_apply_btn(applySettingsBtn))

# 	for cs in [chASettings, chBSettings, chCSettings, chDSettings]:
# 		cs.enabled.configure(command=lambda: enable_apply_btn(applySettingsBtn))
# 		cs.chRange.bind('<<ComboboxSelected>>', lambda _: enable_apply_btn(applySettingsBtn))
# 		cs.coupling.bind('<<ComboboxSelected>>', lambda _: enable_apply_btn(applySettingsBtn))
# 		settings[f'ch{cs.id}analogOffset'].trace_add(
# 				'write', lambda var, index, mode: enable_apply_btn(applySettingsBtn)
# 				)
# 		cs.coupling.bind('<<ComboboxSelected>>', lambda _: enable_apply_btn(applySettingsBtn))

	root.center()
	root.mainloop()

if __name__ == '__main__':
	main()
