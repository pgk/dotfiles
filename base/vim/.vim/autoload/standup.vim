if exists('g:loaded_standup')
  finish
endif
let g:loaded_standup = 1

function! standup#edit()
  :e ~/Sync/docs/standups.md
  :normal gg
endfunction
