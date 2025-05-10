from picosdk.ps6000 import ps6000 as ps
from pathlib import Path

PV_DIR = Path('~/Documents/pyco-view/').expanduser()
PYTHON = Path('~/.venv/bin/python3').expanduser()

chInputRanges = [
	10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000,
	50000, 100000, 200000
	]

maxADC = 32512

channelIDs = ['A', 'B', 'C', 'D']
dataFileTypes = ['txt', 'csv']
modes = {'ADC': 'adc', 'TDC': 'tdc', 'Meantimer': 'mntm'}
timebases = ['200 ps', '400 ps', '800 ps', '1.6 ns', '3.2 ns']
couplings = {'AC 1MΩ': (0, 1000000), 'DC 1MΩ': (1, 1000000), 'DC 50Ω': (2, 50)}
bandwidths = {'Full': 0, '25MHz': 1}

PS6000_CONDITION_TRUE = ps.PS6000_TRIGGER_STATE['PS6000_CONDITION_TRUE']
PS6000_CONDITION_DONT_CARE = ps.PS6000_TRIGGER_STATE['PS6000_CONDITION_DONT_CARE']
PS6000_BELOW = ps.PS6000_THRESHOLD_DIRECTION['PS6000_BELOW']
PS6000_NONE = ps.PS6000_THRESHOLD_DIRECTION['PS6000_NONE']
