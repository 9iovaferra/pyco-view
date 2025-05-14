""" Copyright (C) 2019 Pico Technology Ltd. """
from ctypes import c_int16, c_int32, c_float, Array, byref
import numpy as np
from picosdk.ps6000 import ps6000 as ps
from picosdk.errors import PicoSDKCtypesError
from picosdk.constants import PICO_STATUS_LOOKUP
from pycoviewlib.functions import (
		mV2adc, detect_gate_open_closed, calculate_charge, log, key_from_value,
		)
from pycoviewlib.constants import PV_DIR, maxADC, chInputRanges, couplings, channelIDs
import matplotlib.pyplot as plt
from picosdk.functions import adc2mV, assert_pico_ok
from datetime import datetime
from typing import Union

def plot_data(
		bufferChAmV: Array[c_int16],
		bufferChCmV: Array[c_int16],
		gate: dict,
		time: np.ndarray,
		timeIntervalns: float,
		charge: float,
		peakToPeak: float,
		filestamp: str,
		n: int
		) -> None:
	yLowerLim = min(bufferChAmV) + min(bufferChAmV) * 0.1
	yUpperLim = max(bufferChAmV) + max(bufferChAmV) * 0.3
	# yTicks = np.arange(-1000, 0, 50)

	if n == 1:
		print("New plot!")
		plt.figure(figsize=(10, 6))
		plt.grid()
		plt.xlabel('Time (ns)')
		plt.ylim(yLowerLim, yUpperLim)
		plt.ylabel('Voltage (mV)')

	# fig, ax = plt.subplots(figsize=(10,6))
	# ax.grid()

	""" Channel signals """
	plt.plot(time, bufferChAmV[:], color="blue", label="Channel A (gate)")
	plt.plot(time, bufferChCmV[:], color="green", label="Channel C (detector signal)")

	""" Charge area + bounds from gate """
	fillY = bufferChCmV[gate["open"]["index"]:gate["closed"]["index"]]
	fillX = np.linspace(gate["open"]["ns"], gate["closed"]["ns"], num=len(fillY))
	plt.fill_between(
		fillX, fillY, color="lightgrey", label=f"Total deposited charge\n{charge:.2f} pC"
		)
	plt.plot(
		[gate["open"]["ns"]] * 2, [gate["open"]["mV"], max(bufferChCmV)],
		linestyle="--", color="black"
		)
	plt.plot(
		[gate["closed"]["ns"]] * 2, [gate["closed"]["mV"], max(bufferChCmV)],
		linestyle="--", color="black"
		)

	# """ Threshold """
	# plt.plt.line(
	# 	y=thresholdmV, linestyle="--", color="black",
	# 	label=f"Channel A threshold\n{thresholdmV:.2f} mV"
	# 	)

	""" Gate open and closed points """
	plt.plot(
		gate["open"]["ns"], gate["open"]["mV"],
		color="black", marker=">", label=f"Gate open\n{gate['open']['ns']:.2f} ns"
		)
	plt.plot(
		gate["closed"]["ns"], gate["closed"]["mV"],
		color="black", marker="<", label=f"Gate closed\n{gate['closed']['ns']:.2f} ns"
		)

	""" Amplitude and Peak-To-Peak """
	p2p_artist = [None, None]
	p2p_artist[0] = plt.annotate(
			"",
			xy=(time[bufferChCmV.index(max(bufferChCmV))], max(bufferChCmV)),
			xytext=(time[bufferChCmV.index(max(bufferChCmV))], peakToPeak * (-1)),
			fontsize=12,
			arrowprops=dict(edgecolor="black", arrowstyle="<->", shrinkA=0, shrinkB=0)
			)
	p2p_artist[1] = plt.text(
			time[bufferChCmV.index(max(bufferChCmV))] + 0.5,
			max(bufferChCmV) - peakToPeak / 2, f"Peak-to-peak\n{peakToPeak:.2f} mV")

	plt.title(f"adc_plot_{filestamp}")
	plt.legend(loc="lower right")
	plt.savefig(f"./Data/adc_plot_{filestamp}.png")
	for artist in plt.gca().lines + plt.gca().collections + p2p_artist:
		artist.remove()


class ADC:
	def __init__(self, params: dict[str, Union[int, float, str]]):
		self.params = params
		self.timestamp: str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
		if self.params['log']:  # Creating loghandle if required
			self.loghandle: str = f'adc_log_{self.timestamp}.txt'
		self.datahandle: str = f"{PV_DIR}/Data/adc_data_{self.timestamp}.{self.params['dformat']}"

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

	def setup(self) -> str | None:
		""" Logging runtime parameters """
		if self.params['log']:
			log(self.loghandle, '==> Running acquisition with parameters:', time=True)
			col_width = max([len(k) for k in self.params.keys()])
			for key, value in self.params.items():
				log(self.loghandle, f'{key: <{col_width}} {value:}')

		with open(self.datahandle, 'a') as out:  # Creating data output file
			out.write('n\t\tamplitude (mV)\tpeak2peak (mV)\tcharge (pC)\n')

		""" Opening ps6000 connection: returns handle for future use in API functions """
		self.status['openUnit'] = ps.ps6000OpenUnit(byref(self.chandle), None)
		err = err = self.__check_health(self.status['openUnit'])
		if err is not None:
			return err

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
			err = self.__check_health(self.status[f'setCh{name}'])
			if err is not None:
				return err

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
		err = self.__check_health(self.status['setSimpleTrigger'])
		if err is not None:
			return err

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
		err = self.__check_health(self.status['getTimebase2'])
		if err is not None:
			return err

		return None

	def run(self) -> tuple[float | None, str | None]:
		""" Logging capture """
		if self.params['log']:
			log(self.loghandle, f'==> Beginning capture no. {self.count}', time=True)

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
		buffers length = maxSamples
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
		pointer to overflow = byref(overflow))
		"""
		self.status['getValues'] = ps.ps6000GetValues(
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

		""" Detect where the threshold was hit (both falling & rising edge) """
		gate = detect_gate_open_closed(
				bufferChAmV, time, thresholdmV, self.maxSamples, self.timeIntervalns.value
				)
		# Skip current acquisition if trigger timed out
		if all([gopen['ns'] == 0.0 for gopen in gate.values()]):
			if self.params['log']:
				log(self.loghandle, 'Skipping (trigger timeout).')
			return None, None
		else:
			""" Logging threshold hits """
			if self.params['log']:
				log(self.loghandle, f"gate on: {gate['open']['mV']:.2f}mV, \
					{gate['open']['ns']:.2f}ns @ {gate['open']['index']}",)
				log(self.loghandle, f"gate off: {gate['closed']['mV']:.2f}mV, \
					{gate['closed']['ns']:.2f}ns @ {gate['closed']['index']}")

		""" Calculating relevant data. Creating pickle file for use in `main.py` """
		amplitude = abs(min(bufferChCmV))
		peakToPeak = abs(min(bufferChCmV)) - abs(max(bufferChCmV))
		charge = calculate_charge(
				bufferChCmV, (gate['open']['index'], gate['closed']['index']),
				self.timeIntervalns.value, self.coupling
				)

		""" Logging capture results """
		if self.params['log']:
			log(self.loghandle, f'amplitude: {amplitude:.2f}mV')
			log(self.loghandle, f'peak-to-peak: {peakToPeak:.2f}mV')
			log(self.loghandle, f'charge: {charge:.2f}pC')

		""" Print data to file """
		with open(self.datahandle, 'a') as out:
			out.write(f'{self.count}\t{amplitude:.9f}\t{peakToPeak:.9f}\t{charge:.9f}\n')

		# if params['plot']:
		# 	plot_data(
		# 			bufferChAmV, bufferChCmV, gate, time, timeIntervalns,
		# 			charge, peakToPeak, f'{timestamp}_{str(capcount)}',
		# 			n=capcount
		# 			)

		self.count += 1
		# random_wait = round(np.random.random(), 2)
		# sleep(2 * random_wait)

		return charge, None

	def stop(self) -> str | None:
		""" Stop acquisition & close unit """
		self.status['stop'] = ps.ps6000Stop(self.chandle)
		err = self.__check_health(self.status['stop'])
		if err is not None:
			if self.params['log']:
				log(self.loghandle, f'==> Job finished with error: {err}', time=True)
			return err
		ps.ps6000CloseUnit(self.chandle)

		""" Logging exit status & data location """
		if self.params['log']:
			log(self.loghandle, '==> Job finished without errors. Data saved to:', time=True)
			log(self.loghandle, f'{self.datahandle}')

		return None
