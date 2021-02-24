#!/usr/bin/env bash

# if we are not on a mac exit
set -e


[[ $OSTYPE == *"darwin"* ]] || {
	echo "Not running on darwin. Exiting..."
	exit
}

# command -v brew > /dev/null || {
# 	echo "installing homebrew"
# 	/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
# }



# brew cask install supercollider virtualbox audacity adium colloquy java macvim mysqlworkbench osxfuse vagrant vlc wine-stable wireshark xquartz atom


