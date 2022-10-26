" Statusline setup. If airline is around we will use that, otherwise fallback
" to something sane.
if (exists('g:loaded_airline') && g:loaded_airline)
  let g:airline_theme='molokai'
  let g:airline#extensions#tagbar#enabled = 0
else
  " Status line setup
  function! GitBranch()
    return system("command -v git > /dev/null 2>&1 && git rev-parse --abbrev-ref HEAD 2>/dev/null | tr -d '\n'")
  endfunction

  function! StatuslineGit()
    let l:branchname = GitBranch()
    return strlen(l:branchname) > 0?'  '.l:branchname.' ':''
  endfunction

  set statusline=
  set statusline+=%#PmenuSel#
  set statusline+=%{StatuslineGit()}
  set statusline+=%#LineNr#
  set statusline+=\ %f
  set statusline+=\ %m
  set statusline+=%=
  set statusline+=%#CursorColumn#
  set statusline+=\ %y
  set statusline+=\ %{&fileencoding?&fileencoding:&encoding}
  set statusline+=\[%{&fileformat}\]
  set statusline+=\ %p%%
  set statusline+=\ %l:%c
  set statusline+=\ 
  " End Statusline
endif
