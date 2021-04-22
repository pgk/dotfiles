
function! EditStandups()
  :e ~/Sync/docs/standups.md
  :normal gg
endfunction

command! Standup call EditStandups()
