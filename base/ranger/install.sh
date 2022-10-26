#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath "$0")
PLUGIN_PATH=$(dirname "$full_path")


sudo apt update

sudo apt-get update
sudo apt-get install -y ranger caca-utils highlight atool w3m poppler-utils mediainfo

mkdir -p ~/.local/share/Trash/files/
ln -sf "$PLUGIN_PATH/ranger" "$HOME/.config"

