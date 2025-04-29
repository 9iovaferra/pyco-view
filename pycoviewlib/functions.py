""" Copyright (C) 2019 Pico Technology Ltd. """
from pycoviewlib.constants import maxADC
from ctypes import c_int16, Array
import numpy as np
from datetime import datetime as dt
from typing import Union

def mV2adc(thresh: float, offset: float, range_: int) -> int:
	""" Convert ADC counts to millivolts """
	thresholdADC = int((thresh + offset * 1000) / range_ * maxADC)
	
	return thresholdADC

def parse_config() -> dict:
	""" Parser for .ini file """
	params = {}
	with open("config.ini", "r") as ini:
		for line in ini:
			if "[" in line or line == "\n":
				continue
			p = line.rstrip("\n").split(" = ")
			if p[1].isdigit():
				params[p[0]] = int(p[1])
			elif _isfloat(p[1]):
				params[p[0]] = float(p[1])
			elif p[1].isalpha():
				params[p[0]] = p[1]
			else:
				params[p[0]] = list(int(v) for v in p[1].split(","))
	params["maxSamples"] = params["preTrigSamples"] + params["postTrigSamples"]
	# Convert target channels to list if more than one
	if len(params["target"]) > 1:
		params["target"] = list(params["target"])

	return params

def parse_args(args: list) -> dict:
	""" Parse command line arguments """
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

def log(loghandle: str, entry: str, time=False) -> None:
	""" Write to log file """
	with open(f"./Data/{loghandle}", "a") as logfile:
		if time:
			logfile.write(f"[{dt.now().strftime('%H:%M:%S')}] {entry}\n")
		else:
			logfile.write(f"\t{entry}\n")

### UTILITIES ###

def print_status(status: dict) -> None:
	""" Print status in columns (debug purposes) """
	if bool(status):
		print("==> PicoScope Exit Status:")
		col_width = max([len(k) for k in status.keys()])
		for key, value in status.items():
			print(f"{key: <{col_width}} {value:}")
	else:
		print("No status to show.")

def key_from_value(
		dictionary: dict,
		value: Union[int,str]
		) -> Union[list,str]:
	try:	
		keys = [k for k, v in dictionary.items() if value in v]
	except TypeError:
		keys = [k for k, v in dictionary.items() if v == value]
	except IndexError:
		return ""
	if len(keys) == 1:
		return keys[0]
	else:
		return keys

def _isfloat(value: str) -> bool:
	try:
		float(value)
		return True
	except ValueError:
		return False

