# Functions

# svn diff with colors!! ht: donncha.
function svndiff () {
  svn diff $@ | colordiff | less -R;
}

# FZF

# Open a dev project.
odev() {
  cd "$(find ~/dev -type d -maxdepth 2 | fzf)" && "$EDITOR"
}
