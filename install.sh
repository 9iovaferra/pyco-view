#!/usr/bin/env bash

ICONS=$HOME/.icons
APPS=$HOME/.local/share/applications

# Check if drivers exist, if not install them
if [[ ! -f "/opt/picoscope/lib/libpicoipp.so" && ! -f "/opt/picoscope/lib/libps6000.so" ]]
then 
	zenity --question \
		--title="PycoView Installer" \
		--text="PicoScope drivers are not installed. Download and install them now?"
	if [ $? = 0 ]; then
		mkdir -p drivers/tmp
		curl --output-dir drivers -O \
			https://labs.picotech.com/debian/pool/main/libp/libpicoipp/libpicoipp_1.1.2-4r56_armhf.deb
		curl --output-dir drivers -O \
			https://labs.picotech.com/debian/pool/main/libp/libps6000/libps6000_2.1.40-6r2131_armhf.deb
		dpkg-deb -R drivers/libpicoipp_1.1.2-4r56_armhf.deb drivers/tmp
		echo "/etc/ld.so.conf.d/picoscope.conf" > drivers/tmp/DEBIAN/conffiles
		dpkg-deb -b drivers/tmp drivers/libpicoipp_1.1.2-4r56_armhf_fixed.deb
		sudo apt install $(pwd)/drivers/libpicoipp_1.1.2-4r56_armhf_fixed.deb
		sudo apt install $(pwd)/drivers/libps6000_2.1.40-6r2131_armhf.deb
		rm -rf drivers/
	fi
fi

mkdir -p $ICONS
mkdir -p $APPS

printf %"s\n" "[Desktop Entry]" \
	"Type=Application" \
	"Name[it]=PycoView" \
	"Name[en]=PycoView" \
	"Comment[it]=Applicazione interattiva in Python per lo studio dei raggi cosmici" \
	"Comment[en]=Interactive Python app for the study of cosmic rays" \
	"Path=$(pwd)/PycoView" \
	"Exec=$(pwd)/PycoView/PycoView" \
	"Icon=pycoview" \
	"Terminal=false" \
	"Categories=Education;Science;" \
	"Keywords[it]=Python;Fisica;Raggi cosmici;" \
	"Keywords[en]=Python;Physics;Cosmic rays;" > $APPS/pycoview.desktop

chmod 644 $APPS/pycoview.desktop

cp -p $(pwd)/PycoView/pycoview.png $ICONS/pycoview.png

zenity --info \
	--title="PycoView Installer" \
	--text="PycoView was installed succesfully!" \
	--ok-label="Close"

unset ICONS
unset APPS
