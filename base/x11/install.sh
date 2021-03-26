#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath $0)
PLUGIN_PATH=`dirname $full_path`

# mkdir -p "$HOME/.config/i3"
# mkdir -p "$HOME/.config/i3status"
ln -sf "$PLUGIN_PATH/.xinitrc" "$HOME/.xinitrc"
ln -sf "$PLUGIN_PATH/.xmodmap" "$HOME/.xmodmap"
# ln -sf "$PLUGIN_PATH/i3status-config" "$HOME/.config/i3status/config"

