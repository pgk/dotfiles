#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath $0)
PLUGIN_PATH=$(dirname $full_path)

mkdir -p "$HOME/.vim/bundle"

# mkdir -p "$HOME/.vim"
# mkdir -p "$HOME/.vim-tmp"
mkdir -p "$HOME/.config"
ln -sf "$PLUGIN_PATH/nvim" "$HOME/.config"
# mkdir -p "$HOME/.vim/nvim/gutentags"
# ln -sf "$PLUGIN_PATH/.vimrc" "$HOME/.vimrc"
# ln -sf "$PLUGIN_PATH/.ideavimrc" "$HOME/.ideavimrc"
# ln -sf "$PLUGIN_PATH/.vim/after" "$HOME/.vim"
# ln -sf "$PLUGIN_PATH/.vim/autoload" "$HOME/.vim"
# ln -sf "$PLUGIN_PATH/.vim/ftdetect" "$HOME/.vim"
# ln -sf "$PLUGIN_PATH/.vim/ftplugin" "$HOME/.vim"
# ln -sf "$PLUGIN_PATH/.vim/indent" "$HOME/.vim"
# ln -sf "$PLUGIN_PATH/.vim/plugin" "$HOME/.vim"
# ln -sf "$PLUGIN_PATH/.vim/syntax" "$HOME/.vim"
# ln -sf "$PLUGIN_PATH/.vim/UltiSnips" "$HOME/.vim"
# ln -sf "$PLUGIN_PATH/.vim/lua" "$HOME/.config/nvim"
# ln -sf "$PLUGIN_PATH/.config/nvim/coc-settings.json" "$HOME/.config/nvim/coc-settings.json"
