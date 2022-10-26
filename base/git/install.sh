#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath $0)
PLUGIN_FOLDER=`dirname $full_path`

ln -sf "$PLUGIN_FOLDER/.gitconfig" "$HOME/.gitconfig"
ln -sf "$PLUGIN_FOLDER/.gitignore_global" "$HOME/.gitignore_global"

