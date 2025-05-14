""" Copyright (C) 2019 Pico Technology Ltd. """
from pycoviewlib.constants import maxADC, PV_DIR
from dataclasses import dataclass
from ctypes import c_int16, Array
import numpy as np
from datetime import datetime as dt
from time import perf_counter
from os import listdir
from typing import Union

def mV2adc(thresh: float, offset: float, range_: int) -> int:
	""" Convert millivolts to ADC counts """
	adcCounts = int((thresh + offset * 1000) / range_ * maxADC)

	return adcCounts

def parse_config() -> dict:
	""" Parser for .ini file """
	params = {}
	if 'config.ini' not in listdir(PV_DIR):
		with open(f'{PV_DIR}/backup/config.ini.bak', 'r') as ini:
			lines = ini.readlines()
		with open(f'{PV_DIR}/config.ini', 'w') as ini:
			ini.writelines(lines)

	with open('config.ini', 'r') as ini:
		for line in ini:
			if '[' in line or line == '\n':
				continue
			p = line.rstrip('\n').split(' = ')
			if p[1].isdigit():
				params[p[0]] = int(p[1])
			elif _isfloat(p[1]):
				params[p[0]] = float(p[1])
			elif p[1].isalpha():
				params[p[0]] = p[1]
			else:
				params[p[0]] = list(int(v) for v in p[1].split(','))
	params['maxSamples'] = params['preTrigSamples'] + params['postTrigSamples']
	# Convert target channels to list if more than one
	# if len(params['target']) > 1:
	# 	params['target'] = list(params['target'])

	return params

def parse_args(args: list) -> dict:
	"""
	Parse command line arguments.
	(Deprecated: it was used during development)
	"""
	options = dict.fromkeys([
		'captures', 'plot', 'log', 'dformat', 'trigs', 'livehist'
		])
	for arg in args:
		if arg.isdigit():
			options['captures'] = int(arg)
			break
		else:
			options['captures'] = 1
	options['plot'] = True if 'plot' in args else False
	options['log'] = True if 'log' in args else False
	options['dformat'] = 'csv' if 'csv' in args else 'txt'
	options['trigs'] = 4 if '4way' in args else 2
	options['livehist'] = True if 'live' in args else False

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
		'open': {'mV': threshold, 'ns': 0.0, 'index': 0},
		'closed': {'mV': threshold, 'ns': 0.0, 'index': 0}
		}
	hit = 0
	minValue = min(buffer)
	minValueIndex = buffer.index(minValue)
	minDifference = minValue - threshold
	for i in range(minValueIndex):
		if abs(buffer[i] - threshold) < abs(minDifference):
			hit = i
			minDifference = buffer[i] - threshold
	gateChX['open']['ns'] = time[hit]
	gateChX['open']['index'] = hit
	minDifference = minValue - threshold
	for i in range(minValueIndex, maxSamples):
		if abs(buffer[i] - threshold) < abs(minDifference):
			hit = i
			minDifference = buffer[i] - threshold
	gateChX['closed']['ns'] = time[hit]
	gateChX['closed']['index'] = hit

	return gateChX

def calculate_charge(
		buffer: Array[c_int16],
		gate: tuple[int],
		timeIntervalns: float,
		coupling: int
		) -> float:
	"""
	Total charge deposited by the particle in the detector.
	It is defined as the integral of voltage with respect to time,
	multiplied by dt and divided by the termination coupling.
	"""
	charge = 0.0
	for i in range(gate[0], gate[1]):
		charge += abs(buffer[i])
	charge *= (timeIntervalns / coupling)

	return charge

def log(loghandle: str, entry: str, time=False) -> None:
	""" Write to log file """
	with open(f'{PV_DIR}/Data/{loghandle}', 'a') as logfile:
		if time:
			logfile.write(f"[{dt.now().strftime('%H:%M:%S')}] {entry}\n")
		else:
			logfile.write(f"{' ' * 11}{entry}\n")  # 11 = len of timestamp

# ------------------------- DATA CLASSES --------------------------

@dataclass(order=True)
class DataPack():
	def __init__(self, x=0.0):
		self.x = x

# --------------------------- UTILITIES ---------------------------

def get_timeinterval(timebase: int) -> str:
	"""
	Calculate time interval between captures based on timebase to display on widget.
	See PS6000 Series Programmer's guide
	"""
	interval = int(2 ** timebase / 5e-3 if timebase in range(5) else (timebase - 4) / 1.5625e-4)
	return f'{interval} ps' if interval < 1000 else f'{round(interval / 1000, 1)} ns'

class Manager():
	"""
	During acquisition, script listens for 'q' (quit) command from
	GUI (Stop button was pressed)
	"""
	def __init__(self):
		self.keystroke = 'q'
		self.continue_ = True

	def listen(self):
		event = input('')
		if event == self.keystroke:
			self.continue_ = False

class Benchmark:
	def __init__(self):
		self.stopwatch = [perf_counter()]
		self.convert = {"ms": 1000, "µs": 1000000}

	def split(self):
		self.stopwatch.append(perf_counter())

	def results(self, unit="ms"):
		avg = .0
		for i in range(len(self.stopwatch) - 1):
			avg += (self.stopwatch[i + 1] - self.stopwatch[i])
		print(f"Total execution time: {dt.strftime(dt.utcfromtimestamp(avg), '%T.%f')[:-3]}")
		avg /= (len(self.stopwatch) - 1)
		print(f'Average time per capture: {avg * self.convert[unit]:.1f} {unit}')
		print(f'Event resolution: {1/avg:.1f} Hz')

def print_status(status: dict) -> None:
	""" Print status in columns (debug purposes) """
	if bool(status):
		print('==> PicoScope Exit Status:')
		col_width = max([len(k) for k in status.keys()])
		for key, value in status.items():
			print(f'{key: <{col_width}} {value:}')
	else:
		print('No status to show.')

def key_from_value(dictionary: dict, value: Union[int, str]) -> Union[list, str]:
	try:
		keys = [k for k, v in dictionary.items() if value in v]
	except TypeError:
		keys = [k for k, v in dictionary.items() if v == value]
	except IndexError:
		return ''
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
