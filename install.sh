#!/usr/bin/env bash
# coding: utf-8

set -e

export USER_HOME="$HOME"
export DOTFILE_FOLDER="$USER_HOME/dotfiles"

source "$DOTFILE_FOLDER/includes/os-detect.sh"
source "$DOTFILE_FOLDER/includes/check-dotfile-location.sh"

# if [[ $install_deps -eq 1 ]]; then
# 	mkdir -p "$HOME/dev/go"
# 	export GOPATH="$HOME/dev/go"
# 		command -v lsb_release && lsb_release -d | awk -F"\t" '{print $2}' | grep -iE 'debian|ubuntu' > /dev/null && {
# 	echo "adding dependencies for debian system"
# 	apt update
# 	apt install -y python3 python3-pip python3-dev python3-venv golang curl git wget

# 	echo "done installing deps"
# 	exit 0;
# }

# if [[ "$OSTYPE" == *"darwin"* ]]; then
# 	echo "Running on darwin"
# 	command -v brew > /dev/null || {
# 		echo "installing homebrew"
# 		/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
# 	}
# 	echo "we have brew"
# 	brew update
# 	declare -a mac_installation_bins=("git" "curl" "vim" "python3")
# 	## now loop through the above array
# 	for needed_program in "${mac_installation_bins[@]}"
# 	do
# 		echo "checking if bin installed: $needed_program"
# 		command -v "$needed_program" > /dev/null 2>&1 || {
# 			echo "$needed_program is not available. installing";
# 			brew install "$needed_program"
# 		}
# 		echo "yes."
# 	done

# 	echo "done installing deps"
# 	exit 0;
# fi

# echo "Install deps finished"
# exit 0
# fi

declare -a bins=("git" "vim" "curl")

## now loop through the above array
for needed_program in "${bins[@]}"; do
  echo "checking if bin installed: $needed_program"
  command -v "$needed_program" >/dev/null 2>&1 || {
    echo "$needed_program is not available. please install to continue"
    exit 1
  }
  echo "yes."
done

if [ -f "$HOME/.dotfileprefs" ]; then
  source "$HOME/.dotfileprefs"
fi

bash "$DOTFILE_FOLDER/base/bash/install.sh"
bash "$DOTFILE_FOLDER/base/git/install.sh"
bash "$DOTFILE_FOLDER/base/tmux/install.sh"
bash "$DOTFILE_FOLDER/base/ctags/install.sh"
bash "$DOTFILE_FOLDER/base/vim/install.sh"
bash "$DOTFILE_FOLDER/base/neovim/install.sh"
bash "$DOTFILE_FOLDER/base/alacritty/install.sh"
bash "$DOTFILE_FOLDER/base/abcde/install.sh"
# bash "$DOTFILE_FOLDER/base/unison/install.sh"

cd "$DOTFILE_FOLDER"

for dir in ./plugins/*/; do
  # find "$dir" >"$dir/original_filenames.txt"
  if [ -f "$dir/install.sh" ]; then
    echo "Installing $dir"
    bash "$dir/install.sh"
  fi
done

# install system-specific stuff.
bash "$DOTFILE_FOLDER/install-$SYSTEM_KIND.sh"
