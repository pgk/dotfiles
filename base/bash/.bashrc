# ~/.bashrc: executed by bash(1) for non-login shells.
# see /usr/share/doc/bash/examples/startup-files (in the package bash-doc)
# for examples

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# source ~/.bashrc.before.sh if exists.
if [ -f ~/.bashrc.before.sh ]; then
    . ~/.bashrc.before.sh
fi

unameres="$(uname -s)"
case "${unameres}" in
    Linux*)     MYOS=linux;;
    Darwin*)    MYOS=darwin;;
    CYGWIN*)    MYOS=cygwin;;
    MINGW*)     MYOS=mingw;;
    *)          MYOS="unknown:${unameres}"
esac

# source globals
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

## variables
###############################################

GIT_PS1_SHOWUPSTREAM="auto"
GIT_PS1_SHOWCOLORHINTS="yes"
export RANGER_LOAD_DEFAULT_RC=FALSE
# The default editor
export EDITOR=vim
export LC_ALL="en_US.UTF-8"

## Colors
##
WHITE="\[\033[01;00m\]"
RED="\[\033[01;31m\]"
YELLOW="\[\033[01;33m\]"
GREEN="\[\033[0;32m\]"
LIGHT_GREEN="\[\033[1;32m\]"
BLUE="\[\033[01;34m\]"
GRAY="\[\033[1;30m\]"
LIGHT_GRAY="\[\033[0;37m\]"
CYAN="\[\033[0;36m\]"
LIGHT_CYAN="\[\033[1;36m\]"
NO_COLOR="\[\033[0m\]"

E_RED="\033[01;31m"
E_NO_COLLOR="\033[0m"


export CLICOLOR=1
export LSCOLORS=ExFxBxDxCxegedabagacad

if [ -f ~/dotfiles/base/bash/envvars.sh ]; then
    . ~/dotfiles/base/bash/envvars.sh
fi

if [ -f ~/.envvars.sh ]; then
    . ~/.envvars.sh
fi

# Source the git-prompt.sh
if [ -f "$HOME/dotfiles/base/bash/git-prompt.sh" ]; then
    . "$HOME/dotfiles/base/bash/git-prompt.sh"
fi

# Source the fossil prompt
if [ -f "$HOME/dotfiles/base/bash/fossil-prompt.sh" ]; then
    . "$HOME/dotfiles/base/bash/fossil-prompt.sh"
fi


# don't put duplicate lines or lines starting with space in the history.
# See bash(1) for more options
HISTCONTROL=ignoreboth

# append to the history file, don't overwrite it
shopt -s histappend

# for setting history length see HISTSIZE and HISTFILESIZE in bash(1)
HISTSIZE=10000
HISTFILESIZE=20000

# check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# If set, the pattern "**" used in a pathname expansion context will
# match all files and zero or more directories and subdirectories.
#shopt -s globstar

# make less more friendly for non-text input files, see lesspipe(1)
[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "${debian_chroot:-}" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# set a fancy prompt (non-color, unless we know we "want" color)
case "$TERM" in
    xterm-color|*-256color) color_prompt=yes;;
esac

# uncomment for a colored prompt, if the terminal has the capability; turned
# off by default to not distract the user: the focus in a terminal window
# should be on the output of commands, not on the prompt
force_color_prompt=yes

if [ -n "$force_color_prompt" ]; then
  if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
    # We have color support; assume it's compliant with Ecma-48
    # (ISO/IEC-6429). (Lack of such support is extremely rare, and such
    # a case would tend to support setf rather than setaf.)
    color_prompt=yes
  else
    color_prompt=
  fi
fi


#-------------------------------------------------------------
# Shell Prompt - for many examples, see:
#       http://www.debian-administration.org/articles/205
#       http://www.askapache.com/linux/bash-power-prompt.html
#       http://tldp.org/HOWTO/Bash-Prompt-HOWTO
#       https://github.com/nojhan/liquidprompt
#-------------------------------------------------------------

if [ "$color_prompt" = yes ]; then
    PS1='\[\033[01;36m\][ ${debian_chroot:+($debian_chroot)}\[\033[0m\]\u\[\033[0m\]@\[\033[0m\]\h\[\033[01;32m\] | \[\033[0m\]\w\[\033[00m\] \[\033[01;36m\]]\[\033[01;0m\]$(__git_ps1 " (%s)")$(__fossil_ps1 " (%s)")\[\033[36m\]\$ \[\033[0m\]'
else
    PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w-> '
fi
unset color_prompt force_color_prompt

# If this is an xterm set the title to user@host:dir
case "$TERM" in
xterm*|rxvt*)
    PS1="\[\e]0;${debian_chroot:+($debian_chroot)}\u@\h: \w\a\]$PS1"
    ;;
*)
    ;;
esac

# {{ Functions
if [ -f ~/dotfiles/base/bash/funcs.sh ]; then
    . ~/dotfiles/base/bash/funcs.sh
fi

# {{ Alias definitions.

if [ -f ~/dotfiles/base/bash/aliases.sh ]; then
    . ~/dotfiles/base/bash/aliases.sh
fi

# You may want to put all your additions into a separate file like
# ~/.bash_aliases, instead of adding them here directly.
# See /usr/share/doc/bash-doc/examples in the bash-doc package.
if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi


# {{ Completion

# enable programmable completion features (you don't need to enable
# this, if it's already enabled in /etc/bash.bashrc and /etc/profile
# sources /etc/bash.bashrc).
if [ -f /usr/share/bash-completion/bash_completion ]; then
  . /usr/share/bash-completion/bash_completion
elif [ -f /etc/bash_completion ]; then
  . /etc/bash_completion
fi

[ -d /usr/local/opt/fzf/shell ] && {
  . /usr/local/opt/fzf/shell/completion.bash
  . /usr/local/opt/fzf/shell/key-bindings.bash
}

if [ -f /usr/share/doc/fzf/examples/key-bindings.bash ]; then
  source /usr/share/doc/fzf/examples/key-bindings.bash
fi

if [ -f /usr/share/doc/fzf/examples/completion.bash ]; then
  source /usr/share/doc/fzf/examples/completion.bash
fi


if [ -f /usr/local/etc/bash_completion ]; then
  . /usr/local/etc/bash_completion
fi

if type brew &>/dev/null
then
  HOMEBREW_PREFIX="$(brew --prefix)"
  if [[ -r "${HOMEBREW_PREFIX}/etc/profile.d/bash_completion.sh" ]]
  then
    source "${HOMEBREW_PREFIX}/etc/profile.d/bash_completion.sh"
  else
    for COMPLETION in "${HOMEBREW_PREFIX}/etc/bash_completion.d/"*
    do
      [[ -r "${COMPLETION}" ]] && source "${COMPLETION}"
    done
  fi
fi


if [ -f ~/dotfiles/base/bash/.profile ]; then
    . ~/dotfiles/base/bash/.profile
fi

if [ -d "$HOME/dotfiles/base/phpdev/bin" ]; then
    # phpdev preecedence over system bin.
    export PATH="$HOME/dotfiles/base/phpdev/bin:$PATH"
fi

# for dir in "$HOME"/dotfiles/plugins/*/; do
#     if [ -d "$dir/bin" ]; then
#       export PATH="$PATH:$dir/bin"
#     fi
# done

if [ -d "$HOME/dotfiles/plugins/dotfiles-priv/bin" ]; then
    # phpdev preecedence over system bin.
    export PATH="$HOME/dotfiles/plugins/dotfiles-priv/bin:$PATH"
fi
# export PATH="/usr/local/opt/php@7.4/bin:$PATH"
# export PATH="/usr/local/opt/php@7.4/sbin:$PATH"

if [ -d "$HOME/public_html/bin" ]; then
    # custom server bin precedence over system bin.
    export PATH="$HOME/public_html/bin:$PATH"
fi

if [ -d "$HOME/.local/bin" ]; then
    # custom server bin precedence over system bin.
    export PATH="$HOME/.local/bin:$PATH"
fi

if [ -d "$HOME/bin/platform-tools" ]; then
    # add android platform tools.
    export PATH="$HOME/bin/platform-tools:$PATH"
fi

if [ -d "$HOME/dev/pgk_infrastructure/bin" ]; then
    # add infra bin.
    export PATH="$HOME/dev/pgk_infrastructure/bin:$PATH"
fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# [ -d "$HOME/dev/vagrant-docker-engine" ] && {
#   export DOCKER_HOST=tcp://docker.local:2375
# }
