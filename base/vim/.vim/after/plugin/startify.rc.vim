if !exists('g:loaded_startify')
  finish
endif

" Startify
let g:startify_session_dir = '~/.vim/session'
let g:startify_custom_header = [
      \ '             _',
      \ ' _ __   __ _| | __',
      \ '|  _ \ / _  | |/ / ',
      \ '| |_) | (_| |   <',
      \ '|  __/ \__  |_|\_\',
      \ '|_|    |___/',
      \]
let g:startify_files_number = 5
let g:startify_commands = [
    \ ':help reference',
    \ {'s': [' Standup', ':Standup']},
    \ {'v': [' Edit .virmc', ':Evimrc']},
    \ ]
