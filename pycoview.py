""" Copyright (C) 2019 Pico Technology Ltd. """
import subprocess
from os import path

python = path.expanduser("~/.venv/bin/python3")
exitCode = subprocess.call([python, "tdc.py", "150", "log"])

if exitCode != 0:
	print("/!\\")
