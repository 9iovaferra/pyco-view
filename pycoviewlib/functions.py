""" Copyright (C) 2019 Pico Technology Ltd. """
from ctypes import c_int16, Array
import numpy as np

""" Print status in columns (debug purposes) """
def print_status(status: dict) -> None:
	if bool(status):
		print("==> PicoScope Exit Status:")
		colWidth = max([len(k) for k in status.keys()])
		for key, value in status.items():
			print(f"{key: <{colWidth}} {value:}")
	else:
		print("No status to show.")

""" Parse input arguments """
def parse_args(args: list) -> dict:
	options = dict.fromkeys([
		"captures", "plot", "log", "dformat", "trigs", "livehist"
		])
	for arg in args:
		if arg.isdigit():
			options["captures"] = int(arg)
			break
		else:
			options["captures"] = 1
	options["plot"] = True if "plot" in args else False
	options["log"] = True if "log" in args else False
	options["dformat"] = "csv" if "csv" in args else "txt"
	options["trigs"] = 4 if "4way" in args else 2
	options["livehist"] = True if "live" in args else False
	
	return options

def detect_gate_open_closed(
		buffer: Array[c_int16],
		time: np.ndarray[np.float32],
		threshold: float,
		maxSamples: int,
		timeIntervalns: float
		) -> dict[str, float | int]:
	"""
	minValueIndex = array index of buffer's most negative value.
	Threshold hits are returned as (voltage, time) coordinates.
	"""
	gateChX = {
		"open": {"mV": threshold, "ns": 0.0, "index": 0},
		"closed": {"mV": threshold, "ns": 0.0, "index": 0}
		}
	hit = 0
	minValueIndex = buffer.index(min(buffer))
	minDifference = min(buffer) - threshold
	for i in range(minValueIndex):
		if abs(buffer[i] - threshold) < abs(minDifference):
			hit = i
			minDifference = buffer[i] - threshold
	gateChX["open"]["ns"] = time[hit]
	gateChX["open"]["index"] = hit
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
		gateopen: int,
		gateclosed: int,
		timeIntervalns: float,
		resistance: int
		) -> float:
	"""
	Total charge deposited by the particle in the detector.
	It is defined as the integral of voltage with respect to time,
	multiplied by dt and divided by the termination resistance.
	"""
	charge = 0.0
	for i in range(gateopen, gateclosed):
		charge += abs(buffer[i])	
	charge *= (timeIntervalns / resistance)
	
	return charge
