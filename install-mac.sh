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


brew install reattach-to-user-namespace abcde cd-discid fd ripgrep
brew install virtualbox audacity adium osxfuse vagrant vlc xquartz alacritty --cask


