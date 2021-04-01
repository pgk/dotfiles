#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath "$0")
PLUGIN_PATH=$(dirname "$full_path")

ln -sf "$PLUGIN_PATH/global.ctags" "$HOME/.ctags"

