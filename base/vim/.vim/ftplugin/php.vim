" php-specific filetype stuff.

" set keywordprg=phpman
"
" nnoremap <leader>k :terminal phpman <cword><cr>
nnoremap <silent><Leader>K :Tnew<CR> :T phpman expand(<cword>)

