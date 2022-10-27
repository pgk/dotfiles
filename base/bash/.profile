if [ -d "$HOME/.local/bin" ]; then
  export PATH="$HOME/.local/bin:$PATH";
fi

if [ -d "$HOME/common/bin" ]; then
  export PATH="$PATH:$HOME/common/bin";
fi

if [ -d "$HOME/bin" ]; then
  export PATH="$HOME/bin:$PATH";
fi

if [ -d "$HOME/dev/go" ]; then
  export GOPATH="$HOME/dev/go"
else
  export GOPATH="$HOME/go"
fi

export PATH="$GOPATH/bin:$PATH"

export PATH="$HOME/.cargo/bin:$PATH"
export PATH="$HOME/dotfiles/bin:$PATH"

if [ -d "/usr/local/lib/ruby/gems/2.6.0/bin" ]; then
  export PATH="$PATH:/usr/local/lib/ruby/gems/2.6.0/bin"
fi

if [ -d /usr/local/opt/ruby/bin ]; then
  export PATH="/usr/local/opt/ruby/bin:$PATH"
fi

if [ -f "$HOME/.dotprofile" ]; then
  source "$HOME/.dotprofile"
fi

if [ -d "$HOME/dev/plan9port" ]; then
  export PLAN9="$HOME/dev/plan9port"
  export PATH="$PATH:$PLAN9/bin"
fi

if [ -d "/usr/local/lib/ruby/gems/2.7.0/bin" ]; then
  export PATH="/usr/local/lib/ruby/gems/2.7.0/bin:$PATH"
fi

if [ -f "$HOME/dotfiles/.dotfilerc" ]; then
  source "$HOME/dotfiles/.dotfilerc"
fi

if [ -f "$HOME/.privaterc.sh" ]; then
    source "$HOME/.privaterc.sh"
fi

# opam configuration
test -r "$HOME/.opam/opam-init/init.sh" && . "$HOME/.opam/opam-init/init.sh" > /dev/null 2> /dev/null || true

if [ -f "$HOME/dotfiles/.bash_aliases" ]; then
    source "$HOME/dotfiles/.bash_aliases"
fi

export BYOBU_PREFIX="/usr/local"
export PROMPT='${ret_status} [%M] %{$fg[cyan]%}%c%{$reset_color%} $(git_prompt_info)'

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

[ -d "$HOME/.nimble/bin" ] && export PATH="$HOME/.nimble/bin:$PATH"
