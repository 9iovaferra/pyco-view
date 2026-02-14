from picosdk.PicoDeviceEnums import picoEnum as enums
from ctypes import Structure, c_int16, c_uint16, c_int32
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
timebases = {
    '200 ps': 200,
    '400 ps': 400,
    '800 ps': 800,
    '1.6 ns': 1600,
    '3.2 ns': 3200
}
couplings = {'AC 1MΩ': (0, 1000000), 'DC 1MΩ': (1, 1000000), 'DC 50Ω': (2, 50)}
# couplings = {('AC 1MΩ', 0): 1000000, ('DC 1MΩ', 1): 1000000, ('DC 50Ω', 2): 50}
# couplings = {'AC 1MΩ': 1000000, 'DC 1MΩ': 1000000, 'DC 50Ω': 50}
pCouplings = list(enums.PICO_COUPLING.values()) # necessary?
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

class TriggerCondition(Structure):
    """
    Trigger conditions structure used in psospaSetTriggerChannelConditions.
    `gcc-sysv` is the struct layout as used on Linux and macOS systems
    """
    # _pack_ = 1 ??
    _layout_ = 'gcc-sysv'
    _fields_ = [('source', c_int32), ('condition', c_int32)]

class TriggerProperties(Structure):
    """
    Trigger properties structure used in psospaSetTriggerChannelProperties.
    """
    _layout_ = 'gcc-sysv'
    _fields_ = [
        ('thresholdUpper', c_int16),
        ('thresholdUpperHysteresis', c_uint16),
        ('thresholdLower', c_int16),
        ('thresholdLowerHysteresis', c_uint16),
        ('channel', c_int32),
    ]

class TriggerDirection(Structure):
    """
    Trigger direction structure used in psospaSetTriggerChannelDirections.
    """
    _layout_ = 'gcc-sysv'
    _fields_ = [
        ('channel', c_int32),
        ('direction', c_int32)
        ('thresholdMode', c_uint16)
    ]
