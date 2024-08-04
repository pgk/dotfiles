#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath $0)
PLUGIN_PATH=`dirname $full_path`
ROOT_PATH=$(dirname "$PLUGIN_PATH")


mkdir -p "$HOME/.cddb"
ln -sf "$PLUGIN_PATH/.abcde.conf" "$HOME/.abcde.conf"

