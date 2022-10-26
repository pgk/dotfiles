#!/usr/bin/env bash
# coding: utf-8

set -e

export USER_HOME="$HOME";
export DOTFILE_FOLDER="$USER_HOME/dotfiles";

source "$DOTFILE_FOLDER/includes/os-detect.sh"
source "$DOTFILE_FOLDER/includes/check-dotfile-location.sh"

declare -a bins=("git" "vim" "curl")

## now loop through the above array
for needed_program in "${bins[@]}"
do
	echo "checking if bin installed: $needed_program"
	command -v "$needed_program" > /dev/null 2>&1 || {
		echo "$needed_program is not available. please install to continue";
        	exit 1;
	}
	echo "yes."
done


# source "$HOME/.dotfileprefs"
bash "$DOTFILE_FOLDER/base/bash/install.sh"
bash "$DOTFILE_FOLDER/base/git/install.sh"
bash "$DOTFILE_FOLDER/base/ctags/install.sh"
bash "$DOTFILE_FOLDER/base/vim/install.sh"

