chInputRanges = [
	10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000,
	50000, 100000, 200000
	]

maxADC = 32512

channelIDs = ["A", "B", "C", "D"]
modes = ["ADC", "TDC", "Meantimer"]
timebases = ["200 ps", "400 ps", "800 ps", "1.6 ns", "3.2 ns"]
couplings = {"DC 50Ω": 50, "DC 1MΩ": 1000000, "AC 1MΩ": 1000000}
bandwidths = {"Full": 0, "25MHz": 1}
