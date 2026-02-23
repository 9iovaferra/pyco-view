import PyInstaller.__main__ as pyi
from shutil import rmtree
from pycoviewlib.constants import PV_DIR
from zipfile import ZipFile, ZIP_DEFLATED


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
	f'--splash={PV_DIR}/splash.jpg',
	'--log-level=WARN'
	])

print('Creating archive for distribution...')
zf = ZipFile('PycoView.zip', mode='w', compression=ZIP_DEFLATED, compresslevel=9)
zf.write('PycoView', arcname='PycoView/PycoView')
zf.write('pycoview.png', arcname='PycoView/pycoview.png')
zf.write('logo.png', arcname='PycoView/logo.png')
zf.write('backup/config.ini.bak', arcname='PycoView/backup/config.ini.bak')
zf.write('core', arcname='PycoView/core')
zf.write('presets', arcname='PycoView/presets')
zf.write('pycoviewlib', arcname='PycoView/pycoviewlib')
zf.write('install.sh')
zf.testzip()
zf.close()

print('Cleaning up...')
rmtree('build/')

print('Done! Run `install.sh` to complete installation.')
