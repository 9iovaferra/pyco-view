""" tkSliderWidget Copyright (c) 2020, Mengxun Li """
from tkinter import *
from tkinter import ttk
from pycoviewlib.constants import chInputRanges
from matplotlib.figure import Figure 
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from pycoviewlib.tkSliderWidget.tkSliderWidget import Slider

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

		self.checkVar = IntVar(value=1)
		self.enabled = Checkbutton(
				self.chFrame, variable=self.checkVar, text="Enabled", onvalue=1, offvalue=0, command=placeholder
				)
		self.enabled.grid(column=0, row=0, pady=(THIN_PAD,0), sticky=W+N)

		ttk.Label(self.chFrame, text="Range (±mV)").grid(column=0, row=1, **lbf_contents_padding, sticky=W+N) 
		self.chRange = ttk.Combobox(self.chFrame, state="readonly", values=chInputRanges, width=7)
		self.chRange.current(params['chRange'])
		self.chRange.grid(column=0, row=2, padx=THIN_PAD, sticky=W+N)

		ttk.Label(self.chFrame, text="Coupling").grid(column=0, row=3, **lbf_contents_padding, sticky=W+N) 
		self.coupling = ttk.Combobox(self.chFrame, state="readonly", values=coupling, width=7)
		self.coupling.current(0)
		self.coupling.grid(column=0, row=4, padx=THIN_PAD, sticky=W+N)

		ttk.Label(self.chFrame, text="Analogue offset (mV)").grid(column=0, row=5, **lbf_contents_padding, sticky=W+N) 
		self.analogOffset = Spinbox(
				self.chFrame,
				from_=0,
				to=500, # should update with channel range too
				textvariable=DoubleVar(value=params["analogOffset"]),
				width=7,
				increment=1
				)
		self.analogOffset.grid(column=0, row=6, padx=THIN_PAD, sticky=W+N)

		ttk.Label(self.chFrame, text="Bandwidth").grid(column=0, row=7, **lbf_contents_padding, sticky=W+N) 
		self.bandwidth = ttk.Combobox(self.chFrame, state="readonly", values=bandwidth, width=7)
		self.bandwidth.current(0)
		self.bandwidth.grid(column=0, row=8, padx=THIN_PAD, sticky=W+N)

def placeholder():
	print("This command definitely does something (trust me).")

def make_histogram():
	fig = Figure(figsize=(6,4))
	fig.patch.set_visible(False)
	hist = fig.add_subplot()
	hist.set_facecolor("none")
	hist.patch.set_visible(False)
	hist.set_xlim(0,80)
	hist.set_ylim(0,250)
	hist.set_xlabel("Delay (ns)")
	hist.set_ylabel("Counts")
	fig.tight_layout()
	canvas = FigureCanvasTkAgg(fig, master=histogram)
	canvas.draw()
	canvas.get_tk_widget().pack()

""" Reading runtime parameters from .ini file """
params = {}
with open("config.ini", "r") as ini:
	for p in ini.readlines()[1:]:
		p = p.rstrip("\n").split(" = ")
		params[p[0]] = int(p[1]) if p[1].isdigit() else float(p[1])
params["maxSamples"] = params["preTrigSamples"] + params["postTrigSamples"]

""" Padding presets """
THIN_PAD = 6
WIDE_PAD = 2 * THIN_PAD
uniform_padding = {"padx": WIDE_PAD, "pady": WIDE_PAD, "ipadx": THIN_PAD, "ipady": THIN_PAD}
asym_left_padding = {"padx": (WIDE_PAD,0), "pady": WIDE_PAD, "ipadx": THIN_PAD, "ipady": THIN_PAD}
asym_right_padding = {"padx": (0,WIDE_PAD), "pady": WIDE_PAD, "ipadx": THIN_PAD, "ipady": THIN_PAD}
lbf_padding = {"padx": WIDE_PAD, "pady": WIDE_PAD, "ipadx": THIN_PAD, "ipady": THIN_PAD}
lbf_contents_padding = {"padx": (THIN_PAD,0), "pady": (8,2)}
# Frame padding: "left top right bottom"

""" Parameters options """
timebases = ["200 ps", "400 ps", "800 ps", "1.6 ns", "3.2 ns"]
coupling = ["AC 1MΩ", "DC 1MΩ", "DC 50Ω"]
bandwidth = ["Full", "25MHz"]

""" Main window & frame """
root = RootWindow()

topFrame = ttk.Frame(root, padding=(6,0,6,6))
topFrame.grid(column=0, row=0, padx=WIDE_PAD, pady=(WIDE_PAD,0), sticky=N+W+E)
# topFrame.columnconfigure(0, weight=1)
# topFrame.columnconfigure(1, weight=1)
topFrame.columnconfigure(2, weight=3)
# topFrame.rowconfigure(0, weight=1)

modes = ["ADC", "TDC", "Meantimer"]
ttk.Label(topFrame, text="Mode:").grid(column=0, row=0, sticky=W)
modeSelector = ttk.Combobox(topFrame, state="readonly", width=10, values=modes)
modeSelector.current(0)
modeSelector.grid(column=1, row=0, padx=WIDE_PAD, sticky=N+W)

ttk.Label(topFrame, text="v1.00", anchor=E).grid(column=2, row=0, sticky=E)

""" Tabs """
tabsFrame = ttk.Frame(root, padding=(6,0,6,6))
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
summary.columnconfigure(1, weight=2)

# for i, ch in enumerate(["A", "B", "C", "D"]):
# 	ttk.Label(summary, text=ch).grid(
# 			column=i+1, row=0, padx=(THIN_PAD,0) if i <= 2 else THIN_PAD, pady=(12,0), sticky=E
# 			)
ttk.Label(summary, text="Range (±mV)").grid(column=0, row=1, padx=(THIN_PAD,0), pady=(12,0), sticky=W)
ttk.Label(summary, text=f"{chInputRanges[params['chRange']]}", anchor=E).grid(
		column=1, row=1, padx=(0,THIN_PAD), pady=(12,0), sticky=W+E
		)
ttk.Label(summary, text="Analog offset (mV)").grid(column=0, row=2, padx=(THIN_PAD,0), pady=(2,0), sticky=W)
ttk.Label(summary, text=f"{params['analogOffset'] * 1000}", anchor=E).grid(
		column=1, row=2, padx=(0,THIN_PAD), pady=(2,0), sticky=W+E
		)
ttk.Label(summary, text="Coupling (Ω)").grid(column=0, row=3, padx=(THIN_PAD,0), pady=(2,0), sticky=W)
ttk.Label(summary, text=f"{params['terminalResist']}", anchor=E).grid(
		column=1, row=3, padx=(0,THIN_PAD), pady=(2,0), sticky=W+E
		)
ttk.Label(summary, text="Threshold (16-bit ADC)").grid(column=0, row=4, padx=(THIN_PAD,0), pady=(2,0), sticky=W)
ttk.Label(summary, text=f"{params['thresholdADC']}", anchor=E).grid(
		column=1, row=4, padx=(0,THIN_PAD), pady=(2,0), sticky=W+E
		)
ttk.Separator(summary, orient='horizontal').grid(
		column=0, row=5, columnspan=2, padx=WIDE_PAD, pady=(WIDE_PAD,0), sticky=W+E
		)
ttk.Label(summary, text="Timebase").grid(column=0, row=6, padx=(THIN_PAD,0), pady=(12,0), sticky=W)
ttk.Label(summary, text=f"{timebases[params['timebase']]}", anchor=E).grid(
		column=1, row=6, padx=(0,THIN_PAD), pady=(12,0), sticky=W+E
		)
ttk.Label(summary, text="Trigger delay").grid(column=0, row=7, padx=(THIN_PAD,0), pady=(2,0), sticky=W)
ttk.Label(summary, text=f"{params['delaySeconds']} s", anchor=E).grid(
		column=1, row=7, padx=(0,THIN_PAD), pady=(2,0), sticky=W+E
		)
ttk.Label(summary, text="Auto-trigger").grid(column=0, row=8, padx=(THIN_PAD,0), pady=(2,0), sticky=W)
ttk.Label(summary, text=f"{params['autoTrigms']} ms", anchor=E).grid(
		column=1, row=8, padx=(0,THIN_PAD), pady=(2,0), sticky=W+E
		)
ttk.Label(summary, text="Pre-trigger samples").grid(column=0, row=9, padx=(THIN_PAD,0), pady=(2,0), sticky=W)
ttk.Label(summary, text=f"{params['preTrigSamples']}", anchor=E).grid(
		column=1, row=9, padx=(0,THIN_PAD), pady=(2,0), sticky=W+E
		)
ttk.Label(summary, text="Post-trigger samples").grid(column=0, row=10, padx=(THIN_PAD,0), pady=(2,0), sticky=W)
ttk.Label(summary, text=f"{params['postTrigSamples']}", anchor=E).grid(
		column=1, row=10, padx=(0,THIN_PAD), pady=(2,0), sticky=W+E
		)
logFlag = IntVar(value=1) # read from config file
logCheckBox = Checkbutton(
		summary, variable=logFlag, text="Log acquisition", onvalue=1, offvalue=0, command=placeholder
		)
logCheckBox.grid(column=0, row=11, pady=(0,THIN_PAD), sticky=W+S)

# for i, (key, value) in enumerate(params.items()):
# 	ttk.Label(summary, text=key).grid(
# 			column=0, row=i, padx=(THIN_PAD,0), pady=(12 if i == 0 else 2,0), sticky=W
# 			)
# 	ttk.Label(summary, text=value, anchor=E).grid(
# 			column=1, row=i, padx=(0,THIN_PAD), pady=(12 if i == 0 else 2,0), sticky=W+E
# 			)

startButton = ttk.Button(runTab, text="START", command=placeholder)
startButton.grid(column=0, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=W+S)
stopButton = ttk.Button(runTab, text="STOP", command=placeholder)
stopButton.grid(column=1, row=1, padx=(WIDE_PAD,0), pady=0, ipadx=THIN_PAD, ipady=THIN_PAD, sticky=E+S)

histogram = ttk.Labelframe(runTab, text="Histogram")
histogram.grid(column=2, row=0, columnspan=7, rowspan=2, padx=(WIDE_PAD,0), pady=(WIDE_PAD,0), ipadx=THIN_PAD, ipady=THIN_PAD, sticky=W+E+N+S)
make_histogram()
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
spinbox_default = DoubleVar(value=100)
spinbox = Spinbox(runTab, from_=50, to=200, textvariable=spinbox_default, width=5, increment=10)
spinbox.grid(column=5, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=N+W)
applyButton = Button(runTab, text="Apply", width=3, height=1, command=placeholder)
applyButton.grid(column=6, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=E+N)
resetButton = Button(runTab, text="Reset", width=3, height=1, command=placeholder)
resetButton.grid(column=7, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=E+N)
saveButton = Button(runTab, text="Save", width=3, height=1, command=placeholder)
saveButton.grid(column=8, row=2, padx=(THIN_PAD,0), pady=(THIN_PAD,0), sticky=E+N)

""" Settings tab """
""" Acquisition settings """
acquisition = ttk.Labelframe(settingsTab, text="Acquisition")
acquisition.grid(column=0, row=0, **asym_left_padding, sticky=W+E+N)

ttk.Label(acquisition, text="Pre-trigger samples").grid(column=0, row=0, **lbf_contents_padding, sticky=W+N) 
preTrigSpbx = Spinbox(
		acquisition,
		from_=0,
		to=500,
		textvariable=DoubleVar(value=params["preTrigSamples"]),
		width=7,
		increment=1
		)
preTrigSpbx.grid(column=0, row=1, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(acquisition, text="Post-trigger samples").grid(column=0, row=2, **lbf_contents_padding, sticky=W+N) 
postTrigSpbx = Spinbox(
		acquisition,
		from_=1,
		to=500,
		textvariable=DoubleVar(value=params["postTrigSamples"]),
		width=7,
		increment=1
		)
postTrigSpbx.grid(column=0, row=3, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(acquisition, text="Timebase").grid(column=0, row=4, **lbf_contents_padding, sticky=W+N) 
timebaseCbx = ttk.Combobox(acquisition, state="readonly", values=timebases, width=7)
timebaseCbx.current(0)
timebaseCbx.grid(column=0, row=5, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(acquisition, text="Threshold (mV)").grid(column=0, row=6, **lbf_contents_padding, sticky=W+N) 
thresholdSpbx = Spinbox(
		acquisition,
		from_=-1000, # bounds should update with the channel range
		to=0,
		textvariable=DoubleVar(value=-400), # convert from thresholdADC
		width=7,
		increment=1
		)
thresholdSpbx.grid(column=0, row=7, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(acquisition, text="Auto trigger (ms)").grid(column=0, row=8, **lbf_contents_padding, sticky=W+N) 
autoTrigSpbx = Spinbox(
		acquisition,
		from_=500,
		to=10000,
		textvariable=DoubleVar(value=params["autoTrigms"]),
		width=7,
		increment=100
		)
autoTrigSpbx.grid(column=0, row=9, padx=lbf_contents_padding["padx"], sticky=W+N)

ttk.Label(acquisition, text="Trigger delay (s)").grid(column=0, row=10, **lbf_contents_padding, sticky=W+N) 
delaySpbx = Spinbox(
		acquisition,
		from_=0,
		to=10,
		textvariable=DoubleVar(value=params["autoTrigms"]),
		width=7,
		increment=1
		)
delaySpbx.grid(column=0, row=11, padx=lbf_contents_padding["padx"], sticky=W+N)

""" Channel A settings """
chASettings = ChannelSettings(settingsTab, ch_id="A", column=1)

""" Channel B settings """
chBSettings = ChannelSettings(settingsTab, ch_id="B", column=2)

""" Channel C settings """
chCSettings = ChannelSettings(settingsTab, ch_id="C", column=3)

""" Channel D settings """
chDSettings = ChannelSettings(settingsTab, ch_id="D", column=4)


root.mainloop()
