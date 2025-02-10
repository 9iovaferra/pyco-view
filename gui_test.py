from tkinter import *
from tkinter import ttk

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
root.geometry("600x400")

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
summary = ttk.Labelframe(runTab, text="Summary", width=300, height=300)
summary.grid(column=0, row=0, **padding, sticky=W+E)
for i, (key, value) in enumerate(params.items()):
	ttk.Label(summary, text=key).grid(column=0, row=i, sticky=W)
	ttk.Label(summary, text=value).grid(column=2, row=i, sticky=E)

# for child in topframe.winfo_children():
# 	child.grid_configure(padx=5, pady=5)
# for child in tabsframe.winfo_children():
# 	child.grid_configure(padx=5, pady=5)

root.mainloop()
