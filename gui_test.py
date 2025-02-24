""" tkSliderWidget Copyright (c) 2020, Mengxun Li """
from tkinter import *
from tkinter import ttk
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

root = Tk()
root.title("PycoView")
# root.geometry("600x400")

topframe = ttk.Frame(root, padding="3 3 12 12")
topframe.grid(column=0, row=0, **padding, sticky=N+W+E)
topframe.columnconfigure(0, weight=1)
topframe.columnconfigure(2, weight=3)
topframe.rowconfigure(0, weight=1)

ttk.Label(topframe, text="v1.00", anchor=E).grid(column=2, row=0, sticky=W+E)

""" Mode selector """
modes = ["ADC", "TDC", "Meantimer"]
ttk.Label(topframe, text="Mode:").grid(column=0, row=0, sticky=W)
modeSelector = ttk.Combobox(topframe, state="readonly", values=modes)
modeSelector.current(0)
modeSelector.grid(column=1, row=0, sticky=N+W)

""" Tabs """
tabsframe = ttk.Frame(root, padding="3 3 12 12")
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

histogram = ttk.Labelframe(runTab, text="Histogram")
histogram.grid(column=2, row=0, columnspan=5, rowspan=2, **padding, sticky=W+E+N+S)
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
rangeSlider.grid(column=2, row=2, rowspan=2, **padding, sticky=W+E+N+S)
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

# for child in topframe.winfo_children():
# 	child.grid_configure(padx=5, pady=5)
# for child in tabsframe.winfo_children():
# 	child.grid_configure(padx=5, pady=5)

root.mainloop()
