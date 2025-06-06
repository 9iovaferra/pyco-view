#!/usr/bin/env bash

ICONS=$HOME/.icons
APPS=$HOME/.local/share/applications

mkdir -p $ICONS
mkdir -p $APPS

cp -p pycoview.png $ICONS/pycoview.png
cp -p pycoview.desktop $APPS/pycoview.desktop

echo "Copied icon to ${ICONS}/pycoview.png"
echo "Copied desktop entry to ${APPS}/pycoview.desktop"
echo "Pycoview is now installed!"

unset ICONS
unset APPS
