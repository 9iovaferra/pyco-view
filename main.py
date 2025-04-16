""" Copyright (C) 2019 Pico Technology Ltd. """
""" tkSliderWidget Copyright (c) 2020, Mengxun Li """
from tkinter import *
from tkinter import ttk
from pycoviewlib.functions import parse_config, key_from_value
from pycoviewlib.constants import *
from pycoviewlib.tkSliderWidget.tkSliderWidget import Slider
from matplotlib.figure import Figure 
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from threading import Thread
from subprocess import Popen, PIPE, STDOUT
from os import path, system
from typing import Union
from webbrowser import open_new

python = path.expanduser("~/.venv/bin/python3")

def placeholder():
	print("This command definitely does something (trust me).")

class RootWindow(Tk):
	def __init__(self, *args, **kwargs):
		Tk.__init__(self, *args, **kwargs)
		self.after(0, self.hide())
		self.title("PycoView")
		self.menu_bar = Menu(self)
		self.config(menu=self.menu_bar)
		self.file_menu = Menu(self.menu_bar, tearoff=0)
		self.menu_bar.add_cascade(menu=self.file_menu, label="File")
		self.file_menu.add_command(label="Open data folder", command=self.show_data_folder)
		self.help_menu = Menu(self.menu_bar, tearoff=0)
		self.menu_bar.add_cascade(menu=self.help_menu, label="Help")
		self.help_menu.add_command(label="About", command=self.open_about_window)

	def hide(self, target=None) -> None:
		""" Hide window until widgets are drawn to avoid visual glitch """
		if target is None:
			target = self
		self.attributes("-alpha", 0.0)

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
		target.geometry(f"+{x}+{y}")
		target.attributes("-alpha", 1.0)

	def show_data_folder(self) -> None:
		home = path.expanduser("~")
		datapath = path.realpath(home + "/Documents/pyco-view/Data")
		system(f"xdg-open {datapath}")

	def open_about_window(self) -> None:
		about = Toplevel()
		about.after(0, about.hide())
		about.title("About")
		title = ttk.Label(about, text="PycoView", font=18, anchor=CENTER)
		title.grid(column=0, row=0, **uniform_padding, sticky=N+W+E)
		app_version = ttk.Label(about, text="v0.57 (pre-alpha)", anchor=CENTER)
		app_version.grid(column=0, row=1, **uniform_padding, sticky=N+W+E)
		link = ttk.Label(about, text="Github Repository", foreground="blue", cursor="hand2", anchor=CENTER)
		link.grid(column=0, row=2, **uniform_padding, sticky=S+W+E)
		link.bind("<Button-1>", lambda _: open_new("https://github.com/9iovaferra/pyco-view"))
		self.center(target=about)

class ChannelSettings():
	def __init__(self, parent, ch_id: str, column: int):
		self.chFrame = ttk.Labelframe(parent, text=f"Channel {ch_id}")
		self.chFrame.grid(column=column, row=0, **asym_left_padding, sticky=W+E+N)

		settings[f"ch{ch_id}enabled"] = IntVar(value=params[f"ch{ch_id}enabled"])
		self.enabled = Checkbutton(
				self.chFrame,
				variable=settings[f"ch{ch_id}enabled"],
				text="Enabled",
				onvalue=1,
				offvalue=0,
				command=lambda : update_setting([f"ch{ch_id}enabled"], [settings[f"ch{ch_id}enabled"].get()])
				)
		self.enabled.grid(column=0, row=0, pady=(THIN_PAD,0), sticky=W+N)

		ttk.Label(self.chFrame, text="Range (±mV)").grid(column=0, row=1, **lbf_contents_padding, sticky=W+N) 
		settings[f"ch{ch_id}range"] = IntVar(value=chInputRanges[params[f"ch{ch_id}range"]])
		self.chRange = ttk.Combobox(
				self.chFrame,
				state="readonly",
				values=chInputRanges,
				textvariable=settings[f"ch{ch_id}range"],
				width=7
				)
		self.chRange.grid(column=0, row=2, padx=THIN_PAD, sticky=W+N)

		ttk.Label(self.chFrame, text="Coupling").grid(column=0, row=3, **lbf_contents_padding, sticky=W+N) 
		settings[f"ch{ch_id}coupling"] = StringVar(value=key_from_value(couplings, params[f"ch{ch_id}coupling"])[0])
		self.coupling = ttk.Combobox(
				self.chFrame,
				state="readonly",
				values=list(couplings.keys()),
				textvariable=settings[f"ch{ch_id}coupling"],
				width=7
				)
		self.coupling.grid(column=0, row=4, padx=THIN_PAD, sticky=W+N)

		ttk.Label(self.chFrame, text="Analogue offset (mV)").grid(column=0, row=5, **lbf_contents_padding, sticky=W+N) 
		settings[f"ch{ch_id}analogOffset"] = DoubleVar(value=params[f"ch{ch_id}analogOffset"] * 1000)
		self.analogOffset = Spinbox(
				self.chFrame,
				from_=0,
				to=settings[f"ch{ch_id}range"].get(),
				textvariable=settings[f"ch{ch_id}analogOffset"],
				width=7,
				increment=1
				)
		self.analogOffset.grid(column=0, row=6, padx=THIN_PAD, sticky=W+N)

		ttk.Label(self.chFrame, text="Bandwidth").grid(column=0, row=7, **lbf_contents_padding, sticky=W+N) 
		settings[f"ch{ch_id}bandwidth"] = StringVar(value=key_from_value(bandwidths, params[f"ch{ch_id}bandwidth"])[0])
		self.bandwidth = ttk.Combobox(
				self.chFrame,
				state="readonly",
				values=list(bandwidths.keys()),
				textvariable=settings[f"ch{ch_id}bandwidth"],
				width=7
				)
		self.bandwidth.grid(column=0, row=8, padx=THIN_PAD, sticky=W+N)

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
	keys = []
	values = []
	for k, v in settings.items():
		if "mode" in k:
			new_value = modes[v.get()]
		elif "range" in k:
			new_value = chInputRanges.index(v.get())
		elif "coupling" in k:
			new_value = couplings[v.get()]
		elif "analogOffset" in k:
			new_value = v.get() / 1000
		elif "bandwidth" in k:
			new_value = bandwidths[v.get()]
		else:
			new_value = v.get()
		if params[k] != new_value:
			keys.append(k)
			values.append(new_value)
	update_setting(keys, values)

def update_setting(
		key: list[str],
		new_value: list[Union[str, int, float]]
		) -> None:
	ini = open("config.ini", "r")
	lines = ini.readlines()
	ini.close()
	for k, v in zip(key, new_value):
		print(f"{k}: {params[k]} -> {v}")
		params[k] = v
		for i in range(len(lines)):
			if k in lines[i]:
				lines[i] = f"{k} = {v}\n"
				break
	ini = open("config.ini", "w")
	ini.writelines(lines)
	ini.close()
	print("Config updated.\n")

class Histogram():
	def __init__(self, parent, xlim: list[int], ylim: list[int], bins: int):
		self.fig = Figure(figsize=(6,4))
		self.fig.patch.set_visible(False)
		self.hist = self.fig.add_subplot()
		self.hist.set_facecolor("none")
		self.hist.patch.set_visible(False)
		self.hist.set_xlabel("Delay (ns)")
		self.hist.set_ylabel("Counts")
		self.fig.tight_layout()
		self.parent = parent
		self.xlim = xlim
		self.ylim = ylim
		self.bins = bins

	def draw(self) -> None:
		self.hist.set_xlim(self.xlim)
		self.hist.set_ylim(self.ylim)
		self.canvas = FigureCanvasTkAgg(self.fig, master=self.parent)
		self.canvas.draw()
		self.canvas.get_tk_widget().grid(column=0, row=0, padx=THIN_PAD, pady=THIN_PAD, sticky=W+E+N+S)

class Job:
	def __init__(self, root: Tk, applet: str):
		self.root = root
		self.applet = applet

	def run(self):
		self.__init__(self.root, modes[modeVar.get()])
		self.thread = Thread(target=self.start)
		self.thread.start()
		""" Exit subprocess if GUI is closed """
		self.root.protocol("WM_DELETE_WINDOW", self.kill)
	
	def start(self):
		self.stopped = False
		print(f"Running {self.applet}.py...")
		self.proc = Popen([python, f"{self.applet}.py"], stdin=PIPE)
	
	def stop(self):
		""" Stop subprocess and quit GUI.
		Avoid killing subprocess more than once. """
		if self.stopped:
			print("No process to stop.")
			return
		self.stopped = True
		print(f"Stopping acquisition in '{self.applet}.py'.")
		out, err = self.proc.communicate(input=b"q\n")
		self.thread.join()
		
		# kill subprocess if it hasn't exited after a countdown	
		# self.kill_after(countdown=5)
	
	def kill(self):
		if not self.stopped:
			self.stop()
		self.root.destroy()
	
	# def kill_after(self, countdown: int):
	# 	if self.proc.poll() is None: # subprocess hasn't exited yet
	# 		countdown -= 1
	# 		if countdown < 0:
	# 			self.proc.kill()
	# 		else:
	# 			self.root.after(1000, kill_after, countdown)
	# 			return
	# 	self.proc.wait() # wait for the subprocess' exit


""" Reading runtime parameters from .ini file """
params = parse_config()

offsets = []
ranges = []
for k, v in params.items():
	if "Offset" in k:
		offsets.append(v)
	elif "range" in k:
		ranges.append(chInputRanges[v])

""" Padding presets (frame padding: 'left top right bottom') """
THIN_PAD = 6
LINE_PAD = int(THIN_PAD / 3)
MED_PAD = int((THIN_PAD * 4) / 3)
WIDE_PAD = 2 * THIN_PAD
uniform_padding = {"padx": WIDE_PAD, "pady": WIDE_PAD, "ipadx": THIN_PAD, "ipady": THIN_PAD}
asym_left_padding = {"padx": (WIDE_PAD,0), "pady": WIDE_PAD, "ipadx": THIN_PAD, "ipady": THIN_PAD}
hist_padding = {"padx": (WIDE_PAD,0), "pady": (WIDE_PAD,0), "ipadx": 0, "ipady": 0}
lbf_padding = {"padx": WIDE_PAD, "pady": WIDE_PAD, "ipadx": THIN_PAD, "ipady": THIN_PAD}
lbf_contents_padding = {"padx": (THIN_PAD,0), "pady": (MED_PAD,2)} 

""" Main window & menu bar """
root = RootWindow()

topFrame = ttk.Frame(root, padding=(THIN_PAD,0,THIN_PAD,THIN_PAD))
topFrame.grid(column=0, row=0, padx=WIDE_PAD, pady=(WIDE_PAD,0), sticky=N+W+E)
topFrame.columnconfigure(3, weight=3)

ttk.Label(topFrame, text="Mode:").grid(column=0, row=0, sticky=W)
modeVar = StringVar(value=key_from_value(modes, params["mode"])[0])
modeSelector = ttk.OptionMenu(
		topFrame,
		modeVar,
		key_from_value(modes, params["mode"])[0],
		*tuple(modes.keys()),
		command=lambda _: update_setting(["mode"], [modes[modeVar.get()]])
		)
modeSelector.grid(column=1, row=0, padx=WIDE_PAD, sticky=W)

""" Tabs """
tabsFrame = ttk.Frame(root, padding=(THIN_PAD,0,THIN_PAD,THIN_PAD))
tabsFrame.grid(column=0, row=1, **uniform_padding, sticky=W+E+N+S)
tabControl = ttk.Notebook(tabsFrame)
runTab = ttk.Frame(tabControl, padding=(0,0))
settingsTab = ttk.Frame(tabControl, padding=(0,0))
tabControl.add(runTab, text="Run")
tabControl.add(settingsTab, text="Settings")
tabControl.pack(expand=1, fill="both")

""" Run tab """
summary = ttk.Labelframe(runTab, text="Summary")
summary.grid(column=0, row=0, columnspan=2, **asym_left_padding, sticky=W+E+N+S)

""" Summary labelframe contents """
for i, ch, color in zip(range(4), channelIDs, ["blue", "red", "green3", "gold"]):
	ttk.Label(summary, text=ch, background=color, foreground="white", anchor=E).grid(
			column=i+1, row=0, padx=0 if i == 0 else (THIN_PAD,0), pady=(WIDE_PAD,0), sticky=W+E
			)
for i, entry in enumerate(["Range (±mV)", "Analog offset (mV)", "Coupling (Ω)", "Threshold (mV)"]):
	ttk.Label(summary, text=entry).grid(
			column=0, row=i+1, padx=(THIN_PAD,0), pady=(WIDE_PAD if i == 0 else LINE_PAD,0), sticky=W
			)
for i, entry in enumerate(ranges):
	ttk.Label(summary, text=entry, anchor=E).grid(
			column=i+1, row=1, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky=E
			)
for i, entry in enumerate(offsets):
	ttk.Label(summary, text=int(entry * 1000), anchor=E).grid(
			column=i+1, row=2, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky=E
			)
for i, entry in enumerate([params["chAcoupling"], params["chBcoupling"], params["chCcoupling"], params["chDcoupling"]]):
	ttk.Label(summary, text=entry, anchor=E).grid(
			column=i+1, row=3, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky=E
			)
for i, ch in enumerate(channelIDs):
	ttk.Label(summary, text=f"{params['thresholdmV']:.0f}" if i == channelIDs.index(params["target"]) else "None", anchor=E).grid(
			column=i+1, row=4, padx=0 if i == 0 else (THIN_PAD,0), pady=(LINE_PAD,0), sticky=E
			)

h_separator(summary, row=5, columnspan=5)

ttk.Label(summary, text="Timebase").grid(column=0, row=6, padx=(THIN_PAD,0), pady=(WIDE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{timebases[params['timebase']]}", anchor=E).grid(
		column=1, row=6, columnspan=4, padx=0, pady=(WIDE_PAD,0), sticky=W+E
		)
ttk.Label(summary, text="Trigger delay").grid(column=0, row=7, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{params['delaySeconds']} s", anchor=E).grid(
		column=1, row=7, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky=W+E
		)
ttk.Label(summary, text="Auto-trigger after").grid(column=0, row=8, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{params['autoTrigms']} ms", anchor=E).grid(
		column=1, row=8, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky=W+E
		)
ttk.Label(summary, text="Pre-trigger samples").grid(column=0, row=9, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{params['preTrigSamples']}", anchor=E).grid(
		column=1, row=9, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky=W+E
		)
ttk.Label(summary, text="Post-trigger samples").grid(column=0, row=10, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{params['postTrigSamples']}", anchor=E).grid(
		column=1, row=10, columnspan=4, padx=0, pady=(LINE_PAD,0), sticky=W+E
		)

h_separator(summary, row=11, columnspan=5)

logFlag = IntVar(value=params["log"])
logCheckBox = Checkbutton(
		summary, variable=logFlag, text="Log acquisition",
		onvalue=1, offvalue=0, command=lambda : update_setting(["log"], [logFlag.get()])
		)
logCheckBox.grid(column=0, row=12, columnspan=4, pady=(WIDE_PAD,0), sticky=W+S)
plotFlag = IntVar(value=params["plot"])
plotCheckBox = Checkbutton(
		summary, variable=plotFlag, text="Export figure for each capture",
		onvalue=1, offvalue=0, command=lambda : update_setting(["plot"], [plotFlag.get()])
		)
plotCheckBox.grid(column=0, row=13, columnspan=4, pady=(LINE_PAD,WIDE_PAD), sticky=W+S)

acquisition = Job(root=root, applet=modes[modeVar.get()])
startButton = ttk.Button(runTab, text="START", command=acquisition.run)
startButton.grid(column=0, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=W+E+S)
stopButton = ttk.Button(runTab, text="STOP", command=acquisition.stop)
stopButton.grid(column=1, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=W+E+S)

histogramLbf = ttk.Labelframe(runTab, text="Histogram")
histogramLbf.grid(column=2, row=0, columnspan=7, rowspan=2, **hist_padding, sticky=W+E+N+S)
ttk.Label(runTab, text="Bounds:", anchor=W).grid(column=2, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=N)
rangeSlider = Slider(runTab,
				width=200,
				height=40,
				min_val=0,
				max_val=100,
				init_lis=params["histBounds"],
				step_size=1,
				show_value=True,
				removable=False,
				addable=False
				)
print(rangeSlider.getValues())
rangeSlider.grid(column=3, row=2, padx=0, pady=0, sticky=N)
ttk.Label(runTab, text="Bins:", anchor=CENTER).grid(column=4, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=N)
histBinsVar = IntVar(value=params["histBins"])
binsSpbx = Spinbox(runTab, from_=50, to=200, textvariable=histBinsVar, width=5, increment=10)
binsSpbx.grid(column=5, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=N+W)
histogram = Histogram(parent=histogramLbf, xlim=rangeSlider.getValues(), ylim=[0, 250], bins=histBinsVar.get())
histogram.draw()
applyButton = Button(runTab, text="Apply", width=3, height=1, command=histogram.draw)
applyButton.grid(column=6, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=E+N)
resetButton = Button(runTab, text="Reset", width=3, height=1, command=placeholder)
resetButton.grid(column=7, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=E+N)
saveButton = Button(runTab, text="Save", width=3, height=1, command=placeholder)
saveButton.grid(column=8, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=E+N)

""" Settings tab. The 'settings' dictionary will store all the
temporary changes until the 'Apply' button is pressed, when
such changes will be written to the config.ini file. """
settings = {}

""" Trigger settings """
triggerSettings = ttk.Labelframe(settingsTab, text="Trigger")
triggerSettings.grid(column=0, row=0, rowspan=2, **asym_left_padding, sticky=W+E+N)

ttk.Label(triggerSettings, text="Target(s)").grid(column=0, row=0, columnspan=2, **lbf_contents_padding, sticky=W+N) 
settings["target"] = StringVar(value="")
targetFlags = [StringVar(value="") for _ in range(4)]
targetAChbx = Checkbutton(
		triggerSettings,
		variable=targetFlags[0],
		text="A",
		onvalue="A",
		offvalue="",
		command=lambda : target_selection(targetFlags, settings["target"])
		)
targetBChbx = Checkbutton(
		triggerSettings,
		variable=targetFlags[1],
		text="B",
		onvalue="B",
		offvalue="",
		command=lambda : target_selection(targetFlags, settings["target"])
		)
targetCChbx = Checkbutton(
		triggerSettings,
		variable=targetFlags[2],
		text="C",
		onvalue="C",
		offvalue="",
		command=lambda : target_selection(targetFlags, settings["target"])
		)
targetDChbx = Checkbutton(
		triggerSettings,
		variable=targetFlags[3],
		text="D",
		onvalue="D",
		offvalue="",
		command=lambda : target_selection(targetFlags, settings["target"])
		)
for i, c in enumerate([targetAChbx, targetBChbx, targetCChbx, targetDChbx]):
	c.grid(column=0 if i <= 1 else 1, row=i+1 if i <= 1 else i-1,
		padx=lbf_contents_padding["padx"], sticky=W+N)

# settings["target"] = StringVar(value=params["target"])
# targetSelector = ttk.Combobox(
# 		triggerSettings,
# 		state="readonly",
# 		values=channelIDs,
# 		textvariable=settings["target"],
# 		width=7
# 		)
# targetSelector.grid(column=0, row=1, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Pre-trigger samples").grid(column=0, row=3, columnspan=2, **lbf_contents_padding, sticky=W+N) 
settings["preTrigSamples"] = IntVar(value=params["preTrigSamples"])
preTrigSpbx = Spinbox(
		triggerSettings,
		from_=0,
		to=500,
		textvariable=settings["preTrigSamples"],
		width=7,
		increment=1
		)
preTrigSpbx.grid(column=0, row=4, columnspan=2, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Post-trigger samples").grid(column=0, row=5, columnspan=2, **lbf_contents_padding, sticky=W+N) 
settings["postTrigSamples"] = IntVar(value=params["postTrigSamples"])
postTrigSpbx = Spinbox(
		triggerSettings,
		from_=1,
		to=500,
		textvariable=settings["postTrigSamples"],
		width=7,
		increment=1
		)
postTrigSpbx.grid(column=0, row=6, columnspan=2, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Timebase").grid(column=0, row=7, columnspan=2, **lbf_contents_padding, sticky=W+N) 
settings["timebase"] = IntVar(value=params["timebase"])
timebaseSelector = ttk.Combobox(
		triggerSettings,
		state="readonly",
		values=[0, 1, 2, 3, 4],
		textvariable=settings["timebase"],
		width=7
		)
timebaseSelector.grid(column=0, row=8, columnspan=2, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Threshold (mV)").grid(column=0, row=9, columnspan=2, **lbf_contents_padding, sticky=W+N) 
settings["thresholdmV"] = IntVar(value=int(params["thresholdmV"]))
thresholdSpbx = Spinbox(
		triggerSettings,
		from_=-chInputRanges[params[f"ch{params['target']}range"]],
		to=0,
		textvariable=settings["thresholdmV"],
		width=7,
		increment=1
		)
thresholdSpbx.grid(column=0, row=10, columnspan=2, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Auto trigger (ms)").grid(column=0, row=11, columnspan=2, **lbf_contents_padding, sticky=W+N) 
settings["autoTrigms"] = IntVar(value=params["autoTrigms"])
autoTrigSpbx = Spinbox(
		triggerSettings,
		from_=500,
		to=10000,
		textvariable=settings["autoTrigms"],
		width=7,
		increment=100
		)
autoTrigSpbx.grid(column=0, row=12, columnspan=2, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Trigger delay (s)").grid(column=0, row=13, columnspan=2, **lbf_contents_padding, sticky=W+N) 
settings["delaySeconds"] = IntVar(value=params["delaySeconds"])
delaySpbx = Spinbox(
		triggerSettings,
		from_=0,
		to=10,
		textvariable=settings["delaySeconds"],
		width=7,
		increment=1
		)
delaySpbx.grid(column=0, row=14, columnspan=2, padx=lbf_contents_padding["padx"], sticky=W+N)

""" Channels settings """
chASettings = ChannelSettings(settingsTab, ch_id="A", column=1)
chBSettings = ChannelSettings(settingsTab, ch_id="B", column=2)
chCSettings = ChannelSettings(settingsTab, ch_id="C", column=3)
chDSettings = ChannelSettings(settingsTab, ch_id="D", column=4)

applySettingsBtn = ttk.Button(settingsTab, text="Apply", command=lambda : apply_changes(settings))
applySettingsBtn.grid(column=4, row=1, padx=0, pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=E)

root.center()
root.mainloop()
