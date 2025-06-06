# PycoView
Applicazione interattiva in Python per esperienze di rivelazione di raggi cosmici che sfruttano l'oscilloscopio **PicoScope 6404D**.

## Installazione
Questa guida è dedicata all'installazione del solo file eseguibile dell'applicazione, pronta all'uso per esperienze di laboratorio. Per configurare un ambiente di sviluppo in cui modificare il codice sorgente di PycoView, si seguano i passaggi per il [setup dell'ambiente di sviluppo](setup-dell-ambiente-di-sviluppo-pycoview).

1. Per prima cosa, scaricare l'archivio dalla pagina [Releases](https://github.com/9iovaferra/pyco-view/releases/new) ed estrarlo in una cartella a piacere di cui si abbiano i permessi di lettura e scrittura.
2. Eseguire con un doppio click il file `install.sh`: questo script si occupa di verificare che i driver PicoScope siano installati correttamente e di creare un collegamento nel menu applicazioni. Se i driver non risultano installati, vengono scaricati dalla repository di Picotech.

## Setup dell'ambiente di sviluppo PycoView
Questo procedimento funziona esclusivamente su un **sistema operativo a 32bit**, in quanto le librerie fornite da Picotech per l'utilizzo del PicoScope sono compatibili solo con tale architettura. I pezzi di codice forniti nelle istruzioni che seguono sono per piattaforma **Debian Linux**.

> [!IMPORTANT]
> Ogni volta che si incontra `path/to/` nelle istruzioni che seguono bisogna sostituirlo con la directory scelta.

1. Assicurarsi che Python sia installato:
	```bash
	sudo apt-get install python
	```
3. Creare un **ambiente Python virtuale** in una directory a piacere:
	```bash
	python3 -m venv path/to/.venv
	```
4. È conveniente creare un **alias** per questo ambiente virtuale, sia per Python che per il suo strumento di installazione moduli **pip**. Il nome assegnato (quello tra `alias` e `=`) può essere scelto a piacere:
	```bash
	echo "alias py='path/to/.venv/bin/python3'" >> ~/.bash_profile
	echo "alias pip='path/to/.venv/bin/pip'" >> ~/.bash_profile
	source ~/.bash_profile
	```
5. Per mantenere questo alias ad ogni login, aggiungere quanto segue in fondo al file `~/.bashrc`:
	```bash
	echo -e "if [ -f ~/.bash_profile ]; then\n\tsource ~/.bash_profile\nfi" >> ~/.bashrc
	```

### Installazione dei driver
I **pacchetti Debian** per le librerie [libpicoipp_1.1.2-4r56_armhf.deb](https://labs.picotech.com/debian/pool/main/libp/libpicoipp) e [libps6000_2.1.40-6r2131_armhf.deb](https://labs.picotech.com/debian/pool/main/libp/libps6000) sono già presenti in questa repository nella cartella `libp`. Per installare questi driver è necessario **modificare il pacchetto libpicoipp**: di seguito ci sono le istruzioni per effettuare manualmente questa modifica (fonte: [post di AndrewA](https://www.picotech.com/support/viewtopic.php?p=145119&sid=a2b0fc420d0d17ed7ebf5339db628d9d#p145119) sul forum di supporto Picotech), tuttavia nella stessa cartella è presente anche l'archivio già modificato e si può saltare direttamente al passaggio (5).  
1. Navigare nella directory in cui sono state scaricate le librerie e creare una cartella temporanea:
	```bash
	mkdir tmp
	```
2. Decomprimere l'archivio:
	```bash
	dpkg-deb -R libpicoipp_1.1.2-4r56_armhf.deb tmp
	```
3. Aprire con un editor di testo (es. vim, nano) il file `tmp/DEBIAN/conffiles` e rimuovere la riga: `etc/ld.so.conf.d/picoscope.conf`. Salvare la modifica e uscire dall'editor di testo.
4. Ricostruire il file .deb con:
	```bash
	dpkg-deb -b tmp libpicoipp_1.1.2-4r56_armhf_fixed.deb
	```
5. Installare infine entrambe le librerie:
	```bash
	sudo apt install /path/to/libpicoipp_1.1.2-4r56_armhf_fixed.deb
	sudo apt install /path/to/libps6000_2.1.40-6r2131_armhf.deb
	```
**libpicoipp** e **libps6000** saranno installate in `/opt/picoscope/lib`.

### Installazione del Pico SDK (*Software Development Kit*)
1. Navigare nella [repository ufficiale](https://github.com/picotech/picosdk-python-wrappers/tree/master?tab=readme-ov-file), scaricare l'intero master e decomprimerlo in una cartella a piacere.
2. Navigare nella cartella appena installata e installare tutti i moduli necessari con (sostituire l'alias nel caso si sia scelto un nome diverso nel [Setup iniziale](#setup-iniziale)):
	```bash
	py -m pip install .
	```
3. Se dovesse esserci un errore nella chiamata a `numpy`, si può aggirare con il comando:
	```bash
	sudo apt-get install libopenblas-dev
	```
A questo punto l'**importazione del modulo** in Python (`from picosdk import ps6000 as ps`) dovrebbe andare a buon fine.

## Problemi comuni
### PycoView non si trova nel menu applicazioni
PycoView è categorizzato sotto l'etichetta **"Education"**. Se la categoria non è presente nel menu applicazioni, si può rendere visibile cercando: *Main Menu Editor* e spuntando la casella corrispondente a *Education*.

### Si è lanciato l'eseguibile, ma la finestra dell'app non appare
Una possibile causa è un errore di Tkinter: `_tkinter.tclerror: couldn't connect to display`, dovuto al fatto che **il modulo non è compatibile con il server grafico Wayland**. Per risolvere il problema bisogna **passare al server X11** (se l'applicazione è installata su un Raspberry Pi, questa procedura è possibile attraverso il menu da terminale `raspi-config`).
