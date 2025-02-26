""" tkSliderWidget Copyright (c) 2020, Mengxun Li """
from tkinter import *
from tkinter import ttk
from pycoviewlib.constants import chInputRanges
from matplotlib.figure import Figure 
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from pycoviewlib.tkSliderWidget.tkSliderWidget import Slider

def placeholder():
	print("This button definitely does something (trust me).")

def make_histogram():
	fig = Figure(figsize=(5,3))
	hist = fig.add_subplot()
	hist.set_xlim(0,80)
	hist.set_ylim(0, 250)
	hist.set_xlabel("Delay (ns)")
	hist.set_ylabel("Counts")
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

padding = {"padx": 5, "pady": 5, "ipadx": 5, "ipady": 5}

""" Main window & frame """
root = Tk()
root.title("PycoView")

# padding is: bottom, top, right, left
topframe = ttk.Frame(root, padding="5 5 5 5")
topframe.grid(column=0, row=0, **padding, sticky=N+W+E)
topframe.columnconfigure(0, weight=1)
topframe.columnconfigure(1, weight=1)
topframe.columnconfigure(2, weight=3)
topframe.rowconfigure(0, weight=1)

modes = ["ADC", "TDC", "Meantimer"]
ttk.Label(topframe, text="Mode:").grid(column=0, row=0, sticky=W)
modeSelector = ttk.Combobox(topframe, state="readonly", values=modes)
modeSelector.current(0)
modeSelector.grid(column=1, row=0, sticky=N+W)

ttk.Label(topframe, text="v1.00", anchor=E).grid(column=2, row=0, sticky=W+E)

""" Tabs """
tabsframe = ttk.Frame(root, padding="5 0 5 5")
tabsframe.grid(column=0, row=1, **padding, sticky=W+E+S)
tabControl = ttk.Notebook(tabsframe)
runTab = ttk.Frame(tabControl)
settingsTab = ttk.Frame(tabControl)
tabControl.add(runTab, text="Run")
tabControl.add(settingsTab, text="Settings")
tabControl.pack(expand=1, fill="both")

""" Run tab """
summary = ttk.Labelframe(runTab, text="Summary")
summary.grid(column=0, row=0, columnspan=2, **padding, sticky=W+E+N+S)
for i, (key, value) in enumerate(params.items()):
	ttk.Label(summary, text=key).grid(column=0, row=i, padx=5, sticky=W)
	ttk.Label(summary, text=value, anchor=E).grid(column=2, row=i, sticky=W+E)

startButton = ttk.Button(runTab, text="START", command=placeholder)
startButton.grid(column=0, row=1, **padding, sticky=E+S)
stopButton = ttk.Button(runTab, text="STOP", command=placeholder)
stopButton.grid(column=1, row=1, **padding, sticky=W+S)

histogram = ttk.Labelframe(runTab, text="Histogram", height=500)
histogram.grid(column=2, row=0, columnspan=5, rowspan=2, **padding,  sticky=W+E+N+S)
make_histogram()
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
rangeSlider.grid(column=2, row=2, rowspan=2, sticky=W+E+N+S)
ttk.Label(runTab, text="Bins:", anchor=CENTER).grid(column=3, row=2, sticky=N)
spinbox_default = DoubleVar(value=100)
spinbox = Spinbox(runTab, from_=50, to=200, textvariable=spinbox_default, width=7, increment=10)
spinbox.grid(column=3, row=3, sticky=S)
applyButton = Button(runTab, text="Apply", width=3, height=1, command=placeholder)
applyButton.grid(column=4, row=2, rowspan=2, sticky=E+N+S)
resetButton = Button(runTab, text="Reset", width=3, height=1, command=placeholder)
resetButton.grid(column=5, row=2, rowspan=2, sticky=E+N+S)
saveButton = Button(runTab, text="Save", width=3, height=1, command=placeholder)
saveButton.grid(column=6, row=2, sticky=E+N+S)

""" Settings tab """
acquisition = ttk.Labelframe(settingsTab, text="Acquisition")
acquisition.grid(column=0, row=0, **padding, sticky=W+E+N)

ttk.Label(acquisition, text="Pre-trigger samples").grid(column=0, row=0, padx=5, pady=5, sticky=W+N) 
preTrigSpbx = Spinbox(
		acquisition,
		from_=0,
		to=500,
		textvariable=DoubleVar(value=params["preTrigSamples"]),
		width=7,
		increment=1
		)
preTrigSpbx.grid(column=0, row=1, padx=5, sticky=W+N)

ttk.Label(acquisition, text="Post-trigger samples").grid(column=0, row=2, padx=5, pady=5, sticky=W+N) 
postTrigSpbx = Spinbox(
		acquisition,
		from_=1,
		to=500,
		textvariable=DoubleVar(value=params["postTrigSamples"]),
		width=7,
		increment=1
		)
postTrigSpbx.grid(column=0, row=3, padx=5, sticky=W+N)

ttk.Label(acquisition, text="Timebase").grid(column=0, row=4, padx=5, pady=5, sticky=W+N) 
timebases = ["200 ps", "400 ps", "800 ps", "1.6 ns", "3.2 ns"]
timebaseCbx = ttk.Combobox(acquisition, state="readonly", values=timebases, width=7)
timebaseCbx.current(0)
timebaseCbx.grid(column=0, row=5, padx=5, pady=5, sticky=W+N)

ttk.Label(acquisition, text="Threshold (mV)").grid(column=0, row=6, padx=5, pady=5, sticky=W+N) 
thresholdSpbx = Spinbox(
		acquisition,
		from_=-1000, # bounds should update with the channel range
		to=0,
		textvariable=DoubleVar(value=-400), # convert from thresholdADC
		width=7,
		increment=1
		)
thresholdSpbx.grid(column=0, row=7, padx=5, sticky=W+N)

ttk.Label(acquisition, text="Auto trigger (ms)").grid(column=0, row=8, padx=5, pady=5, sticky=W+N) 
autoTrigSpbx = Spinbox(
		acquisition,
		from_=500,
		to=10000,
		textvariable=DoubleVar(value=params["autoTrigms"]),
		width=7,
		increment=100
		)
autoTrigSpbx.grid(column=0, row=9, padx=5, sticky=W+N)

ttk.Label(acquisition, text="Trigger delay (s)").grid(column=0, row=10, padx=5, pady=5, sticky=W+N) 
delaySpbx = Spinbox(
		acquisition,
		from_=0,
		to=10,
		textvariable=DoubleVar(value=params["autoTrigms"]),
		width=7,
		increment=1
		)
delaySpbx.grid(column=0, row=11, padx=5, sticky=W+N)

""" Channel A settings """
chALbf = ttk.Labelframe(settingsTab, text="Channel A")
chALbf.grid(column=1, row=0, **padding, sticky=W+E+N)

chAEnabledFlag = IntVar()
chAEnabled = Checkbutton(chALbf, variable=chAEnabledFlag, text="Enabled", onvalue=1, offvalue=0, command=placeholder)
chAEnabled.grid(column=0, row=0, pady=5, sticky=W+N)

ttk.Label(chALbf, text="Range (mV)").grid(column=0, row=1, padx=5, pady=5, sticky=W+N) 
chRangeCbx = ttk.Combobox(chALbf, state="readonly", values=chInputRanges, width=7)
chRangeCbx.current(0)
chRangeCbx.grid(column=0, row=2, padx=5, pady=5, sticky=W+N)

ttk.Label(chALbf, text="Coupling").grid(column=0, row=3, padx=5, pady=5, sticky=W+N) 
coupling = ["AC 1MΩ", "DC 1MΩ", "DC 50Ω"]
couplingCbx = ttk.Combobox(chALbf, state="readonly", values=coupling, width=7)
couplingCbx.current(0)
couplingCbx.grid(column=0, row=4, padx=5, pady=5, sticky=W+N)

ttk.Label(chALbf, text="Analogue offset (mV)").grid(column=0, row=5, padx=5, pady=5, sticky=W+N) 
analogOffsetSpbx = Spinbox(
		chALbf,
		from_=0,
		to=500, # should update with channel range too
		textvariable=DoubleVar(value=params["analogOffset"]),
		width=7,
		increment=1
		)
analogOffsetSpbx.grid(column=0, row=6, padx=5, sticky=W+N)

ttk.Label(chALbf, text="Bandwidth").grid(column=0, row=7, padx=5, pady=5, sticky=W+N) 
bandwidth = ["Full", "25MHz"]
bandwidthCbx = ttk.Combobox(chALbf, state="readonly", values=bandwidth, width=7)
bandwidthCbx.current(0)
bandwidthCbx.grid(column=0, row=8, padx=5, pady=5, sticky=W+N)

""" Channel B settings """
chBLbf = ttk.Labelframe(settingsTab, text="Channel B")
chBLbf.grid(column=2, row=0, **padding, sticky=W+E+N)

chAEnabledFlag = IntVar()
chBEnabled = Checkbutton(chBLbf, variable=chAEnabledFlag, text="Enabled", onvalue=1, offvalue=0, command=placeholder)
chBEnabled.grid(column=0, row=0, pady=5, sticky=W+N)

ttk.Label(chBLbf, text="Range (mV)").grid(column=0, row=1, padx=5, pady=5, sticky=W+N) 
chRangeCbx = ttk.Combobox(chBLbf, state="readonly", values=chInputRanges, width=7)
chRangeCbx.current(0)
chRangeCbx.grid(column=0, row=2, padx=5, pady=5, sticky=W+N)

ttk.Label(chBLbf, text="Coupling").grid(column=0, row=3, padx=5, pady=5, sticky=W+N) 
couplingCbx = ttk.Combobox(chBLbf, state="readonly", values=coupling, width=7)
couplingCbx.current(0)
couplingCbx.grid(column=0, row=4, padx=5, pady=5, sticky=W+N)

ttk.Label(chBLbf, text="Analogue offset (mV)").grid(column=0, row=5, padx=5, pady=5, sticky=W+N) 
analogOffsetSpbx = Spinbox(
		chBLbf,
		from_=0,
		to=500, # should update with channel range too
		textvariable=DoubleVar(value=params["analogOffset"]),
		width=7,
		increment=1
		)
analogOffsetSpbx.grid(column=0, row=6, padx=5, sticky=W+N)

ttk.Label(chBLbf, text="Bandwidth").grid(column=0, row=7, padx=5, pady=5, sticky=W+N) 
bandwidthCbx = ttk.Combobox(chBLbf, state="readonly", values=bandwidth, width=7)
bandwidthCbx.current(0)
bandwidthCbx.grid(column=0, row=8, padx=5, pady=5, sticky=W+N)

""" Channel C settings """
chCLbf = ttk.Labelframe(settingsTab, text="Channel C")
chCLbf.grid(column=3, row=0, **padding, sticky=W+E+N)

chCEnabledFlag = IntVar()
chCEnabled = Checkbutton(chCLbf, variable=chCEnabledFlag, text="Enabled", onvalue=1, offvalue=0, command=placeholder)
chCEnabled.grid(column=0, row=0, pady=5, sticky=W+N)

ttk.Label(chCLbf, text="Range (mV)").grid(column=0, row=1, padx=5, pady=5, sticky=W+N) 
chRangeCbx = ttk.Combobox(chCLbf, state="readonly", values=chInputRanges, width=7)
chRangeCbx.current(0)
chRangeCbx.grid(column=0, row=2, padx=5, pady=5, sticky=W+N)

ttk.Label(chCLbf, text="Coupling").grid(column=0, row=3, padx=5, pady=5, sticky=W+N) 
couplingCbx = ttk.Combobox(chCLbf, state="readonly", values=coupling, width=7)
couplingCbx.current(0)
couplingCbx.grid(column=0, row=4, padx=5, pady=5, sticky=W+N)

ttk.Label(chCLbf, text="Analogue offset (mV)").grid(column=0, row=5, padx=5, pady=5, sticky=W+N) 
analogOffsetSpbx = Spinbox(
		chCLbf,
		from_=0,
		to=500, # should update with channel range too
		textvariable=DoubleVar(value=params["analogOffset"]),
		width=7,
		increment=1
		)
analogOffsetSpbx.grid(column=0, row=6, padx=5, sticky=W+N)

ttk.Label(chCLbf, text="Bandwidth").grid(column=0, row=7, padx=5, pady=5, sticky=W+N) 
bandwidthCbx = ttk.Combobox(chCLbf, state="readonly", values=bandwidth, width=7)
bandwidthCbx.current(0)
bandwidthCbx.grid(column=0, row=8, padx=5, pady=5, sticky=W+N)

""" Channel D settings """
chDLbf = ttk.Labelframe(settingsTab, text="Channel C")
chDLbf.grid(column=4, row=0, **padding, sticky=W+E+N)

chDEnabledFlag = IntVar()
chDEnabled = Checkbutton(chDLbf, variable=chDEnabledFlag, text="Enabled", onvalue=1, offvalue=0, command=placeholder)
chDEnabled.grid(column=0, row=0, pady=5, sticky=W+N)

ttk.Label(chDLbf, text="Range (mV)").grid(column=0, row=1, padx=5, pady=5, sticky=W+N) 
chRangeCbx = ttk.Combobox(chDLbf, state="readonly", values=chInputRanges, width=7)
chRangeCbx.current(0)
chRangeCbx.grid(column=0, row=2, padx=5, pady=5, sticky=W+N)

ttk.Label(chDLbf, text="Coupling").grid(column=0, row=3, padx=5, pady=5, sticky=W+N) 
couplingCbx = ttk.Combobox(chDLbf, state="readonly", values=coupling, width=7)
couplingCbx.current(0)
couplingCbx.grid(column=0, row=4, padx=5, pady=5, sticky=W+N)

ttk.Label(chDLbf, text="Analogue offset (mV)").grid(column=0, row=5, padx=5, pady=5, sticky=W+N) 
analogOffsetSpbx = Spinbox(
		chDLbf,
		from_=0,
		to=500, # should update with channel range too
		textvariable=DoubleVar(value=params["analogOffset"]),
		width=7,
		increment=1
		)
analogOffsetSpbx.grid(column=0, row=6, padx=5, sticky=W+N)

ttk.Label(chDLbf, text="Bandwidth").grid(column=0, row=7, padx=5, pady=5, sticky=W+N) 
bandwidthCbx = ttk.Combobox(chDLbf, state="readonly", values=bandwidth, width=7)
bandwidthCbx.current(0)
bandwidthCbx.grid(column=0, row=8, padx=5, pady=5, sticky=W+N)


root.mainloop()
