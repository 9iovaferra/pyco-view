""" Copyright (C) 2019 Pico Technology Ltd. """
from picosdk.ps6000 import ps6000 as ps
from picosdk.functions import adc2mV, assert_pico_ok
from picosdk.errors import PicoSDKCtypesError
from picosdk.constants import PICO_STATUS_LOOKUP
from pycoviewlib.functions import log, detect_gate_open_closed, mV2adc
from pycoviewlib.constants import (
		PV_DIR, chInputRanges, maxADC, channelIDs, PS6000_CONDITION_TRUE, PS6000_CONDITION_DONT_CARE,
		PS6000_BELOW, PS6000_NONE
		)
from ctypes import c_int16, c_int32, c_float, Array, byref
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Union

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

	plt.figure(figsize=(10, 6))

	""" Channel signals """
	plt.plot(time, bufferChAmV[:], color="blue", label="Channel A (gate)")
	plt.plot(time, bufferChCmV[:], color="green", label="Channel C (gate)")

	""" Bounds from gate """
	plt.plot(
		[gate["chA"]["open"]["ns"]] * 2, [gate["chA"]["open"]["mV"], yLowerLim],
		linestyle="--", color="darkblue"
		)
	plt.plot(
		[gate["chA"]["closed"]["ns"]] * 2, [gate["chA"]["closed"]["mV"], yLowerLim],
		linestyle="--", color="darkblue"
		)

	plt.plot(
		[gate["chC"]["open"]["ns"]] * 2, [gate["chC"]["open"]["mV"], yLowerLim],
		linestyle="--", color="darkgreen"
		)
	plt.plot(
		[gate["chC"]["closed"]["ns"]] * 2, [gate["chC"]["closed"]["mV"], yLowerLim],
		linestyle="--", color="darkgreen"
		)

	plt.fill_between(
			np.arange(gate["chA"]["open"]["ns"], gate["chC"]["open"]["ns"], timeIntervalns),
			yLowerLim, yUpperLim,
			color="lightgrey", label=f"Delay\n{deltaT:.2f} ns"
			)

	# """ Threshold """
	# plt.axhline(
	# 	y=thresholdmV, linestyle="--", color="black",
	# 	label=f"Channel A threshold\n{thresholdmV:.2f} mV"
	# )

	""" Gate open and closed points """
	plt.plot(
		gate["chA"]["open"]["ns"], gate["chA"]["open"]["mV"],
		color="darkblue", marker=">",
		label=f"Gate A open\n{gate['chA']['open']['ns']:.2f} ns"
		)
	plt.plot(
		gate["chA"]["closed"]["ns"], gate["chA"]["closed"]["mV"],
		color="darkblue", marker="<",
		label=f"Gate A closed\n{gate['chA']['closed']['ns']:.2f} ns"
		)

	plt.plot(
		gate["chC"]["open"]["ns"], gate["chC"]["open"]["mV"],
		color="darkgreen", marker=">",
		label=f"Gate C open\n{gate['chC']['open']['ns']:.2f} ns"
		)
	plt.plot(
		gate["chC"]["closed"]["ns"], gate["chC"]["closed"]["mV"],
		color="darkgreen", marker="<",
		label=f"Gate C closed\n{gate['chC']['closed']['ns']:.2f} ns"
		)

	# """ Threshold line """
	# plt.plot(time.tolist()[bufferChAmV.index(min(bufferChAmV))], min(bufferChAmV), "ko")

	plt.xlabel('Time (ns)')
	plt.ylabel('Voltage (mV)')
	plt.xlim(0, int(max(time)))
	plt.ylim(yLowerLim, yUpperLim)
	plt.legend(loc="lower right")
	plt.savefig(f"./Data/tdc_plot_{filestamp}.png")


class TDC:
	def __init__(self, params: dict[str, Union[int, float, str]]):
		self.params = params
		self.timestamp: str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
		if self.params['log']:  # Creating loghandle if required
			self.loghandle: str = f'tdc_log_{self.timestamp}.txt'
		self.datahandle: str = f"{PV_DIR}/Data/tdc_data_{self.timestamp}.{self.params['dformat']}"

		self.chandle = c_int16()
		self.status = {}

		self.analogOffset = params['chAanalogOffset']
		self.target = params['target']
		self.nTargets = len(params['target'])
		self.chRange = params[f'ch{self.target[0]}range']
		self.thresholdADC = mV2adc(
				params['thresholdmV'],
				self.analogOffset,
				chInputRanges[self.chRange]
				)
		self.autoTrigms = params['autoTrigms']
		self.preTrigSamples = params['preTrigSamples']
		self.postTrigSamples = params['postTrigSamples']
		self.maxSamples = params['maxSamples']
		self.timebase = params['timebase']
		self.delaySeconds = params['delaySeconds']

		self.overflow = c_int16()  # Overflow location
		self.cmaxSamples = c_int32(self.maxSamples)  # Converted type maxSamples
		self.cmaxADC = c_int16(maxADC)  # Converted maxADC count

		self.count = 1  # Capture counter

	def __check_health(self, status: hex, stop: bool = False) -> str | None:
		try:
			assert_pico_ok(status)
		except PicoSDKCtypesError:
			if stop:
				self.status['stop'] = ps.ps6000Stop(self.chandle)
				self.__check_health(self.status['stop'])
			ps.ps6000CloseUnit(self.chandle)
			return f'{PICO_STATUS_LOOKUP[status]}'
		return None

	def setup(self) -> str | None:
		""" Logging runtime parameters """
		if self.params['log']:
			log(self.loghandle, '==> Running acquisition with parameters:', time=True)
			col_width = max([len(k) for k in self.params.keys()])
			for key, value in self.params.items():
				log(self.loghandle, f'{key: <{col_width}} {value:}')

		with open(self.datahandle, "a") as out:  # Creating data output file
			out.write("n\t\tdeltaT (ns)\n")

		""" Opening ps6000 connection: returns handle for future use in API functions """
		self.status['openUnit'] = ps.ps6000OpenUnit(byref(self.chandle), None)
		err = err = self.__check_health(self.status['openUnit'])
		if err is not None:
			return err

		""" Setting up channels according to `self.params`
		ps.ps6000SetChannel(
			handle:		chandle
			id:			(A=0, B=1, C=2, D=4)
			enabled:	(yes=1, no=0)
			coupling:	(AC1Mohm=0, DC1Mohm=1, DC50ohm=2)
			range:		see chInputRanges in pycoviewlib/constants.py
			offset:		analog offset (value in volts)
			bandwidth:	(FULL=0, 20MHz=1, 25MHz=2)
		) """
		for id, name in enumerate(channelIDs):
			self.status[f'setCh{name}'] = ps.ps6000SetChannel(
					self.chandle,
					id,
					self.params[f'ch{name}enabled'],
					self.params[f'ch{name}coupling'],
					self.params[f'ch{name}range'],
					self.params[f'ch{name}analogOffset'],
					self.params[f'ch{name}bandwidth']
					)
			err = self.__check_health(self.status[f'setCh{name}'])
			if err is not None:
				return err

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
		conditions = [
			PS6000_CONDITION_TRUE if id in self.target else PS6000_CONDITION_DONT_CARE for id in channelIDs
			] + [PS6000_CONDITION_DONT_CARE] * 3
		triggerConditions = ps.PS6000_TRIGGER_CONDITIONS(*conditions)
		nTrigConditions = 1
		self.status['setTriggerChConditions'] = ps.ps6000SetTriggerChannelConditions(
				self.chandle, byref(triggerConditions), nTrigConditions
				)
		err = self.__check_health(self.status['setTriggerChConditions'])
		if err is not None:
			return err

		PropertiesArray = ps.PS6000_TRIGGER_CHANNEL_PROPERTIES * self.nTargets
		properties = [ps.PS6000_TRIGGER_CHANNEL_PROPERTIES(
				self.thresholdADC, 0, 0, 0, channelIDs.index(t), 0
				) for t in self.params["target"]]
		channelProperties = PropertiesArray(*properties)
		nChannelProperties = len(properties)
		self.status['setTriggerChProperties'] = ps.ps6000SetTriggerChannelProperties(
				self.chandle, byref(channelProperties), nChannelProperties, 0, self.autoTrigms
				)
		err = self.__check_health(self.status['setTriggerChProperties'])
		if err is not None:
			return err

		self.status['setTriggerDelay'] = ps.ps6000SetTriggerDelay(self.chandle, self.delaySeconds)
		err = self.__check_health(self.status['setTriggerDelay'])
		if err is not None:
			return err

		triggerDirections = [
				PS6000_BELOW if id in self.target else PS6000_NONE for id in channelIDs
				] + [PS6000_NONE] * 2
		self.status['setTriggerChannelDirections'] = ps.ps6000SetTriggerChannelDirections(
				self.chandle, *triggerDirections
				)
		err = self.__check_health(self.status['setTriggerChannelDirections'])
		if err is not None:
			return err

		""" Get params["timebase"] info & number of pre/post trigger samples to be collected
		noSamples = params["maxSamples"]
		pointer to timeIntervalNanoseconds = byref(timeIntervalns)
		oversample = 1
		pointer to params["maxSamples"] = byref(returnedMaxSamples)
		segment index = 0
		timebase = 1 = 400ps
		"""
		self.timeIntervalns = c_float()
		self.returnedMaxSamples = c_int32()
		self.status['getTimebase2'] = ps.ps6000GetTimebase2(
				self.chandle, self.timebase, self.maxSamples, byref(self.timeIntervalns), 1,
				byref(self.returnedMaxSamples), 0
				)
		err = self.__check_health(self.status['getTimebase2'])
		if err is not None:
			return err

		# """ Benchmarking """
		# benchmark = Benchmark()
		# benchmark = [0.0]
		# benchmark[0] = get_time()

		return None

	def run(self) -> tuple[float | None, str | None]:
		""" Logging capture """
		if self.params['log']:
			log(self.loghandle, f'==> Beginning capture no. {self.count}', time=True)

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
		self.status['runBlock'] = ps.ps6000RunBlock(
				self.chandle, self.preTrigSamples, self.postTrigSamples,
				self.timebase, 0, None, 0, None, None
				)
		err = self.__check_health(self.status['runBlock'], stop=True)
		if err is not None:
			return None, err

		""" Check for data collection to finish using ps6000IsReady """
		ready = c_int16(0)
		check = c_int16(0)
		while ready.value == check.value:
			self.status['isReady'] = ps.ps6000IsReady(self.chandle, byref(ready))

		""" Create buffers ready for assigning pointers for data collection.
		'bufferXMin' are generally used for downsampling but in our case they're equal
		bufferXMax as we don't need to downsample.
		"""
		bufferAMax = (c_int16 * self.maxSamples)()
		bufferAMin = (c_int16 * self.maxSamples)()
		bufferCMax = (c_int16 * self.maxSamples)()
		bufferCMin = (c_int16 * self.maxSamples)()

		""" Set data buffers location for data collection from channels A and C.
		sources = ChA, ChC = 0, 2
		pointer to buffers max = byref(bufferXMax)
		pointer to buffers min = byref(bufferXMin)
		buffers length = params["maxSamples"]
		ratio mode = PS6000_RATIO_MODE_NONE = 0
		"""
		self.status['setDataBuffersA'] = ps.ps6000SetDataBuffers(
				self.chandle, 0, byref(bufferAMax), byref(bufferAMin), self.maxSamples, 0
				)
		err = self.__check_health(self.status['setDataBuffersA'], stop=True)
		if err is not None:
			return None, err

		self.status['setDataBuffersC'] = ps.ps6000SetDataBuffers(
				self.chandle, 2, byref(bufferCMax), byref(bufferCMin), self.maxSamples, 0
				)
		err = self.__check_health(self.status['setDataBuffersC'], stop=True)
		if err is not None:
			return None, err

		""" Retrieve data from scope to buffers assigned above.
		start index = 0
		pointer to number of samples = byref(cmaxSamples)
		downsample ratio = 1
		downsample ratio mode = PS6000_RATIO_MODE_NONE
		pointer to overflow = byref(overflow)
		"""
		self.status["getValues"] = ps.ps6000GetValues(
				self.chandle, 0, byref(self.cmaxSamples), 1, 0, 0, byref(self.overflow)
				)
		err = self.__check_health(self.status['getValues'], stop=True)
		if err is not None:
			return None, err

		""" Convert ADC counts data to mV """
		bufferChAmV = adc2mV(bufferAMax, self.chRange, self.cmaxADC)
		bufferChCmV = adc2mV(bufferCMax, self.chRange, self.cmaxADC)

		""" Removing the analog offset from data points """
		thresholdmV = (self.thresholdADC * chInputRanges[self.chRange]) \
			/ self.cmaxADC.value - (self.analogOffset * 1000)
		for i in range(self.maxSamples):
			bufferChAmV[i] -= (self.analogOffset * 1000)
			bufferChCmV[i] -= (self.analogOffset * 1000)

		""" Create time data """
		time = np.linspace(
			0, (self.cmaxSamples.value - 1) * self.timeIntervalns.value, self.cmaxSamples.value
			)

		""" Detect where the threshold was hit (both rising & falling edge) """
		gate = {'chA': {}, 'chC': {}}
		gate['chA'] = detect_gate_open_closed(
				bufferChAmV, time, thresholdmV, self.maxSamples, self.timeIntervalns.value
				)
		gate['chC'] = detect_gate_open_closed(
				bufferChCmV, time, thresholdmV, self.maxSamples, self.timeIntervalns.value
				)
		# Skip current acquisition if trigger timed out (all gates open at 0.0ns)
		if all([g['open']['ns'] == 0.0 for g in gate.values()]):
			if self.params['log']:
				log(self.loghandle, 'Skipping (trigger timeout).')
			return None, None
		else:
			if self.params['log']:
				""" Logging threshold hits """
				for g, id in zip(gate.values(), ['A', 'C']):
					log(self.loghandle, f"gate {id} on: {g['open']['mV']:.2f}mV, \
						{g['open']['ns']:.2f}ns @ {g['open']['index']}",)
					log(self.loghandle, f"gate {id} off: {g['closed']['mV']:.2f}mV, \
						{g['closed']['ns']:.2f}ns @ {g['closed']['index']}")

		""" Calculating relevant data """
		deltaT = gate['chC']['open']['ns'] - gate['chA']['open']['ns']

		""" Print data to file & plot if requested """
		with open(self.datahandle, 'a') as out:
			out.write(f'{self.count}\t{deltaT:.9f}\n')

		# if params['plot']:
		# 	plot_data(
		# 			bufferChAmV, bufferChCmV, gate, time, deltaT,
		# 			timeIntervalns.value, f'{timestamp}_{capcount}'
		# 			)

		# """ Updating live histogram """
		# # data.append(delay_sim_interactive(value=deltaT, mu=15.808209, sigma=2.953978))
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

		self.count += 1
		# benchmark.split()

		return deltaT, None

	def stop(self) -> str | None:
		""" Stop acquisition & close unit """
		self.status['stop'] = ps.ps6000Stop(self.chandle)
		err = self.__check_health(self.status['stop'])
		if err is not None:
			if self.params['log']:
				log(self.loghandle, f'==> Job finished with error: {err}', time=True)
			return err
		ps.ps6000CloseUnit(self.chandle)

		# """ Execution time benchmarking """
		# benchmark.results()

		""" Logging exit status & data location """
		if self.params['log']:
			log(self.loghandle, '==> Job finished without errors. Data saved to:', time=True)
			log(self.loghandle, f'{self.datahandle}')

		return None
