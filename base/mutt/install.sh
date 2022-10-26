#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath $0)
PLUGIN_FOLDER=`dirname $full_path`

mkdir -p "$HOME/.config/mutt"

[ -f "$HOME/.config/mutt/mutt_extras" ] || echo '# add your mutt accounts here.' > "$HOME/.config/mutt/mutt_extras"

ln -sf "$PLUGIN_FOLDER/muttrc" "$HOME/.config/mutt/muttrc"
