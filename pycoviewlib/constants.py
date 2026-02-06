from picosdk.psospa import psospa as ps
from picosdk.ps6000 import ps6000
from picosdk.PicoDeviceEnums import picoEnum as enums
from pathlib import Path

PV_DIR = Path('~/Documents/PycoView3KE/').expanduser()
PYTHON = Path('~/.venv/bin/python3').expanduser()

chInputRanges = [
    10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000,
    50000, 100000, 200000
]

maxADC = 32512

channelIDs = ['A', 'B', 'C', 'D']
dataFileTypes = ['txt', 'csv']
modes = {'ADC': 'adc', 'TDC': 'tdc', 'Meantimer': 'mntm'}
# timebases = ['200 ps', '400 ps', '800 ps', '1.6 ns', '3.2 ns']
# timebasesPs = [200, 400, 800, 1600, 3200]
timebases = {
    '200 ps': 200,
    '400 ps': 400,
    '800 ps': 800,
    '1.6 ns': 1600,
    '3.2 ns': 3200
}
# couplings = {'AC 1MΩ': (0, 1000000), 'DC 1MΩ': (1, 1000000), 'DC 50Ω': (2, 50)}
couplings = {'AC 1MΩ': (0, 1000000), 'DC 1MΩ': (1, 1000000), 'DC 50Ω': (2, 50)}
pCouplings = list(enums.PICO_COUPLING.values()) # necessary?
# bandwidths = {'Full': 0, '25MHz': 1}
bandwidths = {
    'Full': 0,
    '100KHz': 100000,
    '20KHz': 20000,
    '1MHz': 1000000,
    '20MHz': 20000000,
    '25MHz': 25000000,
    '50MHz': 50000000,
    '200HMz': 200000000,
    '250MHz': 250000000,
    '500MHz': 500000000,
}

PS6000_CONDITION_TRUE = ps6000.PS6000_TRIGGER_STATE['PS6000_CONDITION_TRUE']
PS6000_CONDITION_DONT_CARE = ps6000.PS6000_TRIGGER_STATE['PS6000_CONDITION_DONT_CARE']
PS6000_BELOW = ps6000.PS6000_THRESHOLD_DIRECTION['PS6000_BELOW']
PS6000_NONE = ps6000.PS6000_THRESHOLD_DIRECTION['PS6000_NONE']
