#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath "$0")
PLUGIN_PATH=$(dirname "$full_path")

command -v php > /dev/null 2>&1 || {
  echo "Fatal: PHP is not available. Install it and run me again."
  exit 1;
}

command -v git > /dev/null 2>&1 || {
  echo "Fatal: Git is not available. Install it and run me again."
  exit 1;
}

command -v composer > /dev/null 2>&1 || {
  echo "composer is not available. Installing..."
  bash "$PLUGIN_PATH/install-composer.sh"
}

cd "$PLUGIN_PATH" && composer install

wpcs_path="$PLUGIN_PATH/wpcs"
if [ ! -d "$wpcs_path" ]
then
  cd "$PLUGIN_PATH" && git clone -b master 'https://github.com/WordPress/WordPress-Coding-Standards.git' "$wpcs_path"
  cd "$DOTFILE_FOLDER"
else
  echo "wpcs is installed"
fi

vendor_bin="$PLUGIN_PATH/vendor/bin"
# phpcs setup
php "$vendor_bin/phpcs" --config-set installed_paths "$wpcs_path"
php "$vendor_bin/phpcs" --config-set default_standard "WordPress"

# ln -sf "$PLUGIN_PATH/global.ctags" "$HOME/.ctags"

