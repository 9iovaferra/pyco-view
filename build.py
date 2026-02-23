import PyInstaller.__main__ as pyi
from shutil import rmtree
from pycoviewlib.constants import PV_DIR
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
import os

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
for start in ['backup', 'core', 'presets', 'pycoviewlib']:
    start = Path(start).expanduser()
    for root, dirs, files in os.walk(start):
        for file in files:
            if any([ex in root for ex in ['__pycache__', 'egg-info', 'build']]):
                continue
            if '.sdkwarning' in file:
                continue
            thing = os.path.join(root, file)
            arcname = 'PycoView/' + thing
            zf.write(thing, arcname=arcname)
zf.write('install.sh')
zf.testzip()
zf.close()

print('Cleaning up...')
rmtree('build/')

print('Done! Run `install.sh` to complete installation.')
