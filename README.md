# PycoView
Applicazione interattiva in Python per esperienze di interazione radiazione-materia che sfruttano il PicoScope 6404D.

## Setup iniziale
Per il momento questo procedimento funziona solo su un sistema operativo di architettura 32bit. I pezzi di codice forniti sono per piattaforma Linux.
1. Assicurarsi che Python sia installato
```bash
sudo apt-get install python
```
3. Creare un ambiente Python virtuale
```bash
python -m venv <path-to-venv>/.venv
```
4. Per convenienza, creare un alias per questo ambiente virtuale
```bash
echo "alias python='<path-to-venv>/.venv/bin/python3'" >> ~/.bash_profile
source ~/.bash_profile
```
5. Per mantenere questo alias ad ogni login, aggiungere quanto segue al .bashrc:
```bash
if [ -f ~/.bash_profile ]; then
  source .bash_profile
fi
```

## Installazione dei driver
I file .deb per [libpicoipp](https://labs.picotech.com/debian/pool/main/libp/libpicoipp/libpicoipp_1.1.2-4r56_armhf.deb) e [libps6000](https://labs.picotech.com/debian/pool/main/libp/libps6000/libps6000_2.1.40-6r2131_armhf.deb) sono già presenti nella repository. Per installare questi driver è necessario cambiare una linea dal pacchetto:
1. Navigare nella directory di download delle librerie e creare una cartella temporanea:
```bash
mkdir tmp
```
2. Decomprimere la libreria con
```bash
dpkg-deb -R libpicoipp_1.1.2-4r56_armhf.deb tmp
```
3. Aprire in nano o vim tmp/DEBIAN/conffiles e rimuovere la linea: "etc/ld.so.conf.d/picoscope.conf"
4. Ricostruire il file .deb con
```bash
dpkg-deb -b tmp libpicoipp_1.1.2-4r56_armhf_fixed.deb
```
5. Installare la libreria corretta:
  ```bash
  sudo apt install /path/to/libpicoipp_1.1.2-4r56_armhf_fixed.deb
  ```
6. Installare libps6000:
  ```bash
  sudo apt install /path/to/libps6000_2.1.40-6r2131_armhf.deb
  ```
"libpicoipp" e "libps6000" saranno installate in /opt/picoscope/lib.

## Installazione picosdk
Repo ufficiale: [picosdk-python-wrappers](https://github.com/picotech/picosdk-python-wrappers/tree/master?tab=readme-ov-file).
1. Scaricare l'intero master e decomprimerlo in una cartella a piacere.
2. Navigare nella cartella appena installata e installare tutti i moduli necessari con:
   ```bash
   py -m pip install .
   ```
3. Per aggirare un errore nella chiamata a numpy, lanciare il comando:
  ```bash
  sudo apt-get install libopenblas-dev
  ```
A questo punto lanciando l'importazione del modulo con "from picosdk import ps6000 as ps" dovrebbe andare a buon fine.

## Problemi comuni
### La finestra dell'app non appare
Una possibile causa è un errore di Tkinter: `_tkinter.tclerror: couldn't connect to display` dovuto al fatto che il modulo non è compatibile con il server grafico Wayland. Per risolvere il problema bisogna passare al server X11, attraverso il menu da terminale `raspi-config` 
