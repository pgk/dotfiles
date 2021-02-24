#!/bin/sh
# coding: utf-8

set -e

USER_HOME="$HOME";
DOTFILE_FOLDER="$USER_HOME/dotfiles";

if [[ "$OSTYPE" == "linux-gnu" ]]; then
  export SYSTEM_KIND='linux';
elif [[ "$OSTYPE" == "darwin"* ]]; then
  # Mac OSX
  export SYSTEM_KIND='mac';
else
  # Unknown.
  export SYSTEM_KIND='unknown';
  echo 'unknown system type'
  exit 1;
fi

ls $DOTFILE_FOLDER >/dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "dotfile location is not $DOTFILE_FOLDER. Exiting";
    exit 1;
else
    echo "dotfile folder found";
    cd $DOTFILE_FOLDER || {
        echo "can not change diretory to $DOTFILE_FOLDER";
        exit 1;
    }
fi
