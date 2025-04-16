""" Copyright (C) 2019 Pico Technology Ltd. """
from ctypes import c_int16, c_int32, c_float, Array, byref
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
		timeIntervalns: float,
		charge: float,
		peakToPeak: float,
		filestamp: str,
		n: int
		) -> None:
	yLowerLim = min(bufferChAmV) + min(bufferChAmV) * 0.1
	yUpperLim = max(bufferChAmV) + max(bufferChAmV) * 0.3
	# yTicks = np.arange(-1000, 0, 50)

	# if n % 20 == 0:
	# 	plt.close()
	if n == 1:
		print("New plot!")
		fig = plt.figure(figsize=(10,6))
		plt.grid()
		plt.xlabel('Time (ns)')
		plt.ylim(yLowerLim,yUpperLim)
		plt.ylabel('Voltage (mV)')
	
	# fig, ax = plt.subplots(figsize=(10,6))
	# ax.grid()
		
	""" Channel signals """
	plt.plot(time, bufferChAmV[:],
			 color="blue", label="Channel A (gate)")
	plt.plot(time, bufferChCmV[:],
			 color="green", label="Channel C (detector signal)")
	
	""" Charge area + bounds from gate """
	fillY = bufferChCmV[gate["open"]["index"]:gate["closed"]["index"]]
	fillX = np.linspace(gate["open"]["ns"], gate["closed"]["ns"], num=len(fillY))
	plt.fill_between(fillX, fillY,
			color="lightgrey", label=f"Total deposited charge\n{charge:.2f} C")
	plt.plot([gate["open"]["ns"]] * 2, [gate["open"]["mV"], max(bufferChCmV)],
			 linestyle="--", color="black")
	plt.plot([gate["closed"]["ns"]] * 2, [gate["closed"]["mV"], max(bufferChCmV)],
			 linestyle="--", color="black")
	
	# """ Threshold """
	# plt.plt.line(y=thresholdmV, linestyle="--", color="black",
	#			label=f"Channel A threshold\n{thresholdmV:.2f} mV")
	
	""" Gate open and closed points """
	plt.plot(gate["open"]["ns"], gate["open"]["mV"],
			 color="black", marker=">", label=f"Gate open\n{gate['open']['ns']:.2f} ns")
	plt.plot(gate["closed"]["ns"], gate["closed"]["mV"],
			 color="black", marker="<", label=f"Gate closed\n{gate['closed']['ns']:.2f} ns")
	
	""" Amplitude and Peak-To-Peak """
	p2p_artist = [None, None]
	p2p_artist[0] = plt.annotate(
			"",
			xy=(time[bufferChCmV.index(max(bufferChCmV))], max(bufferChCmV)),
			xytext=(time[bufferChCmV.index(max(bufferChCmV))], peakToPeak * (-1)),
			fontsize=12,
			arrowprops=dict(edgecolor="black", arrowstyle="<->", shrinkA=0, shrinkB=0)
			)
	p2p_artist[1] = plt.text(time[bufferChCmV.index(max(bufferChCmV))] + 0.5,
			 max(bufferChCmV) - peakToPeak / 2,
			 f"Peak-to-peak\n{peakToPeak:.2f} mV")

	plt.title(f"adc_plot_{filestamp}")
	plt.legend(loc="lower right")
	plt.savefig(f"./Data/adc_plot_{filestamp}.png")
	for artist in plt.gca().lines + plt.gca().collections + p2p_artist:
		artist.remove()

def log(loghandle: str, entry: str, time=False) -> None:
	with open(f"./Data/{loghandle}", "a") as logfile:
		if time:
			logfile.write(f"[{datetime.now().strftime('%H:%M:%S')}] {entry}\n")
		else:
			logfile.write(f"           {entry}\n")


def main():
	params: dict = parse_config()
	# print_status(params)

	timestamp: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	
	""" Creating loghandle if required """
	if params["log"] == 1:
		loghandle: str = f"adc_log_{timestamp}.txt"

	""" Creating data folder """
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
	
	""" Creating chandle and status. Setting acquisition parameters.
	Opening ps6000 connection: returns handle for future use in API functions
	"""
	chandle = c_int16()
	status = {}

	delaySeconds = params["delaySeconds"]
	chRange = params[f"ch{params['target']}range"]
	analogOffset = params[f"ch{params['target']}analogOffset"]
	thresholdADC = mV2adc(
			params["thresholdmV"],
			analogOffset,
			chInputRanges[params[f"ch{params['target']}range"]]
			)
	autoTrigms = params["autoTrigms"]
	preTrigSamples = params["preTrigSamples"]
	postTrigSamples = params["postTrigSamples"]
	maxSamples = preTrigSamples + postTrigSamples
	timebase = params["timebase"]
	coupling = params[f"ch{params['target']}coupling"]
	
	""" Logging runtime parameters """
	if params["log"] == 1:
		log(loghandle, "==> Running acquisition with parameters:", time=True)
		col_width = max([len(k) for k in params.keys()])
		for key, value in params.items():
			log(loghandle, f"{key: <{col_width}} {value:}")

	status["openUnit"] = ps.ps6000OpenUnit(byref(chandle), None)
	assert_pico_ok(status["openUnit"])

	""" Setting up two channels, others turned off
	ps.ps6000SetChannel(
		handle:		chandle
		id:			(A=0, B=1, C=2, D=4)
		enabled:	(yes=1, no=0)
		coupling:	(AC1Mohm=0, DC1Mohm=1, DC50ohm=2)
		range:		see chInputRanges in pycoviewlib/constants.py
		offset:		analog offset (value in volts)
		bandwidth:	(FULL=0, 20MHz=1, 25MHz=2)
	) """
	# automate this process so that any 2 channels can be used
	status["setChA"] = ps.ps6000SetChannel(
			chandle, 0, params["chAenabled"], 2, chRange, analogOffset, params["chAbandwidth"]
			)
	assert_pico_ok(status["setChA"])
	status["setChB"] = ps.ps6000SetChannel(
			chandle, 1, params["chBenabled"], 2, chRange, 0, 0
			)
	assert_pico_ok(status["setChB"])
	status["setChC"] = ps.ps6000SetChannel(
			chandle, 2, params["chCenabled"], 2, chRange, analogOffset, params["chCbandwidth"]
			)
	assert_pico_ok(status["setChC"])
	status["setChD"] = ps.ps6000SetChannel(
			chandle, 3, params["chDenabled"], 2, chRange, 0, 0
			)
	assert_pico_ok(status["setChD"])

	""" Setting up trigger on channel A
	enabled = 1
	source = ChA = 0
	threshold = 10000 ADC counts ~=300mV, see thresholdmV below
	direction = PS6000_FALLING = 3
	delay = 0s
	auto Trigger = 10000ms
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
	cmaxADC = c_int16(maxADC)

	""" Creating data output file """	
	dathandle = f"./Data/adc_data_{timestamp}.txt" # read format from gui
	with open(dathandle, "a") as out:
		out.write("cap\tamplitude (mV)\tpeak2peak (mV)\tcharge (C)\n")
	
	""" Thread manager waiting for Stop command """
	manager = Manager()
	assistant = Thread(target=manager.listen)
	assistant.start()

	""" Capture counter """
	capcount = 1

	while manager.continue_:
		""" Logging capture """
		if params["log"] == 1:
			log(loghandle, f"==> Beginning capture no. {capcount}", time=True)
		
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
		bufferChAmV = adc2mV(bufferAMax, chRange, cmaxADC)
		bufferChCmV = adc2mV(bufferCMax, chRange, cmaxADC)

		""" Removing the analog offset from data points """
		thresholdmV = (thresholdADC * chInputRanges[chRange]) / cmaxADC.value - (analogOffset * 1000)
		for i in range(maxSamples):
			bufferChAmV[i] -= (analogOffset * 1000)
			bufferChCmV[i] -= (analogOffset * 1000)

		""" Create time data """
		time = np.linspace(
				0, (cmaxSamples.value - 1) * timeIntervalns.value, cmaxSamples.value, dtype="float32"
				)

		""" Detect where the threshold was hit (both falling & rising edge) """
		gate = detect_gate_open_closed(
				bufferChAmV, time, thresholdmV, maxSamples, timeIntervalns.value
				)
		""" Logging threshold hits """
		if params["log"] == 1:
			log(loghandle,
				f"gate on: {gate['open']['mV']:.2f}mV, {gate['open']['ns']:.2f}ns @ {gate['open']['index']}",)
			log(loghandle,
				f"gate off: {gate['closed']['mV']:.2f}mV, {gate['closed']['ns']:.2f}ns @ {gate['closed']['index']}")
	
		""" Calculating relevant data """
		amplitude = abs(min(bufferChCmV))
		peakToPeak = abs(min(bufferChCmV)) - abs(max(bufferChCmV))
		charge = calculate_charge(
				bufferChCmV, gate["open"]["index"], gate["closed"]["index"],
				timeIntervalns.value, coupling
				)

		""" Logging capture results """
		if params["log"] == 1:
			log(loghandle, f"amplitude: {amplitude:.2f}mV")
			log(loghandle, f"peak-to-peak: {peakToPeak:.2f}mV")
			log(loghandle, f"charge: {charge:.2f}C")
	
		""" Print data to file """
		with open(dathandle, "a") as out:
			out.write(f"{capcount}\t{amplitude:.9f}\t{peakToPeak:.9f}\t{charge:.9f}\n")

		if params["plot"]:
			plot_data(
					bufferChAmV, bufferChCmV, gate, time, timeIntervalns,
					charge, peakToPeak, f"{timestamp}_{str(capcount)}",
					n=capcount
					)

		""" Checking if everything is fine """
		if not 0 in status.values():
			manager.continue_ = False
			if params["log"] == 1:
				log(loghandle, "==> Something went wrong! PicoScope status:", time=True)
				colWidth = max([len(k) for k in status.keys()])
				for key, value in status.items():
					log(loghandle, f"{key: <{colWidth}} {value:}")

		capcount +=1
	
	assistant.join()

	status["stop"] = ps.ps6000Stop(chandle)
	assert_pico_ok(status["stop"])

	""" Close unit & disconnect the scope """
	ps.ps6000CloseUnit(chandle)

	""" Logging exit status & data location """
	if params["log"] == 1:
		log(loghandle, "==> Job finished without errors. Data and/or plots saved to:", time=True)
		log(loghandle, f"{str(dataPath)}")
		log(loghandle, "==> PicoScope exit status:", time=True)
		colWidth = max([len(k) for k in status.keys()])
		for key, value in status.items():
			log(loghandle, f"{key: <{colWidth}} {value:}")


if __name__ == "__main__":
	sys.exit(main())
