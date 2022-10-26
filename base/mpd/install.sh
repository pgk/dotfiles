#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath $0)
PLUGIN_PATH=`dirname $full_path`

mkdir -p "$HOME/.config/mpd"
ln -sf "$PLUGIN_PATH/mpd.conf" "$HOME/.config/mpd/mpd.conf"


