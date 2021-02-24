#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath $0)
PLUGIN_FOLDER=`dirname $full_path`

ln -sf "$PLUGIN_FOLDER/.profile" "$HOME/.profile"
ln -sf "$PLUGIN_FOLDER/.bash_profile" "$HOME/.bash_profile"
ln -sf "$PLUGIN_FOLDER/.bash_login" "$HOME/.bash_login"
ln -sf "$PLUGIN_FOLDER/.bashrc" "$HOME/.bashrc"
ln -sf "$PLUGIN_FOLDER/.inputrc" "$HOME/.inputrc"

if [ ! -f ~/.envvars.sh ]; then
  echo 'Copying envvars example for you to fill in.'
   cp "$PLUGIN_FOLDER/envvars.example.sh"  ~/.envvars.sh
else
  echo 'Seems you have an envvars file on your $HOME. in case you need a bit of guidance on what it should contain:'
  echo '------- ENVVARS EXAMPLE -------'
  cat "$PLUGIN_FOLDER/envvars.example.sh"
  echo '-------------------------------'
fi

