#!/usr/bin/env sh
if ! tmux has-session -t dot; then
  tmux new -s dot -d
  tmux rename-window -t dot:1 repo
  tmux send-keys -t dot:1 'cd ~/dotfiles' Enter

  tmux new-window -t dot:2
  tmux rename-window -t dot:2 code
  tmux send-keys -t dot:2 'cd ~/dotfiles' Enter
  tmux send-keys -t dot:2 nvim Enter
fi
tmux attach -t dot
