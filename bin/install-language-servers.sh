#!/usr/bin/env bash
# installing a bunch of language servers and linters.

command -v shellcheck > /dev/null || {
  command -v  > /dev/null && brew install shellcheck
}

command -v npm && {
  npm install -g typescript typescript-language-server pyright dockerfile-language-server-nodejs vscode-langservers-extracted diagnostic-languageserver eslint_d prettier bash-language-server svelte-language-server
}

command -v go && {
  go install golang.org/x/tools/gopls@latest
}
