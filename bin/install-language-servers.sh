#!/usr/bin/env bash
# installing a bunch of language servers and linters.

command -v shellcheck > /dev/null || {
  command -v  > /dev/null && brew install shellcheck
}

command -v npm && {
  npm install -g typescript typescript-language-server pyright dockerfile-language-server-nodejs vscode-langservers-extracted diagnostic-languageserver eslint_d prettier bash-language-server intelephense svelte-language-server
}

command -v go && {
  go install golang.org/x/tools/gopls@latest
}

command -v composer >/dev/null && {
  composer global require -W php-stubs/wordpress-globals php-stubs/wordpress-stubs php-stubs/woocommerce-stubs php-stubs/acf-pro-stubs wpsyntex/polylang-stubs php-stubs/genesis-stubs php-stubs/wp-cli-stubs
}
