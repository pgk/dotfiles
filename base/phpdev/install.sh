#!/usr/bin/env bash
# coding: utf-8

set -e

full_path=$(realpath "$0")
PLUGIN_PATH=$(dirname "$full_path")

echo "$PLUGIN_PATH"
echo "$full_path"

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

INSTALL_PATH="$HOME/dev/phpdev"
mkdir -p "$INSTALL_PATH"

cp  -f "$PLUGIN_PATH/composer.json" "$INSTALL_PATH/"
cp  -f "$PLUGIN_PATH/composer.lock" "$INSTALL_PATH/"
cp  -f "$PLUGIN_PATH/phpcs.xml" "$INSTALL_PATH/"

cd "$INSTALL_PATH" && composer install

wpcs_path="$INSTALL_PATH/wpcs"
if [ ! -d "$wpcs_path" ]
then
  git clone -b master 'https://github.com/WordPress/WordPress-Coding-Standards.git' "$wpcs_path"
  cd "$DOTFILE_FOLDER"
else
  echo "wpcs is installed"
fi

phpactor_path="$INSTALL_PATH/phpactor"
if [ ! -d "$phpactor_path" ]
then
  git clone -b master 'https://github.com/phpactor/phpactor.git' "$phpactor_path"
  cd $phpactor_path && composer install
  cd "$DOTFILE_FOLDER"
else
  echo "phpactor is installed"
  # cd $phpactor_path && git pull
  # cd $phpactor_path && composer install
  # cd "$DOTFILE_FOLDER"
fi

vendor_bin="$INSTALL_PATH/vendor/bin"
# phpcs setup
php "$vendor_bin/phpcs" --config-set installed_paths "$wpcs_path"
php "$vendor_bin/phpcs" --config-set default_standard "WordPress"

ln -sf "$INSTALL_PATH/phpactor/bin/phpactor" "$HOME/bin/phpactor"

