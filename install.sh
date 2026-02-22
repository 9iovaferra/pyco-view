#!/usr/bin/env bash

PYCOVIEW=$HOME/.local/share/pycoview
ICONS=$HOME/.icons
APPS=$HOME/.local/share/applications
mkdir -p $PYCOVIEW

# Check if drivers exist, if not install them
if ! { [ -f "/opt/picoscope/lib/libpicoipp.so" ] && \
	   [ -f "/opt/picoscope/lib/libps6000a.so" ] && \
	   [ -f "/opt/picoscope/lib/libpsospa.so" ]; }
then 
	zenity --question \
		--title="PycoView Installer" \
		--text="PicoScope drivers are not installed. Download and install them now?"
	if [ $? = 0 ]; then
		mkdir -p $PYCOVIEW/drivers/tmp
		curl --output-dir $PYCOVIEW/drivers -O \
			https://labs.picotech.com/debian/pool/main/libp/libpicoipp/libpicoipp_1.1.2-4r56_armhf.deb
		curl --output-dir $PYCOVIEW/drivers -O \
			https://labs.picotech.com/rc/picoscope7/debian/pool/main/libp/libps6000a/libps6000a_2.0.161-0r193_armhf.deb
		curl --output-dir $PYCOVIEW/drivers -O \
			https://labs.picotech.com/rc/picoscope7/debian/pool/main/libp/libpsospa/libpsospa_1.0.158-0r5815_armhf.deb
		dpkg-deb -R $PYCOVIEW/drivers/libpicoipp_1.1.2-4r56_armhf.deb $PYCOVIEW/drivers/tmp
		echo "/etc/ld.so.conf.d/picoscope.conf" > $PYCOVIEW/drivers/tmp/DEBIAN/conffiles
		dpkg-deb -b $PYCOVIEW/drivers/tmp drivers/libpicoipp_1.1.2-4r56_armhf_fixed.deb
		sudo apt install $PYCOVIEW/drivers/libpicoipp_1.1.2-4r56_armhf_fixed.deb
		sudo apt install $PYCOVIEW/drivers/libps6000a_2.0.161-0r193_armhf.deb
		sudo apt install $PYCOVIEW/drivers/libpsospa_1.0.158-0r5815_armhf.deb
		[[ -d "$PYCOVIEW/drivers" ]] && rm -rf drivers/
	fi
fi

# Move app in place
[ -d "$(pwd)/PycoView" ] && cp -r $(pwd)/PycoView/* $PYCOVIEW/

mkdir -p $ICONS
mkdir -p $APPS
mkdir -p $HOME/Documents/PycoView/Data

# Create shortcuts
printf %"s\n" "[Desktop Entry]" \
	"Type=Application" \
	"Name[it]=PycoView" \
	"Name[en]=PycoView" \
	"Comment[it]=Applicazione interattiva in Python per lo studio dei raggi cosmici" \
	"Comment[en]=Interactive Python app for the study of cosmic rays" \
	"Path=$PYCOVIEW" \
	"Exec=$PYCOVIEW/PycoView" \
	"Icon=pycoview" \
	"Terminal=false" \
	"Categories=Education;Science;" \
	"Keywords[it]=Python;Fisica;Raggi cosmici;" \
	"Keywords[en]=Python;Physics;Cosmic rays;" > $APPS/pycoview.desktop

chmod 644 $APPS/pycoview.desktop
ln -s $APPS/pycoview.desktop  $HOME/Desktop/
 
ln -s $HOME/Documents/PycoView/Data/ $HOME/Desktop/

cp -p $(pwd)/pycoview.png $ICONS/pycoview.png

zenity --info \
	--title="PycoView Installer" \
	--text="PycoView was installed succesfully!" \
	--ok-label="Close"

unset PYCOVIEW
unset ICONS
unset APPS
