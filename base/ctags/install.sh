#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath "$0")
PLUGIN_PATH=$(dirname "$full_path")

mkdir -p "$HOME/.config/"
cp -fr "$PLUGIN_PATH/ctags" "$HOME/.config"

