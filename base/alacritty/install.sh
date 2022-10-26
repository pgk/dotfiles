#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath $0)
PLUGIN_PATH=`dirname $full_path`
ROOT_PATH=$(dirname "$PLUGIN_PATH")


cat "$PLUGIN_PATH/themes/tokyo-night.yml" > "$PLUGIN_PATH/themes/current.yml"
mkdir -p "$HOME/.config/alacritty"
ln -sf "$PLUGIN_PATH/alacritty.yml" "$HOME/.config/alacritty/alacritty.yml"

