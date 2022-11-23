#!/bin/bash
# enable color support of ls and also add handy aliases
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    #alias dir='dir --color=auto'
    #alias vdir='vdir --color=auto'

    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# colored GCC warnings and errors
#export GCC_COLORS='error=01;31:warning=01;35:note=01;36:caret=01;32:locus=01:quote=01'

# some more ls aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'


alias rmi='rm -i'
alias cpi='cp -i'
alias mvi='mv -i'
# -> Prevents accidentally clobbering files.
alias mkdir='mkdir -p'

alias h='history'
alias j='jobs -l'
alias whichv='type -a'
alias tw='twiki ~/Sync/docs/wikis/dev --listen port=8081'

# Pretty-print of some PATH variables:
alias path='echo -e ${PATH//:/\\n}'
alias libpath='echo -e ${LD_LIBRARY_PATH//:/\\n}'


alias du='du -kh'    # Makes a more readable output.
alias df='df -kTh'

alias lx='ls -lXB'         #  Sort by extension.
alias lk='ls -lSr'         #  Sort by size, biggest last.
alias lt='ls -ltr'         #  Sort by date, most recent last.
alias lc='ls -ltcr'        #  Sort by/show change time,most recent last.
alias lu='ls -ltur'        #  Sort by/show access time,most recent last.

alias ll="ls -lvFA"
alias lm='ll |more'        #  Pipe through 'more'
alias lr='ll -R'           #  Recursive ls.
alias la='ll'           #  Show hidden files.

alias ureload='xrdb -merge ~/.Xresources'
alias evimrc='vim ~/dotfiles/.vimrc'
alias edit_dotfiles='vim ~/dotfiles'
alias lockme='i3lock -c 000000'
alias locksuspend='i3lock -c 000000 && echo mem /sys/power/state'
alias lvgaon='xrandr --output VGA-1 --auto --right-of LVDS-1'
alias lvgaoff='xrandr --output VGA-1 --off'
alias kbd_rate='xset r rate 150 50'

command -v nvim > /dev/null 2>&1 && {
  alias vim=nvim
}

# Add an "alert" alias for long running commands.  Use like so:
#   sleep 10; alert
alias alert='notify-send --urgency=low -i "$([ $? = 0 ] && echo terminal || echo error)" "$(history|tail -n1|sed -e '\''s/^\s*[0-9]\+\s*//;s/[;&|]\s*alert$//'\'')"'


alias evrc='vim ~/.vimrc'
alias ebrc='vim ~/.bashrc'
alias essh='vim ~/dotfiles/base/ssh/config'
alias ehosts='vim ~/dotfiles/base/hosts/hosts'

alias brc='source ~/.bashrc'
alias cdot='cd ~/dotfiles'
alias dot='tms ~/dotfiles'
alias dotinstall='bash ~/dotfiles/install.sh'
alias dotih='sudo bash ~/dotfiles/base/hosts/install.sh'
alias dotiu='sudo bash ~/dotfiles/base/unison/install.sh'
alias dev='cd ~/dev'
alias dl='cd ~/Downloads'
alias desk='cd ~/Desktop'
alias fo='fossil'
alias ggfp='git fetch --prune origin'
alias ggc='git commit'
alias ggpr='git pull --rebase'
alias ggs='git status'
alias site='cd ~/dev/kountanis.com'
alias standup='vim ~/Sync/docs/standups.md'
alias vihosts='sudo vim /etc/hosts'
alias vi=vim
alias v=vim
alias g=git
alias uniwatch='unison -ui text -repeat watch'
alias wpcom='tms ~/dev/wpcom_sandbox/wpcom/public_html wpcom'
alias cwpcom='cd ~/dev/wpcom_sandbox/wpcom/public_html'
alias grav='cd ~/dev/gravatar_sandbox/public_html'
alias ωιμ='vim'

