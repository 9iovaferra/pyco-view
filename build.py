import PyInstaller.__main__ as pyi
from pathlib import Path
from shutil import copy2, move
from os import remove, chmod
from pycoviewlib.constants import PV_DIR

# icon_folder = Path('~/.icons').expanduser()
# app_folder = Path('~/.local/share/applications').expanduser()

# icon_folder.mkdir(exist_ok=True)
# app_folder.mkdir(exist_ok=True)

print('Building PycoView with `pyinstaller`. This might take a minute...')
pyi.run([
	'main.py',
	'--onefile',
	'--clean',
	'--hidden-import=PIL._tkinter_finder',
	'--name=PycoView',
	'--noconsole',
	'--distpath=./',
	'--specpath=./build',
	'--upx-dir=~/Documents/upx-5.0.1-arm64_linux/upx',
	f'--splash={PV_DIR}/splash.png',
	'--log-level=WARN'
	])

with open('pycoview.desktop', 'w') as desktop_entry:
	info = [
		'[Desktop Entry]\n',
		'Type=Application\n',
		'Name[it]=PycoView\n',
		'Name[en]=PycoView\n',
		'Comment[it]=Applicazione interattiva in Python per lo studio dei raggi cosmici\n',
		'Comment[en]=Interactive Python app for the study of cosmic rays\n',
		f'Path={PV_DIR}\n',
		f'Exec={PV_DIR}/PycoView\n',
		'Icon=pycoview\n'
		'Terminal=false\n',
		'Categories=Education;Science;\n',
		'Keywords[it]=Python;Fisica;Raggi cosmici;\n',
		'Keywords[en]=Python;Physics;Cosmic rays;\n'
		]
	desktop_entry.writelines(info)

chmod('pycoview.desktop', 0o644)
# copy2(f'{PV_DIR}/pycoview.png', icon_folder)
# copy2(f'{PV_DIR}/pycoview.desktop', f'{app_folder}/pycoview.desktop')
# remove(f'{PV_DIR}/pycoview.desktop')

print('Done! Run `install.sh` to complete installation.')
