""" Copyright (C) 2019 Pico Technology Ltd. """
from picosdk.ps6000 import ps6000 as ps
from picosdk.functions import adc2mV, assert_pico_ok
from pycoviewlib.functions import log, detect_gate_open_closed, parse_config, mV2adc, DataPack
from pycoviewlib.constants import (
		PV_DIR, chInputRanges, maxADC, channelIDs, PS6000_CONDITION_TRUE, PS6000_CONDITION_DONT_CARE,
		PS6000_BELOW, PS6000_NONE
		)
from ctypes import c_int16, c_int32, c_float, Array, byref
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime as dt
from threading import Thread
import sys
from pathlib import Path
import pickle

# Benchmarking
from time import time as get_time

# Delay error simulation
# from fitter import Fitter, get_common_distributions, get_distributions
# from statistics import fmean

class Manager():
	def __init__(self):
		self.keystroke = "q"
		self.continue_ = True
	
	def listen(self):
		event = input("")
		if event == self.keystroke:
			self.continue_ = False

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
	counts, bins = np.histogram(data, bins="fd")
	plt.hist(bins[:-1], bins, weights=counts, color="black")
	plt.xlim(0, 80)
	plt.ylim(0, max(counts) + 0.2 * max(counts))
	plt.xlabel("Delay (ns)")
	plt.ylabel("Counts")
	plt.show()

class Benchmark:
	def __init__(self):
		self.stopwatch = [get_time()]
		self.convert = {"ms": 1000, "µs": 1000000}

	def split(self):
		self.stopwatch.append(get_time())

	def results(self, unit="ms"):
		avg = .0
		for i in range(len(self.stopwatch) - 1):
			avg += (self.stopwatch[i + 1] - self.stopwatch[i])
		print(f"Total execution time: {dt.strftime(dt.utcfromtimestamp(avg), '%T.%f')[:-3]}")
		avg /= (len(self.stopwatch) - 1)
		print(f"Average time per capture: {avg * self.convert[unit]:.1f} {unit}")
		print(f"Event resolution: {1/avg:.1f} Hz")

def main():
	global params
	params = parse_config()

	timestamp = dt.now().strftime("%Y-%m-%d_%H-%M-%S")

	analogOffset = params['chAanalogOffset']
	target = params['target']
	nTargets = len(params['target'])
	chRange = params[f'ch{target[0]}range']
	thresholdADC = mV2adc(
			params['thresholdmV'],
			analogOffset,
			chInputRanges[chRange]
			)

	""" Creating loghandle if required """
	if params['log']:
		loghandle: str = f"tdc_log_{timestamp}.txt"

	""" Creating data folder if not already present """
	try:
		dataPath = Path(f'{PV_DIR}/Data').expanduser()
		dataPath.mkdir(exist_ok=True)
	except PermissionError:
		print('Permission Error: cannot write to this location.')
		if params['log']:
			log(loghandle, f'==> (!) Permission Error: cannot write to {str(dataPath)}.', time=True)
		sys.exit(1)

	""" Creating data output file """
	datahandle: str = f"./Data/tdc_data_{timestamp}.{params['dformat']}"
	with open(datahandle, "a") as out:
		out.write("cap\t\tdeltaT (ns)\n")

	""" Logging runtime parameters """
	if params['log'] == 1:
		log(loghandle, '==> Running acquisition with parameters:', time=True)
		col_width = max([len(k) for k in params.keys()])
		for key, value in params.items():
			log(loghandle, f'{key: <{col_width}} {value:}')

	""" Creating chandle and status. Setting acquisition parameters.
	Opening ps6000 connection: returns handle for future use in API functions
	"""
	chandle = c_int16()
	status = {}

	status['openUnit'] = ps.ps6000OpenUnit(byref(chandle), None)
	assert_pico_ok(status['openUnit'])

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
		status[f'setCh{name}'] = ps.ps6000SetChannel(
				chandle,
				id_,
				params[f'ch{name}enabled'],
				params[f'ch{name}coupling'],
				params[f'ch{name}range'],
				params[f'ch{name}analogOffset'],
				params[f'ch{name}bandwidth']
				)
		assert_pico_ok(status[f'setCh{name}'])

	""" Setting up trigger on channel A and C
	conditions = TRUE for A and C, DONT_CARE otherwise
		(i.e. both must be triggered at the same time)
	nTrigConditions = 2
	channel directions = FALLING (both)
	threshold = 15000 ADC counts ~=-300mV (both)
	auto Trigger = 5000ms (both)
	delay = 0s (both)
	"""
	conditions = [PS6000_CONDITION_TRUE if id_ in target else \
			PS6000_CONDITION_DONT_CARE for id_ in channelIDs] \
			+ [PS6000_CONDITION_DONT_CARE] * 3
	triggerConditions = ps.PS6000_TRIGGER_CONDITIONS(*conditions)
	nTrigConditions = 1
	status['setTriggerChConditions'] = ps.ps6000SetTriggerChannelConditions(
			chandle, byref(triggerConditions), nTrigConditions
			)
	assert_pico_ok(status['setTriggerChConditions'])

	PropertiesArray = ps.PS6000_TRIGGER_CHANNEL_PROPERTIES * nTargets
	properties = [ps.PS6000_TRIGGER_CHANNEL_PROPERTIES(
			thresholdADC, 0, 0, 0, channelIDs.index(t), 0
		) for t in params["target"]]
	channelProperties = PropertiesArray(*properties)
	nChannelProperties = len(properties)
	status['setTriggerChProperties'] = ps.ps6000SetTriggerChannelProperties(
			chandle, byref(channelProperties), nChannelProperties, 0, params['autoTrigms']
			)
	assert_pico_ok(status['setTriggerChProperties'])

	status['setTriggerDelay'] = ps.ps6000SetTriggerDelay(chandle, params['delaySeconds'])
	assert_pico_ok(status['setTriggerDelay'])

	triggerDirections = [PS6000_BELOW if id_ in target else \
			PS6000_NONE for id_ in channelIDs] + [PS6000_NONE] * 2
	status['setTriggerChannelDirections'] = ps.ps6000SetTriggerChannelDirections(
			chandle, *triggerDirections
			)
	assert_pico_ok(status['setTriggerChannelDirections'])

	""" Get params["timebase"] info & number of pre/post trigger samples to be collected
	noSamples = params["maxSamples"]
	pointer to timeIntervalNanoseconds = byref(timeIntervalns)
	oversample = 1
	pointer to params["maxSamples"] = byref(returnedMaxSamples)
	segment index = 0
	timebase = 1 = 400ps
	"""
	timeIntervalns = c_float()
	returnedMaxSamples = c_int32()
	status['getTimebase2'] = ps.ps6000GetTimebase2(
			chandle, params['timebase'], params['maxSamples'], byref(timeIntervalns), 1,
			byref(returnedMaxSamples), 0
			)
	assert_pico_ok(status['getTimebase2'])

	""" Overflow location and converted type maxSamples """
	overflow = c_int16()
	cmaxSamples = c_int32(params['maxSamples'])

	""" Maximum ADC count value """
	cmaxADC = c_int16(maxADC)

	""" Matplotlib interactive mode on """
	# plt.ion()
	# data = []
	data_pack = DataPack()

	""" Benchmarking """
	# benchmark = Benchmark()

	""" Thread manager waiting for Stop command """
	manager = Manager()
	assistant = Thread(target=manager.listen)
	assistant.start()

	""" Capture counter """
	capcount = 1

	while manager.continue_:
		""" Logging capture """
		if params['log']:
			log(loghandle, f'==> Beginning capture no. {capcount}', time=True)

		""" Run block capture
		number of pre-trigger samples = params["preTrigSamples"]
		number of post-trigger samples = params["postTrigSamples"]
		timebase = 1 = 400ps
		oversample = 0
		time indisposed ms = None
		segment index = 0
		lpReady = None (using ps6000IsReady rather than ps6000BlockReady)
		pParameter = None
		"""
		status['runBlock'] = ps.ps6000RunBlock(
				chandle, params['preTrigSamples'], params['postTrigSamples'],
				params['timebase'], 0, None, 0, None, None
				)
		assert_pico_ok(status['runBlock'])

		""" Check for data collection to finish using ps6000IsReady """
		ready = c_int16(0)
		check = c_int16(0)
		while ready.value == check.value:
			status['isReady'] = ps.ps6000IsReady(chandle, byref(ready))

		""" Create buffers ready for assigning pointers for data collection.
		'bufferXMin' are generally used for downsampling but in our case they're equal
		bufferXMax as we don't need to downsample.
		"""
		bufferAMax = (c_int16 * params['maxSamples'])()
		bufferAMin = (c_int16 * params['maxSamples'])()
		bufferCMax = (c_int16 * params['maxSamples'])()
		bufferCMin = (c_int16 * params['maxSamples'])()

		""" Set data buffers location for data collection from channels A and C.
		sources = ChA, ChC = 0, 2
		pointer to buffers max = byref(bufferXMax)
		pointer to buffers min = byref(bufferXMin)
		buffers length = params["maxSamples"]
		ratio mode = PS6000_RATIO_MODE_NONE = 0
		"""
		status['setDataBuffersA'] = ps.ps6000SetDataBuffers(
				chandle, 0, byref(bufferAMax), byref(bufferAMin), params['maxSamples'], 0
				)
		assert_pico_ok(status['setDataBuffersA'])

		status['setDataBuffersC'] = ps.ps6000SetDataBuffers(
				chandle, 2, byref(bufferCMax), byref(bufferCMin), params['maxSamples'], 0
				)
		assert_pico_ok(status['setDataBuffersC'])

		""" Retrieve data from scope to buffers assigned above.
		start index = 0
		pointer to number of samples = byref(cmaxSamples)
		downsample ratio = 1
		downsample ratio mode = PS6000_RATIO_MODE_NONE
		pointer to overflow = byref(overflow)
		"""
		status["getValues"] = ps.ps6000GetValues(
				chandle, 0, byref(cmaxSamples), 1, 0, 0, byref(overflow)
				)
		assert_pico_ok(status["getValues"])

		""" Convert ADC counts data to mV """
		bufferChAmV = adc2mV(bufferAMax, chRange, cmaxADC)
		bufferChCmV = adc2mV(bufferCMax, chRange, cmaxADC)

		""" Removing the analog offset from data points """
		thresholdmV = (thresholdADC * chInputRanges[chRange]) \
				/ cmaxADC.value - (analogOffset * 1000)
		for i in range(params['maxSamples']):
			bufferChAmV[i] -= (analogOffset * 1000)
			bufferChCmV[i] -= (analogOffset * 1000)

		""" Create time data """
		time = np.linspace(
				0, (cmaxSamples.value - 1) * timeIntervalns.value,
				cmaxSamples.value, dtype='float32'
				)

		""" Detect where the threshold was hit (both falling & rising edge) """
		gate = {'chA': {}, 'chC': {}}
		gate['chA'] = detect_gate_open_closed(
				bufferChAmV, time, thresholdmV, params['maxSamples'], timeIntervalns.value
				)
		gate['chC'] = detect_gate_open_closed(
				bufferChCmV, time, thresholdmV, params['maxSamples'], timeIntervalns.value
				)
		# Skip current acquisition if trigger timed out
		if gate['chA']['open']['ns'] == 0.0 and gate['chC']['open']['ns'] == 0.0:
			if params['log']:
				log(loghandle, 'Skipping (trigger timeout).')
			continue
		else:
			if params['log']:
				""" Logging threshold hits """
				if params['log']:
					log(loghandle, f"gate on: {gate['chA']['open']['mV']:.2f}mV, \
							{gate['chA']['open']['ns']:.2f}ns @ {gate['chA']['open']['index']}",)
					log(loghandle, f"gate off: {gate['chA']['closed']['mV']:.2f}mV, \
							{gate['chA']['closed']['ns']:.2f}ns @ {gate['chA']['closed']['index']}")

		""" Calculating relevant data """
		deltaT = gate['chC']['open']['ns'] - gate['chA']['open']['ns']
		data_pack.x = deltaT
		with open(f'pickles/plot{capcount}.pkl', 'wb') as pkl:
			pickle.dump(data_pack, pkl)

		""" Print data to file """
		with open(f'{PV_DIR}/Data/tdc_data_{timestamp}.txt', 'a') as out:
			out.write(f'{capcount}\t{deltaT:.9f}\n')

		if params['plot']:
			plot_data(
					bufferChAmV, bufferChCmV, gate, time, deltaT,
					timeIntervalns.value, f'{timestamp}_{capcount}'
					)

		# """ Updating live histogram """
		# # data.append(delay_sim_interactive(value=deltaT, mu=15.808209, sigma=2.953978))
		# # counts, bins = np.histogram(data, bins="fd")
		# data.append(deltaT)

		# if capcount == 1:
		# 	fig, ax = plt.subplots(figsize=(10, 6), layout='tight')
		# 	ax.set_xlim(0, 80)
		# 	ax.set_ylim(0, 15)
		# 	ax.set_yticks(
		# 			ticks=list(range(0, 15 + 5, 5)),
		# 			labels=[f'{lbl}' for lbl in range(0, 15 + 5, 5)]
		# 			)
		# 	ax.set_xlabel('Delay (ns)')
		# 	ax.set_ylabel('Counts')

		# if ax.patches and capcount % 5 == 0:
		# 	_ = [b.remove() for b in ax.patches]

		# if capcount % 5 == 0:
		# 	counts, bins = np.histogram(data, range=(0, 80), bins=100)
		# 	ax.stairs(counts, bins, color='tab:blue', fill=True)
		# 	yUpperLim = int(ax.get_ylim()[1])
		# 	if np.max(counts) > yUpperLim * 0.95:
		# 		if yUpperLim < 50:
		# 			yLimNudge = 5
		# 		elif yUpperLim in range(50, 100):
		# 			yLimNudge = 10
		# 		elif yUpperLim in range(100, 200):
		# 			yLimNudge = 20
		# 		elif yUpperLim >= 200:
		# 			yLimNudge = 25
		# 		ax.set_ylim(0, yUpperLim + yLimNudge)
		# 		ax.set_yticks(
		# 				ticks=list(range(0, yUpperLim + 2 * yLimNudge, yLimNudge)),
		# 				labels=[f'{lbl}' for lbl in range(0, yUpperLim + 2 * yLimNudge, yLimNudge)]
		# 				)
		# 	plt.pause(0.0001)

		# print(f'Capture no. {capcount}')
		capcount += 1
		# benchmark.split()

		""" Checking if everything is fine """
		if not 0 in status.values():
			""" Logging error(s) """
			if params['log']:
				log(loghandle, '==> Something went wrong! PicoScope status:', time=True)
				colWidth = max([len(k) for k in status.keys()])
				for key, value in status.items():
					log(loghandle, f'{key: <{colWidth}} {value:}')
			break

	# plt.ioff()
	# plt.show()

	""" Stop acquisition """
	status["stop"] = ps.ps6000Stop(chandle)
	assert_pico_ok(status['stop'])

	""" Close unit & disconnect the scope """
	ps.ps6000CloseUnit(chandle)

	""" Post-acquisition histogram """
	# if not runtimeOptions["livehist"]:
	# 	dataSim = delay_sim_from_file(datahandle)
	# 	make_histogram(dataSim)

	""" Benchmark results """
	# benchmark.results()

	""" Logging exit status & data location """
	if params["log"] == 1:
		log(loghandle, '==> Job finished without errors. Data and/or plots saved to:', time=True)
		log(loghandle, f"{str(dataPath)}")
		log(loghandle, "==> PicoScope exit status:", time=True)
		col_width = max([len(k) for k in status.keys()])
		for key, value in status.items():
			log(loghandle, f'{key: <{col_width}} {value:}')


if __name__ == '__main__':
	sys.exit(main())
