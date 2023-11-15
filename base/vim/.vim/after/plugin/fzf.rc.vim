if !exists('g:loaded_fzf')
  finish
endif

if !exists('g:loaded_fzf_vim')
  finish
endif

" Add shortcut for echoing result back to current buffer.
let g:fzf_action = {
  \ 'ctrl-t': 'tab split',
  \ 'ctrl-x': 'split',
  \ 'ctrl-v': 'vsplit',
  \ 'ctrl-o': ':r !echo',
  \ 'ctrl-q': 'fill_quickfix',
  \ 'ctrl-y': {lines -> setreg('*', join(lines, "\n"))}}

" Set ag for ack.vim and fzf
if executable('ag')
  let g:ackprg = 'ag --vimgrep'
  let $FZF_DEFAULT_COMMAND = 'ag --hidden --ignore .git -g ""'
else
  let $FZF_DEFAULT_COMMAND = "find . -type f -not -path '*/\.git/*'"
endif

" nnoremap <silent> <leader>f <cmd>Files<cr>
nnoremap <silent> <leader>ff :FZF<cr>
nnoremap <silent> <leader>fg :GitFiles<cr>
nnoremap <silent> <leader>fl :Lines<cr>
nnoremap <silent> <leader>fb :Buffers<cr>
nnoremap <silent> <leader>fbt :BTags<cr>
nnoremap <silent> <leader>ft :Tags<cr>


if has('nvim') && !exists('g:loaded_cmp')
  " Insert mode completion
  imap <c-x><c-k> <plug>(fzf-complete-word)
  imap <c-x><c-f> <plug>(fzf-complete-path)
  imap <c-x><c-l> <plug>(fzf-complete-line)
endif

if executable('rg')
  nnoremap <silent><Leader>a :Rg<cr>
  nnoremap <silent><leader>aa :Rg <C-R><C-W><CR>
elseif executable('ag')
  nnoremap <silent><Leader>a :Ag<cr>
  nnoremap <silent><leader>aa :Ag <C-R><C-W><CR>
endif

