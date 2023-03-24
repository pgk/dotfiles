#!/usr/bin/env bash

set -e

command -v docker || {
	echo "docker not present."
	exit 1
}

DOTFILES_CONTAINERS_DIR="$HOME/dotfiles/bin"
DC_PHPCS_DOCKERFILE="$DOTFILES_CONTAINERS_DIR/phpcontainers/phpcs"

docker build -t pgk/phpcs-wordpress "$DC_PHPCS_DOCKERFILE"
