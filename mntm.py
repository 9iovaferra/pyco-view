""" Copyright (C) 2019 Pico Technology Ltd. """
from ctypes import c_int16, c_int32, c_float, Array, byref
from picosdk.ps6000 import ps6000 as ps
from picosdk.functions import adc2mV, assert_pico_ok
from picosdk.errors import PicoSDKCtypesError
from picosdk.constants import PICO_STATUS_LOOKUP
from pycoviewlib.functions import log, detect_gate_open_closed, mV2adc, format_data
from pycoviewlib.constants import (
		PV_DIR, chInputRanges, maxADC, channelIDs,
		PS6000_CONDITION_TRUE, PS6000_CONDITION_DONT_CARE, PS6000_BELOW, PS6000_NONE
		)
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Union

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
		title: str,
		) -> None:
	buffersMin = min(min(bufferChAmV), min(bufferChBmV), min(bufferChCmV), min(bufferChDmV))
	buffersMax = max(max(bufferChAmV), max(bufferChBmV), max(bufferChCmV), max(bufferChDmV))
	yLowerLim = buffersMin * 1.2
	yUpperLim = buffersMax * 1.4

	fig, ax = plt.subplots(figsize=(10, 6), layout='tight')
	ax.grid()
	ax.set_xlabel('Time (ns)')
	ax.set_ylabel('Voltage (mV)')
	ax.set_xlim(0, int(max(time)))
	ax.set_ylim(yLowerLim, yUpperLim)

	""" Channel signals """
	ax.plot(time, bufferChAmV[:], color='blue', label='Channel A (gate)')
	ax.plot(time, bufferChBmV[:], color='red', label='Channel B (gate)')
	ax.plot(time, bufferChCmV[:], color='green', label='Channel C (gate)')
	ax.plot(time, bufferChDmV[:], color='gold', label='Channel D (gate)')

	""" Bounds from gate """
	for g, id, color in zip(gate.values(), channelIDs, ['darkblue', 'darkred', 'darkgreen', 'goldenrod']):
		ax.plot(
			g['open']['ns'], g['open']['mV'],
			color=color, marker='>',
			label=f"Gate {id} open\n{g['open']['ns']:.2f} ns"
			)
		ax.plot(
			g['closed']['ns'], g['closed']['mV'],
			color=color, marker='<',
			label=f"Gate {id} closed\n{g['closed']['ns']:.2f} ns"
			)
		ax.plot(
			[g['open']['ns']] * 2, [g['open']['mV'], yLowerLim],
			linestyle='--', color=color
			)
		ax.plot(
			[g['closed']['ns']] * 2, [g['closed']['mV'], yLowerLim],
			linestyle='--', color=color
			)

	ax.fill_between(
			np.arange(delayBounds[0], delayBounds[1], timeIntervalns),
			yLowerLim, yUpperLim,
			color='lightgrey', label=f'Delay\n{deltaT:.2f} ns'
			)

	ax.set_title(title)
	plt.legend(loc="lower right")

	return fig


class Meantimer:
	def __init__(self, params: dict[str, Union[int, float, str]], probe: bool = False):
		self.params = params
		self.probe = probe
		self.timestamp: str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
		if self.params['log']:  # Creating loghandle if required
			self.loghandle: str = f"{self.params['filename']}_{self.timestamp}_mntm_log.txt"
		self.datahandle: str = f"{PV_DIR}/Data/{self.params['filename']}_{self.timestamp}_data.{self.params['dformat']}"

		self.chandle = c_int16()
		self.status = {}

		self.chRange = params[f"ch{params['target'][0]}range"]
		self.analogOffset = params[f"ch{params['target'][0]}analogOffset"]
		self.target = params['target']
		self.nTargets = len(params['target'])
		self.thresholdADC = mV2adc(
				params['thresholdmV'],
				self.analogOffset,
				chInputRanges[self.chRange]
				)
		self.autoTrigms = params['autoTrigms']
		self.delaySeconds = params['delaySeconds']
		self.preTrigSamples = params['preTrigSamples']
		self.postTrigSamples = params['postTrigSamples']
		self.maxSamples = params['maxSamples']
		self.timebase = params['timebase']

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
		err = []
		""" Logging runtime parameters """
		if self.params['log'] and not self.probe:
			log(self.loghandle, '==> Running acquisition with parameters:', time=True)
			col_width = max([len(k) for k in self.params.keys()])
			for key, value in self.params.items():
				log(self.loghandle, f'{key: <{col_width}} {value:}')

		if not self.probe:
			header = []
			if self.params['includeCounter']:
				header.append('n')
			header.append('deltaT (ns)')
			with open(self.datahandle, "a") as out:  # Creating data output file
				out.write(format_data(header, self.params['dformat']))

		""" Opening ps6000 connection: returns handle for future use in API functions """
		self.status['openUnit'] = ps.ps6000OpenUnit(byref(self.chandle), None)
		err.append(self.__check_health(self.status['openUnit']))

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
			err.append(self.__check_health(self.status[f'setCh{name}']))

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
		self.status['setTriggerChannelConditions'] = ps.ps6000SetTriggerChannelConditions(
				self.chandle, byref(triggerConditions), nTrigConditions
				)
		err.append(self.__check_health(self.status['setTriggerChannelConditions']))

		PropertiesArray = ps.PS6000_TRIGGER_CHANNEL_PROPERTIES * self.nTargets
		properties = [ps.PS6000_TRIGGER_CHANNEL_PROPERTIES(
				self.thresholdADC, 0, 0, 0, channelIDs.index(t), 0
				) for t in self.params['target']]
		channelProperties = PropertiesArray(*properties)
		nChannelProperties = len(properties)
		self.status['setTriggerChProperties'] = ps.ps6000SetTriggerChannelProperties(
				self.chandle, byref(channelProperties), nChannelProperties, 0, self.autoTrigms
				)
		err.append(self.__check_health(self.status['setTriggerChProperties']))

		self.status['setTriggerDelay'] = ps.ps6000SetTriggerDelay(self.chandle, self.delaySeconds)
		err.append(self.__check_health(self.status['setTriggerDelay']))

		triggerDirections = [
			PS6000_BELOW if id in self.target else PS6000_NONE for id in channelIDs
			] + [PS6000_NONE] * 2
		self.status['setTriggerChannelDirections'] = ps.ps6000SetTriggerChannelDirections(
				self.chandle, *triggerDirections
				)
		err.append(self.__check_health(self.status['setTriggerChannelDirections']))

		""" Get timebase info & pre/post trigger samples to be collected
		ps.ps6000GetTimebase2(
			handle:				chandle
			timebase:			0=200ps, 1=400ps, 2=800ps, ...
			noSamples:			maxSamples
			intervalns:			timeIntervalns
			oversample:			1
			returnedMaxSamples: actual number of samples collected
			segmentIndex:		0
		) """
		self.timeIntervalns = c_float()
		returnedMaxSamples = c_int32()
		self.status['getTimebase2'] = ps.ps6000GetTimebase2(
			self.chandle, self.timebase, self.maxSamples, byref(self.timeIntervalns), 1,
			byref(returnedMaxSamples), 0
			)
		err.append(self.__check_health(self.status['getTimebase2']))

		# """ Benchmarking """
		# benchmark = Benchmark()
		# benchmark = [0.0]

		return err

	def run(self) -> tuple[float | None, str | None]:
		err = []
		""" Logging capture """
		if self.params['log'] and not self.probe:
			to_be_logged = [dict(entry=f'==> Beginning capture no. {self.count}', time=True)]

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
		self.status['runBlock'] = ps.ps6000RunBlock(
				self.chandle, self.preTrigSamples, self.postTrigSamples, self.timebase, 0, None, 0, None, None
				)
		err.append(self.__check_health(self.status['runBlock'], stop=True))

		""" Check for data collection to finish using ps6000IsReady """
		ready = c_int16(0)
		check = c_int16(0)
		while ready.value == check.value:
			self.status['isReady'] = ps.ps6000IsReady(self.chandle, byref(ready))

		""" Create buffers ready for assigning pointers for data collection.
		'bufferXMin' are generally used for downsampling but in our case they're equal
		to bufferXMax as we don't need to downsample.
		"""
		bufferAMax = (c_int16 * self.maxSamples)()
		bufferAMin = (c_int16 * self.maxSamples)()
		bufferBMax = (c_int16 * self.maxSamples)()
		bufferBMin = (c_int16 * self.maxSamples)()
		bufferCMax = (c_int16 * self.maxSamples)()
		bufferCMin = (c_int16 * self.maxSamples)()
		bufferDMax = (c_int16 * self.maxSamples)()
		bufferDMin = (c_int16 * self.maxSamples)()

		buffers = {
			'A': [bufferAMax, bufferAMin], 'B': [bufferBMax, bufferBMin],
			'C': [bufferCMax, bufferCMin], 'D': [bufferDMax, bufferDMin]
			}

		""" Set data buffers location for data collection.
		sources = ChA, ChB, ChC, ChD = 0, 1, 2, 3
		pointer to buffers max = byref(bufferXMax)
		pointer to buffers min = byref(bufferXMin)
		buffers length = maxSamples
		ratio mode = PS6000_RATIO_MODE_NONE = 0
		"""
		for id, name in enumerate(channelIDs):
			self.status[f'setDataBuffers{name}'] = ps.ps6000SetDataBuffers(
				self.chandle, id, byref(buffers[name][0]), byref(buffers[name][1]), self.maxSamples, 0
				)
			err.append(self.__check_health(self.status[f'setDataBuffers{name}'], stop=True))

		""" Retrieve data from scope to buffers assigned above.
		start index = 0
		pointer to number of samples = byref(cmaxSamples)
		downsample ratio = 1
		downsample ratio mode = PS6000_RATIO_MODE_NONE
		pointer to overflow = byref(overflow))
		"""
		self.status['getValues'] = ps.ps6000GetValues(
				self.chandle, 0, byref(self.cmaxSamples), 1, 0, 0, byref(self.overflow)
				)
		err.append(self.__check_health(self.status['getValues'], stop=True))

		""" Convert ADC counts data to mV """
		bufferChAmV = adc2mV(bufferAMax, self.chRange, self.cmaxADC)
		bufferChBmV = adc2mV(bufferBMax, self.chRange, self.cmaxADC)
		bufferChCmV = adc2mV(bufferCMax, self.chRange, self.cmaxADC)
		bufferChDmV = adc2mV(bufferDMax, self.chRange, self.cmaxADC)

		""" Removing the analog offset from data points """
		thresholdmV = (self.thresholdADC * chInputRanges[self.chRange]) \
			/ self.cmaxADC.value - (self.analogOffset * 1000)
		for i in range(self.maxSamples):
			bufferChAmV[i] -= (self.analogOffset * 1000)
			bufferChBmV[i] -= (self.analogOffset * 1000)
			bufferChCmV[i] -= (self.analogOffset * 1000)
			bufferChDmV[i] -= (self.analogOffset * 1000)

		""" Create time data """
		time = np.linspace(
			0, (self.cmaxSamples.value - 1) * self.timeIntervalns.value, self.cmaxSamples.value
			)

		""" Detect d atapoints where the threshold was hit (both falling & rising edge) """
		gate = {'chA': {}, 'chB': {}, 'chC': {}, 'chD': {}}
		for id, buffer in zip(channelIDs, [bufferChAmV, bufferChBmV, bufferChCmV, bufferChDmV]):
			gate[f'ch{id}'] = detect_gate_open_closed(
					buffer, time, thresholdmV, self.maxSamples, self.timeIntervalns.value
					)
		# Skip current acquisition if trigger timed out (all gates open at 0.0ns)
		if all([g['open']['ns'] == 0.0 for g in gate.values()]):
			if self.params['log'] and not self.probe:
				to_be_logged.append('Skipping (trigger timeout).')
			return None, [None]

		""" Calculating relevant data """
		data = []
		if self.params['includeCounter']:
			data.append(self.count)
		delayBounds = (
				gate['chA']['open']['ns'] + (gate['chB']['open']['ns'] - gate['chA']['open']['ns']) / 2,
				gate['chC']['open']['ns'] + (gate['chD']['open']['ns'] - gate['chC']['open']['ns']) / 2
				)
		deltaT = delayBounds[1] - delayBounds[0]
		data.append(deltaT)

		if self.params['log'] and not self.probe:
			to_be_logged.append('Ok!')
			for item in to_be_logged:
				if isinstance(item, dict):
					log(self.loghandle, **item)
				else:
					log(self.loghandle, item)

		""" Print data to file & plot if requested """
		if not self.probe:
			with open(self.datahandle, 'a') as out:
				out.write(format_data(data, self.params['dformat']))
		else:
			figure = plot_data(
				bufferChAmV, bufferChBmV, bufferChCmV, bufferChDmV, gate, delayBounds,
				time, deltaT, self.timeIntervalns.value, f'Meantimer Probe {self.timestamp}'
				)
			return figure, err

		self.count += 1
		# benchmark.split()

		return deltaT, err

	def stop(self) -> str | None:
		""" Stop acquisition & close unit """
		self.status['stop'] = ps.ps6000Stop(self.chandle)
		err = self.__check_health(self.status['stop'])
		ps.ps6000CloseUnit(self.chandle)
		if err is not None:
			if self.params['log'] and not self.probe:
				log(self.loghandle, f'==> Job finished with error: {err}', time=True)
			return err

		# """ Execution time benchmarking """
		# benchmark.results()

		""" Logging exit status & data location """
		if self.params['log'] and not self.probe:
			log(self.loghandle, '==> Job finished without errors. Data saved to:', time=True)
			log(self.loghandle, f'{self.datahandle}')

		return None
