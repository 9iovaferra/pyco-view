""" tkSliderWidget Copyright (c) 2020, Mengxun Li """
from tkinter import *
from tkinter import ttk
from pycoviewlib.functions import parse_config
from pycoviewlib.constants import *
from matplotlib.figure import Figure 
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from pycoviewlib.tkSliderWidget.tkSliderWidget import Slider
from typing import Union

def placeholder():
	print("This command definitely does something (trust me).")

class RootWindow(Tk):
	def __init__(self, *args, **kwargs):
		Tk.__init__(self, *args, **kwargs)
		self.title("PycoView")
		self.withdraw()
		self.after(0, self.deiconify)

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
				command=lambda : update_setting(f"ch{ch_id}enabled", self.enabledFlag.get())
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

def apply_changes(settings: dict) -> None:
	keys = []
	values = []
	for k, v in settings.items():
		if "range" in k:
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
		key: str | list[str],
		new_value: Union[str, int, float] | list[Union[str, int, float]]
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

# def mv2adc(thresholdmV: int) -> None:
# 	settings["thresholdADC"] = int(
# 			(thresholdmV + params[f"ch{params['target']}analogOffset"] * 1000) \
# 			/ chInputRanges[params[f"ch{params['target']}range"]] * maxADC
# 			)
# 	print(settings["thresholdADC"])

def key_from_value(dictionary: dict, value: int) -> list[str]:
	return [k for k, v in dictionary.items() if v == value]


""" Reading runtime parameters from .ini file """
params = parse_config()

offsets = []
ranges = []
for k, v in params.items():
	if "Offset" in k:
		offsets.append(v)
	elif "range" in k:
		ranges.append(chInputRanges[v])
# params["thresholdmV"] = []
# for t, o, r in zip(params["target"], offsets, ranges):
# 	params["thresholdmV"].append((params["thresholdADC"] * r) / maxADC - (o * 1000) if t == 1 else None)

# params["thresholdmV"] = int(
# 		params["thresholdADC"] / maxADC * chInputRanges[params[f"ch{params['target']}range"]] \
# 				- (params[f"ch{params['target']}analogOffset"] * 1000)
# 		)

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

""" Main window & frame """
root = RootWindow()

topFrame = ttk.Frame(root, padding=(THIN_PAD,0,THIN_PAD,THIN_PAD))
topFrame.grid(column=0, row=0, padx=WIDE_PAD, pady=(WIDE_PAD,0), sticky=N+W+E)
topFrame.columnconfigure(3, weight=3)

ttk.Label(topFrame, text="Mode:").grid(column=0, row=0, sticky=W)
modeVar = StringVar(topFrame, params["mode"])
modeSelector = ttk.Combobox(topFrame, state="readonly", width=10, values=modes, textvariable=modeVar)
modeSelector.grid(column=1, row=0, padx=WIDE_PAD, sticky=W)

ttk.Button(topFrame, text="Update", command=lambda : update_setting(key="mode", new_value=modeVar.get())).grid(column=2, row=0, sticky=W)

ttk.Label(topFrame, text="v1.00", anchor=E).grid(column=3, row=0, sticky=E)

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

for i, ch, color in zip(range(4), channelIDs, ["blue", "red", "green3", "gold"]):
	ttk.Label(summary, text=ch, foreground=color, anchor=E).grid(
			column=i+1, row=0, padx=(THIN_PAD,0) if i <= 2 else THIN_PAD, pady=(WIDE_PAD,0), sticky=E
			)
for i, entry in enumerate(["Range (±mV)", "Analog offset (mV)", "Coupling (Ω)", "Threshold (mV)"]):
	ttk.Label(summary, text=entry).grid(
			column=0, row=i+1, padx=(THIN_PAD,0), pady=(WIDE_PAD if i == 0 else LINE_PAD,0), sticky=W
			)
for i, entry in enumerate(ranges):
	ttk.Label(summary, text=entry, anchor=E).grid(
			column=i+1, row=1, padx=(THIN_PAD,0) if i == 0 else 0, pady=(LINE_PAD,0), sticky=E
			)
for i, entry in enumerate(offsets):
	ttk.Label(summary, text=int(entry * 1000), anchor=E).grid(
			column=i+1, row=2, padx=(THIN_PAD,0) if i == 0 else 0, pady=(LINE_PAD,0), sticky=E
			)
for i, entry in enumerate([params["chAcoupling"], params["chBcoupling"], params["chCcoupling"], params["chDcoupling"]]):
	ttk.Label(summary, text=entry, anchor=E).grid(
			column=i+1, row=3, padx=(THIN_PAD,0) if i == 0 else 0, pady=(LINE_PAD,0), sticky=E
			)
for i, ch in enumerate(channelIDs):
	ttk.Label(summary, text=f"{params['thresholdmV']:.0f}" if i == channelIDs.index(params["target"]) else "-", anchor=E).grid(
			column=i+1, row=4, padx=(THIN_PAD,0) if i == 0 else 0, pady=(LINE_PAD,0), sticky=E
			)
# ttk.Label(summary, text=f"{chInputRanges[params['chRange']]}", anchor=E).grid(
# 		column=1, row=1, padx=(0,THIN_PAD), pady=(WIDE_PAD,0), sticky=W+E
# 		)
# ttk.Label(summary, text=f"{params['analogOffset'] * 1000}", anchor=E).grid(
# 		column=1, row=2, padx=(0,THIN_PAD), pady=(LINE_PAD,0), sticky=W+E
# 		)
# ttk.Label(summary, text=f"{params['terminalResist']}", anchor=E).grid(
# 		column=1, row=3, padx=(0,THIN_PAD), pady=(LINE_PAD,0), sticky=W+E
# 		)
# ttk.Label(summary, text=f"{thresholdmV:.0f}", anchor=E).grid(
# 		column=1, row=4, padx=(0,THIN_PAD), pady=(LINE_PAD,0), sticky=W+E
# 		)

h_separator(summary, row=5, columnspan=5)

ttk.Label(summary, text="Timebase").grid(column=0, row=6, padx=(THIN_PAD,0), pady=(WIDE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{timebases[params['timebase']]}", anchor=E).grid(
		column=1, row=6, columnspan=4, padx=(0,THIN_PAD), pady=(WIDE_PAD,0), sticky=W+E
		)
ttk.Label(summary, text="Trigger delay").grid(column=0, row=7, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{params['delaySeconds']} s", anchor=E).grid(
		column=1, row=7, columnspan=4, padx=(0,THIN_PAD), pady=(LINE_PAD,0), sticky=W+E
		)
ttk.Label(summary, text="Auto-trigger").grid(column=0, row=8, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{params['autoTrigms']} ms", anchor=E).grid(
		column=1, row=8, columnspan=4, padx=(0,THIN_PAD), pady=(LINE_PAD,0), sticky=W+E
		)
ttk.Label(summary, text="Pre-trigger samples").grid(column=0, row=9, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{params['preTrigSamples']}", anchor=E).grid(
		column=1, row=9, columnspan=4, padx=(0,THIN_PAD), pady=(LINE_PAD,0), sticky=W+E
		)
ttk.Label(summary, text="Post-trigger samples").grid(column=0, row=10, padx=(THIN_PAD,0), pady=(LINE_PAD,0), sticky=W)
ttk.Label(summary, text=f"{params['postTrigSamples']}", anchor=E).grid(
		column=1, row=10, columnspan=4, padx=(0,THIN_PAD), pady=(LINE_PAD,0), sticky=W+E
		)

h_separator(summary, row=11, columnspan=5)

logFlag = IntVar(value=params["log"]) # read from config file
logCheckBox = Checkbutton(
		summary, variable=logFlag, text="Log acquisition",
		onvalue=1, offvalue=0, command=lambda : update_setting(key="log", new_value=logFlag.get())
		)
logCheckBox.grid(column=0, row=12, columnspan=4, pady=(WIDE_PAD,0), sticky=W+S)

startButton = ttk.Button(runTab, text="START", command=placeholder)
startButton.grid(column=0, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=W+S)
stopButton = ttk.Button(runTab, text="STOP", command=placeholder)
stopButton.grid(column=1, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=E+S)

histogramLbf = ttk.Labelframe(runTab, text="Histogram")
histogramLbf.grid(column=2, row=0, columnspan=7, rowspan=2, **hist_padding, sticky=W+E+N+S)
ttk.Label(runTab, text="Bounds:", anchor=W).grid(column=2, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=N)
rangeSlider = Slider(runTab,
				width=200,
				height=40,
				min_val=0,
				max_val=100,
				init_lis=[0, 80],
				step_size=1,
				show_value=True,
				removable=False,
				addable=False
				)
rangeSlider.grid(column=3, row=2, padx=0, pady=0, sticky=N)
ttk.Label(runTab, text="Bins:", anchor=CENTER).grid(column=4, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=N)
histBinsVar = IntVar(value=100)
binsSpbx = Spinbox(runTab, from_=50, to=200, textvariable=histBinsVar, width=5, increment=10)
binsSpbx.grid(column=5, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=N+W)
histogram = Histogram(parent=histogramLbf, xlim=[0, 80], ylim=[0, 250], bins=histBinsVar.get())
histogram.draw()
applyButton = Button(runTab, text="Apply", width=3, height=1, command=histogram.draw)
applyButton.grid(column=6, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=E+N)
resetButton = Button(runTab, text="Reset", width=3, height=1, command=placeholder)
resetButton.grid(column=7, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=E+N)
saveButton = Button(runTab, text="Save", width=3, height=1, command=placeholder)
saveButton.grid(column=8, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=E+N)

""" Settings tab """
settings = {}

""" Trigger settings """
triggerSettings = ttk.Labelframe(settingsTab, text="Trigger")
triggerSettings.grid(column=0, row=0, rowspan=2, **asym_left_padding, sticky=W+E+N)

# def return_target(list_: tuple[int]) -> str:
# 	for flag, ch in zip(list_, channelIDs):
# 		if flag == 1:
# 			return ch

ttk.Label(triggerSettings, text="Target").grid(column=0, row=0, **lbf_contents_padding, sticky=W+N) 
settings["target"] = StringVar(root, params["target"])
targetCbx = ttk.Combobox(triggerSettings, state="readonly", values=channelIDs, textvariable=settings["target"], width=7)
targetCbx.grid(column=0, row=1, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Pre-trigger samples").grid(column=0, row=2, **lbf_contents_padding, sticky=W+N) 
settings["preTrigSamples"] = IntVar(value=params["preTrigSamples"])
preTrigSpbx = Spinbox(
		triggerSettings,
		from_=0,
		to=500,
		textvariable=settings["preTrigSamples"],
		width=7,
		increment=1
		)
preTrigSpbx.grid(column=0, row=3, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Post-trigger samples").grid(column=0, row=4, **lbf_contents_padding, sticky=W+N) 
settings["postTrigSamples"] = IntVar(value=params["postTrigSamples"])
postTrigSpbx = Spinbox(
		triggerSettings,
		from_=1,
		to=500,
		textvariable=settings["postTrigSamples"],
		width=7,
		increment=1
		)
postTrigSpbx.grid(column=0, row=5, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Timebase").grid(column=0, row=6, **lbf_contents_padding, sticky=W+N) 
settings["timebase"] = IntVar(value=params["timebase"])
timebaseCbx = ttk.Combobox(triggerSettings, state="readonly", values=[0, 1, 2, 3, 4], textvariable=settings["timebase"], width=7)
timebaseCbx.grid(column=0, row=7, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Threshold (mV)").grid(column=0, row=8, **lbf_contents_padding, sticky=W+N) 
settings["thresholdmV"] = IntVar(value=int(params["thresholdmV"]))
thresholdSpbx = Spinbox(
		triggerSettings,
		from_=-chInputRanges[params[f"ch{params['target']}range"]],
		to=0,
		textvariable=settings["thresholdmV"],
		width=7,
		increment=1
		)
thresholdSpbx.grid(column=0, row=9, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Auto trigger (ms)").grid(column=0, row=10, **lbf_contents_padding, sticky=W+N) 
settings["autoTrigms"] = IntVar(value=params["autoTrigms"])
autoTrigSpbx = Spinbox(
		triggerSettings,
		from_=500,
		to=10000,
		textvariable=settings["autoTrigms"],
		width=7,
		increment=100
		)
autoTrigSpbx.grid(column=0, row=11, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(triggerSettings, text="Trigger delay (s)").grid(column=0, row=12, **lbf_contents_padding, sticky=W+N) 
settings["delaySeconds"] = IntVar(value=params["delaySeconds"])
delaySpbx = Spinbox(
		triggerSettings,
		from_=0,
		to=10,
		textvariable=settings["delaySeconds"],
		width=7,
		increment=1
		)
delaySpbx.grid(column=0, row=13, padx=lbf_contents_padding["padx"], sticky=W+N)

""" Channels settings """
chASettings = ChannelSettings(settingsTab, ch_id="A", column=1)
chBSettings = ChannelSettings(settingsTab, ch_id="B", column=2)
chCSettings = ChannelSettings(settingsTab, ch_id="C", column=3)
chDSettings = ChannelSettings(settingsTab, ch_id="D", column=4)

applySettingsBtn = ttk.Button(settingsTab, text="Apply", command=lambda : apply_changes(settings))
applySettingsBtn.grid(column=4, row=1, padx=0, pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=E)


root.mainloop()
