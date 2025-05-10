""" Copyright (C) 2019 Pico Technology Ltd. """
from ctypes import c_int16, c_uint16, c_int32, c_float, Array, byref
import numpy as np
from picosdk.ps6000 import ps6000 as ps
from pycoviewlib.functions import *
from pycoviewlib.constants import *
import matplotlib.pyplot as plt
from picosdk.functions import adc2mV, assert_pico_ok
from threading import Thread
from datetime import datetime
import sys
from pathlib import Path

# Benchmarking
from time import time as get_time

# Delay error simulation
from fitter import Fitter, get_common_distributions, get_distributions
from statistics import fmean

def plot_data(
		bufferChAmV: Array[c_int16],
		bufferChBmV: Array[c_int16],
		bufferChCmV: Array[c_int16],
		bufferChDmV: Array[c_int16],
		gate: dict,
		delayBounds: tuple,
		time: np.ndarray,
		deltaT: float,
		timeIntervalns: float,
		filestamp: str,
		) -> None:
	buffersMin = min(min(bufferChAmV), min(bufferChBmV), min(bufferChCmV), min(bufferChDmV))
	buffersMax = max(max(bufferChAmV), max(bufferChBmV), max(bufferChCmV), max(bufferChDmV))
	yLowerLim = buffersMin + buffersMin * 0.2
	yUpperLim = buffersMax + buffersMax * 0.4
	# yTicks = np.arange(-1000, 0, 50)

	plt.figure(figsize=(12,6))
		
	""" Channel signals """
	plt.plot(time, bufferChAmV[:],
			 color="blue", label="Channel A (gate)")
	plt.plot(time, bufferChBmV[:],
			 color="red", label="Channel B (gate)")
	plt.plot(time, bufferChCmV[:],
			 color="green", label="Channel C (gate)")
	plt.plot(time, bufferChDmV[:],
			 color="gold", label="Channel D (gate)")
	
	""" Bounds from gate """
	plt.plot([gate["chA"]["open"]["ns"]] * 2,
			 [gate["chA"]["open"]["mV"], yLowerLim],
			 linestyle="--", color="darkblue")
	plt.plot([gate["chA"]["closed"]["ns"]] * 2,
			 [gate["chA"]["closed"]["mV"], yLowerLim],
			 linestyle="--", color="darkblue")

	plt.plot([gate["chB"]["open"]["ns"]] * 2,
			 [gate["chB"]["open"]["mV"], yLowerLim],
			 linestyle="--", color="darkred")
	plt.plot([gate["chB"]["closed"]["ns"]] * 2,
			 [gate["chB"]["closed"]["mV"], yLowerLim],
			 linestyle="--", color="darkred")

	plt.plot([gate["chC"]["open"]["ns"]] * 2,
			 [gate["chC"]["open"]["mV"], yLowerLim],
			 linestyle="--", color="darkgreen")
	plt.plot([gate["chC"]["closed"]["ns"]] * 2,
			 [gate["chC"]["closed"]["mV"], yLowerLim],
			 linestyle="--", color="darkgreen")
	
	plt.plot([gate["chD"]["open"]["ns"]] * 2,
			 [gate["chD"]["open"]["mV"], yLowerLim],
			 linestyle="--", color="goldenrod")
	plt.plot([gate["chD"]["closed"]["ns"]] * 2,
			 [gate["chD"]["closed"]["mV"], yLowerLim],
			 linestyle="--", color="goldenrod")

	plt.fill_between(
			np.arange(delayBounds[0], delayBounds[1], timeIntervalns),
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

	plt.plot(gate["chB"]["open"]["ns"],
			 gate["chB"]["open"]["mV"],
			 color="darkred", marker=">",
			 label=f"Gate B open\n{gate['chB']['open']['ns']:.2f} ns")
	plt.plot(gate["chB"]["closed"]["ns"],
			 gate["chB"]["closed"]["mV"],
			 color="darkred", marker="<",
			 label=f"Gate B closed\n{gate['chB']['closed']['ns']:.2f} ns")

	plt.plot(gate["chC"]["open"]["ns"],
			 gate["chC"]["open"]["mV"],
			 color="darkgreen", marker=">",
			 label=f"Gate C open\n{gate['chC']['open']['ns']:.2f} ns")
	plt.plot(gate["chC"]["closed"]["ns"],
			 gate["chC"]["closed"]["mV"],
			 color="darkgreen", marker="<",
			 label=f"Gate C closed\n{gate['chC']['closed']['ns']:.2f} ns")

	plt.plot(gate["chD"]["open"]["ns"],
			 gate["chD"]["open"]["mV"],
			 color="goldenrod", marker=">",
			 label=f"Gate D open\n{gate['chD']['open']['ns']:.2f} ns")
	plt.plot(gate["chD"]["closed"]["ns"],
			 gate["chD"]["closed"]["mV"],
			 color="goldenrod", marker="<",
			 label=f"Gate D closed\n{gate['chD']['closed']['ns']:.2f} ns")
		
	# """ Threshold line """
	# plt.plot(time.tolist()[bufferChAmV.index(min(bufferChAmV))], min(bufferChAmV), "ko")

	plt.xlabel('Time (ns)')
	plt.ylabel('Voltage (mV)')
	plt.xlim(0, int(max(time)))
	plt.ylim(yLowerLim,yUpperLim)
	plt.legend(loc="lower right")
	plt.savefig(f"./Data/mntm_plot_{filestamp}.png")



def delay_sim_from_file(datahandle: str) -> list:
	oldData = "/home/pi/Documents/pyco-view/delay-sim/mean-timer.txt"	
	with open(oldData, "r") as f:
		data = [float(value) for value in f.readlines()]
	fit = Fitter(data, distributions=['norm'])
	fit.fit()
	sigma = fit.fitted_param['norm'][1]
	with open(datahandle, "r") as f:
		data = [float(line.split()[1]) for line in f.readlines()[1:]]
	mu = fmean(data)
	
	""" normalvariate is thread-safe unlike gauss.
	Subtracting mu to get delay only (approximately) """
	dataSim = [v + (np.random.normal(mu, sigma) - mu) for v in data]
	
	return dataSim

def delay_sim_interactive(value: float, mu: float, sigma: float) -> float:
	newValue = value + (np.random.normal(mu, sigma) - mu)

	return newValue

def make_histogram(data: list) -> None:
	# with open(datahandle, "r") as f:
	#	data = [float(line.split()[1]) for line in f.readlines()[1:]]
	# xrange = (int(min(data)) - 0.5, int(max(data)) + 0.5)
	counts, bins = np.histogram(data, bins="fd")
	plt.hist(bins[:-1], bins, weights=counts, color="lightcoral")
	plt.xlim(0,80)
	plt.ylim(0, max(counts) + 0.2 * max(counts))
	plt.xlabel("Delay (ns)")
	plt.ylabel("Counts")
	plt.show()


def main():
	params: dict = parse_config()
	# print_status(params)

	timestamp: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	
	""" Creating loghandle if required """
	if params["log"] == 1:
		loghandle: str = f"mntm_log_{timestamp}.txt"
	
	""" Creating data folder if not already present """
	try:
		dataPath = Path("~/Documents/pyco-view/Data").expanduser()
		dataPath.mkdir(exist_ok=True)
	except PermissionError:
		print("Permission Error: cannot write to this location.")
		if params["log"] == 1:
			log(loghandle,
	   			f"==> (!) Permission Error: cannot write to {str(dataPath)}.",
	   			time=True)
		sys.exit(1)
	
	""" Creating data output file """	
	datahandle: str = f"./Data/mntm_data_{timestamp}.{params['dformat']}"
	with open(datahandle, "a") as out:
		out.write("cap\t\tdeltaT (ns)\n")
	
	""" Creating chandle and status. Setting acquisition parameters.
	Opening ps6000 connection: returns handle for future use in API functions
	"""
	chandle = c_int16()
	status = {}

	delaySeconds = params["delaySeconds"]
	chRange = params[f"ch{params['target'][0]}range"]
	analogOffset = params[f"ch{params['target'][0]}analogOffset"]
	nTargets = len(params["target"])
	thresholdADC = mV2adc(
			params["thresholdmV"],
			analogOffset,
			chInputRanges[chRange]
			)
	autoTrigms = params["autoTrigms"]
	preTrigSamples = params["preTrigSamples"]
	postTrigSamples = params["postTrigSamples"]
	maxSamples = params["maxSamples"]
	timebase = params["timebase"]
	coupling = couplings[params[f"ch{params['target'][0]}coupling"]][1]

	""" Logging runtime parameters """
	if params["log"] == 1:
		log(loghandle, "==> Running acquisition with parameters:", time=True)
		col_width = max([len(k) for k in params.keys()])
		for key, value in params.items():
			log(loghandle, f"{key: <{col_width}} {value:}")

	status["openUnit"] = ps.ps6000OpenUnit(byref(chandle), None)
	assert_pico_ok(status["openUnit"])

	""" Setting up channels according to `params`
	ps.ps6000SetChannel(
		handle:		chandle
		id:			(A=0, B=1, C=2, D=4)
		enabled:	(yes=1, no=0)
		coupling:	(AC1Mohm=0, DC1Mohm=1, DC50ohm=2)
		range:		see chInputRanges in pycoviewlib/constants.py
		offset:		analog offset (value in volts)
		bandwidth:	(FULL=0, 20MHz=1, 25MHz=2)
	) """
	for id_, name in enumerate(channelIDs):
		status[f"setCh{name}"] = ps.ps6000SetChannel(
				chandle,
				id_,
				params[f"ch{name}enabled"],
				params[f"ch{name}coupling"],
				params[f"ch{name}range"],
				params[f"ch{name}analogOffset"],
				params[f"ch{name}bandwidth"]
				)
		assert_pico_ok(status[f"setCh{name}"])
	
	""" Setting up advanced trigger on target channels.
	ps.ps6000SetTriggerChannelConditions(
		handle:			chandle
		conditions:		TRUE for target channels, DONT_CARE otherwise
		nConditions:	number of ps.PS6000_TRIGGER_CONDITIONS
	)
	ps.TRIGGER_CHANNEL_PROPERTIES(
		threshold:			value in ADC counts
		hysteresisUpper:	0
		thresholdUpper:		0
		hysteresisLower:	0
		channel:			(A=0, B=1, C=2, D=4)
		threshold mode:		(0=LEVEL, 1=WINDOW)
	)
	HYSTERESIS: distance by which signal must fall above/below the
		lower/upper threshold in order to re-arm the trigger.
	ps.ps6000SetTriggerChannelProperties(
		handle:		chandle
		properties:	channelProperties
		auxEnable:	(yes=1, no=0)
		wait for:	value in milliseconds
	) """
	conditions = [PS6000_CONDITION_TRUE if id_ in target else \
		PS6000_CONDITION_DONT_CARE for id_ in channelIDs] \
		+ [PS6000_CONDITION_DONT_CARE] * 3
	triggerConditions = ps.PS6000_TRIGGER_CONDITIONS(*conditions)
	nTrigConditions = 1
	status["setTriggerChannelConditions"] = ps.ps6000SetTriggerChannelConditions(
			chandle, byref(triggerConditions), nTrigConditions
			)
	assert_pico_ok(status["setTriggerChannelConditions"])

	PropertiesArray = ps.PS6000_TRIGGER_CHANNEL_PROPERTIES * nTargets
	properties = [ps.PS6000_TRIGGER_CHANNEL_PROPERTIES(
			thresholdADC, 0, 0, 0, channelIDs.index(t), 0
		) for t in params["target"]]
	channelProperties = PropertiesArray(*properties)
	nChannelProperties = len(properties)
	status["setTriggerChProperties"] = ps.ps6000SetTriggerChannelProperties(
			chandle, byref(channelProperties), nChannelProperties, 0, autoTrigms
			)
	assert_pico_ok(status["setTriggerChProperties"])

	status["setTriggerDelay"] = ps.ps6000SetTriggerDelay(chandle, delaySeconds)
	assert_pico_ok(status["setTriggerDelay"])

	triggerDirections = [PS6000_BELOW if id_ in target else \
		PS6000_NONE for id_ in channelIDs] + [PS6000_NONE] * 2
	status["setTriggerChannelDirections"] = ps.ps6000SetTriggerChannelDirections(
			chandle, *triggerDirections
			)
	assert_pico_ok(status["setTriggerChannelDirections"])

	""" Get timebase info & pre/post trigger samples to be collected
	handle:				chandle
	timebase:			0=200ps, 1=400ps, 2=800ps, ...
	noSamples:			maxSamples
	intervalns:			timeIntervalns
	oversample:			1
	returnedMaxSamples: as the name implies
	segmentIndex:		0
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

	""" Maximum ADC count value (see `constants.py`) """
	cmaxADC = c_int16(maxADC)

	""" Execution time benchmarking (see below) """
	benchmark = [0.0]
	benchmark[0] = get_time()

	""" Matplotlib interactive mode on """
	if runtimeOptions["livehist"]:
		plt.ion()
		data = []

	""" Thread manager waiting for Stop command """
	manager = Manager()
	assistant = Thread(target=manager.listen)
	assistant.start()

	""" Capture counter """
	capcount = 1

	while manager.continue_:
		""" Logging capture """
		if params["log"] == 1:
			log(loghandle, f"==> Beginning capture no. {icap + 1}", time=True)
		
		""" Run block capture
		number of pre-trigger samples = preTrigSamples
		number of post-trigger samples = postTrigSamples
		timebase = 2 = 800ps
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
		to bufferXMax as we don't need to downsample.
		"""
		bufferAMax = (c_int16 * maxSamples)()
		bufferAMin = (c_int16 * maxSamples)()
		bufferBMax = (c_int16 * maxSamples)()
		bufferBMin = (c_int16 * maxSamples)()
		bufferCMax = (c_int16 * maxSamples)()
		bufferCMin = (c_int16 * maxSamples)()
		bufferDMax = (c_int16 * maxSamples)()
		bufferDMin = (c_int16 * maxSamples)()

		""" Set data buffers location for data collection.
		sources = ChA, ChB, ChC, ChD = 0, 1, 2, 3
		pointer to buffers max = byref(bufferXMax)
		pointer to buffers min = byref(bufferXMin)
		buffers length = maxSamples
		ratio mode = PS6000_RATIO_MODE_NONE = 0 
		"""
		status["setDataBuffersA"] = ps.ps6000SetDataBuffers(
				chandle, 0, byref(bufferAMax), byref(bufferAMin), maxSamples, 0
				)
		assert_pico_ok(status["setDataBuffersA"])

		status["setDataBuffersB"] = ps.ps6000SetDataBuffers(
				chandle, 1, byref(bufferBMax), byref(bufferBMin), maxSamples, 0
				)
		assert_pico_ok(status["setDataBuffersB"])

		status["setDataBuffersC"] = ps.ps6000SetDataBuffers(
				chandle, 2, byref(bufferCMax), byref(bufferCMin), maxSamples, 0
				)
		assert_pico_ok(status["setDataBuffersC"])		

		status["setDataBuffersD"] = ps.ps6000SetDataBuffers(
				chandle, 3, byref(bufferDMax), byref(bufferDMin), maxSamples, 0
				)
		assert_pico_ok(status["setDataBuffersD"])

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
		bufferChAmV = adc2mV(bufferAMax, chRange, cmaxADC)
		bufferChBmV = adc2mV(bufferBMax, chRange, cmaxADC)
		bufferChCmV = adc2mV(bufferCMax, chRange, cmaxADC)
		bufferChDmV = adc2mV(bufferDMax, chRange, cmaxADC)

		""" Removing the analog offset from data points """
		thresholdmV = (thresholdADC * chInputRanges[chRange]) / cmaxADC.value - (analogOffset * 1000)
		for i in range(maxSamples):
			bufferChAmV[i] -= (analogOffset * 1000)
			bufferChBmV[i] -= (analogOffset * 1000)
			bufferChCmV[i] -= (analogOffset * 1000)
			bufferChDmV[i] -= (analogOffset * 1000)

		""" Create time data """
		time = np.linspace(
				0, (cmaxSamples.value - 1) * timeIntervalns.value, cmaxSamples.value, dtype="float32"
				)

		""" Detect datapoints where the threshold was hit (both falling & rising edge) """
		gate = {"chA": {}, "chB": {}, "chC": {}, "chD": {}}
		gate["chA"] = detect_gate_open_closed(
				bufferChAmV, time, thresholdmV, maxSamples, timeIntervalns.value
				)
		gate["chB"] = detect_gate_open_closed(
				bufferChBmV, time, thresholdmV, maxSamples, timeIntervalns.value
				)
		gate["chC"] = detect_gate_open_closed(
				bufferChCmV, time, thresholdmV, maxSamples, timeIntervalns.value
				)
		gate["chD"] = detect_gate_open_closed(
				bufferChDmV, time, thresholdmV, maxSamples, timeIntervalns.value
				)
		# Skip current acquisition if trigger timed out
		if gate['chA']['open']['ns'] == 0.0 and gate['chB']['open']['ns'] == 0.0 \
			and gate['chC']['open']['ns'] == 0.0 and gate['chD']['open']['ns'] == 0.0:
			if params['log']:
				log(loghandle, 'Skipping (trigger timeout).')
			continue
		else:
			if params['log']:
				""" Logging threshold hits """
				if params['log']:
					log(loghandle, f"gate A on: {gate['chA']['open']['mV']:.2f}mV, \
						{gate['chA']['open']['ns']:.2f}ns @ {gate['chA']['open']['index']}",)
					log(loghandle, f"gate A off: {gate['chA']['closed']['mV']:.2f}mV, \
						{gate['chA']['closed']['ns']:.2f}ns @ {gate['chA']['closed']['index']}")
					log(loghandle, f"gate B on: {gate['chB']['open']['mV']:.2f}mV, \
						{gate['chB']['open']['ns']:.2f}ns @ {gate['chB']['open']['index']}",)
					log(loghandle, f"gate B off: {gate['chB']['closed']['mV']:.2f}mV, \
						{gate['chB']['closed']['ns']:.2f}ns @ {gate['chB']['closed']['index']}")
					log(loghandle, f"gate C on: {gate['chC']['open']['mV']:.2f}mV, \
						{gate['chC']['open']['ns']:.2f}ns @ {gate['chC']['open']['index']}",)
					log(loghandle, f"gate C off: {gate['chC']['closed']['mV']:.2f}mV, \
						{gate['chC']['closed']['ns']:.2f}ns @ {gate['chC']['closed']['index']}")
					log(loghandle, f"gate D on: {gate['chD']['open']['mV']:.2f}mV, \
						{gate['chD']['open']['ns']:.2f}ns @ {gate['chD']['open']['index']}",)
					log(loghandle, f"gate D off: {gate['chD']['closed']['mV']:.2f}mV, \
						{gate['chD']['closed']['ns']:.2f}ns @ {gate['chD']['closed']['index']}")

		delayBounds = (
				gate["chA"]["open"]["ns"] + (gate["chB"]["open"]["ns"] - gate["chA"]["open"]["ns"]) / 2,
				gate["chC"]["open"]["ns"] + (gate["chD"]["open"]["ns"] - gate["chC"]["open"]["ns"]) / 2
				)
		deltaT = delayBounds[1] - delayBounds[0]
		
		""" Print data to file & plot if requested """
		with open(datahandle, "a") as out:
			out.write(f"{icap + 1}\t\t{deltaT:.9f}\n")
		if params["plot"] == 1:
			""" Create time data """
			time = np.linspace(
					0, (cmaxSamples.value - 1) * timeIntervalns.value, cmaxSamples.value, dtype="float32"
					)
			plot_data(
					bufferChAmV, bufferChBmV, bufferChCmV, bufferChDmV, gate, delayBounds,
					time, deltaT, timeIntervalns.value, f"{timestamp}_{str(icap)}"
					)

		benchmark.append(get_time())

		""" Updating live histogram """
		if runtimeOptions["livehist"]:
			data.append(delay_sim_interactive(value=deltaT, mu=15.808209, sigma=2.953978))
			# counts, bins = np.histogram(data, bins="fd")
			counts, bins = np.histogram(data, range=(0,80), bins=80)
			
			if icap == 0:
				fig, ax = plt.subplots(figsize=(10,6))
				livecounts, livebins, livebars = ax.hist(
					bins[:-1], bins, weights=counts, color="lightcoral"
					) # rwidth=0.95
				ax.set_xlim(0, 80)
				ax.set_ylim(0, runtimeOptions["captures"] * 0.6) # should update this if needed
				ax.set_xlabel("Delay (ns)")
				ax.set_ylabel("Counts")
			
			if icap != runtimeOptions["captures"] - 2:
				_ = [b.remove() for b in livebars]
				livecounts, livebins, livebars = ax.hist(
					bins[:-1], bins, weights=counts, color="lightcoral"
					) # rwidth=0.95
				# ax.set_ylim(0, max(counts) + 0.2 * max(counts))
				# ax.set_xlabel("Delay (ns)")
				# ax.set_ylabel("Counts")
				plt.pause(0.01)
			else:
				plt.ioff()
				plt.show()

		""" Checking if everything is fine """
		if not 0 in status.values():
			manager.continue_ = False
			if params["log"] == 1:
				log(loghandle, "==> Something went wrong! PicoScope status:", time=True)
				col_width = max([len(k) for k in status.keys()])
				for key, value in status.items():
					log(loghandle, f"{key: <{col_width}} {value:}")

		capcount += 1

	assistant.join()

	""" Stop acquisition & close unit """
	status["stop"] = ps.ps6000Stop(chandle)
	assert_pico_ok(status["stop"])
	ps.ps6000CloseUnit(chandle)

	# """ Post-acquisition histogram """
	# if not runtimeOptions["livehist"]:
	# 	dataSim = delay_sim_from_file(datahandle)
	# 	make_histogram(dataSim)
	
	""" Execution time benchmarking """
	avgTime = 0.0
	for i in range(len(benchmark) - 1):
		avgTime += (benchmark[i + 1] - benchmark[i])
	print(f"Total execution time: {avgTime * 1000:.6f} ms")
	avgTime /= (len(benchmark) - 1)
	print(f"Average time per capture: {avgTime * 1000:.6f} ms")
	print(f"Event resolution: {1/avgTime:.1f} Hz")

	""" Logging exit status & data location """
	if params["log"] == 1:
		log(loghandle,
			"==> Job finished without errors. Data and/or plots saved to:", time=True)
		log(loghandle, f"{str(dataPath)}")
		log(loghandle, "==> PicoScope exit status:", time=True)
		col_width = max([len(k) for k in status.keys()])
		for key, value in status.items():
			log(loghandle, f"{key: <{col_width}} {value:}")


if __name__ == "__main__":
	sys.exit(main())
