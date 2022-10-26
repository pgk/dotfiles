#!/usr/bin/env sh
set -e

sudo apt update

sudo apt install -y neovim git python3 build-essential xclip xsel \
	xorg libx11-dev libxinerama-dev libxft-dev xinit feh \
	ranger newsboat xbindkeys fonts-inconsolata x11-xserver-utils xorg-dev \
	xautolock xtrlock

