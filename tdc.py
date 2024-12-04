""" Copyright (C) 2019 Pico Technology Ltd. """
from ctypes import c_int16, c_uint16, c_int32, c_float, Array, byref
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
		) -> dict[str, float | int]:
	"""
	minValueIndex = array index of the buffer's negative peak
		(most negative value).
	Threshold hits are returned as (voltage, time) coordinates.
	"""
	gateChX = {
		"open": {"mV": threshold, "ns": 0.0, "index": 0},
		"closed": {"mV": threshold, "ns": 0.0, "index": 0}
		}
	# gateOpen = {"mV": threshold, "ns": 0.0, "index": 0}
	# gateClosed = {"mV": threshold, "ns": 0.0, "index": 0} 
	hit = 0
	minValueIndex = buffer.index(min(buffer))
	minDifference = min(buffer) - threshold
	for i in range(minValueIndex):
		if abs(buffer[i] - threshold) < abs(minDifference):
			hit = i
			minDifference = buffer[i] - threshold
	gateChX["open"]["ns"] = time[hit]
	gateChX["open"]["index"] = hit
	# gateOpen["ns"] = time[hit]
	# gateOpen["index"] = hit
	minDifference = min(buffer) - threshold
	for i in range(minValueIndex, maxSamples):
		if abs(buffer[i] - threshold) < abs(minDifference):
			hit = i
			minDifference = buffer[i] - threshold
	gateChX["closed"]["ns"] = time[hit]
	gateChX["closed"]["index"] = hit
	
	return gateChX

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
		gate: dict,
		time: np.ndarray,
		deltaT: float,
		timeIntervalns: float,
		filestamp: str,
		) -> None:
	buffersMin = min(min(bufferChAmV), min(bufferChCmV))
	buffersMax = max(max(bufferChAmV), max(bufferChCmV))
	yLowerLim = buffersMin + buffersMin * 0.2
	yUpperLim = buffersMax + buffersMax * 0.4
	# yTicks = np.arange(-1000, 0, 50)

	plt.figure(figsize=(10,6))
		
	""" Channel signals """
	plt.plot(time, bufferChAmV[:],
			 color="blue", label="Channel A (gate)")
	plt.plot(time, bufferChCmV[:],
			 color="green", label="Channel C (gate)")
	
	""" Bounds from gate """
	plt.plot([gate["chA"]["open"]["ns"]] * 2,
			 [gate["chA"]["open"]["mV"], yLowerLim],
			 linestyle="--", color="darkblue")
	plt.plot([gate["chA"]["closed"]["ns"]] * 2,
			 [gate["chA"]["closed"]["mV"], yLowerLim],
			 linestyle="--", color="darkblue")

	plt.plot([gate["chC"]["open"]["ns"]] * 2,
			 [gate["chC"]["open"]["mV"], yLowerLim],
			 linestyle="--", color="darkgreen")
	plt.plot([gate["chC"]["closed"]["ns"]] * 2,
			 [gate["chC"]["closed"]["mV"], yLowerLim],
			 linestyle="--", color="darkgreen")

	plt.fill_between(
			np.arange(gate["chA"]["open"]["ns"], gate["chC"]["open"]["ns"], timeIntervalns),
			yLowerLim, yUpperLim,
			color="lightgrey", label=f"Delay\n{deltaT:.2f} ns"
			)
	
	# """ Threshold """
	# plt.axhline(y=thresholdmV, linestyle="--", color="black",
	#			label=f"Channel A threshold\n{thresholdmV:.2f} mV")
	
	""" Gate open and closed points """
	plt.plot(gate["chA"]["open"]["ns"],
			 gate["chA"]["open"]["mV"],
			 color="darkblue", marker=">",
			 label=f"Gate A open\n{gate['chA']['open']['ns']:.2f} ns")
	plt.plot(gate["chA"]["closed"]["ns"],
			 gate["chA"]["closed"]["mV"],
			 color="darkblue", marker="<",
			 label=f"Gate A closed\n{gate['chA']['closed']['ns']:.2f} ns")

	plt.plot(gate["chC"]["open"]["ns"],
			 gate["chC"]["open"]["mV"],
			 color="darkgreen", marker=">",
			 label=f"Gate C open\n{gate['chC']['open']['ns']:.2f} ns")
	plt.plot(gate["chC"]["closed"]["ns"],
			 gate["chC"]["closed"]["mV"],
			 color="darkgreen", marker="<",
			 label=f"Gate C closed\n{gate['chC']['closed']['ns']:.2f} ns")
		
	# """ Threshold line """
	# plt.plot(time.tolist()[bufferChAmV.index(min(bufferChAmV))], min(bufferChAmV), "ko")

	plt.xlabel('Time (ns)')
	plt.ylabel('Voltage (mV)')
	plt.xlim(0, int(max(time)))
	plt.ylim(yLowerLim,yUpperLim)
	plt.legend(loc="lower right")
	plt.savefig(f"./Data/tdc_plot_{filestamp}.png")

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
				break
			else:
				options["captures"] = 1
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
		loghandle: str = f"tdc_log_{timestamp}.txt"
	
	""" Creating data folder if not already present """
	try:
		dataPath = Path("~/Documents/pyco-view/Data").expanduser()
		dataPath.mkdir(exist_ok=True)
	except PermissionError:
		print("Permission Error: cannot write to this location.")
		if runtimeOptions["log"]:
			log(loghandle,
	   			f"==> (!) Permission Error: cannot write to {str(dataPath)}.",
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
	preTrigSamples = 100
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
		colWidth = max([len(k) for k in params.keys()])
		for key, value in params.items():
			log(loghandle, f"{key: <{colWidth}} {value:}")

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
	
	""" Setting up trigger on channel A and C
	conditions = TRUE for A and C, DONT_CARE otherwise
		(i.e. both must be triggered at the same time)
	nTrigConditions = 2
	channel directions = FALLING (both)
	threshold = 15000 ADC counts ~=-300mV (both)
	hysteresis = 1.5% of thresholdADC
		(distance by which signal must fall above/below the
		lower/upper threshold in order to re-arm the trigger)
	auto Trigger = 10000ms (both)
	delay = 0s (both)
	"""
	triggerConditions = ps.PS6000_TRIGGER_CONDITIONS(
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_TRUE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_TRUE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"]
			)
	nTrigConditions = 1

	status["setTriggerChannelConditions"] = ps.ps6000SetTriggerChannelConditions(
			chandle, byref(triggerConditions), nTrigConditions
			)
	assert_pico_ok(status["setTriggerChannelConditions"])

	# hysteresis = c_uint16(int(thresholdADC * 0.015))
	Properties = ps.PS6000_TRIGGER_CHANNEL_PROPERTIES * 2
	channelProperties = Properties(
			ps.PS6000_TRIGGER_CHANNEL_PROPERTIES(
				thresholdADC,
				0,	# hysteresis,
				0,	# (thresholdADC * -1),
				0,	# hysteresis,
				ps.PS6000_CHANNEL["PS6000_CHANNEL_A"],
				ps.PS6000_THRESHOLD_MODE["PS6000_LEVEL"]
				),
			ps.PS6000_TRIGGER_CHANNEL_PROPERTIES(
				thresholdADC,
				0,	# hysteresis,
				0,	# (thresholdADC * -1),
				0,	# hysteresis,
				ps.PS6000_CHANNEL["PS6000_CHANNEL_C"],
				ps.PS6000_THRESHOLD_MODE["PS6000_LEVEL"]
				)
			)
	nChannelProperties = 2
	status["setTriggerChProperties"] = ps.ps6000SetTriggerChannelProperties(
			chandle, byref(channelProperties), nChannelProperties, 0, autoTrigms
			)
	assert_pico_ok(status["setTriggerChProperties"])

	status["setTriggerDelay"] = ps.ps6000SetTriggerDelay(chandle, delaySeconds)
	assert_pico_ok(status["setTriggerDelay"])

	status["setTriggerChannelDirections"] = ps.ps6000SetTriggerChannelDirections(
			chandle, 
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_BELOW"],
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_NONE"],
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_BELOW"],
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_NONE"], 
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_NONE"],
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_NONE"]
			)
	assert_pico_ok(status["setTriggerChannelDirections"])
	
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

	""" Creating data output file """	
	with open(f"./Data/tdc_data_{timestamp}.{runtimeOptions['dformat']}", "a") as out:
		out.write("cap\tdeltaT (ns)\n")

	for icap in range(runtimeOptions["captures"]):
		""" Logging capture """
		if runtimeOptions["log"]:
			log(loghandle, f"==> Beginning capture no. {icap + 1}", time=True)
		
		""" Run block capture
		number of pre-trigger samples = preTrigSamples
		number of post-trigger samples = postTrigSamples
		timebase = 1 = 400ps
		oversample = 0
		time indisposed ms = None
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
		gate = {"chA": {}, "chC": {}}
		gate["chA"] = detect_gate_open_closed(
				bufferChAmV, time, thresholdmV, maxSamples, timeIntervalns.value
				)
		gate["chC"] = detect_gate_open_closed(
				bufferChCmV, time, thresholdmV, maxSamples, timeIntervalns.value
				)
		""" Logging threshold hits """
		if runtimeOptions["log"]:
			log(loghandle,
				f"gate on: {gate['chA']['open']['mV']:.2f}mV, {gate['chA']['open']['ns']:.2f}ns @ {gate['chA']['open']['index']}",)
			log(loghandle,
				f"gate off: {gate['chA']['closed']['mV']:.2f}mV, {gate['chA']['closed']['ns']:.2f}ns @ {gate['chA']['closed']['index']}")

		deltaT = gate["chC"]["open"]["ns"] - gate["chA"]["open"]["ns"]
		""" Print data to file """
		with open(f"./Data/tdc_data_{timestamp}.txt", "a") as out:
			out.write(f"{icap + 1}\t{deltaT:.9f}\n")

		if runtimeOptions["plot"]:
			plot_data(
					bufferChAmV, bufferChCmV, gate, time, deltaT, timeIntervalns.value,
					f"{timestamp}_{str(icap)}"
					)

		""" Checking if everything is fine """
		if not 0 in status.values():
			""" Logging error(s) """
			if runtimeOptions["log"]:
				log(loghandle, "==> Something went wrong! PicoScope status:", time=True)
				colWidth = max([len(k) for k in status.keys()])
				for key, value in status.items():
					log(loghandle, f"{key: <{colWidth}} {value:}")
			sys.exit(1)

	status["stop"] = ps.ps6000Stop(chandle)
	assert_pico_ok(status["stop"])

	""" Close unit & disconnect the scope """
	ps.ps6000CloseUnit(chandle)

	""" Logging exit status & data location """
	if runtimeOptions["log"]:
		log(loghandle,
			"==> Job finished without errors. Data and/or plots saved to:", time=True)
		log(loghandle, f"{str(dataPath)}")
		log(loghandle, "==> PicoScope exit status:", time=True)
		colWidth = max([len(k) for k in status.keys()])
		for key, value in status.items():
			log(loghandle, f"{key: <{colWidth}} {value:}")


if __name__ == "__main__":
	sys.exit(main())
