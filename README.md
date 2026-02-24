# PycoView
<p align="center">
	<img width="65%" alt="PycoView screenshot" src="https://github.com/9iovaferra/pyco-view/blob/main/screenshot.png" />
</p>

<div align="center">
	Interactive Raspberry Pi Python app for the study of <b>cosmic rays</b> via scintillation detectors<br>
	and <b>PicoScope® 3000E</b> series oscilloscopes.
</div>

## Installation
This section guides you through the installation of the executable binary only, ready to be used for lab experiences. To configure the development environment to edit the source code, follow the steps in [Development setup](#development-setup) below.

> [!IMPORTANT]
> The latest Raspberry Pi OS version PycoView is (currently) compatible with is the one based on **Debian 12 (Bookworm), 32bit architecture**, for the Raspberry Pi 5. You can download an image from the [official Raspberry Pi OS archive](https://www.raspberrypi.com/software/operating-systems/).

1. Download the [latest release archive](https://github.com/9iovaferra/pyco-view/releases/latest) and extract it in the `~/Downloads/` folder.
2. Double-click on the `install.sh` file: this script will
   
    - ensure PicoScope drivers are installed, downloading them from the official repository if necessary;
    - check the Python environment and install the relevant modules;
    - move items in place at `~/.local/share/pycoview`;
    - create links on the desktop and app launcher menu for easy access.

## Development setup

> [!NOTE]
> In the following steps, swap `path/to/` with the appropriate directory.

1. Ensure the latest version of Python is installed
	```bash
	sudo apt-get install python
	```

2. Create a virtual Python environment
	```bash
	python3 -m venv path/to/.venv
	```
	
	- It is convenient to create aliases for Python and pip package manager
		```bash
		echo "alias py='path/to/.venv/bin/python3'" >> ~/.bashrc
		echo "alias pip='path/to/.venv/bin/pip'" >> ~/.bashrc
		source ~/.bashrc
		```

3. Clone this repository in `~/.local/share/pycoview` (some app scripts rely on this location to find configuration files)
	```bash
	git clone https://github.com/9iovaferra/pyco-view.git pycoview
 	```

4. The `install.sh` script can be used to install PicoScope drivers and the PicoScope software development kit (SDK).
	<details>
	
	<summary>Manual drivers installation</summary>
	
	1. Download the Debian packages:
		- [libpicoipp_1.1.2-4r56_armhf.deb](https://labs.picotech.com/debian/pool/main/libp/libpicoipp)
		- [libps6000a_2.0.161-0r193_armhf.deb](https://labs.picotech.com/rc/picoscope7/debian/pool/main/libp/libps6000a)
		- [libpsospa_1.0.158-0r5815_armhf.deb](https://labs.picotech.com/rc/picoscope7/debian/pool/main/libp/libpsospa)
	
	2. It is necessary to modify the <b>libpicoipp</b> package. From [the PicoTech forum](https://www.picotech.com/support/viewtopic.php?p=145119&sid=a2b0fc420d0d17ed7ebf5339db628d9d#p145119), navigate to the download location and create a temporary folder
		```bash
		mkdir tmp
		```
	
	3. Decompress the archive
		```bash
		dpkg-deb -R libpicoipp_1.1.2-4r56_armhf.deb tmp
		```
	
	4. Open the file `tmp/DEBIAN/conffiles` in a text editor (e.g. vim, nano) and delete the line: `etc/ld.so.conf.d/picoscope.conf`. Save the file and exit.
	
	5. Re-build the package with
		```bash
		dpkg-deb -b tmp libpicoipp_1.1.2-4r56_armhf_fixed.deb
		```
	
	6. Lastly, install the drivers
		```bash
		sudo apt install /path/to/libpicoipp_1.1.2-4r56_armhf_fixed.deb
		sudo apt install /path/to/libps6000a_2.0.161-0r193_armhf.deb
		sudo apt install /path/to/libpsospa_1.0.158-0r5815_armhf.deb
		```
	You can check if the installation was successful by inspecting `/opt/picoscope/lib`.
	
	</details>

	<details>

	<summary>Manual SDK installation</summary>
		
	Follow the instruction on the [official GitHub page](https://github.com/picotech/picosdk-python-wrappers/tree/master?tab=readme-ov-file).
		
	</details>


## Common issues
### PycoView cannot be found in the app menu
PycoView is categorized under **"Education"**. Launch *Main Menu Editor* and tick the *Education* box.

### The Numpy module cannot be installed
It may be due to the missing OpenBLAS package, try installing it with
```bash
sudo apt-get install libopenblas-dev
```

### The app window does not show up or loads extremely slow
The UI is written with the Tcl/Tk Python wrapper module Tkinter. This module does not play nice with the **Wayland** compositor, [enabled by default](https://www.raspberrypi.com/news/bookworm-the-new-version-of-raspberry-pi-os/) on all Raspberry Pi OS versions from Bookworm onward. It is therefore strongly recommended to **switch to the X11 compositor** via the terminal utility `raspi-config`.
