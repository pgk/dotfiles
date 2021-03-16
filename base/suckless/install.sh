#!/usr/bin/env sh
set -e

thisdir="$HOME/dotfiles"
suckless="$HOME/suckless"

mkdir -p "$suckless"

[ -d "$suckless/dwm" ] || git clone https://git.suckless.org/dwm "$suckless/dwm"
[ -d "$suckless/dwmstatus" ] || git clone https://git.suckless.org/dwmstatus "$suckless/dwmstatus"
[ -d "$suckless/dmenu" ] || git clone https://git.suckless.org/dmenu "$suckless/dmenu"
[ -d "$suckless/st" ] || git clone https://git.suckless.org/st "$suckless/st"
[ -d "$suckless/slock" ] || git clone https://git.suckless.org/slock "$suckless/slock"

cd "$suckless/dmenu" && sudo make clean install 
cd "$suckless/dwm" && sudo make clean install 
cd "$suckless/dwmstatus" && sudo make clean install 
cd "$suckless/st" && sudo make clean install 
cd "$suckless/slock" && sudo make clean install 
