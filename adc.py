""" Copyright (C) 2019 Pico Technology Ltd. """
from ctypes import c_int16, c_int32, c_float, Array, byref
import numpy as np
from picosdk.ps6000 import ps6000 as ps
from picosdk.errors import PicoSDKCtypesError
from picosdk.constants import PICO_STATUS_LOOKUP
from pycoviewlib.functions import (
		mV2adc, detect_gate_open_closed, calculate_charge, log, key_from_value,
		format_data
		)
from pycoviewlib.constants import PV_DIR, maxADC, chInputRanges, couplings, channelIDs
import matplotlib.pyplot as plt
from picosdk.functions import adc2mV, assert_pico_ok
from datetime import datetime
from typing import Union

def plot_data(
		bufferGate: Array[c_int16],
		bufferSignal: Array[c_int16],
		gate: dict,
		time: np.ndarray,
		timeIntervalns: float,
		charge: float,
		peakToPeak: float,
		title: str,
		) -> None:
	maxSignal = max(bufferSignal)
	yLowerLim = min(min(bufferGate), min(bufferSignal)) * 1.1
	yUpperLim = max(abs(max(bufferGate)), abs(maxSignal)) * 1.3

	fig, ax = plt.subplots(figsize=(10, 6), layout='tight')
	ax.grid()
	ax.set_ylim(yLowerLim, yUpperLim)
	ax.set_xlabel('Time (ns)')
	ax.set_ylabel('Voltage (mV)')

	""" Channel signals """
	ax.plot(time, bufferGate[:], color='blue', label='Channel A (gate)')
	ax.plot(time, bufferSignal[:], color='green', label='Channel C (detector signal)')

	""" Charge area + bounds from gate """
	fillY = bufferSignal[gate['open']['index']:gate['closed']['index']]
	fillX = np.linspace(gate['open']['ns'], gate['closed']['ns'], num=len(fillY))
	ax.fill_between(
		fillX, fillY, color='lightgrey', label=f'Total deposited charge\n{charge:.2f} pC'
		)
	ax.plot(
		[gate['open']['ns']] * 2, [gate['open']['mV'], maxSignal],
		linestyle='--', color='black'
		)
	ax.plot(
		[gate['closed']['ns']] * 2, [gate['closed']['mV'], maxSignal],
		linestyle='--', color='black'
		)

	""" Gate open and closed points """
	ax.plot(
		gate['open']['ns'], gate['open']['mV'],
		color="black", marker=">", label=f"Gate open\n{gate['open']['ns']:.2f} ns"
		)
	ax.plot(
		gate['closed']['ns'], gate['closed']['mV'],
		color="black", marker="<", label=f"Gate closed\n{gate['closed']['ns']:.2f} ns"
		)

	""" Amplitude and Peak-To-Peak """
	ax.annotate(
			'',
			xy=(time[bufferSignal.index(maxSignal)], maxSignal),
			xytext=(time[bufferSignal.index(maxSignal)], min(bufferSignal)),
			fontsize=12,
			arrowprops=dict(edgecolor='black', arrowstyle='<->', shrinkA=0, shrinkB=0)
			)
	ax.text(
			time[bufferSignal.index(maxSignal)] + 0.5,
			maxSignal - peakToPeak / 2, f'Peak-to-peak\n{peakToPeak:.2f} mV')

	ax.set_title(title)
	ax.legend(loc='lower right')

	return fig


class ADC:
	def __init__(self, params: dict[str, Union[int, float, str]], probe: bool = False):
		self.params = params
		self.probe = probe
		self.timestamp: str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
		if self.params['log']:  # Creating loghandle if required
			self.loghandle: str = f"{self.params['filename']}_{self.timestamp}_adc_log.txt"
		self.datahandle: str = f"{PV_DIR}/Data/{self.params['filename']}_{self.timestamp}_data.{self.params['dformat']}"

		self.chandle = c_int16()
		self.status = {}

		self.delaySeconds = params['delaySeconds']
		self.chRange = params[f"ch{params['target']}range"]
		self.analogOffset = params[f"ch{params['target']}analogOffset"]
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
		self.coupling = couplings[key_from_value(couplings, params[f"ch{params['target']}coupling"])][1]

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

	def setup(self) -> list[str] | None:
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
			if self.params['includeAmplitude']:
				header.append('amplitude (mV)')
			if self.params['includePeakToPeak']:
				header.append('peak2peak (mV)')
			header.append('charge (pC)')
			with open(self.datahandle, 'a') as out:  # Creating data output file
				out.write(format_data(header, self.params['dformat']))

		""" Opening ps6000 connection: returns handle for future use in API functions """
		self.status['openUnit'] = ps.ps6000OpenUnit(byref(self.chandle), None)
		err.append(self.__check_health(self.status['openUnit']))

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

		""" Setting up simple trigger on target channel
		ps.ps6000SetSimpleTrigger(
			handle:		chandle
			enabled:	(yes=1, no=0)
			source:		(A=0, B=1, C=2, D=4)
			threshold:	value in ADC counts
			direction:	PS6000_FALLING=3
			delay:		value in seconds
			wait for:	value in milliseconds
		) """
		self.status['setSimpleTrigger'] = ps.ps6000SetSimpleTrigger(
				self.chandle,
				1,
				channelIDs.index(self.params['target']),
				self.thresholdADC,
				3,
				self.delaySeconds,
				self.autoTrigms
				)
		err.append(self.__check_health(self.status['setSimpleTrigger']))

		""" Get timebase info & pre/post trigger samples to be collected
		noSamples = maxSamples
		pointer to timeIntervalNanoseconds = byref(timeIntervalns)
		oversample = 1
		pointer to maxSamples = byref(returnedMaxSamples)
		segment index = 0
		timebase = 1 = 400ps
		"""
		self.timeIntervalns = c_float()
		self.returnedMaxSamples = c_int32()
		self.status['getTimebase2'] = ps.ps6000GetTimebase2(
				self.chandle, self.timebase, self.maxSamples, byref(self.timeIntervalns), 1,
				byref(self.returnedMaxSamples), 0
				)
		err.append(self.__check_health(self.status['getTimebase2']))

		return err

	def run(self) -> tuple[float | None, list[str] | None] | plt.Figure:
		err = []
		""" Logging capture """
		if self.params['log'] and not self.probe:
			to_be_logged = [dict(entry=f'==> Beginning capture no. {self.count}', time=True)]

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
		self.status['runBlock'] = ps.ps6000RunBlock(
				self.chandle, self.preTrigSamples, self.postTrigSamples,
				self.timebase, 0, None, 0, None, None
				)
		err.append(self.__check_health(self.status['runBlock'], stop=True))

		""" Check for data collection to finish using ps6000IsReady """
		ready = c_int16(0)
		check = c_int16(0)
		while ready.value == check.value:
			ps.ps6000IsReady(self.chandle, byref(ready))

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
		buffers length = maxSamples
		ratio mode = PS6000_RATIO_MODE_NONE = 0
		"""
		self.status['setDataBuffersA'] = ps.ps6000SetDataBuffers(
				self.chandle, 0, byref(bufferAMax), byref(bufferAMin), self.maxSamples, 0
				)
		err.append(self.__check_health(self.status['setDataBuffersA'], stop=True))

		self.status['setDataBuffersC'] = ps.ps6000SetDataBuffers(
				self.chandle, 2, byref(bufferCMax), byref(bufferCMin), self.maxSamples, 0
				)
		err.append(self.__check_health(self.status['setDataBuffersC'], stop=True))

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

		""" Detect where the threshold was hit (both falling & rising edge) """
		gate = detect_gate_open_closed(
				bufferChAmV, time, thresholdmV, self.maxSamples, self.timeIntervalns.value
				)
		# Skip current acquisition if trigger timed out
		if all([gopen['ns'] == 0.0 for gopen in gate.values()]):
			if self.params['log'] and not self.probe:
				to_be_logged.append('Skipping (trigger timeout).')
			return None, [None]
		# else:
		# 	""" Logging threshold hits """
		# 	if self.params['log'] and not self.probe:
		# 		log(self.loghandle, f"gate on: {gate['open']['mV']:.2f}mV, \
		# 			{gate['open']['ns']:.2f}ns @ {gate['open']['index']}",)
		# 		log(self.loghandle, f"gate off: {gate['closed']['mV']:.2f}mV, \
		# 			{gate['closed']['ns']:.2f}ns @ {gate['closed']['index']}")

		""" Calculating relevant data """
		data = []
		if self.params['includeCounter']:
			data.append(self.count)
		if self.params['includeAmplitude'] or self.probe:
			amplitude = abs(min(bufferChCmV))
			data.append(amplitude)
		if self.params['includePeakToPeak'] or self.probe:
			peakToPeak = abs(min(bufferChCmV)) - abs(max(bufferChCmV))
			data.append(peakToPeak)
		charge = calculate_charge(
				bufferChCmV, (gate['open']['index'], gate['closed']['index']),
				self.timeIntervalns.value, self.coupling
				)
		data.append(charge)

		""" Logging capture results """
		if self.params['log'] and not self.probe:
			to_be_logged.append('Ok!')
			for item in to_be_logged:
				if isinstance(item, dict):
					log(self.loghandle, **item)
				else:
					log(self.loghandle, item)

		# """ Logging capture results """
		# if self.params['log'] and not self.probe:
		# 	if self.params['includeAmplitude']:
		# 		log(self.loghandle, f'amplitude: {amplitude:.2f}mV')
		# 	if self.params['includePeakToPeak']:
		# 		log(self.loghandle, f'peak-to-peak: {peakToPeak:.2f}mV')
		# 	log(self.loghandle, f'charge: {charge:.2f}pC')

		""" Print data to file """
		if not self.probe:
			with open(self.datahandle, 'a') as out:
				out.write(format_data(data, self.params['dformat']))
		else:
			figure = plot_data(
				bufferChAmV, bufferChCmV, gate, time, self.timeIntervalns,
				charge, peakToPeak, f'ADC Probe {self.timestamp}'
				)
			return figure, err

		self.count += 1

		return charge, err

	def stop(self) -> str | None:
		""" Stop acquisition & close unit """
		self.status['stop'] = ps.ps6000Stop(self.chandle)
		err = self.__check_health(self.status['stop'])
		ps.ps6000CloseUnit(self.chandle)
		if err is not None:
			if self.params['log'] and not self.probe:
				log(self.loghandle, f'==> Job finished with error: {err}', time=True)
			return err

		""" Logging exit status & data location """
		if self.params['log'] and not self.probe:
			log(self.loghandle, '==> Job finished without errors. Data saved to:', time=True)
			log(self.loghandle, f'{self.datahandle}')

		return None
