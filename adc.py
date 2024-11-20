""" Copyright (C) 2019 Pico Technology Ltd. """
from ctypes import c_int16, c_int32, c_float, Array, byref
import numpy as np
from picosdk.ps6000 import ps6000 as ps
import matplotlib.pyplot as plt
from picosdk.functions import adc2mV, assert_pico_ok
from datetime import datetime
import sys
from pathlib import Path

def print_status(status: dict) -> None:
	if bool(status):
		print("PicoScope Exit Status:")
		for key, value in status.items():
			print("{: <15} {: <15}".format(key, value))
	else:
		print("No status to show.")

def detect_gate_open_closed(
		buffer: Array[c_int16],
		time: np.ndarray[np.float32],
		threshold: float,
		maxSamples: int,
		timeIntervalns: float
		) -> tuple[dict[str, float | int]]:
	"""
	minValueIndex = array index of the buffer's negative peak
		(most negative value).
	Threshold hits are returned as (voltage, time) coordinates.
	"""
	gateOpen = {"mV": threshold, "ns": 0.0, "index": 0}
	gateClosed = {"mV": threshold, "ns": 0.0, "index": 0} 
	hit = 0
	minValueIndex = buffer.index(min(buffer))
	minDifference = min(buffer) - threshold
	for i in range(minValueIndex):
		if abs(buffer[i] - threshold) < abs(minDifference):
			hit = i
			minDifference = buffer[i] - threshold
	gateOpen["ns"] = time[hit]
	gateOpen["index"] = hit
	minDifference = min(buffer) - threshold
	for i in range(minValueIndex, maxSamples):
		if abs(buffer[i] - threshold) < abs(minDifference):
			hit = i
			minDifference = buffer[i] - threshold
	gateClosed["ns"] = time[hit]
	gateClosed["index"] = hit
	
	return gateOpen, gateClosed

def calculate_charge(
		buffer: Array[c_int16],
		gateOpen: dict,
		gateClosed: dict,
		timeIntervalns: float,
		resistance: int
		) -> float:
	"""
	Total charge deposited by the particle in the detector.
	It is defined as the integral of voltage with respect to time,
	multiplied by dt and divided by the termination resistance.
	"""
	charge = 0.0
	for i in range(gateOpen, gateClosed):
		charge += abs(buffer[i])	
	charge *= (timeIntervalns / resistance)
	
	return charge

def plot_data(
		bufferChAmV: Array[c_int16],
		bufferChCmV: Array[c_int16],
		gateOpen: dict,
		gateClosed: dict,
		timeIntervalns: float,
		peakToPeak: float,
		time: np.ndarray,
		charge: float,
		filestamp: str,
		) -> None:
	yLowerLim = min(bufferChAmV) + min(bufferChAmV) * 0.1
	yUpperLim = max(bufferChAmV) + max(bufferChAmV) * 0.3
	# yTicks = np.arange(-1000, 0, 50)

	plt.figure(figsize=(10,6))
		
	""" Channel signals """
	plt.plot(time, bufferChAmV[:],
			 color="blue", label="Channel A (gate)")
	plt.plot(time, bufferChCmV[:],
			 color="green", label="Channel C (detector signal)")
	
	""" Charge area + bounds from gate """
	plt.fill_between(
			np.arange(gateOpen["ns"], gateClosed["ns"], timeIntervalns.value),
			bufferChCmV[gateOpen["index"]:gateClosed["index"]], max(bufferChCmV),
			color="lightgrey", label=f"Total deposited charge\n{charge:.2f} C"
			)
	plt.plot([gateOpen["ns"]] * 2, [gateOpen["mV"], max(bufferChCmV)],
			 linestyle="--", color="black")
	plt.plot([gateClosed["ns"]] * 2, [gateClosed["mV"], max(bufferChCmV)],
			 linestyle="--", color="black")
	
	""" Threshold """
	# plt.axhline(y=thresholdmV, linestyle="--", color="black",
	#			label=f"Channel A threshold\n{thresholdmV:.2f} mV")
	
	""" Gate open and closed points """
	plt.plot(gateOpen["ns"], gateOpen["mV"],
			 color="black", marker=">", label=f"Gate open\n{gateOpen['ns']:.2f} ns")
	plt.plot(gateClosed["ns"], gateClosed["mV"],
			 color="black", marker="<", label=f"Gate closed\n{gateClosed['ns']:.2f} ns")
	
	""" Amplitude and Peak-To-Peak """
	plt.plot([time[bufferChCmV.index(max(bufferChCmV))]] * 2,
			 [max(bufferChCmV), min(bufferChCmV)],
			 color="black")
	plt.text(time[bufferChCmV.index(max(bufferChCmV))] + 0.5,
			 max(bufferChCmV) - peakToPeak / 2,
			 f"Peak-to-peak\n{peakToPeak:.2f} mV")
	
	""" Threshold line """
	# plt.plot(time.tolist()[bufferChAmV.index(min(bufferChAmV))], min(bufferChAmV), "ko")

	plt.xlabel('Time (ns)')
	plt.ylim(yLowerLim,yUpperLim)
	plt.ylabel('Voltage (mV)')
	plt.legend(loc="lower right")
	plt.savefig(f"./Data/plot_{filestamp}.png")

def parse_args(args: list) -> dict:
	options = dict.fromkeys([
		"captures", "plot", "log", "dformat"
		])
	if len(args) == 1:
		options["captures"] = 1
		options["plot"] = False
		options["log"] = False
		options["dformat"] = "txt"
	else:
		for arg in args:
			if arg.isdigit():
				options["captures"] = int(arg)
		options["plot"] = True if "plot" in args else False
		options["log"] = True if "log" in args else False
		options["dformat"] = "csv" if "csv" in args else "txt"
	
	return options

def log(loghandle: str, entry: str, time=False) -> None:
	with open(f"./Data/{loghandle}", "a") as logfile:
		if time:
			logfile.write(f"[{datetime.now().strftime('%H:%M:%S')}] {entry}\n")
		else:
			logfile.write(f"           {entry}\n")


def main():
	runtimeOptions: dict = parse_args(sys.argv)

	timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	
	""" Creating loghandle if required """
	if runtimeOptions["log"]:
		loghandle: str = f"log_{timestamp}.txt"

	""" Creating data folder """
	try:
		Path("~/Documents/pyco-view/Data").expanduser().mkdir(exist_ok=True)
	except PermissionError:
		print("Permission Error: cannot write to this location.")
		if runtimeOptions["log"]:
			log(loghandle,
	   			f"==> (!) Permission Error: cannot write to {str(Path('~/Documents/pyco-view/Data').expanduser())}.",
	   			time=True)
		sys.exit(1)
	
	""" Creating chandle and status. Setting acquisition parameters.
	Opening ps6000 connection: returns handle for future use in API functions
	"""
	chandle = c_int16()
	status = {}

	chInputRanges = [
			10, 20, 50, 100, 200, 500, 1000, 2000,
			5000, 10000, 20000, 50000, 100000, 200000
			]
	delaySeconds = 0
	chRange = 5
	analogOffset = 0.45
	thresholdADC = 10000
	autoTrigms = 10000
	preTrigSamples = 50
	postTrigSamples = 250
	maxSamples = preTrigSamples + postTrigSamples
	timebase = 1
	terminalResist = 50
	
	""" Logging runtime parameters """
	if runtimeOptions["log"]:
		log(loghandle, "==> Running acquisition with parameters:", time=True)
		params = dict(zip(
			["delaySeconds", "chRangemV", "analogOffset", "thresholdADC",
			"autoTrigms", "preTrigSamples", "postTrigSamples", "maxSamples",
			"timebase", "terminalResist"],
			[0, 500, 0.45, 10000, 10000, 50, 250, maxSamples, 1, 5, 0]
			))	
		for key, value in params.items():
			log(loghandle, "{: <15} {: <15}".format(key, value))

	status["openUnit"] = ps.ps6000OpenUnit(byref(chandle), None)
	assert_pico_ok(status["openUnit"])

	""" Setting up channel A and C (B and D turned off)
				A			B
	handle		chandle		chandle
	channel		ChA=0		ChB=1
	enabled		1			1
	coupling	DC=1		DC=1	(50ohm)
	range		500mV=5		500mV=5
	offset		0V			0V
	bandwidth	Full=0		Full=0
	"""
	status["setChA"] = ps.ps6000SetChannel(chandle, 0, 1, 1, chRange, analogOffset, 0)
	assert_pico_ok(status["setChA"])
	status["setChB"] = ps.ps6000SetChannel(chandle, 1, 0, 1, chRange, 0, 0)
	assert_pico_ok(status["setChB"])
	status["setChC"] = ps.ps6000SetChannel(chandle, 2, 1, 1, chRange, analogOffset, 0)
	assert_pico_ok(status["setChC"])
	status["setChD"] = ps.ps6000SetChannel(chandle, 3, 0, 1, chRange, 0, 0)
	assert_pico_ok(status["setChD"])

	""" Setting up trigger on channel A
	enabled = 1
	source = ChA = 0
	threshold = 26000 ADC counts ~=400mV, see thresholdmV below
	direction = PS6000_FALLING = 3
	delay = 0s
	auto Trigger = 1000ms
	"""
	status["trigger"] = ps.ps6000SetSimpleTrigger(
			chandle, 1, 0, thresholdADC, 3, delaySeconds, autoTrigms
			)
	assert_pico_ok(status["trigger"])

	""" Get timebase info & number of pre/post trigger samples to be collected
	noSamples = maxSamples
	pointer to timeIntervalNanoseconds = byref(timeIntervalns)
	oversample = 1
	pointer to maxSamples = byref(returnedMaxSamples)
	segment index = 0
	timebase = 1 = 400ps
	"""
	timeIntervalns = c_float()
	returnedMaxSamples = c_int32()
	status["getTimebase2"] = ps.ps6000GetTimebase2(
			chandle, timebase, maxSamples, byref(timeIntervalns), 1,
			byref(returnedMaxSamples), 0
			)
	assert_pico_ok(status["getTimebase2"])

	""" Overflow location and converted type maxSamples. """
	overflow = c_int16()
	cmaxSamples = c_int32(maxSamples)

	""" Maximum ADC count value """
	maxADC = c_int16(32512)

	""" Creating data output file and log file if requested """	
	with open(f"./Data/data_{timestamp}.{runtimeOptions['dformat']}", "a") as out:
		out.write("cap\tamplitude (mV)\tpeak2peak (mV)\tcharge (C)\n")

	for icap in range(runtimeOptions["captures"]):
		""" Logging capture """
		if runtimeOptions["log"]:
			log(loghandle, f"==> Beginning capture no. {icap}", time=True)
		
		""" Run block capture
		number of pre-trigger samples = preTrigSamples
		number of post-trigger samples = postTrigSamples
		timebase = 1 = 400ps
		oversample = 0
		time indisposed ms = None (not needed in the example)
		segment index = 0
		lpReady = None (using ps6000IsReady rather than ps6000BlockReady)
		pParameter = None
		"""
		status["runBlock"] = ps.ps6000RunBlock(
				chandle, preTrigSamples, postTrigSamples, timebase, 0, None, 0, None, None
				)
		assert_pico_ok(status["runBlock"])

		""" Check for data collection to finish using ps6000IsReady """
		ready = c_int16(0)
		check = c_int16(0)
		while ready.value == check.value:
			status["isReady"] = ps.ps6000IsReady(chandle, byref(ready))

		""" Create buffers ready for assigning pointers for data collection.
		'bufferXMin' are generally used for downsampling but in our case they're equal
		bufferXMax as we don't need to downsample.
		"""
		bufferAMax = (c_int16 * maxSamples)()
		bufferAMin = (c_int16 * maxSamples)()
		bufferCMax = (c_int16 * maxSamples)()
		bufferCMin = (c_int16 * maxSamples)()

		""" Set data buffers location for data collection from channels A and C.
		sources = ChA, ChC = 0, 2
		pointer to buffers max = byref(bufferXMax)
		pointer to buffers min = byref(bufferXMin)
		buffers length = maxSamples
		ratio mode = PS6000_RATIO_MODE_NONE = 0 
		"""
		status["setDataBuffersA"] = ps.ps6000SetDataBuffers(
				chandle, 0, byref(bufferAMax), byref(bufferAMin), maxSamples, 0
				)
		assert_pico_ok(status["setDataBuffersA"])

		status["setDataBuffersC"] = ps.ps6000SetDataBuffers(
				chandle, 2, byref(bufferCMax), byref(bufferCMin), maxSamples, 0
				)
		assert_pico_ok(status["setDataBuffersC"])		

		""" Retrieve data from scope to buffers assigned above.
		start index = 0
		pointer to number of samples = byref(cmaxSamples)
		downsample ratio = 1
		downsample ratio mode = PS6000_RATIO_MODE_NONE
		pointer to overflow = byref(overflow))
		"""
		status["getValues"] = ps.ps6000GetValues(
				chandle, 0, byref(cmaxSamples), 1, 0, 0, byref(overflow)
				)
		assert_pico_ok(status["getValues"])		

		""" Convert ADC counts data to mV """
		bufferChAmV = adc2mV(bufferAMax, chRange, maxADC)
		bufferChCmV = adc2mV(bufferCMax, chRange, maxADC)

		""" Removing the analog offset from data points """
		thresholdmV = (thresholdADC * chInputRanges[chRange]) / maxADC.value - (analogOffset * 1000)
		for i in range(maxSamples):
			bufferChAmV[i] -= (analogOffset * 1000)
			bufferChCmV[i] -= (analogOffset * 1000)

		""" Create time data """
		time = np.linspace(
				0, (cmaxSamples.value - 1) * timeIntervalns.value, cmaxSamples.value, dtype="float32"
				)

		""" Detect datapoints where the threshold was hit (both falling & rising edge) """
		gateOpen, gateClosed = detect_gate_open_closed(
				bufferChAmV, time, thresholdmV, maxSamples, timeIntervalns.value
				)
		""" Logging threshold hits """
		if runtimeOptions["log"]:
			log(loghandle,
				f"gate on: {gateOpen['mV']:.2f}mV, {gateOpen['ns']:.2f}ns @ {gateOpen['index']}",)
			log(loghandle,
				f"gate off: {gateClosed['mV']:.2f}mV, {gateClosed['ns']:.2f}ns @ {gateClosed['index']}")
	
		""" Calculating relevant data """
		amplitude = abs(min(bufferChCmV))
		peakToPeak = abs(min(bufferChCmV)) - abs(max(bufferChCmV))
		charge = calculate_charge(
				bufferChCmV, gateOpen["index"], gateClosed["index"],
				timeIntervalns.value, terminalResist
				)
		""" Logging capture results """
		if runtimeOptions["log"]:
			log(loghandle, f"amplitude: {amplitude:.2f}mV")
			log(loghandle, f"peak-to-peak: {peakToPeak:.2f}mV")
			log(loghandle, f"charge: {charge:.2f}C")

		""" Print data to file """
		with open(f"./Data/data_{timestamp}.txt", "a") as out:
			out.write(f"{icap + 1}\t{amplitude:.9f}\t{peakToPeak:.9f}\t{charge:.9f}\n")

		if runtimeOptions["plot"]:
			plot_data(
					bufferChAmV, bufferChCmV, gateOpen, gateClosed, timeIntervalns,
					peakToPeak, time, charge, f"{timestamp}_{str(icap)}"
					)

		""" Checking if everything is fine """
		for s in status.values():
			if s != 0:
				print("Something went wrong!")
				print_status(status)
				if runtimeOptions["log"]:
					log(loghandle, "==> (!) Something went wrong! PicoScope status:", time=True)
				sys.exit(1)

	status["stop"] = ps.ps6000Stop(chandle)
	assert_pico_ok(status["stop"])

	""" Close unit & disconnect the scope """
	ps.ps6000CloseUnit(chandle)

	""" Logging exit status & data location """
	if runtimeOptions["log"]:
		log(loghandle, "==> Job finished without errors. Data and/or plots saved to:", time=True)
		log(loghandle, f"{str(Path('~/Documents/pyco-view/Data').expanduser())}")
		log(loghandle, "==> PicoScope exit status:", time=True)
		for key, value in status.items():
			log(loghandle, "{: <15} {: <15}".format(key, value))

#	""" Display status returns """
#	if runtimeOptions["log"]:
#		print_status(status)

if __name__ == "__main__":
	sys.exit(main())
